# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_rbac_depth.py
# REM: Coverage depth tests for core/rbac.py
# REM: Pure unit tests — in-memory RBACManager, no DB, no Redis, no HTTP

import pytest
from datetime import datetime, timedelta, timezone

from core.rbac import (
    Permission, Role, ROLE_PERMISSIONS,
    User, Session, RBACManager,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════

class TestPermissionEnum:
    def test_view_dashboard(self):
        assert Permission.VIEW_DASHBOARD == "view:dashboard"

    def test_view_agents(self):
        assert Permission.VIEW_AGENTS == "view:agents"

    def test_approve_requests(self):
        assert Permission.APPROVE_REQUESTS == "action:approve"

    def test_manage_agents(self):
        assert Permission.MANAGE_AGENTS == "manage:agents"

    def test_admin_config(self):
        assert Permission.ADMIN_CONFIG == "admin:config"

    def test_security_quarantine(self):
        assert Permission.SECURITY_QUARANTINE == "security:quarantine"

    def test_security_audit(self):
        assert Permission.SECURITY_AUDIT == "security:audit"

    def test_security_override(self):
        assert Permission.SECURITY_OVERRIDE == "security:override"

    def test_at_least_16_permissions(self):
        assert len(Permission) >= 16


class TestRoleEnum:
    def test_viewer(self):
        assert Role.VIEWER == "viewer"

    def test_operator(self):
        assert Role.OPERATOR == "operator"

    def test_admin(self):
        assert Role.ADMIN == "admin"

    def test_security_officer(self):
        assert Role.SECURITY_OFFICER == "security_officer"

    def test_super_admin(self):
        assert Role.SUPER_ADMIN == "super_admin"

    def test_five_roles(self):
        assert len(Role) == 5


class TestRolePermissionsMapping:
    def test_viewer_has_view_permissions(self):
        perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert Permission.VIEW_DASHBOARD in perms
        assert Permission.VIEW_AGENTS in perms

    def test_viewer_cannot_approve(self):
        perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert Permission.APPROVE_REQUESTS not in perms

    def test_operator_can_approve(self):
        perms = ROLE_PERMISSIONS[Role.OPERATOR]
        assert Permission.APPROVE_REQUESTS in perms
        assert Permission.REJECT_REQUESTS in perms

    def test_admin_can_manage_agents(self):
        perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.MANAGE_AGENTS in perms

    def test_security_officer_has_security_perms(self):
        perms = ROLE_PERMISSIONS[Role.SECURITY_OFFICER]
        assert Permission.SECURITY_QUARANTINE in perms
        assert Permission.SECURITY_PROMOTE in perms
        assert Permission.SECURITY_AUDIT in perms

    def test_super_admin_has_all_permissions(self):
        perms = ROLE_PERMISSIONS[Role.SUPER_ADMIN]
        for p in Permission:
            assert p in perms

    def test_all_roles_have_entries(self):
        for role in Role:
            assert role in ROLE_PERMISSIONS


# ═══════════════════════════════════════════════════════════════════════════════
# User dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserDataclass:
    def _make_user(self, roles=None, custom=None, denied=None, active=True):
        return User(
            user_id="u-001",
            username="alice",
            email="alice@example.com",
            roles=roles or {Role.VIEWER},
            created_at=datetime.now(timezone.utc),
            is_active=active,
            custom_permissions=custom or set(),
            denied_permissions=denied or set(),
        )

    def test_get_all_permissions_viewer(self):
        u = self._make_user(roles={Role.VIEWER})
        perms = u.get_all_permissions()
        assert Permission.VIEW_DASHBOARD in perms

    def test_get_all_permissions_operator(self):
        u = self._make_user(roles={Role.OPERATOR})
        perms = u.get_all_permissions()
        assert Permission.APPROVE_REQUESTS in perms

    def test_get_all_permissions_multiple_roles(self):
        u = self._make_user(roles={Role.VIEWER, Role.OPERATOR})
        perms = u.get_all_permissions()
        assert Permission.APPROVE_REQUESTS in perms
        assert Permission.VIEW_DASHBOARD in perms

    def test_custom_permissions_added(self):
        u = self._make_user(
            roles={Role.VIEWER},
            custom={Permission.MANAGE_AGENTS}
        )
        assert u.has_permission(Permission.MANAGE_AGENTS)

    def test_denied_permissions_removed(self):
        u = self._make_user(
            roles={Role.OPERATOR},
            denied={Permission.APPROVE_REQUESTS}
        )
        assert not u.has_permission(Permission.APPROVE_REQUESTS)

    def test_inactive_user_has_no_permissions(self):
        u = self._make_user(roles={Role.SUPER_ADMIN}, active=False)
        assert not u.has_permission(Permission.VIEW_DASHBOARD)

    def test_has_permission_true(self):
        u = self._make_user(roles={Role.ADMIN})
        assert u.has_permission(Permission.MANAGE_AGENTS) is True

    def test_has_permission_false(self):
        u = self._make_user(roles={Role.VIEWER})
        assert u.has_permission(Permission.MANAGE_AGENTS) is False

    def test_to_dict_keys(self):
        u = self._make_user()
        d = u.to_dict()
        assert "user_id" in d
        assert "username" in d
        assert "email" in d
        assert "roles" in d
        assert "is_active" in d
        assert "mfa_enabled" in d
        assert "created_at" in d
        assert "permission_count" in d

    def test_to_dict_last_login_none(self):
        u = self._make_user()
        d = u.to_dict()
        assert d["last_login"] is None

    def test_to_dict_roles_are_strings(self):
        u = self._make_user(roles={Role.VIEWER})
        d = u.to_dict()
        assert all(isinstance(r, str) for r in d["roles"])


# ═══════════════════════════════════════════════════════════════════════════════
# Session dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionDataclass:
    def test_not_expired(self):
        now = datetime.now(timezone.utc)
        session = Session(
            session_id="sess-001",
            user_id="u-001",
            created_at=now,
            expires_at=now + timedelta(hours=8),
        )
        assert session.is_expired() is False

    def test_expired(self):
        now = datetime.now(timezone.utc)
        session = Session(
            session_id="sess-002",
            user_id="u-001",
            created_at=now - timedelta(hours=9),
            expires_at=now - timedelta(hours=1),
        )
        assert session.is_expired() is True


# ═══════════════════════════════════════════════════════════════════════════════
# RBACManager
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mgr(monkeypatch):
    """Fresh RBACManager for each test — Redis I/O patched out (pure in-memory)."""
    monkeypatch.setattr(RBACManager, "_load_from_redis", lambda self: None)
    monkeypatch.setattr(RBACManager, "_save_user", lambda self, user: None)
    return RBACManager()


class TestRBACManagerCreateUser:
    def test_create_user_returns_user(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        assert user is not None
        assert user.username == "bob"

    def test_create_user_has_user_id(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        assert user.user_id.startswith("user_")

    def test_create_user_default_role_viewer_on_unknown(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["nonexistent_role"])
        # Falls back to VIEWER
        assert Role.VIEWER in user.roles

    def test_create_user_empty_roles_defaults_viewer(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", [])
        assert Role.VIEWER in user.roles

    def test_create_user_admin_role(self, mgr):
        user = mgr.create_user("alice", "alice@test.com", ["admin"])
        assert Role.ADMIN in user.roles

    def test_create_user_multiple_roles(self, mgr):
        user = mgr.create_user("carol", "carol@test.com", ["viewer", "operator"])
        assert Role.VIEWER in user.roles
        assert Role.OPERATOR in user.roles

    def test_create_user_is_active(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        assert user.is_active is True


class TestRBACManagerGetUser:
    def test_get_user_by_id(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        found = mgr.get_user(user.user_id)
        assert found is not None
        assert found.username == "bob"

    def test_get_user_nonexistent(self, mgr):
        assert mgr.get_user("nonexistent-id") is None

    def test_get_user_by_username(self, mgr):
        mgr.create_user("alice", "alice@test.com", ["viewer"])
        found = mgr.get_user_by_username("alice")
        assert found is not None
        assert found.username == "alice"

    def test_get_user_by_username_nonexistent(self, mgr):
        assert mgr.get_user_by_username("nobody") is None


class TestRBACManagerAssignRole:
    def test_assign_role_returns_true(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        result = mgr.assign_role(user.user_id, "operator")
        assert result is True
        assert Role.OPERATOR in user.roles

    def test_assign_invalid_role_returns_false(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        result = mgr.assign_role(user.user_id, "nonexistent_role")
        assert result is False

    def test_assign_role_unknown_user_returns_false(self, mgr):
        result = mgr.assign_role("unknown-id", "admin")
        assert result is False


class TestRBACManagerRemoveRole:
    def test_remove_role_returns_true(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer", "operator"])
        result = mgr.remove_role(user.user_id, "operator")
        assert result is True
        assert Role.OPERATOR not in user.roles

    def test_remove_role_not_present_returns_false(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        result = mgr.remove_role(user.user_id, "admin")
        assert result is False

    def test_remove_invalid_role_returns_false(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        result = mgr.remove_role(user.user_id, "bogus_role")
        assert result is False

    def test_remove_role_unknown_user_returns_false(self, mgr):
        result = mgr.remove_role("unknown-id", "viewer")
        assert result is False


class TestRBACManagerDeactivateUser:
    def test_deactivate_user(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        result = mgr.deactivate_user(user.user_id)
        assert result is True
        assert user.is_active is False

    def test_deactivate_unknown_user(self, mgr):
        assert mgr.deactivate_user("unknown-id") is False

    def test_deactivate_invalidates_sessions(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        session = mgr.create_session(user.user_id)
        mgr.deactivate_user(user.user_id)
        assert session.is_valid is False


class TestRBACManagerSessions:
    def test_create_session_returns_session(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        session = mgr.create_session(user.user_id)
        assert session is not None
        assert session.session_id.startswith("sess_")

    def test_create_session_inactive_user_returns_none(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        mgr.deactivate_user(user.user_id)
        session = mgr.create_session(user.user_id)
        assert session is None

    def test_create_session_unknown_user_returns_none(self, mgr):
        session = mgr.create_session("unknown-id")
        assert session is None

    def test_create_session_with_metadata(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        session = mgr.create_session(user.user_id, ip_address="1.2.3.4",
                                     user_agent="TestAgent/1.0")
        assert session.ip_address == "1.2.3.4"
        assert session.user_agent == "TestAgent/1.0"

    def test_validate_session_returns_user(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        session = mgr.create_session(user.user_id)
        found = mgr.validate_session(session.session_id)
        assert found is not None
        assert found.username == "bob"

    def test_validate_session_nonexistent(self, mgr):
        assert mgr.validate_session("sess_nonexistent") is None

    def test_validate_session_invalidated(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        session = mgr.create_session(user.user_id)
        mgr.invalidate_session(session.session_id)
        assert mgr.validate_session(session.session_id) is None

    def test_invalidate_session_returns_true(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        session = mgr.create_session(user.user_id)
        assert mgr.invalidate_session(session.session_id) is True

    def test_invalidate_nonexistent_session(self, mgr):
        assert mgr.invalidate_session("sess_nonexistent") is False

    def test_create_session_updates_last_login(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        assert user.last_login is None
        mgr.create_session(user.user_id)
        assert user.last_login is not None


class TestRBACManagerPermissionCheck:
    def test_check_permission_granted(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["operator"])
        session = mgr.create_session(user.user_id)
        assert mgr.check_permission(session.session_id, Permission.APPROVE_REQUESTS) is True

    def test_check_permission_denied(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        session = mgr.create_session(user.user_id)
        assert mgr.check_permission(session.session_id, Permission.MANAGE_AGENTS) is False

    def test_check_permission_invalid_session(self, mgr):
        assert mgr.check_permission("invalid-sess", Permission.VIEW_DASHBOARD) is False


class TestRBACManagerAPIKey:
    def test_register_api_key(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["admin"])
        result = mgr.register_api_key("test-key-001", user.user_id)
        assert result is True

    def test_register_api_key_unknown_user(self, mgr):
        result = mgr.register_api_key("test-key-001", "unknown-id")
        assert result is False

    def test_get_user_by_api_key(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["admin"])
        mgr.register_api_key("key-abc", user.user_id)
        found = mgr.get_user_by_api_key("key-abc")
        assert found is not None
        assert found.username == "bob"

    def test_get_user_by_unknown_api_key(self, mgr):
        assert mgr.get_user_by_api_key("unknown-key") is None

    def test_check_api_key_permission_granted(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["admin"])
        mgr.register_api_key("key-abc", user.user_id)
        assert mgr.check_api_key_permission("key-abc", Permission.MANAGE_AGENTS) is True

    def test_check_api_key_permission_denied_for_viewer(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        mgr.register_api_key("key-abc", user.user_id)
        assert mgr.check_api_key_permission("key-abc", Permission.MANAGE_AGENTS) is False

    def test_check_api_key_permission_unknown_key(self, mgr):
        assert mgr.check_api_key_permission("no-such-key", Permission.VIEW_DASHBOARD) is False

    def test_check_api_key_permission_inactive_user(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["admin"])
        mgr.register_api_key("key-abc", user.user_id)
        mgr.deactivate_user(user.user_id)
        assert mgr.check_api_key_permission("key-abc", Permission.ADMIN_CONFIG) is False


class TestRBACManagerListAndReport:
    def test_list_users_empty(self, mgr):
        assert mgr.list_users() == []

    def test_list_users_returns_dicts(self, mgr):
        mgr.create_user("alice", "alice@test.com", ["viewer"])
        mgr.create_user("bob", "bob@test.com", ["admin"])
        result = mgr.list_users()
        assert len(result) == 2
        assert all(isinstance(u, dict) for u in result)

    def test_list_roles_returns_all_roles(self, mgr):
        roles = mgr.list_roles()
        role_names = [r["role"] for r in roles]
        assert "viewer" in role_names
        assert "admin" in role_names
        assert "super_admin" in role_names

    def test_list_roles_each_has_permissions(self, mgr):
        for entry in mgr.list_roles():
            assert "permissions" in entry
            assert isinstance(entry["permissions"], list)

    def test_get_permission_report(self, mgr):
        user = mgr.create_user("alice", "alice@test.com", ["admin"])
        report = mgr.get_permission_report(user.user_id)
        assert report is not None
        assert "user_id" in report
        assert "permissions" in report
        assert "can_approve" in report
        assert "can_manage_agents" in report

    def test_get_permission_report_nonexistent_user(self, mgr):
        assert mgr.get_permission_report("unknown-id") is None

    def test_permission_report_security_officer_flag(self, mgr):
        user = mgr.create_user("alice", "alice@test.com", ["security_officer"])
        report = mgr.get_permission_report(user.user_id)
        assert report["is_security_officer"] is True

    def test_permission_report_not_security_officer(self, mgr):
        user = mgr.create_user("bob", "bob@test.com", ["viewer"])
        report = mgr.get_permission_report(user.user_id)
        assert report["is_security_officer"] is False
