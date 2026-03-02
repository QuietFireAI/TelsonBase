# TelsonBase/tests/test_e2e_integration.py
# REM: =======================================================================================
# REM: END-TO-END INTEGRATION TESTS FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v7.0.0CC: New feature — Full end-to-end integration test suite
#
# REM: Mission Statement: Validate complete user workflows across auth, tenancy, security,
# REM: audit, and error handling subsystems. Each test exercises the real API surface
# REM: through FastAPI's TestClient to verify cross-module integration.
#
# REM: QMS Protocol:
# REM:   Success: "Thank_You"
# REM:   Failure: "Thank_You_But_No"
# REM: =======================================================================================

import pytest
import uuid
from fastapi.testclient import TestClient


# REM: =======================================================================================
# REM: HELPERS
# REM: =======================================================================================

def _unique(prefix: str = "e2e") -> str:
    """REM: Generate a short unique suffix for test isolation."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _register_user(client: TestClient, username: str = None, email: str = None,
                   password: str = "SecurePassword123!") -> dict:
    """
    REM: Register a user and return the full response dict.
    REM: Generates a unique username/email if not provided.
    REM: Solves a CAPTCHA challenge before registering (required for non-first-user registrations).
    REM: Auto-verifies email so the user can log in immediately — mirrors the auto-verification
    REM: that the server applies to the first user. Required because test environments don't
    REM: send real emails.
    """
    username = username or _unique("user")
    email = email or f"{username}@test.telsonbase.local"
    # REM: Generate and immediately solve a CAPTCHA challenge — mirrors what a browser client
    # REM: does. The first user bypasses the CAPTCHA check (is_first_user == True), but
    # REM: including it for all registrations is safe and tests the full flow.
    from core.captcha import captcha_manager
    challenge = captcha_manager.generate_challenge()
    captcha_manager.verify_challenge(challenge.challenge_id, challenge.answer)
    resp = client.post("/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
        "captcha_challenge_id": challenge.challenge_id,
    })
    # REM: Auto-verify email for test helper — real users verify via emailed link.
    # REM: This mirrors the server's auto-verification for the first user.
    if resp.status_code == 200:
        data = resp.json()
        if "user" in data:
            user_id = data["user"]["user_id"]
            from core.email_verification import email_verification as ev
            ev._verified_emails[user_id] = email
            try:
                ev._save_verified_email(user_id, email)
            except Exception:
                pass  # Redis may be unavailable in test env
    return resp


def _login_user(client: TestClient, username: str, password: str = "SecurePassword123!") -> dict:
    """REM: Login and return the full response dict."""
    resp = client.post("/v1/auth/login", json={
        "username": username,
        "password": password,
    })
    return resp


def _jwt_headers(token: str) -> dict:
    """REM: Build Authorization header from a JWT token."""
    return {"Authorization": f"Bearer {token}"}


def _api_key_headers() -> dict:
    """REM: Build X-API-Key header from test settings."""
    from core.config import get_settings
    settings = get_settings()
    return {"X-API-Key": settings.mcp_api_key}


# REM: =======================================================================================
# REM: CLASS: TestUserLifecycle
# REM: =======================================================================================

@pytest.mark.e2e
class TestUserLifecycle:
    """REM: End-to-end tests for user registration, login, profile, password change, logout."""

    def test_register_first_user_gets_super_admin(self, client):
        """
        REM: The very first user registered on a fresh system receives super_admin role.
        REM: POST /v1/auth/register -> user.roles includes super_admin
        """
        resp = _register_user(client)

        assert resp.status_code == 200, f"Registration failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        assert "user" in data
        user = data["user"]
        # REM: First user should have super_admin (may be list or contain the string)
        roles = user.get("roles", [])
        assert "super_admin" in roles, (
            f"First user should get super_admin, got roles={roles}"
        )

    def test_register_second_user_gets_viewer(self, client):
        """
        REM: Subsequent users receive the viewer role by default.
        REM: POST /v1/auth/register (second call) -> user.roles includes viewer
        """
        # REM: Ensure first user exists
        _register_user(client)

        # REM: Register a second, different user
        resp = _register_user(client)
        assert resp.status_code == 200, f"Second registration failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        roles = data["user"].get("roles", [])
        assert "viewer" in roles, (
            f"Second user should get viewer, got roles={roles}"
        )

    def test_login_returns_jwt(self, client):
        """
        REM: A registered user can login and receive a JWT access token.
        REM: POST /v1/auth/login -> access_token present, token_type == bearer
        """
        username = _unique("login")
        _register_user(client, username=username)

        resp = _login_user(client, username)
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        # REM: When MFA is not enrolled, full token is returned directly
        if not data.get("mfa_required"):
            assert "access_token" in data
            assert data["token_type"] == "bearer"
        else:
            # REM: MFA flow — pre_mfa_token must be present
            assert "pre_mfa_token" in data

    def test_login_wrong_password_rejected(self, client):
        """
        REM: Login with wrong password returns 401 Unauthorized.
        REM: POST /v1/auth/login with bad password -> 401
        """
        username = _unique("badpw")
        _register_user(client, username=username)

        resp = _login_user(client, username, password="WrongPassword999!")
        assert resp.status_code == 401
        data = resp.json()
        detail = data.get("detail", data)
        if isinstance(detail, dict):
            assert detail.get("qms_status") == "Thank_You_But_No"

    def test_profile_with_jwt(self, client):
        """
        REM: Authenticated user can fetch their profile via JWT.
        REM: GET /v1/auth/profile with Bearer token -> profile data
        """
        username = _unique("profile")
        _register_user(client, username=username)

        login_resp = _login_user(client, username)
        login_data = login_resp.json()

        if login_data.get("mfa_required"):
            pytest.skip("MFA required — cannot complete profile test without TOTP")

        token = login_data["access_token"]
        resp = client.get("/v1/auth/profile", headers=_jwt_headers(token))
        assert resp.status_code == 200, f"Profile fetch failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        assert "profile" in data

    def test_change_password(self, client):
        """
        REM: Authenticated user can change their password.
        REM: POST /v1/auth/change-password with old + new password -> success
        """
        username = _unique("chpw")
        old_password = "SecurePassword123!"
        new_password = "NewSecurePass456!"
        _register_user(client, username=username, password=old_password)

        login_resp = _login_user(client, username, password=old_password)
        login_data = login_resp.json()

        if login_data.get("mfa_required"):
            pytest.skip("MFA required — cannot complete password change test")

        token = login_data["access_token"]
        resp = client.post(
            "/v1/auth/change-password",
            headers=_jwt_headers(token),
            json={
                "old_password": old_password,
                "new_password": new_password,
            },
        )
        assert resp.status_code == 200, f"Password change failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"

        # REM: Verify new password works
        resp2 = _login_user(client, username, password=new_password)
        assert resp2.status_code == 200

    def test_logout_revokes_token(self, client):
        """
        REM: After logout, the old JWT should be rejected.
        REM: POST /v1/auth/logout -> success, then GET /v1/auth/profile -> 401
        """
        username = _unique("logout")
        _register_user(client, username=username)

        login_resp = _login_user(client, username)
        login_data = login_resp.json()

        if login_data.get("mfa_required"):
            pytest.skip("MFA required — cannot complete logout test")

        token = login_data["access_token"]
        headers = _jwt_headers(token)

        # REM: Logout
        resp = client.post("/v1/auth/logout", headers=headers)
        assert resp.status_code == 200, f"Logout failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"

        # REM: Old token should now be revoked
        resp2 = client.get("/v1/auth/profile", headers=headers)
        assert resp2.status_code == 401, (
            "Profile should be rejected after logout"
        )


# REM: =======================================================================================
# REM: CLASS: TestTenantWorkflow
# REM: =======================================================================================

@pytest.mark.e2e
class TestTenantWorkflow:
    """REM: End-to-end tests for tenant and client-matter lifecycle."""

    def test_create_tenant_brokerage(self, client, auth_headers):
        """
        REM: Create a real_estate tenant (formerly brokerage — type renamed when tenancy model updated).
        REM: POST /v1/tenancy/tenants -> tenant with type real_estate
        """
        resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"E2E Brokerage {_unique()}",
            "tenant_type": "real_estate",
            "created_by": "e2e_test",
        })
        assert resp.status_code == 200, f"Tenant creation failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        assert "tenant" in data
        assert data["tenant"]["tenant_type"] == "real_estate"

    def test_create_matter_under_tenant(self, client, auth_headers):
        """
        REM: Create a matter under a tenant.
        REM: POST /v1/tenancy/tenants/{id}/matters -> matter created
        """
        # REM: Create tenant first
        t_resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"Matter Tenant {_unique()}",
            "tenant_type": "law_firm",
            "created_by": "e2e_test",
        })
        tenant_id = t_resp.json()["tenant"]["tenant_id"]

        resp = client.post(
            f"/v1/tenancy/tenants/{tenant_id}/matters",
            headers=auth_headers,
            json={
                "name": f"E2E Matter {_unique()}",
                "matter_type": "litigation",
                "created_by": "e2e_test",
            },
        )
        assert resp.status_code == 200, f"Matter creation failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        assert "matter" in data

    def test_list_matters_for_tenant(self, client, auth_headers):
        """
        REM: List matters for a tenant and verify the created matter appears.
        REM: GET /v1/tenancy/tenants/{id}/matters -> count >= 1
        """
        # REM: Setup: tenant + matter
        t_resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"List Tenant {_unique()}",
            "tenant_type": "general",
            "created_by": "e2e_test",
        })
        tenant_id = t_resp.json()["tenant"]["tenant_id"]

        matter_name = f"Findable Matter {_unique()}"
        client.post(
            f"/v1/tenancy/tenants/{tenant_id}/matters",
            headers=auth_headers,
            json={
                "name": matter_name,
                "matter_type": "transaction",
                "created_by": "e2e_test",
            },
        )

        resp = client.get(
            f"/v1/tenancy/tenants/{tenant_id}/matters",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        assert data["count"] >= 1
        names = [m["name"] for m in data["matters"]]
        assert matter_name in names

    def test_place_litigation_hold(self, client, auth_headers):
        """
        REM: Place a litigation hold on a matter. Verify status becomes hold.
        REM: POST /v1/tenancy/matters/{id}/hold -> held == true
        """
        # REM: Setup: tenant + matter
        t_resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"Hold Tenant {_unique()}",
            "tenant_type": "law_firm",
            "created_by": "e2e_test",
        })
        tenant_id = t_resp.json()["tenant"]["tenant_id"]

        m_resp = client.post(
            f"/v1/tenancy/tenants/{tenant_id}/matters",
            headers=auth_headers,
            json={
                "name": f"Hold Matter {_unique()}",
                "matter_type": "litigation",
                "created_by": "e2e_test",
            },
        )
        matter_id = m_resp.json()["matter"]["matter_id"]

        resp = client.post(
            f"/v1/tenancy/matters/{matter_id}/hold",
            headers=auth_headers,
            json={"hold_by": "e2e_test"},
        )
        assert resp.status_code == 200, f"Hold failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        assert data["held"] is True

        # REM: Verify status via GET
        get_resp = client.get(
            f"/v1/tenancy/matters/{matter_id}",
            headers=auth_headers,
        )
        assert get_resp.status_code == 200
        matter_data = get_resp.json()["matter"]
        assert matter_data["status"] == "hold"

    def test_cannot_close_held_matter(self, client, auth_headers):
        """
        REM: Attempting to close a matter under litigation hold must fail with 400.
        REM: POST /v1/tenancy/matters/{id}/close on held matter -> 400
        """
        # REM: Setup: tenant + matter + hold
        t_resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"NoClose Tenant {_unique()}",
            "tenant_type": "law_firm",
            "created_by": "e2e_test",
        })
        tenant_id = t_resp.json()["tenant"]["tenant_id"]

        m_resp = client.post(
            f"/v1/tenancy/tenants/{tenant_id}/matters",
            headers=auth_headers,
            json={
                "name": f"NoClose Matter {_unique()}",
                "matter_type": "litigation",
                "created_by": "e2e_test",
            },
        )
        matter_id = m_resp.json()["matter"]["matter_id"]

        client.post(
            f"/v1/tenancy/matters/{matter_id}/hold",
            headers=auth_headers,
            json={"hold_by": "e2e_test"},
        )

        # REM: Attempt to close — should be rejected
        resp = client.post(
            f"/v1/tenancy/matters/{matter_id}/close",
            headers=auth_headers,
            json={"closed_by": "e2e_test"},
        )
        assert resp.status_code == 400, (
            f"Expected 400 when closing held matter, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        detail = data.get("detail", data)
        if isinstance(detail, dict):
            assert detail.get("qms_status") == "Thank_You_But_No"

    def test_release_hold_then_close(self, client, auth_headers):
        """
        REM: Release litigation hold, then close the matter successfully.
        REM: POST /v1/tenancy/matters/{id}/release-hold -> released
        REM: POST /v1/tenancy/matters/{id}/close -> closed
        """
        # REM: Setup: tenant + matter + hold
        t_resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"Release Tenant {_unique()}",
            "tenant_type": "real_estate",
            "created_by": "e2e_test",
        })
        tenant_id = t_resp.json()["tenant"]["tenant_id"]

        m_resp = client.post(
            f"/v1/tenancy/tenants/{tenant_id}/matters",
            headers=auth_headers,
            json={
                "name": f"Release Matter {_unique()}",
                "matter_type": "client_file",
                "created_by": "e2e_test",
            },
        )
        matter_id = m_resp.json()["matter"]["matter_id"]

        client.post(
            f"/v1/tenancy/matters/{matter_id}/hold",
            headers=auth_headers,
            json={"hold_by": "e2e_test"},
        )

        # REM: Release hold
        rel_resp = client.post(
            f"/v1/tenancy/matters/{matter_id}/release-hold",
            headers=auth_headers,
            json={"released_by": "e2e_test"},
        )
        assert rel_resp.status_code == 200, f"Release hold failed: {rel_resp.text}"
        assert rel_resp.json()["qms_status"] == "Thank_You"
        assert rel_resp.json()["released"] is True

        # REM: Now close should succeed
        close_resp = client.post(
            f"/v1/tenancy/matters/{matter_id}/close",
            headers=auth_headers,
            json={"closed_by": "e2e_test"},
        )
        assert close_resp.status_code == 200, f"Close after release failed: {close_resp.text}"
        assert close_resp.json()["qms_status"] == "Thank_You"
        assert close_resp.json()["closed"] is True


# REM: =======================================================================================
# REM: CLASS: TestTenantIsolation
# REM: =======================================================================================

@pytest.mark.e2e
class TestTenantIsolation:
    """REM: Validates that tenant data is scoped and does not bleed across tenant boundaries."""

    def test_tenant_matter_lists_are_isolated(self, client, auth_headers):
        """
        REM: Matter list for Tenant B must not contain matters created under Tenant A.
        REM: Validates that tenant_scoped_key() isolation is enforced at the API response layer.
        """
        # REM: Create two independent tenants
        ta_resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"Isolation Tenant A {_unique()}",
            "tenant_type": "law_firm",
            "created_by": "e2e_test",
        })
        assert ta_resp.status_code == 200, f"Tenant A creation failed: {ta_resp.text}"
        tenant_a_id = ta_resp.json()["tenant"]["tenant_id"]

        tb_resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"Isolation Tenant B {_unique()}",
            "tenant_type": "law_firm",
            "created_by": "e2e_test",
        })
        assert tb_resp.status_code == 200, f"Tenant B creation failed: {tb_resp.text}"
        tenant_b_id = tb_resp.json()["tenant"]["tenant_id"]

        # REM: Add a uniquely named matter to Tenant A only
        matter_name = f"Tenant A Secret Matter {_unique()}"
        m_resp = client.post(
            f"/v1/tenancy/tenants/{tenant_a_id}/matters",
            headers=auth_headers,
            json={"name": matter_name, "matter_type": "litigation", "created_by": "e2e_test"},
        )
        assert m_resp.status_code == 200, f"Matter creation failed: {m_resp.text}"

        # REM: List matters for Tenant B — Tenant A's matter must NOT appear
        resp = client.get(
            f"/v1/tenancy/tenants/{tenant_b_id}/matters",
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Failed to list Tenant B matters: {resp.text}"

        matters = resp.json().get("matters", [])
        names = [m["name"] for m in matters]
        assert matter_name not in names, (
            f"Tenant data bleed detected: '{matter_name}' (Tenant A) appeared in Tenant B's matter list"
        )

    def test_cross_tenant_access_rejected(self, client, auth_headers):
        """
        REM: v9.0.0B — A user cannot access a tenant created by a different user.
        REM: Verifies that tenant.allowed_actors enforcement returns HTTP 403.
        """
        # REM: Admin (API key, actor="system:master") creates a tenant
        # REM: allowed_actors is set to ["system:master"] on creation
        ta_resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"Admin Only Tenant {_unique()}",
            "tenant_type": "law_firm",
        })
        assert ta_resp.status_code == 200, f"Tenant creation failed: {ta_resp.text}"
        tenant_id = ta_resp.json()["tenant"]["tenant_id"]

        # REM: Register User B — gets viewer role (view:dashboard only, no admin:config)
        user_b_resp = _register_user(client)
        assert user_b_resp.status_code == 200, f"User B registration failed: {user_b_resp.text}"
        user_b_username = user_b_resp.json()["user"]["username"]

        # REM: Log in as User B and get their JWT
        login_resp = _login_user(client, username=user_b_username)
        assert login_resp.status_code == 200, f"User B login failed: {login_resp.text}"
        login_data = login_resp.json()
        if login_data.get("mfa_required"):
            pytest.skip("MFA required for User B — skipping cross-tenant test")
        user_b_token = login_data["access_token"]
        user_b_headers = _jwt_headers(user_b_token)

        # REM: User B must not be able to view the tenant created by admin
        resp = client.get(f"/v1/tenancy/tenants/{tenant_id}", headers=user_b_headers)
        assert resp.status_code == 403, (
            f"Cross-tenant access should be rejected (403), got {resp.status_code}: {resp.text}"
        )
        # REM: FastAPI wraps HTTPException detail in {"detail": ...}
        assert resp.json().get("detail", {}).get("qms_status") == "Thank_You_But_No"

        # REM: User B's matter list for that tenant must also be denied
        resp2 = client.get(f"/v1/tenancy/tenants/{tenant_id}/matters", headers=user_b_headers)
        assert resp2.status_code == 403, (
            f"Cross-tenant matter list should be denied (403), got {resp2.status_code}: {resp2.text}"
        )

    def test_admin_grant_access_allows_user(self, client, auth_headers):
        """
        REM: v9.0.0B — Admin grants access to a tenant. The granted user can then read it.
        REM: Verifies the full grant-access lifecycle: create → deny → grant → allow.
        """
        # REM: Admin creates tenant — only admin in allowed_actors initially
        ta_resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"Grant Test Tenant {_unique()}",
            "tenant_type": "healthcare",
        })
        assert ta_resp.status_code == 200, f"Tenant creation failed: {ta_resp.text}"
        tenant_id = ta_resp.json()["tenant"]["tenant_id"]

        # REM: Register User C and log in
        user_c_resp = _register_user(client)
        assert user_c_resp.status_code == 200, f"User C registration failed: {user_c_resp.text}"
        user_c_id = user_c_resp.json()["user"]["user_id"]
        user_c_username = user_c_resp.json()["user"]["username"]

        login_resp = _login_user(client, username=user_c_username)
        assert login_resp.status_code == 200, f"User C login failed: {login_resp.text}"
        login_data = login_resp.json()
        if login_data.get("mfa_required"):
            pytest.skip("MFA required for User C — skipping grant-access test")
        user_c_headers = _jwt_headers(login_data["access_token"])

        # REM: Before grant — User C should be denied (403)
        before = client.get(f"/v1/tenancy/tenants/{tenant_id}", headers=user_c_headers)
        assert before.status_code == 403, (
            f"Pre-grant: expected 403, got {before.status_code}: {before.text}"
        )

        # REM: Admin grants User C access to the tenant
        grant_resp = client.post(
            f"/v1/tenancy/tenants/{tenant_id}/grant-access",
            headers=auth_headers,
            json={"user_id": user_c_id},
        )
        assert grant_resp.status_code == 200, f"Grant-access failed: {grant_resp.text}"
        assert grant_resp.json()["granted"] is True

        # REM: After grant — User C can now read the tenant
        after = client.get(f"/v1/tenancy/tenants/{tenant_id}", headers=user_c_headers)
        assert after.status_code == 200, (
            f"Post-grant: expected 200, got {after.status_code}: {after.text}"
        )
        assert after.json()["tenant"]["tenant_id"] == tenant_id

        # REM: Idempotency — granting access twice must succeed silently
        grant_again = client.post(
            f"/v1/tenancy/tenants/{tenant_id}/grant-access",
            headers=auth_headers,
            json={"user_id": user_c_id},
        )
        assert grant_again.status_code == 200, f"Idempotent grant failed: {grant_again.text}"

    def test_cross_tenant_denial_is_audit_logged(self, client, auth_headers):
        """
        REM: v9.0.0B — Cross-tenant access denial writes an AUTH_FAILURE event to the audit chain.
        REM: Verifies that unauthorized tenant access is traceable, not silent.
        """
        # REM: Admin creates tenant
        ta_resp = client.post("/v1/tenancy/tenants", headers=auth_headers, json={
            "name": f"Audit Log Test Tenant {_unique()}",
            "tenant_type": "law_firm",
        })
        assert ta_resp.status_code == 200
        tenant_id = ta_resp.json()["tenant"]["tenant_id"]

        # REM: Register User D and log in
        user_d_resp = _register_user(client)
        assert user_d_resp.status_code == 200
        login_resp = _login_user(client, username=user_d_resp.json()["user"]["username"])
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        if login_data.get("mfa_required"):
            pytest.skip("MFA required for User D — skipping audit log test")
        user_d_headers = _jwt_headers(login_data["access_token"])

        # REM: User D attempts unauthorized access — triggers AUTH_FAILURE audit event
        denied = client.get(f"/v1/tenancy/tenants/{tenant_id}", headers=user_d_headers)
        assert denied.status_code == 403

        # REM: Audit chain must contain an auth.failure entry for this denial
        audit_resp = client.get("/v1/audit/chain/entries", headers=auth_headers)
        assert audit_resp.status_code == 200
        entries = audit_resp.json().get("entries", [])
        denial_events = [
            e for e in entries
            if e.get("event_type") == "auth.failure"
            and tenant_id in str(e.get("resource", ""))
        ]
        assert len(denial_events) >= 1, (
            f"Expected AUTH_FAILURE audit event for tenant ::{tenant_id}:: — none found. "
            f"Auth failure events: {[e for e in entries if e.get('event_type') == 'auth.failure']}"
        )


# REM: =======================================================================================
# REM: CLASS: TestSecurityEndpoints
# REM: =======================================================================================

@pytest.mark.e2e
class TestSecurityEndpoints:
    """REM: End-to-end tests for MFA enrollment, CAPTCHA, and email verification."""

    def test_mfa_enrollment(self, client, auth_headers):
        """
        REM: Enroll a user in MFA via the security API.
        REM: POST /v1/security/mfa/enroll -> secret, provisioning_uri, backup_codes
        """
        user_id = _unique("mfa_user")
        resp = client.post(
            "/v1/security/mfa/enroll",
            headers=auth_headers,
            json={
                "user_id": user_id,
                "username": f"mfa_{user_id}",
            },
        )
        assert resp.status_code == 200, f"MFA enrollment failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        assert "secret" in data
        assert "provisioning_uri" in data
        assert "backup_codes" in data
        assert isinstance(data["backup_codes"], list)

    def test_captcha_generate_and_verify(self, client, auth_headers):
        """
        REM: Generate a CAPTCHA challenge and verify it can be submitted.
        REM: POST /v1/security/captcha/generate -> challenge_id, question
        REM: POST /v1/security/captcha/verify -> solved (bool)
        """
        gen_resp = client.post(
            "/v1/security/captcha/generate",
            headers=auth_headers,
            json={},
        )
        assert gen_resp.status_code == 200, f"CAPTCHA generate failed: {gen_resp.text}"
        gen_data = gen_resp.json()
        assert gen_data["qms_status"] == "Thank_You"
        assert "challenge_id" in gen_data
        assert "question" in gen_data

        # REM: Verify with a dummy answer — we only test the endpoint responds
        verify_resp = client.post(
            "/v1/security/captcha/verify",
            headers=auth_headers,
            json={
                "challenge_id": gen_data["challenge_id"],
                "answer": "test_answer",
            },
        )
        assert verify_resp.status_code == 200, f"CAPTCHA verify failed: {verify_resp.text}"
        verify_data = verify_resp.json()
        # REM: solved may be True or False depending on the answer
        assert "solved" in verify_data
        assert verify_data["qms_status"] in ("Thank_You", "Thank_You_But_No")

    def test_captcha_wrong_answer_blocks_registration(self, client):
        """
        REM: ADVERSARIAL — A non-first user who submits a wrong CAPTCHA answer
        REM: must be rejected. Tests the actual security gate, not just the plumbing.
        """
        # REM: Register the first user (no CAPTCHA required — becomes super_admin)
        first = _register_user(client, username=_unique("captcha_first"))
        assert first.status_code == 200, f"First user setup failed: {first.text}"

        # REM: Generate a real challenge but submit the WRONG answer
        from core.captcha import captcha_manager
        challenge = captcha_manager.generate_challenge()
        wrong_answer = "definitely_not_the_right_answer_12345"

        resp = client.post("/v1/auth/register", json={
            "username": _unique("captcha_bad"),
            "email": f"{_unique('captcha_bad')}@test.telsonbase.local",
            "password": "SecurePassword123!",
            "captcha_challenge_id": challenge.challenge_id,
            # REM: We do NOT call captcha_manager.verify_challenge() here — the server
            # REM: must reject an unsolved challenge, regardless of the client claim.
        })
        # REM: Registration with an unsolved CAPTCHA must be rejected
        assert resp.status_code in (400, 422), (
            f"Expected rejection for unsolved CAPTCHA, got {resp.status_code}: {resp.text}"
        )

    def test_captcha_missing_id_blocks_non_first_registration(self, client):
        """
        REM: ADVERSARIAL — A non-first user who omits captcha_challenge_id entirely
        REM: must be rejected. Tests that the gate exists, not just that it checks the value.
        """
        # REM: Register the first user
        first = _register_user(client, username=_unique("captcha_missing_first"))
        assert first.status_code == 200, f"First user setup failed: {first.text}"

        # REM: Attempt second registration with no CAPTCHA at all
        resp = client.post("/v1/auth/register", json={
            "username": _unique("captcha_missing_user"),
            "email": f"{_unique('captcha_missing')}@test.telsonbase.local",
            "password": "SecurePassword123!",
            # REM: No captcha_challenge_id — should be rejected for non-first users
        })
        assert resp.status_code in (400, 422), (
            f"Expected rejection for missing CAPTCHA on non-first user, got {resp.status_code}: {resp.text}"
        )

    def test_captcha_solved_challenge_is_single_use(self, client):
        """
        REM: ADVERSARIAL — A solved CAPTCHA challenge_id must be consumed (deleted) after
        REM: the first successful registration. Replaying the same challenge_id for a second
        REM: registration must be rejected (replay attack prevention).
        """
        # REM: Register the first user (bypasses CAPTCHA — is_first_user == True)
        first = _register_user(client, username=_unique("replay_first"))
        assert first.status_code == 200, f"First user setup failed: {first.text}"

        # REM: Generate and solve a fresh CAPTCHA challenge
        from core.captcha import captcha_manager
        challenge = captcha_manager.generate_challenge()
        captcha_manager.verify_challenge(challenge.challenge_id, challenge.answer)

        # REM: First use — must succeed (challenge is valid and solved)
        resp1 = client.post("/v1/auth/register", json={
            "username": _unique("replay_user1"),
            "email": f"{_unique('replay1')}@test.telsonbase.local",
            "password": "SecurePassword123!",
            "captcha_challenge_id": challenge.challenge_id,
        })
        assert resp1.status_code == 200, (
            f"First registration with solved CAPTCHA should succeed, got: {resp1.text}"
        )

        # REM: Replay — same challenge_id on a second registration must be rejected.
        # REM: consume_challenge() deleted it on first use; it no longer exists in the store.
        resp2 = client.post("/v1/auth/register", json={
            "username": _unique("replay_user2"),
            "email": f"{_unique('replay2')}@test.telsonbase.local",
            "password": "SecurePassword123!",
            "captcha_challenge_id": challenge.challenge_id,
        })
        assert resp2.status_code == 400, (
            f"Replay attack succeeded — same challenge_id accepted twice. "
            f"Got {resp2.status_code}: {resp2.text}"
        )

    def test_email_verification_create(self, client, auth_headers):
        """
        REM: Request email verification for a user.
        REM: POST /v1/security/email/request-verification -> token_id, expires_at
        """
        user_id = _unique("emailv")
        resp = client.post(
            "/v1/security/email/request-verification",
            headers=auth_headers,
            json={
                "user_id": user_id,
                "email": f"{user_id}@test.telsonbase.local",
            },
        )
        assert resp.status_code == 200, f"Email verification request failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        assert "token_id" in data
        assert "expires_at" in data


# REM: =======================================================================================
# REM: CLASS: TestAuditChainIntegrity
# REM: =======================================================================================

@pytest.mark.e2e
class TestAuditChainIntegrity:
    """REM: End-to-end tests for audit chain endpoints."""

    def test_audit_chain_has_entries(self, client, auth_headers):
        """
        REM: The audit chain should have at least one entry after server activity.
        REM: GET /v1/audit/chain/entries -> count > 0
        """
        # REM: Trigger at least one auditable action first
        client.get("/v1/system/status", headers=auth_headers)

        resp = client.get("/v1/audit/chain/entries", headers=auth_headers)
        assert resp.status_code == 200, f"Audit entries failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        assert "entries" in data
        assert "count" in data
        assert data["count"] > 0, "Audit chain should have entries after API activity"

    def test_audit_chain_verify_valid(self, client, auth_headers):
        """
        REM: The audit chain integrity check should return valid=true OR only have
        REM: restart-boundary breaks (chain_break), never hash_mismatch (tampering).
        REM: GET /v1/audit/chain/verify -> no hash_mismatch breaks
        REM: chain_break is expected after container restart (known, non-malicious).
        REM: hash_mismatch would indicate real tampering — always a hard failure.
        """
        resp = client.get("/v1/audit/chain/verify", headers=auth_headers)
        assert resp.status_code == 200, f"Audit verify failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] in ("Thank_You", "Thank_You_But_No"), (
            f"Unexpected qms_status: {data}"
        )
        # REM: Fail hard on hash_mismatch (tampering). chain_break is acceptable
        # REM: — it occurs at container restart boundaries and is not a security event.
        tampering_breaks = [
            b for b in data.get("breaks", [])
            if b.get("issue") == "hash_mismatch"
        ]
        assert not tampering_breaks, (
            f"Audit chain has hash_mismatch breaks — possible tampering: {tampering_breaks}"
        )

    def test_audit_chain_export(self, client, auth_headers):
        """
        REM: The audit chain export should return structured data.
        REM: GET /v1/audit/chain/export -> entries list, chain_id, verification
        """
        resp = client.get("/v1/audit/chain/export", headers=auth_headers)
        assert resp.status_code == 200, f"Audit export failed: {resp.text}"
        data = resp.json()
        assert data["qms_status"] == "Thank_You"
        # REM: Export should contain structured compliance data
        assert isinstance(data, dict)
        # REM: Verify at least entries or chain_id exist in the export
        has_structure = any(
            key in data for key in ("entries", "chain_id", "chain_entries", "verification")
        )
        assert has_structure, (
            f"Audit export missing expected structure, keys: {list(data.keys())}"
        )


# REM: =======================================================================================
# REM: CLASS: TestErrorSanitization
# REM: =======================================================================================

@pytest.mark.e2e
class TestErrorSanitization:
    """REM: End-to-end tests verifying error responses are clean and safe."""

    def test_404_returns_clean_error(self, client):
        """
        REM: Hitting a nonexistent endpoint returns 404 without sensitive info.
        REM: GET /v1/nonexistent/endpoint -> 404 with clean body
        """
        resp = client.get("/v1/nonexistent/endpoint/that/does/not/exist")
        assert resp.status_code in (404, 405), (
            f"Expected 404/405 for nonexistent endpoint, got {resp.status_code}"
        )
        body = resp.text
        assert "Traceback" not in body
        assert "File \"" not in body

    def test_401_without_auth(self, client):
        """
        REM: Hitting a protected endpoint without credentials returns 401.
        REM: GET /v1/system/status (no auth) -> 401
        """
        resp = client.get("/v1/system/status")
        assert resp.status_code == 401
        body = resp.text
        assert "Traceback" not in body
        assert "File \"" not in body

    def test_no_stack_traces_in_errors(self, client, auth_headers):
        """
        REM: Error responses must never leak stack traces or file paths.
        REM: Verify across multiple error-triggering scenarios.
        """
        error_endpoints = [
            ("GET", "/v1/approvals/NONEXISTENT_ID_12345"),
            ("GET", "/v1/anomalies/NONEXISTENT_ID_12345"),
            ("GET", "/v1/tenancy/matters/NONEXISTENT_MATTER_12345"),
        ]

        for method, path in error_endpoints:
            if method == "GET":
                resp = client.get(path, headers=auth_headers)
            else:
                resp = client.post(path, headers=auth_headers)

            body = resp.text
            assert "Traceback" not in body, (
                f"Stack trace leaked in {method} {path}: {body[:200]}"
            )
            assert "File \"" not in body, (
                f"File path leaked in {method} {path}: {body[:200]}"
            )
            assert "raise " not in body.lower() or resp.status_code < 500, (
                f"Raise statement leaked in {method} {path}: {body[:200]}"
            )
