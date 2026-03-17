# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_user_management_depth.py
# REM: Depth tests for core/user_management.py — pure in-memory, no external deps

import sys
from unittest.mock import MagicMock

# REM: Stub bcrypt if not installed (CI Docker has it; local dev Python 3.14 may not)
if "bcrypt" not in sys.modules:
    _mock_bcrypt = MagicMock()
    sys.modules["bcrypt"] = _mock_bcrypt

import pytest
from datetime import datetime, timedelta, timezone

from core.user_management import (
    UserManager,
    MAX_FAILED_ATTEMPTS,
    LOCKOUT_DURATION_MINUTES,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    monkeypatch.setattr("core.persistence.get_redis", lambda: None)


@pytest.fixture
def mgr():
    m = object.__new__(UserManager)
    m._password_hashes = {}
    m._failed_attempts = {}
    m._lockout_until = {}
    m._user_count = 0
    return m


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_max_failed_attempts(self):
        assert MAX_FAILED_ATTEMPTS == 5

    def test_lockout_duration_minutes(self):
        assert LOCKOUT_DURATION_MINUTES == 15


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_password_strength
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidatePasswordStrength:
    def test_valid_password_returns_true(self, mgr):
        ok, msg = mgr._validate_password_strength("SecurePass1!")
        assert ok is True
        assert msg == ""

    def test_too_short_returns_false(self, mgr):
        ok, msg = mgr._validate_password_strength("Short1!")
        assert ok is False
        assert "12 characters" in msg

    def test_exactly_12_chars_valid(self, mgr):
        # exactly 12: S e c u r e P a s s 1 !
        ok, _ = mgr._validate_password_strength("SecurePass1!")
        assert ok is True

    def test_11_chars_invalid(self, mgr):
        ok, _ = mgr._validate_password_strength("Securepass1")
        assert ok is False

    def test_no_uppercase_returns_false(self, mgr):
        ok, msg = mgr._validate_password_strength("securepass1!")
        assert ok is False
        assert "uppercase" in msg.lower()

    def test_no_lowercase_returns_false(self, mgr):
        ok, msg = mgr._validate_password_strength("SECUREPASS1!")
        assert ok is False
        assert "lowercase" in msg.lower()

    def test_no_digit_returns_false(self, mgr):
        ok, msg = mgr._validate_password_strength("SecurePassword!")
        assert ok is False
        assert "digit" in msg.lower()

    def test_no_special_char_returns_false(self, mgr):
        ok, msg = mgr._validate_password_strength("SecurePass123")
        assert ok is False
        assert "special" in msg.lower()

    def test_special_char_exclamation(self, mgr):
        ok, _ = mgr._validate_password_strength("SecurePass1!")
        assert ok is True

    def test_special_char_at(self, mgr):
        ok, _ = mgr._validate_password_strength("SecurePass1@")
        assert ok is True

    def test_special_char_hash(self, mgr):
        ok, _ = mgr._validate_password_strength("SecurePass1#")
        assert ok is True

    def test_special_char_dollar(self, mgr):
        ok, _ = mgr._validate_password_strength("SecurePass1$")
        assert ok is True

    def test_special_char_underscore(self, mgr):
        ok, _ = mgr._validate_password_strength("SecurePass1_")
        assert ok is True

    def test_long_password_valid(self, mgr):
        ok, _ = mgr._validate_password_strength("A" * 40 + "b1!")
        assert ok is True

    def test_empty_password_returns_false(self, mgr):
        ok, _ = mgr._validate_password_strength("")
        assert ok is False

    def test_returns_tuple_of_two(self, mgr):
        result = mgr._validate_password_strength("SecurePass1!")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_error_message_nonempty_on_failure(self, mgr):
        ok, msg = mgr._validate_password_strength("weak")
        assert ok is False
        assert len(msg) > 0

    def test_valid_error_message_empty_on_success(self, mgr):
        ok, msg = mgr._validate_password_strength("GoodPassword1!")
        assert ok is True
        assert msg == ""


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_email
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateEmail:
    def test_valid_simple_email(self, mgr):
        assert mgr._validate_email("user@example.com") is True

    def test_valid_subdomain(self, mgr):
        assert mgr._validate_email("user@mail.example.com") is True

    def test_valid_plus_addressing(self, mgr):
        assert mgr._validate_email("user+tag@example.com") is True

    def test_valid_dots_in_local(self, mgr):
        assert mgr._validate_email("first.last@example.com") is True

    def test_valid_two_char_tld(self, mgr):
        assert mgr._validate_email("user@example.io") is True

    def test_valid_numeric_in_domain(self, mgr):
        assert mgr._validate_email("user@example123.com") is True

    def test_missing_at_sign(self, mgr):
        assert mgr._validate_email("userexample.com") is False

    def test_missing_domain(self, mgr):
        assert mgr._validate_email("user@") is False

    def test_missing_tld(self, mgr):
        assert mgr._validate_email("user@example") is False

    def test_single_char_tld_invalid(self, mgr):
        assert mgr._validate_email("user@example.c") is False

    def test_empty_string(self, mgr):
        assert mgr._validate_email("") is False

    def test_at_only(self, mgr):
        assert mgr._validate_email("@") is False

    def test_returns_bool(self, mgr):
        result = mgr._validate_email("user@example.com")
        assert isinstance(result, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# _is_account_locked
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsAccountLocked:
    def test_not_locked_initially(self, mgr):
        assert mgr._is_account_locked("alice") is False

    def test_locked_when_lockout_in_future(self, mgr):
        mgr._lockout_until["alice"] = datetime.now(timezone.utc) + timedelta(minutes=5)
        assert mgr._is_account_locked("alice") is True

    def test_not_locked_when_lockout_expired(self, mgr):
        mgr._lockout_until["alice"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert mgr._is_account_locked("alice") is False

    def test_expired_lockout_key_cleared(self, mgr):
        mgr._lockout_until["alice"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        mgr._is_account_locked("alice")
        assert "alice" not in mgr._lockout_until

    def test_expired_lockout_clears_failed_attempts(self, mgr):
        mgr._lockout_until["alice"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        mgr._failed_attempts["alice"] = 5
        mgr._is_account_locked("alice")
        assert "alice" not in mgr._failed_attempts

    def test_active_lockout_not_cleared(self, mgr):
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        mgr._lockout_until["alice"] = future
        mgr._is_account_locked("alice")
        assert "alice" in mgr._lockout_until

    def test_unknown_user_not_locked(self, mgr):
        assert mgr._is_account_locked("nobody") is False

    def test_different_users_independent(self, mgr):
        mgr._lockout_until["alice"] = datetime.now(timezone.utc) + timedelta(minutes=5)
        assert mgr._is_account_locked("bob") is False


# ═══════════════════════════════════════════════════════════════════════════════
# _record_failed_attempt
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecordFailedAttempt:
    def test_first_attempt_sets_count_to_one(self, mgr):
        mgr._record_failed_attempt("alice")
        assert mgr._failed_attempts["alice"] == 1

    def test_increments_on_each_call(self, mgr):
        for _ in range(3):
            mgr._record_failed_attempt("alice")
        assert mgr._failed_attempts["alice"] == 3

    def test_no_lockout_below_threshold(self, mgr):
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            mgr._record_failed_attempt("alice")
        assert "alice" not in mgr._lockout_until

    def test_lockout_triggered_at_threshold(self, mgr):
        for _ in range(MAX_FAILED_ATTEMPTS):
            mgr._record_failed_attempt("alice")
        assert "alice" in mgr._lockout_until

    def test_lockout_time_is_in_future(self, mgr):
        for _ in range(MAX_FAILED_ATTEMPTS):
            mgr._record_failed_attempt("alice")
        assert mgr._lockout_until["alice"] > datetime.now(timezone.utc)

    def test_lockout_duration_approximately_correct(self, mgr):
        before = datetime.now(timezone.utc)
        for _ in range(MAX_FAILED_ATTEMPTS):
            mgr._record_failed_attempt("alice")
        diff = (mgr._lockout_until["alice"] - before).total_seconds()
        assert abs(diff - LOCKOUT_DURATION_MINUTES * 60) < 5

    def test_independent_user_counters(self, mgr):
        mgr._record_failed_attempt("alice")
        mgr._record_failed_attempt("alice")
        mgr._record_failed_attempt("bob")
        assert mgr._failed_attempts["alice"] == 2
        assert mgr._failed_attempts["bob"] == 1

    def test_does_not_lockout_one_below_threshold(self, mgr):
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            mgr._record_failed_attempt("alice")
        assert mgr._is_account_locked("alice") is False

    def test_lockout_confirmed_by_is_account_locked(self, mgr):
        for _ in range(MAX_FAILED_ATTEMPTS):
            mgr._record_failed_attempt("alice")
        assert mgr._is_account_locked("alice") is True


# ═══════════════════════════════════════════════════════════════════════════════
# _clear_failed_attempts
# ═══════════════════════════════════════════════════════════════════════════════

class TestClearFailedAttempts:
    def test_clears_failed_count(self, mgr):
        mgr._failed_attempts["alice"] = 3
        mgr._clear_failed_attempts("alice")
        assert "alice" not in mgr._failed_attempts

    def test_clears_lockout_entry(self, mgr):
        mgr._lockout_until["alice"] = datetime.now(timezone.utc) + timedelta(minutes=10)
        mgr._clear_failed_attempts("alice")
        assert "alice" not in mgr._lockout_until

    def test_idempotent_for_unknown_user(self, mgr):
        mgr._clear_failed_attempts("nobody")  # should not raise

    def test_does_not_affect_other_users(self, mgr):
        mgr._failed_attempts["alice"] = 2
        mgr._failed_attempts["bob"] = 4
        mgr._clear_failed_attempts("alice")
        assert mgr._failed_attempts["bob"] == 4

    def test_clears_both_dicts(self, mgr):
        mgr._failed_attempts["alice"] = 5
        mgr._lockout_until["alice"] = datetime.now(timezone.utc) + timedelta(minutes=5)
        mgr._clear_failed_attempts("alice")
        assert "alice" not in mgr._failed_attempts
        assert "alice" not in mgr._lockout_until

    def test_after_clear_is_account_locked_returns_false(self, mgr):
        mgr._lockout_until["alice"] = datetime.now(timezone.utc) + timedelta(minutes=10)
        mgr._clear_failed_attempts("alice")
        assert mgr._is_account_locked("alice") is False


# ═══════════════════════════════════════════════════════════════════════════════
# is_first_user
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsFirstUser:
    def test_true_when_zero_users(self, mgr):
        assert mgr.is_first_user() is True

    def test_false_when_one_user(self, mgr):
        mgr._user_count = 1
        assert mgr.is_first_user() is False

    def test_false_when_multiple_users(self, mgr):
        mgr._user_count = 10
        assert mgr.is_first_user() is False

    def test_returns_bool(self, mgr):
        assert isinstance(mgr.is_first_user(), bool)
