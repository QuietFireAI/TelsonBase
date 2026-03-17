# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_email_verification_depth.py
# REM: Depth tests for core/email_verification.py — pure in-memory, no external deps

import sys
from unittest.mock import AsyncMock, MagicMock, patch

# REM: Stub email_sender so create_verification doesn't attempt SMTP
if "core.email_sender" not in sys.modules:
    _mock_sender = MagicMock()
    _mock_sender.send_verification_email = AsyncMock(return_value=None)
    sys.modules["core.email_sender"] = _mock_sender

import pytest
from datetime import datetime, timedelta, timezone

from core.email_verification import (
    EmailVerificationManager,
    VerificationStatus,
    VerificationToken,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    monkeypatch.setattr("core.persistence.get_redis", lambda: None)


@pytest.fixture
def mgr():
    m = object.__new__(EmailVerificationManager)
    m._tokens = {}
    m._verified_emails = {}
    m._resend_tracking = {}
    return m


# ═══════════════════════════════════════════════════════════════════════════════
# VerificationStatus enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerificationStatus:
    def test_pending_value(self):
        assert VerificationStatus.PENDING.value == "pending"

    def test_verified_value(self):
        assert VerificationStatus.VERIFIED.value == "verified"

    def test_expired_value(self):
        assert VerificationStatus.EXPIRED.value == "expired"

    def test_failed_value(self):
        assert VerificationStatus.FAILED.value == "failed"

    def test_four_statuses(self):
        assert len(VerificationStatus) == 4


# ═══════════════════════════════════════════════════════════════════════════════
# EmailVerificationManager constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_max_attempts(self, mgr):
        assert mgr.MAX_ATTEMPTS == 3

    def test_max_resends_per_hour(self, mgr):
        assert mgr.MAX_RESENDS_PER_HOUR == 3

    def test_token_lifetime_24h(self, mgr):
        assert mgr.TOKEN_LIFETIME == timedelta(hours=24)


# ═══════════════════════════════════════════════════════════════════════════════
# create_verification
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateVerification:
    def test_returns_verification_token(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        assert isinstance(tok, VerificationToken)

    def test_stored_by_user_id(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        assert "u1" in mgr._tokens

    def test_status_pending(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        assert tok.status == VerificationStatus.PENDING

    def test_attempts_zero(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        assert tok.attempts == 0

    def test_email_stored(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        assert tok.email == "user@example.com"

    def test_user_id_stored(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        assert tok.user_id == "u1"

    def test_token_nonempty(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        assert len(tok.token) > 0

    def test_expires_in_24h(self, mgr):
        before = datetime.now(timezone.utc)
        tok = mgr.create_verification("u1", "user@example.com")
        diff = (tok.expires_at - before).total_seconds()
        assert abs(diff - 86400) < 5

    def test_overwrites_existing_token(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        tok2 = mgr.create_verification("u1", "user@example.com")
        assert mgr._tokens["u1"] is tok2

    def test_different_users_independent(self, mgr):
        mgr.create_verification("u1", "a@example.com")
        mgr.create_verification("u2", "b@example.com")
        assert "u1" in mgr._tokens
        assert "u2" in mgr._tokens


# ═══════════════════════════════════════════════════════════════════════════════
# verify_email
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyEmail:
    def test_valid_token_returns_true(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        assert mgr.verify_email("u1", tok.token) is True

    def test_invalid_token_returns_false(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        assert mgr.verify_email("u1", "wrong_token") is False

    def test_unknown_user_returns_false(self, mgr):
        assert mgr.verify_email("nobody", "any_token") is False

    def test_status_becomes_verified_on_success(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr.verify_email("u1", tok.token)
        assert mgr._tokens["u1"].status == VerificationStatus.VERIFIED

    def test_already_verified_returns_true(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr.verify_email("u1", tok.token)
        assert mgr.verify_email("u1", "any_token") is True

    def test_increments_attempts_on_failure(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        mgr.verify_email("u1", "wrong")
        assert mgr._tokens["u1"].attempts == 1

    def test_increments_attempts_on_success(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr.verify_email("u1", tok.token)
        assert mgr._tokens["u1"].attempts == 1

    def test_expired_token_returns_false(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr._tokens["u1"].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert mgr.verify_email("u1", tok.token) is False

    def test_expired_token_sets_status(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr._tokens["u1"].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        mgr.verify_email("u1", tok.token)
        assert mgr._tokens["u1"].status == VerificationStatus.EXPIRED

    def test_max_attempts_returns_false(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr._tokens["u1"].attempts = mgr.MAX_ATTEMPTS
        assert mgr.verify_email("u1", tok.token) is False

    def test_max_attempts_sets_failed_status(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr._tokens["u1"].attempts = mgr.MAX_ATTEMPTS
        mgr.verify_email("u1", tok.token)
        assert mgr._tokens["u1"].status == VerificationStatus.FAILED

    def test_verified_email_stored_on_success(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr.verify_email("u1", tok.token)
        assert "u1" in mgr._verified_emails


# ═══════════════════════════════════════════════════════════════════════════════
# is_verified
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsVerified:
    def test_false_initially(self, mgr):
        assert mgr.is_verified("u1") is False

    def test_false_before_verify(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        assert mgr.is_verified("u1") is False

    def test_true_after_verify(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr.verify_email("u1", tok.token)
        assert mgr.is_verified("u1") is True

    def test_returns_bool(self, mgr):
        assert isinstance(mgr.is_verified("u1"), bool)


# ═══════════════════════════════════════════════════════════════════════════════
# get_verification_status
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetVerificationStatus:
    def test_no_record_returns_dict(self, mgr):
        status = mgr.get_verification_status("u1")
        assert isinstance(status, dict)

    def test_no_record_user_id_correct(self, mgr):
        status = mgr.get_verification_status("u1")
        assert status["user_id"] == "u1"

    def test_no_record_not_verified(self, mgr):
        status = mgr.get_verification_status("u1")
        assert status["verified"] is False

    def test_no_record_status_none(self, mgr):
        status = mgr.get_verification_status("u1")
        assert status["status"] is None

    def test_pending_status(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        status = mgr.get_verification_status("u1")
        assert status["status"] == "pending"

    def test_has_email(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        status = mgr.get_verification_status("u1")
        assert status["email"] == "user@example.com"

    def test_has_attempts(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        status = mgr.get_verification_status("u1")
        assert "attempts" in status
        assert status["attempts"] == 0

    def test_has_max_attempts(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        status = mgr.get_verification_status("u1")
        assert status["max_attempts"] == mgr.MAX_ATTEMPTS

    def test_verified_true_after_verify(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr.verify_email("u1", tok.token)
        status = mgr.get_verification_status("u1")
        assert status["verified"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# _check_rate_limit
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckRateLimit:
    def test_allowed_for_new_user(self, mgr):
        assert mgr._check_rate_limit("u1") is True

    def test_allowed_below_limit(self, mgr):
        now = datetime.now(timezone.utc)
        mgr._resend_tracking["u1"] = [now, now]
        assert mgr._check_rate_limit("u1") is True

    def test_blocked_at_limit(self, mgr):
        now = datetime.now(timezone.utc)
        mgr._resend_tracking["u1"] = [now, now, now]
        assert mgr._check_rate_limit("u1") is False

    def test_old_entries_pruned(self, mgr):
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        mgr._resend_tracking["u1"] = [old, old, old]
        # All old → within limit
        assert mgr._check_rate_limit("u1") is True

    def test_mix_old_and_recent(self, mgr):
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=2)
        mgr._resend_tracking["u1"] = [old, now, now]
        # 2 recent → below limit
        assert mgr._check_rate_limit("u1") is True


# ═══════════════════════════════════════════════════════════════════════════════
# cleanup_expired
# ═══════════════════════════════════════════════════════════════════════════════

class TestCleanupExpired:
    def test_returns_zero_when_none_expired(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        assert mgr.cleanup_expired() == 0

    def test_removes_expired_token(self, mgr):
        mgr.create_verification("u1", "user@example.com")
        mgr._tokens["u1"].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        mgr.cleanup_expired()
        assert "u1" not in mgr._tokens

    def test_returns_count_of_removed(self, mgr):
        for uid in ["u1", "u2", "u3"]:
            mgr.create_verification(uid, f"{uid}@example.com")
            mgr._tokens[uid].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert mgr.cleanup_expired() == 3

    def test_keeps_verified_even_if_expired(self, mgr):
        tok = mgr.create_verification("u1", "user@example.com")
        mgr.verify_email("u1", tok.token)
        mgr._tokens["u1"].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        mgr.cleanup_expired()
        assert "u1" in mgr._tokens

    def test_empty_manager_returns_zero(self, mgr):
        assert mgr.cleanup_expired() == 0
