"""
Unit tests — JWT token generation: expiry and payload validation.

The app generates tokens using the raw `jwt` library (PyJWT), NOT
flask_jwt_extended.create_access_token(). We therefore decode with
PyJWT directly and verify the payload fields the app sets:
  sub  → str(user_id)
  exp  → datetime in future, ≤ 24 h from now
  iat  → issued-at timestamp
"""

import time
import jwt as pyjwt
import pytest

REGISTER = "/auth/register"
LOGIN    = "/auth/login"
SECRET   = "test-jwt-secret-not-for-production"


def _login(client, email, password):
    resp = client.post(LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.get_json()["data"]["accessToken"]


class TestJWTTokenGeneration:

    def test_login_returns_access_token(self, client, sample_user):
        resp = client.post(LOGIN, json={
            "email":    sample_user.email,
            "password": sample_user.password,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "accessToken" in data["data"]

    def test_token_payload_contains_user_id(self, client, app, sample_user):
        token = _login(client, sample_user.email, sample_user.password)
        decoded = pyjwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        # sub must be the user's UUID string
        assert "sub" in decoded
        assert isinstance(decoded["sub"], str)
        assert len(decoded["sub"]) > 0

    def test_token_has_expiry(self, client, app, sample_user):
        token = _login(client, sample_user.email, sample_user.password)
        decoded = pyjwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        assert "exp" in decoded
        assert decoded["exp"] > time.time()

    def test_token_expiry_is_bounded(self, client, app, sample_user):
        token = _login(client, sample_user.email, sample_user.password)
        decoded = pyjwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        ttl_seconds = decoded["exp"] - time.time()
        assert ttl_seconds <= 86400, "Token TTL exceeds 24-hour maximum"

    def test_expired_token_rejected(self, client, app, sample_user):
        """
        Manually craft a token that is already expired and confirm
        the API rejects it with 401.
        """
        from datetime import datetime, timedelta

        expired_token = pyjwt.encode(
            {
                "sub": "some-user-id",
                "iat": datetime.utcnow() - timedelta(hours=2),
                "exp": datetime.utcnow() - timedelta(hours=1),
            },
            app.config["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        # Any JWT-protected endpoint will do; /api/organisations requires auth
        resp = client.get(
            "/api/organisations",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    def test_invalid_token_rejected(self, client):
        resp = client.get(
            "/api/organisations",
            headers={"Authorization": "Bearer this.is.not.valid"},
        )
        assert resp.status_code == 401

    def test_missing_token_rejected(self, client):
        resp = client.get("/api/organisations")
        assert resp.status_code == 401