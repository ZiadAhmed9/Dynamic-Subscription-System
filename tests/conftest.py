"""Shared test fixtures."""

import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """Create an application instance configured for testing."""
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(autouse=True)
def db_session(app):
    """Ensure a clean database state for each test.

    Re-creates all tables before each test to guarantee isolation.
    """
    with app.app_context():
        _db.create_all()
        yield _db.session
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()
