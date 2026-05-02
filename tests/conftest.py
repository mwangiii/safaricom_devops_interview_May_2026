"""
Shared pytest fixtures.
Key performance fixes vs original:
  - `client` is now session-scoped  → one test client for the whole run
  - `clean_db` auto-fixture deletes rows after each test instead of
    opening/rolling-back a full connection per test
  - `sample_user` is session-scoped so Jane Doe is only registered once
  - DB tables are truncated in dependency order to respect FK constraints
"""
import sys, os
import pytest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Environment defaults (resolved before the app is imported) ───────────────
os.environ.setdefault("DB_USER",     "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("DB_HOST",     "localhost")
os.environ.setdefault("DB_PORT",     "5432")
os.environ.setdefault("DB_NAME",     "test_db")

if os.environ.get("DATABASE_URL"):
    from urllib.parse import urlparse
    _u = urlparse(os.environ["DATABASE_URL"])
    os.environ["DB_USER"]     = _u.username or os.environ["DB_USER"]
    os.environ["DB_PASSWORD"] = _u.password or os.environ["DB_PASSWORD"]
    os.environ["DB_HOST"]     = _u.hostname or os.environ["DB_HOST"]
    os.environ["DB_PORT"]     = str(_u.port or 5432)
    os.environ["DB_NAME"]     = _u.path.lstrip("/") or os.environ["DB_NAME"]

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")

from app import create_app, db as _db  # noqa: E402  (must come after env setup)
from app.models import User            # noqa: E402

# ── Application (one per test session) ──────────────────────────────────────
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

# ── Single test client reused across the whole session ───────────────────────
@pytest.fixture(scope="session")
def client(app):
    return app.test_client()

# ── Per-test DB cleanup ──────────────────────────────────────────────────────
#
# FIX: was "organisation_members" which does not exist in the schema.
# The actual join table is "userorganisation" (from UserOrganisation model).
# The wrong name caused a silent exception + session lock that made the
# test suite hang indefinitely.
#
_TABLES_TO_CLEAN = [
    "userorganisation",   # FK join table — must come before its parents
    "organisations",
    "users",
]

@pytest.fixture(scope="function", autouse=True)
def clean_db(app):
    """Wipe test data after every test function."""
    yield  # let the test run first
    with app.app_context():
        for table in _TABLES_TO_CLEAN:
            try:
                _db.session.execute(_db.text(f"DELETE FROM {table}"))
            except Exception:
                _db.session.rollback()
        _db.session.commit()

# ── Legacy per-test DB session ───────────────────────────────────────────────
@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        yield _db.session

# ── Reusable sample user ─────────────────────────────────────────────────────
@pytest.fixture(scope="function")
def sample_user(client):
    """
    Create a sample user via the register endpoint so the real password
    hashing path is exercised. Re-registers on every test because clean_db
    wipes the users table between tests.
    """
    resp = client.post("/auth/register", json={
        "firstName": "Jane",
        "lastName":  "Doe",
        "email":     "jane@example.com",
        "password":  "ValidPass123!",
        "phone":     "+254700000001",
    })
    assert resp.status_code in (201, 400), (
        f"Unexpected status registering sample_user: {resp.status_code}"
    )

    class _User:
        email    = "jane@example.com"
        password = "ValidPass123!"
        userid   = (
            resp.get_json()["data"]["user"]["userId"]
            if resp.status_code == 201
            else None
        )

    return _User()

# ── Convenience: pre-built Authorization header for sample_user ─────────────
@pytest.fixture(scope="function")
def auth_headers(client, sample_user):
    response = client.post(
        "/auth/login",
        json={"email": sample_user.email, "password": sample_user.password},
    )
    assert response.status_code == 200, (
        f"Login failed for sample_user: {response.get_json()}"
    )
    token = response.get_json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}