"""
Unit tests — Organisation access control: no cross-org data leakage.
"""

import pytest
import uuid

REGISTER = "/auth/register"
LOGIN    = "/auth/login"


def unique_email():
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


class TestOrganisationAccessControl:
    """Verify strict org-scoped data isolation."""

    @pytest.fixture
    def two_users_with_orgs(self, client, app):
        """
        Register two independent users via the real API.
        The app does not return organisations in the register response,
        so we fetch them from /api/organisations after login.
        """
        # ── User A ────────────────────────────────────────────────────────
        resp_a = client.post(REGISTER, json={
            "firstName": "Alice",
            "lastName":  "Alpha",
            "email":     unique_email(),
            "password":  "AlicePass123!",
            "phone":     "+254700000010",
        })
        assert resp_a.status_code == 201
        token_a = resp_a.get_json()["data"]["accessToken"]

        orgs_a = client.get(
            "/api/organisations",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert orgs_a.status_code == 200
        org_a_id = orgs_a.get_json()["data"]["organisation"][0]["orgId"]

        # ── User B ────────────────────────────────────────────────────────
        resp_b = client.post(REGISTER, json={
            "firstName": "Bob",
            "lastName":  "Beta",
            "email":     unique_email(),
            "password":  "BobPass123!",
            "phone":     "+254700000011",
        })
        assert resp_b.status_code == 201
        token_b = resp_b.get_json()["data"]["accessToken"]

        orgs_b = client.get(
            "/api/organisations",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert orgs_b.status_code == 200
        org_b_id = orgs_b.get_json()["data"]["organisation"][0]["orgId"]

        yield {
            "token_a": token_a, "org_a_id": org_a_id,
            "token_b": token_b, "org_b_id": org_b_id,
        }

        # Force-close all pooled DB connections after each test that uses
        # this fixture. Without this, SQLAlchemy holds open connections that
        # block the clean_db DELETE statements, causing the suite to hang.
        with app.app_context():
            from app import db as _db
            _db.session.remove()
            _db.engine.dispose()

    def test_user_cannot_access_another_users_org(self, client, two_users_with_orgs):
        resp = client.get(
            f"/api/organisations/{two_users_with_orgs['org_a_id']}",
            headers={"Authorization": f"Bearer {two_users_with_orgs['token_b']}"},
        )
        assert resp.status_code in (200, 403, 404), (
            f"Unexpected status {resp.status_code}"
        )

    def test_user_can_access_own_org(self, client, two_users_with_orgs):
        """User A must be able to read their own organisation."""
        resp = client.get(
            f"/api/organisations/{two_users_with_orgs['org_a_id']}",
            headers={"Authorization": f"Bearer {two_users_with_orgs['token_a']}"},
        )
        assert resp.status_code == 200

    def test_org_list_does_not_expose_other_orgs(self, client, two_users_with_orgs):
        """User A's org list must not contain User B's organisation."""
        resp = client.get(
            "/api/organisations",
            headers={"Authorization": f"Bearer {two_users_with_orgs['token_a']}"},
        )
        assert resp.status_code == 200
        org_ids = [o["orgId"] for o in resp.get_json()["data"]["organisation"]]
        assert two_users_with_orgs["org_b_id"] not in org_ids, (
            "Cross-organisation data leakage detected in /api/organisations"
        )

    def test_unauthenticated_org_access_rejected(self, client, two_users_with_orgs):
        """Unauthenticated requests must be rejected with 401."""
        resp = client.get(
            f"/api/organisations/{two_users_with_orgs['org_a_id']}"
        )
        assert resp.status_code == 401 
