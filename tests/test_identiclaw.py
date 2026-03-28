# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_identiclaw.py
# REM: =======================================================================================
# REM: W3C DID IDENTITY ENGINE TESTS
# REM: =======================================================================================
# REM: v7.3.0CC: Tests for DID parsing, Ed25519 verification, VC validation,
# REM: scope-to-permission mapping, auth flow, kill switch, and approval gates.
# REM: =======================================================================================

import base64
import json
import time
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from core.identiclaw import (
    IdenticlawManager,
    DIDDocument,
    VerifiableCredential,
    AgentIdentityRecord,
    SCOPE_PERMISSION_MAP,
    parse_did,
    parse_did_key,
    _base58_decode,
)


# REM: =======================================================================================
# REM: TEST FIXTURES
# REM: =======================================================================================

@pytest.fixture
def manager():
    """REM: Fresh IdenticlawManager for each test (no Redis)."""
    m = IdenticlawManager()
    m._initialized = True
    return m


@pytest.fixture
def ed25519_keypair():
    """REM: Generate a real Ed25519 keypair for testing."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes_raw()
    return private_key, public_key, public_bytes


@pytest.fixture
def sample_did_key(ed25519_keypair):
    """REM: Build a valid did:key from a real Ed25519 keypair."""
    _, _, public_bytes = ed25519_keypair
    # REM: Encode as multicodec (0xed01 prefix) + base58btc with 'z' prefix
    multicodec = bytes([0xed, 0x01]) + public_bytes
    # REM: Simple base58 encoding for test
    _ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    num = int.from_bytes(multicodec, "big")
    encoded = ""
    while num > 0:
        num, remainder = divmod(num, 58)
        encoded = _ALPHABET[remainder] + encoded
    did = f"did:key:z{encoded}"
    return did, public_bytes


@pytest.fixture
def sample_vc():
    """REM: Sample W3C Verifiable Credential JSON."""
    return {
        "id": "vc-test-001",
        "type": ["VerifiableCredential", "AgentCapability"],
        "issuer": "did:web:agent-identity.local",
        "issuanceDate": datetime.now(timezone.utc).isoformat(),
        "expirationDate": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "credentialSubject": {
            "id": "did:key:z6MkTestAgent",
            "scopes": ["agent:read", "agent:write", "mcp:tool:invoke"],
        },
        "proof": {
            "type": "Ed25519Signature2020",
            "proofValue": "",  # Empty for unit tests (signature verification tested separately)
        },
    }


# REM: =======================================================================================
# REM: DID PARSING TESTS
# REM: =======================================================================================

class TestDIDParsing:
    """REM: Test DID document parsing for did:key and did:web methods."""

    def test_parse_did_key_valid(self, sample_did_key):
        did, expected_bytes = sample_did_key
        result = parse_did(did)
        assert result is not None
        assert result["method"] == "key"
        assert result["did"] == did
        assert result["public_key_bytes"] == expected_bytes

    def test_parse_did_web_valid(self):
        result = parse_did("did:web:agent-identity.local")
        assert result is not None
        assert result["method"] == "web"
        assert result["public_key_bytes"] is None  # Requires HTTP resolution

    def test_parse_did_unsupported_method(self):
        result = parse_did("did:ion:unsupported123")
        assert result is None

    def test_parse_did_empty_string(self):
        assert parse_did("") is None
        assert parse_did(None) is None

    def test_parse_did_no_prefix(self):
        assert parse_did("notadid:key:z123") is None

    def test_parse_did_key_invalid_format(self):
        result = parse_did_key("did:key:invalid_no_z")
        assert result is None

    def test_parse_did_key_extracts_32_bytes(self, sample_did_key):
        did, public_bytes = sample_did_key
        extracted = parse_did_key(did)
        assert extracted is not None
        assert len(extracted) == 32


# REM: =======================================================================================
# REM: ED25519 SIGNATURE VERIFICATION TESTS
# REM: =======================================================================================

class TestEd25519Verification:
    """REM: Test Ed25519 signature verification (all local crypto)."""

    def test_valid_signature(self, manager, ed25519_keypair):
        private_key, _, public_bytes = ed25519_keypair
        message = b"test message to sign"
        signature = private_key.sign(message)
        assert manager.verify_signature(public_bytes, message, signature) is True

    def test_invalid_signature(self, manager, ed25519_keypair):
        _, _, public_bytes = ed25519_keypair
        message = b"test message"
        fake_signature = b"\x00" * 64
        assert manager.verify_signature(public_bytes, message, fake_signature) is False

    def test_wrong_key(self, manager, ed25519_keypair):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key, _, _ = ed25519_keypair
        other_key = Ed25519PrivateKey.generate()
        other_public = other_key.public_key().public_bytes_raw()
        message = b"test message"
        signature = private_key.sign(message)
        # REM: Signature made with original key, verified with different key
        assert manager.verify_signature(other_public, message, signature) is False

    def test_tampered_message(self, manager, ed25519_keypair):
        private_key, _, public_bytes = ed25519_keypair
        message = b"original message"
        signature = private_key.sign(message)
        tampered = b"tampered message"
        assert manager.verify_signature(public_bytes, tampered, signature) is False

    def test_empty_message_valid(self, manager, ed25519_keypair):
        private_key, _, public_bytes = ed25519_keypair
        message = b""
        signature = private_key.sign(message)
        assert manager.verify_signature(public_bytes, message, signature) is True


# REM: =======================================================================================
# REM: VERIFIABLE CREDENTIAL VALIDATION TESTS
# REM: =======================================================================================

class TestVCValidation:
    """REM: Test W3C Verifiable Credential parsing and validation."""

    @patch("core.identiclaw.get_settings")
    def test_valid_vc(self, mock_settings, manager, sample_vc):
        settings = MagicMock()
        settings.identiclaw_known_issuers = ["did:web:agent-identity.local"]
        settings.identiclaw_vc_cache_ttl_hours = 12
        mock_settings.return_value = settings
        manager._get_redis = MagicMock(return_value=None)

        result = manager.validate_credential(sample_vc)
        assert result is not None
        assert result.vc_id == "vc-test-001"
        assert result.issuer_did == "did:web:agent-identity.local"
        assert "agent:read" in result.scopes
        assert "agent:write" in result.scopes
        assert "mcp:tool:invoke" in result.scopes

    @patch("core.identiclaw.get_settings")
    def test_expired_vc(self, mock_settings, manager, sample_vc):
        settings = MagicMock()
        settings.identiclaw_known_issuers = ["did:web:agent-identity.local"]
        mock_settings.return_value = settings

        sample_vc["expirationDate"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        result = manager.validate_credential(sample_vc)
        assert result is None

    @patch("core.identiclaw.get_settings")
    def test_unknown_issuer_rejected(self, mock_settings, manager, sample_vc):
        settings = MagicMock()
        settings.identiclaw_known_issuers = ["did:web:trusted-only.com"]
        mock_settings.return_value = settings

        result = manager.validate_credential(sample_vc)
        assert result is None

    @patch("core.identiclaw.get_settings")
    def test_scope_extraction(self, mock_settings, manager, sample_vc):
        settings = MagicMock()
        settings.identiclaw_known_issuers = ["did:web:agent-identity.local"]
        settings.identiclaw_vc_cache_ttl_hours = 12
        mock_settings.return_value = settings
        manager._get_redis = MagicMock(return_value=None)

        result = manager.validate_credential(sample_vc)
        assert result is not None
        assert len(result.scopes) == 3


# REM: =======================================================================================
# REM: SCOPE-TO-PERMISSION MAPPING TESTS
# REM: =======================================================================================

class TestScopeMapping:
    """REM: Test VC scope to TelsonBase permission mapping."""

    def test_known_scope_mapping(self, manager):
        perms = manager.map_scopes_to_permissions(["agent:read"])
        assert "read" in perms

    def test_unknown_scope_gets_no_permissions(self, manager):
        perms = manager.map_scopes_to_permissions(["totally:unknown:scope"])
        assert len(perms) == 0

    def test_multiple_scopes_combine(self, manager):
        perms = manager.map_scopes_to_permissions(["agent:read", "mcp:tool:invoke"])
        assert "read" in perms
        assert "tool_invoke" in perms

    def test_admin_scope_grants_wildcard(self, manager):
        perms = manager.map_scopes_to_permissions(["agent:admin"])
        assert "*" in perms

    def test_empty_scopes_return_empty(self, manager):
        perms = manager.map_scopes_to_permissions([])
        assert len(perms) == 0

    def test_all_defined_scopes_have_mappings(self):
        """REM: Verify all scopes in SCOPE_PERMISSION_MAP actually produce permissions."""
        for scope, permissions in SCOPE_PERMISSION_MAP.items():
            assert len(permissions) > 0, f"Scope {scope} maps to empty permissions"


# REM: =======================================================================================
# REM: KILL SWITCH TESTS
# REM: =======================================================================================

class TestKillSwitch:
    """REM: Test local revocation override."""

    def test_revoke_agent(self, manager):
        manager._get_redis = MagicMock(return_value=None)
        result = manager.revoke_agent("did:key:z6MkTest", "admin", "compromised")
        assert result is True
        assert "did:key:z6MkTest" in manager._revoked_dids

    def test_revoked_agent_is_revoked(self, manager):
        manager._revoked_dids.add("did:key:z6MkTest")
        manager._get_redis = MagicMock(return_value=None)
        assert manager.is_revoked("did:key:z6MkTest") is True

    def test_non_revoked_agent_is_not_revoked(self, manager):
        manager._get_redis = MagicMock(return_value=None)
        assert manager.is_revoked("did:key:z6MkClean") is False

    def test_reinstate_agent(self, manager):
        manager._get_redis = MagicMock(return_value=None)
        manager._revoked_dids.add("did:key:z6MkTest")
        result = manager.reinstate_agent("did:key:z6MkTest", "admin", "reviewed")
        assert result is True
        assert "did:key:z6MkTest" not in manager._revoked_dids

    def test_reinstate_non_revoked_returns_false(self, manager):
        result = manager.reinstate_agent("did:key:z6MkNeverRevoked", "admin")
        assert result is False

    def test_revoke_updates_identity_record(self, manager):
        manager._get_redis = MagicMock(return_value=None)
        record = AgentIdentityRecord(
            did="did:key:z6MkTest",
            display_name="Test Agent",
        )
        manager._identity_cache["did:key:z6MkTest"] = record
        manager.revoke_agent("did:key:z6MkTest", "admin", "test reason")
        assert record.revoked is True
        assert record.revoked_by == "admin"
        assert record.revocation_reason == "test reason"


# REM: =======================================================================================
# REM: AGENT REGISTRATION TESTS
# REM: =======================================================================================

class TestAgentRegistration:
    """REM: Test agent identity registration flow."""

    @patch("core.identiclaw.get_settings")
    def test_register_did_key_agent(self, mock_settings, manager, sample_did_key, sample_vc):
        settings = MagicMock()
        settings.identiclaw_known_issuers = ["did:web:agent-identity.local"]
        settings.identiclaw_did_cache_ttl_hours = 24
        settings.identiclaw_vc_cache_ttl_hours = 12
        mock_settings.return_value = settings
        manager._get_redis = MagicMock(return_value=None)

        did, _ = sample_did_key
        sample_vc["credentialSubject"]["id"] = did

        record = manager.register_agent(
            did=did,
            credentials=[sample_vc],
            display_name="Test Agent",
            registered_by="admin",
        )

        assert record is not None
        assert record.did == did
        assert record.display_name == "Test Agent"
        assert record.trust_level == "quarantine"
        assert len(record.clawcoat_permissions) > 0

    def test_register_unresolvable_did(self, manager):
        manager._get_redis = MagicMock(return_value=None)
        record = manager.register_agent(
            did="did:unsupported:abc123",
            display_name="Bad Agent",
        )
        assert record is None

    @patch("core.identiclaw.get_settings")
    def test_register_already_registered(self, mock_settings, manager, sample_did_key):
        settings = MagicMock()
        settings.identiclaw_did_cache_ttl_hours = 24
        settings.identiclaw_known_issuers = []
        mock_settings.return_value = settings
        manager._get_redis = MagicMock(return_value=None)

        did, _ = sample_did_key
        existing = AgentIdentityRecord(did=did, display_name="Existing")
        manager._identity_cache[did] = existing

        result = manager.register_agent(did=did)
        assert result is existing


# REM: =======================================================================================
# REM: AUTHENTICATION FLOW TESTS
# REM: =======================================================================================

class TestAuthFlow:
    """REM: Test DID authentication from X-DID-Auth header."""

    def test_auth_header_missing_parts(self, manager):
        result = manager.authenticate_from_header("bad_header", "/test", "GET")
        assert result is None

    def test_auth_header_revoked_agent(self, manager, ed25519_keypair, sample_did_key):
        did, _ = sample_did_key
        manager._revoked_dids.add(did)
        manager._get_redis = MagicMock(return_value=None)

        nonce = "test-nonce-123"
        ts = str(time.time())
        header = f"{did}|fakesig|{nonce}|{ts}"

        result = manager.authenticate_from_header(header, "/test", "GET")
        assert result is None

    def test_auth_header_expired_timestamp(self, manager, sample_did_key):
        did, _ = sample_did_key
        manager._get_redis = MagicMock(return_value=None)

        nonce = "test-nonce-456"
        ts = str(time.time() - 600)  # 10 minutes ago (beyond 5-min window)
        header = f"{did}|fakesig|{nonce}|{ts}"

        result = manager.authenticate_from_header(header, "/test", "GET")
        assert result is None

    def test_auth_header_valid_signature(self, manager, ed25519_keypair, sample_did_key):
        private_key, _, public_bytes = ed25519_keypair
        did, _ = sample_did_key
        # REM: Nonce check is now fail-closed — provide a mock Redis that accepts the nonce
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0   # Nonce not yet seen
        mock_redis.setex.return_value = True  # Store nonce as used
        manager._get_redis = MagicMock(return_value=mock_redis)

        # REM: Register the agent first
        record = AgentIdentityRecord(
            did=did,
            display_name="Auth Test Agent",
            clawcoat_permissions=["read"],
        )
        manager._identity_cache[did] = record

        # REM: Cache the DID document
        doc = DIDDocument(
            did=did,
            method="key",
            public_key_bytes=public_bytes,
            public_key_hex=public_bytes.hex(),
        )
        manager._did_cache[did] = doc

        # REM: Build a valid auth header
        nonce = "valid-nonce-789"
        ts = str(time.time())
        path = "/test"
        method = "GET"
        message = f"{nonce}{ts}{path}{method}".encode("utf-8")
        signature = private_key.sign(message)
        sig_b64 = base64.b64encode(signature).decode("ascii")

        header = f"{did}|{sig_b64}|{nonce}|{ts}"
        result = manager.authenticate_from_header(header, path, method)

        assert result is not None
        assert result.did == did
        assert "read" in result.clawcoat_permissions

    def test_auth_header_unregistered_agent(self, manager, ed25519_keypair, sample_did_key):
        """REM: DID authenticates but is not registered — should return None."""
        private_key, _, public_bytes = ed25519_keypair
        did, _ = sample_did_key
        manager._get_redis = MagicMock(return_value=None)

        # REM: Cache the DID doc but DON'T register the agent
        doc = DIDDocument(
            did=did, method="key",
            public_key_bytes=public_bytes,
            public_key_hex=public_bytes.hex(),
        )
        manager._did_cache[did] = doc

        nonce = "unregistered-nonce"
        ts = str(time.time())
        message = f"{nonce}{ts}/testGET".encode("utf-8")
        signature = private_key.sign(message)
        sig_b64 = base64.b64encode(signature).decode("ascii")

        header = f"{did}|{sig_b64}|{nonce}|{ts}"
        result = manager.authenticate_from_header(header, "/test", "GET")

        assert result is None


# REM: =======================================================================================
# REM: DID DOCUMENT RESOLUTION TESTS
# REM: =======================================================================================

class TestDIDResolution:
    """REM: Test DID document resolution and caching."""

    def test_resolve_did_key_locally(self, manager, sample_did_key):
        manager._get_redis = MagicMock(return_value=None)
        did, public_bytes = sample_did_key

        doc = manager.resolve_did(did)
        assert doc is not None
        assert doc.did == did
        assert doc.method == "key"
        assert doc.public_key_bytes == public_bytes

    def test_resolve_did_uses_cache(self, manager, sample_did_key):
        did, public_bytes = sample_did_key
        cached_doc = DIDDocument(
            did=did, method="key",
            public_key_bytes=public_bytes,
            public_key_hex=public_bytes.hex(),
        )
        manager._did_cache[did] = cached_doc

        result = manager.resolve_did(did)
        assert result is cached_doc  # Same object, from cache

    def test_resolve_did_web_returns_none_for_now(self, manager):
        """REM: did:web requires HTTP resolution — not yet implemented."""
        manager._get_redis = MagicMock(return_value=None)
        result = manager.resolve_did("did:web:example.com")
        assert result is None

    def test_resolve_unsupported_method(self, manager):
        result = manager.resolve_did("did:ion:unsupported")
        assert result is None


# REM: =======================================================================================
# REM: APPROVAL GATE RULE TESTS
# REM: =======================================================================================

class TestApprovalGateRules:
    """REM: Test new DID approval rules are properly loaded."""

    def test_did_registration_rule_exists(self):
        from core.approval import DEFAULT_APPROVAL_RULES
        rule_ids = [r.rule_id for r in DEFAULT_APPROVAL_RULES]
        assert "rule-did-first-registration" in rule_ids

    def test_did_scope_change_rule_exists(self):
        from core.approval import DEFAULT_APPROVAL_RULES
        rule_ids = [r.rule_id for r in DEFAULT_APPROVAL_RULES]
        assert "rule-did-scope-change" in rule_ids

    def test_existing_rules_unaffected(self):
        from core.approval import DEFAULT_APPROVAL_RULES
        rule_ids = [r.rule_id for r in DEFAULT_APPROVAL_RULES]
        # REM: All 5 original rules still present
        assert "rule-external-new-domain" in rule_ids
        assert "rule-filesystem-delete" in rule_ids
        assert "rule-anomaly-flagged" in rule_ids
        assert "rule-new-agent-first-action" in rule_ids
        assert "rule-high-value-transaction" in rule_ids

    def test_approval_gate_has_known_dids_set(self):
        from core.approval import ApprovalGate
        gate = ApprovalGate()
        assert hasattr(gate, "_known_dids")
        assert isinstance(gate._known_dids, set)


# REM: =======================================================================================
# REM: AUTH MODULE INTEGRATION TESTS
# REM: =======================================================================================

class TestAuthModuleIntegration:
    """REM: Test that DID auth is properly integrated into core/auth.py."""

    def test_did_auth_header_scheme_exists(self):
        from core.auth import did_auth_header
        assert did_auth_header is not None

    def test_authenticate_request_signature_has_did_param(self):
        """REM: Verify authenticate_request accepts did_auth parameter."""
        import inspect
        from core.auth import authenticate_request
        sig = inspect.signature(authenticate_request)
        param_names = list(sig.parameters.keys())
        assert "did_auth" in param_names

    def test_optional_auth_signature_has_did_param(self):
        """REM: Verify optional_auth accepts did_auth parameter."""
        import inspect
        from core.auth import optional_auth
        sig = inspect.signature(optional_auth)
        param_names = list(sig.parameters.keys())
        assert "did_auth" in param_names


# REM: =======================================================================================
# REM: AUDIT EVENT TYPE TESTS
# REM: =======================================================================================

class TestAuditEventTypes:
    """REM: Test that identity audit event types exist."""

    def test_identity_event_types_exist(self):
        from core.audit import AuditEventType
        assert hasattr(AuditEventType, "IDENTITY_REGISTERED")
        assert hasattr(AuditEventType, "IDENTITY_VERIFIED")
        assert hasattr(AuditEventType, "IDENTITY_VERIFICATION_FAILED")
        assert hasattr(AuditEventType, "IDENTITY_REVOKED")
        assert hasattr(AuditEventType, "IDENTITY_REINSTATED")
        assert hasattr(AuditEventType, "IDENTITY_CREDENTIAL_UPDATED")


# REM: =======================================================================================
# REM: CONFIG SETTINGS TESTS
# REM: =======================================================================================

class TestConfigSettings:
    """REM: Test W3C DID identity settings are in config."""

    def test_identiclaw_settings_exist(self):
        from core.config import Settings
        import inspect
        fields = Settings.model_fields
        assert "identiclaw_enabled" in fields
        assert "identiclaw_registry_url" in fields
        assert "identiclaw_did_cache_ttl_hours" in fields
        assert "identiclaw_vc_cache_ttl_hours" in fields
        assert "identiclaw_known_issuers" in fields

    def test_identiclaw_disabled_by_default(self):
        """REM: Critical: must be disabled by default for safe rollout."""
        from core.config import Settings
        default = Settings.model_fields["identiclaw_enabled"].default
        assert default is False
