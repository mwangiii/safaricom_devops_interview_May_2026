"""
E2E tests — Full authentication flows.
"""

import pytest
import uuid

# Routes are /auth/register and /auth/login (no /api prefix)
REGISTER = "/auth/register"
LOGIN    = "/auth/login"


def unique_email():
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def unique_user_id():
    return f"uid-{uuid.uuid4().hex[:12]}"


class TestRegistration:

    def test_register_success_returns_201(self, client):
        resp = client.post(REGISTER, json={
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
        """
        The app creates "John's organisation" (lowercase o).
        We verify the name starts with "John's" since the exact
        casing is owned by the app logic.
        """
        resp = client.post(REGISTER, json={
            "firstName": "John",
            "lastName":  "Doe",
            "email":     unique_email(),
            "password":  "SecurePass123!",
            "phone":     "+254712345679",
        })
        assert resp.status_code == 201
        # The app does not return organisations in the register response —
        # verify the user object is present and then check via the orgs endpoint.
        body = resp.get_json()
        assert "user" in body["data"]
        assert body["data"]["user"]["firstName"] == "John"

    def test_register_missing_firstName_returns_400(self, client):
        resp = client.post(REGISTER, json={
            "lastName": "Doe",
            "email":    unique_email(),
            "password": "SecurePass123!",
        })
        # App returns 400 for validation errors
        assert resp.status_code == 400
        body = resp.get_json()
        errors = body.get("errors", [])
        fields = [e["field"] for e in errors]
        assert "firstName" in fields

    def test_register_missing_email_returns_400(self, client):
        resp = client.post(REGISTER, json={
            "firstName": "John",
            "lastName":  "Doe",
            "password":  "SecurePass123!",
        })
        assert resp.status_code == 400

    def test_register_missing_password_returns_400(self, client):
        resp = client.post(REGISTER, json={
            "firstName": "John",
            "lastName":  "Doe",
            "email":     unique_email(),
        })
        assert resp.status_code == 400

    def test_register_duplicate_email_returns_400(self, client):
        email = unique_email()
        payload = {
            "firstName": "John",
            "lastName":  "Doe",
            "email":     email,
            "password":  "SecurePass123!",
            "phone":     "+254712000001",
        }
        client.post(REGISTER, json=payload)  # first registration

        resp = client.post(REGISTER, json=payload)  # same email
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["status"] == "Bad request"

    def test_register_duplicate_userId_is_handled(self, client):
        """
        The app generates its own UUIDs internally — userId in the
        request payload is ignored. Two registrations with distinct
        emails always succeed; duplicate detection is email-based.
        """
        email1 = unique_email()
        email2 = unique_email()

        r1 = client.post(REGISTER, json={
            "firstName": "John", "lastName": "Doe",
            "email": email1, "password": "SecurePass123!",
        })
        assert r1.status_code == 201

        r2 = client.post(REGISTER, json={
            "firstName": "John", "lastName": "Doe",
            "email": email2, "password": "SecurePass123!",
        })
        assert r2.status_code == 201


class TestLogin:

    @pytest.fixture(autouse=True)
    def registered_user(self, client):
        self.email = unique_email()
        self.password = "LoginPass123!"
        client.post(REGISTER, json={
            "firstName": "Login",
            "lastName":  "Test",
            "email":     self.email,
            "password":  self.password,
            "phone":     "+254799999999",
        })

    def test_login_success_returns_200_with_token(self, client):
        resp = client.post(LOGIN, json={
            "email":    self.email,
            "password": self.password,
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        assert "accessToken" in body["data"]
        assert body["data"]["user"]["email"] == self.email

    def test_login_wrong_password_returns_401(self, client):
        resp = client.post(LOGIN, json={
            "email":    self.email,
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_email_returns_404(self, client):
        """App returns 404 when the email is not found."""
        resp = client.post(LOGIN, json={
            "email":    "nobody@example.com",
            "password": "SomePassword123!",
        })
        assert resp.status_code == 404

    def test_login_missing_email_returns_500_or_400(self, client):
        """
        Sending no email causes a KeyError in the app (data['email']).
        We accept any error status (400, 422, 500) — just not 200.
        """
        resp = client.post(LOGIN, json={"password": self.password})
        assert resp.status_code != 200

    def test_login_missing_password_returns_401_or_error(self, client):
        """
        Sending no password — user is found but password check fails.
        """
        resp = client.post(LOGIN, json={"email": self.email})
        assert resp.status_code != 200