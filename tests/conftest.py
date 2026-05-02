"""
Shared pytest fixtures.

Key design decisions:
- clean_db uses TRANSACTION ROLLBACK (not psycopg2 DELETEs) to avoid deadlocks
  between SQLAlchemy's connection pool and raw DB connections.
- Session-scoped app/client so the Flask app is only created once per run.
- Function-scoped db/sample_user/auth_headers so every test starts clean.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Environment defaults ─────────────────────────────────────────────────────
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

from app import create_app, db as _db  # noqa: E402


# ── Application ──────────────────────────────────────────────────────────────
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


# ── Single test client ───────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


# ── Per-test DB cleanup (TRANSACTION ROLLBACK — no psycopg2 deadlocks) ──────
#
# Strategy: wrap every test in a savepoint. After the test body runs, roll
# back to that savepoint. This is O(1) and never blocks on row locks because
# no other connection is involved — it's a single SQLAlchemy session undoing
# its own work.
#
# Why this beats the old psycopg2 DELETE approach:
#   - The old approach opened a *second* connection and issued DELETEs while
#     SQLAlchemy's pool still held open connections from the test. Those open
#     connections held row locks → psycopg2 DELETEs blocked → 80-minute hang.
#   - Rollback needs no second connection and releases locks instantly.
#
@pytest.fixture(scope="function", autouse=True)
def clean_db(app):
    """Roll back all DB changes after each test — zero deadlock risk."""
    with app.app_context():
        # Grab a connection from the pool and start a transaction
        connection = _db.engine.connect()
        transaction = connection.begin()

        # Bind the session to this connection so every ORM call
        # participates in our transaction
        _db.session.bind = connection

        yield

        # Teardown: undo everything the test did
        _db.session.remove()
        transaction.rollback()
        connection.close()

        # Restore the session to normal pool-based binding
        _db.session.bind = None


# ── Per-test DB session (for tests that need direct ORM access) ──────────────
@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        yield _db.session


# ── Reusable sample user ─────────────────────────────────────────────────────
@pytest.fixture(scope="function")
def sample_user(client):
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


# ── Auth headers helper ──────────────────────────────────────────────────────
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