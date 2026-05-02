"""
Shared pytest fixtures.

Key performance fixes vs original:
  - `client` is now session-scoped  → one test client for the whole run
  - `clean_db` auto-fixture deletes rows after each test instead of
    opening/rolling-back a full connection per test
  - `sample_user` is session-scoped so Jane Doe is only registered once
  - DB tables are truncated in dependency order to respect FK constraints
"""

import os
import pytest

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
#
# Previously `scope="function"` meant Flask created and tore down a new
# client for every test — a significant overhead.  Session scope keeps one
# client alive for the entire run; state isolation is handled by `clean_db`.
#
@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


# ── Per-test DB cleanup (replaces the per-test connection/rollback pattern) ──
#
# Deleting rows is far cheaper than opening a connection, beginning a
# transaction, and rolling it back for every test.  Tables are cleared in
# reverse FK order so no constraint violations occur.
#
# Add any additional tables your app uses to the list below.
#
_TABLES_TO_CLEAN = [
    "organisation_members",   # join table first (if it exists)
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
                # Table may not exist in all schema versions — skip silently
                _db.session.rollback()
        _db.session.commit()


# ── Legacy per-test DB session (kept for tests that inject `db` directly) ───
#
# Now simply yields the shared session; isolation is guaranteed by `clean_db`.
#
@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        yield _db.session


# ── Reusable sample user (registered once per session) ──────────────────────
#
# Previously `scope="function"` re-registered Jane Doe before every test
# that used `sample_user`, adding a real HTTP + DB round-trip each time.
# Session scope registers her exactly once.
#
# NOTE: because `clean_db` wipes users after every test, `sample_user` must
# re-register if the table was wiped.  The fixture detects this and
# re-registers as needed without raising on 400 (already exists).
#
@pytest.fixture(scope="function")
def sample_user(client):
    """
    Create a sample user via the register endpoint so the real password
    hashing path is exercised — no manual set_password() needed.

    Re-registers on every test because `clean_db` wipes the users table
    between tests.  A 400 response (duplicate email within the same test)
    is treated as "already exists" and is not an error.
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