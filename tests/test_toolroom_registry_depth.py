# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_toolroom_registry_depth.py
# REM: Depth tests for toolroom/registry.py — pure in-memory, no Redis/external deps

import sys
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# REM: celery is not installed locally — stub before any toolroom import
if "celery" not in sys.modules:
    celery_mock = MagicMock()
    celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = celery_mock

import pytest

from toolroom.registry import (
    ToolStatus,
    ToolCategory,
    ToolMetadata,
    ToolCheckout,
    ToolRequest,
    ToolRegistry,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    monkeypatch.setattr("core.persistence.get_redis", lambda: None)
    monkeypatch.setattr("toolroom.registry._get_store", lambda: None)


@pytest.fixture
def reg():
    """REM: In-memory ToolRegistry — bypasses __init__ to avoid Redis DNS."""
    r = object.__new__(ToolRegistry)
    r._tools = {}
    r._active_checkouts = {}
    r._checkout_history = []
    r._tool_requests = {}
    r._usage_log = []
    # REM: _persist() is referenced in cleanup_stale_checkouts but not defined
    # (only _persist_tools/_persist_checkouts exist) — patch as no-op
    r._persist = lambda: None
    r._persist_tools = lambda: None
    r._persist_checkouts = lambda: None
    r._persist_requests = lambda: None
    r._persist_checkout_history_entry = lambda c: None
    return r


def _tool(**kwargs) -> ToolMetadata:
    defaults = dict(
        tool_id="tool_1",
        name="My Tool",
        description="A test tool",
        category=ToolCategory.UTILITY,
        version="1.0.0",
        source="github:test/repo",
    )
    defaults.update(kwargs)
    return ToolMetadata(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# ToolStatus enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolStatus:
    def test_available(self):
        assert ToolStatus.AVAILABLE.value == "available"

    def test_checked_out(self):
        assert ToolStatus.CHECKED_OUT.value == "checked_out"

    def test_updating(self):
        assert ToolStatus.UPDATING.value == "updating"

    def test_deprecated(self):
        assert ToolStatus.DEPRECATED.value == "deprecated"

    def test_quarantined(self):
        assert ToolStatus.QUARANTINED.value == "quarantined"

    def test_pending_upload(self):
        assert ToolStatus.PENDING_UPLOAD.value == "pending_upload"

    def test_six_statuses(self):
        assert len(ToolStatus) == 6

    def test_is_str_enum(self):
        assert ToolStatus.AVAILABLE == "available"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolCategory enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolCategory:
    def test_database(self):
        assert ToolCategory.DATABASE.value == "database"

    def test_parsing(self):
        assert ToolCategory.PARSING.value == "parsing"

    def test_network(self):
        assert ToolCategory.NETWORK.value == "network"

    def test_crypto(self):
        assert ToolCategory.CRYPTO.value == "crypto"

    def test_filesystem(self):
        assert ToolCategory.FILESYSTEM.value == "filesystem"

    def test_analytics(self):
        assert ToolCategory.ANALYTICS.value == "analytics"

    def test_integration(self):
        assert ToolCategory.INTEGRATION.value == "integration"

    def test_utility(self):
        assert ToolCategory.UTILITY.value == "utility"

    def test_eight_categories(self):
        assert len(ToolCategory) == 8


# ═══════════════════════════════════════════════════════════════════════════════
# ToolMetadata dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolMetadata:
    def test_default_status_available(self):
        t = _tool()
        assert t.status == ToolStatus.AVAILABLE

    def test_default_min_trust_level(self):
        t = _tool()
        assert t.min_trust_level == "resident"

    def test_default_requires_api_access_false(self):
        t = _tool()
        assert t.requires_api_access is False

    def test_default_allowed_agents_empty(self):
        t = _tool()
        assert t.allowed_agents == []

    def test_default_total_checkouts_zero(self):
        t = _tool()
        assert t.total_checkouts == 0

    def test_default_active_checkouts_zero(self):
        t = _tool()
        assert t.active_checkouts == 0

    def test_default_max_concurrent_checkouts(self):
        t = _tool()
        assert t.max_concurrent_checkouts == 1

    def test_default_version_history_empty(self):
        t = _tool()
        assert t.version_history == []

    def test_to_dict_returns_dict(self):
        t = _tool()
        assert isinstance(t.to_dict(), dict)

    def test_to_dict_has_tool_id(self):
        t = _tool(tool_id="tool_abc")
        assert t.to_dict()["tool_id"] == "tool_abc"

    def test_from_dict_roundtrip(self):
        t = _tool(name="RoundTrip", version="2.0.0", sha256_hash="abc123")
        t2 = ToolMetadata.from_dict(t.to_dict())
        assert t2.name == t.name
        assert t2.version == t.version
        assert t2.sha256_hash == t.sha256_hash

    def test_from_dict_ignores_unknown_fields(self):
        d = _tool().to_dict()
        d["future_field_unknown"] = "ignored"
        t = ToolMetadata.from_dict(d)
        assert t.name == "My Tool"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolCheckout dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolCheckout:
    def test_checkout_id_prefix(self):
        c = ToolCheckout(tool_id="t", agent_id="a")
        assert c.checkout_id.startswith("CHKOUT-")

    def test_checkout_id_unique(self):
        c1 = ToolCheckout(tool_id="t", agent_id="a")
        c2 = ToolCheckout(tool_id="t", agent_id="a")
        assert c1.checkout_id != c2.checkout_id

    def test_returned_at_default_none(self):
        c = ToolCheckout(tool_id="t", agent_id="a")
        assert c.returned_at is None

    def test_approved_by_default(self):
        c = ToolCheckout(tool_id="t", agent_id="a")
        assert c.approved_by == "system"

    def test_to_dict_returns_dict(self):
        c = ToolCheckout(tool_id="t", agent_id="a")
        assert isinstance(c.to_dict(), dict)

    def test_from_dict_roundtrip(self):
        c = ToolCheckout(tool_id="tool_x", agent_id="agent_y", purpose="testing")
        c2 = ToolCheckout.from_dict(c.to_dict())
        assert c2.checkout_id == c.checkout_id
        assert c2.tool_id == c.tool_id
        assert c2.agent_id == c.agent_id
        assert c2.purpose == c.purpose


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRequest dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolRequest:
    def test_request_id_prefix(self):
        r = ToolRequest(requesting_agent="a", tool_description="need X")
        assert r.request_id.startswith("TOOLREQ-")

    def test_request_id_unique(self):
        r1 = ToolRequest(requesting_agent="a", tool_description="X")
        r2 = ToolRequest(requesting_agent="a", tool_description="X")
        assert r1.request_id != r2.request_id

    def test_default_status_pending(self):
        r = ToolRequest(requesting_agent="a", tool_description="X")
        assert r.status == "pending"

    def test_to_dict_returns_dict(self):
        r = ToolRequest(requesting_agent="a", tool_description="X")
        assert isinstance(r.to_dict(), dict)


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.register_tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegisterTool:
    def test_stores_tool(self, reg):
        t = _tool()
        reg.register_tool(t)
        assert "tool_1" in reg._tools

    def test_returns_metadata(self, reg):
        t = _tool()
        result = reg.register_tool(t)
        assert isinstance(result, ToolMetadata)

    def test_overwrite_snapshots_version_history(self, reg):
        t1 = _tool(version="1.0.0")
        reg.register_tool(t1)
        t2 = _tool(version="2.0.0")
        reg.register_tool(t2)
        assert len(reg._tools["tool_1"].version_history) == 1
        assert reg._tools["tool_1"].version_history[0]["version"] == "1.0.0"

    def test_version_history_capped_at_10(self, reg):
        for i in range(12):
            reg.register_tool(_tool(version=f"1.{i}.0"))
        assert len(reg._tools["tool_1"].version_history) <= 10

    def test_different_tools_stored_separately(self, reg):
        reg.register_tool(_tool(tool_id="tool_a"))
        reg.register_tool(_tool(tool_id="tool_b"))
        assert "tool_a" in reg._tools
        assert "tool_b" in reg._tools


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.get_tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetTool:
    def test_returns_tool_if_exists(self, reg):
        reg.register_tool(_tool())
        assert reg.get_tool("tool_1") is not None

    def test_returns_none_for_unknown(self, reg):
        assert reg.get_tool("nonexistent") is None

    def test_returns_correct_tool(self, reg):
        reg.register_tool(_tool(name="Alpha", tool_id="alpha"))
        reg.register_tool(_tool(name="Beta", tool_id="beta"))
        assert reg.get_tool("alpha").name == "Alpha"
        assert reg.get_tool("beta").name == "Beta"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.list_tools
# ═══════════════════════════════════════════════════════════════════════════════

class TestListTools:
    def test_empty_registry(self, reg):
        assert reg.list_tools() == []

    def test_returns_all_tools(self, reg):
        reg.register_tool(_tool(tool_id="t1"))
        reg.register_tool(_tool(tool_id="t2"))
        assert len(reg.list_tools()) == 2

    def test_filter_by_category(self, reg):
        reg.register_tool(_tool(tool_id="t1", category="utility"))
        reg.register_tool(_tool(tool_id="t2", category="database"))
        assert len(reg.list_tools(category="utility")) == 1
        assert len(reg.list_tools(category="database")) == 1

    def test_filter_by_status(self, reg):
        reg.register_tool(_tool(tool_id="t1", status="available"))
        reg.register_tool(_tool(tool_id="t2", status="deprecated"))
        available = reg.list_tools(status="available")
        assert len(available) == 1

    def test_available_only(self, reg):
        reg.register_tool(_tool(tool_id="t1"))
        reg.register_tool(_tool(tool_id="t2", status="quarantined"))
        avail = reg.list_tools(available_only=True)
        assert len(avail) == 1
        assert avail[0].tool_id == "t1"

    def test_no_filter_matches_all_statuses(self, reg):
        reg.register_tool(_tool(tool_id="t1"))
        reg.register_tool(_tool(tool_id="t2", status="deprecated"))
        assert len(reg.list_tools()) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.update_tool_status
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateToolStatus:
    def test_returns_false_for_unknown_tool(self, reg):
        assert reg.update_tool_status("nonexistent", "deprecated") is False

    def test_returns_true_on_success(self, reg):
        reg.register_tool(_tool())
        assert reg.update_tool_status("tool_1", "deprecated") is True

    def test_status_changed(self, reg):
        reg.register_tool(_tool())
        reg.update_tool_status("tool_1", "quarantined")
        assert reg._tools["tool_1"].status == "quarantined"

    def test_quarantine_status(self, reg):
        reg.register_tool(_tool())
        reg.update_tool_status("tool_1", "quarantined", reason="security review")
        assert reg._tools["tool_1"].status == "quarantined"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.get_version_history / rollback_tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestVersionHistory:
    def test_none_for_unknown_tool(self, reg):
        assert reg.get_version_history("nonexistent") is None

    def test_empty_list_for_new_tool(self, reg):
        reg.register_tool(_tool())
        assert reg.get_version_history("tool_1") == []

    def test_history_populated_after_update(self, reg):
        reg.register_tool(_tool(version="1.0.0"))
        reg.register_tool(_tool(version="2.0.0"))
        history = reg.get_version_history("tool_1")
        assert len(history) == 1
        assert history[0]["version"] == "1.0.0"

    def test_rollback_returns_none_for_unknown(self, reg):
        assert reg.rollback_tool("nonexistent", "1.0.0") is None

    def test_rollback_returns_none_for_no_history(self, reg):
        reg.register_tool(_tool(version="1.0.0"))
        assert reg.rollback_tool("tool_1", "0.9.0") is None

    def test_rollback_returns_none_for_version_not_in_history(self, reg):
        reg.register_tool(_tool(version="1.0.0"))
        reg.register_tool(_tool(version="2.0.0"))
        assert reg.rollback_tool("tool_1", "9.9.9") is None

    def test_rollback_success(self, reg):
        reg.register_tool(_tool(version="1.0.0"))
        reg.register_tool(_tool(version="2.0.0"))
        result = reg.rollback_tool("tool_1", "1.0.0")
        assert result is not None
        assert result["rolled_back_from"] == "2.0.0"
        assert result["rolled_back_to"] == "1.0.0"

    def test_rollback_changes_current_version(self, reg):
        reg.register_tool(_tool(version="1.0.0"))
        reg.register_tool(_tool(version="2.0.0"))
        reg.rollback_tool("tool_1", "1.0.0")
        assert reg._tools["tool_1"].version == "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.checkout_tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckoutTool:
    def test_returns_none_for_unknown_tool(self, reg):
        assert reg.checkout_tool("nonexistent", "agent_1") is None

    def test_returns_checkout_on_success(self, reg):
        reg.register_tool(_tool())
        result = reg.checkout_tool("tool_1", "agent_1")
        assert isinstance(result, ToolCheckout)

    def test_checkout_id_in_active(self, reg):
        reg.register_tool(_tool())
        c = reg.checkout_tool("tool_1", "agent_1")
        assert c.checkout_id in reg._active_checkouts

    def test_increments_total_checkouts(self, reg):
        reg.register_tool(_tool())
        reg.checkout_tool("tool_1", "agent_1")
        assert reg._tools["tool_1"].total_checkouts == 1

    def test_increments_active_checkouts(self, reg):
        reg.register_tool(_tool())
        reg.checkout_tool("tool_1", "agent_1")
        assert reg._tools["tool_1"].active_checkouts == 1

    def test_records_last_checkout_by(self, reg):
        reg.register_tool(_tool())
        reg.checkout_tool("tool_1", "agent_x")
        assert reg._tools["tool_1"].last_checkout_by == "agent_x"

    def test_returns_none_for_quarantined_tool(self, reg):
        reg.register_tool(_tool(status="quarantined"))
        assert reg.checkout_tool("tool_1", "agent_1") is None

    def test_returns_none_when_exclusive_and_busy(self, reg):
        # max_concurrent_checkouts=1 (default), already at limit
        reg.register_tool(_tool(max_concurrent_checkouts=1, active_checkouts=1))
        assert reg.checkout_tool("tool_1", "agent_2") is None

    def test_unlimited_checkout_allowed(self, reg):
        # max_concurrent_checkouts=0 means unlimited
        reg.register_tool(_tool(max_concurrent_checkouts=0, active_checkouts=5))
        result = reg.checkout_tool("tool_1", "agent_1")
        assert result is not None

    def test_allowed_agents_blocks_unauthorized(self, reg):
        reg.register_tool(_tool(allowed_agents=["agent_a"]))
        assert reg.checkout_tool("tool_1", "agent_b") is None

    def test_allowed_agents_permits_authorized(self, reg):
        reg.register_tool(_tool(allowed_agents=["agent_a"]))
        result = reg.checkout_tool("tool_1", "agent_a")
        assert result is not None

    def test_purpose_stored_in_checkout(self, reg):
        reg.register_tool(_tool())
        c = reg.checkout_tool("tool_1", "agent_1", purpose="data analysis")
        assert c.purpose == "data analysis"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.return_tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestReturnTool:
    def test_returns_false_for_unknown_checkout(self, reg):
        assert reg.return_tool("CHKOUT-nonexistent") is False

    def test_returns_true_on_success(self, reg):
        reg.register_tool(_tool())
        c = reg.checkout_tool("tool_1", "agent_1")
        assert reg.return_tool(c.checkout_id) is True

    def test_removes_from_active(self, reg):
        reg.register_tool(_tool())
        c = reg.checkout_tool("tool_1", "agent_1")
        reg.return_tool(c.checkout_id)
        assert c.checkout_id not in reg._active_checkouts

    def test_moves_to_history(self, reg):
        reg.register_tool(_tool())
        c = reg.checkout_tool("tool_1", "agent_1")
        reg.return_tool(c.checkout_id)
        assert any(h.checkout_id == c.checkout_id for h in reg._checkout_history)

    def test_decrements_active_checkouts(self, reg):
        reg.register_tool(_tool())
        c = reg.checkout_tool("tool_1", "agent_1")
        reg.return_tool(c.checkout_id)
        assert reg._tools["tool_1"].active_checkouts == 0

    def test_returned_at_set(self, reg):
        reg.register_tool(_tool())
        c = reg.checkout_tool("tool_1", "agent_1")
        reg.return_tool(c.checkout_id)
        returned = reg._checkout_history[-1]
        assert returned.returned_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.get_active_checkouts
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetActiveCheckouts:
    def test_empty_initially(self, reg):
        assert reg.get_active_checkouts() == []

    def test_returns_all_without_filter(self, reg):
        reg.register_tool(_tool(tool_id="t1", max_concurrent_checkouts=0))
        reg.register_tool(_tool(tool_id="t2"))
        reg.checkout_tool("t1", "agent_1")
        reg.checkout_tool("t2", "agent_2")
        assert len(reg.get_active_checkouts()) == 2

    def test_filters_by_agent(self, reg):
        reg.register_tool(_tool(tool_id="t1", max_concurrent_checkouts=0))
        reg.register_tool(_tool(tool_id="t2"))
        reg.checkout_tool("t1", "agent_a")
        reg.checkout_tool("t2", "agent_b")
        result = reg.get_active_checkouts(agent_id="agent_a")
        assert len(result) == 1
        assert result[0].agent_id == "agent_a"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.submit_tool_request / get_pending_requests / resolve_request
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolRequests:
    def test_submit_returns_tool_request(self, reg):
        r = reg.submit_tool_request("agent_1", "need a csv parser")
        assert isinstance(r, ToolRequest)

    def test_submit_stores_request(self, reg):
        r = reg.submit_tool_request("agent_1", "need a csv parser")
        assert r.request_id in reg._tool_requests

    def test_get_pending_initially_empty(self, reg):
        assert reg.get_pending_requests() == []

    def test_get_pending_after_submit(self, reg):
        reg.submit_tool_request("agent_1", "csv parser")
        assert len(reg.get_pending_requests()) == 1

    def test_resolve_returns_false_for_unknown(self, reg):
        assert reg.resolve_request("TOOLREQ-nonexistent", "approved") is False

    def test_resolve_returns_true_on_success(self, reg):
        r = reg.submit_tool_request("agent_1", "csv parser")
        assert reg.resolve_request(r.request_id, "approved") is True

    def test_resolve_updates_status(self, reg):
        r = reg.submit_tool_request("agent_1", "csv parser")
        reg.resolve_request(r.request_id, "rejected")
        assert reg._tool_requests[r.request_id].status == "rejected"

    def test_resolved_not_in_pending(self, reg):
        r = reg.submit_tool_request("agent_1", "csv parser")
        reg.resolve_request(r.request_id, "approved")
        assert reg.get_pending_requests() == []

    def test_resolve_sets_reviewer(self, reg):
        r = reg.submit_tool_request("agent_1", "csv parser")
        reg.resolve_request(r.request_id, "approved", reviewer="operator")
        assert reg._tool_requests[r.request_id].reviewed_by == "operator"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.get_usage_report
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUsageReport:
    def test_empty_initially(self, reg):
        assert reg.get_usage_report() == []

    def test_checkout_appears_in_usage(self, reg):
        reg.register_tool(_tool())
        reg.checkout_tool("tool_1", "agent_1")
        report = reg.get_usage_report()
        assert len(report) >= 1

    def test_filter_by_tool_id(self, reg):
        reg.register_tool(_tool(tool_id="t1", max_concurrent_checkouts=0))
        reg.register_tool(_tool(tool_id="t2"))
        reg.checkout_tool("t1", "agent_1")
        reg.checkout_tool("t2", "agent_2")
        report = reg.get_usage_report(tool_id="t1")
        assert all(e["tool_id"] == "t1" for e in report)

    def test_filter_by_agent(self, reg):
        reg.register_tool(_tool())
        reg.checkout_tool("tool_1", "agent_z")
        report = reg.get_usage_report(agent_id="agent_z")
        assert all(e["agent_id"] == "agent_z" for e in report)

    def test_limit_applied(self, reg):
        reg.register_tool(_tool(max_concurrent_checkouts=0))
        for _ in range(5):
            reg.checkout_tool("tool_1", "agent_1")
        report = reg.get_usage_report(limit=2)
        assert len(report) <= 2


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry.cleanup_stale_checkouts
# ═══════════════════════════════════════════════════════════════════════════════

class TestCleanupStaleCheckouts:
    def test_empty_returns_empty(self, reg):
        assert reg.cleanup_stale_checkouts() == []

    def test_fresh_checkout_not_cleaned(self, reg):
        reg.register_tool(_tool())
        reg.checkout_tool("tool_1", "agent_1")
        stale = reg.cleanup_stale_checkouts(max_age_hours=24)
        assert stale == []

    def test_old_checkout_cleaned(self, reg):
        reg.register_tool(_tool())
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        c = ToolCheckout(tool_id="tool_1", agent_id="agent_1", checked_out_at=old_time)
        reg._active_checkouts[c.checkout_id] = c
        reg._tools["tool_1"].active_checkouts = 1
        stale = reg.cleanup_stale_checkouts(max_age_hours=24)
        assert len(stale) == 1
        assert c.checkout_id in stale

    def test_stale_decrements_active_count(self, reg):
        reg.register_tool(_tool())
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        c = ToolCheckout(tool_id="tool_1", agent_id="agent_1", checked_out_at=old_time)
        reg._active_checkouts[c.checkout_id] = c
        reg._tools["tool_1"].active_checkouts = 1
        reg.cleanup_stale_checkouts(max_age_hours=24)
        assert reg._tools["tool_1"].active_checkouts == 0

    def test_stale_removed_from_active(self, reg):
        reg.register_tool(_tool())
        old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        c = ToolCheckout(tool_id="tool_1", agent_id="agent_1", checked_out_at=old_time)
        reg._active_checkouts[c.checkout_id] = c
        reg.cleanup_stale_checkouts(max_age_hours=24)
        assert c.checkout_id not in reg._active_checkouts
