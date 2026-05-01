# tests/e2e/test_auth_spec.py
"""
E2E tests — Full authentication flows.
Mirrors the spec requirements in auth.spec.*.
"""

import pytest
import uuid


def unique_email():
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def unique_user_id():
    return f"uid-{uuid.uuid4().hex[:12]}"


# ─────────────────────────────────────────────────────────────────────────────
class TestRegistration:

    def test_register_success_returns_201(self, client):
        resp = client.post("/api/auth/register", json={
            "userId":    unique_user_id(),
            "firstName": "John",
            "lastName":  "Doe",
            "email":     unique_email(),
            "password":  "SecurePass123!",
            "phone":     "+254712345678",
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["status"] == "success"
        assert "accessToken" in body["data"]

    def test_register_creates_default_organisation(self, client):
        """Default org for 'John Doe' must be "John's Organisation"."""
        resp = client.post("/api/auth/register", json={
            "userId":    unique_user_id(),
            "firstName": "John",
            "lastName":  "Doe",
            "email":     unique_email(),
            "password":  "SecurePass123!",
            "phone":     "+254712345679",
        })
        assert resp.status_code == 201
        orgs = resp.get_json()["data"]["user"]["organisations"]
        assert len(orgs) >= 1
        assert orgs[0]["name"] == "John's Organisation"

    def test_register_missing_firstName_returns_422(self, client):
        resp = client.post("/api/auth/register", json={
            "userId":   unique_user_id(),
            "lastName": "Doe",
            "email":    unique_email(),
            "password": "SecurePass123!",
        })
        assert resp.status_code == 422
        body = resp.get_json()
        errors = body.get("errors", [])
        fields = [e["field"] for e in errors]
        assert "firstName" in fields

    def test_register_missing_email_returns_422(self, client):
        resp = client.post("/api/auth/register", json={
            "userId":    unique_user_id(),
            "firstName": "John",
            "lastName":  "Doe",
            "password":  "SecurePass123!",
        })
        assert resp.status_code == 422

    def test_register_missing_password_returns_422(self, client):
        resp = client.post("/api/auth/register", json={
            "userId":    unique_user_id(),
            "firstName": "John",
            "lastName":  "Doe",
            "email":     unique_email(),
        })
        assert resp.status_code == 422

    def test_register_duplicate_email_returns_422(self, client):
        email = unique_email()
        payload = {
            "userId":    unique_user_id(),
            "firstName": "John",
            "lastName":  "Doe",
            "email":     email,
            "password":  "SecurePass123!",
            "phone":     "+254712000001",
        }
        client.post("/api/auth/register", json=payload)  # first registration

        payload["userId"] = unique_user_id()  # different userId, same email
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 422
        body = resp.get_json()
        assert body["status"] == "Bad request"

    def test_register_duplicate_userId_returns_422(self, client):
        user_id = unique_user_id()
        payload = {
            "userId":    user_id,
            "firstName": "John",
            "lastName":  "Doe",
            "email":     unique_email(),
            "password":  "SecurePass123!",
        }
        client.post("/api/auth/register", json=payload)  # first registration

        payload["email"] = unique_email()  # different email, same userId
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
class TestLogin:

    @pytest.fixture(autouse=True)
    def registered_user(self, client):
        self.email = unique_email()
        self.password = "LoginPass123!"
        client.post("/api/auth/register", json={
            "userId":    unique_user_id(),
            "firstName": "Login",
            "lastName":  "Test",
            "email":     self.email,
            "password":  self.password,
            "phone":     "+254799999999",
        })

    def test_login_success_returns_200_with_token(self, client):
        resp = client.post("/api/auth/login", json={
            "email":    self.email,
            "password": self.password,
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        assert "accessToken" in body["data"]
        assert body["data"]["user"]["email"] == self.email

    def test_login_wrong_password_returns_401(self, client):
        resp = client.post("/api/auth/login", json={
            "email":    self.email,
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401
        body = resp.get_json()
        assert body["status"] == "Bad request"

    def test_login_nonexistent_email_returns_401(self, client):
        resp = client.post("/api/auth/login", json={
            "email":    "nobody@example.com",
            "password": "SomePassword123!",
        })
        assert resp.status_code == 401

    def test_login_missing_email_returns_422(self, client):
        resp = client.post("/api/auth/login", json={"password": self.password})
        assert resp.status_code == 422

    def test_login_missing_password_returns_422(self, client):
        resp = client.post("/api/auth/login", json={"email": self.email})
        assert resp.status_code == 422
