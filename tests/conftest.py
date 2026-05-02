"""
Shared pytest fixtures.
"""
import sys, os
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
from app.models import User            # noqa: E402


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


# ── Per-test DB cleanup ──────────────────────────────────────────────────────
#
# KEY FIX: Use a raw psycopg2 connection that is completely independent of
# SQLAlchemy's connection pool. This avoids the deadlock where SQLAlchemy
# holds open connections from the previous test that block our DELETEs.
#
@pytest.fixture(scope="function", autouse=True)
def clean_db(app):
    """Wipe test data after every test using a fresh independent connection."""
    yield

    import psycopg2

    # Dispose SQLAlchemy pool first so no app connections hold row locks
    with app.app_context():
        try:
            _db.session.remove()
            _db.engine.dispose()
        except Exception:
            pass

    # Use a raw connection completely outside SQLAlchemy
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"],
            connect_timeout=5,
        )
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '5000'")
        cur.execute("DELETE FROM userorganisation")
        cur.execute("DELETE FROM organisations")
        cur.execute("DELETE FROM users")
        conn.commit()
        cur.close()
    except Exception as e:
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


# ── Legacy per-test DB session ───────────────────────────────────────────────
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