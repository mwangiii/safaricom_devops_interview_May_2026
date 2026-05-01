# tests/unit/test_jwt.py
"""
Unit tests — JWT token generation: expiry and payload validation.
"""

import time
import pytest
from flask_jwt_extended import decode_token


class TestJWTTokenGeneration:
    """JWT token correctness tests."""

    def test_login_returns_access_token(self, client, sample_user):
        resp = client.post(
            "/api/auth/login",
            json={"email": "jane@example.com", "password": "ValidPass123!"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "accessToken" in data["data"]

    def test_token_payload_contains_user_id(self, client, app, sample_user):
        resp = client.post(
            "/api/auth/login",
            json={"email": "jane@example.com", "password": "ValidPass123!"},
        )
        token = resp.get_json()["data"]["accessToken"]

        with app.app_context():
            decoded = decode_token(token)
            assert decoded["sub"] == sample_user.userId

    def test_token_has_expiry(self, client, app, sample_user):
        resp = client.post(
            "/api/auth/login",
            json={"email": "jane@example.com", "password": "ValidPass123!"},
        )
        token = resp.get_json()["data"]["accessToken"]

        with app.app_context():
            decoded = decode_token(token)
            assert "exp" in decoded
            # exp must be in the future
            assert decoded["exp"] > time.time()

    def test_token_expiry_is_bounded(self, client, app, sample_user):
        resp = client.post(
            "/api/auth/login",
            json={"email": "jane@example.com", "password": "ValidPass123!"},
        )
        token = resp.get_json()["data"]["accessToken"]

        with app.app_context():
            decoded = decode_token(token)
            # Must not be configured for more than 24 hours
            ttl_seconds = decoded["exp"] - time.time()
            assert ttl_seconds <= 86400, "Token TTL exceeds 24-hour maximum"

    def test_expired_token_rejected(self, client, app, sample_user, monkeypatch):
        """Force an expired token and verify the API rejects it."""
        from datetime import timedelta
        monkeypatch.setitem(app.config, "JWT_ACCESS_TOKEN_EXPIRES", timedelta(seconds=-1))

        resp = client.post(
            "/api/auth/login",
            json={"email": "jane@example.com", "password": "ValidPass123!"},
        )
        token = resp.get_json()["data"]["accessToken"]

        protected_resp = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert protected_resp.status_code == 401

    def test_invalid_token_rejected(self, client):
        resp = client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer this.is.not.valid"},
        )
        assert resp.status_code == 401

    def test_missing_token_rejected(self, client):
        resp = client.get("/api/users/me")
        assert resp.status_code == 401
