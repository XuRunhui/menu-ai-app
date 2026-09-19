"""Password hashing (Argon2id via pwdlib) and signed session tokens (JWT via PyJWT)."""

import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

logger = logging.getLogger(__name__)

_password_hash = PasswordHash.recommended()
# Verified against when the username doesn't exist, so response time doesn't reveal valid usernames.
_DUMMY_HASH = _password_hash.hash(secrets.token_urlsafe(16))

JWT_ALGORITHM = "HS256"

if settings.auth_secret_key:
    _secret_key = settings.auth_secret_key
else:
    _secret_key = secrets.token_urlsafe(32)
    logger.warning("AUTH_SECRET_KEY not set; using a random key (all sessions end on restart)")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Check a password; always spends hashing time, even when there is no stored hash."""
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, password_hash)


def create_session_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.auth_session_days),
    }
    return jwt.encode(payload, _secret_key, algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> int | None:
    """Return the user id from a valid, unexpired token, else None."""
    try:
        payload = jwt.decode(token, _secret_key, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
