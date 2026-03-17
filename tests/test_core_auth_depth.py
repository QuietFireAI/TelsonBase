# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_auth_depth.py
# REM: Depth tests for core/auth.py — pure in-memory, no Redis/external deps

import hashlib
import pytest
from datetime import datetime, timedelta, timezone

import core.auth as auth_module
from core.auth import (
    APIKEY_AUDIT_INTERVAL,
    _APIKEY_PREFIX,
    _REVOCATION_PREFIX,
    _hash_key,
    _should_log_apikey_auth,
    _revoked_tokens_fallback,
    is_token_revoked,
    revoke_token,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    monkeypatch.setattr("core.persistence.get_redis", lambda: None)
    # REM: Also patch the auth module's own _get_redis_client to always return None
    monkeypatch.setattr("core.auth._get_redis_client", lambda: None)


@pytest.fixture(autouse=True)
def _reset_apikey_logged(monkeypatch):
    """REM: Clear the module-level rate-limit dict between tests."""
    monkeypatch.setattr("core.auth._apikey_last_logged", {})


@pytest.fixture(autouse=True)
def _reset_revocation_fallback():
    """REM: Clear the in-memory revocation set between tests."""
    _revoked_tokens_fallback.clear()
    yield
    _revoked_tokens_fallback.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_apikey_audit_interval_five_minutes(self):
        assert APIKEY_AUDIT_INTERVAL == timedelta(minutes=5)

    def test_revocation_prefix(self):
        assert _REVOCATION_PREFIX == "jwt:revoked:"

    def test_apikey_prefix(self):
        assert _APIKEY_PREFIX == "apikeys:"


# ═══════════════════════════════════════════════════════════════════════════════
# _hash_key
# ═══════════════════════════════════════════════════════════════════════════════

class TestHashKey:
    def test_returns_string(self):
        assert isinstance(_hash_key("mykey"), str)

    def test_returns_sha256_hex(self):
        key = "testkey"
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert _hash_key(key) == expected

    def test_length_is_64(self):
        assert len(_hash_key("any_key")) == 64

    def test_deterministic(self):
        assert _hash_key("same") == _hash_key("same")

    def test_different_keys_different_hashes(self):
        assert _hash_key("key_a") != _hash_key("key_b")

    def test_empty_string(self):
        result = _hash_key("")
        assert len(result) == 64

    def test_unicode_key(self):
        result = _hash_key("πασσword")
        assert len(result) == 64


# ═══════════════════════════════════════════════════════════════════════════════
# _should_log_apikey_auth
# ═══════════════════════════════════════════════════════════════════════════════

class TestShouldLogApikeyAuth:
    def test_returns_true_for_new_actor(self):
        assert _should_log_apikey_auth("actor-1") is True

    def test_second_call_returns_false(self):
        _should_log_apikey_auth("actor-1")
        assert _should_log_apikey_auth("actor-1") is False

    def test_different_actors_independent(self):
        assert _should_log_apikey_auth("actor-a") is True
        assert _should_log_apikey_auth("actor-b") is True

    def test_returns_true_after_interval_expired(self, monkeypatch):
        # Pre-populate last-logged time as 6 minutes ago (past the 5-min interval)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=6)
        monkeypatch.setattr("core.auth._apikey_last_logged", {"actor-x": old_time})
        assert _should_log_apikey_auth("actor-x") is True

    def test_returns_false_within_interval(self, monkeypatch):
        # Pre-populate last-logged time as 2 minutes ago (within 5-min interval)
        recent = datetime.now(timezone.utc) - timedelta(minutes=2)
        monkeypatch.setattr("core.auth._apikey_last_logged", {"actor-y": recent})
        assert _should_log_apikey_auth("actor-y") is False

    def test_updates_last_logged_on_true(self):
        before = datetime.now(timezone.utc)
        _should_log_apikey_auth("actor-new")
        stored = auth_module._apikey_last_logged.get("actor-new")
        assert stored is not None
        assert stored >= before

    def test_returns_bool(self):
        result = _should_log_apikey_auth("actor-type")
        assert isinstance(result, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# revoke_token / is_token_revoked (in-memory fallback path)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRevokeToken:
    def test_returns_true(self):
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        assert revoke_token("jti-abc", expires) is True

    def test_adds_to_fallback_set(self):
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        revoke_token("jti-xyz", expires)
        assert "jti-xyz" in _revoked_tokens_fallback

    def test_revoked_by_stored(self):
        # Just verifies the function accepts the parameter without error
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        revoke_token("jti-admin", expires, revoked_by="admin-1")
        assert "jti-admin" in _revoked_tokens_fallback

    def test_multiple_tokens(self):
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        revoke_token("jti-1", expires)
        revoke_token("jti-2", expires)
        assert "jti-1" in _revoked_tokens_fallback
        assert "jti-2" in _revoked_tokens_fallback


class TestIsTokenRevoked:
    def test_false_for_unknown_token(self):
        assert is_token_revoked("never-revoked") is False

    def test_true_after_revocation(self):
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        revoke_token("jti-check", expires)
        assert is_token_revoked("jti-check") is True

    def test_false_for_different_token(self):
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        revoke_token("jti-other", expires)
        assert is_token_revoked("jti-different") is False

    def test_fallback_check_without_redis(self):
        # With Redis mocked to None, fallback set is the source of truth
        _revoked_tokens_fallback.add("direct-add")
        assert is_token_revoked("direct-add") is True

    def test_empty_revocation_returns_false(self):
        assert is_token_revoked("") is False
