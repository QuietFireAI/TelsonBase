# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
# TelsonBase/tests/test_hermes_agent.py
# REM: =======================================================================================
# REM: HERMES AGENT TESTS
# REM: =======================================================================================
# REM: Hermes is the operator's own agent and the reference "governed agent" on TelsonBase.
# REM: These tests lock in its security posture, especially that cross-agent dispatch PAUSES
# REM: for human approval (VULN-BASE-01 regression) and cannot be skipped by casing.
# REM: =======================================================================================

from unittest.mock import MagicMock, patch

import pytest

from agents.base import AgentRequest
from agents.hermes_agent import HermesAgent, get_hermes
from core.approval import approval_gate, ApprovalStatus
from core.trust_levels import AgentTrustLevel


@pytest.fixture
def hermes(mocker):
    mocker.patch("toolroom.registry._get_store", return_value=None)
    h = HermesAgent()
    try:
        h.register()
    except Exception:
        pass
    return h


class TestHermesBasics:
    def test_construct_without_llm(self):
        """REM: Hermes must be constructable even if Ollama is down (lazy handle)."""
        h = HermesAgent()
        assert h.agent_name == "hermes_agent"
        assert h._service is None

    def test_singleton(self):
        assert get_hermes() is get_hermes()

    def test_starts_at_probation(self):
        """REM: Earned trust — Hermes starts at PROBATION, never RESIDENT."""
        assert HermesAgent.INITIAL_TRUST_LEVEL == AgentTrustLevel.PROBATION

    def test_no_direct_external_capability(self):
        """REM: Sovereign by design — no direct external network capability."""
        assert "external.none" in HermesAgent.CAPABILITIES
        assert not any(c.startswith("external.read") or c.startswith("external.write")
                       for c in HermesAgent.CAPABILITIES)

    def test_dispatch_in_requires_approval(self):
        assert "dispatch" in HermesAgent.REQUIRES_APPROVAL_FOR


class TestHermesAsk:
    def test_ask_missing_prompt(self, hermes):
        result = hermes._ask({})
        assert "Excuse_Me" in result["qms"]

    def test_ask_calls_local_llm(self, hermes):
        fake = MagicMock()
        fake.generate.return_value = {"response": "hello from local", "model": "llama3"}
        hermes._service = fake
        result = hermes._ask({"prompt": "hi"})
        assert result["response"] == "hello from local"
        assert "Thank_You" in result["qms"]
        fake.generate.assert_called_once()

    def test_ask_llm_error_is_graceful(self, hermes):
        fake = MagicMock()
        fake.generate.side_effect = RuntimeError("ollama down")
        hermes._service = fake
        result = hermes._ask({"prompt": "hi"})
        assert "Thank_You_But_No" in result["qms"]
        assert "ollama down" in result["error"]


class TestHermesDispatchGate:
    """REM: VULN-BASE-01 regression — dispatch MUST pause for human approval, and the
    gate MUST NOT be skippable by changing the action's letter casing."""

    def _reject_wait(self, request_id, timeout=None):
        r = approval_gate._pending_requests.get(request_id)
        if r:
            r.status = ApprovalStatus.REJECTED
        return r

    @pytest.mark.parametrize("action", ["dispatch", "Dispatch", "DISPATCH"])
    def test_dispatch_pauses_and_denies_without_approval(self, hermes, action):
        req = AgentRequest(
            request_id=f"req-{action}", agent_name="hermes_agent", requester="operator",
            action=action,
            payload={"target_agent": "backup_agent", "target_action": "delete_all"},
        )
        with patch.object(approval_gate, "wait_for_decision", side_effect=self._reject_wait):
            resp = hermes.handle_request(req)
        assert resp.success is False
        assert resp.approval_required is True

    def test_dispatch_missing_target_is_rejected(self, hermes):
        result = hermes._dispatch({})
        assert "Excuse_Me" in result["qms"]


class TestHermesStatus:
    def test_status_reports_governance(self, hermes):
        result = hermes._status()
        assert result["agent_name"] == "hermes_agent"
        assert "trust_level" in result
        assert "Thank_You" in result["qms"]
