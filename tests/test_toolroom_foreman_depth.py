# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_toolroom_foreman_depth.py
# REM: Depth tests for toolroom/foreman.py — constants, source validation, trust logic

import sys
from unittest.mock import MagicMock

# REM: celery not installed locally — identity decorator keeps task functions callable
if "celery" not in sys.modules:
    celery_mock = MagicMock()
    celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = celery_mock

import pytest

from toolroom.foreman import (
    FOREMAN_AGENT_ID,
    CAPABILITIES,
    REQUIRES_APPROVAL_FOR,
    DEFAULT_GITHUB_SOURCES,
    _SOURCES_REDIS_KEY,
    APPROVED_GITHUB_SOURCES,
    ForemanAgent,
)
from core.trust_levels import AgentTrustLevel


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestForemanConstants:
    def test_foreman_agent_id(self):
        assert FOREMAN_AGENT_ID == "foreman_agent"

    def test_capabilities_is_list(self):
        assert isinstance(CAPABILITIES, list)

    def test_capabilities_nonempty(self):
        assert len(CAPABILITIES) > 0

    def test_capabilities_has_filesystem_read(self):
        assert any("filesystem.read" in c for c in CAPABILITIES)

    def test_capabilities_has_filesystem_write(self):
        assert any("filesystem.write" in c for c in CAPABILITIES)

    def test_capabilities_has_github_access(self):
        assert any("github.com" in c for c in CAPABILITIES)

    def test_capabilities_has_redis(self):
        assert any("redis" in c for c in CAPABILITIES)

    def test_requires_approval_for_is_list(self):
        assert isinstance(REQUIRES_APPROVAL_FOR, list)

    def test_requires_approval_has_install(self):
        assert "install_tool_from_github" in REQUIRES_APPROVAL_FOR

    def test_requires_approval_has_update(self):
        assert "update_tool_from_github" in REQUIRES_APPROVAL_FOR

    def test_requires_approval_has_quarantine(self):
        assert "quarantine_tool" in REQUIRES_APPROVAL_FOR

    def test_requires_approval_has_delete(self):
        assert "delete_tool" in REQUIRES_APPROVAL_FOR

    def test_requires_approval_has_api_access(self):
        assert "enable_api_access_for_tool" in REQUIRES_APPROVAL_FOR

    def test_default_github_sources_is_list(self):
        assert isinstance(DEFAULT_GITHUB_SOURCES, list)

    def test_default_github_sources_nonempty(self):
        assert len(DEFAULT_GITHUB_SOURCES) > 0

    def test_default_sources_has_jq(self):
        assert "jqlang/jq" in DEFAULT_GITHUB_SOURCES

    def test_sources_redis_key(self):
        assert _SOURCES_REDIS_KEY == "toolroom:approved_sources"

    def test_approved_sources_is_list(self):
        assert isinstance(APPROVED_GITHUB_SOURCES, list)


# ═══════════════════════════════════════════════════════════════════════════════
# ForemanAgent.add_approved_source — repo format validation (pure Python)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def foreman():
    """Minimal ForemanAgent bypassing __init__ (avoids Redis/registry)."""
    f = object.__new__(ForemanAgent)
    f.agent_id = FOREMAN_AGENT_ID
    return f


class TestAddApprovedSourceValidation:
    def test_valid_format_creates_approval_request(self, foreman, monkeypatch):
        mock_gate = MagicMock()
        mock_request = MagicMock()
        mock_request.request_id = "appr-123"
        mock_gate.create_request.return_value = mock_request
        monkeypatch.setattr("toolroom.foreman.approval_gate", mock_gate)
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["other/repo"])
        result = foreman.add_approved_source("owner/repo")
        assert result["status"] == "pending_approval"

    def test_invalid_format_no_slash_returns_error(self, foreman):
        result = foreman.add_approved_source("noslash")
        assert result["status"] == "error"
        assert "invalid" in result["message"].lower() or "format" in result["message"].lower()

    def test_invalid_format_three_parts_returns_error(self, foreman):
        result = foreman.add_approved_source("too/many/parts")
        assert result["status"] == "error"

    def test_empty_string_returns_error(self, foreman):
        result = foreman.add_approved_source("")
        assert result["status"] == "error"

    def test_already_approved_returns_error(self, foreman, monkeypatch):
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["jqlang/jq"])
        result = foreman.add_approved_source("jqlang/jq")
        assert result["status"] == "error"
        assert "already" in result["message"].lower()

    def test_normalizes_to_lowercase(self, foreman, monkeypatch):
        mock_gate = MagicMock()
        mock_request = MagicMock()
        mock_request.request_id = "appr-001"
        mock_gate.create_request.return_value = mock_request
        monkeypatch.setattr("toolroom.foreman.approval_gate", mock_gate)
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", [])
        result = foreman.add_approved_source("Owner/Repo")
        # Should normalize to lowercase and succeed (pending_approval)
        assert result["status"] == "pending_approval"
        assert "owner/repo" in result["qms"].lower() or "owner/repo" in result.get("message", "").lower()

    def test_strips_whitespace(self, foreman, monkeypatch):
        mock_gate = MagicMock()
        mock_request = MagicMock()
        mock_request.request_id = "appr-002"
        mock_gate.create_request.return_value = mock_request
        monkeypatch.setattr("toolroom.foreman.approval_gate", mock_gate)
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", [])
        result = foreman.add_approved_source("  owner/repo  ")
        assert result["status"] == "pending_approval"


# ═══════════════════════════════════════════════════════════════════════════════
# Trust level comparison logic (extracted from handle_checkout_request)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrustHierarchy:
    """REM: Test the trust level ordering and index logic used in checkout auth."""

    # REM: The same _trust_hierarchy is built inline in handle_checkout_request
    _hierarchy = [
        AgentTrustLevel.QUARANTINE,
        AgentTrustLevel.PROBATION,
        AgentTrustLevel.RESIDENT,
        AgentTrustLevel.CITIZEN,
        AgentTrustLevel.AGENT,
    ]
    _values = [lvl.value for lvl in _hierarchy]

    def test_quarantine_is_index_0(self):
        assert self._values.index("quarantine") == 0

    def test_probation_is_index_1(self):
        assert self._values.index("probation") == 1

    def test_resident_is_index_2(self):
        assert self._values.index("resident") == 2

    def test_citizen_is_index_3(self):
        assert self._values.index("citizen") == 3

    def test_agent_is_index_4(self):
        assert self._values.index("agent") == 4

    def test_five_levels_in_hierarchy(self):
        assert len(self._hierarchy) == 5

    def test_quarantine_below_resident(self):
        assert self._values.index("quarantine") < self._values.index("resident")

    def test_agent_above_citizen(self):
        assert self._values.index("agent") > self._values.index("citizen")

    def test_agent_is_apex(self):
        assert self._values.index("agent") == max(range(len(self._values)))

    def test_quarantine_is_lowest(self):
        assert self._values.index("quarantine") == 0


# ═══════════════════════════════════════════════════════════════════════════════
# execute_remove_approved_source (pure logic — no approval gate needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteRemoveApprovedSource:
    def test_not_in_list_returns_error(self, foreman, monkeypatch):
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["jqlang/jq"])
        result = foreman.execute_remove_approved_source("nobody/noone")
        assert result["status"] == "error"

    def test_remove_success_requires_redis(self, foreman, monkeypatch):
        """REM: Successful removal calls _save_approved_sources which needs Redis.
        We verify the error path — that removal of present repo returns error
        when Redis is unavailable (not success)."""
        # When Redis unavailable, _save_approved_sources returns False → error
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["jqlang/jq"])
        monkeypatch.setattr("toolroom.foreman._save_approved_sources", lambda x: False)
        result = foreman.execute_remove_approved_source("jqlang/jq")
        # Should fail because save failed
        assert result["status"] == "error"

    def test_remove_success_when_save_works(self, foreman, monkeypatch):
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["jqlang/jq", "other/repo"])
        monkeypatch.setattr("toolroom.foreman._save_approved_sources", lambda x: True)
        result = foreman.execute_remove_approved_source("jqlang/jq")
        assert result["status"] == "success"


# ═══════════════════════════════════════════════════════════════════════════════
# Fixture — ForemanAgent with mock registry (for method tests)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def foreman_with_registry():
    """ForemanAgent bypassing __init__, with mock registry."""
    f = object.__new__(ForemanAgent)
    f.agent_id = FOREMAN_AGENT_ID
    f.registry = MagicMock()
    return f


# ═══════════════════════════════════════════════════════════════════════════════
# ForemanAgent.handle_return
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleReturn:
    def test_return_success(self, foreman_with_registry):
        foreman_with_registry.registry.return_tool.return_value = True
        result = foreman_with_registry.handle_return("checkout-depth-001")
        assert result["status"] == "success"
        assert "checkout-depth-001" in result["qms"]

    def test_return_not_found(self, foreman_with_registry):
        foreman_with_registry.registry.return_tool.return_value = False
        result = foreman_with_registry.handle_return("checkout-missing-xyz")
        assert result["status"] == "error"
        assert "not_found" in result["qms"]


# ═══════════════════════════════════════════════════════════════════════════════
# ForemanAgent.execute_add_approved_source
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteAddApprovedSource:
    def test_already_approved_returns_error(self, foreman_with_registry, monkeypatch):
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["jqlang/jq"])
        result = foreman_with_registry.execute_add_approved_source("jqlang/jq")
        assert result["status"] == "error"
        assert "already" in result["message"]

    def test_success_when_save_works(self, foreman_with_registry, monkeypatch):
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", [])
        monkeypatch.setattr("toolroom.foreman._save_approved_sources", lambda x: True)
        result = foreman_with_registry.execute_add_approved_source("new/repo")
        assert result["status"] == "success"
        assert "new/repo" in result["approved_sources"]

    def test_failure_when_save_fails(self, foreman_with_registry, monkeypatch):
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", [])
        monkeypatch.setattr("toolroom.foreman._save_approved_sources", lambda x: False)
        result = foreman_with_registry.execute_add_approved_source("new/repo")
        assert result["status"] == "error"


# ═══════════════════════════════════════════════════════════════════════════════
# ForemanAgent.list_approved_sources
# ═══════════════════════════════════════════════════════════════════════════════

class TestListApprovedSources:
    def test_list_returns_success(self, foreman_with_registry, monkeypatch):
        monkeypatch.setattr("toolroom.foreman._load_approved_sources", lambda: ["jqlang/jq"])
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["jqlang/jq"])
        result = foreman_with_registry.list_approved_sources()
        assert result["status"] == "success"
        assert isinstance(result["approved_sources"], list)
        assert "count" in result

    def test_list_reflects_current_sources(self, foreman_with_registry, monkeypatch):
        monkeypatch.setattr("toolroom.foreman._load_approved_sources", lambda: ["a/b", "c/d"])
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["a/b", "c/d"])
        result = foreman_with_registry.list_approved_sources()
        assert result["count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# ForemanAgent.propose_tool_install
# ═══════════════════════════════════════════════════════════════════════════════

class TestProposeToolInstall:
    def test_unapproved_source_returns_error(self, foreman_with_registry, monkeypatch):
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["jqlang/jq"])
        result = foreman_with_registry.propose_tool_install(
            "unapproved/repo", "mytool", "description", "utility"
        )
        assert result["status"] == "error"
        assert "unapproved_source" in result["qms"]

    def test_approved_source_creates_approval_request(self, foreman_with_registry, monkeypatch):
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["jqlang/jq"])
        mock_gate = MagicMock()
        mock_request = MagicMock()
        mock_request.request_id = "appr-install-depth-001"
        mock_gate.create_request.return_value = mock_request
        monkeypatch.setattr("toolroom.foreman.approval_gate", mock_gate)
        result = foreman_with_registry.propose_tool_install(
            "jqlang/jq", "jq tool", "JSON tool", "utility"
        )
        assert result["status"] == "pending_approval"
        assert result["approval_request_id"] == "appr-install-depth-001"

    def test_normalizes_repo_to_lowercase(self, foreman_with_registry, monkeypatch):
        monkeypatch.setattr("toolroom.foreman.APPROVED_GITHUB_SOURCES", ["jqlang/jq"])
        mock_gate = MagicMock()
        mock_request = MagicMock()
        mock_request.request_id = "appr-install-depth-002"
        mock_gate.create_request.return_value = mock_request
        monkeypatch.setattr("toolroom.foreman.approval_gate", mock_gate)
        # Pass with uppercase — should normalize
        result = foreman_with_registry.propose_tool_install(
            "JQLANG/JQ", "jq tool", "JSON tool", "utility"
        )
        assert result["status"] == "pending_approval"


# ═══════════════════════════════════════════════════════════════════════════════
# ForemanAgent.handle_new_tool_request
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleNewToolRequest:
    def test_returns_pending_review(self, foreman_with_registry):
        mock_request = MagicMock()
        mock_request.request_id = "req-depth-001"
        foreman_with_registry.registry.submit_tool_request.return_value = mock_request
        result = foreman_with_registry.handle_new_tool_request("agent1", "Need a SQL parser")
        assert result["status"] == "pending_review"
        assert result["request_id"] == "req-depth-001"

    def test_includes_agent_in_qms(self, foreman_with_registry):
        mock_request = MagicMock()
        mock_request.request_id = "req-depth-002"
        foreman_with_registry.registry.submit_tool_request.return_value = mock_request
        result = foreman_with_registry.handle_new_tool_request("my_agent", "Need a parser")
        assert "my_agent" in result["qms"]

    def test_passes_all_params_to_registry(self, foreman_with_registry):
        mock_request = MagicMock()
        mock_request.request_id = "req-depth-003"
        foreman_with_registry.registry.submit_tool_request.return_value = mock_request
        foreman_with_registry.handle_new_tool_request(
            "agent1", "desc", suggested_source="github:x/y", justification="needed"
        )
        foreman_with_registry.registry.submit_tool_request.assert_called_once_with(
            agent_id="agent1",
            description="desc",
            suggested_source="github:x/y",
            justification="needed",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ForemanAgent.get_toolroom_status
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetToolroomStatus:
    def test_status_returns_success(self, foreman_with_registry):
        mock_tool = MagicMock()
        mock_tool.status = "available"
        mock_tool.category = "utility"
        mock_tool.to_dict.return_value = {"tool_id": "t1", "status": "available"}
        foreman_with_registry.registry.list_tools.return_value = [mock_tool]
        foreman_with_registry.registry.get_active_checkouts.return_value = []
        foreman_with_registry.registry.get_pending_requests.return_value = []
        result = foreman_with_registry.get_toolroom_status()
        assert result["status"] == "success"
        assert result["total_tools"] == 1

    def test_status_empty_toolroom(self, foreman_with_registry):
        foreman_with_registry.registry.list_tools.return_value = []
        foreman_with_registry.registry.get_active_checkouts.return_value = []
        foreman_with_registry.registry.get_pending_requests.return_value = []
        result = foreman_with_registry.get_toolroom_status()
        assert result["status"] == "success"
        assert result["total_tools"] == 0

    def test_status_breakdown_by_category(self, foreman_with_registry):
        t1 = MagicMock()
        t1.status = "available"
        t1.category = "utility"
        t1.to_dict.return_value = {}
        t2 = MagicMock()
        t2.status = "available"
        t2.category = "database"
        t2.to_dict.return_value = {}
        foreman_with_registry.registry.list_tools.return_value = [t1, t2]
        foreman_with_registry.registry.get_active_checkouts.return_value = []
        foreman_with_registry.registry.get_pending_requests.return_value = []
        result = foreman_with_registry.get_toolroom_status()
        assert "utility" in result["category_breakdown"]
        assert "database" in result["category_breakdown"]


# ═══════════════════════════════════════════════════════════════════════════════
# ForemanAgent._execution_result_to_response
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecutionResultToResponse:
    def test_success_result(self, foreman_with_registry):
        result_obj = MagicMock()
        result_obj.success = True
        result_obj.tool_id = "test_tool"
        result_obj.exit_code = 0
        result_obj.duration_seconds = 0.5
        result_obj.output_data = {"result": "ok"}
        response = foreman_with_registry._execution_result_to_response(result_obj)
        assert response["status"] == "success"
        assert response["tool_id"] == "test_tool"
        assert response["exit_code"] == 0

    def test_failure_result_with_error_message(self, foreman_with_registry):
        result_obj = MagicMock()
        result_obj.success = False
        result_obj.tool_id = "test_tool"
        result_obj.exit_code = 1
        result_obj.duration_seconds = 0.2
        result_obj.error_message = "something went wrong"
        result_obj.stderr = ""
        response = foreman_with_registry._execution_result_to_response(result_obj)
        assert response["status"] == "error"
        assert response["tool_id"] == "test_tool"

    def test_failure_result_with_stderr(self, foreman_with_registry):
        result_obj = MagicMock()
        result_obj.success = False
        result_obj.tool_id = "test_tool2"
        result_obj.exit_code = 2
        result_obj.duration_seconds = 0.1
        result_obj.error_message = ""  # Empty — falls through to stderr
        result_obj.stderr = "command not found: jq"
        response = foreman_with_registry._execution_result_to_response(result_obj)
        assert response["status"] == "error"


# ═══════════════════════════════════════════════════════════════════════════════
# ForemanAgent.sync_function_tools
# ═══════════════════════════════════════════════════════════════════════════════

class TestSyncFunctionTools:
    def test_sync_empty_registry(self, foreman_with_registry, monkeypatch):
        mock_fr = MagicMock()
        mock_fr.list_all.return_value = []
        monkeypatch.setattr("toolroom.foreman.function_tool_registry", mock_fr)
        result = foreman_with_registry.sync_function_tools()
        assert result["status"] == "success"
        assert result["synced_count"] == 0

    def test_sync_with_one_tool(self, foreman_with_registry, monkeypatch):
        mock_entry = MagicMock()
        mock_entry.tool_id = "func_tool_depth_1"
        mock_entry.name = "Func Tool"
        mock_entry.description = "A test function tool"
        mock_entry.category = "utility"
        mock_entry.version = "1.0.0"
        mock_entry.func.__module__ = "test_module"
        mock_entry.func.__name__ = "test_func"
        mock_entry.requires_api_access = False
        mock_entry.min_trust_level = "resident"
        mock_entry.manifest.to_dict.return_value = {}
        mock_fr = MagicMock()
        mock_fr.list_all.return_value = [mock_entry]
        monkeypatch.setattr("toolroom.foreman.function_tool_registry", mock_fr)
        result = foreman_with_registry.sync_function_tools()
        assert result["status"] == "success"
        assert result["synced_count"] == 1
        foreman_with_registry.registry.register_tool.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# ForemanAgent.handle_checkout_request — all branches
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleCheckoutRequest:
    def test_tool_not_found(self, foreman_with_registry):
        foreman_with_registry.registry.get_tool.return_value = None
        result = foreman_with_registry.handle_checkout_request("agent1", "missing_tool")
        assert result["status"] == "error"
        assert "missing_tool" in result["message"]

    def test_agent_not_authorized(self, foreman_with_registry):
        tool = MagicMock()
        tool.allowed_agents = ["allowed_agent"]
        foreman_with_registry.registry.get_tool.return_value = tool
        result = foreman_with_registry.handle_checkout_request("unauthorized_agent", "tool1")
        assert result["status"] == "error"
        assert "not authorized" in result["message"]

    def test_insufficient_trust_level(self, foreman_with_registry):
        tool = MagicMock()
        tool.allowed_agents = []
        tool.requires_api_access = False
        tool.min_trust_level = AgentTrustLevel.CITIZEN.value  # citizen required
        foreman_with_registry.registry.get_tool.return_value = tool
        result = foreman_with_registry.handle_checkout_request(
            "agent1", "tool1", agent_trust_level="probation"
        )
        assert result["status"] == "error"
        assert "trust" in result["message"].lower()

    def test_requires_api_access_creates_approval(self, foreman_with_registry, monkeypatch):
        tool = MagicMock()
        tool.allowed_agents = []
        tool.requires_api_access = True
        tool.min_trust_level = "resident"
        foreman_with_registry.registry.get_tool.return_value = tool
        mock_gate = MagicMock()
        mock_request = MagicMock()
        mock_request.request_id = "appr-api-depth-001"
        mock_gate.create_request.return_value = mock_request
        monkeypatch.setattr("toolroom.foreman.approval_gate", mock_gate)
        result = foreman_with_registry.handle_checkout_request(
            "agent1", "api_tool", agent_trust_level="resident"
        )
        assert result["status"] == "pending_approval"
        assert result["approval_required"] is True

    def test_successful_checkout(self, foreman_with_registry):
        tool = MagicMock()
        tool.allowed_agents = []
        tool.requires_api_access = False
        tool.min_trust_level = "probation"
        foreman_with_registry.registry.get_tool.return_value = tool
        checkout = MagicMock()
        checkout.checkout_id = "checkout-depth-success-001"
        foreman_with_registry.registry.checkout_tool.return_value = checkout
        result = foreman_with_registry.handle_checkout_request(
            "agent1", "tool1", agent_trust_level="resident"
        )
        assert result["status"] == "success"
        assert result["checkout_id"] == "checkout-depth-success-001"

    def test_checkout_failure_returns_error(self, foreman_with_registry):
        tool = MagicMock()
        tool.allowed_agents = []
        tool.requires_api_access = False
        tool.min_trust_level = "quarantine"
        foreman_with_registry.registry.get_tool.return_value = tool
        foreman_with_registry.registry.checkout_tool.return_value = None
        result = foreman_with_registry.handle_checkout_request(
            "agent1", "tool1", agent_trust_level="resident"
        )
        assert result["status"] == "error"
        assert "checkout_failed" in result["qms"]

    def test_unknown_agent_trust_defaults_to_quarantine(self, foreman_with_registry):
        tool = MagicMock()
        tool.allowed_agents = []
        tool.requires_api_access = False
        tool.min_trust_level = "citizen"
        foreman_with_registry.registry.get_tool.return_value = tool
        result = foreman_with_registry.handle_checkout_request(
            "agent1", "tool1", agent_trust_level="superpower"
        )
        # unknown level → quarantine (0) < citizen (3) → denied
        assert result["status"] == "error"

    def test_unknown_tool_trust_defaults_to_most_restrictive(self, foreman_with_registry):
        tool = MagicMock()
        tool.allowed_agents = []
        tool.requires_api_access = False
        tool.min_trust_level = "ultracitizen"  # unknown
        foreman_with_registry.registry.get_tool.return_value = tool
        result = foreman_with_registry.handle_checkout_request(
            "agent1", "tool1", agent_trust_level="resident"
        )
        # unknown tool level → apex (4) > resident (2) → denied
        assert result["status"] == "error"

    def test_apex_agent_can_checkout_any_tool(self, foreman_with_registry):
        tool = MagicMock()
        tool.allowed_agents = []
        tool.requires_api_access = False
        tool.min_trust_level = "citizen"
        foreman_with_registry.registry.get_tool.return_value = tool
        checkout = MagicMock()
        checkout.checkout_id = "checkout-apex-001"
        foreman_with_registry.registry.checkout_tool.return_value = checkout
        result = foreman_with_registry.handle_checkout_request(
            "apex_agent", "citizen_tool", agent_trust_level="agent"
        )
        assert result["status"] == "success"


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level functions: _load_approved_sources / _save_approved_sources
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadSaveApprovedSources:
    def test_load_falls_back_to_defaults_on_redis_error(self, monkeypatch):
        import toolroom.foreman as fm
        import redis
        monkeypatch.setattr(
            redis.Redis, "from_url", staticmethod(lambda *a, **k: (_ for _ in ()).throw(Exception("down")))
        )
        result = fm._load_approved_sources()
        assert isinstance(result, list)
        assert len(result) > 0  # falls back to DEFAULT_GITHUB_SOURCES

    def test_save_returns_false_on_redis_error(self, monkeypatch):
        import toolroom.foreman as fm
        import redis
        monkeypatch.setattr(
            redis.Redis, "from_url", staticmethod(lambda *a, **k: (_ for _ in ()).throw(Exception("down")))
        )
        result = fm._save_approved_sources(["jqlang/jq"])
        assert result is False

    def test_load_returns_list(self, monkeypatch):
        import toolroom.foreman as fm
        mock_client = MagicMock()
        mock_client.get.return_value = '["jqlang/jq", "dbcli/pgcli"]'
        import redis
        monkeypatch.setattr(redis.Redis, "from_url", staticmethod(lambda *a, **k: mock_client))
        result = fm._load_approved_sources()
        assert isinstance(result, list)

    def test_load_seeds_defaults_when_redis_empty(self, monkeypatch):
        import toolroom.foreman as fm
        mock_client = MagicMock()
        mock_client.get.return_value = None  # No data in Redis
        import redis
        monkeypatch.setattr(redis.Redis, "from_url", staticmethod(lambda *a, **k: mock_client))
        result = fm._load_approved_sources()
        # Should seed defaults
        mock_client.set.assert_called_once()
        assert isinstance(result, list)

    def test_save_updates_module_cache(self, monkeypatch):
        import toolroom.foreman as fm
        mock_client = MagicMock()
        import redis
        monkeypatch.setattr(redis.Redis, "from_url", staticmethod(lambda *a, **k: mock_client))
        result = fm._save_approved_sources(["new/repo"])
        assert result is True
        assert "new/repo" in fm.APPROVED_GITHUB_SOURCES
