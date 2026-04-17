import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

from fastapi import Response, Request, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup environment before imports
os.environ["JWT_SECRET"] = "test-secret"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret"

from main import app
from db import Base, get_db
from models import Users, RefreshToken
from auth import (
    create_access_token,
    get_current_user,
    hash_token,
    password_hash,
)
from routes.auth.token import logout

# Use a local engine for these tests
LOCAL_DB_URL = "sqlite:///:memory:"
local_engine = create_engine(LOCAL_DB_URL, connect_args={"check_same_thread": False})
LocalSessionLocal = sessionmaker(bind=local_engine)


def override_get_db():
    db = LocalSessionLocal()
    try:
        yield db
    finally:
        db.close()


class LogoutTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=local_engine)
        app.dependency_overrides[get_db] = override_get_db

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=local_engine)
        local_engine.dispose()

    async def asyncSetUp(self):
        Base.metadata.drop_all(bind=local_engine)
        Base.metadata.create_all(bind=local_engine)
        self.db = LocalSessionLocal()

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

    @patch("routes.auth.token.redis_client", new_callable=AsyncMock)
    async def test_logout_success(self, mock_redis):
        # Setup: Create tokens
        access_token = create_access_token("testuser", "teacher")
        refresh_token = "fake-refresh-token"
        rt_hash = hash_token(refresh_token)
        
        db_rt = RefreshToken(
            token_hash=rt_hash,
            user_id=self.test_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        self.db.add(db_rt)
        self.db.commit()

        # Mock request and response
        request = AsyncMock(spec=Request)
        request.headers = {"Authorization": f"Bearer {access_token}"}
        
        response = Response()
        
        # Act
        result = await logout(
            response=response,
            request=request,
            current_user=self.test_user,
            db=self.db,
            refresh_token=refresh_token
        )

        # Assert
        self.assertEqual(result.status, "success")
        
        # Verify access token blacklisted in Redis
        mock_redis.setex.assert_called_once()
        args, _ = mock_redis.setex.call_args
        self.assertTrue(args[0].startswith("blacklist:"))
        self.assertGreater(args[1], 0) # TTL should be > 0
        self.assertEqual(args[2], "1")

        # Verify refresh token deleted from DB
        db_rt_after = self.db.query(RefreshToken).filter(RefreshToken.token_hash == rt_hash).first()
        self.assertIsNone(db_rt_after)

        # Verify refresh token cookie cleared
        set_cookie_header = response.headers.get("set-cookie")
        self.assertIn('refresh_token=""', set_cookie_header)
        self.assertIn("Max-Age=0", set_cookie_header)

    @patch("routes.auth.token.redis_client", new_callable=AsyncMock)
    async def test_logout_no_refresh_token(self, mock_redis):
        access_token = create_access_token("testuser", "teacher")
        
        request = AsyncMock(spec=Request)
        request.headers = {"Authorization": f"Bearer {access_token}"}
        response = Response()
        
        result = await logout(
            response=response,
            request=request,
            current_user=self.test_user,
            db=self.db,
            refresh_token=None
        )

        self.assertEqual(result.status, "success")
        mock_redis.setex.assert_called_once()
        
        # No cookie should be cleared if none provided
        self.assertIsNone(response.headers.get("set-cookie"))

    @patch("auth.redis_client", new_callable=AsyncMock)
    async def test_get_current_user_rejection_after_logout(self, mock_redis):
        access_token = create_access_token("testuser", "teacher")
        
        # Mock redis.exists to return 1 (True) for the blacklisted token
        mock_redis.exists.return_value = 1
        
        with self.assertRaises(HTTPException) as context:
            await get_current_user(db=self.db, token=access_token)
        
        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Failed to authenticate user")
        
        # Verify redis.exists was called with the correct hash
        token_hash = hash_token(access_token)
        mock_redis.exists.assert_called_with(f"blacklist:{token_hash}")


if __name__ == "__main__":
    unittest.main()
