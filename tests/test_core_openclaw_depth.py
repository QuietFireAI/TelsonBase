# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_openclaw_depth.py
# REM: Depth tests for core/openclaw.py — constants, enums, data models,
# REM: and OpenClawManager pure-logic methods (no Redis/external deps)

from datetime import datetime, timezone

import pytest

from core.openclaw import (TOOL_CATEGORY_MAP, TRUST_PERMISSION_MATRIX,
                           VALID_DEMOTIONS, VALID_PROMOTIONS, ActionCategory,
                           OpenClawActionRequest, OpenClawActionResult,
                           OpenClawInstance, OpenClawManager,
                           TrustChangeRecord, TrustLevel)

# ═══════════════════════════════════════════════════════════════════════════════
# TrustLevel enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrustLevel:
    def test_quarantine_value(self):
        assert TrustLevel.QUARANTINE.value == "quarantine"

    def test_probation_value(self):
        assert TrustLevel.PROBATION.value == "probation"

    def test_resident_value(self):
        assert TrustLevel.RESIDENT.value == "resident"

    def test_citizen_value(self):
        assert TrustLevel.CITIZEN.value == "citizen"

    def test_agent_value(self):
        assert TrustLevel.AGENT.value == "agent"

    def test_five_levels(self):
        assert len(TrustLevel) == 5

    def test_is_str_enum(self):
        assert TrustLevel.QUARANTINE == "quarantine"


# ═══════════════════════════════════════════════════════════════════════════════
# VALID_PROMOTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidPromotions:
    def test_quarantine_promotes_to_probation_only(self):
        assert VALID_PROMOTIONS[TrustLevel.QUARANTINE] == [TrustLevel.PROBATION]

    def test_probation_promotes_to_resident_only(self):
        assert VALID_PROMOTIONS[TrustLevel.PROBATION] == [TrustLevel.RESIDENT]

    def test_resident_promotes_to_citizen_only(self):
        assert VALID_PROMOTIONS[TrustLevel.RESIDENT] == [TrustLevel.CITIZEN]

    def test_citizen_promotes_to_agent_only(self):
        assert VALID_PROMOTIONS[TrustLevel.CITIZEN] == [TrustLevel.AGENT]

    def test_agent_has_no_promotions(self):
        assert VALID_PROMOTIONS[TrustLevel.AGENT] == []

    def test_quarantine_cannot_skip_to_citizen(self):
        assert TrustLevel.CITIZEN not in VALID_PROMOTIONS[TrustLevel.QUARANTINE]

    def test_five_entries_in_matrix(self):
        assert len(VALID_PROMOTIONS) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# VALID_DEMOTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidDemotions:
    def test_agent_can_demote_to_any_lower(self):
        demotions = VALID_DEMOTIONS[TrustLevel.AGENT]
        assert TrustLevel.CITIZEN in demotions
        assert TrustLevel.RESIDENT in demotions
        assert TrustLevel.PROBATION in demotions
        assert TrustLevel.QUARANTINE in demotions

    def test_citizen_cannot_demote_to_agent(self):
        assert TrustLevel.AGENT not in VALID_DEMOTIONS[TrustLevel.CITIZEN]

    def test_quarantine_has_no_demotions(self):
        assert VALID_DEMOTIONS[TrustLevel.QUARANTINE] == []

    def test_probation_can_only_demote_to_quarantine(self):
        assert VALID_DEMOTIONS[TrustLevel.PROBATION] == [TrustLevel.QUARANTINE]

    def test_five_entries_in_demotions(self):
        assert len(VALID_DEMOTIONS) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# ActionCategory enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestActionCategory:
    def test_read_internal_value(self):
        assert ActionCategory.READ_INTERNAL.value == "read_internal"

    def test_write_internal_value(self):
        assert ActionCategory.WRITE_INTERNAL.value == "write_internal"

    def test_delete_value(self):
        assert ActionCategory.DELETE.value == "delete"

    def test_external_request_value(self):
        assert ActionCategory.EXTERNAL_REQUEST.value == "external_request"

    def test_financial_value(self):
        assert ActionCategory.FINANCIAL.value == "financial"

    def test_system_config_value(self):
        assert ActionCategory.SYSTEM_CONFIG.value == "system_config"

    def test_seven_categories(self):
        assert len(ActionCategory) == 7

    def test_is_str_enum(self):
        assert ActionCategory.READ_INTERNAL == "read_internal"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL_CATEGORY_MAP
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolCategoryMap:
    def test_file_read_is_read_internal(self):
        assert TOOL_CATEGORY_MAP["file_read"] == ActionCategory.READ_INTERNAL

    def test_read_file_alias(self):
        assert TOOL_CATEGORY_MAP["read_file"] == ActionCategory.READ_INTERNAL

    def test_file_write_is_write_internal(self):
        assert TOOL_CATEGORY_MAP["file_write"] == ActionCategory.WRITE_INTERNAL

    def test_file_delete_is_delete(self):
        assert TOOL_CATEGORY_MAP["file_delete"] == ActionCategory.DELETE

    def test_http_request_is_external(self):
        assert TOOL_CATEGORY_MAP["http_request"] == ActionCategory.EXTERNAL_REQUEST

    def test_payment_send_is_financial(self):
        assert TOOL_CATEGORY_MAP["payment_send"] == ActionCategory.FINANCIAL

    def test_config_update_is_system_config(self):
        assert TOOL_CATEGORY_MAP["config_update"] == ActionCategory.SYSTEM_CONFIG

    def test_slack_send_is_communication(self):
        assert TOOL_CATEGORY_MAP["slack_send"] == ActionCategory.COMMUNICATION

    def test_database_query_is_read_internal(self):
        assert TOOL_CATEGORY_MAP["database_query"] == ActionCategory.READ_INTERNAL

    def test_email_send_is_external(self):
        assert TOOL_CATEGORY_MAP["email_send"] == ActionCategory.EXTERNAL_REQUEST

    def test_map_is_nonempty(self):
        assert len(TOOL_CATEGORY_MAP) > 10


# ═══════════════════════════════════════════════════════════════════════════════
# TRUST_PERMISSION_MATRIX
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrustPermissionMatrix:
    def test_five_levels_in_matrix(self):
        assert len(TRUST_PERMISSION_MATRIX) == 5

    def test_each_level_has_three_keys(self):
        for level, perms in TRUST_PERMISSION_MATRIX.items():
            assert "autonomous" in perms
            assert "gated" in perms
            assert "blocked" in perms

    def test_quarantine_has_no_autonomous(self):
        assert TRUST_PERMISSION_MATRIX[TrustLevel.QUARANTINE]["autonomous"] == []

    def test_quarantine_gated_includes_read(self):
        gated = TRUST_PERMISSION_MATRIX[TrustLevel.QUARANTINE]["gated"]
        assert ActionCategory.READ_INTERNAL in gated

    def test_quarantine_blocks_external(self):
        blocked = TRUST_PERMISSION_MATRIX[TrustLevel.QUARANTINE]["blocked"]
        assert ActionCategory.EXTERNAL_REQUEST in blocked

    def test_probation_autonomous_includes_read(self):
        autonomous = TRUST_PERMISSION_MATRIX[TrustLevel.PROBATION]["autonomous"]
        assert ActionCategory.READ_INTERNAL in autonomous

    def test_resident_autonomous_includes_write(self):
        autonomous = TRUST_PERMISSION_MATRIX[TrustLevel.RESIDENT]["autonomous"]
        assert ActionCategory.WRITE_INTERNAL in autonomous

    def test_resident_has_no_blocked(self):
        assert TRUST_PERMISSION_MATRIX[TrustLevel.RESIDENT]["blocked"] == []

    def test_citizen_autonomous_includes_all_categories(self):
        autonomous = TRUST_PERMISSION_MATRIX[TrustLevel.CITIZEN]["autonomous"]
        for cat in ActionCategory:
            assert cat in autonomous

    def test_citizen_has_no_gated(self):
        assert TRUST_PERMISSION_MATRIX[TrustLevel.CITIZEN]["gated"] == []

    def test_agent_autonomous_includes_all_categories(self):
        autonomous = TRUST_PERMISSION_MATRIX[TrustLevel.AGENT]["autonomous"]
        for cat in ActionCategory:
            assert cat in autonomous

    def test_agent_has_no_blocked(self):
        assert TRUST_PERMISSION_MATRIX[TrustLevel.AGENT]["blocked"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# OpenClawInstance model
# ═══════════════════════════════════════════════════════════════════════════════

class TestOpenClawInstance:
    def test_default_trust_level_quarantine(self):
        i = OpenClawInstance()
        assert i.trust_level == TrustLevel.QUARANTINE.value

    def test_default_manners_score_one(self):
        i = OpenClawInstance()
        assert i.manners_score == 1.0

    def test_default_action_count_zero(self):
        i = OpenClawInstance()
        assert i.action_count == 0

    def test_default_actions_allowed_zero(self):
        i = OpenClawInstance()
        assert i.actions_allowed == 0

    def test_default_actions_blocked_zero(self):
        i = OpenClawInstance()
        assert i.actions_blocked == 0

    def test_default_actions_gated_zero(self):
        i = OpenClawInstance()
        assert i.actions_gated == 0

    def test_default_suspended_false(self):
        i = OpenClawInstance()
        assert i.suspended is False

    def test_default_allowed_tools_empty(self):
        i = OpenClawInstance()
        assert i.allowed_tools == []

    def test_default_blocked_tools_empty(self):
        i = OpenClawInstance()
        assert i.blocked_tools == []

    def test_instance_id_generated(self):
        i = OpenClawInstance()
        assert len(i.instance_id) > 0

    def test_instance_id_unique(self):
        i1 = OpenClawInstance()
        i2 = OpenClawInstance()
        assert i1.instance_id != i2.instance_id


# ═══════════════════════════════════════════════════════════════════════════════
# OpenClawActionRequest model
# ═══════════════════════════════════════════════════════════════════════════════

class TestOpenClawActionRequest:
    def test_construction(self):
        r = OpenClawActionRequest(instance_id="abc", tool_name="file_read")
        assert r.instance_id == "abc"
        assert r.tool_name == "file_read"

    def test_default_tool_args_empty(self):
        r = OpenClawActionRequest(instance_id="x", tool_name="y")
        assert r.tool_args == {}

    def test_nonce_generated(self):
        r = OpenClawActionRequest(instance_id="x", tool_name="y")
        assert len(r.nonce) > 0

    def test_nonce_unique(self):
        r1 = OpenClawActionRequest(instance_id="x", tool_name="y")
        r2 = OpenClawActionRequest(instance_id="x", tool_name="y")
        assert r1.nonce != r2.nonce

    def test_timestamp_is_float(self):
        r = OpenClawActionRequest(instance_id="x", tool_name="y")
        assert isinstance(r.timestamp, float)


# ═══════════════════════════════════════════════════════════════════════════════
# OpenClawActionResult model
# ═══════════════════════════════════════════════════════════════════════════════

class TestOpenClawActionResult:
    def test_default_allowed_false(self):
        r = OpenClawActionResult()
        assert r.allowed is False

    def test_default_reason_empty(self):
        r = OpenClawActionResult()
        assert r.reason == ""

    def test_default_approval_required_false(self):
        r = OpenClawActionResult()
        assert r.approval_required is False

    def test_default_approval_id_none(self):
        r = OpenClawActionResult()
        assert r.approval_id is None

    def test_default_manners_score_one(self):
        r = OpenClawActionResult()
        assert r.manners_score_at_decision == 1.0

    def test_default_anomaly_flagged_false(self):
        r = OpenClawActionResult()
        assert r.anomaly_flagged is False

    def test_allowed_true(self):
        r = OpenClawActionResult(allowed=True, reason="Autonomous")
        assert r.allowed is True


# ═══════════════════════════════════════════════════════════════════════════════
# OpenClawManager — in-memory logic (no Redis)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mgr():
    """Clean OpenClawManager bypassing Redis-loading startup."""
    m = object.__new__(OpenClawManager)
    m._instances = {}
    m._suspended_ids = set()
    m._trust_history = {}
    m._initialized = True
    m._get_redis = lambda: None
    m._persist_instance = lambda inst: None
    m._persist_trust_history = lambda iid: None
    return m


def _add_instance(mgr, name="Test Claw", trust_level="quarantine",
                  suspended=False, blocked_tools=None) -> OpenClawInstance:
    inst = OpenClawInstance(
        name=name,
        trust_level=trust_level,
        api_key_hash="abc123",
        suspended=suspended,
        blocked_tools=blocked_tools or [],
    )
    mgr._instances[inst.instance_id] = inst
    return inst


class TestOpenClawManagerGetInstance:
    def test_returns_none_for_unknown(self, mgr):
        assert mgr.get_instance("nonexistent") is None

    def test_returns_instance_when_registered(self, mgr):
        inst = _add_instance(mgr)
        result = mgr.get_instance(inst.instance_id)
        assert result is not None
        assert result.instance_id == inst.instance_id

    def test_returns_correct_from_multiple(self, mgr):
        a = _add_instance(mgr, name="Alpha")
        b = _add_instance(mgr, name="Beta")
        assert mgr.get_instance(a.instance_id).name == "Alpha"
        assert mgr.get_instance(b.instance_id).name == "Beta"


class TestOpenClawManagerListInstances:
    def test_empty_initially(self, mgr):
        assert mgr.list_instances() == []

    def test_returns_all(self, mgr):
        _add_instance(mgr, name="A")
        _add_instance(mgr, name="B")
        assert len(mgr.list_instances()) == 2

    def test_returns_both_active_and_suspended(self, mgr):
        _add_instance(mgr, name="Active")
        _add_instance(mgr, name="Suspended", suspended=True)
        result = mgr.list_instances()
        assert len(result) == 2

    def test_returns_list_type(self, mgr):
        _add_instance(mgr, name="A")
        assert isinstance(mgr.list_instances(), list)


class TestOpenClawManagerIsSuspended:
    def test_not_suspended_by_default(self, mgr):
        inst = _add_instance(mgr)
        assert mgr.is_suspended(inst.instance_id) is False

    def test_suspended_when_in_set(self, mgr):
        inst = _add_instance(mgr)
        mgr._suspended_ids.add(inst.instance_id)
        assert mgr.is_suspended(inst.instance_id) is True

    def test_unknown_instance_not_suspended(self, mgr):
        assert mgr.is_suspended("nonexistent") is False
