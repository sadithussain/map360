"""Password hashing and JWT utilities.

Passwords are hashed with bcrypt (using the ``bcrypt`` library directly);
plain-text passwords must never be stored or logged. Access tokens are
application-issued JWTs signed with the secret and algorithm from
:mod:`app.core.config`.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from app.core.config import get_settings

# bcrypt only considers the first 72 bytes of a password, and modern versions
# raise if given more. Inputs are truncated to that limit before hashing, which
# also matches the previous passlib-based behaviour so existing stored hashes
# still verify.
_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(password: str) -> bytes:
    """Encode a password to UTF-8 and cap it at bcrypt's 72-byte limit."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def get_password_hash(password: str) -> str:
    """Return a bcrypt hash suitable for persisting on a user record."""
    hashed = bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Return True if the plain-text password matches the stored hash."""
    try:
        return bcrypt.checkpw(
            _to_bcrypt_bytes(password), hashed_password.encode("utf-8")
        )
    except ValueError:
        # A malformed or unrecognized hash string is treated as a non-match
        # rather than propagating, so callers always receive a clean boolean.
        return False


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
