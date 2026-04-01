from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from auth import JWT_TOKEN_EXPIRY, authenticate_user, create_access_token
from db import get_db
from models import Token

router = APIRouter()


@router.post("/token")
async def login(form: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    user = authenticate_user(form.username, form.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
            detail="Incorrect username or password",
        )
    data = {"sub": user.username, "role": user.role}
    expire_delta = timedelta(minutes=JWT_TOKEN_EXPIRY)
    access_token = create_access_token(data, expire_delta=expire_delta)
    return Token(access_token=access_token, token_type="bearer")
