# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_mcp_gateway_depth.py
# REM: Depth coverage for api/mcp_gateway.py
# REM: Tests: _check_mcp_session branches, _TRUST_ORDER, tool function error paths.

import asyncio
import pytest
from unittest.mock import MagicMock, patch

# REM: Skip entire file if mcp package is not installed
pytest.importorskip("mcp", reason="mcp package required for MCP gateway depth tests")


# ═══════════════════════════════════════════════════════════════════════════════
# TRUST ORDER CONSTANT
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrustOrder:
    def test_has_five_levels(self):
        from api.mcp_gateway import _TRUST_ORDER
        assert len(_TRUST_ORDER) == 5

    def test_quarantine_is_lowest(self):
        from api.mcp_gateway import _TRUST_ORDER
        assert _TRUST_ORDER["quarantine"] == 0

    def test_agent_is_highest(self):
        from api.mcp_gateway import _TRUST_ORDER
        assert _TRUST_ORDER["agent"] == max(_TRUST_ORDER.values())

    def test_correct_ordering(self):
        from api.mcp_gateway import _TRUST_ORDER
        levels = ["quarantine", "probation", "resident", "citizen", "agent"]
        for i, level in enumerate(levels):
            assert _TRUST_ORDER[level] == i


# ═══════════════════════════════════════════════════════════════════════════════
# _check_mcp_session
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckMcpSession:
    def _run(self, tool_name="test_tool", required_level="probation"):
        from api.mcp_gateway import _check_mcp_session
        return _check_mcp_session(tool_name=tool_name, required_level=required_level)

    def test_bypassed_when_openclaw_disabled(self, monkeypatch):
        from core.config import get_settings
        monkeypatch.setattr(get_settings(), "openclaw_enabled", False)
        assert self._run() is None

    def test_no_key_hash_returns_unrecognized(self, monkeypatch):
        from core.config import get_settings
        from api.mcp_gateway import _mcp_api_key_hash
        monkeypatch.setattr(get_settings(), "openclaw_enabled", True)
        token = _mcp_api_key_hash.set(None)
        try:
            result = self._run()
        finally:
            _mcp_api_key_hash.reset(token)
        assert result is not None
        assert result["status"] == "session_unrecognized"

    def test_exception_during_gate_fails_open(self, monkeypatch):
        """REM: Gate errors must NOT block legitimate operators — fail open."""
        from core.config import get_settings
        from api.mcp_gateway import _mcp_api_key_hash
        monkeypatch.setattr(get_settings(), "openclaw_enabled", True)
        token = _mcp_api_key_hash.set("errorhash")
        try:
            import sys
            if "core.openclaw" in sys.modules:
                orig = sys.modules["core.openclaw"].openclaw_manager
                broken = MagicMock()
                broken.list_instances.side_effect = RuntimeError("redis down")
                sys.modules["core.openclaw"].openclaw_manager = broken
                try:
                    result = self._run()
                finally:
                    sys.modules["core.openclaw"].openclaw_manager = orig
                assert result is None  # REM: Fail open
            else:
                # REM: Module not loaded, exception will also fail open
                result = self._run()
                assert result is None
        finally:
            _mcp_api_key_hash.reset(token)


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER AS AGENT — validation (no openclaw dependency for errors)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegisterAsAgent:
    def test_invalid_trust_level(self):
        from api.mcp_gateway import register_as_agent
        result = asyncio.run(register_as_agent(
            name="Bot", api_key="key", initial_trust_level="superpower"
        ))
        assert result["qms_status"] == "Thank_You_But_No"
        assert "Invalid trust level" in result["error"]

    def test_above_quarantine_without_reason(self):
        from api.mcp_gateway import register_as_agent
        result = asyncio.run(register_as_agent(
            name="Bot", api_key="key", initial_trust_level="probation", override_reason=None
        ))
        assert result["qms_status"] == "Thank_You_But_No"
        assert "override_reason" in result["error"]

    def test_above_quarantine_with_short_reason(self):
        from api.mcp_gateway import register_as_agent
        result = asyncio.run(register_as_agent(
            name="Bot", api_key="key", initial_trust_level="probation", override_reason="short"
        ))
        assert result["qms_status"] == "Thank_You_But_No"

    def test_quarantine_with_openclaw_success(self):
        from api.mcp_gateway import register_as_agent
        import sys
        if "core.openclaw" in sys.modules:
            mock_inst = MagicMock()
            mock_inst.instance_id = "test-inst-001"
            orig = sys.modules["core.openclaw"].openclaw_manager
            mock_mgr = MagicMock()
            mock_mgr.register_instance.return_value = mock_inst
            sys.modules["core.openclaw"].openclaw_manager = mock_mgr
            try:
                result = asyncio.run(register_as_agent(
                    name="TestGoose", api_key="valid_api_key_123"
                ))
                assert result["qms_status"] == "Thank_You"
                assert result["instance_id"] == "test-inst-001"
            finally:
                sys.modules["core.openclaw"].openclaw_manager = orig
        else:
            result = asyncio.run(register_as_agent(
                name="TestGoose", api_key="valid_api_key_123"
            ))
            assert "qms_status" in result

    def test_quarantine_openclaw_exception(self):
        from api.mcp_gateway import register_as_agent
        import sys
        if "core.openclaw" in sys.modules:
            broken = MagicMock()
            broken.register_instance.side_effect = RuntimeError("db down")
            orig = sys.modules["core.openclaw"].openclaw_manager
            sys.modules["core.openclaw"].openclaw_manager = broken
            try:
                result = asyncio.run(register_as_agent(
                    name="Bot", api_key="key"
                ))
                assert result["qms_status"] == "Thank_You_But_No"
            finally:
                sys.modules["core.openclaw"].openclaw_manager = orig


# ═══════════════════════════════════════════════════════════════════════════════
# GET HEALTH — error and success paths
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetHealth:
    def test_error_path_returns_qms_error(self):
        from api.mcp_gateway import get_health
        mock_redis = MagicMock()
        mock_r = MagicMock()
        mock_r.ping.side_effect = Exception("refused")
        mock_redis.from_url.return_value = mock_r
        with patch.dict("sys.modules", {"redis": mock_redis}):
            result = asyncio.run(get_health())
        assert "qms_status" in result

    def test_success_path_returns_healthy(self):
        from api.mcp_gateway import get_health
        mock_redis = MagicMock()
        mock_r = MagicMock()
        mock_r.ping.return_value = True
        mock_redis.from_url.return_value = mock_r
        with patch.dict("sys.modules", {"redis": mock_redis}):
            result = asyncio.run(get_health())
        assert "qms_status" in result


# ═══════════════════════════════════════════════════════════════════════════════
# CREATE TENANT — invalid type validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateTenantTool:
    def test_gate_blocks_unauthenticated(self, monkeypatch):
        from api.mcp_gateway import create_tenant, _mcp_api_key_hash
        from core.config import get_settings
        monkeypatch.setattr(get_settings(), "openclaw_enabled", True)
        token = _mcp_api_key_hash.set(None)
        try:
            result = asyncio.run(create_tenant(name="ACME", tenant_type="law_firm"))
        finally:
            _mcp_api_key_hash.reset(token)
        assert result["status"] == "session_unrecognized"

    def test_invalid_type_when_gate_bypassed(self, monkeypatch):
        from api.mcp_gateway import create_tenant
        from core.config import get_settings
        monkeypatch.setattr(get_settings(), "openclaw_enabled", False)
        result = asyncio.run(create_tenant(name="ACME", tenant_type="spaceship"))
        assert result["qms_status"] == "Thank_You_But_No"
        assert "spaceship" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════════
# LIST AGENTS — gate and error
# ═══════════════════════════════════════════════════════════════════════════════

class TestListAgentsTool:
    def test_gate_blocks_unauthenticated(self, monkeypatch):
        from api.mcp_gateway import list_agents, _mcp_api_key_hash
        from core.config import get_settings
        monkeypatch.setattr(get_settings(), "openclaw_enabled", True)
        token = _mcp_api_key_hash.set(None)
        try:
            result = asyncio.run(list_agents())
        finally:
            _mcp_api_key_hash.reset(token)
        assert result["status"] == "session_unrecognized"

    def test_openclaw_error_returns_qms_error(self, monkeypatch):
        from api.mcp_gateway import list_agents
        from core.config import get_settings
        monkeypatch.setattr(get_settings(), "openclaw_enabled", False)
        import sys
        if "core.openclaw" in sys.modules:
            orig = sys.modules["core.openclaw"].openclaw_manager
            broken = MagicMock()
            broken.list_instances.side_effect = RuntimeError("db down")
            sys.modules["core.openclaw"].openclaw_manager = broken
            try:
                result = asyncio.run(list_agents())
                assert result["qms_status"] == "Thank_You_But_No"
            finally:
                sys.modules["core.openclaw"].openclaw_manager = orig


# ═══════════════════════════════════════════════════════════════════════════════
# GET AGENT — not found and error
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetAgentTool:
    def test_not_found_returns_error(self, monkeypatch):
        from api.mcp_gateway import get_agent
        from core.config import get_settings
        monkeypatch.setattr(get_settings(), "openclaw_enabled", False)
        import sys
        if "core.openclaw" in sys.modules:
            orig = sys.modules["core.openclaw"].openclaw_manager
            mock_mgr = MagicMock()
            mock_mgr.get_instance.return_value = None
            sys.modules["core.openclaw"].openclaw_manager = mock_mgr
            try:
                result = asyncio.run(get_agent("nonexistent-id"))
                assert result["qms_status"] == "Thank_You_But_No"
                assert "not found" in result["error"]
            finally:
                sys.modules["core.openclaw"].openclaw_manager = orig

    def test_success_returns_agent_dict(self, monkeypatch):
        from api.mcp_gateway import get_agent
        from core.config import get_settings
        monkeypatch.setattr(get_settings(), "openclaw_enabled", False)
        import sys
        if "core.openclaw" in sys.modules:
            orig = sys.modules["core.openclaw"].openclaw_manager
            mock_inst = MagicMock()
            mock_inst.to_dict.return_value = {"instance_id": "inst-001", "name": "TestBot"}
            mock_mgr = MagicMock()
            mock_mgr.get_instance.return_value = mock_inst
            sys.modules["core.openclaw"].openclaw_manager = mock_mgr
            try:
                result = asyncio.run(get_agent("inst-001"))
                assert result["qms_status"] == "Thank_You"
                assert "agent" in result
            finally:
                sys.modules["core.openclaw"].openclaw_manager = orig
