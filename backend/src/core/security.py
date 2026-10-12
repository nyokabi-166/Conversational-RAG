"""Password hashing and JWT helpers for API authentication."""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 600_000
_DEVELOPMENT_SECRET = "local-development-secret-do-not-use-in-production"
_TOKEN_ALGORITHM = "HS256"
_TOKEN_LIFETIME = timedelta(minutes=60)


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash suitable for storing in the database."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS
    )
    return "$".join(
        (
            _PASSWORD_SCHEME,
            str(_PASSWORD_ITERATIONS),
            salt.hex(),
            digest.hex(),
        )
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password hash, returning False for malformed stored values."""
    try:
        scheme, iterations, salt_hex, digest_hex = stored_hash.split("$", maxsplit=3)
        if scheme != _PASSWORD_SCHEME:
            return False
        iteration_count = int(iterations)
        if iteration_count < 1:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (AttributeError, TypeError, ValueError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iteration_count
    )
    return hmac.compare_digest(actual, expected)


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if secret:
        if len(secret) < 32:
            raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters.")
        return secret
    if os.getenv("APP_ENV", "production").lower() == "development":
        return _DEVELOPMENT_SECRET
    raise RuntimeError("JWT_SECRET_KEY must be set outside development and test.")


def create_access_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed bearer token with an expiration claim."""
    now = datetime.now(timezone.utc)
    claims = {**data, "iat": now, "exp": now + (expires_delta or _TOKEN_LIFETIME)}
    return jwt.encode(claims, _jwt_secret(), algorithm=_TOKEN_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a bearer token, returning None when it is invalid."""
    try:
        claims = jwt.decode(token, _jwt_secret(), algorithms=[_TOKEN_ALGORITHM])
    except (jwt.InvalidTokenError, RuntimeError):
        return None
    return claims if isinstance(claims, dict) else None
