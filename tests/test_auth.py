import os
import unittest
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup environment before imports
os.environ["JWT_SECRET"] = "test-secret"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret"

from main import app
from db import Base, get_db
from models import Users, RefreshToken
from auth import (
    ALGORITHM,
    JWT_SECRET,
    JWT_REFRESH_SECRET,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_token,
    get_current_user,
    password_hash,
)
from routes.auth.token import hash_token, login, refresh, cleanup_refresh_tokens

# Use a local engine for these tests to avoid interfering with other tests
LOCAL_DB_URL = "sqlite:///:memory:"
local_engine = create_engine(LOCAL_DB_URL, connect_args={"check_same_thread": False})
LocalSessionLocal = sessionmaker(bind=local_engine)


def override_get_db():
    db = LocalSessionLocal()
    try:
        yield db
    finally:
        db.close()


class AuthTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Register the tables on the local engine
        Base.metadata.create_all(bind=local_engine)
        app.dependency_overrides[get_db] = override_get_db

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=local_engine)
        local_engine.dispose()

    async def asyncSetUp(self):
        # Clear database between tests
        Base.metadata.drop_all(bind=local_engine)
        Base.metadata.create_all(bind=local_engine)
        self.db = LocalSessionLocal()

        # Create a test user
        self.test_user = Users(
            username="testuser",
            password_hash=password_hash.hash("testpassword"),
            role="teacher",
        )
        self.db.add(self.test_user)
        self.db.commit()
        self.db.refresh(self.test_user)

    async def asyncTearDown(self):
        self.db.close()

    # --- Unit Tests for auth.py ---

    def test_authenticate_user_success(self):
        user = authenticate_user("testuser", "testpassword", self.db)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "testuser")

    def test_authenticate_user_wrong_password(self):
        user = authenticate_user("testuser", "wrongpassword", self.db)
        self.assertFalse(user)

    def test_authenticate_user_not_found(self):
        user = authenticate_user("nonexistent", "testpassword", self.db)
        self.assertFalse(user)

    def test_create_access_token(self):
        token = create_access_token("testuser", "teacher")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        self.assertEqual(payload["sub"], "testuser")
        self.assertEqual(payload["role"], "teacher")
        self.assertEqual(payload["type"], "access")
        self.assertIn("exp", payload)

    def test_create_refresh_token(self):
        token = create_refresh_token("testuser")
        payload = jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[ALGORITHM])
        self.assertEqual(payload["sub"], "testuser")
        self.assertEqual(payload["type"], "refresh")
        self.assertIn("exp", payload)

    async def test_get_current_user_valid_token(self):
        with patch("auth.is_token_blacklisted", return_value=False):
            token = create_access_token("testuser", "teacher")
            user = await get_current_user(self.db, token)
            self.assertEqual(user.username, "testuser")

    async def test_get_current_user_expired_token(self):
        with patch("auth.is_token_blacklisted", return_value=False):
            # Create an expired token manually using a very old date to avoid TZ issues
            exp = datetime(2000, 1, 1, tzinfo=timezone.utc)
            token = create_token(
                {"sub": "testuser", "role": "teacher", "type": "access"},
                exp,
                JWT_SECRET
            )
            with self.assertRaises(HTTPException) as context:
                await get_current_user(self.db, token)
            self.assertEqual(context.exception.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(context.exception.detail, "Failed to authenticate user")

    async def test_get_current_user_wrong_token_type(self):
        with patch("auth.is_token_blacklisted", return_value=False):
            # Using a refresh token as an access token
            token = create_refresh_token("testuser")
            with self.assertRaises(HTTPException) as context:
                await get_current_user(self.db, token)
            self.assertEqual(context.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    async def test_get_current_user_invalid_signature(self):
        with patch("auth.is_token_blacklisted", return_value=False):
            token = create_access_token("testuser", "teacher")
            tampered_token = token + "tampered"
            with self.assertRaises(HTTPException) as context:
                await get_current_user(self.db, tampered_token)
            self.assertEqual(context.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    async def test_get_current_user_blacklisted_token(self):
        with patch("auth.is_token_blacklisted", return_value=True):
            token = create_access_token("testuser", "teacher")
            with self.assertRaises(HTTPException) as context:
                await get_current_user(self.db, token)
            self.assertEqual(context.exception.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(context.exception.detail, "Failed to authenticate user")

    # --- Tests for routes/auth/token.py (Direct function calls) ---

    async def test_login_endpoint_success(self):
        response = Response()
        form = OAuth2PasswordRequestForm(username="testuser", password="testpassword")
        
        result = await login(response, form, self.db)
        
        self.assertIsNotNone(result.access_token)
        self.assertEqual(result.token_type, "bearer")
        
        set_cookie_header = response.headers.get("set-cookie")
        self.assertIn("refresh_token=", set_cookie_header)
        refresh_token = set_cookie_header.split("refresh_token=")[1].split(";")[0]
        
        rt_hash = hash_token(refresh_token)
        db_rt = self.db.query(RefreshToken).filter(RefreshToken.token_hash == rt_hash).first()
        self.assertIsNotNone(db_rt)
        self.assertEqual(db_rt.user_id, self.test_user.id)

    async def test_login_endpoint_failure(self):
        response = Response()
        form = OAuth2PasswordRequestForm(username="testuser", password="wrongpassword")
        
        with self.assertRaises(HTTPException) as context:
            await login(response, form, self.db)
        self.assertEqual(context.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    async def test_refresh_endpoint_success(self):
        # Setup: Login to get a refresh token
        response_login = Response()
        form = OAuth2PasswordRequestForm(username="testuser", password="testpassword")
        await login(response_login, form, self.db)
        
        set_cookie_header = response_login.headers.get("set-cookie")
        refresh_token = set_cookie_header.split("refresh_token=")[1].split(";")[0]
        old_rt_hash = hash_token(refresh_token)

        # Sleep to ensure next token has a different 'exp' timestamp
        time.sleep(1.1)

        # Act: Call refresh function
        response_refresh = Response()
        result = await refresh(response_refresh, refresh_token, self.db)
        
        self.assertIsNotNone(result.access_token)
        
        # Verify new refresh token cookie
        new_set_cookie = response_refresh.headers.get("set-cookie")
        self.assertIn("refresh_token=", new_set_cookie)
        new_refresh_token = new_set_cookie.split("refresh_token=")[1].split(";")[0]
        self.assertNotEqual(refresh_token, new_refresh_token)
        
        # Old hash should be deleted
        old_rt_db = self.db.query(RefreshToken).filter(RefreshToken.token_hash == old_rt_hash).first()
        self.assertIsNone(old_rt_db)
        
        # New hash should be present
        new_rt_hash = hash_token(new_refresh_token)
        new_rt_db = self.db.query(RefreshToken).filter(RefreshToken.token_hash == new_rt_hash).first()
        self.assertIsNotNone(new_rt_db)

    async def test_refresh_endpoint_expired_token(self):
        # Setup: Create an expired refresh token manually and put it in DB
        exp = datetime(2000, 1, 1, tzinfo=timezone.utc)
        token = create_token(
            {"sub": "testuser", "type": "refresh"},
            exp,
            JWT_REFRESH_SECRET
        )
        rt_hash = hash_token(token)
        db_rt = RefreshToken(
            token_hash=rt_hash,
            user_id=self.test_user.id,
            expires_at=exp
        )
        self.db.add(db_rt)
        self.db.commit()

        # Act & Assert: Try to refresh with expired token
        response = Response()
        with self.assertRaises(HTTPException) as context:
            await refresh(response, token, self.db)
        self.assertEqual(context.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    async def test_refresh_endpoint_reuse_detection(self):
        # Setup: Login and get a refresh token
        response_login = Response()
        form = OAuth2PasswordRequestForm(username="testuser", password="testpassword")
        await login(response_login, form, self.db)
        set_cookie_header = response_login.headers.get("set-cookie")
        refresh_token = set_cookie_header.split("refresh_token=")[1].split(";")[0]

        # Sleep to ensure next token has a different 'exp' timestamp
        time.sleep(1.1)

        # First refresh (success)
        response_refresh1 = Response()
        await refresh(response_refresh1, refresh_token, self.db)
        
        # Second refresh with SAME old token (failure, as it was deleted from DB)
        response_refresh2 = Response()
        with self.assertRaises(HTTPException) as context:
            await refresh(response_refresh2, refresh_token, self.db)
        self.assertEqual(context.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cleanup_refresh_tokens(self):
        # Setup: One valid, two expired tokens
        now = datetime.now(timezone.utc)
        expired = now - timedelta(days=1)
        valid = now + timedelta(days=1)

        t1 = RefreshToken(token_hash="h1", user_id=self.test_user.id, expires_at=expired)
        t2 = RefreshToken(token_hash="h2", user_id=self.test_user.id, expires_at=expired)
        t3 = RefreshToken(token_hash="h3", user_id=self.test_user.id, expires_at=valid)
        
        self.db.add_all([t1, t2, t3])
        self.db.commit()

        # Act
        cleanup_refresh_tokens(self.db)
        self.db.commit()

        # Assert
        tokens = self.db.query(RefreshToken).all()
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].token_hash, "h3")


if __name__ == "__main__":
    unittest.main()
