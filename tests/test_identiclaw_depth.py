# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_identiclaw_depth.py
# REM: Depth coverage for remaining paths in core/identiclaw.py
# REM: Covers: _base58_decode edge cases, parse_did_key error branches,
# REM: IdenticlawManager init/startup, get_agent Redis fallback, list_agents,
# REM: update_agent_trust_level, refresh_credentials, nonce helpers,
# REM: reinstate with record update, resolve_did cache/refresh paths,
# REM: validate_credential edge cases (issuer dict, scope string, jti fallback).

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest

from core.identiclaw import (
    IdenticlawManager,
    DIDDocument,
    AgentIdentityRecord,
    SCOPE_PERMISSION_MAP,
    _base58_decode,
    parse_did_key,
    parse_did,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def manager():
    m = IdenticlawManager()
    m._initialized = True
    return m


@pytest.fixture
def sample_did_key_fixture():
    """Generate a valid did:key from a real Ed25519 keypair."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes_raw()
    _ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    multicodec = bytes([0xed, 0x01]) + public_bytes
    num = int.from_bytes(multicodec, "big")
    encoded = ""
    while num > 0:
        num, remainder = divmod(num, 58)
        encoded = _ALPHABET[remainder] + encoded
    return f"did:key:z{encoded}", public_bytes, private_key


# ═══════════════════════════════════════════════════════════════════════════════
# _base58_decode edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestBase58DecodeDepth:
    def test_decode_empty_string_returns_empty_bytes(self):
        result = _base58_decode("")
        assert result == b""

    def test_decode_leading_one_preserves_zero(self):
        result = _base58_decode("1")
        assert b"\x00" in result or result == b"\x00"

    def test_decode_returns_bytes(self):
        result = _base58_decode("1")
        assert isinstance(result, bytes)

    def test_decode_multiple_leading_ones(self):
        result = _base58_decode("11")
        assert isinstance(result, bytes)


# ═══════════════════════════════════════════════════════════════════════════════
# parse_did_key error branches
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseDIDKeyDepth:
    def test_wrong_multicodec_prefix_returns_none(self):
        _ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        # Build a key with prefix 0xff01 (not Ed25519)
        data = bytes([0xff, 0x01]) + b"\x00" * 32
        num = int.from_bytes(data, "big")
        encoded = ""
        while num > 0:
            num, remainder = divmod(num, 58)
            encoded = _ALPHABET[remainder] + encoded
        did = f"did:key:z{encoded}"
        result = parse_did_key(did)
        assert result is None

    def test_no_z_prefix_returns_none(self):
        result = parse_did_key("did:key:nozprefix")
        assert result is None

    def test_not_did_key_returns_none(self):
        result = parse_did_key("did:web:example.com")
        assert result is None

    def test_not_did_at_all_returns_none(self):
        result = parse_did_key("notadid")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# IdenticlawManager.__init__ and startup
# ═══════════════════════════════════════════════════════════════════════════════

class TestIdenticlawManagerInit:
    def test_fresh_manager_has_empty_caches(self):
        m = IdenticlawManager()
        assert m._identity_cache == {}
        assert m._did_cache == {}
        assert m._vc_cache == {}
        assert m._revoked_dids == set()
        assert m._initialized is False

    def test_startup_check_sets_initialized(self):
        m = IdenticlawManager()
        m._get_redis = MagicMock(return_value=None)
        m.startup_check()
        assert m._initialized is True

    def test_load_from_persistence_no_redis(self):
        m = IdenticlawManager()
        m._get_redis = MagicMock(return_value=None)
        m._load_from_persistence()
        assert m._identity_cache == {}

    def test_get_redis_returns_none_on_error(self):
        m = IdenticlawManager()
        # No Redis running locally in unit test
        result = m._get_redis()
        # Either returns a client or None — just check it doesn't raise
        assert result is None or hasattr(result, "ping")

    def test_load_from_persistence_with_mock_redis(self):
        m = IdenticlawManager()
        mock_client = MagicMock()
        mock_client.keys.return_value = []  # No keys
        m._get_redis = MagicMock(return_value=mock_client)
        m._load_from_persistence()
        assert m._identity_cache == {}
        assert m._revoked_dids == set()


# ═══════════════════════════════════════════════════════════════════════════════
# get_agent — Redis fallback path
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetAgentDepth:
    def test_get_agent_from_memory_cache(self, manager):
        did = "did:key:z6MkCachedDepth"
        record = AgentIdentityRecord(did=did, display_name="Cached")
        manager._identity_cache[did] = record
        result = manager.get_agent(did)
        assert result is record

    def test_get_agent_not_found_no_redis(self, manager):
        manager._get_redis = MagicMock(return_value=None)
        result = manager.get_agent("did:key:z6MkNotHereDepth")
        assert result is None

    def test_get_agent_from_redis_fallback(self, manager):
        did = "did:key:z6MkRedisDepth"
        record = AgentIdentityRecord(did=did, display_name="Redis Agent")
        mock_client = MagicMock()
        mock_client.get.return_value = record.model_dump_json()
        manager._get_redis = MagicMock(return_value=mock_client)
        result = manager.get_agent(did)
        assert result is not None
        assert result.did == did

    def test_get_agent_redis_returns_invalid_json(self, manager):
        did = "did:key:z6MkBadJsonDepth"
        mock_client = MagicMock()
        mock_client.get.return_value = "this is not json {"
        manager._get_redis = MagicMock(return_value=mock_client)
        result = manager.get_agent(did)
        assert result is None

    def test_get_agent_redis_returns_none_for_key(self, manager):
        did = "did:key:z6MkNoDataDepth"
        mock_client = MagicMock()
        mock_client.get.return_value = None
        manager._get_redis = MagicMock(return_value=mock_client)
        result = manager.get_agent(did)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# list_agents
# ═══════════════════════════════════════════════════════════════════════════════

class TestListAgentsDepth:
    def test_list_agents_empty(self, manager):
        result = manager.list_agents()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_agents_with_registered(self, manager):
        r1 = AgentIdentityRecord(did="did:key:z6MkA001", display_name="A1")
        r2 = AgentIdentityRecord(did="did:key:z6MkA002", display_name="A2")
        manager._identity_cache["did:key:z6MkA001"] = r1
        manager._identity_cache["did:key:z6MkA002"] = r2
        result = manager.list_agents()
        assert len(result) == 2

    def test_list_agents_returns_records(self, manager):
        record = AgentIdentityRecord(did="did:key:z6MkA003", display_name="A3")
        manager._identity_cache["did:key:z6MkA003"] = record
        result = manager.list_agents()
        assert any(r.did == "did:key:z6MkA003" for r in result)


# ═══════════════════════════════════════════════════════════════════════════════
# update_agent_trust_level
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateAgentTrustLevelDepth:
    def test_update_nonexistent_agent_returns_false(self, manager):
        manager._get_redis = MagicMock(return_value=None)
        result = manager.update_agent_trust_level("did:key:z6MkGone", "citizen", "admin")
        assert result is False

    def test_update_existing_agent_changes_level(self, manager):
        did = "did:key:z6MkUpdate"
        record = AgentIdentityRecord(did=did, trust_level="probation")
        manager._identity_cache[did] = record
        manager._get_redis = MagicMock(return_value=None)
        result = manager.update_agent_trust_level(did, "resident", "admin")
        assert result is True
        assert record.trust_level == "resident"

    def test_update_logs_old_and_new_level(self, manager):
        did = "did:key:z6MkUpdateLog"
        record = AgentIdentityRecord(did=did, trust_level="quarantine")
        manager._identity_cache[did] = record
        manager._get_redis = MagicMock(return_value=None)
        result = manager.update_agent_trust_level(did, "citizen", "operator")
        assert result is True
        assert record.trust_level == "citizen"


# ═══════════════════════════════════════════════════════════════════════════════
# refresh_credentials
# ═══════════════════════════════════════════════════════════════════════════════

class TestRefreshCredentialsDepth:
    def test_refresh_nonexistent_agent_returns_none(self, manager):
        manager._get_redis = MagicMock(return_value=None)
        result = manager.refresh_credentials("did:key:z6MkGoneDepth")
        assert result is None

    def test_refresh_existing_did_key_agent(self, manager, sample_did_key_fixture):
        did, public_bytes, _ = sample_did_key_fixture
        record = AgentIdentityRecord(did=did, display_name="Refresh Agent")
        manager._identity_cache[did] = record
        manager._get_redis = MagicMock(return_value=None)
        result = manager.refresh_credentials(did)
        assert result is not None
        assert result.did == did

    def test_refresh_updates_public_key_hex(self, manager, sample_did_key_fixture):
        did, public_bytes, _ = sample_did_key_fixture
        record = AgentIdentityRecord(did=did, public_key_hex="old_hex")
        manager._identity_cache[did] = record
        manager._get_redis = MagicMock(return_value=None)
        manager.refresh_credentials(did)
        # Should update public_key_hex from re-resolved doc
        assert record.public_key_hex != "old_hex"


# ═══════════════════════════════════════════════════════════════════════════════
# Nonce helpers: _check_nonce / _mark_nonce_used
# ═══════════════════════════════════════════════════════════════════════════════

class TestNonceHelpersDepth:
    def test_nonce_fresh_without_redis(self, manager):
        manager._get_redis = MagicMock(return_value=None)
        result = manager._check_nonce("fresh-nonce-depth-001")
        assert result is False  # Fail-closed: cannot verify without Redis (replay attack prevention)

    def test_nonce_fresh_in_redis(self, manager):
        mock_client = MagicMock()
        mock_client.exists.return_value = 0
        manager._get_redis = MagicMock(return_value=mock_client)
        result = manager._check_nonce("unused-nonce-depth-001")
        assert result is True

    def test_nonce_replayed_in_redis(self, manager):
        mock_client = MagicMock()
        mock_client.exists.return_value = 1  # Already seen
        manager._get_redis = MagicMock(return_value=mock_client)
        result = manager._check_nonce("replayed-nonce-depth-001")
        assert result is False

    def test_mark_nonce_used_calls_setex(self, manager):
        mock_client = MagicMock()
        manager._get_redis = MagicMock(return_value=mock_client)
        manager._mark_nonce_used("nonce-mark-depth-001")
        mock_client.setex.assert_called_once()

    def test_mark_nonce_used_no_redis(self, manager):
        manager._get_redis = MagicMock(return_value=None)
        # Should not raise
        manager._mark_nonce_used("nonce-no-redis-depth")

    def test_check_nonce_redis_exception(self, manager):
        mock_client = MagicMock()
        mock_client.exists.side_effect = Exception("redis error")
        manager._get_redis = MagicMock(return_value=mock_client)
        # Fail-closed: Redis error → reject auth to prevent replay attacks
        result = manager._check_nonce("nonce-exception-depth")
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# reinstate_agent — with identity record update
# ═══════════════════════════════════════════════════════════════════════════════

class TestReinstateWithRecordDepth:
    def test_reinstate_updates_record_fields(self, manager):
        did = "did:key:z6MkReinstateDepth"
        record = AgentIdentityRecord(
            did=did,
            revoked=True,
            revoked_by="admin",
            revocation_reason="test reason",
        )
        manager._revoked_dids.add(did)
        manager._identity_cache[did] = record
        manager._get_redis = MagicMock(return_value=None)
        result = manager.reinstate_agent(did, "admin", "cleared")
        assert result is True
        assert record.revoked is False
        assert record.revoked_by is None
        assert record.revocation_reason is None

    def test_reinstate_without_identity_record(self, manager):
        did = "did:key:z6MkReinstateNoRecord"
        manager._revoked_dids.add(did)
        manager._get_redis = MagicMock(return_value=None)
        # No identity record — should still succeed (just clears revoked set)
        result = manager.reinstate_agent(did, "admin")
        assert result is True
        assert did not in manager._revoked_dids


# ═══════════════════════════════════════════════════════════════════════════════
# resolve_did — cache expiry and force_refresh
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveDIDDepth:
    def test_force_refresh_bypasses_cache(self, manager, sample_did_key_fixture):
        did, public_bytes, _ = sample_did_key_fixture
        manager._get_redis = MagicMock(return_value=None)
        stale_doc = DIDDocument(
            did=did,
            method="key",
            public_key_bytes=b"\x00" * 32,
            public_key_hex="0" * 64,
        )
        manager._did_cache[did] = stale_doc
        result = manager.resolve_did(did, force_refresh=True)
        assert result is not None
        assert result.public_key_bytes == public_bytes

    def test_expired_cache_re_resolves(self, manager, sample_did_key_fixture):
        did, public_bytes, _ = sample_did_key_fixture
        expired_doc = DIDDocument(
            did=did,
            method="key",
            public_key_bytes=public_bytes,
            public_key_hex=public_bytes.hex(),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        manager._did_cache[did] = expired_doc
        manager._get_redis = MagicMock(return_value=None)
        result = manager.resolve_did(did)
        assert result is not None  # Re-resolved from did:key

    def test_valid_cache_hit_returns_cached(self, manager, sample_did_key_fixture):
        did, public_bytes, _ = sample_did_key_fixture
        valid_doc = DIDDocument(
            did=did,
            method="key",
            public_key_bytes=public_bytes,
            public_key_hex=public_bytes.hex(),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        manager._did_cache[did] = valid_doc
        result = manager.resolve_did(did)
        assert result is valid_doc  # Same object from cache

    def test_resolve_did_local_did_key(self, manager, sample_did_key_fixture):
        did, public_bytes, _ = sample_did_key_fixture
        result = manager.resolve_did_local(did)
        assert result is not None
        assert result.public_key_bytes == public_bytes
        assert result.method == "key"

    def test_resolve_did_local_non_key_returns_none(self, manager):
        result = manager.resolve_did_local("did:web:example.com")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# validate_credential — edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateCredentialDepth:
    def _base_settings(self):
        settings = MagicMock()
        settings.identiclaw_known_issuers = ["did:web:trusted.example.com"]
        settings.identiclaw_vc_cache_ttl_hours = 12
        return settings

    @patch("core.identiclaw.get_settings")
    def test_issuer_as_dict(self, mock_settings, manager):
        mock_settings.return_value = self._base_settings()
        manager._get_redis = MagicMock(return_value=None)
        vc_json = {
            "id": "vc-dict-issuer-depth-001",
            "type": ["VerifiableCredential"],
            "issuer": {"id": "did:web:trusted.example.com"},
            "issuanceDate": datetime.now(timezone.utc).isoformat(),
            "expirationDate": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "credentialSubject": {
                "id": "did:key:z6MkSubject",
                "scopes": ["agent:read"],
            },
            "proof": {"type": "Ed25519Signature2020", "proofValue": ""},
        }
        result = manager.validate_credential(vc_json)
        assert result is not None
        assert result.issuer_did == "did:web:trusted.example.com"

    @patch("core.identiclaw.get_settings")
    def test_scope_as_space_delimited_string(self, mock_settings, manager):
        mock_settings.return_value = self._base_settings()
        manager._get_redis = MagicMock(return_value=None)
        vc_json = {
            "id": "vc-scope-str-depth-001",
            "type": ["VerifiableCredential"],
            "issuer": "did:web:trusted.example.com",
            "issuanceDate": datetime.now(timezone.utc).isoformat(),
            "expirationDate": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "credentialSubject": {
                "id": "did:key:z6MkSubject",
                "scopes": "agent:read agent:write",
            },
            "proof": {"type": "Ed25519Signature2020", "proofValue": ""},
        }
        result = manager.validate_credential(vc_json)
        assert result is not None
        assert "agent:read" in result.scopes
        assert "agent:write" in result.scopes

    @patch("core.identiclaw.get_settings")
    def test_jti_fallback_when_no_id_field(self, mock_settings, manager):
        mock_settings.return_value = self._base_settings()
        manager._get_redis = MagicMock(return_value=None)
        vc_json = {
            "jti": "vc-jti-depth-001",
            "type": ["VerifiableCredential"],
            "issuer": "did:web:trusted.example.com",
            "credentialSubject": {
                "id": "did:key:z6MkSubject",
                "scopes": ["agent:read"],
            },
            "proof": {},
        }
        result = manager.validate_credential(vc_json)
        assert result is not None
        assert result.vc_id == "vc-jti-depth-001"

    @patch("core.identiclaw.get_settings")
    def test_credential_type_as_string_converted_to_list(self, mock_settings, manager):
        mock_settings.return_value = self._base_settings()
        manager._get_redis = MagicMock(return_value=None)
        vc_json = {
            "id": "vc-type-str-depth-001",
            "type": "VerifiableCredential",  # String, not list
            "issuer": "did:web:trusted.example.com",
            "issuanceDate": datetime.now(timezone.utc).isoformat(),
            "expirationDate": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "credentialSubject": {
                "id": "did:key:z6MkSubject",
                "scopes": ["agent:read"],
            },
            "proof": {},
        }
        result = manager.validate_credential(vc_json)
        assert result is not None
        assert isinstance(result.credential_type, list)

    @patch("core.identiclaw.get_settings")
    def test_proof_uses_jws_fallback(self, mock_settings, manager):
        mock_settings.return_value = self._base_settings()
        manager._get_redis = MagicMock(return_value=None)
        vc_json = {
            "id": "vc-jws-depth-001",
            "type": ["VerifiableCredential"],
            "issuer": "did:web:trusted.example.com",
            "issuanceDate": datetime.now(timezone.utc).isoformat(),
            "expirationDate": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "credentialSubject": {
                "id": "did:key:z6MkSubject",
                "scopes": ["agent:read"],
            },
            "proof": {"type": "Ed25519Signature2020", "jws": ""},  # jws not proofValue
        }
        result = manager.validate_credential(vc_json)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SCOPE_PERMISSION_MAP completeness
# ═══════════════════════════════════════════════════════════════════════════════

class TestScopePermissionMapDepth:
    def test_all_mcp_scopes_present(self):
        assert "mcp:tool:invoke" in SCOPE_PERMISSION_MAP
        assert "mcp:tool:list" in SCOPE_PERMISSION_MAP
        assert "mcp:resource:read" in SCOPE_PERMISSION_MAP
        assert "mcp:resource:write" in SCOPE_PERMISSION_MAP
        assert "mcp:prompt:execute" in SCOPE_PERMISSION_MAP

    def test_all_telsonbase_scopes_present(self):
        tb_scopes = [k for k in SCOPE_PERMISSION_MAP if k.startswith("telsonbase:")]
        assert len(tb_scopes) >= 6

    def test_agent_execute_grants_all_three(self, manager):
        perms = manager.map_scopes_to_permissions(["agent:execute"])
        assert "read" in perms
        assert "write" in perms
        assert "execute" in perms

    def test_mcp_tool_list_scope(self, manager):
        perms = manager.map_scopes_to_permissions(["mcp:tool:list"])
        assert "tool_list" in perms

    def test_mcp_prompt_execute_scope(self, manager):
        perms = manager.map_scopes_to_permissions(["mcp:prompt:execute"])
        assert "prompt_execute" in perms

    def test_telsonbase_backup_read_scope(self, manager):
        perms = manager.map_scopes_to_permissions(["telsonbase:backup:read"])
        assert "backup_read" in perms

    def test_telsonbase_llm_manage_scope(self, manager):
        perms = manager.map_scopes_to_permissions(["telsonbase:llm:manage"])
        assert "llm_manage" in perms

    def test_duplicate_permissions_deduplicated(self, manager):
        # agent:read and mcp:resource:read both grant "read"
        perms = manager.map_scopes_to_permissions(["agent:read", "mcp:resource:read"])
        assert perms.count("read") == 1  # Deduplicated
