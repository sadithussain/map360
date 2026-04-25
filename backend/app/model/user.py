"""User ORM model and related helpers."""
import uuid

from app import db


class User(db.Model):
    """Application user persisted in the `users` table."""

    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    hashed_password = db.Column(db.String(256), nullable=False)

    def __repr__(self) -> str:
        return f'<User {self.username}>'
