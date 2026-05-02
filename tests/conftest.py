"""
Shared pytest fixtures.
"""

import os
import pytest

os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test_db")

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
from app.models import User


@pytest.fixture(scope="session")
def app():
    application = create_app()
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
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        session = _db.session
        yield session
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def sample_user(client):
    """
    Create a sample user via the register endpoint so we use
    the real password hashing the app uses — no set_password() needed.
    """
    resp = client.post("/auth/register", json={
        "firstName": "Jane",
        "lastName":  "Doe",
        "email":     "jane@example.com",
        "password":  "ValidPass123!",
        "phone":     "+254700000001",
    })
    # If already registered (session scope reuse), that's fine
    assert resp.status_code in (201, 400)

    # Return a simple namespace the tests can use
    class _User:
        email    = "jane@example.com"
        password = "ValidPass123!"
        # userid comes from the registration response when status is 201
        userid = (
            resp.get_json()["data"]["user"]["userId"]
            if resp.status_code == 201
            else None
        )

    return _User()


@pytest.fixture
def auth_headers(client, sample_user):
    response = client.post(
        "/auth/login",
        json={"email": sample_user.email, "password": sample_user.password},
    )
    assert response.status_code == 200
    token = response.get_json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}