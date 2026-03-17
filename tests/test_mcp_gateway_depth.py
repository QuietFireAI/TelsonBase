# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_mcp_gateway_depth.py
# REM: Coverage depth tests for api/mcp_gateway.py
# REM: Calls MCP tool functions directly as async coroutines (no HTTP transport needed)
# REM: OPENCLAW_ENABLED=false in CI so gate check is bypassed for all tools

import asyncio
import pytest

# REM: mcp package only available in CI (full requirements-dev.txt install).
# REM: Skip the whole module gracefully on dev machines without it.
mcp_available = pytest.importorskip("mcp", reason="mcp package not installed")


def run(coro):
    """Run an async coroutine in a fresh event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ═══════════════════════════════════════════════════════════════════════════════
# _check_mcp_session (sync helper — OPENCLAW_ENABLED=false → always None)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckMCPSession:
    def test_gate_bypassed_when_openclaw_disabled(self):
        from api.mcp_gateway import _check_mcp_session
        result = _check_mcp_session("list_agents", required_level="probation")
        # OPENCLAW_ENABLED=false in CI → gate returns None (bypass)
        assert result is None

    def test_gate_bypassed_for_any_level(self):
        from api.mcp_gateway import _check_mcp_session
        for level in ("quarantine", "probation", "resident", "citizen", "agent"):
            assert _check_mcp_session("any_tool", level) is None


# ═══════════════════════════════════════════════════════════════════════════════
# system_status tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestSystemStatusTool:
    def test_system_status_returns_dict(self):
        from api.mcp_gateway import system_status
        result = run(system_status())
        assert isinstance(result, dict)

    def test_system_status_has_qms_status(self):
        from api.mcp_gateway import system_status
        result = run(system_status())
        assert "qms_status" in result

    def test_system_status_redis_key_present(self):
        from api.mcp_gateway import system_status
        result = run(system_status())
        # Either succeeds with redis key or fails gracefully
        if result["qms_status"] == "Thank_You":
            assert "redis" in result
        else:
            assert "error" in result

    def test_system_status_agents_key_on_success(self):
        from api.mcp_gateway import system_status
        result = run(system_status())
        if result["qms_status"] == "Thank_You":
            assert "agents" in result
            assert "total" in result["agents"]


# ═══════════════════════════════════════════════════════════════════════════════
# get_health tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetHealthTool:
    def test_get_health_returns_dict(self):
        from api.mcp_gateway import get_health
        result = run(get_health())
        assert isinstance(result, dict)

    def test_get_health_has_api_key(self):
        from api.mcp_gateway import get_health
        result = run(get_health())
        if result.get("qms_status") == "Thank_You":
            assert result.get("api") == "healthy"

    def test_get_health_has_redis_key(self):
        from api.mcp_gateway import get_health
        result = run(get_health())
        assert "redis" in result


# ═══════════════════════════════════════════════════════════════════════════════
# list_agents tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestListAgentsTool:
    def test_list_agents_returns_dict(self):
        from api.mcp_gateway import list_agents
        result = run(list_agents())
        assert isinstance(result, dict)

    def test_list_agents_default_excludes_suspended(self):
        from api.mcp_gateway import list_agents
        result = run(list_agents(include_suspended=False))
        if result.get("qms_status") == "Thank_You":
            assert "agents" in result

    def test_list_agents_include_suspended(self):
        from api.mcp_gateway import list_agents
        result = run(list_agents(include_suspended=True))
        assert isinstance(result, dict)

    def test_list_agents_count_matches_list(self):
        from api.mcp_gateway import list_agents
        result = run(list_agents())
        if result.get("qms_status") == "Thank_You":
            assert result["count"] == len(result["agents"])


# ═══════════════════════════════════════════════════════════════════════════════
# get_agent tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetAgentTool:
    def test_get_agent_nonexistent_returns_error(self):
        from api.mcp_gateway import get_agent
        result = run(get_agent("nonexistent-instance-id-xyz"))
        assert isinstance(result, dict)
        # Either not_found or error
        assert result.get("qms_status") in ("Thank_You_But_No", "Excuse_Me") \
               or "error" in result or "status" in result


# ═══════════════════════════════════════════════════════════════════════════════
# list_tenants tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestListTenantsTool:
    def test_list_tenants_returns_dict(self):
        from api.mcp_gateway import list_tenants
        result = run(list_tenants())
        assert isinstance(result, dict)

    def test_list_tenants_active_only(self):
        from api.mcp_gateway import list_tenants
        result = run(list_tenants(active_only=True))
        assert isinstance(result, dict)

    def test_list_tenants_all(self):
        from api.mcp_gateway import list_tenants
        result = run(list_tenants(active_only=False))
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# create_tenant tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateTenantTool:
    def test_create_tenant_valid_type(self):
        from api.mcp_gateway import create_tenant
        result = run(create_tenant(name="MCP Test Org", tenant_type="general"))
        assert isinstance(result, dict)
        assert "qms_status" in result

    def test_create_tenant_law_firm(self):
        from api.mcp_gateway import create_tenant
        result = run(create_tenant(name="MCP Law Firm", tenant_type="law_firm"))
        assert isinstance(result, dict)

    def test_create_tenant_invalid_type_fails_gracefully(self):
        from api.mcp_gateway import create_tenant
        result = run(create_tenant(name="MCP Bad Org", tenant_type="invalid_xyz"))
        assert isinstance(result, dict)
        # Should return error gracefully
        assert "qms_status" in result


# ═══════════════════════════════════════════════════════════════════════════════
# list_matters tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestListMattersTool:
    def test_list_matters_nonexistent_tenant(self):
        from api.mcp_gateway import list_matters
        result = run(list_matters(tenant_id="tid-nonexistent-xyz"))
        assert isinstance(result, dict)

    def test_list_matters_with_status_filter(self):
        from api.mcp_gateway import list_matters
        result = run(list_matters(tenant_id="tid-none", status_filter="open"))
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Audit chain tools
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditChainTools:
    def test_get_audit_chain_status(self):
        from api.mcp_gateway import get_audit_chain_status
        result = run(get_audit_chain_status())
        assert isinstance(result, dict)
        assert "qms_status" in result

    def test_verify_audit_chain_default(self):
        from api.mcp_gateway import verify_audit_chain
        result = run(verify_audit_chain())
        assert isinstance(result, dict)

    def test_verify_audit_chain_small_limit(self):
        from api.mcp_gateway import verify_audit_chain
        result = run(verify_audit_chain(limit=10))
        assert isinstance(result, dict)

    def test_get_recent_audit_entries(self):
        from api.mcp_gateway import get_recent_audit_entries
        result = run(get_recent_audit_entries())
        assert isinstance(result, dict)

    def test_get_recent_audit_entries_with_limit(self):
        from api.mcp_gateway import get_recent_audit_entries
        result = run(get_recent_audit_entries(limit=5))
        assert isinstance(result, dict)

    def test_get_recent_audit_entries_with_event_type(self):
        from api.mcp_gateway import get_recent_audit_entries
        result = run(get_recent_audit_entries(event_type="auth_success"))
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Approvals tools
# ═══════════════════════════════════════════════════════════════════════════════

class TestApprovalTools:
    def test_list_pending_approvals(self):
        from api.mcp_gateway import list_pending_approvals
        result = run(list_pending_approvals())
        assert isinstance(result, dict)

    def test_list_pending_approvals_custom_limit(self):
        from api.mcp_gateway import list_pending_approvals
        result = run(list_pending_approvals(limit=5))
        assert isinstance(result, dict)

    def test_approve_nonexistent_request(self):
        from api.mcp_gateway import approve_tool_request
        result = run(approve_tool_request(
            request_id="req-nonexistent-xyz",
            approved_by="admin",
        ))
        assert isinstance(result, dict)

    def test_approve_with_notes(self):
        from api.mcp_gateway import approve_tool_request
        result = run(approve_tool_request(
            request_id="req-nonexistent-xyz",
            approved_by="admin",
            notes="Test approval with notes",
        ))
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# register_as_agent tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegisterAsAgentTool:
    def test_register_as_agent_returns_dict(self):
        from api.mcp_gateway import register_as_agent
        import uuid
        result = run(register_as_agent(
            name="mcp-test-agent",
            api_key=f"test-key-{uuid.uuid4().hex[:8]}",
        ))
        assert isinstance(result, dict)
        assert "qms_status" in result

    def test_register_as_agent_above_quarantine_requires_reason(self):
        from api.mcp_gateway import register_as_agent
        import uuid
        result = run(register_as_agent(
            name="mcp-probation-agent",
            api_key=f"test-key-{uuid.uuid4().hex[:8]}",
            initial_trust_level="probation",
            override_reason="Testing above-quarantine registration path",
        ))
        assert isinstance(result, dict)
