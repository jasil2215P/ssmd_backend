from datetime import datetime, timedelta
from typing import Annotated
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session
import hashlib
import os

from auth import (
    ALGORITHM,
    JWT_REFRESH_SECRET,
    JWT_REFRESH_TOKEN_EXPIRY_DAYS,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_user,
)
from db import get_db
from models import RefreshToken, TokenResponse

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/tokens",
    response_model=TokenResponse,
    summary="Login and create auth tokens",
)
@router.post("/token", include_in_schema=False, response_model=TokenResponse)
async def login(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(form.username, form.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
            detail="Incorrect username or password",
        )

    refresh_token_expires_at = datetime.now() + timedelta(
        days=JWT_REFRESH_TOKEN_EXPIRY_DAYS
    )
    access_token = create_access_token(username=user.username, role=user.role)
    refresh_token = create_refresh_token(
        username=user.username, expires=refresh_token_expires_at
    )

    token_hash = hash_token(refresh_token)
    refresh_token_data = RefreshToken(
        token_hash=token_hash,
        user_id=user.id,
        expires_at=refresh_token_expires_at,
    )

    db.add(refresh_token_data)
    db.commit()

    is_prod = os.getenv("ENVIRONMENT") == "production"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=JWT_REFRESH_TOKEN_EXPIRY_DAYS * 24 * 60 * 60,
    )
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.post(
    "/auth/tokens/refresh",
    response_model=TokenResponse,
    summary="Refresh auth tokens",
)
@router.post("/refresh", include_in_schema=False, response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
    db: Session = Depends(get_db),
):
    credential_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
        detail="Failed to authenticate user",
    )
    cleanup_refresh_tokens(db)

    if not refresh_token:
        raise credential_error

    try:
        decoded = jwt.decode(refresh_token, JWT_REFRESH_SECRET, [ALGORITHM])
        username = decoded.get("sub")
        if decoded.get("type") != "refresh" or not username:
            raise credential_error
    except JWTError:
        raise credential_error

    now = datetime.now()
    if not check_and_delete_refresh_token(hash_token(refresh_token), db, now):
        raise credential_error

    user = get_user(username, db=db)
    if not user:
        raise credential_error

    refresh_token_expires_at = now + timedelta(days=JWT_REFRESH_TOKEN_EXPIRY_DAYS)
    access_token = create_access_token(username=user.username, role=user.role)
    new_refresh_token = create_refresh_token(
        username=user.username,
        expires=refresh_token_expires_at,
    )
    token_hash = hash_token(new_refresh_token)
    refresh_token_data = RefreshToken(
        token_hash=token_hash,
        user_id=user.id,
        expires_at=refresh_token_expires_at,
    )

    db.add(refresh_token_data)
    db.commit()

    is_prod = os.getenv("ENVIRONMENT") == "production"
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=JWT_REFRESH_TOKEN_EXPIRY_DAYS * 24 * 60 * 60,
    )
    return TokenResponse(access_token=access_token, token_type="bearer")


def check_and_delete_refresh_token(
    refresh_token_hash: str, db: Session, now: datetime
) -> bool:
    deleted = (
        db.query(RefreshToken)
        .where(
            RefreshToken.token_hash == refresh_token_hash,
            RefreshToken.expires_at >= now,
        )
        .delete()
    )
    db.commit()

    if deleted == 0:
        return False
    else:
        return True


def hash_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def cleanup_refresh_tokens(db: Session):
    db.query(RefreshToken).where(RefreshToken.expires_at < datetime.now()).delete()
