# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
"""
REM: Adversarial security tests — TelsonBase.
REM: These tests attack the platform the way an adversary would, not the way a
REM: well-behaved caller does. They assert the security boundary holds under:
REM:   - forged signatures
REM:   - replay attacks (duplicate message IDs)
REM:   - expired-message replay (outside the window)
REM:   - cross-agent key confusion
REM:   - revoked-agent re-registration
REM:   - tampered payloads
REM:   - Telegram HITL forgery (the bug the audit found)
REM: Added 2026-06-12 as part of pre-launch adversarial hardening.
"""
import uuid
import hmac
import hashlib
from datetime import datetime, timezone, timedelta

import pytest

from core.signing import (
    SignedAgentMessage,
    AgentKeyRegistry,
    MessageSigner,
    REPLAY_WINDOW_SECONDS,
)


def _fresh_registry_with_agent(agent_id="agent_attacker_target"):
    reg = AgentKeyRegistry()
    key = reg.register_agent(agent_id)
    signer = MessageSigner(agent_id, key)
    return reg, signer, agent_id, key


class TestSignatureForgery:
    """REM: An attacker who does not hold the secret key must not pass verification."""

    def test_forged_signature_rejected(self):
        reg, signer, agent_id, _ = _fresh_registry_with_agent()
        msg = signer.sign(action="payment_send", payload={"amount": 1000000})
        # REM: Attacker overwrites the signature with a guess.
        forged = msg.model_copy(update={"signature": "deadbeef" * 8})
        ok, reason = reg.verify_message(forged)
        assert ok is False
        assert "signature" in reason.lower()

    def test_wrong_key_signature_rejected(self):
        reg, _, agent_id, _ = _fresh_registry_with_agent()
        # REM: Attacker signs with a key they chose, not the registered one.
        attacker_key = b"attacker-controlled-key-not-registered"
        evil_signer = MessageSigner(agent_id, attacker_key)
        msg = evil_signer.sign(action="file_delete", payload={"path": "/data"})
        ok, reason = reg.verify_message(msg)
        assert ok is False
        assert "signature" in reason.lower()

    def test_tampered_payload_after_signing_rejected(self):
        """REM: Signature must cover the payload — flipping it post-sign must fail."""
        reg, signer, _, _ = _fresh_registry_with_agent()
        msg = signer.sign(action="payment_send", payload={"amount": 10})
        # REM: Attacker intercepts and raises the amount, keeps the old signature.
        tampered = msg.model_copy(update={"payload": {"amount": 10_000_000}})
        ok, reason = reg.verify_message(tampered)
        assert ok is False
        assert "signature" in reason.lower()


class TestReplayProtection:
    """REM: A captured valid message must not be replayable."""

    def test_duplicate_message_id_rejected(self):
        reg, signer, _, _ = _fresh_registry_with_agent()
        msg = signer.sign(action="file_read", payload={"path": "/x"})
        ok1, _ = reg.verify_message(msg)
        assert ok1 is True
        # REM: Replay the exact same signed message.
        ok2, reason = reg.verify_message(msg)
        assert ok2 is False
        assert "replay" in reason.lower() or "seen" in reason.lower()

    def test_expired_message_rejected(self):
        reg, _, agent_id, key = _fresh_registry_with_agent()
        # REM: Build a correctly-signed but stale message (outside the window).
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=REPLAY_WINDOW_SECONDS + 60)
        msg = SignedAgentMessage(
            message_id=str(uuid.uuid4()),
            agent_id=agent_id,
            timestamp=old_ts,
            action="file_read",
            payload={},
            signature="placeholder",
        )
        good_sig = hmac.new(key, msg.get_signing_payload().encode("utf-8"), hashlib.sha256).hexdigest()
        signed_old = msg.model_copy(update={"signature": good_sig})
        ok, reason = reg.verify_message(signed_old)
        assert ok is False
        assert "expired" in reason.lower()


class TestAgentIdentityBoundary:
    """REM: Identity controls must not be bypassable by re-registration or unknown IDs."""

    def test_unknown_agent_rejected(self):
        reg = AgentKeyRegistry()
        # REM: Message from an agent that was never registered.
        stray = SignedAgentMessage(
            message_id=str(uuid.uuid4()),
            agent_id="ghost_agent",
            action="file_read",
            payload={},
            signature="whatever",
        )
        ok, reason = reg.verify_message(stray)
        assert ok is False
        assert "unknown" in reason.lower()

    def test_revoked_agent_cannot_reregister(self):
        reg = AgentKeyRegistry()
        reg.register_agent("doomed_agent")
        reg.revoke_agent("doomed_agent")
        # REM: A revoked agent must not be silently re-admitted.
        with pytest.raises(PermissionError):
            reg.register_agent("doomed_agent")

    def test_revoked_agent_messages_rejected(self):
        reg, signer, agent_id, _ = _fresh_registry_with_agent("revoke_me")
        msg = signer.sign(action="file_read", payload={})
        reg.revoke_agent(agent_id)
        ok, reason = reg.verify_message(msg)
        assert ok is False
        assert "revoked" in reason.lower()


class TestTelegramHITLForgery:
    """
    REM: Regression test for the auth-bypass the 2026-06-12 audit found and fixed.
    REM: The HITL approval webhook must reject inbound updates that are not from
    REM: the configured admin chat, and must validate the secret token.
    """

    def _gateway(self, secret="s3cr3t", chat="999"):
        from core.telegram_gateway import TelegramGateway
        gw = TelegramGateway()
        gw.configure(token="t", chat_id=chat, webhook_secret=secret)
        return gw

    def test_secret_token_required_constant_time(self):
        gw = self._gateway(secret="correct-secret")
        assert gw.verify_webhook_secret("correct-secret") is True
        assert gw.verify_webhook_secret("wrong-secret") is False
        assert gw.verify_webhook_secret("") is False

    def test_inbound_from_wrong_chat_rejected(self):
        gw = self._gateway(chat="999")
        # REM: Forged callback_query from an attacker chat must not be authorized.
        assert gw._is_authorized_sender("12345") is False
        assert gw._is_authorized_sender("999") is True

    def test_forged_approval_does_not_reach_gate(self, monkeypatch):
        """REM: A callback_query from an unauthorized chat must be dropped before
        REM: approval_gate.approve is ever called."""
        gw = self._gateway(chat="999")
        called = {"approve": False}

        import core.approval as approval_mod
        monkeypatch.setattr(
            approval_mod.approval_gate, "approve",
            lambda *a, **k: called.__setitem__("approve", True) or True,
        )
        # REM: Attacker forges an approve tap from chat 12345 (not the admin 999).
        forged_update = {
            "callback_query": {
                "id": "cb1",
                "data": "approve:some-request-id",
                "from": {"username": "attacker"},
                "message": {"message_id": 1, "chat": {"id": 12345}},
            }
        }
        gw.handle_update(forged_update)
        assert called["approve"] is False, "Forged approval reached the HITL gate"


class TestToolNameTraversal:
    """REM: Regression for the 2026-06-12 CodeQL path-injection finding.
    REM: Tool names flow into filesystem paths; traversal must be rejected at validation."""

    def _manifest(self, name):
        from toolroom.manifest import ToolManifest
        return ToolManifest(name=name, entry_point="python main.py", version="1.0.0")

    def test_traversal_name_rejected(self):
        from toolroom.manifest import validate_manifest
        for evil in ["../escape", "a/b", "..\\win", "tool/../../etc"]:
            errors = validate_manifest(self._manifest(evil))
            assert any("traversal" in e or "separator" in e for e in errors), f"accepted {evil!r}"

    def test_legitimate_name_with_space_ok(self):
        from toolroom.manifest import validate_manifest
        # REM: Spaces are legitimate; the fix must not break normal names.
        errors = validate_manifest(self._manifest("Test Tool"))
        assert not any("separator" in e or "traversal" in e for e in errors)
