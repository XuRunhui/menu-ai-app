"""Username/password registration and login with an httpOnly session cookie."""

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import client_ip
from app.core.security import (
    create_session_token,
    decode_session_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.db.session import get_db
from app.models.auth import (
    AuthConfigResponse,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

SESSION_COOKIE = "menuist_session"
MAX_FAILED_LOGINS = 10
FAILED_LOGIN_WINDOW_SECONDS = 15 * 60

_failed_logins: dict[str, deque[float]] = defaultdict(deque)
_failed_lock = threading.Lock()


def _recent_failures(key: str, now: float) -> deque[float]:
    attempts = _failed_logins[key]
    while attempts and now - attempts[0] > FAILED_LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    return attempts


def reset_login_throttle() -> None:
    """Clear failed-login state (used by tests)."""
    with _failed_lock:
        _failed_logins.clear()


def _set_session_cookie(response: Response, request: Request, user_id: int) -> None:
    # Behind HTTPS proxies (e.g. Hugging Face) the backend itself sees plain HTTP.
    is_https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "").startswith("https")
    )
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user_id),
        max_age=settings.auth_session_days * 24 * 3600,
        httponly=True,
        secure=is_https,
        samesite="lax",
        path="/",
    )


def require_accounts() -> None:
    """Dependency: account endpoints respond 404 while AUTH_ENABLED is off (guest-only demo)."""
    if not settings.auth_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Accounts are turned off")


def session_user_id(request: Request) -> int | None:
    """User id from the session cookie without touching the database (used for request logs)."""
    token = request.cookies.get(SESSION_COOKIE)
    return decode_session_token(token) if token else None


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Dependency: the signed-in user, or None for anonymous visitors (always None with accounts off)."""
    if not settings.auth_enabled:
        return None
    user_id = session_user_id(request)
    return db.get(User, user_id) if user_id is not None else None


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    """Dependency: the signed-in user, or 401."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    return user


def _unique_username(db: Session, email: str | None, display_name: str | None) -> str:
    """Derive an available username like 'jane.doe' or 'jane.doe2' from a Google profile."""
    seed = (email or "").split("@")[0] or display_name or "user"
    base = re.sub(r"[^a-z0-9_.-]", "", seed.lower())[:28] or "user"
    base = base if len(base) >= 3 else f"{base}user"
    candidate, suffix = base, 1
    while db.scalar(select(User.id).where(User.username == candidate)) is not None:
        suffix += 1
        candidate = f"{base[:32 - len(str(suffix))]}{suffix}"
    return candidate


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_accounts)])
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    """Create an account and sign the user in."""
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken")

    db.refresh(user)
    logger.info("[auth] Registered user id=%s", user.id)
    _set_session_cookie(response, request, user.id)
    return user


@router.post("/login", response_model=UserResponse, dependencies=[Depends(require_accounts)])
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    """Verify credentials and set the session cookie."""
    throttle_key = f"{client_ip(request)}::{payload.username}"
    now = time.time()
    with _failed_lock:
        if len(_recent_failures(throttle_key, now)) >= MAX_FAILED_LOGINS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Please wait 15 minutes and try again.",
            )

    user = db.scalar(select(User).where(User.username == payload.username))
    if not verify_password(payload.password, user.password_hash if user else None):
        with _failed_lock:
            _recent_failures(throttle_key, now).append(now)
        # Same message for unknown user and wrong password, so usernames can't be probed.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    with _failed_lock:
        _failed_logins.pop(throttle_key, None)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    _set_session_cookie(response, request, user.id)
    return user


@router.get("/config", response_model=AuthConfigResponse)
def auth_config() -> AuthConfigResponse:
    """Public auth settings the frontend needs (e.g. whether to show Google sign-in)."""
    return AuthConfigResponse(
        auth_enabled=settings.auth_enabled,
        google_client_id=(settings.google_oauth_client_id or None) if settings.auth_enabled else None,
    )


def verify_google_credential(credential: str) -> dict:
    """Verify a Google Identity Services ID token; raises ValueError when invalid."""
    return google_id_token.verify_oauth2_token(
        credential, google_requests.Request(), settings.google_oauth_client_id
    )


@router.post("/google", response_model=UserResponse, dependencies=[Depends(require_accounts)])
def google_login(
    payload: GoogleLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    """Sign in (or sign up) with a Google ID token from the Google Identity Services button."""
    if not settings.google_oauth_client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google sign-in is not configured")

    try:
        claims = verify_google_credential(payload.credential)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google sign-in failed")
    if not claims.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account email is not verified")

    user = db.scalar(select(User).where(User.google_sub == claims["sub"]))
    if user is None:
        user = User(
            username=_unique_username(db, claims.get("email"), claims.get("name")),
            email=claims.get("email"),
            google_sub=claims["sub"],
        )
        db.add(user)
        logger.info("[auth] Created account from Google sign-in")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, request, user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_accounts)])
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserResponse, dependencies=[Depends(require_accounts)])
def me(user: User = Depends(get_current_user)) -> User:
    return user
