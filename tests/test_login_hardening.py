# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
# tests/test_login_hardening.py
# REM: Regression tests for the 2026-11-11 sign-in changes: role assignment at sign-up,
# REM: required second factor, step tokens, backup codes, attempt limits, ending existing
# REM: logins, and sign-in state shared between server processes.
# REM: Run against commit bb8a86f (the code before these changes): 14 of these tests fail,
# REM: 9 cannot start because they use functions added by the change, and 2 pass on both
# REM: (they pin behaviour that must stay: default role viewer, administrator may assign).

import os
import uuid

import pyotp
import pytest

PW = "SecurePassword123!"
API = {"X-API-Key": "test_api_key_12345"}


def _redis_up() -> bool:
    try:
        import redis
        return bool(redis.Redis.from_url(os.environ["REDIS_URL"]).ping())
    except Exception:
        return False


# REM: CI's unit job runs without Redis. Tests about state shared through Redis skip there.
requires_redis = pytest.mark.skipif(not _redis_up(), reason="needs Redis (shared sign-in state)")


@pytest.fixture
def token_lookups_open(monkeypatch):
    """
    REM: The revocation list and per-account cutoff live in Redis and fail closed without it.
    REM: Tests about other token rules stub those two lookups so they also run without Redis.
    """
    import core.auth as auth_module
    monkeypatch.setattr(auth_module, "is_token_revoked", lambda jti: False)
    monkeypatch.setattr(auth_module, "is_issued_before_cutoff", lambda sub, iat: False)


@pytest.fixture
def mfa_enforced(monkeypatch):
    monkeypatch.setenv("TELSONBASE_MFA_ENFORCEMENT", "on")


def _verify_email(user_id: str, email: str) -> None:
    from core.email_verification import email_verification as ev
    ev._verified_emails[user_id] = email
    try:
        ev._save_verified_email(user_id, email)
    except Exception:
        pass


def _make_user(role: str = None):
    """REM: A verified account that is not the first account. Returns (username, user_id)."""
    from core.user_management import user_manager
    if user_manager.is_first_user():
        seed = f"seed_{uuid.uuid4().hex[:8]}"
        user_manager.register_user(seed, f"{seed}@test.example.com", PW)
    name = f"lh_{uuid.uuid4().hex[:10]}"
    email = f"{name}@test.example.com"
    user = user_manager.register_user(name, email, PW, roles=[role] if role else None)
    _verify_email(user["user_id"], email)
    return name, user["user_id"]


def _solved_captcha() -> str:
    from core.captcha import captcha_manager
    challenge = captcha_manager.generate_challenge()
    captcha_manager.verify_challenge(challenge.challenge_id, challenge.answer)
    return challenge.challenge_id


def _login(client, username: str):
    return client.post("/v1/auth/login", json={"username": username, "password": PW})


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════════════
# Sign-up: role assignment
# ═══════════════════════════════════════════════════════════════════════════════

class TestSignupRole:
    def test_public_signup_cannot_choose_a_role(self, client):
        _make_user()
        name = f"lh_{uuid.uuid4().hex[:10]}"
        resp = client.post("/v1/auth/register", json={
            "username": name, "email": f"{name}@test.example.com", "password": PW,
            "role": "super_admin", "captcha_challenge_id": _solved_captcha(),
        })
        assert resp.status_code == 403
        from core.rbac import rbac_manager
        assert rbac_manager.get_user_by_username(name) is None

    def test_public_signup_without_role_is_viewer(self, client):
        _make_user()
        name = f"lh_{uuid.uuid4().hex[:10]}"
        resp = client.post("/v1/auth/register", json={
            "username": name, "email": f"{name}@test.example.com", "password": PW,
            "captcha_challenge_id": _solved_captcha(),
        })
        assert resp.status_code == 200
        assert resp.json()["user"]["roles"] == ["viewer"]

    def test_administrator_credential_may_assign_a_role(self, client):
        _make_user()
        name = f"lh_{uuid.uuid4().hex[:10]}"
        resp = client.post("/v1/auth/register", headers=API, json={
            "username": name, "email": f"{name}@test.example.com", "password": PW,
            "role": "operator", "captcha_challenge_id": _solved_captcha(),
        })
        assert resp.status_code == 200
        assert resp.json()["user"]["roles"] == ["operator"]

    def test_unknown_role_name_is_refused(self, client):
        _make_user()
        name = f"lh_{uuid.uuid4().hex[:10]}"
        resp = client.post("/v1/auth/register", headers=API, json={
            "username": name, "email": f"{name}@test.example.com", "password": PW,
            "role": "wizard", "captcha_challenge_id": _solved_captcha(),
        })
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Required second factor
# ═══════════════════════════════════════════════════════════════════════════════

class TestRequiredSecondFactor:
    def test_no_access_token_until_enrolled(self, client, mfa_enforced):
        name, _ = _make_user("admin")
        data = _login(client, name).json()
        assert data["mfa_required"] is True
        assert data["mfa_enrollment_required"] is True
        assert "access_token" not in data
        assert data["enrollment_token"]

    def test_enforcement_off_reports_recommendation(self, client, monkeypatch):
        monkeypatch.setenv("TELSONBASE_MFA_ENFORCEMENT", "off")
        name, _ = _make_user("admin")
        data = _login(client, name).json()
        assert "access_token" in data
        assert data["mfa_enrollment_recommended"] is True

    def test_role_without_requirement_is_unaffected(self, client, mfa_enforced):
        name, _ = _make_user()
        data = _login(client, name).json()
        assert "access_token" in data
        assert data["mfa_enrollment_recommended"] is False

    def test_enrol_then_sign_in_with_code(self, client, mfa_enforced, token_lookups_open):
        name, user_id = _make_user("admin")
        enrollment_token = _login(client, name).json()["enrollment_token"]

        enrolled = client.post("/v1/auth/mfa/enroll", json={"enrollment_token": enrollment_token})
        assert enrolled.status_code == 200
        secret = enrolled.json()["secret"]
        assert len(enrolled.json()["backup_codes"]) == 10

        second = _login(client, name).json()
        assert second["mfa_required"] is True
        assert "access_token" not in second

        done = client.post("/v1/auth/login/mfa", json={
            "pre_mfa_token": second["pre_mfa_token"],
            "totp_code": pyotp.TOTP(secret).now(),
        })
        assert done.status_code == 200
        profile = client.get("/v1/auth/profile", headers=_bearer(done.json()["access_token"]))
        assert profile.status_code == 200
        assert profile.json()["profile"]["user_id"] == user_id

    def test_enrolment_is_not_repeated(self, client, mfa_enforced, token_lookups_open):
        from core.auth import create_access_token
        from core.mfa import mfa_manager
        name, user_id = _make_user("admin")
        first = mfa_manager.enroll_mfa(user_id, name)
        again = client.post("/v1/auth/mfa/enroll", json={
            "enrollment_token": create_access_token(f"mfa_enroll:{user_id}"),
        })
        assert again.status_code == 409
        assert mfa_manager._get_record(user_id).secret == first["secret"]

    def test_admin_route_does_not_replace_an_enrolment(self, client):
        from core.mfa import mfa_manager
        user_id = f"lh_{uuid.uuid4().hex[:10]}"
        body = {"user_id": user_id, "username": user_id}
        assert client.post("/v1/security/mfa/enroll", headers=API, json=body).status_code == 200
        secret = mfa_manager._get_record(user_id).secret
        assert client.post("/v1/security/mfa/enroll", headers=API, json=body).status_code == 409
        assert mfa_manager._get_record(user_id).secret == secret


# ═══════════════════════════════════════════════════════════════════════════════
# Step tokens, backup codes, attempt limit
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecondFactorStep:
    def _enrolled_user(self):
        from core.mfa import mfa_manager
        name, user_id = _make_user("admin")
        return name, user_id, mfa_manager.enroll_mfa(user_id, name)

    def test_step_tokens_are_not_access_tokens(self, client, token_lookups_open):
        from core.auth import create_access_token, decode_token
        _, user_id = _make_user()
        for prefix in ("pre_mfa:", "mfa_enroll:"):
            token = create_access_token(f"{prefix}{user_id}")
            assert decode_token(token) is not None  # a valid token, at its own endpoint
            assert client.get("/v1/auth/profile", headers=_bearer(token)).status_code == 401

    def test_backup_code_signs_in_once(self, client, token_lookups_open):
        name, _, enrolment = self._enrolled_user()
        code = enrolment["backup_codes"][0]

        first = client.post("/v1/auth/login/mfa", json={
            "pre_mfa_token": _login(client, name).json()["pre_mfa_token"], "backup_code": code,
        })
        assert first.status_code == 200
        assert first.json()["access_token"]

        reused = client.post("/v1/auth/login/mfa", json={
            "pre_mfa_token": _login(client, name).json()["pre_mfa_token"], "backup_code": code,
        })
        assert reused.status_code == 401

    def test_exactly_one_kind_of_code(self, client, token_lookups_open):
        name, _, enrolment = self._enrolled_user()
        pre = _login(client, name).json()["pre_mfa_token"]
        both = client.post("/v1/auth/login/mfa", json={
            "pre_mfa_token": pre, "totp_code": "123456", "backup_code": enrolment["backup_codes"][0],
        })
        assert both.status_code == 400
        neither = client.post("/v1/auth/login/mfa", json={"pre_mfa_token": pre})
        assert neither.status_code == 400

    def test_wrong_codes_lock_the_step(self, client, token_lookups_open):
        from core.mfa import MFAManager
        name, _, enrolment = self._enrolled_user()
        for _ in range(MFAManager.MAX_FAILED_CODES):
            wrong = client.post("/v1/auth/login/mfa", json={
                "pre_mfa_token": _login(client, name).json()["pre_mfa_token"], "totp_code": "000000",
            })
            assert wrong.status_code == 401
        # REM: A correct code is now refused as well, until the lockout window passes
        locked = client.post("/v1/auth/login/mfa", json={
            "pre_mfa_token": _login(client, name).json()["pre_mfa_token"],
            "totp_code": pyotp.TOTP(enrolment["secret"]).now(),
        })
        assert locked.status_code == 429


# ═══════════════════════════════════════════════════════════════════════════════
# Token rules
# ═══════════════════════════════════════════════════════════════════════════════

class TestTokenRules:
    def _signed(self, claims: dict) -> str:
        from datetime import datetime, timedelta, timezone

        import jwt

        from core.config import get_settings
        settings = get_settings()
        claims = {"exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
        return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def test_token_without_subject_is_refused(self, token_lookups_open):
        from core.auth import decode_token
        assert decode_token(self._signed({"jti": "jti_x"})) is None

    def test_token_without_id_is_refused(self, token_lookups_open):
        from core.auth import decode_token
        assert decode_token(self._signed({"sub": "someone"})) is None

    def test_non_ascii_key_is_refused_not_an_error(self):
        from core.auth import api_key_registry, constant_time_equal
        assert constant_time_equal("ключ", "key") is False
        assert api_key_registry.validate("ключ-ключ") is None

    def test_deactivated_account_token_is_refused(self, client, token_lookups_open):
        from core.auth import create_access_token
        from core.rbac import rbac_manager
        _, user_id = _make_user()
        token = create_access_token(user_id, ["view:dashboard"])
        assert client.get("/v1/auth/profile", headers=_bearer(token)).status_code == 200
        assert rbac_manager.deactivate_user(user_id, deactivated_by="test") is True
        assert client.get("/v1/auth/profile", headers=_bearer(token)).status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Ending existing logins (needs Redis: the cutoff is shared state)
# ═══════════════════════════════════════════════════════════════════════════════

@requires_redis
class TestEndingLogins:
    def test_logout_ends_every_token_of_the_account(self, client):
        name, _ = _make_user()
        token_a = _login(client, name).json()["access_token"]
        token_b = _login(client, name).json()["access_token"]
        assert client.get("/v1/auth/profile", headers=_bearer(token_b)).status_code == 200

        assert client.post("/v1/auth/logout", headers=_bearer(token_a)).status_code == 200
        assert client.get("/v1/auth/profile", headers=_bearer(token_a)).status_code == 401
        assert client.get("/v1/auth/profile", headers=_bearer(token_b)).status_code == 401

        # REM: A login made after the logout works
        token_c = _login(client, name).json()["access_token"]
        assert client.get("/v1/auth/profile", headers=_bearer(token_c)).status_code == 200

    def test_password_change_ends_existing_tokens(self, client):
        name, _ = _make_user()
        token_a = _login(client, name).json()["access_token"]
        token_b = _login(client, name).json()["access_token"]

        changed = client.post("/v1/auth/change-password", headers=_bearer(token_a), json={
            "old_password": PW, "new_password": "AnotherPassword456!",
        })
        assert changed.status_code == 200
        assert changed.json()["reauthentication_required"] is True
        assert client.get("/v1/auth/profile", headers=_bearer(token_a)).status_code == 401
        assert client.get("/v1/auth/profile", headers=_bearer(token_b)).status_code == 401

        assert _login(client, name).status_code == 401  # old password
        fresh = client.post("/v1/auth/login", json={"username": name, "password": "AnotherPassword456!"})
        assert fresh.status_code == 200

    def test_wrong_old_password_counts_toward_lockout(self, client):
        from core.user_management import MAX_FAILED_ATTEMPTS
        name, _ = _make_user()
        token = _login(client, name).json()["access_token"]
        for _ in range(MAX_FAILED_ATTEMPTS):
            resp = client.post("/v1/auth/change-password", headers=_bearer(token), json={
                "old_password": "NotThePassword999!", "new_password": "AnotherPassword456!",
            })
            assert resp.status_code == 400
        # REM: The correct old password is refused while the account is locked
        resp = client.post("/v1/auth/change-password", headers=_bearer(token), json={
            "old_password": PW, "new_password": "AnotherPassword456!",
        })
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Sign-in state shared between server processes (needs Redis)
# ═══════════════════════════════════════════════════════════════════════════════

@requires_redis
class TestSharedSignInState:
    """
    REM: Stand-in for a second server process: a second manager object that loaded its
    REM: state before the change was made through the first one.
    """

    def test_account_made_on_one_process_signs_in_on_another(self, client):
        from core.user_management import UserManager
        other = UserManager()
        name, _ = _make_user()
        assert other.authenticate_user(name, PW) is not None

    def test_password_change_reaches_the_other_process(self, client):
        from core.user_management import UserManager, user_manager
        name, user_id = _make_user()
        other = UserManager()
        assert other.authenticate_user(name, PW) is not None
        assert user_manager.change_password(user_id, PW, "AnotherPassword456!") is True
        assert other.authenticate_user(name, PW) is None
        assert other.authenticate_user(name, "AnotherPassword456!") is not None

    def test_enrolment_and_disable_reach_the_other_process(self, client):
        from core.mfa import MFAManager, mfa_manager
        other = MFAManager()
        user_id = f"lh_{uuid.uuid4().hex[:10]}"
        secret = mfa_manager.enroll_mfa(user_id, user_id)["secret"]
        assert other.is_enrolled(user_id) is True
        assert other.verify_mfa(user_id, pyotp.TOTP(secret).now()) is True
        assert mfa_manager.disable_mfa(user_id, disabled_by="test") is True
        assert other.is_enrolled(user_id) is False

    def test_failed_sign_ins_are_counted_across_processes(self, client):
        from core.user_management import (MAX_FAILED_ATTEMPTS, UserManager,
                                          user_manager)
        name, _ = _make_user()
        other = UserManager()
        for _ in range(MAX_FAILED_ATTEMPTS):
            assert user_manager.authenticate_user(name, "NotThePassword999!") is None
        # REM: The correct password is refused on the other process while the lockout holds
        assert other.authenticate_user(name, PW) is None
