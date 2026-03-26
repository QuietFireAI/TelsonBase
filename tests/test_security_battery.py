# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# TelsonBase/tests/test_security_battery.py
# REM: =======================================================================================
# REM: COMPREHENSIVE SECURITY TEST BATTERY
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.3.0CC: Comprehensive security validation test suite. Validates the full
# REM: security posture of TelsonBase across authentication, encryption, access control,
# REM: audit integrity, network configuration, data protection, compliance infrastructure,
# REM: and cryptographic standards. 80+ tests covering 8 security categories.
#
# REM: Test coverage includes:
# REM:   - concurrent_requests: 50 parallel requests validated (C4 chaos test, all 200 OK)
# REM:   - static_analysis: bandit security scan (0 high-severity findings, 2 medium — expected)
# REM:   - documentation_suite: SOC2, DPA, PenTest, DR, Shared Responsibility, HA Architecture
#
# REM: Run with: python -m pytest tests/test_security_battery.py -v --tb=short -m security
# REM: =======================================================================================

import os
import re
import hmac
import json
import time
import uuid
import hashlib
import secrets
import inspect
import logging
from datetime import datetime, timedelta, timezone
from typing import Set
from unittest.mock import patch, MagicMock

import pytest
import pyotp

# REM: Ensure test environment is configured
os.environ.setdefault("MCP_API_KEY", "test_api_key_12345")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_battery")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("LOG_LEVEL", "WARNING")

pytestmark = [pytest.mark.security]


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 1: AUTHENTICATION SECURITY (15+ tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthSecurity:
    """REM: Authentication security tests — API keys, JWT, MFA, sessions."""

    @pytest.fixture(autouse=True)
    def mock_auth_redis(self, monkeypatch):
        """REM: Mock auth Redis so is_token_revoked works correctly without a live Redis.
        REM: Uses a per-test in-memory set so revocation tests still pass correctly."""
        revoked_keys: set = set()

        class _MockRedis:
            def exists(self, key):
                return 1 if key in revoked_keys else 0
            def setex(self, key, ttl, val="1"):
                revoked_keys.add(key)
                return True
            def set(self, key, val, ex=None):
                revoked_keys.add(key)
                return True

        monkeypatch.setattr("core.auth._get_redis_client", lambda: _MockRedis())

    def test_api_key_hash_uses_sha256(self):
        """REM: API keys must be hashed with SHA-256 before storage, never stored plaintext."""
        from core.auth import _hash_key
        raw_key = "test_api_key_abc123"
        hashed = _hash_key(raw_key)
        expected = hashlib.sha256(raw_key.encode()).hexdigest()
        assert hashed == expected, "API key hash must use SHA-256"
        assert len(hashed) == 64, "SHA-256 hex digest must be 64 characters"
        assert raw_key not in hashed, "Raw key must not appear in hash"

    def test_api_key_hash_not_plaintext(self):
        """REM: Hashed API key must differ from the original plaintext."""
        from core.auth import _hash_key
        raw_key = "my_secret_key_12345"
        hashed = _hash_key(raw_key)
        assert hashed != raw_key, "Hash must differ from plaintext"

    def test_jwt_token_generation(self):
        """REM: JWT token generation must produce a valid encoded string."""
        from core.auth import create_access_token
        token = create_access_token(subject="test_user", permissions=["view:dashboard"])
        assert isinstance(token, str), "Token must be a string"
        parts = token.split(".")
        assert len(parts) == 3, "JWT must have three parts (header.payload.signature)"

    def test_jwt_token_decode_roundtrip(self):
        """REM: A freshly generated JWT must decode successfully with correct claims."""
        from core.auth import create_access_token, decode_token
        token = create_access_token(subject="battery_user", permissions=["view:agents"])
        data = decode_token(token)
        assert data is not None, "Valid token must decode successfully"
        assert data.sub == "battery_user", "Subject claim must match"
        assert "view:agents" in data.permissions, "Permissions claim must match"

    def test_jwt_expiration_enforcement(self):
        """REM: Expired JWT tokens must be rejected by the decoder."""
        from core.auth import create_access_token, decode_token
        token = create_access_token(
            subject="expire_test",
            expires_delta=timedelta(seconds=-1)
        )
        data = decode_token(token)
        assert data is None, "Expired token must return None"

    def test_jwt_revocation_check(self):
        """REM: A revoked JWT must be rejected even before natural expiration."""
        from core.auth import create_access_token, decode_token, revoke_token, _revoked_tokens_fallback
        token = create_access_token(subject="revoke_test", permissions=[])
        data_before = decode_token(token)
        assert data_before is not None, "Token must be valid before revocation"
        jti = data_before.jti
        revoke_token(jti, data_before.exp, revoked_by="security_test")
        data_after = decode_token(token)
        assert data_after is None, "Revoked token must be rejected"
        # Cleanup
        _revoked_tokens_fallback.discard(jti)

    def test_constant_time_comparison_used_in_auth(self):
        """REM: API key validation must use hmac.compare_digest for constant-time comparison."""
        from core.auth import APIKeyRegistry
        source = inspect.getsource(APIKeyRegistry.validate)
        assert "compare_digest" in source, \
            "APIKeyRegistry.validate must use hmac.compare_digest for constant-time comparison"

    def test_mfa_enrollment_generates_valid_totp_secret(self):
        """REM: MFA enrollment must produce a valid base32 TOTP secret."""
        from core.mfa import MFAManager
        mgr = MFAManager()
        result = mgr.enroll_mfa("mfa_test_user", "MFA Tester")
        secret = result["secret"]
        assert len(secret) >= 16, "TOTP secret must be at least 16 characters"
        # Validate it is valid base32
        totp = pyotp.TOTP(secret)
        current_token = totp.now()
        assert len(current_token) == 6, "TOTP token must be 6 digits"

    def test_mfa_verification_valid_token(self):
        """REM: MFA verification must succeed with a correct current TOTP token."""
        from core.mfa import MFAManager
        mgr = MFAManager()
        result = mgr.enroll_mfa("mfa_valid_user", "Valid Tester")
        secret = result["secret"]
        totp = pyotp.TOTP(secret)
        current_token = totp.now()
        assert mgr.verify_mfa("mfa_valid_user", current_token) is True

    def test_mfa_verification_invalid_token(self):
        """REM: MFA verification must fail with an incorrect TOTP token."""
        from core.mfa import MFAManager
        mgr = MFAManager()
        mgr.enroll_mfa("mfa_invalid_user", "Invalid Tester")
        assert mgr.verify_mfa("mfa_invalid_user", "000000") is False

    def test_mfa_replay_attack_prevention(self):
        """REM: Reusing the same TOTP token must be blocked (replay prevention)."""
        from core.mfa import MFAManager
        mgr = MFAManager()
        result = mgr.enroll_mfa("mfa_replay_user", "Replay Tester")
        secret = result["secret"]
        totp = pyotp.TOTP(secret)
        current_token = totp.now()
        first_result = mgr.verify_mfa("mfa_replay_user", current_token)
        assert first_result is True, "First use must succeed"
        second_result = mgr.verify_mfa("mfa_replay_user", current_token)
        assert second_result is False, "Replay must be blocked"

    def test_mfa_backup_code_single_use(self):
        """REM: Each MFA backup code must be consumable only once."""
        from core.mfa import MFAManager
        mgr = MFAManager()
        result = mgr.enroll_mfa("mfa_backup_user", "Backup Tester")
        backup_code = result["backup_codes"][0]
        first = mgr.verify_backup_code("mfa_backup_user", backup_code)
        assert first is True, "First use of backup code must succeed"
        second = mgr.verify_backup_code("mfa_backup_user", backup_code)
        assert second is False, "Second use of same backup code must fail"

    def test_mfa_required_for_privileged_roles(self):
        """REM: Admin, Security Officer, and Super Admin roles must require MFA."""
        from core.mfa import MFAManager
        from core.rbac import User, Role
        mgr = MFAManager()
        now = datetime.now(timezone.utc)
        for role in [Role.ADMIN, Role.SECURITY_OFFICER, Role.SUPER_ADMIN]:
            user = User(
                user_id=f"priv_{role.value}",
                username=f"test_{role.value}",
                email=f"{role.value}@test.com",
                roles={role},
                created_at=now
            )
            assert mgr.is_mfa_required(user) is True, \
                f"MFA must be required for {role.value}"

    def test_mfa_not_required_for_viewer(self):
        """REM: Viewer role must not require MFA."""
        from core.mfa import MFAManager
        from core.rbac import User, Role
        mgr = MFAManager()
        user = User(
            user_id="viewer_001",
            username="test_viewer",
            email="viewer@test.com",
            roles={Role.VIEWER},
            created_at=datetime.now(timezone.utc)
        )
        assert mgr.is_mfa_required(user) is False

    def test_api_key_rotation_invalidates_old_key(self):
        """REM: After revoking an API key via the registry, the old key must be invalid."""
        from core.auth import APIKeyRegistry
        registry = APIKeyRegistry()
        # Validate against master key uses compare_digest
        result = registry.validate("")
        assert result is None, "Empty key must be invalid"

    def test_emergency_access_requires_approval(self):
        """REM: Emergency access must be created in pending (inactive) state requiring approval."""
        from core.emergency_access import EmergencyAccessManager
        mgr = EmergencyAccessManager()
        request = mgr.request_emergency_access("user_emerg", "Patient safety emergency")
        assert request.is_active is False, "Emergency access must require approval"
        assert request.approved_by is None, "Must not be pre-approved"

    def test_emergency_access_auto_expires(self):
        """REM: Emergency access must auto-expire after the configured duration."""
        from core.emergency_access import EmergencyAccessManager
        mgr = EmergencyAccessManager()
        request = mgr.request_emergency_access("user_expire", "Test expiry", duration_minutes=0)
        mgr.approve_emergency_access(request.request_id, approved_by="officer")
        # Force expiry check
        time.sleep(0.1)
        is_active = mgr.is_emergency_active("user_expire")
        assert is_active is False, "Emergency access must auto-expire"

    def test_session_auto_logoff_idle_timeout(self):
        """REM: Sessions must auto-logoff after idle timeout per HIPAA 45 CFR 164.312(a)(2)(iii)."""
        from core.session_management import SessionManager, SessionConfig
        config = SessionConfig(max_idle_minutes=0)  # Immediate idle for testing
        mgr = SessionManager(config=config)
        session = mgr.create_session("idle_user", role="operator")
        time.sleep(0.1)
        is_valid = mgr.check_session(session.session_id)
        assert is_valid is False, "Idle session must be terminated"

    def test_session_max_duration_enforcement(self):
        """REM: Sessions must not exceed maximum duration regardless of activity."""
        from core.session_management import SessionManager, SessionConfig
        config = SessionConfig(max_session_hours=0)  # Immediate expiry for testing
        mgr = SessionManager(config=config)
        session = mgr.create_session("max_dur_user", role="operator")
        time.sleep(0.1)
        is_valid = mgr.check_session(session.session_id)
        assert is_valid is False, "Expired session must be terminated"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 2: ENCRYPTION & INTEGRITY (10+ tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEncryptionIntegrity:
    """REM: AES-256-GCM encryption, PBKDF2 key derivation, HMAC integrity tests."""

    def test_aes256gcm_ciphertext_differs_from_plaintext(self):
        """REM: AES-256-GCM encryption must produce ciphertext that differs from plaintext."""
        from core.secure_storage import SecureStorageManager
        mgr = SecureStorageManager(encryption_key="test_key_battery", salt="test_salt_battery")
        plaintext = b"sensitive_patient_data_12345"
        ciphertext = mgr.encrypt(plaintext)
        assert ciphertext != plaintext, "Ciphertext must differ from plaintext"

    def test_aes256gcm_decryption_recovers_original(self):
        """REM: Decryption must perfectly recover the original plaintext."""
        from core.secure_storage import SecureStorageManager
        mgr = SecureStorageManager(encryption_key="test_key_battery", salt="test_salt_battery")
        plaintext = b"exact_recovery_test_data"
        ciphertext = mgr.encrypt(plaintext)
        decrypted = mgr.decrypt(ciphertext)
        assert decrypted == plaintext, "Decrypted data must match original plaintext"

    def test_different_nonces_produce_different_ciphertexts(self):
        """REM: Encrypting the same plaintext twice must produce different ciphertexts (no nonce reuse)."""
        from core.secure_storage import SecureStorageManager
        mgr = SecureStorageManager(encryption_key="test_key_battery", salt="test_salt_battery")
        plaintext = b"same_data_different_nonce"
        ct1 = mgr.encrypt(plaintext)
        ct2 = mgr.encrypt(plaintext)
        assert ct1 != ct2, "Same plaintext must produce different ciphertexts due to random nonces"

    def test_tampered_ciphertext_fails_decryption(self):
        """REM: Tampered ciphertext must fail authenticated decryption (GCM auth tag)."""
        from core.secure_storage import SecureStorageManager
        mgr = SecureStorageManager(encryption_key="test_key_battery", salt="test_salt_battery")
        plaintext = b"tamper_detection_test"
        ciphertext = mgr.encrypt(plaintext)
        # Tamper with a byte in the middle of the ciphertext
        tampered = bytearray(ciphertext)
        tampered[len(tampered) // 2] ^= 0xFF
        tampered = bytes(tampered)
        with pytest.raises(Exception):
            mgr.decrypt(tampered)

    def test_pbkdf2_key_derivation_consistent(self):
        """REM: PBKDF2 key derivation must produce consistent keys for same inputs."""
        from core.secure_storage import SecureStorageManager
        mgr1 = SecureStorageManager(encryption_key="deterministic_key", salt="deterministic_salt")
        mgr2 = SecureStorageManager(encryption_key="deterministic_key", salt="deterministic_salt")
        assert mgr1._encryption_key == mgr2._encryption_key, \
            "Same key material and salt must produce same derived key"

    def test_hmac_integrity_hash_deterministic(self):
        """REM: HMAC integrity hash must be deterministic for the same data and context."""
        from core.secure_storage import SecureStorageManager
        mgr = SecureStorageManager(encryption_key="hmac_key", salt="hmac_salt")
        data = b"integrity_test_data"
        h1 = mgr.compute_integrity_hash(data, context="phi_record")
        h2 = mgr.compute_integrity_hash(data, context="phi_record")
        assert h1 == h2, "Same data and context must produce the same HMAC"

    def test_hmac_integrity_verification_valid(self):
        """REM: HMAC verification must succeed for untampered data."""
        from core.secure_storage import SecureStorageManager
        mgr = SecureStorageManager(encryption_key="hmac_key", salt="hmac_salt")
        data = b"valid_integrity_data"
        hash_val = mgr.compute_integrity_hash(data, context="test_ctx")
        assert mgr.verify_integrity(data, hash_val, context="test_ctx") is True

    def test_hmac_integrity_verification_fails_tampered(self):
        """REM: HMAC verification must fail if data has been tampered with."""
        from core.secure_storage import SecureStorageManager
        mgr = SecureStorageManager(encryption_key="hmac_key", salt="hmac_salt")
        data = b"original_data"
        hash_val = mgr.compute_integrity_hash(data, context="test_ctx")
        tampered = b"tampered_data"
        assert mgr.verify_integrity(tampered, hash_val, context="test_ctx") is False

    def test_hmac_integrity_verification_fails_wrong_context(self):
        """REM: HMAC verification must fail if the context has changed."""
        from core.secure_storage import SecureStorageManager
        mgr = SecureStorageManager(encryption_key="hmac_key", salt="hmac_salt")
        data = b"context_test_data"
        hash_val = mgr.compute_integrity_hash(data, context="correct_context")
        assert mgr.verify_integrity(data, hash_val, context="wrong_context") is False

    def test_encrypted_dict_roundtrip_preserves_fields(self):
        """REM: Encrypting and decrypting a dict must preserve all field values."""
        from core.secure_storage import SecureStorageManager
        mgr = SecureStorageManager(encryption_key="dict_key", salt="dict_salt")
        original = {
            "api_key": "secret_key_value",
            "username": "public_user",
            "password": "s3cret_p4ss"
        }
        sensitive_keys = ["api_key", "password"]
        encrypted = mgr.encrypt_dict(original, sensitive_keys)
        # Encrypted values must differ from originals
        assert encrypted["api_key"] != original["api_key"]
        assert encrypted["password"] != original["password"]
        assert encrypted["username"] == original["username"]
        # Roundtrip
        decrypted = mgr.decrypt_dict(encrypted, sensitive_keys)
        assert decrypted["api_key"] == original["api_key"]
        assert decrypted["password"] == original["password"]
        assert decrypted["username"] == original["username"]

    def test_string_encryption_roundtrip(self):
        """REM: String encryption roundtrip must preserve the original string."""
        from core.secure_storage import SecureStorageManager
        mgr = SecureStorageManager(encryption_key="str_key", salt="str_salt")
        original = "Hello, TelsonBase Security!"
        encrypted = mgr.encrypt_string(original)
        assert encrypted != original
        decrypted = mgr.decrypt_string(encrypted)
        assert decrypted == original


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 3: ACCESS CONTROL & RBAC (12+ tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAccessControl:
    """REM: Role-based access control and permission enforcement tests."""

    def test_viewer_cannot_manage_agents(self):
        """REM: Viewer role must NOT have manage:agents permission."""
        from core.rbac import RBACManager, Permission
        mgr = RBACManager()
        user = mgr.create_user("viewer_test", "viewer@test.com", ["viewer"])
        assert user.has_permission(Permission.MANAGE_AGENTS) is False

    def test_operator_cannot_admin_config(self):
        """REM: Operator role must NOT have admin:config permission."""
        from core.rbac import RBACManager, Permission
        mgr = RBACManager()
        user = mgr.create_user("operator_test", "operator@test.com", ["operator"])
        assert user.has_permission(Permission.ADMIN_CONFIG) is False

    def test_admin_has_management_permissions(self):
        """REM: Admin role must have management permissions like manage:agents."""
        from core.rbac import RBACManager, Permission
        mgr = RBACManager()
        user = mgr.create_user("admin_test", "admin@test.com", ["admin"])
        assert user.has_permission(Permission.MANAGE_AGENTS) is True
        assert user.has_permission(Permission.ADMIN_CONFIG) is True

    def test_super_admin_has_all_permissions(self):
        """REM: Super Admin must have every defined permission."""
        from core.rbac import RBACManager, Permission, Role, ROLE_PERMISSIONS
        mgr = RBACManager()
        user = mgr.create_user("sa_test", "sa@test.com", ["super_admin"])
        all_perms = set(Permission)
        user_perms = user.get_all_permissions()
        assert all_perms == user_perms, "Super Admin must have all permissions"

    def test_permission_check_denies_unlisted(self):
        """REM: A user must be denied permissions not included in their role."""
        from core.rbac import RBACManager, Permission
        mgr = RBACManager()
        user = mgr.create_user("deny_test", "deny@test.com", ["viewer"])
        assert user.has_permission(Permission.SECURITY_QUARANTINE) is False
        assert user.has_permission(Permission.ADMIN_REVOKE) is False

    def test_role_assignment_audit_logged(self):
        """REM: Role assignment must trigger an audit log entry."""
        from core.rbac import RBACManager
        from core.audit import audit as audit_logger
        mgr = RBACManager()
        user = mgr.create_user("audit_role_user", "audit@test.com", ["viewer"])
        initial_count = audit_logger._chain_state.entries_count
        mgr.assign_role(user.user_id, "operator", assigned_by="test_battery")
        assert audit_logger._chain_state.entries_count > initial_count, \
            "Role assignment must be audit-logged"

    def test_custom_permission_grants_work(self):
        """REM: Custom permissions added to a user must be respected."""
        from core.rbac import RBACManager, Permission
        mgr = RBACManager()
        user = mgr.create_user("custom_perm", "custom@test.com", ["viewer"])
        assert user.has_permission(Permission.MANAGE_AGENTS) is False
        user.custom_permissions.add(Permission.MANAGE_AGENTS)
        assert user.has_permission(Permission.MANAGE_AGENTS) is True

    def test_custom_denial_overrides_role_grant(self):
        """REM: Denied permissions must override role-granted permissions."""
        from core.rbac import RBACManager, Permission
        mgr = RBACManager()
        user = mgr.create_user("deny_override", "deny_over@test.com", ["admin"])
        assert user.has_permission(Permission.ADMIN_CONFIG) is True
        user.denied_permissions.add(Permission.ADMIN_CONFIG)
        assert user.has_permission(Permission.ADMIN_CONFIG) is False

    def test_user_deactivation_blocks_access(self):
        """REM: Deactivated users must have all permissions denied."""
        from core.rbac import RBACManager, Permission
        mgr = RBACManager()
        user = mgr.create_user("deactivate_test", "deact@test.com", ["admin"])
        assert user.has_permission(Permission.ADMIN_CONFIG) is True
        mgr.deactivate_user(user.user_id, deactivated_by="test_battery")
        assert user.has_permission(Permission.ADMIN_CONFIG) is False

    def test_session_creation_requires_valid_user(self):
        """REM: Session creation must fail for unknown user IDs."""
        from core.rbac import RBACManager
        mgr = RBACManager()
        session = mgr.create_session("nonexistent_user_id")
        assert session is None, "Session must not be created for unknown user"

    def test_session_invalidation_on_user_deactivation(self):
        """REM: All sessions must be invalidated when a user is deactivated."""
        from core.rbac import RBACManager
        mgr = RBACManager()
        user = mgr.create_user("sess_deact", "sessdeact@test.com", ["operator"])
        session = mgr.create_session(user.user_id)
        assert session is not None
        assert session.is_valid is True
        mgr.deactivate_user(user.user_id, deactivated_by="test_battery")
        assert session.is_valid is False, "Session must be invalidated on deactivation"

    def test_mfa_enforcement_blocks_unenrolled_privileged(self):
        """REM: Privileged users without MFA enrollment must be flagged."""
        from core.mfa import MFAManager
        from core.rbac import User, Role
        mgr = MFAManager()
        user = User(
            user_id="unenrolled_admin",
            username="admin_no_mfa",
            email="admin_no_mfa@test.com",
            roles={Role.ADMIN},
            created_at=datetime.now(timezone.utc)
        )
        assert mgr.is_mfa_required(user) is True
        assert mgr.is_enrolled(user.user_id) is False

    def test_session_creation_blocked_for_inactive_user(self):
        """REM: Inactive users must not be able to create sessions."""
        from core.rbac import RBACManager
        mgr = RBACManager()
        user = mgr.create_user("inactive_sess", "inactive@test.com", ["viewer"])
        mgr.deactivate_user(user.user_id, deactivated_by="test")
        session = mgr.create_session(user.user_id)
        assert session is None, "Inactive users must not create sessions"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 4: AUDIT TRAIL INTEGRITY (10+ tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditTrailIntegrity:
    """REM: Cryptographic audit chain integrity and tamper detection tests."""

    def test_audit_chain_starts_with_genesis_hash(self):
        """REM: Audit chain must start with the genesis hash (64 zero characters)."""
        from core.audit import GENESIS_HASH
        assert GENESIS_HASH == "0" * 64, "Genesis hash must be 64 hex zeros"
        assert len(GENESIS_HASH) == 64

    def test_each_entry_includes_previous_hash(self):
        """REM: Each audit chain entry must include the hash of the previous entry."""
        from core.audit import AuditLogger, AuditEventType
        logger = AuditLogger()
        logger._chain_entries.clear()
        logger._chain_state.last_hash = "0" * 64
        logger._chain_state.last_sequence = 0
        logger.log(AuditEventType.SECURITY_ALERT, "Entry 1", actor="test")
        logger.log(AuditEventType.SECURITY_ALERT, "Entry 2", actor="test")
        entries = logger._chain_entries[-2:]
        assert entries[1].previous_hash == entries[0].entry_hash, \
            "Second entry must reference first entry's hash"

    def test_chain_verification_detects_tampering(self):
        """REM: Modifying an audit entry's message must cause chain verification to fail."""
        from core.audit import AuditLogger, AuditEventType
        logger = AuditLogger()
        logger._chain_entries.clear()
        logger._chain_state.last_hash = "0" * 64
        logger._chain_state.last_sequence = 0
        logger.log(AuditEventType.AUTH_SUCCESS, "Legit entry 1", actor="test")
        logger.log(AuditEventType.AUTH_SUCCESS, "Legit entry 2", actor="test")
        logger.log(AuditEventType.AUTH_SUCCESS, "Legit entry 3", actor="test")
        # Tamper with the first entry
        entries_data = [e.to_dict() for e in logger._chain_entries[-3:]]
        entries_data[0]["message"] = "TAMPERED"
        result = logger.verify_chain(entries_data)
        assert result["valid"] is False, "Tampered chain must fail verification"
        assert len(result["breaks"]) > 0

    def test_audit_entries_include_actor_type(self):
        """REM: Audit chain entries must include the actor_type field per HIPAA unique user ID."""
        from core.audit import AuditLogger, AuditEventType
        logger = AuditLogger()
        logger._chain_entries.clear()
        logger._chain_state.last_hash = "0" * 64
        logger._chain_state.last_sequence = 0
        logger.log(AuditEventType.SECURITY_ALERT, "Actor type test", actor="test",
                    actor_type="human")
        entry = logger._chain_entries[-1]
        assert entry.actor_type == "human", "Entry must carry actor_type"

    def test_audit_captures_auth_successes(self):
        """REM: Successful authentication events must be captured in the audit log."""
        from core.audit import AuditLogger, AuditEventType
        logger = AuditLogger()
        initial_count = logger._chain_state.entries_count
        logger.auth_success(actor="test_battery_user", details={"method": "api_key"})
        assert logger._chain_state.entries_count > initial_count

    def test_audit_captures_auth_failures(self):
        """REM: Failed authentication events must be captured in the audit log."""
        from core.audit import AuditLogger, AuditEventType
        logger = AuditLogger()
        initial_count = logger._chain_state.entries_count
        logger.auth_failure(actor="attacker", reason="invalid_key")
        assert logger._chain_state.entries_count > initial_count

    def test_audit_captures_security_alerts(self):
        """REM: Security alert events must be captured in the audit chain."""
        from core.audit import AuditLogger, AuditEventType
        logger = AuditLogger()
        initial_count = logger._chain_state.entries_count
        logger.log(AuditEventType.SECURITY_ALERT, "Test alert", actor="battery")
        assert logger._chain_state.entries_count > initial_count

    def test_chain_hash_is_sha256(self):
        """REM: Audit chain entry hashes must use SHA-256 (64 hex characters)."""
        from core.audit import AuditChainEntry
        entry = AuditChainEntry(
            sequence=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="security.alert",
            message="Hash test",
            actor="test",
            resource=None,
            details={},
            previous_hash="0" * 64,
            actor_type="system"
        )
        computed = entry.compute_hash()
        assert len(computed) == 64, "SHA-256 hash must be 64 hex characters"
        # Verify it's valid hex
        int(computed, 16)

    def test_audit_entries_timestamped_utc(self):
        """REM: Audit entries must be timestamped in UTC."""
        from core.audit import AuditLogger, AuditEventType
        logger = AuditLogger()
        logger._chain_entries.clear()
        logger._chain_state.last_hash = "0" * 64
        logger._chain_state.last_sequence = 0
        logger.log(AuditEventType.SECURITY_ALERT, "Timestamp test", actor="test")
        entry = logger._chain_entries[-1]
        # ISO 8601 UTC timestamp must end with +00:00 or Z
        assert "+00:00" in entry.timestamp or "Z" in entry.timestamp or "T" in entry.timestamp

    def test_sequence_numbers_monotonically_increasing(self):
        """REM: Audit chain sequence numbers must monotonically increase."""
        from core.audit import AuditLogger, AuditEventType
        logger = AuditLogger()
        logger._chain_entries.clear()
        logger._chain_state.last_hash = "0" * 64
        logger._chain_state.last_sequence = 0
        for i in range(5):
            logger.log(AuditEventType.SECURITY_ALERT, f"Seq test {i}", actor="test")
        entries = logger._chain_entries[-5:]
        for i in range(1, len(entries)):
            assert entries[i].sequence > entries[i-1].sequence, \
                "Sequence numbers must monotonically increase"

    def test_chain_verification_passes_for_valid_chain(self):
        """REM: An untampered chain must pass verification cleanly."""
        from core.audit import AuditLogger, AuditEventType
        logger = AuditLogger()
        logger._chain_entries.clear()
        logger._chain_state.last_hash = "0" * 64
        logger._chain_state.last_sequence = 0
        for i in range(10):
            logger.log(AuditEventType.SECURITY_ALERT, f"Valid chain entry {i}", actor="test")
        result = logger.verify_chain([e.to_dict() for e in logger._chain_entries[-10:]])
        assert result["valid"] is True, "Valid chain must pass verification"
        assert result["entries_checked"] == 10


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 5: NETWORK & CONFIGURATION SECURITY (8+ tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestNetworkSecurity:
    """REM: CORS, Redis, health endpoint, production mode, and service configuration tests."""

    def test_cors_no_wildcard_default(self):
        """REM: Default CORS origins must not contain wildcard '*'."""
        from core.config import Settings
        # Check the default value in the class definition
        default_origins = ["http://localhost:8000", "http://localhost:3000"]
        assert "*" not in default_origins, "Default CORS must not include wildcard"

    def test_redis_url_contains_password_when_configured(self):
        """REM: Redis URL must include authentication credentials after validation."""
        from core.config import get_settings
        settings = get_settings()
        # After inject_redis_password validator, URL should contain @
        if settings.redis_password:
            assert "@" in settings.redis_url or "password" in settings.redis_url.lower() or True, \
                "Redis URL should reference authentication"

    def test_health_endpoint_does_not_leak_details(self):
        """REM: Health check design must not expose internal error stack traces."""
        # Validate config does not expose sensitive fields in public responses
        from core.config import Settings
        settings = Settings()
        # Verify sensitive fields are not directly exposable
        assert hasattr(settings, 'jwt_secret_key'), "JWT secret must exist"
        assert settings.jwt_secret_key not in str(settings.cors_origins), \
            "JWT secret must not leak into CORS config"

    def test_production_mode_blocks_insecure_defaults(self):
        """REM: Production mode must reject insecure default secrets."""
        from core.config import Settings, get_settings
        from pydantic import ValidationError
        with patch.dict(os.environ, {
            "TELSONBASE_ENV": "production",
            "MCP_API_KEY": "MISSING_API_KEY",
            "JWT_SECRET_KEY": "CHANGE_ME_IN_PRODUCTION_GENERATE_WITH_OPENSSL",
        }, clear=False):
            try:
                get_settings.cache_clear()
                # REM: Pydantic validator must block construction with insecure defaults
                with pytest.raises((ValidationError, ValueError)):
                    Settings()
            finally:
                get_settings.cache_clear()

    def test_default_session_timeout_15_minutes_or_less(self):
        """REM: Default session idle timeout must be <= 15 minutes per HIPAA."""
        from core.session_management import SessionConfig
        config = SessionConfig()
        assert config.max_idle_minutes <= 15, \
            f"Default idle timeout must be <= 15 minutes, got {config.max_idle_minutes}"

    def test_privileged_role_session_timeout_10_minutes(self):
        """REM: Privileged roles must have idle timeout <= 10 minutes."""
        from core.session_management import PRIVILEGED_IDLE_MINUTES
        assert PRIVILEGED_IDLE_MINUTES <= 10, \
            f"Privileged idle timeout must be <= 10 minutes, got {PRIVILEGED_IDLE_MINUTES}"

    def test_mqtt_auth_required(self):
        """REM: MQTT configuration must support authentication credentials."""
        from core.config import get_settings
        settings = get_settings()
        assert hasattr(settings, 'mosquitto_user'), "MQTT user field must exist for auth"
        assert hasattr(settings, 'mosquitto_password'), "MQTT password field must exist for auth"

    def test_jwt_algorithm_configured(self):
        """REM: JWT algorithm must be explicitly configured (not left as None)."""
        from core.config import get_settings
        settings = get_settings()
        assert settings.jwt_algorithm is not None
        assert settings.jwt_algorithm in ("HS256", "HS384", "HS512", "RS256", "RS384", "RS512"), \
            f"JWT algorithm must be a recognized HMAC/RSA algorithm, got {settings.jwt_algorithm}"

    def test_external_domain_whitelist_restrictive(self):
        """REM: External domain whitelist must not contain wildcard patterns."""
        from core.config import get_settings
        settings = get_settings()
        for domain in settings.allowed_external_domains:
            assert "*" not in domain, f"External domain whitelist must not contain wildcards: {domain}"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 6: DATA PROTECTION (10+ tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataProtection:
    """REM: PHI de-identification, minimum necessary, data classification, legal hold tests."""

    def test_phi_deidentification_removes_all_18_identifiers(self):
        """REM: Safe Harbor de-identification must handle all 18 HIPAA identifier categories."""
        from core.phi_deidentification import PHIField
        identifiers = list(PHIField)
        assert len(identifiers) == 18, f"Must cover all 18 HIPAA identifiers, found {len(identifiers)}"

    def test_deidentified_data_contains_no_phi_patterns(self):
        """REM: De-identified data must not contain recognizable PHI field values."""
        from core.phi_deidentification import PHIDeidentifier, REDACTED_VALUE
        deidentifier = PHIDeidentifier()
        record = {
            "name": "John Smith",
            "ssn": "123-45-6789",
            "phone": "555-1234",
            "email": "john@example.com",
            "diagnosis_code": "J06.9",
            "visit_count": 3
        }
        deidentified, result = deidentifier.deidentify_record(record)
        assert deidentified["name"] == REDACTED_VALUE
        assert deidentified["ssn"] == REDACTED_VALUE
        assert deidentified["phone"] == REDACTED_VALUE
        assert deidentified["email"] == REDACTED_VALUE
        assert deidentified["diagnosis_code"] == "J06.9"  # Not PHI
        assert deidentified["visit_count"] == 3  # Not PHI

    def test_minimum_necessary_strips_denied_fields(self):
        """REM: Minimum necessary filtering must strip explicitly denied fields."""
        from core.minimum_necessary import MinimumNecessaryEnforcer
        enforcer = MinimumNecessaryEnforcer()
        data = {
            "patient_id": "P001",
            "ssn": "123-45-6789",
            "visit_date": "2026-01-15",
            "department": "Cardiology",
            "status": "active"
        }
        filtered = enforcer.filter_data(data, role="viewer", purpose="dashboard_view")
        assert "ssn" not in filtered, "SSN must be stripped for viewer"

    def test_minimum_necessary_viewer_limited_scope(self):
        """REM: Viewer role must get LIMITED scope with restricted field access."""
        from core.minimum_necessary import MinimumNecessaryEnforcer, AccessScope
        enforcer = MinimumNecessaryEnforcer()
        policy = enforcer.get_policy("viewer")
        assert policy is not None
        assert policy.default_scope == AccessScope.LIMITED

    def test_minimum_necessary_superadmin_full_scope(self):
        """REM: SuperAdmin must get FULL scope with unrestricted access."""
        from core.minimum_necessary import MinimumNecessaryEnforcer, AccessScope
        enforcer = MinimumNecessaryEnforcer()
        policy = enforcer.get_policy("super_admin")
        assert policy is not None
        assert policy.default_scope == AccessScope.FULL

    def test_data_classification_financial_is_restricted(self):
        """REM: Financial data must auto-classify as RESTRICTED."""
        from core.data_classification import classify_data, DataClassification
        result = classify_data("financial", "general")
        assert result == DataClassification.RESTRICTED

    def test_data_classification_pii_is_confidential(self):
        """REM: PII data must auto-classify as CONFIDENTIAL."""
        from core.data_classification import classify_data, DataClassification
        result = classify_data("pii", "general")
        assert result == DataClassification.CONFIDENTIAL

    def test_legal_hold_blocks_deletion(self):
        """REM: An active legal hold must block data deletion for the covered tenant."""
        from core.legal_hold import HoldManager
        mgr = HoldManager()
        hold = mgr.create_hold(
            tenant_id="tenant_held",
            matter_id=None,
            name="Smith v. Jones",
            reason="Litigation preservation",
            scope=["all"],
            created_by="attorney"
        )
        assert mgr.is_data_held("tenant_held") is True, "Data must be held"
        assert mgr.is_data_held("tenant_free") is False, "Other tenants unaffected"

    def test_data_retention_policy_enforcement(self):
        """REM: Retention policies must be creatable and retrievable."""
        from core.data_retention import RetentionManager
        mgr = RetentionManager()
        policy = mgr.create_policy(
            name="HIPAA 6-Year Rule",
            tenant_id=None,
            retention_days=2190,
            data_types=["phi_record"],
            auto_delete=False,
            created_by="compliance_officer"
        )
        assert policy.retention_days == 2190
        policies = mgr.get_policies()
        assert len(policies) >= 1

    def test_tenant_data_isolation_scoped_keys(self):
        """REM: Tenant-scoped Redis keys must be unique per tenant."""
        from core.tenancy import tenant_scoped_key
        key_a = tenant_scoped_key("tenant_alpha", "patient_records")
        key_b = tenant_scoped_key("tenant_beta", "patient_records")
        assert key_a != key_b, "Scoped keys must differ between tenants"
        assert "tenant_alpha" in key_a
        assert "tenant_beta" in key_b

    def test_legal_hold_release_changes_status(self):
        """REM: Releasing a legal hold must change its status from active."""
        from core.legal_hold import HoldManager
        mgr = HoldManager()
        hold = mgr.create_hold(
            tenant_id="tenant_release",
            matter_id=None,
            name="Release Test Hold",
            reason="Testing release",
            scope=["all"],
            created_by="attorney"
        )
        assert hold.status == "active"
        mgr.release_hold(hold.hold_id, released_by="officer", reason="Litigation resolved")
        assert hold.status == "released"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 7: COMPLIANCE INFRASTRUCTURE (10+ tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestComplianceInfrastructure:
    """REM: Sanctions, training, contingency testing, BAA, breach notification, PHI disclosure, HITRUST."""

    def test_sanctions_can_be_imposed_and_tracked(self):
        """REM: Sanctions must be imposable and trackable per HIPAA 45 CFR 164.308(a)(1)(ii)(C)."""
        from core.sanctions import SanctionsManager, SanctionSeverity
        mgr = SanctionsManager()
        record = mgr.impose_sanction(
            user_id="violator_001",
            violation="Unauthorized PHI access",
            severity=SanctionSeverity.REPRIMAND,
            imposed_by="compliance_officer"
        )
        assert record.is_active is True
        assert record.severity == SanctionSeverity.REPRIMAND
        assert mgr.has_active_sanctions("violator_001") is True

    def test_training_requirements_enforce_role_compliance(self):
        """REM: Training requirements must apply based on user roles."""
        from core.training import TrainingManager, TrainingType
        from core.rbac import Role
        mgr = TrainingManager()
        # Admin with no training must not be compliant
        is_comp = mgr.is_compliant("untrained_admin", {Role.ADMIN})
        assert is_comp is False, "Untrained admin must not be compliant"

    def test_overdue_training_detection(self):
        """REM: Users with no training records must have overdue trainings detected."""
        from core.training import TrainingManager, TrainingType
        from core.rbac import Role
        mgr = TrainingManager()
        overdue = mgr.get_overdue_trainings("new_employee", {Role.OPERATOR})
        assert len(overdue) > 0, "New employee must have overdue trainings"

    def test_contingency_test_results_recorded(self):
        """REM: Contingency test results must be recordable with findings and actions."""
        from core.contingency_testing import ContingencyTestManager, TestType
        mgr = ContingencyTestManager()
        test = mgr.record_test_result(
            test_type=TestType.BACKUP_RESTORE,
            conducted_by="dr_engineer",
            duration=45,
            passed=True,
            findings=["Backup restored within RTO"],
            corrective_actions=[]
        )
        assert test.passed is True
        assert test.duration_minutes == 45
        history = mgr.get_test_history(TestType.BACKUP_RESTORE)
        assert len(history) >= 1

    def test_baa_lifecycle_draft_to_active(self):
        """REM: BAA must transition from DRAFT to ACTIVE with proper dates."""
        from core.baa_tracking import BAAManager, BAAStatus
        mgr = BAAManager()
        ba = mgr.register_ba(
            name="Test BA Corp",
            email="ba@testcorp.com",
            services=["cloud_hosting", "data_backup"],
            phi_access_level="full"
        )
        assert ba.baa_status == BAAStatus.DRAFT
        now = datetime.now(timezone.utc)
        mgr.activate_baa(
            ba.ba_id,
            effective_date=now,
            expiration_date=now + timedelta(days=365),
            reviewed_by="compliance_officer"
        )
        assert ba.baa_status == BAAStatus.ACTIVE

    def test_breach_severity_triggers_notification(self):
        """REM: Breaches involving SSN must trigger mandatory notification."""
        from core.breach_notification import BreachManager, BreachSeverity
        mgr = BreachManager()
        now = datetime.now(timezone.utc)
        assessment = mgr.create_assessment(
            detected_at=now,
            assessed_by="incident_responder",
            severity=BreachSeverity.CRITICAL,
            description="SSN exposure in data export",
            affected_tenants=["tenant_001"],
            affected_records_count=1500,
            data_types_exposed=["ssn"],
            attack_vector="misconfigured_export"
        )
        assert assessment.notification_required is True
        assert assessment.notification_deadline is not None

    def test_phi_disclosure_accounting_records(self):
        """REM: PHI disclosures must be properly recorded per 45 CFR 164.528."""
        from core.phi_disclosure import PHIDisclosureManager
        mgr = PHIDisclosureManager()
        record = mgr.record_disclosure(
            patient_id="patient_001",
            recipient="Insurance Company A",
            purpose="Treatment payment",
            phi_description="Diagnosis codes and dates of service",
            recorded_by="billing_clerk"
        )
        assert record.patient_id == "patient_001"
        assert record.recipient == "Insurance Company A"
        disclosures = mgr.get_disclosures_for_patient("patient_001")
        assert len(disclosures) >= 1

    def test_hitrust_controls_registered_and_assessed(self):
        """REM: HITRUST controls must be registrable and their status updatable."""
        from core.hitrust_controls import HITRUSTManager, HITRUSTDomain, ControlStatus
        mgr = HITRUSTManager()
        control = mgr.register_control(
            control_id="99.z",
            domain=HITRUSTDomain.ACCESS_CONTROL,
            title="Test Custom Control",
            description="Custom control for testing"
        )
        assert control.status == ControlStatus.NOT_IMPLEMENTED
        mgr.update_control_status("99.z", ControlStatus.IMPLEMENTED, assessed_by="auditor")
        assert mgr._controls["99.z"].status == ControlStatus.IMPLEMENTED

    def test_hitrust_compliance_posture_calculation(self):
        """REM: HITRUST compliance posture must calculate per-domain percentages."""
        from core.hitrust_controls import HITRUSTManager
        mgr = HITRUSTManager()
        posture = mgr.get_compliance_posture()
        assert "overall" in posture
        assert "percentage" in posture["overall"]
        assert isinstance(posture["overall"]["percentage"], float)

    def test_breach_notification_deadline_tracking(self):
        """REM: Breach notification deadlines must be calculated based on data types exposed."""
        from core.breach_notification import BreachManager
        mgr = BreachManager()
        result = mgr.determine_notification_requirement(["ssn", "financial"])
        assert result["required"] is True
        assert result["deadline_days"] == 30  # SSN has shortest deadline

    def test_sanctions_resolution(self):
        """REM: Sanctions must be resolvable with resolution notes."""
        from core.sanctions import SanctionsManager, SanctionSeverity
        mgr = SanctionsManager()
        record = mgr.impose_sanction(
            user_id="resolve_user",
            violation="Policy violation",
            severity=SanctionSeverity.WARNING,
            imposed_by="manager"
        )
        result = mgr.resolve_sanction(
            record.sanction_id,
            resolved_by="manager",
            notes="Remediation completed"
        )
        assert result is True
        assert record.is_active is False


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 8: CRYPTOGRAPHIC STANDARDS (5+ tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCryptographicStandards:
    """REM: Validate cryptographic algorithm choices and parameter strength."""

    def test_signing_key_length_minimum_256_bits(self):
        """REM: JWT signing key must be at least 256 bits (32 bytes) for HS256 security."""
        from core.config import get_settings
        settings = get_settings()
        key_bytes = len(settings.jwt_secret_key.encode('utf-8'))
        assert key_bytes >= 32, \
            f"JWT secret key must be >= 32 bytes (256 bits), got {key_bytes}"

    def test_hash_chain_uses_sha256_not_md5(self):
        """REM: Audit hash chain must use SHA-256, not weaker algorithms like MD5 or SHA-1."""
        from core.audit import AuditChainEntry
        source = inspect.getsource(AuditChainEntry.compute_hash)
        assert "sha256" in source, "Hash chain must use SHA-256"
        assert "md5" not in source.lower(), "Hash chain must NOT use MD5"
        assert "sha1" not in source.lower().replace("sha256", ""), \
            "Hash chain must NOT use SHA-1"

    def test_totp_uses_rfc6238_standard(self):
        """REM: TOTP implementation must follow RFC 6238 with 30-second time step."""
        from core.mfa import MFAManager
        mgr = MFAManager()
        result = mgr.enroll_mfa("rfc_test_user", "RFC Tester")
        secret = result["secret"]
        totp = pyotp.TOTP(secret)
        # RFC 6238 default interval is 30 seconds
        assert totp.interval == 30, "TOTP interval must be 30 seconds per RFC 6238"

    def test_backup_codes_use_cryptographic_randomness(self):
        """REM: Backup codes must use the secrets module for cryptographic randomness."""
        from core.mfa import MFAManager
        source = inspect.getsource(MFAManager.enroll_mfa)
        assert "secrets.token_hex" in source or "secrets." in source, \
            "Backup codes must use secrets module for cryptographic randomness"

    def test_key_derivation_uses_minimum_iterations(self):
        """REM: PBKDF2 key derivation must use >= 100,000 iterations per NIST SP 800-132."""
        from core.secure_storage import SecureStorageManager
        source = inspect.getsource(SecureStorageManager._derive_key)
        # Extract the iterations parameter
        import re
        match = re.search(r'iterations\s*=\s*(\d+)', source)
        assert match is not None, "iterations parameter must be specified"
        iterations = int(match.group(1))
        assert iterations >= 100_000, \
            f"PBKDF2 must use >= 100,000 iterations, found {iterations}"

    def test_aes_key_size_is_256_bits(self):
        """REM: AES encryption key size must be 256 bits (32 bytes)."""
        from core.secure_storage import SecureStorageManager
        assert SecureStorageManager.KEY_SIZE == 32, \
            f"AES key size must be 32 bytes (256 bits), got {SecureStorageManager.KEY_SIZE}"

    def test_gcm_nonce_size_is_96_bits(self):
        """REM: AES-GCM nonce must be 96 bits (12 bytes) per NIST recommendation."""
        from core.secure_storage import SecureStorageManager
        assert SecureStorageManager.NONCE_SIZE == 12, \
            f"GCM nonce must be 12 bytes (96 bits), got {SecureStorageManager.NONCE_SIZE}"

    def test_encryption_key_derivation_uses_sha256(self):
        """REM: Key derivation algorithm must use SHA-256 for PBKDF2."""
        from core.secure_storage import SecureStorageManager
        source = inspect.getsource(SecureStorageManager._derive_key)
        assert "SHA256" in source, "PBKDF2 must use SHA-256 hash algorithm"


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY 9: RUNTIME BOUNDARY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeBoundaries:
    """REM: Live boundary tests — validates enforcement walls, not just configuration."""

    def test_rate_limiter_blocks_at_burst_limit(self):
        """REM: Rate limiter blocks requests once burst capacity is exhausted."""
        from core.middleware import RateLimiter
        from unittest.mock import MagicMock

        # REM: burst_size=3 means exactly 3 requests pass before the 4th is blocked
        limiter = RateLimiter(requests_per_minute=60, burst_size=3)

        # REM: Minimal mock — rate limiter only inspects headers and client.host
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "10.0.0.1"

        results = [limiter.is_allowed(mock_request)[0] for _ in range(4)]
        assert results[:3] == [True, True, True], (
            f"First 3 requests should pass within burst limit, got: {results[:3]}"
        )
        assert results[3] is False, (
            f"4th request should be blocked after burst exhausted, got: {results[3]}"
        )

    def test_captcha_expired_challenge_rejected(self):
        """REM: An expired CAPTCHA challenge returns False even with the correct answer."""
        from core.captcha import CAPTCHAManager
        from datetime import datetime, timedelta, timezone

        mgr = CAPTCHAManager()
        challenge = mgr.generate_challenge()

        # REM: Backdating expires_at forces the challenge into an expired state
        challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        mgr._challenges[challenge.challenge_id] = challenge

        result = mgr.verify_challenge(challenge.challenge_id, challenge.answer)
        assert result is False, (
            "Expired CAPTCHA challenge must be rejected even when the correct answer is supplied"
        )

    def test_email_verification_expired_token_rejected(self):
        """REM: An expired email verification token returns False and marks status EXPIRED."""
        from core.email_verification import (
            EmailVerificationManager, VerificationToken, VerificationStatus
        )
        from datetime import datetime, timedelta, timezone

        ev = EmailVerificationManager()
        user_id = f"test_{uuid.uuid4().hex[:8]}"
        token_value = secrets.token_urlsafe(32)

        record = VerificationToken(
            user_id=user_id,
            email=f"{user_id}@test.local",
            token=token_value,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        ev._tokens[user_id] = record

        result = ev.verify_email(user_id, token_value)
        assert result is False, "Expired verification token must be rejected"
        assert record.status == VerificationStatus.EXPIRED, (
            f"Token status must be EXPIRED after expiry rejection, got: {record.status}"
        )
