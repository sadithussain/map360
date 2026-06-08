"""Shared pytest fixtures and test environment setup.

The application settings require a Postgres connection URL and a JWT secret at
import time. Tests never touch a live database, so we populate the required
environment variables with safe placeholders before any application module is
imported. The async engine is created lazily and is never connected during the
unit/router tests in this suite.
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/postgres",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-of-sufficient-length")
os.environ.setdefault("ENVIRONMENT", "development")
