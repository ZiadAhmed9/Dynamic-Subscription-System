"""Application configuration classes.

Supports multiple environments via class inheritance.
DATABASE_URL can be set via environment variable; defaults to SQLite for local dev.
"""

import os


class BaseConfig:
    """Base configuration shared across all environments."""

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    RESTX_MASK_SWAGGER = False


class DevelopmentConfig(BaseConfig):
    """Development configuration — SQLite fallback for local testing."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///dev.db",
    )


class TestingConfig(BaseConfig):
    """Testing configuration — in-memory SQLite for fast tests."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(BaseConfig):
    """Production configuration — requires DATABASE_URL to be set."""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
