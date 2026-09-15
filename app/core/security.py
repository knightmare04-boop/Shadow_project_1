"""Password hashing and JWT helpers.

Uses ``bcrypt`` directly rather than ``passlib`` — passlib is unmaintained and
its bcrypt backend detection breaks against bcrypt>=4.1 (removed
``__about__`` attribute triggers a confusing false "password too long"
error). Direct bcrypt is simpler and is what current FastAPI security
guidance recommends now that passlib has no active maintainer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

# bcrypt's own hard limit — never silently truncate a password; reject long
# ones explicitly instead (a 200-char password should be an error, not a
# quietly-shortened hash that only checks the first 72 bytes).
_MAX_PASSWORD_BYTES = 72


def hash_password(plain_password: str) -> str:
    encoded = plain_password.encode("utf-8")
    if len(encoded) > _MAX_PASSWORD_BYTES:
        raise ValueError(f"password exceeds bcrypt's {_MAX_PASSWORD_BYTES}-byte limit")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    encoded = plain_password.encode("utf-8")
    if len(encoded) > _MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash (e.g. legacy/corrupt row) — never raise into an auth path.
        return False


def create_access_token(*, subject: str, role: str, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
