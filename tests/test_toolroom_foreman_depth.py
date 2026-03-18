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
