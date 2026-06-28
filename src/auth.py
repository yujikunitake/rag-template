# --- Config ---
import os
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt as _bcrypt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from jose import JWTError, jwt
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User

try:
    SECRET_KEY = os.environ["JWT_SECRET_KEY"]
except KeyError:
    raise RuntimeError(
        "JWT_SECRET_KEY environment variable is not set. "
        "Set a secure value before starting the application."
    )
ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE = timedelta(minutes=15)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)
SECURE_COOKIES = os.environ.get("ENV") != "development"

# --- Utilities ---

limiter = Limiter(key_func=get_remote_address)

# pre-computed hash to prevent timing attack when user does not exist
_DUMMY_HASH = _bcrypt.hashpw(b"__dummy__", _bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(user_id: str, typ: str, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    return jwt.encode({"sub": user_id, "exp": expire, "typ": typ}, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    return _create_token(user_id, "access", expires_delta or ACCESS_TOKEN_EXPIRE)


def create_refresh_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    return _create_token(user_id, "refresh", expires_delta or REFRESH_TOKEN_EXPIRE)


def _decode_token(token: str, expected_typ: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") is None or payload.get("typ") != expected_typ:
            raise HTTPException(status_code=401, detail="invalid token")
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="invalid token")


def _set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        samesite="lax",
        secure=SECURE_COOKIES,
        max_age=int(ACCESS_TOKEN_EXPIRE.total_seconds()),
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        samesite="lax",
        secure=SECURE_COOKIES,
        max_age=int(REFRESH_TOKEN_EXPIRE.total_seconds()),
    )


def _clear_auth_cookies(response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


# --- Dependency ---


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not access_token:
        raise HTTPException(status_code=401, detail="not authenticated")
    user_id = _decode_token(access_token, "access")
    user = db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return user


# --- Router ---

auth_router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@auth_router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse

    user = db.query(User).filter(User.email == body.email).first()

    if not user:
        verify_password(body.password, _DUMMY_HASH)
        raise HTTPException(status_code=401, detail="invalid credentials")

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="invalid credentials")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    response = JSONResponse({"email": user.email, "user_id": str(user.id)})
    _set_auth_cookies(response, access_token, refresh_token)
    return response


@auth_router.post("/refresh")
def refresh(
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    from fastapi.responses import JSONResponse

    if not refresh_token:
        raise HTTPException(status_code=401, detail="not authenticated")

    user_id = _decode_token(refresh_token, "refresh")
    user = db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="user not found")

    access_token = create_access_token(str(user.id))
    response = JSONResponse({"ok": True})
    response.set_cookie("access_token", access_token, httponly=True, samesite="lax")
    return response


@auth_router.post("/logout")
def logout():
    from fastapi.responses import JSONResponse

    response = JSONResponse({"ok": True})
    _clear_auth_cookies(response)
    return response


@auth_router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email, "user_id": current_user.id}
