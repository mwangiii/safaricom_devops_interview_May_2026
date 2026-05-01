# tests/conftest.py
"""
Shared pytest fixtures.
Works both locally (DATABASE_URL env var) and inside Docker (same env var
injected via docker-compose environment block or CI service container).
"""

import os
import pytest

from app import create_app, db as _db
from app.models import User, Organisation


@pytest.fixture(scope="session")
def app():
    """Create application with test configuration."""
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": os.environ.get(
            "DATABASE_URL",
            "postgresql://test_user:test_password@localhost:5432/test_db",
        ),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "JWT_SECRET_KEY": "test-jwt-secret-not-for-production",
        "SECRET_KEY": "test-secret-key-not-for-production",
        "JWT_ACCESS_TOKEN_EXPIRES": 3600,   # 1 hour for tests
    }
    application = create_app(test_config)

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
