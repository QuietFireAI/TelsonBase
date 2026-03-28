# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_openclaw.py
# REM: =======================================================================================
# REM: OPENCLAW GOVERNANCE ENGINE TESTS — "CONTROL YOUR CLAW"
# REM: =======================================================================================
# REM: v7.4.0CC: Tests for instance registration, governance pipeline, trust level
# REM: promotion/demotion, kill switch, Manners auto-demotion, and approval gate integration.
# REM: =======================================================================================

import hashlib
import json
import time
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from core.openclaw import (
    OpenClawManager,
    OpenClawInstance,
    OpenClawActionRequest,
    OpenClawActionResult,
    TrustLevel,
    ActionCategory,
    TRUST_PERMISSION_MATRIX,
    TOOL_CATEGORY_MAP,
    VALID_PROMOTIONS,
    VALID_DEMOTIONS,
)


# REM: =======================================================================================
# REM: TEST FIXTURES
# REM: =======================================================================================

@pytest.fixture
def manager():
    """REM: Fresh OpenClawManager for each test (no Redis)."""
    m = OpenClawManager()
    m._initialized = True
    return m


@pytest.fixture
def registered_claw(manager):
    """REM: Register a default claw instance for testing."""
    instance = manager.register_instance(
        name="Test Claw",
        api_key="test-api-key-12345",
        registered_by="test_admin",
    )
    return instance


@pytest.fixture
def citizen_claw(manager, registered_claw):
    """REM: A claw promoted all the way to CITIZEN for testing."""
    iid = registered_claw.instance_id
    manager.promote_trust(iid, "probation", "admin", "test promotion")
    manager.promote_trust(iid, "resident", "admin", "test promotion")
    manager.promote_trust(iid, "citizen", "admin", "test promotion")
    return manager.get_instance(iid)


# REM: =======================================================================================
# REM: REGISTRATION TESTS
# REM: =======================================================================================

class TestRegistration:
    """REM: Tests for OpenClaw instance registration."""

    def test_register_instance_defaults_to_quarantine(self, manager):
        """REM: New instances start at QUARANTINE trust level."""
        instance = manager.register_instance(
            name="My Claw",
            api_key="my-secret-key",
            registered_by="admin",
        )
        assert instance is not None
        assert instance.trust_level == "quarantine"
        assert instance.suspended is False
        assert instance.action_count == 0
        assert instance.manners_score == 1.0

    def test_register_instance_hashes_api_key(self, manager):
        """REM: API key is stored as SHA-256 hash, never plaintext."""
        api_key = "super-secret-api-key"
        instance = manager.register_instance(
            name="Hashed Claw",
            api_key=api_key,
            registered_by="admin",
        )
        expected_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        assert instance.api_key_hash == expected_hash
        assert api_key not in instance.model_dump_json()

    def test_register_duplicate_api_key_returns_existing(self, manager):
        """REM: Duplicate API key returns the existing instance."""
        first = manager.register_instance(name="First", api_key="same-key", registered_by="admin")
        second = manager.register_instance(name="Second", api_key="same-key", registered_by="admin")
        assert first.instance_id == second.instance_id

    def test_register_max_instances_enforced(self, manager):
        """REM: Cannot exceed max instance limit."""
        with patch("core.openclaw.get_settings") as mock_settings:
            settings = MagicMock()
            settings.openclaw_max_instances = 2
            settings.openclaw_default_trust_level = "quarantine"
            settings.redis_url = "redis://localhost:6379/0"
            mock_settings.return_value = settings

            manager.register_instance(name="Claw 1", api_key="key1", registered_by="admin")
            manager.register_instance(name="Claw 2", api_key="key2", registered_by="admin")
            result = manager.register_instance(name="Claw 3", api_key="key3", registered_by="admin")
            assert result is None  # Max reached

    def test_register_with_allowed_tools(self, manager):
        """REM: Instance can have explicit tool allowlist."""
        instance = manager.register_instance(
            name="Restricted Claw",
            api_key="restricted-key",
            allowed_tools=["file_read", "search"],
            registered_by="admin",
        )
        assert instance.allowed_tools == ["file_read", "search"]

    def test_register_with_blocked_tools(self, manager):
        """REM: Instance can have explicit tool blocklist."""
        instance = manager.register_instance(
            name="Blocked Claw",
            api_key="blocked-key",
            blocked_tools=["file_delete", "payment_send"],
            registered_by="admin",
        )
        assert instance.blocked_tools == ["file_delete", "payment_send"]


# REM: =======================================================================================
# REM: GOVERNANCE PIPELINE TESTS
# REM: =======================================================================================

class TestGovernancePipeline:
    """REM: Tests for the core governance pipeline (evaluate_action)."""

    def test_unregistered_instance_rejected(self, manager):
        """REM: Actions from unregistered instances are rejected."""
        result = manager.evaluate_action("nonexistent", "file_read")
        assert result.allowed is False
        assert "not registered" in result.reason.lower()

    def test_quarantine_blocks_all_autonomously(self, manager, registered_claw):
        """REM: QUARANTINE trust level requires approval for ALL actions."""
        # REM: Read action — should be gated (not autonomous at quarantine)
        result = manager.evaluate_action(registered_claw.instance_id, "file_read")
        assert result.allowed is False
        assert result.approval_required is True
        assert result.trust_level_at_decision == "quarantine"

    def test_quarantine_blocks_destructive(self, manager, registered_claw):
        """REM: QUARANTINE blocks destructive actions entirely."""
        result = manager.evaluate_action(registered_claw.instance_id, "file_delete")
        assert result.allowed is False
        assert result.approval_required is False  # Blocked, not gated
        assert "blocked" in result.reason.lower()

    def test_quarantine_blocks_external(self, manager, registered_claw):
        """REM: QUARANTINE blocks external requests entirely."""
        result = manager.evaluate_action(registered_claw.instance_id, "http_request")
        assert result.allowed is False
        assert result.approval_required is False

    def test_probation_allows_read_autonomously(self, manager, registered_claw):
        """REM: PROBATION allows read-only internal actions autonomously."""
        iid = registered_claw.instance_id
        manager.promote_trust(iid, "probation", "admin")
        result = manager.evaluate_action(iid, "file_read")
        assert result.allowed is True
        assert result.trust_level_at_decision == "probation"

    def test_probation_gates_external(self, manager, registered_claw):
        """REM: PROBATION gates external actions (requires approval)."""
        iid = registered_claw.instance_id
        manager.promote_trust(iid, "probation", "admin")
        result = manager.evaluate_action(iid, "http_request")
        assert result.allowed is False
        assert result.approval_required is True

    def test_probation_blocks_destructive(self, manager, registered_claw):
        """REM: PROBATION blocks destructive actions entirely."""
        iid = registered_claw.instance_id
        manager.promote_trust(iid, "probation", "admin")
        result = manager.evaluate_action(iid, "file_delete")
        assert result.allowed is False
        assert result.approval_required is False

    def test_resident_allows_read_write(self, manager, registered_claw):
        """REM: RESIDENT allows read and write actions autonomously."""
        iid = registered_claw.instance_id
        manager.promote_trust(iid, "probation", "admin")
        manager.promote_trust(iid, "resident", "admin")
        result = manager.evaluate_action(iid, "file_write")
        assert result.allowed is True

    def test_resident_gates_destructive(self, manager, registered_claw):
        """REM: RESIDENT gates destructive actions (requires approval)."""
        iid = registered_claw.instance_id
        manager.promote_trust(iid, "probation", "admin")
        manager.promote_trust(iid, "resident", "admin")
        result = manager.evaluate_action(iid, "file_delete")
        assert result.allowed is False
        assert result.approval_required is True

    def test_citizen_allows_all(self, manager, citizen_claw):
        """REM: CITIZEN allows all action categories autonomously."""
        iid = citizen_claw.instance_id
        for tool in ["file_read", "file_write", "file_delete", "http_request", "payment_send"]:
            result = manager.evaluate_action(iid, tool)
            assert result.allowed is True, f"CITIZEN should allow {tool}"

    def test_blocked_tool_rejected(self, manager):
        """REM: Explicitly blocked tools are always rejected."""
        instance = manager.register_instance(
            name="Restricted",
            api_key="restricted-key",
            blocked_tools=["file_delete"],
            registered_by="admin",
        )
        # REM: Promote to citizen so trust level doesn't block it
        iid = instance.instance_id
        manager.promote_trust(iid, "probation", "admin")
        manager.promote_trust(iid, "resident", "admin")
        manager.promote_trust(iid, "citizen", "admin")

        result = manager.evaluate_action(iid, "file_delete")
        assert result.allowed is False
        assert "blocked" in result.reason.lower()

    def test_allowlist_enforcement(self, manager):
        """REM: If allowlist is set, only listed tools are allowed."""
        instance = manager.register_instance(
            name="Allowlisted",
            api_key="allowlist-key",
            allowed_tools=["file_read"],
            registered_by="admin",
        )
        iid = instance.instance_id
        manager.promote_trust(iid, "probation", "admin")

        # REM: file_read is on the allowlist and autonomous at probation
        result = manager.evaluate_action(iid, "file_read")
        assert result.allowed is True

        # REM: search is NOT on the allowlist
        result = manager.evaluate_action(iid, "search")
        assert result.allowed is False
        assert "not on allowlist" in result.reason.lower()

    def test_action_counters_updated(self, manager, registered_claw):
        """REM: Action counters are updated correctly."""
        iid = registered_claw.instance_id

        # REM: Quarantine read → gated (counts as gated)
        manager.evaluate_action(iid, "file_read")
        instance = manager.get_instance(iid)
        assert instance.action_count == 1
        assert instance.actions_gated == 1

        # REM: Quarantine delete → blocked
        manager.evaluate_action(iid, "file_delete")
        instance = manager.get_instance(iid)
        assert instance.action_count == 2
        assert instance.actions_blocked == 1

    def test_unknown_tool_defaults_to_write(self, manager, registered_claw):
        """REM: Unknown tools default to WRITE_INTERNAL category (gated at quarantine)."""
        result = manager.evaluate_action(registered_claw.instance_id, "unknown_tool_xyz")
        # REM: At quarantine, write_internal is blocked
        assert result.allowed is False


# REM: =======================================================================================
# REM: TRUST LEVEL TESTS
# REM: =======================================================================================

class TestTrustLevels:
    """REM: Tests for trust level promotion and demotion."""

    def test_valid_promotion_path(self, manager, registered_claw):
        """REM: Promotion must follow: QUARANTINE → PROBATION → RESIDENT → CITIZEN."""
        iid = registered_claw.instance_id
        assert manager.promote_trust(iid, "probation", "admin") is True
        assert manager.promote_trust(iid, "resident", "admin") is True
        assert manager.promote_trust(iid, "citizen", "admin") is True
        assert manager.get_instance(iid).trust_level == "citizen"

    def test_invalid_promotion_skip(self, manager, registered_claw):
        """REM: Cannot skip trust levels during promotion."""
        iid = registered_claw.instance_id
        # REM: Cannot jump from quarantine to resident
        assert manager.promote_trust(iid, "resident", "admin") is False
        assert manager.get_instance(iid).trust_level == "quarantine"

    def test_invalid_promotion_to_citizen_from_quarantine(self, manager, registered_claw):
        """REM: Cannot jump from quarantine directly to citizen."""
        iid = registered_claw.instance_id
        assert manager.promote_trust(iid, "citizen", "admin") is False

    def test_demotion_can_skip_levels(self, manager, citizen_claw):
        """REM: Demotions can skip levels (instant consequences)."""
        iid = citizen_claw.instance_id
        # REM: Citizen → Quarantine (skipping 2 levels) should work
        assert manager.demote_trust(iid, "quarantine", "admin", "emergency") is True
        assert manager.get_instance(iid).trust_level == "quarantine"

    def test_demotion_citizen_to_probation(self, manager, citizen_claw):
        """REM: Citizen can be demoted to probation."""
        iid = citizen_claw.instance_id
        assert manager.demote_trust(iid, "probation", "admin") is True
        assert manager.get_instance(iid).trust_level == "probation"

    def test_cannot_promote_above_citizen(self, manager, citizen_claw):
        """REM: Cannot promote beyond citizen."""
        iid = citizen_claw.instance_id
        # REM: No valid promotions from citizen
        assert manager.promote_trust(iid, "citizen", "admin") is False

    def test_cannot_demote_below_quarantine(self, manager, registered_claw):
        """REM: Cannot demote below quarantine."""
        iid = registered_claw.instance_id
        # REM: No valid demotions from quarantine
        assert manager.demote_trust(iid, "quarantine", "admin") is False

    def test_invalid_trust_level_rejected(self, manager, registered_claw):
        """REM: Invalid trust level strings are rejected."""
        iid = registered_claw.instance_id
        assert manager.promote_trust(iid, "superadmin", "admin") is False

    def test_trust_history_recorded(self, manager, registered_claw):
        """REM: Trust changes are recorded in history."""
        iid = registered_claw.instance_id
        manager.promote_trust(iid, "probation", "admin", "good behavior")

        history = manager._trust_history.get(iid, [])
        # REM: Should have registration + promotion = 2 entries
        assert len(history) == 2
        latest = history[-1]
        assert latest.old_level == "quarantine"
        assert latest.new_level == "probation"
        assert latest.changed_by == "admin"
        assert latest.reason == "good behavior"
        assert latest.change_type == "promotion"


# REM: =======================================================================================
# REM: KILL SWITCH TESTS
# REM: =======================================================================================

class TestKillSwitch:
    """REM: Tests for the suspend/reinstate kill switch."""

    def test_suspend_blocks_all_actions(self, manager, registered_claw):
        """REM: Suspended instances have all actions rejected."""
        iid = registered_claw.instance_id
        manager.suspend_instance(iid, "admin", "security concern")

        result = manager.evaluate_action(iid, "file_read")
        assert result.allowed is False
        assert "suspended" in result.reason.lower()

    def test_suspend_sets_metadata(self, manager, registered_claw):
        """REM: Suspension sets the right metadata on the instance."""
        iid = registered_claw.instance_id
        manager.suspend_instance(iid, "admin", "security concern")

        instance = manager.get_instance(iid)
        assert instance.suspended is True
        assert instance.suspended_by == "admin"
        assert instance.suspended_reason == "security concern"
        assert instance.suspended_at is not None

    def test_reinstate_allows_actions(self, manager, registered_claw):
        """REM: Reinstated instances can act again (at their current trust level)."""
        iid = registered_claw.instance_id
        # REM: Promote first so we can test autonomous action after reinstate
        manager.promote_trust(iid, "probation", "admin")

        manager.suspend_instance(iid, "admin", "test")
        result = manager.evaluate_action(iid, "file_read")
        assert result.allowed is False

        manager.reinstate_instance(iid, "admin", "cleared")
        result = manager.evaluate_action(iid, "file_read")
        assert result.allowed is True  # Probation allows file_read

    def test_reinstate_clears_metadata(self, manager, registered_claw):
        """REM: Reinstatement clears all suspension metadata."""
        iid = registered_claw.instance_id
        manager.suspend_instance(iid, "admin", "test")
        manager.reinstate_instance(iid, "admin", "cleared")

        instance = manager.get_instance(iid)
        assert instance.suspended is False
        assert instance.suspended_by is None
        assert instance.suspended_reason is None
        assert instance.suspended_at is None

    def test_reinstate_nonsuspended_fails(self, manager, registered_claw):
        """REM: Cannot reinstate an instance that isn't suspended."""
        iid = registered_claw.instance_id
        assert manager.reinstate_instance(iid, "admin") is False

    def test_suspend_nonexistent_fails(self, manager):
        """REM: Cannot suspend a nonexistent instance."""
        assert manager.suspend_instance("nonexistent", "admin") is False

    def test_kill_switch_checked_before_trust(self, manager, citizen_claw):
        """REM: Kill switch is checked BEFORE trust level — even citizens are blocked."""
        iid = citizen_claw.instance_id
        manager.suspend_instance(iid, "admin", "emergency")

        result = manager.evaluate_action(iid, "file_read")
        assert result.allowed is False
        assert "suspended" in result.reason.lower()

    def test_kill_switch_survives_cache_clear(self, manager, registered_claw):
        """
        REM: Suspended state must persist when the in-memory cache is cleared.
        REM: Simulates a worker restart or memory eviction — Redis is the source of truth.
        """
        iid = registered_claw.instance_id

        # REM: Suspend and capture the serialized instance for the mock Redis backend
        manager.suspend_instance(iid, "admin", "cache clear test")
        instance = manager.get_instance(iid)
        instance_json = instance.model_dump_json()

        # REM: Simulate cache clear (e.g. new worker, restart, eviction)
        manager._instances = {}
        manager._suspended_ids = set()

        # REM: Mock Redis so the manager reloads both instance data and suspension flag
        mock_redis = MagicMock()
        mock_redis.get.return_value = instance_json
        mock_redis.exists.return_value = 1

        with patch.object(manager, "_get_redis", return_value=mock_redis):
            result = manager.evaluate_action(iid, "file_read")

        assert result.allowed is False, (
            "Kill switch must be enforced after cache clear — Redis-backed suspension not honored"
        )
        assert "suspended" in result.reason.lower(), (
            f"Rejection reason should mention suspension, got: '{result.reason}'"
        )


# REM: =======================================================================================
# REM: Manners COMPLIANCE AUTO-DEMOTION TESTS
# REM: =======================================================================================

class TestMannersAutoDemotion:
    """REM: Tests for Manners compliance auto-demotion."""

    def test_low_manners_score_triggers_auto_demotion(self, manager, citizen_claw):
        """REM: Manners score below threshold auto-demotes to quarantine."""
        iid = citizen_claw.instance_id

        # REM: Lower Manners score below threshold
        manager.update_manners_score(iid, 0.40)

        # REM: Next action should trigger auto-demotion
        result = manager.evaluate_action(iid, "file_read")
        instance = manager.get_instance(iid)
        assert instance.trust_level == "quarantine"

    def test_auto_demotion_records_in_history(self, manager, citizen_claw):
        """REM: Auto-demotion is recorded in trust history."""
        iid = citizen_claw.instance_id
        manager.update_manners_score(iid, 0.30)
        manager.evaluate_action(iid, "file_read")

        history = manager._trust_history.get(iid, [])
        auto_demotions = [h for h in history if h.change_type == "auto_demotion"]
        assert len(auto_demotions) > 0
        assert auto_demotions[-1].new_level == "quarantine"
        assert "manners" in auto_demotions[-1].reason.lower()

    def test_already_quarantined_no_double_demotion(self, manager, registered_claw):
        """REM: Instance already at quarantine is not auto-demoted again."""
        iid = registered_claw.instance_id
        manager.update_manners_score(iid, 0.20)

        initial_history_len = len(manager._trust_history.get(iid, []))
        manager.evaluate_action(iid, "file_read")
        final_history_len = len(manager._trust_history.get(iid, []))

        # REM: No new auto-demotion entry should be added
        assert final_history_len == initial_history_len

    def test_manners_score_clamped_0_1(self, manager, registered_claw):
        """REM: Manners score is clamped between 0.0 and 1.0."""
        iid = registered_claw.instance_id
        manager.update_manners_score(iid, 2.5)
        assert manager.get_instance(iid).manners_score == 1.0

        manager.update_manners_score(iid, -0.5)
        assert manager.get_instance(iid).manners_score == 0.0


# REM: =======================================================================================
# REM: TRUST REPORT TESTS
# REM: =======================================================================================

class TestTrustReport:
    """REM: Tests for trust report generation."""

    def test_trust_report_contents(self, manager, registered_claw):
        """REM: Trust report contains expected fields."""
        iid = registered_claw.instance_id
        manager.evaluate_action(iid, "file_read")  # Generate some action
        report = manager.get_trust_report(iid)

        assert report is not None
        assert report["instance_id"] == iid
        assert report["name"] == "Test Claw"
        assert report["current_trust_level"] == "quarantine"
        assert "action_summary" in report
        assert "trust_history" in report
        assert report["action_summary"]["total"] == 1

    def test_trust_report_nonexistent(self, manager):
        """REM: Trust report returns None for nonexistent instance."""
        assert manager.get_trust_report("nonexistent") is None


# REM: =======================================================================================
# REM: AUTHENTICATION TESTS
# REM: =======================================================================================

class TestAuthentication:
    """REM: Tests for API key authentication."""

    def test_authenticate_valid_key(self, manager, registered_claw):
        """REM: Valid API key returns the instance."""
        instance = manager.authenticate_instance("test-api-key-12345")
        assert instance is not None
        assert instance.instance_id == registered_claw.instance_id

    def test_authenticate_invalid_key(self, manager, registered_claw):
        """REM: Invalid API key returns None."""
        assert manager.authenticate_instance("wrong-key") is None

    def test_authenticate_suspended_returns_none(self, manager, registered_claw):
        """REM: Suspended instance cannot authenticate."""
        manager.suspend_instance(registered_claw.instance_id, "admin")
        assert manager.authenticate_instance("test-api-key-12345") is None


# REM: =======================================================================================
# REM: TRUST PERMISSION MATRIX TESTS
# REM: =======================================================================================

class TestPermissionMatrix:
    """REM: Verify the trust permission matrix is internally consistent."""

    def test_quarantine_has_no_autonomous(self):
        """REM: QUARANTINE has zero autonomous action categories."""
        assert len(TRUST_PERMISSION_MATRIX[TrustLevel.QUARANTINE]["autonomous"]) == 0

    def test_citizen_has_all_autonomous(self):
        """REM: CITIZEN has all non-COMMUNICATION categories as autonomous.
        REM: M17 — COMMUNICATION is always gated (never autonomous) at every tier."""
        citizen_auto = TRUST_PERMISSION_MATRIX[TrustLevel.CITIZEN]["autonomous"]
        expected = {cat for cat in ActionCategory if cat != ActionCategory.COMMUNICATION}
        assert set(citizen_auto) == expected

    def test_citizen_communication_is_gated(self):
        """REM: M17 — COMMUNICATION is gated at CITIZEN (outbound messages are irreversible)."""
        assert ActionCategory.COMMUNICATION in TRUST_PERMISSION_MATRIX[TrustLevel.CITIZEN]["gated"]

    def test_citizen_has_no_blocked(self):
        """REM: CITIZEN has nothing blocked."""
        assert len(TRUST_PERMISSION_MATRIX[TrustLevel.CITIZEN]["blocked"]) == 0

    def test_no_overlapping_categories(self):
        """REM: Each trust level has no overlapping categories between autonomous/gated/blocked."""
        for level in TrustLevel:
            perms = TRUST_PERMISSION_MATRIX[level]
            auto_set = set(perms["autonomous"])
            gated_set = set(perms["gated"])
            blocked_set = set(perms["blocked"])
            assert auto_set.isdisjoint(gated_set), f"{level}: autonomous overlaps with gated"
            assert auto_set.isdisjoint(blocked_set), f"{level}: autonomous overlaps with blocked"
            assert gated_set.isdisjoint(blocked_set), f"{level}: gated overlaps with blocked"

    def test_valid_promotions_are_sequential(self):
        """REM: Valid promotions are one step at a time: QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT."""
        assert VALID_PROMOTIONS[TrustLevel.QUARANTINE] == [TrustLevel.PROBATION]
        assert VALID_PROMOTIONS[TrustLevel.PROBATION] == [TrustLevel.RESIDENT]
        assert VALID_PROMOTIONS[TrustLevel.RESIDENT] == [TrustLevel.CITIZEN]
        assert VALID_PROMOTIONS[TrustLevel.CITIZEN] == [TrustLevel.AGENT]
        assert VALID_PROMOTIONS[TrustLevel.AGENT] == []

    def test_valid_demotions_allow_skipping(self):
        """REM: Valid demotions allow skipping levels."""
        assert TrustLevel.QUARANTINE in VALID_DEMOTIONS[TrustLevel.CITIZEN]
        assert TrustLevel.PROBATION in VALID_DEMOTIONS[TrustLevel.CITIZEN]
        assert TrustLevel.RESIDENT in VALID_DEMOTIONS[TrustLevel.CITIZEN]


# REM: =======================================================================================
# REM: LISTING AND QUERY TESTS
# REM: =======================================================================================

class TestQueryMethods:
    """REM: Tests for listing and querying instances."""

    def test_list_instances(self, manager, registered_claw):
        """REM: list_instances returns all registered instances."""
        instances = manager.list_instances()
        assert len(instances) >= 1
        assert any(i.instance_id == registered_claw.instance_id for i in instances)

    def test_get_instance_by_id(self, manager, registered_claw):
        """REM: get_instance returns the correct instance."""
        instance = manager.get_instance(registered_claw.instance_id)
        assert instance is not None
        assert instance.name == "Test Claw"

    def test_get_nonexistent_instance(self, manager):
        """REM: get_instance returns None for nonexistent ID."""
        assert manager.get_instance("nonexistent") is None


# REM: =======================================================================================
# REM: DEREGISTER TESTS
# REM: =======================================================================================

class TestDeregister:
    """REM: Tests for permanent instance deregistration."""

    def test_deregister_removes_from_local_cache(self, manager, registered_claw):
        """REM: Deregistered instance is no longer in local cache."""
        iid = registered_claw.instance_id
        result = manager.deregister_instance(iid, deregistered_by="admin", reason="cleanup")
        assert result is True
        assert iid not in manager._instances

    def test_deregister_get_returns_none(self, manager, registered_claw):
        """REM: get_instance returns None after deregistration (no Redis fallback in test)."""
        iid = registered_claw.instance_id
        manager.deregister_instance(iid, deregistered_by="admin")
        assert manager.get_instance(iid) is None

    def test_deregister_nonexistent_returns_false(self, manager):
        """REM: Deregistering a nonexistent ID returns False."""
        assert manager.deregister_instance("nonexistent-id", deregistered_by="admin") is False

    def test_deregister_clears_suspended_set(self, manager, registered_claw):
        """REM: Suspension flag is cleared on deregistration."""
        iid = registered_claw.instance_id
        manager.suspend_instance(iid, suspended_by="admin", reason="test")
        assert iid in manager._suspended_ids
        manager.deregister_instance(iid, deregistered_by="admin")
        assert iid not in manager._suspended_ids

    def test_deregister_clears_trust_history(self, manager, registered_claw):
        """REM: Trust history is removed on deregistration."""
        iid = registered_claw.instance_id
        manager.deregister_instance(iid, deregistered_by="admin")
        assert iid not in manager._trust_history

    def test_deregister_returns_true_on_success(self, manager, registered_claw):
        """REM: Successful deregistration returns True."""
        result = manager.deregister_instance(
            registered_claw.instance_id, deregistered_by="admin", reason="test cleanup"
        )
        assert result is True

    def test_deregister_idempotent_second_call_returns_false(self, manager, registered_claw):
        """REM: Second deregistration of the same ID returns False (already gone)."""
        iid = registered_claw.instance_id
        manager.deregister_instance(iid, deregistered_by="admin")
        assert manager.deregister_instance(iid, deregistered_by="admin") is False

    def test_deregister_does_not_affect_other_instances(self, manager):
        """REM: Deregistering one instance does not touch others."""
        a = manager.register_instance("Agent A", api_key="key-aaa", registered_by="admin")
        b = manager.register_instance("Agent B", api_key="key-bbb", registered_by="admin")
        manager.deregister_instance(a.instance_id, deregistered_by="admin")
        assert manager.get_instance(b.instance_id) is not None


# REM: =======================================================================================
# REM: DEMOTION HARD-BLOCK (AGENT TIER) TESTS
# REM: =======================================================================================

class TestAgentDemotionHardBlock:
    """REM: Tests for AGENT-tier demotion requiring acknowledged=true at route layer.
    REM: The manager itself allows the demotion — the hard-block lives in the route handler.
    REM: These tests verify the manager behavior and DemoteRequest model validation.
    """

    @pytest.fixture
    def agent_claw(self, manager, registered_claw):
        """REM: Promote a claw all the way to AGENT tier."""
        iid = registered_claw.instance_id
        manager.promote_trust(iid, "probation", "admin", "test")
        manager.promote_trust(iid, "resident", "admin", "test")
        manager.promote_trust(iid, "citizen", "admin", "test")
        manager.promote_trust(iid, "agent", "admin", "test")
        return manager.get_instance(iid)

    def test_manager_demote_from_agent_succeeds(self, manager, agent_claw):
        """REM: Manager allows demotion from AGENT — hard-block is route-layer only."""
        iid = agent_claw.instance_id
        result = manager.demote_trust(iid, "citizen", demoted_by="admin", reason="behaviour review")
        assert result is True
        assert manager.get_instance(iid).trust_level == "citizen"

    def test_manager_demote_from_agent_records_in_trust_history(self, manager, agent_claw):
        """REM: Demotion from AGENT is recorded in trust history."""
        iid = agent_claw.instance_id
        manager.demote_trust(iid, "probation", demoted_by="admin", reason="anomaly spike")
        history = manager._trust_history.get(iid, [])
        demotion = [r for r in history if r.change_type == "demotion"]
        assert len(demotion) >= 1
        assert demotion[-1].new_level == "probation"
        assert demotion[-1].changed_by == "admin"

    def test_manager_demote_agent_to_quarantine(self, manager, agent_claw):
        """REM: AGENT can be demoted all the way to QUARANTINE in one step."""
        iid = agent_claw.instance_id
        result = manager.demote_trust(iid, "quarantine", demoted_by="admin", reason="critical violation")
        assert result is True
        assert manager.get_instance(iid).trust_level == "quarantine"

    def test_demote_request_acknowledged_field_defaults_false(self):
        """REM: DemoteRequest.acknowledged defaults to False (hard-block active by default)."""
        from api.openclaw_routes import DemoteRequest
        req = DemoteRequest(new_level="citizen", reason="test")
        assert req.acknowledged is False

    def test_demote_request_acknowledged_can_be_true(self):
        """REM: DemoteRequest.acknowledged accepts true."""
        from api.openclaw_routes import DemoteRequest
        req = DemoteRequest(new_level="citizen", reason="test", acknowledged=True)
        assert req.acknowledged is True
