# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_agents_base_depth.py
# REM: Depth tests for agents/base.py — AgentRequest/AgentResponse Pydantic models

import sys
from unittest.mock import MagicMock

# REM: celery not installed locally — use identity decorator so task functions remain callable
if "celery" not in sys.modules:
    celery_mock = MagicMock()
    celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = celery_mock

import pytest
from datetime import datetime, timezone

from agents.base import AgentRequest, AgentResponse


# ═══════════════════════════════════════════════════════════════════════════════
# AgentRequest model
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentRequest:
    def test_requires_action(self):
        with pytest.raises(Exception):
            AgentRequest()  # no action → validation error

    def test_minimal_construction(self):
        r = AgentRequest(action="read_file")
        assert r.action == "read_file"

    def test_request_id_generated(self):
        r = AgentRequest(action="do_thing")
        assert r.request_id is not None
        assert len(r.request_id) > 0

    def test_request_id_unique(self):
        r1 = AgentRequest(action="x")
        r2 = AgentRequest(action="x")
        assert r1.request_id != r2.request_id

    def test_request_id_is_uuid_format(self):
        import uuid
        r = AgentRequest(action="x")
        # Should not raise
        uuid.UUID(r.request_id)

    def test_default_payload_empty_dict(self):
        r = AgentRequest(action="x")
        assert r.payload == {}

    def test_default_requester_system(self):
        r = AgentRequest(action="x")
        assert r.requester == "system"

    def test_default_priority_normal(self):
        r = AgentRequest(action="x")
        assert r.priority == "normal"

    def test_default_signed_message_none(self):
        r = AgentRequest(action="x")
        assert r.signed_message is None

    def test_timestamp_is_datetime(self):
        r = AgentRequest(action="x")
        assert isinstance(r.timestamp, datetime)

    def test_custom_action(self):
        r = AgentRequest(action="analyze_threat")
        assert r.action == "analyze_threat"

    def test_custom_payload(self):
        r = AgentRequest(action="x", payload={"key": "value"})
        assert r.payload["key"] == "value"

    def test_custom_requester(self):
        r = AgentRequest(action="x", requester="agent_alpha")
        assert r.requester == "agent_alpha"

    def test_high_priority(self):
        r = AgentRequest(action="x", priority="high")
        assert r.priority == "high"

    def test_explicit_request_id(self):
        r = AgentRequest(action="x", request_id="my-custom-id")
        assert r.request_id == "my-custom-id"


# ═══════════════════════════════════════════════════════════════════════════════
# AgentResponse model
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentResponse:
    def _make_response(self, **kwargs) -> AgentResponse:
        defaults = dict(
            request_id="req-1",
            agent_name="test_agent",
            success=True,
            qms_status="Thank_You",
        )
        defaults.update(kwargs)
        return AgentResponse(**defaults)

    def test_minimal_construction(self):
        r = self._make_response()
        assert r.request_id == "req-1"
        assert r.agent_name == "test_agent"
        assert r.success is True
        assert r.qms_status == "Thank_You"

    def test_default_result_none(self):
        r = self._make_response()
        assert r.result is None

    def test_default_error_none(self):
        r = self._make_response()
        assert r.error is None

    def test_default_anomalies_empty(self):
        r = self._make_response()
        assert r.anomalies_detected == []

    def test_default_approval_required_false(self):
        r = self._make_response()
        assert r.approval_required is False

    def test_default_approval_id_none(self):
        r = self._make_response()
        assert r.approval_id is None

    def test_timestamp_is_datetime(self):
        r = self._make_response()
        assert isinstance(r.timestamp, datetime)

    def test_success_false(self):
        r = self._make_response(success=False, qms_status="Thank_You_But_No")
        assert r.success is False

    def test_error_stored(self):
        r = self._make_response(success=False, qms_status="Thank_You_But_No",
                                error="Permission denied")
        assert r.error == "Permission denied"

    def test_result_stored(self):
        r = self._make_response(result={"data": [1, 2, 3]})
        assert r.result == {"data": [1, 2, 3]}

    def test_anomalies_stored(self):
        r = self._make_response(anomalies_detected=["anom-001", "anom-002"])
        assert len(r.anomalies_detected) == 2
        assert "anom-001" in r.anomalies_detected

    def test_approval_required_true(self):
        r = self._make_response(approval_required=True, approval_id="appr-xyz")
        assert r.approval_required is True
        assert r.approval_id == "appr-xyz"

    def test_thank_you_qms_status(self):
        r = self._make_response(qms_status="Thank_You")
        assert "Thank_You" in r.qms_status

    def test_thank_you_but_no_qms_status(self):
        r = self._make_response(qms_status="Thank_You_But_No")
        assert "Thank_You_But_No" in r.qms_status
