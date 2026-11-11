# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
# TelsonBase/tests/test_hermes_routes.py
# REM: =======================================================================================
# REM: HERMES OPERATIONAL API TESTS
# REM: =======================================================================================
# REM: Verifies the runnable Hermes surface: ask (local LLM, no gate), dispatch (HITL pause,
# REM: 202 + approval id, sends nothing), dispatch/execute (refuses without approval),
# REM: status. This is the reference "governed agent is operational" contract.
# REM: =======================================================================================

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def hermes_singleton(mocker):
    mocker.patch("toolroom.registry._get_store", return_value=None)
    from agents.hermes_agent import get_hermes
    h = get_hermes()
    try:
        h.register()
    except Exception:
        pass
    return h


class TestHermesRoutes:
    def test_status_endpoint(self, client, auth_headers, hermes_singleton):
        r = client.get("/v1/agents/hermes/status", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["agent_name"] == "hermes_agent"

    def test_ask_endpoint(self, client, auth_headers, hermes_singleton):
        fake = MagicMock()
        fake.generate.return_value = {"response": "sovereign hello", "model": "llama3"}
        hermes_singleton._service = fake
        r = client.post("/v1/agents/hermes/ask",
                        headers=auth_headers, json={"prompt": "hi"})
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert "sovereign hello" in r.json()["result"]["response"]

    def test_dispatch_pauses_and_sends_nothing(self, client, auth_headers, hermes_singleton):
        """REM: dispatch must return 202 pending_approval and NOT send anything."""
        with patch.object(hermes_singleton, "_dispatch") as sent:
            r = client.post("/v1/agents/hermes/dispatch", headers=auth_headers,
                            json={"target_agent": "backup_agent",
                                  "target_action": "delete_all"})
            assert r.status_code == 202
            body = r.json()
            assert body["status"] == "pending_approval"
            assert body["approval_request_id"].startswith("APPR-")
            sent.assert_not_called()  # nothing dispatched without approval

    def test_dispatch_execute_without_approval_rejected(self, client, auth_headers, hermes_singleton):
        r = client.post("/v1/agents/hermes/dispatch/execute", headers=auth_headers,
                        json={"approval_request_id": "APPR-doesnotexist",
                              "target_agent": "backup_agent",
                              "target_action": "delete_all"})
        assert r.status_code == 200
        assert r.json()["status"] == "error"
        assert "approval_not_found" in r.json()["qms"]

    def test_dispatch_missing_target_rejected(self, client, auth_headers, hermes_singleton):
        r = client.post("/v1/agents/hermes/dispatch", headers=auth_headers,
                        json={"target_agent": "", "target_action": ""})
        # Pydantic min_length rejects empty -> 422
        assert r.status_code == 422
