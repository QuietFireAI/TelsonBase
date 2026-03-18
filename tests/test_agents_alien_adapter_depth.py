# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_agents_alien_adapter_depth.py
# REM: Depth tests for agents/alien_adapter.py — pure in-memory, no external deps

import sys
from unittest.mock import MagicMock, patch

# REM: celery not installed locally — stub before agents package import
# REM: shared_task must be identity decorator so @shared_task functions remain directly callable
if "celery" not in sys.modules:
    celery_mock = MagicMock()
    celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = celery_mock

import pytest
from datetime import datetime, timezone

import agents.alien_adapter as alien_module
from agents.alien_adapter import (
    AlienStatus,
    AlienAgent,
    ALIEN_CAPABILITIES,
    get_alien,
    list_aliens,
    promote_alien,
    revoke_alien,
    LangChainAdapter,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _clear_registry():
    """REM: Clear the in-memory alien registry between tests."""
    alien_module._ALIEN_REGISTRY.clear()
    yield
    alien_module._ALIEN_REGISTRY.clear()


def _add_alien(alien_id: str = "alien_test_abc12345", framework: str = "langchain",
               name: str = "Test Alien", status: AlienStatus = AlienStatus.QUARANTINE) -> AlienAgent:
    """Helper to inject a minimal AlienAgent directly into the registry."""
    alien = AlienAgent(
        alien_id=alien_id,
        framework=framework,
        name=name,
        description="",
        status=status,
        capabilities=ALIEN_CAPABILITIES[status].copy(),
    )
    alien_module._ALIEN_REGISTRY[alien_id] = alien
    return alien


# ═══════════════════════════════════════════════════════════════════════════════
# AlienStatus enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlienStatus:
    def test_quarantine_value(self):
        assert AlienStatus.QUARANTINE.value == "quarantine"

    def test_probation_value(self):
        assert AlienStatus.PROBATION.value == "probation"

    def test_resident_value(self):
        assert AlienStatus.RESIDENT.value == "resident"

    def test_citizen_value(self):
        assert AlienStatus.CITIZEN.value == "citizen"

    def test_four_statuses(self):
        assert len(AlienStatus) == 4

    def test_is_str_enum(self):
        assert AlienStatus.QUARANTINE == "quarantine"


# ═══════════════════════════════════════════════════════════════════════════════
# ALIEN_CAPABILITIES constant
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlienCapabilities:
    def test_has_four_status_levels(self):
        assert len(ALIEN_CAPABILITIES) == 4

    def test_quarantine_has_filesystem_read(self):
        caps = ALIEN_CAPABILITIES[AlienStatus.QUARANTINE]
        assert any("filesystem.read" in c for c in caps)

    def test_quarantine_has_no_external(self):
        caps = ALIEN_CAPABILITIES[AlienStatus.QUARANTINE]
        assert any("external.none" in c for c in caps)

    def test_probation_can_write_sandbox(self):
        caps = ALIEN_CAPABILITIES[AlienStatus.PROBATION]
        assert any("filesystem.write" in c for c in caps)

    def test_resident_has_data_read(self):
        caps = ALIEN_CAPABILITIES[AlienStatus.RESIDENT]
        assert any("filesystem.read:/data/*" in c for c in caps)

    def test_citizen_has_full_filesystem(self):
        caps = ALIEN_CAPABILITIES[AlienStatus.CITIZEN]
        assert any("filesystem.*" in c for c in caps)

    def test_citizen_has_full_external(self):
        caps = ALIEN_CAPABILITIES[AlienStatus.CITIZEN]
        assert any("external.*" in c for c in caps)

    def test_all_statuses_have_caps(self):
        for status in AlienStatus:
            assert len(ALIEN_CAPABILITIES[status]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# AlienAgent dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlienAgent:
    def test_default_status_quarantine(self):
        a = AlienAgent(alien_id="x", framework="lc", name="X", description="")
        assert a.status == AlienStatus.QUARANTINE

    def test_default_request_count_zero(self):
        a = AlienAgent(alien_id="x", framework="lc", name="X", description="")
        assert a.request_count == 0

    def test_default_blocked_count_zero(self):
        a = AlienAgent(alien_id="x", framework="lc", name="X", description="")
        assert a.blocked_count == 0

    def test_default_last_activity_none(self):
        a = AlienAgent(alien_id="x", framework="lc", name="X", description="")
        assert a.last_activity is None

    def test_default_vetted_by_none(self):
        a = AlienAgent(alien_id="x", framework="lc", name="X", description="")
        assert a.vetted_by is None

    def test_default_notes_empty(self):
        a = AlienAgent(alien_id="x", framework="lc", name="X", description="")
        assert a.notes == ""

    def test_capabilities_default_empty(self):
        a = AlienAgent(alien_id="x", framework="lc", name="X", description="")
        assert a.capabilities == []

    def test_registered_at_is_datetime(self):
        a = AlienAgent(alien_id="x", framework="lc", name="X", description="")
        assert isinstance(a.registered_at, datetime)


# ═══════════════════════════════════════════════════════════════════════════════
# get_alien
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetAlien:
    def test_returns_none_for_unknown(self):
        assert get_alien("alien_nonexistent") is None

    def test_returns_alien_when_registered(self):
        alien = _add_alien()
        result = get_alien(alien.alien_id)
        assert result is alien

    def test_returns_correct_alien_from_multiple(self):
        a1 = _add_alien(alien_id="alien_a")
        a2 = _add_alien(alien_id="alien_b")
        assert get_alien("alien_a") is a1
        assert get_alien("alien_b") is a2


# ═══════════════════════════════════════════════════════════════════════════════
# list_aliens
# ═══════════════════════════════════════════════════════════════════════════════

class TestListAliens:
    def test_empty_when_registry_empty(self):
        assert list_aliens() == []

    def test_returns_all_when_no_filter(self):
        _add_alien(alien_id="a1")
        _add_alien(alien_id="a2", status=AlienStatus.RESIDENT)
        assert len(list_aliens()) == 2

    def test_filter_by_quarantine(self):
        _add_alien(alien_id="a1", status=AlienStatus.QUARANTINE)
        _add_alien(alien_id="a2", status=AlienStatus.RESIDENT)
        result = list_aliens(status=AlienStatus.QUARANTINE)
        assert len(result) == 1
        assert result[0].alien_id == "a1"

    def test_filter_by_citizen(self):
        _add_alien(alien_id="a1", status=AlienStatus.CITIZEN)
        _add_alien(alien_id="a2", status=AlienStatus.QUARANTINE)
        result = list_aliens(status=AlienStatus.CITIZEN)
        assert len(result) == 1
        assert result[0].alien_id == "a1"

    def test_empty_when_filter_matches_nothing(self):
        _add_alien(alien_id="a1", status=AlienStatus.QUARANTINE)
        result = list_aliens(status=AlienStatus.CITIZEN)
        assert result == []

    def test_returns_list_type(self):
        assert isinstance(list_aliens(), list)


# ═══════════════════════════════════════════════════════════════════════════════
# promote_alien
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _patch_capability_enforcer(monkeypatch):
    """REM: Patch capability_enforcer.register_agent — it parses URLs as ActionType,
    which fails locally for 'external.https://...' patterns."""
    monkeypatch.setattr("agents.alien_adapter.capability_enforcer.register_agent",
                        lambda agent_id, caps: None)


class TestPromoteAlien:
    def test_returns_false_for_unknown_alien(self):
        assert promote_alien("alien_nonexistent", AlienStatus.RESIDENT, "admin") is False

    def test_returns_true_on_success(self):
        alien = _add_alien()
        result = promote_alien(alien.alien_id, AlienStatus.RESIDENT, "admin")
        assert result is True

    def test_status_updated(self):
        alien = _add_alien(status=AlienStatus.QUARANTINE)
        promote_alien(alien.alien_id, AlienStatus.PROBATION, "admin")
        assert alien.status == AlienStatus.PROBATION

    def test_capabilities_updated_to_new_level(self):
        alien = _add_alien(status=AlienStatus.QUARANTINE)
        promote_alien(alien.alien_id, AlienStatus.CITIZEN, "admin")
        assert alien.capabilities == ALIEN_CAPABILITIES[AlienStatus.CITIZEN]

    def test_vetted_by_stored(self):
        alien = _add_alien()
        promote_alien(alien.alien_id, AlienStatus.RESIDENT, "supervisor")
        assert alien.vetted_by == "supervisor"

    def test_vetted_at_set(self):
        alien = _add_alien()
        promote_alien(alien.alien_id, AlienStatus.RESIDENT, "admin")
        assert alien.vetted_at is not None

    def test_notes_stored(self):
        alien = _add_alien()
        promote_alien(alien.alien_id, AlienStatus.RESIDENT, "admin", notes="Passed review")
        assert alien.notes == "Passed review"


# ═══════════════════════════════════════════════════════════════════════════════
# revoke_alien
# ═══════════════════════════════════════════════════════════════════════════════

class TestRevokeAlien:
    def test_returns_false_for_unknown_alien(self):
        assert revoke_alien("alien_nonexistent", "admin", "suspicious") is False

    def test_returns_true_on_success(self):
        alien = _add_alien(status=AlienStatus.CITIZEN)
        result = revoke_alien(alien.alien_id, "admin", "suspicious activity")
        assert result is True

    def test_status_reverted_to_quarantine(self):
        alien = _add_alien(status=AlienStatus.CITIZEN)
        revoke_alien(alien.alien_id, "admin", "suspicious")
        assert alien.status == AlienStatus.QUARANTINE

    def test_capabilities_reverted_to_quarantine(self):
        alien = _add_alien(status=AlienStatus.CITIZEN)
        revoke_alien(alien.alien_id, "admin", "suspicious")
        assert alien.capabilities == ALIEN_CAPABILITIES[AlienStatus.QUARANTINE]

    def test_notes_contain_revoked_marker(self):
        alien = _add_alien(status=AlienStatus.RESIDENT)
        revoke_alien(alien.alien_id, "admin", "bad behavior")
        assert "REVOKED" in alien.notes
        assert "bad behavior" in alien.notes


# ═══════════════════════════════════════════════════════════════════════════════
# LangChainAdapter._has_* capability checks (pure Python)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLangChainAdapterCapabilityChecks:
    def _make_adapter_with_caps(self, caps):
        """Create minimal LangChainAdapter with specific capabilities (no init)."""
        adapter = object.__new__(LangChainAdapter)
        adapter.alien = AlienAgent(
            alien_id="test", framework="langchain", name="T", description="",
            capabilities=caps,
        )
        return adapter

    def test_file_read_true_for_filesystem_read(self):
        adapter = self._make_adapter_with_caps(["filesystem.read:/data/*"])
        assert adapter._has_file_read_capability() is True

    def test_file_read_true_for_filesystem_star(self):
        adapter = self._make_adapter_with_caps(["filesystem.*"])
        assert adapter._has_file_read_capability() is True

    def test_file_read_false_when_no_cap(self):
        adapter = self._make_adapter_with_caps(["external.none"])
        assert adapter._has_file_read_capability() is False

    def test_file_write_true_for_filesystem_write(self):
        adapter = self._make_adapter_with_caps(["filesystem.write:/sandbox/*"])
        assert adapter._has_file_write_capability() is True

    def test_file_write_true_for_filesystem_star(self):
        adapter = self._make_adapter_with_caps(["filesystem.*"])
        assert adapter._has_file_write_capability() is True

    def test_file_write_false_when_no_cap(self):
        adapter = self._make_adapter_with_caps(["filesystem.read:/data/*"])
        assert adapter._has_file_write_capability() is False

    def test_http_true_for_external_http(self):
        adapter = self._make_adapter_with_caps(["external.https://api.openai.com/*"])
        assert adapter._has_http_capability() is True

    def test_http_true_for_external_star(self):
        adapter = self._make_adapter_with_caps(["external.*"])
        assert adapter._has_http_capability() is True

    def test_http_false_for_external_none(self):
        adapter = self._make_adapter_with_caps(["external.none"])
        assert adapter._has_http_capability() is False

    def test_quarantine_has_no_http(self):
        adapter = self._make_adapter_with_caps(ALIEN_CAPABILITIES[AlienStatus.QUARANTINE])
        assert adapter._has_http_capability() is False

    def test_citizen_has_all_caps(self):
        adapter = self._make_adapter_with_caps(ALIEN_CAPABILITIES[AlienStatus.CITIZEN])
        assert adapter._has_file_read_capability() is True
        assert adapter._has_file_write_capability() is True
        assert adapter._has_http_capability() is True


# ═══════════════════════════════════════════════════════════════════════════════
# LangChainAdapter._parse_and_write (pure JSON parsing)
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseAndWrite:
    def _make_adapter(self):
        adapter = object.__new__(LangChainAdapter)
        adapter.alien = AlienAgent(
            alien_id="test", framework="langchain", name="T", description="",
            capabilities=ALIEN_CAPABILITIES[AlienStatus.CITIZEN],
        )
        adapter.alien_id = "test"
        # REM: Mock context.invoke_tool so we don't need full setup
        ctx = MagicMock()
        ctx.invoke_tool.return_value = {"success": True, "path": "/tmp/out.txt", "bytes_written": 5}
        adapter.context = ctx
        return adapter

    def test_invalid_json_returns_error(self):
        adapter = self._make_adapter()
        result = adapter._parse_and_write("not json")
        assert "error" in result
        assert "JSON" in result["error"]

    def test_valid_json_calls_invoke_tool(self):
        adapter = self._make_adapter()
        import json
        data = json.dumps({"path": "/tmp/x.txt", "content": "hello"})
        adapter._parse_and_write(data)
        adapter.context.invoke_tool.assert_called_once_with("write_file", path="/tmp/x.txt", content="hello")
