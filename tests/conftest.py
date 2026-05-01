# tests/conftest.py
"""
Shared pytest fixtures.
Works both locally (DATABASE_URL env var) and inside Docker (same env var
injected via docker-compose environment block or CI service container).
"""

import os
import pytest

# Patch environment variables BEFORE importing create_app so that
# get_database_url() inside __init__.py sees the test values.
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test_db")

# Allow DATABASE_URL to override the individual vars above.
if os.environ.get("DATABASE_URL"):
    from urllib.parse import urlparse
    _u = urlparse(os.environ["DATABASE_URL"])
    os.environ["DB_USER"]     = _u.username or os.environ["DB_USER"]
    os.environ["DB_PASSWORD"] = _u.password or os.environ["DB_PASSWORD"]
    os.environ["DB_HOST"]     = _u.hostname or os.environ["DB_HOST"]
    os.environ["DB_PORT"]     = str(_u.port or 5432)
    os.environ["DB_NAME"]     = _u.path.lstrip("/") or os.environ["DB_NAME"]

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")

from app import create_app, db as _db
from app.models import User, Organisation


@pytest.fixture(scope="session")
def app():
    """Create application for testing.

    create_app() takes no arguments, so we override the config dict
    on the returned app object before yielding it.
    """
    application = create_app()

    # Override settings that differ in the test environment.
    application.config.update(
        TESTING=True,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY="test-jwt-secret-not-for-production",
        SECRET_KEY="test-secret-key-not-for-production",
        JWT_ACCESS_TOKEN_EXPIRES=3600,
    )

    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    """Database session that rolls back after each test."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        session = _db.session

        yield session

        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def sample_user(db):
    """Pre-created user fixture."""
    user = User(
        userId="user-fixture-001",
        firstName="Jane",
        lastName="Doe",
        email="jane@example.com",
        phone="+254700000001",
    )
    user.set_password("ValidPass123!")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def auth_headers(client, sample_user):
    """Return JWT Authorization header for authenticated requests."""
    response = client.post(
        "/api/auth/login",
        json={"email": "jane@example.com", "password": "ValidPass123!"},
    )
    assert response.status_code == 200
    token = response.get_json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}