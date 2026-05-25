"""Password hashing and verification utilities.

Uses bcrypt via passlib's CryptContext. Plain-text passwords must never be
stored or logged; callers should hash on registration and verify on login.
"""

from passlib.context import CryptContext

# bcrypt is the default scheme; "auto" marks older hashes for upgrade on verify.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Return a bcrypt hash suitable for persisting on a user record."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Return True if the plain-text password matches the stored hash."""
    return pwd_context.verify(password, hashed_password)
