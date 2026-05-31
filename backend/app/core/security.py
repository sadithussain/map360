"""Password hashing and JWT utilities.

Passwords use bcrypt via passlib's CryptContext; plain-text passwords must never
be stored or logged. Access tokens are application-issued JWTs signed with the
secret and algorithm from :mod:`app.core.config`.
"""

from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# bcrypt is the default scheme; "auto" marks older hashes for upgrade on verify.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Return a bcrypt hash suitable for persisting on a user record."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Return True if the plain-text password matches the stored hash."""
    return pwd_context.verify(password, hashed_password)


def create_access_token(
    subject: str, expires_delta: timedelta | None = None
) -> str:
    """Return a signed JWT access token for the given subject.

    The ``subject`` is stored in the standard ``sub`` claim (typically the
    user's id). Expiry defaults to ``access_token_expire_minutes`` from
    settings unless ``expires_delta`` is provided.
    """
    settings = get_settings()
    expire_delta = expires_delta or timedelta(
        minutes=settings.access_token_expire_minutes
    )
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expire_delta,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token.

    Verifies the signature, algorithm, and expiry. Raises
    :class:`jwt.PyJWTError` (or a subclass) when the token is invalid or
    expired; callers are responsible for translating that into an HTTP error.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
