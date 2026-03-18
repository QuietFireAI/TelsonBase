# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_agents_demo_depth.py
# REM: Depth coverage for agents/demo_agent.py
# REM: Constants and health task are pure. Store-backed tasks use mock _get_stores().

import sys
from unittest.mock import MagicMock, patch

if "celery" not in sys.modules:
    celery_mock = MagicMock()
    celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = celery_mock

import pytest

import agents.demo_agent as demo_mod
from agents.demo_agent import (
    AGENT_NAME,
    AGENT_VERSION,
    CAPABILITIES,
    REQUIRES_APPROVAL_FOR,
    check_approval_status,
    flag_anomaly,
    health,
    record_behavior,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestDemoAgentConstants:
    def test_agent_name(self):
        assert AGENT_NAME == "demo_agent"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_capabilities_is_list(self):
        assert isinstance(CAPABILITIES, list)
        assert len(CAPABILITIES) > 0

    def test_capabilities_has_filesystem_read(self):
        assert any("filesystem.read" in c for c in CAPABILITIES)

    def test_capabilities_has_filesystem_write(self):
        assert any("filesystem.write" in c for c in CAPABILITIES)

    def test_requires_approval_for_list(self):
        assert isinstance(REQUIRES_APPROVAL_FOR, list)
        assert "delete_file" in REQUIRES_APPROVAL_FOR
        assert "bulk_process" in REQUIRES_APPROVAL_FOR


# ═══════════════════════════════════════════════════════════════════════════════
# health task — pure, no external deps
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthTask:
    def test_health_returns_agent_name(self):
        result = health()
        assert result["agent"] == "demo_agent"

    def test_health_returns_version(self):
        result = health()
        assert result["version"] == "1.0.0"

    def test_health_status_healthy(self):
        result = health()
        assert result["status"] == "healthy"

    def test_health_has_capabilities(self):
        result = health()
        assert isinstance(result["capabilities"], list)

    def test_health_has_requires_approval(self):
        result = health()
        assert isinstance(result["requires_approval_for"], list)

    def test_health_qms_status(self):
        result = health()
        assert result["qms_status"] == "Thank_You"


# ═══════════════════════════════════════════════════════════════════════════════
# Fixture: mock _get_stores() to return in-memory fakes
# ═══════════════════════════════════════════════════════════════════════════════

def _make_stores(capabilities=None, approval_status="pending"):
    """Build a mock stores dict matching what _get_stores() returns."""
    anomaly_store = MagicMock()
    anomaly_store.get_baseline.return_value = None
    anomaly_store.store_baseline.return_value = True
    anomaly_store.store_anomaly.return_value = True

    capability_store = MagicMock()
    capability_store.get_capabilities.return_value = capabilities
    capability_store.store_capabilities.return_value = True

    signing_store = MagicMock()
    signing_store.store_key.return_value = True

    approval_store = MagicMock()
    approval_store.get_request.return_value = {
        "status": approval_status,
        "decided_by": "admin",
        "decided_at": "2026-01-01T00:00:00+00:00",
        "decision_notes": "approved by admin",
    } if approval_status != "not_found" else None
    approval_store.store_request.return_value = True

    return {
        "signing_store": signing_store,
        "capability_store": capability_store,
        "anomaly_store": anomaly_store,
        "approval_store": approval_store,
        "AgentKeyRegistry": MagicMock(),
        "MessageSigner": MagicMock(),
        "CapabilityEnforcer": MagicMock(),
        "ResourceType": MagicMock(),
        "ActionType": MagicMock(),
        "BehaviorMonitor": MagicMock(),
        "AnomalyType": MagicMock(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# check_approval_status
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckApprovalStatus:
    def test_not_found_returns_not_found(self):
        stores = _make_stores(approval_status="not_found")
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = check_approval_status("req-001")
        assert result["status"] == "not_found"

    def test_approved_status(self):
        stores = _make_stores(approval_status="approved")
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = check_approval_status("req-002")
        assert result["status"] == "approved"

    def test_pending_status(self):
        stores = _make_stores(approval_status="pending")
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = check_approval_status("req-003")
        assert result["status"] == "pending"

    def test_has_decided_by(self):
        stores = _make_stores(approval_status="approved")
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = check_approval_status("req-004")
        assert result["decided_by"] == "admin"

    def test_has_notes(self):
        stores = _make_stores(approval_status="approved")
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = check_approval_status("req-005")
        assert result["notes"] == "approved by admin"


# ═══════════════════════════════════════════════════════════════════════════════
# record_behavior
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecordBehavior:
    def test_record_success_updates_baseline(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            record_behavior("read_file", "/app/demo/input/test.txt", True)
        stores["anomaly_store"].store_baseline.assert_called_once()

    def test_record_failure_increments_error_count(self):
        stores = _make_stores()
        captured = {}

        def capture_store(agent_id, baseline):
            captured["baseline"] = baseline
            return True

        stores["anomaly_store"].store_baseline.side_effect = capture_store

        with patch.object(demo_mod, "_get_stores", return_value=stores):
            record_behavior("read_file", "/app/demo/input/test.txt", False)

        assert captured["baseline"]["error_count"] == 1

    def test_record_existing_baseline_increments_count(self):
        stores = _make_stores()
        stores["anomaly_store"].get_baseline.return_value = {
            "observation_count": 5,
            "known_actions": ["read_file"],
            "known_resources": [],
            "action_counts": {"read_file": 5},
            "error_count": 0,
        }
        captured = {}

        def capture_store(agent_id, baseline):
            captured["baseline"] = baseline
            return True

        stores["anomaly_store"].store_baseline.side_effect = capture_store

        with patch.object(demo_mod, "_get_stores", return_value=stores):
            record_behavior("read_file", "/app/demo/input/new.txt", True)

        assert captured["baseline"]["observation_count"] == 6

    def test_record_new_action_adds_to_known_actions(self):
        stores = _make_stores()
        stores["anomaly_store"].get_baseline.return_value = {
            "observation_count": 0,
            "known_actions": [],
            "known_resources": [],
            "action_counts": {},
            "error_count": 0,
        }
        captured = {}

        def capture_store(agent_id, baseline):
            captured["baseline"] = baseline
            return True

        stores["anomaly_store"].store_baseline.side_effect = capture_store

        with patch.object(demo_mod, "_get_stores", return_value=stores):
            record_behavior("new_action", "/some/path", True)

        assert "new_action" in captured["baseline"]["known_actions"]


# ═══════════════════════════════════════════════════════════════════════════════
# flag_anomaly
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlagAnomaly:
    def test_flag_anomaly_returns_anomaly_id(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = flag_anomaly("capability_probe", "test description",
                                  {"path": "/test"}, "medium")
        assert result.startswith("ANOM-")

    def test_flag_anomaly_stores_anomaly(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            flag_anomaly("rate_spike", "too many requests", {}, "high")
        stores["anomaly_store"].store_anomaly.assert_called_once()

    def test_flag_anomaly_requires_human_review_for_high(self):
        stores = _make_stores()
        captured = {}

        def capture(anomaly):
            captured["anomaly"] = anomaly
            return True

        stores["anomaly_store"].store_anomaly.side_effect = capture

        with patch.object(demo_mod, "_get_stores", return_value=stores):
            flag_anomaly("test", "desc", {}, "high")

        assert captured["anomaly"]["requires_human_review"] is True

    def test_flag_anomaly_medium_not_requires_review(self):
        stores = _make_stores()
        captured = {}

        def capture(anomaly):
            captured["anomaly"] = anomaly
            return True

        stores["anomaly_store"].store_anomaly.side_effect = capture

        with patch.object(demo_mod, "_get_stores", return_value=stores):
            flag_anomaly("test", "desc", {}, "medium")

        assert captured["anomaly"]["requires_human_review"] is False

    def test_flag_anomaly_critical_requires_review(self):
        stores = _make_stores()
        captured = {}

        def capture(anomaly):
            captured["anomaly"] = anomaly
            return True

        stores["anomaly_store"].store_anomaly.side_effect = capture

        with patch.object(demo_mod, "_get_stores", return_value=stores):
            flag_anomaly("test", "desc", {}, "critical")

        assert captured["anomaly"]["requires_human_review"] is True

    def test_flag_anomaly_resolved_false(self):
        stores = _make_stores()
        captured = {}

        def capture(anomaly):
            captured["anomaly"] = anomaly
            return True

        stores["anomaly_store"].store_anomaly.side_effect = capture

        with patch.object(demo_mod, "_get_stores", return_value=stores):
            flag_anomaly("test", "desc", {})

        assert captured["anomaly"]["resolved"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# check_capability
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckCapability:
    def test_no_registered_caps_returns_false(self):
        stores = _make_stores(capabilities=None)
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = demo_mod.check_capability("filesystem", "read", "/app/demo/input/f.txt")
        assert result is False

    def test_none_capabilities_returns_false(self):
        # Alias of the above — reinforces that None caps → False regardless of path
        stores = _make_stores(capabilities=None)
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = demo_mod.check_capability("filesystem", "write", "/app/demo/output/f.txt")
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# register_agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegisterAgent:
    def test_register_agent_returns_true(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = demo_mod.register_agent()
        assert result is True

    def test_register_agent_stores_key(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            demo_mod.register_agent()
        from unittest.mock import ANY
        stores["signing_store"].store_key.assert_called_once_with("demo_agent", ANY)

    def test_register_agent_stores_capabilities(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            demo_mod.register_agent()
        stores["capability_store"].store_capabilities.assert_called_once_with(
            "demo_agent", CAPABILITIES
        )


# ═══════════════════════════════════════════════════════════════════════════════
# request_approval
# ═══════════════════════════════════════════════════════════════════════════════

class TestRequestApproval:
    def test_returns_request_id(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            req_id = demo_mod.request_approval("delete_file", "Delete test", {"filepath": "/test"})
        assert req_id.startswith("APPR-")

    def test_stores_request(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            demo_mod.request_approval("delete_file", "Delete test", {"filepath": "/test"})
        stores["approval_store"].store_request.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# list_files task — capability-denied path
# ═══════════════════════════════════════════════════════════════════════════════

class TestListFilesTask:
    def test_unauthorized_path_returns_denied(self):
        stores = _make_stores(capabilities=[])
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            with patch("agents.demo_agent.check_capability", return_value=False):
                result = demo_mod.list_files("/etc")
        assert result["success"] is False
        assert result["qms_status"] == "Thank_You_But_No"


# ═══════════════════════════════════════════════════════════════════════════════
# delete_file task — approval flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeleteFileTask:
    def test_no_approval_creates_request(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = demo_mod.delete_file("/app/demo/input/test.txt")
        assert result["success"] is False
        assert "approval_id" in result
        assert result["qms_status"] == "Excuse_Me"

    def test_approved_request_proceeds(self):
        stores = _make_stores(approval_status="approved")
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            with patch("agents.demo_agent.check_capability", return_value=False):
                result = demo_mod.delete_file("/app/demo/input/test.txt",
                                              approval_id="APPR-TEST01")
        # Approval verified but capability check still runs
        assert result is not None

    def test_rejected_approval_returns_error(self):
        stores = _make_stores(approval_status="rejected")
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = demo_mod.delete_file("/app/demo/input/test.txt",
                                          approval_id="APPR-REJECT01")
        assert result["success"] is False
        assert result["qms_status"] == "Thank_You_But_No"

    def test_pending_approval_returns_excuse_me(self):
        stores = _make_stores(approval_status="pending")
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = demo_mod.delete_file("/app/demo/input/test.txt",
                                          approval_id="APPR-PENDING01")
        assert result["success"] is False
        assert result["qms_status"] == "Excuse_Me"

    def test_invalid_approval_returns_error(self):
        stores = _make_stores(approval_status="unknown_status")
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            result = demo_mod.delete_file("/app/demo/input/test.txt",
                                          approval_id="APPR-INVALID01")
        assert result["success"] is False
        assert result["qms_status"] == "Thank_You_But_No"


# ═══════════════════════════════════════════════════════════════════════════════
# attempt_unauthorized task
# ═══════════════════════════════════════════════════════════════════════════════

class TestAttemptUnauthorizedTask:
    def test_denied_returns_expected_failure(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            with patch("agents.demo_agent.check_capability", return_value=False):
                result = demo_mod.attempt_unauthorized("/etc/passwd")
        assert result["success"] is False
        assert result["qms_status"] == "Thank_You_But_No"
        assert "blocked" in result["message"].lower() or "denied" in result["error"].lower()

    def test_allowed_returns_security_warning(self):
        stores = _make_stores()
        with patch.object(demo_mod, "_get_stores", return_value=stores):
            with patch("agents.demo_agent.check_capability", return_value=True):
                with patch("agents.demo_agent.flag_anomaly", return_value="ANOM-001"):
                    result = demo_mod.attempt_unauthorized("/etc/passwd")
        assert result["success"] is True
        assert "SECURITY" in result.get("warning", "")
