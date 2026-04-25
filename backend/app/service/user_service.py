"""User service layer handling registration and authentication."""
import logging

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.model.user import User

logger = logging.getLogger(__name__)


class UserService:
    """Encapsulates user creation and authentication operations."""

    @staticmethod
    def create_user(
        email: str,
        username: str,
        raw_password: str,
        first_name: str | None = None,
        last_name: str | None = None
    ) -> User:
        """Create and persist a new user with a hashed password."""

        email = (email or "").strip().lower()
        username = (username or "").strip()

        if not email or not username or not raw_password:
            raise ValueError("email, username, and password are required.")

        if len(raw_password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        existing_user = User.query.filter(
            or_(User.email == email, User.username == username)
        ).first()

        if existing_user:
            raise ValueError("A user with this email or username already exists.")

        # Store only a one-way hash, never the raw password.
        hashed_password = generate_password_hash(raw_password)

        new_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            hashed_password=hashed_password
        )

        db.session.add(new_user)

        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            logger.warning(
                "IntegrityError on user creation for email=%s username=%s",
                email,
                username,
            )
            raise ValueError(
                "A user with this email or username already exists."
            ) from exc

        return new_user

    @staticmethod
    def verify_user(username: str, raw_password: str) -> User | None:
        """Return the user when credentials are valid; otherwise None."""

        username = (username or "").strip()

        if not username or not raw_password:
            return None

        user = User.query.filter_by(username=username).first()

        if not user:
            return None

        if not check_password_hash(user.hashed_password, raw_password):
            return None

        return user
