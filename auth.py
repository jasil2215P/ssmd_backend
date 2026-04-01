from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash
from sqlalchemy import text

from db import get_db
from models import TokenData, UserInDb
from dotenv import load_dotenv
import os

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
password_hash = PasswordHash.recommended()


load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
JWT_TOKEN_EXPIRY = 30
DUMMY_HASH = password_hash.hash("dummy pwd")


def get_current_user(db=Depends(get_db), token: str = Depends(oauth2_scheme)):
    credential_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
        detail="Failed to authenticate user",
    )
    try:
        decoded = jwt.decode(token, JWT_SECRET, [ALGORITHM])
        username = decoded.get("sub")
        if not username:
            raise credential_error
        token_data = TokenData(username=username)
    except JWTError:
        raise credential_error

    user = get_user(username=token_data.username, db=db)
    if not user:
        raise credential_error
    return user


def require_role(role: List[str]):
    def check_role(user=Depends(get_current_user)):
        if user.role not in role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return user

    return check_role


def get_user(username: str, db):
    query = text("""
        SELECT * FROM users WHERE users.username = :username
    """)

    result = db.execute(query, {"username": username}).fetchone()
    if result is None:
        return None
    return UserInDb.model_validate(result._mapping)


def verify_password(plain_password: str, hashed_password: str):
    return password_hash.verify(plain_password, hashed_password)


def authenticate_user(username: str, password: str, db):
    user = get_user(username, db)
    if not user:
        verify_password(password, DUMMY_HASH)
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user


def create_access_token(data, expire_delta: timedelta):
    to_encode = data.copy()
    if expire_delta:
        expire = datetime.now(timezone.utc) + expire_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_token = jwt.encode(to_encode, JWT_SECRET, ALGORITHM)
    return encoded_token
