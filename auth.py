from datetime import datetime, timedelta
from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash

from db import get_db
from models import TokenData, UserInDb
from dotenv import load_dotenv
import os

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/tokens")
password_hash = PasswordHash.recommended()


load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET")
if JWT_SECRET is None:
    raise Exception("JWT_SECRET not set!")

JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET")
if JWT_REFRESH_SECRET is None:
    raise Exception("JWT_REFRESH_SECRET not set!")
if JWT_REFRESH_SECRET == JWT_SECRET:
    raise Exception("JWT_REFRESH_SECRET must differ from JWT_SECRET")

ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRY_MINUTES = 1
JWT_REFRESH_TOKEN_EXPIRY_DAYS = 7
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
        token_type = decoded.get("type")
        if token_type != "access":
            raise credential_error
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
    from models import Users

    result = db.query(Users).filter(Users.username == username).first()
    if result is None:
        return None
    return UserInDb.model_validate(result, from_attributes=True)


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


def create_token(data, expire: datetime, secret):
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    encoded_token = jwt.encode(to_encode, secret, ALGORITHM)
    return encoded_token


def create_access_token(username: str, role: str):
    return create_token(
        {"sub": username, "role": role, "type": "access"},
        datetime.now() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRY_MINUTES),
        JWT_SECRET,
    )


def create_refresh_token(
    username: str,
    expires: datetime | None = None,
):
    if expires is None:
        expires = datetime.now() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRY_DAYS)
    return create_token(
        {"sub": username, "type": "refresh"},
        expires,
        JWT_REFRESH_SECRET,
    )
