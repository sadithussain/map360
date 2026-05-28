"""Application settings loaded from environment variables.

Configuration is read from process environment and an optional ``.env`` file
(see ``backend/.env.example``). Supabase provides the hosted Postgres database
and object storage; authentication is handled by this application, not Supabase
Auth, so JWT settings live here as well.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration.

    Attributes:
        environment: Deployment context, used to toggle debug behaviour.
        database_url: Async SQLAlchemy URL for the Supabase Postgres database.
        supabase_url: Base URL of the Supabase project (used for storage).
        supabase_service_role_key: Server-side key for Supabase Storage access.
        supabase_media_bucket: Storage bucket name for uploaded media.
        jwt_secret_key: Secret used to sign application-issued JWTs.
        jwt_algorithm: Signing algorithm for JWTs.
        access_token_expire_minutes: Lifetime of issued access tokens.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"

    # Supabase Postgres connection. Use the async driver form, e.g.
    # postgresql+asyncpg://postgres:<password>@<host>:5432/postgres
    database_url: PostgresDsn = Field(...)

    # Supabase project + storage (media uploads handled later in the roadmap).
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_media_bucket: str = "media"

    # Application-owned authentication.
    jwt_secret_key: str = Field(..., min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: PostgresDsn) -> PostgresDsn:
        """Ensure the database URL uses an async-capable driver."""
        scheme = value.scheme
        if scheme not in {"postgresql+asyncpg", "postgresql+psycopg"}:
            raise ValueError(
                "DATABASE_URL must use an async driver, e.g. 'postgresql+asyncpg://...'"
            )
        return value

    @property
    def is_development(self) -> bool:
        """True when running in the development environment."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance for dependency injection."""
    return Settings()
