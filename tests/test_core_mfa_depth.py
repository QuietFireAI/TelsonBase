# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
# tests/test_core_mfa_depth.py
# REM: Depth tests for core/mfa.py — pure in-memory, no external deps

import pyotp
import pytest
from datetime import datetime, timezone

from core.mfa import MFAManager, MFARecord
from core.rbac import Role, User

# REM: Hand-built managers with fixed ids — keep them off the shared Redis store
pytestmark = pytest.mark.usefixtures("no_security_store")


BACKUP_CODE_COUNT = MFAManager.BACKUP_CODE_COUNT
BACKUP_CODE_LENGTH = MFAManager.BACKUP_CODE_LENGTH


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    monkeypatch.setattr("core.persistence.get_redis", lambda: None)


@pytest.fixture
def mgr():
    m = object.__new__(MFAManager)
    m._records = {}
    m._local_failures = {}
    return m


def _user(roles=None):
    if roles is None:
        roles = set()
    return User(
        user_id="u1",
        username="test_user",
        email="test@example.com",
        roles=roles,
        created_at=datetime.now(timezone.utc),
        is_active=True
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_backup_code_count(self):
        assert MFAManager.BACKUP_CODE_COUNT == 10

    def test_backup_code_length(self):
        assert MFAManager.BACKUP_CODE_LENGTH == 8

    def test_mfa_required_roles_has_admin(self):
        assert Role.ADMIN in MFAManager.MFA_REQUIRED_ROLES

    def test_mfa_required_roles_has_security_officer(self):
        assert Role.SECURITY_OFFICER in MFAManager.MFA_REQUIRED_ROLES

    def test_mfa_required_roles_has_super_admin(self):
        assert Role.SUPER_ADMIN in MFAManager.MFA_REQUIRED_ROLES

    def test_mfa_required_roles_count(self):
        assert len(MFAManager.MFA_REQUIRED_ROLES) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# enroll_mfa
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnrollMfa:
    def test_returns_dict(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        assert isinstance(result, dict)

    def test_has_secret(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        assert "secret" in result
        assert len(result["secret"]) > 0

    def test_has_provisioning_uri(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        assert "provisioning_uri" in result
        assert "otpauth" in result["provisioning_uri"]

    def test_has_backup_codes(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        assert "backup_codes" in result
        assert len(result["backup_codes"]) == BACKUP_CODE_COUNT

    def test_backup_code_length(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        for code in result["backup_codes"]:
            # BACKUP_CODE_LENGTH=8 chars (but token_hex(4) gives 8 hex chars)
            assert len(code) == BACKUP_CODE_LENGTH

    def test_record_stored(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        assert "user-1" in mgr._records

    def test_record_is_active(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        assert mgr._records["user-1"].is_active is True

    def test_re_enrollment_requires_explicit_replace(self, mgr):
        r1 = mgr.enroll_mfa("user-1", "Alice")
        # An active enrolment is not silently replaced
        with pytest.raises(ValueError):
            mgr.enroll_mfa("user-1", "Alice")
        assert mgr._records["user-1"].secret == r1["secret"]
        # Explicit replace generates a new secret
        r2 = mgr.enroll_mfa("user-1", "Alice", replace=True)
        assert mgr._records["user-1"].secret == r2["secret"]
        assert r2["secret"] != r1["secret"]

    def test_provisioning_uri_has_issuer(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        assert "TelsonBase" in result["provisioning_uri"]

    def test_provisioning_uri_has_username(self, mgr):
        result = mgr.enroll_mfa("user-1", "AliceName")
        assert "AliceName" in result["provisioning_uri"]


# ═══════════════════════════════════════════════════════════════════════════════
# verify_mfa
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyMfa:
    def _enroll_and_get_totp(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        secret = result["secret"]
        totp = pyotp.TOTP(secret)
        return totp

    def test_valid_token_returns_true(self, mgr):
        totp = self._enroll_and_get_totp(mgr)
        assert mgr.verify_mfa("user-1", totp.now()) is True

    def test_invalid_token_returns_false(self, mgr):
        self._enroll_and_get_totp(mgr)
        assert mgr.verify_mfa("user-1", "000000") is False

    def test_unknown_user_returns_false(self, mgr):
        assert mgr.verify_mfa("unknown", "123456") is False

    def test_replay_prevention(self, mgr):
        totp = self._enroll_and_get_totp(mgr)
        token = totp.now()
        mgr.verify_mfa("user-1", token)  # First use
        assert mgr.verify_mfa("user-1", token) is False  # Replay blocked

    def test_last_verified_at_set_on_success(self, mgr):
        totp = self._enroll_and_get_totp(mgr)
        mgr.verify_mfa("user-1", totp.now())
        assert mgr._records["user-1"].last_verified_at is not None

    def test_last_used_token_set_on_success(self, mgr):
        totp = self._enroll_and_get_totp(mgr)
        token = totp.now()
        mgr.verify_mfa("user-1", token)
        assert mgr._records["user-1"].last_used_token == token

    def test_inactive_record_returns_false(self, mgr):
        totp = self._enroll_and_get_totp(mgr)
        mgr._records["user-1"].is_active = False
        assert mgr.verify_mfa("user-1", totp.now()) is False


# ═══════════════════════════════════════════════════════════════════════════════
# verify_backup_code
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyBackupCode:
    def test_valid_backup_code_returns_true(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        code = result["backup_codes"][0]
        assert mgr.verify_backup_code("user-1", code) is True

    def test_invalid_backup_code_returns_false(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        assert mgr.verify_backup_code("user-1", "bad_code") is False

    def test_backup_code_consumed_after_use(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        code = result["backup_codes"][0]
        initial_count = len(mgr._records["user-1"].backup_codes)
        mgr.verify_backup_code("user-1", code)
        assert len(mgr._records["user-1"].backup_codes) == initial_count - 1

    def test_used_backup_code_invalid_on_second_use(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        code = result["backup_codes"][0]
        mgr.verify_backup_code("user-1", code)
        assert mgr.verify_backup_code("user-1", code) is False

    def test_unknown_user_returns_false(self, mgr):
        assert mgr.verify_backup_code("unknown", "abc") is False

    def test_inactive_record_returns_false(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        code = result["backup_codes"][0]
        mgr._records["user-1"].is_active = False
        assert mgr.verify_backup_code("user-1", code) is False

    def test_last_verified_at_set_on_success(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        code = result["backup_codes"][0]
        mgr.verify_backup_code("user-1", code)
        assert mgr._records["user-1"].last_verified_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# is_mfa_required
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsMfaRequired:
    def test_admin_requires_mfa(self, mgr):
        user = _user(roles={Role.ADMIN})
        assert mgr.is_mfa_required(user) is True

    def test_security_officer_requires_mfa(self, mgr):
        user = _user(roles={Role.SECURITY_OFFICER})
        assert mgr.is_mfa_required(user) is True

    def test_super_admin_requires_mfa(self, mgr):
        user = _user(roles={Role.SUPER_ADMIN})
        assert mgr.is_mfa_required(user) is True

    def test_viewer_does_not_require_mfa(self, mgr):
        user = _user(roles={Role.VIEWER})
        assert mgr.is_mfa_required(user) is False

    def test_no_roles_does_not_require_mfa(self, mgr):
        user = _user(roles=set())
        assert mgr.is_mfa_required(user) is False

    def test_operator_does_not_require_mfa(self, mgr):
        user = _user(roles={Role.OPERATOR})
        assert mgr.is_mfa_required(user) is False


# ═══════════════════════════════════════════════════════════════════════════════
# is_enrolled
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsEnrolled:
    def test_false_before_enrollment(self, mgr):
        assert mgr.is_enrolled("user-1") is False

    def test_true_after_enrollment(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        assert mgr.is_enrolled("user-1") is True

    def test_false_after_disable(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        mgr.disable_mfa("user-1", "admin-1")
        assert mgr.is_enrolled("user-1") is False


# ═══════════════════════════════════════════════════════════════════════════════
# disable_mfa
# ═══════════════════════════════════════════════════════════════════════════════

class TestDisableMfa:
    def test_returns_true_on_success(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        assert mgr.disable_mfa("user-1", "admin-1") is True

    def test_record_removed(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        mgr.disable_mfa("user-1", "admin-1")
        assert "user-1" not in mgr._records

    def test_returns_false_for_non_enrolled(self, mgr):
        assert mgr.disable_mfa("user-1", "admin-1") is False

    def test_returns_false_for_already_inactive(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        mgr._records["user-1"].is_active = False
        assert mgr.disable_mfa("user-1", "admin-1") is False


# ═══════════════════════════════════════════════════════════════════════════════
# get_mfa_status
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetMfaStatus:
    def test_not_enrolled_status(self, mgr):
        status = mgr.get_mfa_status("user-1")
        assert status["enrolled"] is False
        assert status["active"] is False
        assert status["user_id"] == "user-1"

    def test_enrolled_status(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        status = mgr.get_mfa_status("user-1")
        assert status["enrolled"] is True
        assert status["active"] is True

    def test_has_enrolled_at(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        status = mgr.get_mfa_status("user-1")
        assert "enrolled_at" in status
        assert isinstance(status["enrolled_at"], str)

    def test_backup_codes_remaining_count(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        status = mgr.get_mfa_status("user-1")
        assert status["backup_codes_remaining"] == BACKUP_CODE_COUNT

    def test_backup_codes_decrements_after_use(self, mgr):
        result = mgr.enroll_mfa("user-1", "Alice")
        mgr.verify_backup_code("user-1", result["backup_codes"][0])
        status = mgr.get_mfa_status("user-1")
        assert status["backup_codes_remaining"] == BACKUP_CODE_COUNT - 1

    def test_last_verified_at_none_initially(self, mgr):
        mgr.enroll_mfa("user-1", "Alice")
        status = mgr.get_mfa_status("user-1")
        assert status["last_verified_at"] is None
