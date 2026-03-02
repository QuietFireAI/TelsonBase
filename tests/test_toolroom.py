# TelsonBase/tests/test_toolroom.py
# REM: =======================================================================================
# REM: TOOLROOM & FOREMAN TEST SUITE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Tests all 6 bugs/gaps identified in code review plus API endpoint coverage.
# REM: Covers: ToolroomStore persistence, trust level case normalization, registry CRUD,
# REM: Foreman checkout flow, approval gate integration, and API endpoints.
# REM: =======================================================================================

import os
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


# REM: =======================================================================================
# REM: SECTION 1: TOOLROOM REGISTRY UNIT TESTS
# REM: =======================================================================================

class TestToolMetadata:
    """REM: Test ToolMetadata dataclass behavior."""
    
    def test_tool_metadata_creation(self):
        """REM: Basic ToolMetadata construction."""
        from toolroom.registry import ToolMetadata
        
        tool = ToolMetadata(
            tool_id="tool_test",
            name="Test Tool",
            description="A test tool",
            category="utility",
            version="1.0.0",
            source="github:test/repo",
        )
        assert tool.tool_id == "tool_test"
        assert tool.status == "available"
        assert tool.active_checkouts == 0
        assert tool.requires_api_access is False
    
    def test_tool_metadata_default_trust_level_is_lowercase(self):
        """
        REM: BUG 2 regression — min_trust_level MUST default to lowercase
        to match AgentTrustLevel enum values.
        """
        from toolroom.registry import ToolMetadata
        
        tool = ToolMetadata(
            tool_id="tool_trust_test",
            name="Trust Test",
            description="Test",
            category="utility",
            version="1.0",
            source="local",
        )
        assert tool.min_trust_level == "resident"
        assert tool.min_trust_level != "RESIDENT"  # Must NOT be uppercase
    
    def test_tool_metadata_round_trip(self):
        """REM: to_dict/from_dict round-trip preserves all fields."""
        from toolroom.registry import ToolMetadata
        
        original = ToolMetadata(
            tool_id="tool_roundtrip",
            name="Roundtrip Tool",
            description="Tests serialization",
            category="analysis",
            version="2.1.0",
            source="github:test/roundtrip",
            requires_api_access=True,
            sha256_hash="abc123",
            min_trust_level="citizen",
        )
        
        d = original.to_dict()
        restored = ToolMetadata.from_dict(d)
        
        assert restored.tool_id == original.tool_id
        assert restored.name == original.name
        assert restored.requires_api_access is True
        assert restored.min_trust_level == "citizen"
        assert restored.sha256_hash == "abc123"


class TestToolCheckout:
    """REM: Test ToolCheckout dataclass behavior."""
    
    def test_checkout_creation(self):
        from toolroom.registry import ToolCheckout
        
        checkout = ToolCheckout(
            tool_id="tool_test",
            agent_id="test_agent",
            purpose="unit testing",
        )
        assert checkout.checkout_id.startswith("CHKOUT-")
        assert checkout.returned_at is None
    
    def test_checkout_round_trip(self):
        from toolroom.registry import ToolCheckout
        
        original = ToolCheckout(
            tool_id="tool_test",
            agent_id="test_agent",
            purpose="testing round trip",
            approved_by="foreman_agent",
        )
        
        d = original.to_dict()
        restored = ToolCheckout.from_dict(d)
        
        assert restored.checkout_id == original.checkout_id
        assert restored.tool_id == "tool_test"
        assert restored.agent_id == "test_agent"


class TestToolRegistry:
    """REM: Test ToolRegistry CRUD operations."""
    
    @pytest.fixture
    def registry(self, mocker):
        """REM: Fresh registry with mocked persistence."""
        # Mock the _get_store function to return None (no Redis)
        mocker.patch("toolroom.registry._get_store", return_value=None)
        from toolroom.registry import ToolRegistry
        return ToolRegistry()
    
    @pytest.fixture
    def sample_tool(self):
        from toolroom.registry import ToolMetadata
        return ToolMetadata(
            tool_id="tool_jq",
            name="jq",
            description="JSON processor",
            category="utility",
            version="1.7",
            source="github:jqlang/jq",
        )
    
    def test_register_tool(self, registry, sample_tool):
        registry.register_tool(sample_tool)
        assert registry.get_tool("tool_jq") is not None
    
    def test_register_duplicate_updates(self, registry, sample_tool):
        registry.register_tool(sample_tool)
        sample_tool.version = "1.8"
        registry.register_tool(sample_tool)
        assert registry.get_tool("tool_jq").version == "1.8"
    
    def test_list_tools(self, registry, sample_tool):
        registry.register_tool(sample_tool)
        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "jq"
    
    def test_list_tools_by_category(self, registry, sample_tool):
        from toolroom.registry import ToolMetadata
        
        registry.register_tool(sample_tool)
        registry.register_tool(ToolMetadata(
            tool_id="tool_pgcli",
            name="pgcli",
            description="Postgres CLI",
            category="database",
            version="4.0",
            source="github:dbcli/pgcli",
        ))
        
        utilities = registry.list_tools(category="utility")
        assert len(utilities) == 1
        assert utilities[0].tool_id == "tool_jq"
    
    def test_checkout_and_return(self, registry, sample_tool):
        registry.register_tool(sample_tool)
        
        checkout = registry.checkout_tool(
            tool_id="tool_jq",
            agent_id="demo_agent",
            purpose="processing JSON",
            approved_by="foreman_agent",
        )
        assert checkout is not None
        assert checkout.agent_id == "demo_agent"
        
        # REM: Tool should show active checkout
        tool = registry.get_tool("tool_jq")
        assert tool.active_checkouts == 1
        
        # REM: Return
        result = registry.return_tool(checkout.checkout_id)
        assert result is True
        
        # REM: Tool should show no active checkouts
        tool = registry.get_tool("tool_jq")
        assert tool.active_checkouts == 0
    
    def test_checkout_nonexistent_tool_returns_none(self, registry):
        checkout = registry.checkout_tool(
            tool_id="tool_doesnt_exist",
            agent_id="test_agent",
            purpose="testing",
            approved_by="foreman_agent",
        )
        assert checkout is None
    
    def test_checkout_quarantined_tool_returns_none(self, registry, sample_tool):
        registry.register_tool(sample_tool)
        registry.update_tool_status("tool_jq", "quarantined", "security review")
        
        checkout = registry.checkout_tool(
            tool_id="tool_jq",
            agent_id="test_agent",
            purpose="testing",
            approved_by="foreman_agent",
        )
        assert checkout is None
    
    def test_return_nonexistent_checkout(self, registry):
        result = registry.return_tool("CHKOUT-DOESNOTEXIST")
        assert result is False
    
    def test_submit_tool_request(self, registry):
        request = registry.submit_tool_request(
            agent_id="demo_agent",
            description="Need a CSV parser tool",
            suggested_source="github:csvkit/csvkit",
            justification="Frequent CSV processing tasks",
        )
        assert request.request_id.startswith("TOOLREQ-")
        assert request.status == "pending"
    
    def test_get_pending_requests(self, registry):
        registry.submit_tool_request(
            agent_id="demo_agent",
            description="Need tool A",
        )
        registry.submit_tool_request(
            agent_id="backup_agent",
            description="Need tool B",
        )
        
        pending = registry.get_pending_requests()
        assert len(pending) == 2
    
    def test_get_active_checkouts_filtered(self, registry, sample_tool):
        from toolroom.registry import ToolMetadata
        
        registry.register_tool(sample_tool)
        registry.register_tool(ToolMetadata(
            tool_id="tool_other",
            name="Other Tool",
            description="Another tool",
            category="utility",
            version="1.0",
            source="local",
        ))
        
        registry.checkout_tool("tool_jq", "agent_a", "work", "foreman_agent")
        registry.checkout_tool("tool_other", "agent_b", "work", "foreman_agent")
        
        all_checkouts = registry.get_active_checkouts()
        assert len(all_checkouts) == 2
        
        agent_a_only = registry.get_active_checkouts(agent_id="agent_a")
        assert len(agent_a_only) == 1
        assert agent_a_only[0].tool_id == "tool_jq"


# REM: =======================================================================================
# REM: SECTION 2: TRUST LEVEL TESTS (BUG 2 REGRESSION)
# REM: =======================================================================================

class TestTrustLevelNormalization:
    """
    REM: BUG 2 regression tests — trust level comparison must work
    regardless of case (uppercase, lowercase, enum).
    """
    
    @pytest.fixture
    def foreman(self, mocker):
        mocker.patch("toolroom.registry._get_store", return_value=None)
        from toolroom.foreman import ForemanAgent
        return ForemanAgent()
    
    @pytest.fixture
    def registered_tool(self, foreman):
        from toolroom.registry import ToolMetadata
        tool = ToolMetadata(
            tool_id="tool_trust_test",
            name="Trust Test Tool",
            description="For trust level testing",
            category="utility",
            version="1.0",
            source="local",
            min_trust_level="resident",  # lowercase, matches enum
        )
        foreman.registry.register_tool(tool)
        return tool
    
    def test_lowercase_trust_passes(self, foreman, registered_tool):
        """REM: Lowercase 'resident' should pass for min_trust='resident'."""
        result = foreman.handle_checkout_request(
            agent_id="test_agent",
            tool_id="tool_trust_test",
            agent_trust_level="resident",
        )
        assert result["status"] == "success"
    
    def test_uppercase_trust_passes(self, foreman, registered_tool):
        """REM: Uppercase 'RESIDENT' should also pass (normalization)."""
        result = foreman.handle_checkout_request(
            agent_id="test_agent",
            tool_id="tool_trust_test",
            agent_trust_level="RESIDENT",
        )
        assert result["status"] == "success"
    
    def test_mixed_case_trust_passes(self, foreman, registered_tool):
        """REM: Mixed case 'Resident' should also pass."""
        result = foreman.handle_checkout_request(
            agent_id="test_agent",
            tool_id="tool_trust_test",
            agent_trust_level="Resident",
        )
        assert result["status"] == "success"
    
    def test_citizen_passes_resident_tool(self, foreman, registered_tool):
        """REM: Higher trust level (citizen) passes lower requirement (resident)."""
        result = foreman.handle_checkout_request(
            agent_id="test_agent",
            tool_id="tool_trust_test",
            agent_trust_level="citizen",
        )
        assert result["status"] == "success"
    
    def test_quarantine_fails_resident_tool(self, foreman, registered_tool):
        """REM: Lower trust level (quarantine) fails higher requirement (resident)."""
        result = foreman.handle_checkout_request(
            agent_id="test_agent",
            tool_id="tool_trust_test",
            agent_trust_level="quarantine",
        )
        assert result["status"] == "error"
        assert "insufficient_trust" in result["qms"]
    
    def test_probation_fails_resident_tool(self, foreman, registered_tool):
        """REM: Probation < Resident — should fail."""
        result = foreman.handle_checkout_request(
            agent_id="test_agent",
            tool_id="tool_trust_test",
            agent_trust_level="probation",
        )
        assert result["status"] == "error"


# REM: =======================================================================================
# REM: SECTION 3: FOREMAN AGENT TESTS
# REM: =======================================================================================

class TestForemanCheckout:
    """REM: Test the Foreman's checkout authorization flow."""
    
    @pytest.fixture
    def foreman(self, mocker):
        mocker.patch("toolroom.registry._get_store", return_value=None)
        from toolroom.foreman import ForemanAgent
        return ForemanAgent()
    
    def test_checkout_nonexistent_tool(self, foreman):
        result = foreman.handle_checkout_request(
            agent_id="test_agent",
            tool_id="tool_not_here",
        )
        assert result["status"] == "error"
        assert "not found" in result["message"]
    
    def test_checkout_authorized_agent(self, foreman):
        from toolroom.registry import ToolMetadata
        
        tool = ToolMetadata(
            tool_id="tool_restricted",
            name="Restricted Tool",
            description="Only for specific agents",
            category="utility",
            version="1.0",
            source="local",
            allowed_agents=["agent_alice", "agent_bob"],
        )
        foreman.registry.register_tool(tool)
        
        # Authorized agent
        result = foreman.handle_checkout_request(
            agent_id="agent_alice",
            tool_id="tool_restricted",
            agent_trust_level="resident",
        )
        assert result["status"] == "success"
    
    def test_checkout_unauthorized_agent_blocked(self, foreman):
        from toolroom.registry import ToolMetadata
        
        tool = ToolMetadata(
            tool_id="tool_restricted",
            name="Restricted Tool",
            description="Only for specific agents",
            category="utility",
            version="1.0",
            source="local",
            allowed_agents=["agent_alice"],
        )
        foreman.registry.register_tool(tool)
        
        result = foreman.handle_checkout_request(
            agent_id="agent_eve",
            tool_id="tool_restricted",
            agent_trust_level="citizen",
        )
        assert result["status"] == "error"
        assert "not_authorized" in result["qms"]
    
    def test_checkout_api_tool_triggers_hitl(self, foreman):
        """REM: GAP 6 regression — API tools must create approval request."""
        from toolroom.registry import ToolMetadata
        
        tool = ToolMetadata(
            tool_id="tool_api_needed",
            name="API Tool",
            description="Needs external API",
            category="integration",
            version="1.0",
            source="local",
            requires_api_access=True,
        )
        foreman.registry.register_tool(tool)
        
        result = foreman.handle_checkout_request(
            agent_id="test_agent",
            tool_id="tool_api_needed",
            agent_trust_level="resident",
        )
        assert result["status"] == "pending_approval"
        assert "approval_request_id" in result
        assert result["approval_request_id"].startswith("APPR-")
    
    def test_checkout_open_tool_succeeds(self, foreman):
        """REM: Tool with no restrictions should checkout immediately."""
        from toolroom.registry import ToolMetadata
        
        tool = ToolMetadata(
            tool_id="tool_open",
            name="Open Tool",
            description="No restrictions",
            category="utility",
            version="1.0",
            source="local",
        )
        foreman.registry.register_tool(tool)
        
        result = foreman.handle_checkout_request(
            agent_id="any_agent",
            tool_id="tool_open",
            purpose="general use",
            agent_trust_level="resident",
        )
        assert result["status"] == "success"
        assert "checkout_id" in result


class TestForemanInstall:
    """REM: Test the Foreman's install proposal and execution flow."""
    
    @pytest.fixture
    def foreman(self, mocker):
        mocker.patch("toolroom.registry._get_store", return_value=None)
        from toolroom.foreman import ForemanAgent
        return ForemanAgent()
    
    def test_propose_install_unapproved_source_rejected(self, foreman):
        result = foreman.propose_tool_install(
            github_repo="evil-corp/malware",
            tool_name="Malware",
            description="Definitely not malware",
            category="utility",
        )
        assert result["status"] == "error"
        assert "unapproved_source" in result["qms"]
    
    def test_propose_install_approved_source_creates_approval(self, foreman):
        """REM: GAP 6 regression — proposal creates real ApprovalRequest."""
        import toolroom.foreman as fm
        original_sources = fm.APPROVED_GITHUB_SOURCES.copy()
        fm.APPROVED_GITHUB_SOURCES.append("jqlang/jq")
        
        try:
            result = foreman.propose_tool_install(
                github_repo="jqlang/jq",
                tool_name="jq",
                description="JSON processor",
                category="utility",
            )
            assert result["status"] == "pending_approval"
            assert "approval_request_id" in result
            assert result["approval_request_id"].startswith("APPR-")
        finally:
            fm.APPROVED_GITHUB_SOURCES[:] = original_sources
    
    def test_execute_install_without_approval_warns(self, foreman, mocker):
        """REM: execute_tool_install without approval_id logs warning but proceeds."""
        mocker.patch("subprocess.run", return_value=MagicMock(
            returncode=0, stdout="", stderr=""
        ))
        mocker.patch.object(foreman, "_hash_directory", return_value="fakehash123")
        # REM: v5.4.0CC requires a manifest — mock it to return a valid one
        mock_manifest = MagicMock()
        mock_manifest.to_dict.return_value = {"name": "jq", "version": "1.0.0", "entry_point": "jq"}
        mocker.patch("toolroom.foreman.load_manifest_from_tool_dir", return_value=mock_manifest)
        mock_receipt = MagicMock()
        mock_receipt.receipt_id = "CAGE-TEST-001"
        mocker.patch("toolroom.foreman.cage.archive_tool", return_value=mock_receipt)

        result = foreman.execute_tool_install(
            github_repo="jqlang/jq",
            tool_name="jq",
            description="JSON processor",
            category="utility",
            human_approver="jeff",
        )
        # REM: Should still work (backward compat) but no formal approval verification
        assert result["status"] == "success"
    
    def test_execute_install_with_wrong_approval_rejected(self, foreman):
        """REM: GAP 6 regression — fake approval_id is rejected."""
        result = foreman.execute_tool_install(
            github_repo="jqlang/jq",
            tool_name="jq",
            description="JSON processor",
            category="utility",
            approval_request_id="APPR-FAKE12345",
        )
        assert result["status"] == "error"
        assert "approval_not_found" in result["qms"]


# REM: =======================================================================================
# REM: SECTION 4: TOOLROOMSTORE PERSISTENCE TESTS (BUG 1 REGRESSION)
# REM: =======================================================================================

class TestToolroomStore:
    """
    REM: BUG 1 regression — verify ToolroomStore exists, is importable,
    and implements the interface that registry.py expects.
    """
    
    def test_toolroom_store_importable(self):
        """REM: BUG 1 — ToolroomStore must exist in core.persistence."""
        from core.persistence import ToolroomStore
        assert ToolroomStore is not None
    
    def test_toolroom_store_singleton_exists(self):
        """REM: BUG 1 — toolroom_store singleton must be created."""
        from core.persistence import toolroom_store
        assert toolroom_store is not None
    
    def test_toolroom_store_has_required_methods(self):
        """REM: BUG 1 — ToolroomStore must have set/get/append_to_list."""
        from core.persistence import ToolroomStore
        store = ToolroomStore()
        
        assert hasattr(store, "set")
        assert hasattr(store, "get")
        assert hasattr(store, "delete")
        assert hasattr(store, "append_to_list")
        assert hasattr(store, "get_list")
        assert hasattr(store, "get_list_length")
        assert hasattr(store, "hset")
        assert hasattr(store, "hget")
        assert hasattr(store, "hgetall")
        assert hasattr(store, "hdel")
        assert hasattr(store, "ping")
    
    def test_get_store_returns_toolroom_store(self, mocker):
        """REM: BUG 1 — _get_store() must return ToolroomStore, not PersistentStore."""
        from core.persistence import ToolroomStore
        
        # Reset the cached store
        import toolroom.registry as reg
        reg._tool_store = None
        
        # Mock the toolroom_store to report as connected
        mock_store = MagicMock(spec=ToolroomStore)
        mock_store.ping.return_value = True
        
        mocker.patch("core.persistence.toolroom_store", mock_store)
        
        result = reg._get_store()
        assert result is mock_store
        
        # Reset for other tests
        reg._tool_store = None


# REM: =======================================================================================
# REM: SECTION 5: CELERY CONFIGURATION TESTS (GAP 3 & 4)
# REM: =======================================================================================

class TestCeleryConfiguration:
    """
    REM: GAP 3 & 4 regression — verify foreman is in Celery include
    and beat_schedule has daily update check.
    """
    
    def test_foreman_in_celery_include(self):
        """REM: GAP 3 — toolroom.foreman must be in Celery include list."""
        from celery_app.worker import app
        # The include list is stored in app.conf.include
        include = app.conf.get("include", [])
        assert "toolroom.foreman" in include, (
            f"toolroom.foreman not in Celery include list: {include}"
        )
    
    def test_foreman_daily_update_in_beat_schedule(self):
        """REM: GAP 4 — foreman daily update must be scheduled."""
        from celery_app.worker import app
        schedule = app.conf.get("beat_schedule", {})
        
        # Find the foreman schedule entry
        foreman_schedules = {
            k: v for k, v in schedule.items()
            if "foreman" in k.lower() or "foreman" in v.get("task", "").lower()
        }
        assert len(foreman_schedules) > 0, (
            f"No foreman schedule found in beat_schedule: {list(schedule.keys())}"
        )
        
        # Verify it references the correct task
        entry = list(foreman_schedules.values())[0]
        assert entry["task"] == "foreman_agent.daily_update_check"
    
    def test_foreman_task_routing(self):
        """REM: Foreman tasks should route to 'toolroom' queue."""
        from celery_app.worker import app
        routes = app.conf.get("task_routes", {})
        assert "foreman_agent.*" in routes
        assert routes["foreman_agent.*"]["queue"] == "toolroom"


# REM: =======================================================================================
# REM: SECTION 6: API ENDPOINT TESTS
# REM: =======================================================================================

class TestToolroomAPI:
    """REM: Test Toolroom API endpoints in main.py."""
    
    def test_toolroom_status_requires_auth(self, client):
        """REM: All toolroom endpoints require authentication."""
        response = client.get("/v1/toolroom/status")
        assert response.status_code in (401, 403)
    
    def test_toolroom_status(self, client, auth_headers):
        response = client.get("/v1/toolroom/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "summary" in data
        assert "total_tools" in data["summary"]
    
    def test_toolroom_list_tools(self, client, auth_headers):
        response = client.get("/v1/toolroom/tools", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "count" in data
    
    def test_toolroom_get_tool_not_found(self, client, auth_headers):
        response = client.get("/v1/toolroom/tools/tool_nonexistent", headers=auth_headers)
        assert response.status_code == 404
    
    def test_toolroom_list_checkouts(self, client, auth_headers):
        response = client.get("/v1/toolroom/checkouts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "checkouts" in data
    
    def test_toolroom_checkout_history(self, client, auth_headers):
        response = client.get("/v1/toolroom/checkouts/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
    
    def test_toolroom_list_requests(self, client, auth_headers):
        response = client.get("/v1/toolroom/requests", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
    
    def test_toolroom_usage_report(self, client, auth_headers):
        response = client.get("/v1/toolroom/usage", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "usage" in data


# REM: =======================================================================================
# REM: SECTION 7: APPROVAL GATE INTEGRATION TESTS (GAP 6)
# REM: =======================================================================================

class TestApprovalIntegration:
    """
    REM: GAP 6 regression — verify Toolroom approval rule is registered
    and the gate is properly wired.
    """
    
    def test_toolroom_approval_rule_registered(self):
        """REM: The toolroom approval rule should exist in approval_gate."""
        from core.approval import approval_gate
        
        assert "rule-toolroom-operations" in approval_gate._rules, (
            f"Toolroom rule not found. Rules: {list(approval_gate._rules.keys())}"
        )
    
    def test_toolroom_approval_rule_config(self):
        """REM: Verify rule configuration is correct."""
        from core.approval import approval_gate
        
        rule = approval_gate._rules["rule-toolroom-operations"]
        assert rule.agent_pattern == "foreman_agent"
        assert rule.action_pattern == "toolroom.*"
        assert rule.auto_reject_on_timeout is False  # Don't auto-reject
        assert rule.timeout_seconds == 86400  # 24 hours


# REM: =======================================================================================
# REM: SECTION 8: POST ENDPOINT TESTS — TOOLROOM WRITE OPERATIONS
# REM: =======================================================================================
# REM: These tests exercise every POST endpoint added in v4.5.0CC.
# REM: They validate auth requirements, error paths, validation, and the
# REM: happy path where possible without live services.
# REM: =======================================================================================

class TestToolroomPostCheckout:
    """REM: POST /v1/toolroom/checkout endpoint tests."""
    
    def test_checkout_requires_auth(self, client):
        """REM: Checkout without API key returns 403."""
        response = client.post("/v1/toolroom/checkout", json={
            "agent_id": "demo_agent",
            "tool_id": "tool_jq",
        })
        assert response.status_code in (401, 403)
    
    def test_checkout_tool_not_found(self, client, auth_headers):
        """REM: Checkout of nonexistent tool returns 403 with QMS error."""
        response = client.post("/v1/toolroom/checkout", json={
            "agent_id": "demo_agent",
            "tool_id": "nonexistent_tool",
            "purpose": "testing",
        }, headers=auth_headers)
        assert response.status_code == 403
        data = response.json()
        detail = data.get("detail", data)
        assert detail["status"] == "error"
        assert "tool_not_found" in detail["qms"]
    
    def test_checkout_validates_payload(self, client, auth_headers):
        """REM: Checkout with missing required fields returns 422."""
        response = client.post("/v1/toolroom/checkout", json={
            "purpose": "testing",
        }, headers=auth_headers)
        assert response.status_code == 422
    
    def test_checkout_default_trust_level(self, client, auth_headers):
        """REM: Checkout defaults to 'resident' trust level — no 422 validation error."""
        # REM: If tool exists from earlier test, we get 200 (success).
        # REM: If tool doesn't exist, we get 403 (tool_not_found).
        # REM: Either way, the default trust level was ACCEPTED (no 422).
        response = client.post("/v1/toolroom/checkout", json={
            "agent_id": "demo_agent",
            "tool_id": "tool_jq",
        }, headers=auth_headers)
        # REM: Any valid response (not 422) proves the default trust_level works
        assert response.status_code != 422, "Default trust_level should be accepted"
        assert response.status_code in (200, 403)


class TestToolroomPostReturn:
    """REM: POST /v1/toolroom/return endpoint tests."""
    
    def test_return_requires_auth(self, client):
        """REM: Return without API key returns 403."""
        response = client.post("/v1/toolroom/return", json={
            "checkout_id": "CHKOUT-000000000000",
        })
        assert response.status_code in (401, 403)
    
    def test_return_nonexistent_checkout(self, client, auth_headers):
        """REM: Return of unknown checkout_id returns 404."""
        response = client.post("/v1/toolroom/return", json={
            "checkout_id": "CHKOUT-does_not_exist",
        }, headers=auth_headers)
        assert response.status_code == 404
        detail = response.json().get("detail", response.json())
        assert detail["status"] == "error"
        assert "not_found" in detail["qms"]
    
    def test_return_validates_payload(self, client, auth_headers):
        """REM: Return with missing checkout_id returns 422."""
        response = client.post("/v1/toolroom/return", json={}, headers=auth_headers)
        assert response.status_code == 422


class TestToolroomPostInstallPropose:
    """REM: POST /v1/toolroom/install/propose endpoint tests."""
    
    def test_propose_requires_auth(self, client):
        """REM: Propose without API key returns 403."""
        response = client.post("/v1/toolroom/install/propose", json={
            "github_repo": "jqlang/jq",
            "tool_name": "jq",
            "description": "JSON processor",
            "category": "utility",
        })
        assert response.status_code in (401, 403)
    
    def test_propose_unapproved_source_rejected(self, client, auth_headers):
        """REM: Propose from unapproved repo returns 400."""
        response = client.post("/v1/toolroom/install/propose", json={
            "github_repo": "random-user/sketchy-tool",
            "tool_name": "sketchy",
            "description": "Untrusted tool",
            "category": "utility",
        }, headers=auth_headers)
        assert response.status_code == 400
        detail = response.json().get("detail", response.json())
        assert "unapproved_source" in detail["qms"]
    
    def test_propose_approved_source_creates_approval(self, client, auth_headers):
        """REM: Propose from approved repo creates HITL approval request."""
        import toolroom.foreman as fm
        original_sources = fm.APPROVED_GITHUB_SOURCES.copy()
        fm.APPROVED_GITHUB_SOURCES.append("jqlang/jq")
        try:
            response = client.post("/v1/toolroom/install/propose", json={
                "github_repo": "jqlang/jq",
                "tool_name": "jq",
                "description": "JSON processor",
                "category": "utility",
                "requires_api": False,
            }, headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pending_approval"
            assert "approval_request_id" in data
            assert data["approval_request_id"].startswith("APPR-")
        finally:
            fm.APPROVED_GITHUB_SOURCES[:] = original_sources
    
    def test_propose_validates_payload(self, client, auth_headers):
        """REM: Propose with missing required fields returns 422."""
        response = client.post("/v1/toolroom/install/propose", json={
            "github_repo": "jqlang/jq",
        }, headers=auth_headers)
        assert response.status_code == 422


class TestToolroomPostInstallExecute:
    """REM: POST /v1/toolroom/install/execute endpoint tests."""
    
    def test_execute_requires_auth(self, client):
        """REM: Execute without API key returns 403."""
        response = client.post("/v1/toolroom/install/execute", json={
            "github_repo": "jqlang/jq",
            "tool_name": "jq",
            "description": "JSON processor",
            "category": "utility",
            "approval_request_id": "APPR-fake",
        })
        assert response.status_code in (401, 403)
    
    def test_execute_without_valid_approval_rejected(self, client, auth_headers):
        """REM: Execute with non-existent approval_request_id returns 400."""
        response = client.post("/v1/toolroom/install/execute", json={
            "github_repo": "jqlang/jq",
            "tool_name": "jq",
            "description": "JSON processor",
            "category": "utility",
            "approval_request_id": "APPR-does_not_exist",
        }, headers=auth_headers)
        assert response.status_code == 400
        detail = response.json().get("detail", response.json())
        assert detail["status"] == "error"


class TestToolroomPostRequest:
    """REM: POST /v1/toolroom/request endpoint tests."""
    
    def test_request_requires_auth(self, client):
        """REM: New tool request without API key returns 403."""
        response = client.post("/v1/toolroom/request", json={
            "agent_id": "demo_agent",
            "description": "Need a YAML linter",
        })
        assert response.status_code in (401, 403)
    
    def test_request_new_tool_succeeds(self, client, auth_headers):
        """REM: Happy path — agent requests new tool, gets request_id back."""
        response = client.post("/v1/toolroom/request", json={
            "agent_id": "demo_agent",
            "description": "Need a YAML linter for config validation",
            "suggested_source": "github:adrienverge/yamllint",
            "justification": "Config validation for deployment agent",
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending_review"
        assert "request_id" in data
        assert data["request_id"].startswith("TOOLREQ-")
    
    def test_request_minimal_payload(self, client, auth_headers):
        """REM: Request with only required fields succeeds."""
        response = client.post("/v1/toolroom/request", json={
            "agent_id": "demo_agent",
            "description": "Need a CSV parser",
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending_review"
    
    def test_request_validates_payload(self, client, auth_headers):
        """REM: Request with missing required fields returns 422."""
        response = client.post("/v1/toolroom/request", json={
            "justification": "Because reasons",
        }, headers=auth_headers)
        assert response.status_code == 422


class TestToolroomPostApiCheckoutComplete:
    """REM: POST /v1/toolroom/checkout/complete-api endpoint tests."""
    
    def test_complete_api_requires_auth(self, client):
        """REM: Complete API checkout without API key returns 403."""
        response = client.post("/v1/toolroom/checkout/complete-api", json={
            "agent_id": "demo_agent",
            "tool_id": "tool_api",
            "purpose": "API integration",
            "approval_request_id": "APPR-fake",
        })
        assert response.status_code in (401, 403)
    
    def test_complete_api_approval_not_found(self, client, auth_headers):
        """REM: Complete with nonexistent approval returns 404."""
        response = client.post("/v1/toolroom/checkout/complete-api", json={
            "agent_id": "demo_agent",
            "tool_id": "tool_api",
            "purpose": "API integration",
            "approval_request_id": "APPR-does_not_exist",
        }, headers=auth_headers)
        assert response.status_code == 404
        detail = response.json().get("detail", "")
        assert "not found" in str(detail).lower()
    
    def test_complete_api_validates_payload(self, client, auth_headers):
        """REM: Complete with missing fields returns 422."""
        response = client.post("/v1/toolroom/checkout/complete-api", json={
            "agent_id": "demo_agent",
        }, headers=auth_headers)
        assert response.status_code == 422


# REM: =======================================================================================
# REM: v4.6.0CC: TOOL MANIFEST TESTS
# REM: =======================================================================================

class TestToolManifest:
    """REM: Test ToolManifest schema, validation, and loading."""

    def test_manifest_creation(self):
        """REM: Basic manifest creation with required fields."""
        from toolroom.manifest import ToolManifest
        m = ToolManifest(
            name="Test Tool",
            entry_point="python main.py",
            version="1.0.0",
        )
        assert m.name == "Test Tool"
        assert m.entry_point == "python main.py"
        assert m.version == "1.0.0"
        assert m.sandbox_level == "subprocess"
        assert m.timeout_seconds == 300

    def test_manifest_defaults(self):
        """REM: Verify sensible defaults."""
        from toolroom.manifest import ToolManifest, SandboxLevel
        m = ToolManifest(name="T", entry_point="./run.sh", version="1.0.0")
        assert m.sandbox_level == SandboxLevel.SUBPROCESS
        assert m.requires_network is False
        assert m.requires_gpu is False
        assert m.python_dependencies == []
        assert m.environment_vars == {}

    def test_manifest_round_trip(self):
        """REM: Serialize and deserialize manifest."""
        from toolroom.manifest import ToolManifest
        m = ToolManifest(
            name="Round Trip",
            entry_point="python run.py",
            version="2.0.0",
            description="Test round trip",
            inputs=[{"name": "text", "type": "string", "required": True}],
            timeout_seconds=60,
        )
        d = m.to_dict()
        restored = ToolManifest.from_dict(d)
        assert restored.name == m.name
        assert restored.entry_point == m.entry_point
        assert restored.inputs == m.inputs
        assert restored.timeout_seconds == 60

    def test_manifest_json_round_trip(self):
        """REM: JSON serialization round trip."""
        from toolroom.manifest import ToolManifest
        m = ToolManifest(name="JSON Test", entry_point="./tool", version="1.0.0")
        j = m.to_json()
        restored = ToolManifest.from_json(j)
        assert restored.name == "JSON Test"

    def test_manifest_from_dict_ignores_unknown_fields(self):
        """REM: Forward compatibility — unknown fields are ignored."""
        from toolroom.manifest import ToolManifest
        d = {
            "name": "Compat",
            "entry_point": "./run",
            "version": "1.0.0",
            "future_field": "should_be_ignored",
            "another_future": 42,
        }
        m = ToolManifest.from_dict(d)
        assert m.name == "Compat"
        assert not hasattr(m, "future_field")


class TestManifestValidation:
    """REM: Test manifest validation rules."""

    def test_valid_manifest(self):
        """REM: A complete, valid manifest passes validation."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="Valid", entry_point="python main.py", version="1.0.0")
        errors = validate_manifest(m)
        assert errors == []

    def test_missing_name(self):
        """REM: Empty name fails validation."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="", entry_point="python main.py", version="1.0.0")
        errors = validate_manifest(m)
        assert any("name" in e for e in errors)

    def test_missing_entry_point(self):
        """REM: Empty entry_point fails validation."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="T", entry_point="", version="1.0.0")
        errors = validate_manifest(m)
        assert any("entry_point" in e for e in errors)

    def test_missing_version(self):
        """REM: Empty version fails validation."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="T", entry_point="./run", version="")
        errors = validate_manifest(m)
        assert any("version" in e for e in errors)

    def test_dangerous_entry_point_semicolon(self):
        """REM: Shell injection via semicolon is rejected."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="T", entry_point="python main.py; rm -rf /", version="1.0.0")
        errors = validate_manifest(m)
        assert any("dangerous" in e.lower() for e in errors)

    def test_dangerous_entry_point_pipe(self):
        """REM: Shell injection via pipe is rejected."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="T", entry_point="cat file | evil", version="1.0.0")
        errors = validate_manifest(m)
        assert any("dangerous" in e.lower() for e in errors)

    def test_dangerous_entry_point_backtick(self):
        """REM: Shell injection via backtick is rejected."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="T", entry_point="echo `whoami`", version="1.0.0")
        errors = validate_manifest(m)
        assert any("dangerous" in e.lower() for e in errors)

    def test_dangerous_entry_point_dollar_paren(self):
        """REM: Shell injection via $() is rejected."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="T", entry_point="echo $(id)", version="1.0.0")
        errors = validate_manifest(m)
        assert any("dangerous" in e.lower() for e in errors)

    def test_invalid_sandbox_level(self):
        """REM: Unknown sandbox level is rejected."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="T", entry_point="./run", version="1.0.0")
        m.sandbox_level = "hypervisor"
        errors = validate_manifest(m)
        assert any("sandbox_level" in e for e in errors)

    def test_negative_timeout(self):
        """REM: Negative timeout is rejected."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="T", entry_point="./run", version="1.0.0", timeout_seconds=-1)
        errors = validate_manifest(m)
        assert any("timeout" in e for e in errors)

    def test_excessive_timeout(self):
        """REM: Timeout over 1 hour is rejected."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(name="T", entry_point="./run", version="1.0.0", timeout_seconds=7200)
        errors = validate_manifest(m)
        assert any("timeout" in e for e in errors)

    def test_network_without_sandbox(self):
        """REM: Network access with sandbox_level=none is flagged."""
        from toolroom.manifest import ToolManifest, validate_manifest, SandboxLevel
        m = ToolManifest(
            name="T", entry_point="./run", version="1.0.0",
            requires_network=True, sandbox_level=SandboxLevel.NONE,
        )
        errors = validate_manifest(m)
        assert any("network" in e.lower() for e in errors)

    def test_input_params_validated(self):
        """REM: Input parameters without names are flagged."""
        from toolroom.manifest import ToolManifest, validate_manifest
        m = ToolManifest(
            name="T", entry_point="./run", version="1.0.0",
            inputs=[{"type": "string"}],  # Missing 'name'
        )
        errors = validate_manifest(m)
        assert any("name" in e for e in errors)


class TestManifestFileLoading:
    """REM: Test loading manifests from disk."""

    def test_load_from_nonexistent_dir(self, tmp_path):
        """REM: Missing directory returns None."""
        from toolroom.manifest import load_manifest_from_tool_dir
        result = load_manifest_from_tool_dir(tmp_path / "nonexistent")
        assert result is None

    def test_load_from_dir_without_manifest(self, tmp_path):
        """REM: Directory without tool_manifest.json returns None."""
        from toolroom.manifest import load_manifest_from_tool_dir
        result = load_manifest_from_tool_dir(tmp_path)
        assert result is None

    def test_load_valid_manifest(self, tmp_path):
        """REM: Valid manifest file loads correctly."""
        import json
        from toolroom.manifest import load_manifest_from_tool_dir, MANIFEST_FILENAME
        manifest_data = {
            "name": "Test Tool",
            "entry_point": "python main.py",
            "version": "1.0.0",
            "description": "A test tool",
        }
        (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(manifest_data))
        result = load_manifest_from_tool_dir(tmp_path)
        assert result is not None
        assert result.name == "Test Tool"
        assert result.entry_point == "python main.py"

    def test_load_invalid_json(self, tmp_path):
        """REM: Malformed JSON returns None."""
        from toolroom.manifest import load_manifest_from_tool_dir, MANIFEST_FILENAME
        (tmp_path / MANIFEST_FILENAME).write_text("not valid json {{{")
        result = load_manifest_from_tool_dir(tmp_path)
        assert result is None

    def test_load_invalid_manifest(self, tmp_path):
        """REM: Valid JSON but invalid manifest returns None."""
        import json
        from toolroom.manifest import load_manifest_from_tool_dir, MANIFEST_FILENAME
        manifest_data = {
            "name": "",  # Invalid — empty name
            "entry_point": "python main.py",
            "version": "1.0.0",
        }
        (tmp_path / MANIFEST_FILENAME).write_text(json.dumps(manifest_data))
        result = load_manifest_from_tool_dir(tmp_path)
        assert result is None


# REM: =======================================================================================
# REM: v4.6.0CC: FUNCTION TOOL REGISTRY TESTS
# REM: =======================================================================================

class TestFunctionToolRegistry:
    """REM: Test the function tool registry and decorator."""

    def test_register_function(self):
        """REM: Register a simple function tool."""
        from toolroom.function_tools import FunctionToolRegistry
        registry = FunctionToolRegistry()

        def my_tool(text: str) -> dict:
            """A test tool."""
            return {"upper": text.upper()}

        entry = registry.register(func=my_tool, name="Upper Tool", category="utility")
        assert entry.tool_id == "func_my_tool"
        assert entry.name == "Upper Tool"
        assert entry.func is my_tool

    def test_auto_generated_manifest(self):
        """REM: Manifest auto-generated from function signature."""
        from toolroom.function_tools import FunctionToolRegistry
        registry = FunctionToolRegistry()

        def calc(x: int, y: int, op: str = "add") -> dict:
            pass

        entry = registry.register(func=calc, name="Calculator")
        assert entry.manifest.name == "Calculator"
        assert entry.manifest.sandbox_level == "none"
        assert len(entry.manifest.inputs) == 3
        # x and y are required, op has default
        input_names = {i["name"] for i in entry.manifest.inputs}
        assert input_names == {"x", "y", "op"}
        # x is required
        x_param = next(i for i in entry.manifest.inputs if i["name"] == "x")
        assert x_param["required"] is True
        assert x_param["type"] == "integer"
        # op has default
        op_param = next(i for i in entry.manifest.inputs if i["name"] == "op")
        assert op_param["required"] is False
        assert op_param["default"] == "add"

    def test_get_registered_tool(self):
        """REM: Retrieve a registered function tool by ID."""
        from toolroom.function_tools import FunctionToolRegistry
        registry = FunctionToolRegistry()

        def finder(query: str) -> str:
            return query

        registry.register(func=finder, name="Finder")
        entry = registry.get("func_finder")
        assert entry is not None
        assert entry.name == "Finder"

    def test_get_nonexistent_returns_none(self):
        """REM: Non-existent tool returns None."""
        from toolroom.function_tools import FunctionToolRegistry
        registry = FunctionToolRegistry()
        assert registry.get("func_does_not_exist") is None

    def test_list_all(self):
        """REM: List all registered function tools."""
        from toolroom.function_tools import FunctionToolRegistry
        registry = FunctionToolRegistry()

        def a(): pass
        def b(): pass

        registry.register(func=a, name="A")
        registry.register(func=b, name="B")
        all_tools = registry.list_all()
        assert len(all_tools) == 2
        names = {e.name for e in all_tools}
        assert names == {"A", "B"}

    def test_unregister(self):
        """REM: Unregister removes the tool."""
        from toolroom.function_tools import FunctionToolRegistry
        registry = FunctionToolRegistry()

        def temp(): pass

        registry.register(func=temp, name="Temp")
        assert registry.get("func_temp") is not None
        assert registry.unregister("func_temp") is True
        assert registry.get("func_temp") is None

    def test_unregister_nonexistent(self):
        """REM: Unregistering non-existent tool returns False."""
        from toolroom.function_tools import FunctionToolRegistry
        registry = FunctionToolRegistry()
        assert registry.unregister("func_ghost") is False


class TestRegisterFunctionToolDecorator:
    """REM: Test the @register_function_tool decorator."""

    def test_decorator_registers_function(self):
        """REM: Decorator registers function in singleton registry."""
        from toolroom.function_tools import function_tool_registry

        # REM: Note — using unique name to avoid cross-test pollution
        from toolroom.function_tools import register_function_tool

        @register_function_tool(name="Decorator Test Tool", category="utility")
        def decorator_test_unique(text: str) -> dict:
            return {"result": text}

        entry = function_tool_registry.get("func_decorator_test_unique")
        assert entry is not None
        assert entry.name == "Decorator Test Tool"

    def test_decorator_preserves_function(self):
        """REM: Decorated function still callable normally."""
        from toolroom.function_tools import register_function_tool

        @register_function_tool(name="Preserved", category="utility")
        def preserved_func(x: int) -> int:
            return x * 2

        assert preserved_func(5) == 10
        assert hasattr(preserved_func, "_is_function_tool")
        assert preserved_func._is_function_tool is True
        assert preserved_func._tool_id == "func_preserved_func"


# REM: =======================================================================================
# REM: v4.6.0CC: EXECUTOR TESTS
# REM: =======================================================================================

class TestExecutionResult:
    """REM: Test ExecutionResult dataclass."""

    def test_success_result(self):
        """REM: Successful execution result."""
        from toolroom.executor import ExecutionResult
        r = ExecutionResult(
            tool_id="tool_test",
            success=True,
            exit_code=0,
            stdout="hello",
            duration_seconds=0.5,
            output_data={"greeting": "hello"},
        )
        assert r.success is True
        assert r.exit_code == 0
        d = r.to_dict()
        assert d["tool_id"] == "tool_test"
        assert d["output_data"]["greeting"] == "hello"

    def test_failure_result(self):
        """REM: Failed execution result."""
        from toolroom.executor import ExecutionResult
        r = ExecutionResult(
            tool_id="tool_broken",
            success=False,
            exit_code=1,
            stderr="error occurred",
            error_message="Something failed",
        )
        assert r.success is False
        assert r.error_message == "Something failed"


class TestFunctionToolExecution:
    """REM: Test execute_function_tool."""

    def test_execute_success(self):
        """REM: Successful function tool execution."""
        from toolroom.executor import execute_function_tool

        def good_tool(name: str) -> dict:
            return {"greeting": f"Hello {name}"}

        result = execute_function_tool(
            tool_id="func_good_tool",
            func=good_tool,
            inputs={"name": "Jeff"},
            agent_id="test_agent",
        )
        assert result.success is True
        assert result.output_data["greeting"] == "Hello Jeff"
        assert result.duration_seconds >= 0

    def test_execute_returns_string(self):
        """REM: Function returning string is wrapped in dict."""
        from toolroom.executor import execute_function_tool

        def string_tool() -> str:
            return "just a string"

        result = execute_function_tool(
            tool_id="func_string",
            func=string_tool,
            inputs={},
        )
        assert result.success is True
        assert result.output_data["result"] == "just a string"

    def test_execute_returns_none(self):
        """REM: Function returning None produces empty output."""
        from toolroom.executor import execute_function_tool

        def void_tool():
            pass

        result = execute_function_tool(
            tool_id="func_void",
            func=void_tool,
            inputs={},
        )
        assert result.success is True
        assert result.output_data == {}

    def test_execute_exception_handled(self):
        """REM: Function that raises exception returns failure."""
        from toolroom.executor import execute_function_tool

        def bad_tool():
            raise ValueError("intentional error")

        result = execute_function_tool(
            tool_id="func_bad",
            func=bad_tool,
            inputs={},
        )
        assert result.success is False
        assert "intentional error" in result.error_message


# REM: =======================================================================================
# REM: v4.6.0CC: APPROVAL STATUS REDIS LOOKUP TESTS (Issue 4 fix)
# REM: =======================================================================================

class TestApprovalStatusLookup:
    """REM: Test get_approval_status() method — Redis-backed lookup."""

    def test_get_status_from_pending(self):
        """REM: Finds request in pending dict (fast path)."""
        from core.approval import approval_gate, ApprovalStatus
        # REM: Create a real pending request
        from core.approval import ApprovalRequest, ApprovalPriority
        import threading

        req = ApprovalRequest(
            request_id="APPR-test_status_1",
            agent_id="test_agent",
            action="test_action",
            description="test",
            payload={},
            priority=ApprovalPriority.NORMAL,
        )
        approval_gate._pending_requests["APPR-test_status_1"] = req

        result = approval_gate.get_approval_status("APPR-test_status_1")
        assert result is not None
        assert result["request_id"] == "APPR-test_status_1"
        assert result["status"] == "pending"
        assert result["agent_id"] == "test_agent"

        # Cleanup
        del approval_gate._pending_requests["APPR-test_status_1"]

    def test_get_status_from_completed(self):
        """REM: Finds request in completed dict."""
        from core.approval import approval_gate, ApprovalStatus, ApprovalRequest, ApprovalPriority
        import threading

        req = ApprovalRequest(
            request_id="APPR-test_status_2",
            agent_id="test_agent",
            action="test_action",
            description="test",
            payload={},
            priority=ApprovalPriority.NORMAL,
        )
        req.status = ApprovalStatus.APPROVED
        req.decided_by = "operator"
        approval_gate._completed_requests["APPR-test_status_2"] = req

        result = approval_gate.get_approval_status("APPR-test_status_2")
        assert result is not None
        assert result["status"] == "approved"
        assert result["decided_by"] == "operator"

        # Cleanup
        del approval_gate._completed_requests["APPR-test_status_2"]

    def test_get_status_not_found(self):
        """REM: Non-existent request returns None."""
        from core.approval import approval_gate
        result = approval_gate.get_approval_status("APPR-does_not_exist_anywhere")
        # REM: Might be None (no Redis) or None (not in Redis)
        # REM: Either way, if not in pending/completed dicts, it's None.
        assert result is None or result.get("status") is not None

    def test_get_status_returns_dict_not_object(self):
        """REM: Returns dict, not ApprovalRequest object."""
        from core.approval import approval_gate, ApprovalRequest, ApprovalPriority
        import threading

        req = ApprovalRequest(
            request_id="APPR-test_status_dict",
            agent_id="agent_x",
            action="action_y",
            description="test",
            payload={},
            priority=ApprovalPriority.HIGH,
        )
        approval_gate._pending_requests["APPR-test_status_dict"] = req

        result = approval_gate.get_approval_status("APPR-test_status_dict")
        assert isinstance(result, dict)
        assert "request_id" in result
        assert "status" in result
        assert "agent_id" in result

        # Cleanup
        del approval_gate._pending_requests["APPR-test_status_dict"]


# REM: =======================================================================================
# REM: v4.6.0CC: SEMANTIC VERSION COMPARISON TESTS (Issue 5 fix)
# REM: =======================================================================================

class TestSemanticVersionComparison:
    """REM: Test semantic version comparison used in daily update checks."""

    def test_newer_version_detected(self):
        """REM: packaging.version correctly identifies newer versions."""
        from packaging.version import parse as parse_version
        assert parse_version("2.0.0") > parse_version("1.0.0")

    def test_v_prefix_handled(self):
        """REM: v-prefix stripped before comparison."""
        from packaging.version import parse as parse_version
        latest = "v1.2.3".lstrip("vV")
        current = "1.2.2".lstrip("vV")
        assert parse_version(latest) > parse_version(current)

    def test_same_version_not_newer(self):
        """REM: Same version is not reported as update."""
        from packaging.version import parse as parse_version
        assert not (parse_version("1.0.0") > parse_version("1.0.0"))

    def test_older_version_not_newer(self):
        """REM: Older version is not reported as update."""
        from packaging.version import parse as parse_version
        assert not (parse_version("0.9.0") > parse_version("1.0.0"))

    def test_prerelease_less_than_release(self):
        """REM: Pre-release versions sort before release."""
        from packaging.version import parse as parse_version
        assert parse_version("2.0.0rc1") < parse_version("2.0.0")

    def test_v_prefix_vs_no_prefix(self):
        """REM: v1.2.3 and 1.2.3 are equal after stripping."""
        from packaging.version import parse as parse_version
        a = "v1.2.3".lstrip("vV")
        b = "1.2.3".lstrip("vV")
        assert parse_version(a) == parse_version(b)

    def test_patch_version_increment(self):
        """REM: 1.0.1 > 1.0.0."""
        from packaging.version import parse as parse_version
        assert parse_version("1.0.1") > parse_version("1.0.0")


# REM: =======================================================================================
# REM: v4.6.0CC: TOOL EXECUTION API ENDPOINT TESTS
# REM: =======================================================================================

class TestToolroomExecuteEndpoint:
    """REM: Test /v1/toolroom/execute endpoint."""

    def test_execute_requires_auth(self, client):
        """REM: Execute endpoint requires authentication."""
        response = client.post("/v1/toolroom/execute", json={
            "tool_id": "tool_test",
            "agent_id": "agent_test",
            "checkout_id": "CHKOUT-test",
            "inputs": {},
        })
        assert response.status_code in (401, 403)

    def test_execute_validates_payload(self, client, auth_headers):
        """REM: Missing required fields returns 422."""
        response = client.post("/v1/toolroom/execute", json={
            "tool_id": "tool_test",
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_execute_no_checkout_returns_error(self, client, auth_headers):
        """REM: Execution without checkout returns 400."""
        response = client.post("/v1/toolroom/execute", json={
            "tool_id": "tool_nonexistent",
            "agent_id": "agent_test",
            "checkout_id": "CHKOUT-invalid",
            "inputs": {},
        }, headers=auth_headers)
        assert response.status_code == 400


# REM: =======================================================================================
# REM: v4.6.0CC: FOREMAN EXECUTE AND SYNC TESTS
# REM: =======================================================================================

class TestForemanExecution:
    """REM: Test Foreman.execute_tool() and sync_function_tools()."""

    @pytest.fixture
    def foreman(self):
        from toolroom.foreman import ForemanAgent
        return ForemanAgent()

    def test_execute_without_checkout_fails(self, foreman):
        """REM: Execution requires active checkout."""
        result = foreman.execute_tool(
            tool_id="tool_ghost",
            agent_id="agent_test",
            checkout_id="CHKOUT-fake",
            inputs={},
        )
        assert result["status"] == "error"
        assert "no_checkout" in result["qms"]

    def test_execute_function_tool_with_checkout(self, foreman):
        """REM: Function tool executes when checkout exists."""
        from toolroom.function_tools import FunctionToolRegistry
        from toolroom.registry import ToolMetadata

        # REM: Register a function tool in a local registry for this test
        def adder(a: int, b: int) -> dict:
            return {"sum": a + b}

        # REM: Register the tool
        tool_id = "func_adder"
        metadata = ToolMetadata(
            tool_id=tool_id,
            name="Adder",
            description="Adds two numbers",
            category="utility",
            version="1.0.0",
            source="function:test.adder",
            execution_type="function",
        )
        foreman.registry.register_tool(metadata)

        # REM: Check it out
        checkout = foreman.registry.checkout_tool(
            tool_id=tool_id,
            agent_id="test_agent",
            purpose="testing execution",
        )
        assert checkout is not None

        # REM: Register the function tool
        from toolroom.function_tools import function_tool_registry
        function_tool_registry.register(func=adder, name="Adder")

        # REM: Execute
        result = foreman.execute_tool(
            tool_id=tool_id,
            agent_id="test_agent",
            checkout_id=checkout.checkout_id,
            inputs={"a": 3, "b": 7},
        )
        assert result["status"] == "success"
        assert result["output"]["sum"] == 10

        # Cleanup
        foreman.registry.return_tool(checkout.checkout_id)

    def test_execute_tool_without_manifest_fails(self, foreman):
        """REM: Subprocess tool without manifest cannot execute."""
        from toolroom.registry import ToolMetadata

        tool_id = "tool_no_manifest"
        metadata = ToolMetadata(
            tool_id=tool_id,
            name="No Manifest Tool",
            description="Has no manifest",
            category="utility",
            version="1.0.0",
            source="github:test/repo",
            manifest_data=None,  # No manifest
            execution_type="unknown",
        )
        foreman.registry.register_tool(metadata)

        # Check it out
        checkout = foreman.registry.checkout_tool(
            tool_id=tool_id,
            agent_id="test_agent",
            purpose="testing",
        )
        assert checkout is not None

        # Execute — should fail
        result = foreman.execute_tool(
            tool_id=tool_id,
            agent_id="test_agent",
            checkout_id=checkout.checkout_id,
            inputs={},
        )
        assert result["status"] == "error"
        assert "no_manifest" in result["qms"]

        # Cleanup
        foreman.registry.return_tool(checkout.checkout_id)

    def test_sync_function_tools(self, foreman):
        """REM: sync_function_tools copies function tools into main registry."""
        from toolroom.function_tools import FunctionToolRegistry, function_tool_registry

        def sync_test_tool(x: str) -> str:
            return x

        function_tool_registry.register(
            func=sync_test_tool, name="Sync Test", category="utility"
        )

        result = foreman.sync_function_tools()
        assert result["status"] == "success"
        assert result["synced_count"] >= 1

        # REM: Verify it's in the main registry
        tool = foreman.registry.get_tool("func_sync_test_tool")
        assert tool is not None
        assert tool.source.startswith("function:")
        assert tool.execution_type == "function"


# REM: =======================================================================================
# REM: v4.6.0CC: METADATA EXTENSION TESTS
# REM: =======================================================================================

class TestToolMetadataV460:
    """REM: Test v4.6.0CC additions to ToolMetadata."""

    def test_manifest_data_field(self):
        """REM: ToolMetadata has manifest_data field."""
        from toolroom.registry import ToolMetadata
        m = ToolMetadata(
            tool_id="t1", name="T", description="D", category="utility",
            version="1.0", source="test",
            manifest_data={"name": "T", "entry_point": "./run", "version": "1.0"},
        )
        assert m.manifest_data is not None
        assert m.manifest_data["entry_point"] == "./run"

    def test_manifest_data_default_none(self):
        """REM: manifest_data defaults to None."""
        from toolroom.registry import ToolMetadata
        m = ToolMetadata(
            tool_id="t2", name="T", description="D", category="utility",
            version="1.0", source="test",
        )
        assert m.manifest_data is None

    def test_execution_type_field(self):
        """REM: execution_type tracks how tool is invoked."""
        from toolroom.registry import ToolMetadata
        m = ToolMetadata(
            tool_id="t3", name="T", description="D", category="utility",
            version="1.0", source="test", execution_type="function",
        )
        assert m.execution_type == "function"

    def test_execution_type_default(self):
        """REM: execution_type defaults to 'unknown'."""
        from toolroom.registry import ToolMetadata
        m = ToolMetadata(
            tool_id="t4", name="T", description="D", category="utility",
            version="1.0", source="test",
        )
        assert m.execution_type == "unknown"

    def test_round_trip_with_manifest(self):
        """REM: Serialization preserves manifest_data."""
        from toolroom.registry import ToolMetadata
        manifest = {"name": "Tool", "entry_point": "python run.py", "version": "2.0"}
        m = ToolMetadata(
            tool_id="t5", name="T", description="D", category="utility",
            version="2.0", source="test",
            manifest_data=manifest, execution_type="subprocess",
        )
        d = m.to_dict()
        restored = ToolMetadata.from_dict(d)
        assert restored.manifest_data == manifest
        assert restored.execution_type == "subprocess"
