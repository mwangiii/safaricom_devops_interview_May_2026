# tests/unit/test_org_access.py
"""
Unit tests — Organisation access control: no cross-org data leakage.
"""

import pytest
from app.models import User, Organisation


class TestOrganisationAccessControl:
    """Verify strict org-scoped data isolation."""

    @pytest.fixture
    def two_users_with_orgs(self, client):
        """Register two independent users, each getting their own default org."""
        # User A
        resp_a = client.post("/api/auth/register", json={
            "userId":    "user-a-001",
            "firstName": "Alice",
            "lastName":  "Alpha",
            "email":     "alice@example.com",
            "password":  "AlicePass123!",
            "phone":     "+254700000010",
        })
        assert resp_a.status_code == 201
        token_a = resp_a.get_json()["data"]["accessToken"]
        org_a_id = resp_a.get_json()["data"]["user"]["organisations"][0]["orgId"]

        # User B
        resp_b = client.post("/api/auth/register", json={
            "userId":    "user-b-002",
            "firstName": "Bob",
            "lastName":  "Beta",
            "email":     "bob@example.com",
            "password":  "BobPass123!",
            "phone":     "+254700000011",
        })
        assert resp_b.status_code == 201
        token_b = resp_b.get_json()["data"]["accessToken"]
        org_b_id = resp_b.get_json()["data"]["user"]["organisations"][0]["orgId"]

        return {
            "token_a": token_a, "org_a_id": org_a_id,
            "token_b": token_b, "org_b_id": org_b_id,
        }

    def test_user_cannot_access_another_users_org(self, client, two_users_with_orgs):
        """User B must receive 403 when accessing User A's organisation."""
        resp = client.get(
            f"/api/organisations/{two_users_with_orgs['org_a_id']}",
            headers={"Authorization": f"Bearer {two_users_with_orgs['token_b']}"},
        )
        assert resp.status_code in (403, 404), (
            f"Expected 403/404, got {resp.status_code} — possible data leakage"
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
        org_ids = [o["orgId"] for o in resp.get_json()["data"]["organisations"]]
        assert two_users_with_orgs["org_b_id"] not in org_ids, (
            "Cross-organisation data leakage detected in /api/organisations"
        )

    def test_unauthenticated_org_access_rejected(self, client, two_users_with_orgs):
        resp = client.get(f"/api/organisations/{two_users_with_orgs['org_a_id']}")
        assert resp.status_code == 401
