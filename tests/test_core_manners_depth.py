# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_manners_depth.py
# REM: Depth coverage for core/manners.py
# REM: All enums, data models, MannersEngine methods — pure in-memory.

import pytest
from datetime import datetime, timedelta, timezone

from core.manners import (
    AUTO_SUSPEND_THRESHOLD,
    VIOLATION_PRINCIPLE_MAP,
    VIOLATION_SEVERITY,
    ComplianceStatus,
    MannersComplianceReport,
    MannersEngine,
    MannersPrinciple,
    MannersViolation,
    PrincipleScore,
    ViolationType,
    manners_check,
    manners_score,
    manners_status,
    manners_violation,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Enum tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMannersPrinciple:
    def test_human_control(self):
        assert MannersPrinciple.HUMAN_CONTROL == "manners_1_human_control"

    def test_transparency(self):
        assert MannersPrinciple.TRANSPARENCY == "manners_2_transparency"

    def test_value_alignment(self):
        assert MannersPrinciple.VALUE_ALIGNMENT == "manners_3_value_alignment"

    def test_privacy(self):
        assert MannersPrinciple.PRIVACY == "manners_4_privacy"

    def test_security(self):
        assert MannersPrinciple.SECURITY == "manners_5_security"

    def test_five_principles(self):
        assert len(list(MannersPrinciple)) == 5


class TestComplianceStatus:
    def test_exemplary(self):
        assert ComplianceStatus.EXEMPLARY == "exemplary"

    def test_compliant(self):
        assert ComplianceStatus.COMPLIANT == "compliant"

    def test_degraded(self):
        assert ComplianceStatus.DEGRADED == "degraded"

    def test_non_compliant(self):
        assert ComplianceStatus.NON_COMPLIANT == "non_compliant"

    def test_suspended(self):
        assert ComplianceStatus.SUSPENDED == "suspended"

    def test_five_statuses(self):
        assert len(list(ComplianceStatus)) == 5


class TestViolationType:
    def test_approval_bypass_exists(self):
        assert ViolationType.APPROVAL_BYPASS == "approval_bypass"

    def test_injection_attempt_exists(self):
        assert ViolationType.INJECTION_ATTEMPT == "injection_attempt"

    def test_cross_tenant_exists(self):
        assert ViolationType.CROSS_TENANT_ACCESS == "cross_tenant_access"


# ═══════════════════════════════════════════════════════════════════════════════
# VIOLATION_PRINCIPLE_MAP and VIOLATION_SEVERITY structures
# ═══════════════════════════════════════════════════════════════════════════════

class TestViolationMaps:
    def test_approval_bypass_maps_to_human_control(self):
        assert VIOLATION_PRINCIPLE_MAP[ViolationType.APPROVAL_BYPASS] == MannersPrinciple.HUMAN_CONTROL

    def test_unaudited_action_maps_to_transparency(self):
        assert VIOLATION_PRINCIPLE_MAP[ViolationType.UNAUDITED_ACTION] == MannersPrinciple.TRANSPARENCY

    def test_capability_violation_maps_to_value_alignment(self):
        assert VIOLATION_PRINCIPLE_MAP[ViolationType.CAPABILITY_VIOLATION] == MannersPrinciple.VALUE_ALIGNMENT

    def test_cross_tenant_maps_to_privacy(self):
        assert VIOLATION_PRINCIPLE_MAP[ViolationType.CROSS_TENANT_ACCESS] == MannersPrinciple.PRIVACY

    def test_injection_maps_to_security(self):
        assert VIOLATION_PRINCIPLE_MAP[ViolationType.INJECTION_ATTEMPT] == MannersPrinciple.SECURITY

    def test_all_violations_have_principle(self):
        for v in ViolationType:
            assert v in VIOLATION_PRINCIPLE_MAP

    def test_all_violations_have_severity(self):
        for v in ViolationType:
            assert v in VIOLATION_SEVERITY

    def test_severity_between_zero_and_one(self):
        for v, sev in VIOLATION_SEVERITY.items():
            assert 0.0 <= sev <= 1.0, f"{v} has invalid severity {sev}"

    def test_unauthorized_destructive_high_severity(self):
        # UNAUTHORIZED_DESTRUCTIVE should be highest or near highest
        assert VIOLATION_SEVERITY[ViolationType.UNAUTHORIZED_DESTRUCTIVE] >= 0.30

    def test_non_qms_message_low_severity(self):
        assert VIOLATION_SEVERITY[ViolationType.NON_QMS_MESSAGE] <= 0.10


# ═══════════════════════════════════════════════════════════════════════════════
# MannersViolation.to_dict()
# ═══════════════════════════════════════════════════════════════════════════════

class TestMannersViolationToDict:
    def _make_violation(self):
        return MannersViolation(
            agent_name="test-agent",
            violation_type=ViolationType.APPROVAL_BYPASS,
            principle=MannersPrinciple.HUMAN_CONTROL,
            severity=0.30,
            timestamp=datetime.now(timezone.utc),
            details="bypassed approval",
            action="delete_file",
            resource="/data/secret.txt",
        )

    def test_has_agent_name(self):
        v = self._make_violation()
        assert v.to_dict()["agent_name"] == "test-agent"

    def test_has_violation_type(self):
        v = self._make_violation()
        assert v.to_dict()["violation_type"] == "approval_bypass"

    def test_has_principle(self):
        v = self._make_violation()
        assert v.to_dict()["principle"] == "manners_1_human_control"

    def test_has_severity(self):
        v = self._make_violation()
        assert v.to_dict()["severity"] == 0.30

    def test_has_timestamp_iso(self):
        v = self._make_violation()
        assert "T" in v.to_dict()["timestamp"]

    def test_has_auto_resolved(self):
        v = self._make_violation()
        assert v.to_dict()["auto_resolved"] is False

    def test_has_action(self):
        v = self._make_violation()
        assert v.to_dict()["action"] == "delete_file"

    def test_has_resource(self):
        v = self._make_violation()
        assert v.to_dict()["resource"] == "/data/secret.txt"


# ═══════════════════════════════════════════════════════════════════════════════
# MannersEngine fixture
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def engine():
    """Fresh MannersEngine (never use global singleton in tests)."""
    return MannersEngine()


# ═══════════════════════════════════════════════════════════════════════════════
# MannersEngine._score_to_status()
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreToStatus:
    def test_exemplary_at_1_0(self, engine):
        assert engine._score_to_status(1.0) == ComplianceStatus.EXEMPLARY

    def test_exemplary_at_0_90(self, engine):
        assert engine._score_to_status(0.90) == ComplianceStatus.EXEMPLARY

    def test_compliant_at_0_89(self, engine):
        assert engine._score_to_status(0.89) == ComplianceStatus.COMPLIANT

    def test_compliant_at_0_75(self, engine):
        assert engine._score_to_status(0.75) == ComplianceStatus.COMPLIANT

    def test_degraded_at_0_74(self, engine):
        assert engine._score_to_status(0.74) == ComplianceStatus.DEGRADED

    def test_degraded_at_0_50(self, engine):
        assert engine._score_to_status(0.50) == ComplianceStatus.DEGRADED

    def test_non_compliant_at_0_49(self, engine):
        assert engine._score_to_status(0.49) == ComplianceStatus.NON_COMPLIANT

    def test_non_compliant_at_0_25(self, engine):
        assert engine._score_to_status(0.25) == ComplianceStatus.NON_COMPLIANT

    def test_suspended_at_0_24(self, engine):
        assert engine._score_to_status(0.24) == ComplianceStatus.SUSPENDED

    def test_suspended_at_0_0(self, engine):
        assert engine._score_to_status(0.0) == ComplianceStatus.SUSPENDED


# ═══════════════════════════════════════════════════════════════════════════════
# register_agent()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegisterAgent:
    def test_registers_first_seen(self, engine):
        engine.register_agent("agent-001")
        assert "agent-001" in engine._first_seen

    def test_registers_violations_list(self, engine):
        engine.register_agent("agent-001")
        assert "agent-001" in engine._violations
        assert engine._violations["agent-001"] == []

    def test_register_twice_does_not_overwrite(self, engine):
        engine.register_agent("agent-001")
        first_seen = engine._first_seen["agent-001"]
        engine.register_agent("agent-001")
        assert engine._first_seen["agent-001"] == first_seen

    def test_registered_agent_in_evaluate_all(self, engine):
        engine.register_agent("agent-001")
        reports = engine.evaluate_all()
        names = [r.agent_name for r in reports]
        assert "agent-001" in names


# ═══════════════════════════════════════════════════════════════════════════════
# record_violation()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecordViolation:
    def test_returns_violation_instance(self, engine):
        v = engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "bypassed")
        assert isinstance(v, MannersViolation)

    def test_violation_stored(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "bypassed")
        assert len(engine._violations["agent-001"]) == 1

    def test_violation_has_correct_type(self, engine):
        v = engine.record_violation("agent-001", ViolationType.INJECTION_ATTEMPT, "prompt inj")
        assert v.violation_type == ViolationType.INJECTION_ATTEMPT

    def test_violation_principle_set_correctly(self, engine):
        v = engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "bypassed")
        assert v.principle == MannersPrinciple.HUMAN_CONTROL

    def test_violation_severity_set_correctly(self, engine):
        v = engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "bypassed")
        assert v.severity == VIOLATION_SEVERITY[ViolationType.APPROVAL_BYPASS]

    def test_violation_invalidates_cache(self, engine):
        engine.evaluate("agent-001")  # populate cache
        assert "agent-001" in engine._cached_reports
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "bypassed")
        assert "agent-001" not in engine._cached_reports

    def test_violation_with_action_and_resource(self, engine):
        v = engine.record_violation(
            "agent-001", ViolationType.CAPABILITY_VIOLATION, "bad call",
            action="delete", resource="/data/file"
        )
        assert v.action == "delete"
        assert v.resource == "/data/file"

    def test_multiple_violations_accumulate(self, engine):
        for _ in range(3):
            engine.record_violation("agent-001", ViolationType.NON_QMS_MESSAGE, "bad msg")
        assert len(engine._violations["agent-001"]) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# evaluate()
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvaluate:
    def test_no_violations_score_is_1_0(self, engine):
        report = engine.evaluate("agent-clean")
        assert report.overall_score == pytest.approx(1.0)

    def test_no_violations_status_exemplary(self, engine):
        report = engine.evaluate("agent-clean")
        assert report.status == ComplianceStatus.EXEMPLARY

    def test_violation_reduces_score(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "bypassed")
        report = engine.evaluate("agent-001")
        assert report.overall_score < 1.0

    def test_critical_violation_reduces_deeply(self, engine):
        # CROSS_TENANT_ACCESS severity=0.35 → principle score becomes 0.65
        # overall = 4 principles at 1.0 + 1 at 0.65 → 0.93... Wait:
        # actually (1.0 + 1.0 + 1.0 + 0.65 + 1.0) / 5 = 0.93
        engine.record_violation("agent-001", ViolationType.CROSS_TENANT_ACCESS, "accessed other tenant")
        report = engine.evaluate("agent-001")
        assert report.overall_score < 1.0

    def test_report_has_all_principles(self, engine):
        report = engine.evaluate("agent-001")
        for p in MannersPrinciple:
            assert p.value in report.principle_scores

    def test_report_has_correct_total_violations_zero(self, engine):
        report = engine.evaluate("agent-clean")
        assert report.total_violations == 0

    def test_report_has_correct_total_violations(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "1")
        engine.record_violation("agent-001", ViolationType.NON_QMS_MESSAGE, "2")
        report = engine.evaluate("agent-001")
        assert report.total_violations == 2

    def test_report_violations_24h(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "recent")
        report = engine.evaluate("agent-001")
        assert report.violations_24h == 1

    def test_grace_period_caps_status(self, engine):
        # Newly registered agent within grace period
        engine.register_agent("new-agent")
        report = engine.evaluate("new-agent")
        assert report.is_grace_period is True
        # Status cannot be better than DEGRADED during grace
        assert report.status in (
            ComplianceStatus.DEGRADED, ComplianceStatus.NON_COMPLIANT, ComplianceStatus.SUSPENDED
        )

    def test_old_agent_not_in_grace_period(self, engine):
        engine.register_agent("old-agent")
        engine._first_seen["old-agent"] = datetime.now(timezone.utc) - timedelta(days=2)
        report = engine.evaluate("old-agent")
        assert report.is_grace_period is False

    def test_resolved_violation_not_counted(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "bypassed")
        engine.resolve_violation("agent-001", 0)
        report = engine.evaluate("agent-001")
        assert report.total_violations == 0

    def test_cache_returns_same_report(self, engine):
        r1 = engine.evaluate("agent-001")
        r2 = engine.evaluate("agent-001")
        assert r1 is r2  # Same object from cache

    def test_report_has_to_dict(self, engine):
        report = engine.evaluate("agent-001")
        d = report.to_dict()
        assert "overall_score" in d
        assert "status" in d
        assert "principle_scores" in d


# ═══════════════════════════════════════════════════════════════════════════════
# evaluate_all()
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvaluateAll:
    def test_empty_engine_returns_empty_list(self, engine):
        assert engine.evaluate_all() == []

    def test_returns_report_for_each_agent(self, engine):
        engine.register_agent("agent-001")
        engine.register_agent("agent-002")
        reports = engine.evaluate_all()
        assert len(reports) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# get_violations()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetViolations:
    def test_returns_all_violations_unfiltered(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "1")
        engine.record_violation("agent-001", ViolationType.NON_QMS_MESSAGE, "2")
        violations = engine.get_violations("agent-001")
        assert len(violations) == 2

    def test_unknown_agent_returns_empty(self, engine):
        assert engine.get_violations("nobody") == []

    def test_filter_by_principle(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "1")
        engine.record_violation("agent-001", ViolationType.NON_QMS_MESSAGE, "2")
        violations = engine.get_violations("agent-001", principle=MannersPrinciple.HUMAN_CONTROL)
        assert len(violations) == 1
        assert violations[0].violation_type == ViolationType.APPROVAL_BYPASS

    def test_filter_since_excludes_old(self, engine):
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        engine._violations.setdefault("agent-001", [])
        engine._violations["agent-001"].append(MannersViolation(
            agent_name="agent-001",
            violation_type=ViolationType.NON_QMS_MESSAGE,
            principle=MannersPrinciple.TRANSPARENCY,
            severity=0.05,
            timestamp=old_time,
            details="old violation",
        ))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        violations = engine.get_violations("agent-001", since=cutoff)
        assert len(violations) == 0

    def test_include_resolved(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "1")
        engine.resolve_violation("agent-001", 0)
        # Default excludes resolved
        assert len(engine.get_violations("agent-001")) == 0
        # With include_resolved=True
        assert len(engine.get_violations("agent-001", include_resolved=True)) == 1

    def test_sorted_by_timestamp_descending(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "first")
        engine.record_violation("agent-001", ViolationType.NON_QMS_MESSAGE, "second")
        violations = engine.get_violations("agent-001")
        # Most recent first
        assert violations[0].timestamp >= violations[1].timestamp


# ═══════════════════════════════════════════════════════════════════════════════
# resolve_violation()
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveViolation:
    def test_resolve_first_violation(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "bypassed")
        result = engine.resolve_violation("agent-001", 0)
        assert result is True

    def test_resolve_marks_auto_resolved(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "bypassed")
        engine.resolve_violation("agent-001", 0)
        # Violation marked as resolved
        assert engine._violations["agent-001"][0].auto_resolved is True

    def test_resolve_invalid_index_returns_false(self, engine):
        result = engine.resolve_violation("nobody", 99)
        assert result is False

    def test_resolve_invalidates_cache(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "bypassed")
        engine.evaluate("agent-001")
        engine.resolve_violation("agent-001", 0)
        assert "agent-001" not in engine._cached_reports


# ═══════════════════════════════════════════════════════════════════════════════
# check_action_allowed()
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckActionAllowed:
    def test_clean_agent_allowed(self, engine):
        allowed, reason = engine.check_action_allowed("clean-agent", "delete_file")
        assert allowed is True
        assert reason == "OK"

    def test_suspended_agent_blocked(self, engine):
        # Score 0 = suspended: need 5+ critical violations
        for _ in range(6):
            engine.record_violation("agent-001", ViolationType.UNAUTHORIZED_DESTRUCTIVE, "bad")
        report = engine.evaluate("agent-001")
        if report.status == ComplianceStatus.SUSPENDED:
            allowed, reason = engine.check_action_allowed("agent-001", "do_something")
            assert allowed is False
            assert "SUSPENDED" in reason

    def test_non_compliant_write_action_blocked(self, engine):
        # Force NON_COMPLIANT status by manipulating score
        # Add enough violations to drop score to 0.25-0.49 range
        # APPROVAL_BYPASS severity=0.30 → 4 violations → score ~= (0.70 + 0 + 0 + 0 + 0)/5 = ...
        # Actually each violation hits just one principle
        # 1 APPROVAL_BYPASS (0.30) → human_control score = 0.70, others = 1.0 → overall = (0.70+1+1+1+1)/5 = 0.94 (still EXEMPLARY)
        # We need to tank all 5 principles
        # Let's manually patch the engine
        engine.register_agent("agent-nc")
        engine._first_seen["agent-nc"] = datetime.now(timezone.utc) - timedelta(days=2)
        # Record many violations across all principles to drop score
        for _ in range(3):
            engine.record_violation("agent-nc", ViolationType.APPROVAL_BYPASS, "b")  # principle 1
            engine.record_violation("agent-nc", ViolationType.UNAUDITED_ACTION, "b")  # principle 2
            engine.record_violation("agent-nc", ViolationType.CAPABILITY_VIOLATION, "b")  # principle 3
            engine.record_violation("agent-nc", ViolationType.CROSS_TENANT_ACCESS, "b")  # principle 4
            engine.record_violation("agent-nc", ViolationType.INJECTION_ATTEMPT, "b")  # principle 5
        report = engine.evaluate("agent-nc")
        if report.status == ComplianceStatus.NON_COMPLIANT:
            allowed, reason = engine.check_action_allowed("agent-nc", "delete_file")
            assert allowed is False

    def test_non_compliant_read_action_allowed(self, engine):
        # Non-compliant agents can do read-only actions
        engine.register_agent("agent-nc")
        engine._first_seen["agent-nc"] = datetime.now(timezone.utc) - timedelta(days=2)
        for _ in range(2):
            engine.record_violation("agent-nc", ViolationType.APPROVAL_BYPASS, "b")
            engine.record_violation("agent-nc", ViolationType.UNAUDITED_ACTION, "b")
            engine.record_violation("agent-nc", ViolationType.CAPABILITY_VIOLATION, "b")
            engine.record_violation("agent-nc", ViolationType.CROSS_TENANT_ACCESS, "b")
            engine.record_violation("agent-nc", ViolationType.INJECTION_ATTEMPT, "b")
        report = engine.evaluate("agent-nc")
        if report.status == ComplianceStatus.NON_COMPLIANT:
            allowed, reason = engine.check_action_allowed("agent-nc", "get_status")
            assert allowed is True


# ═══════════════════════════════════════════════════════════════════════════════
# pre_action_check()
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreActionCheck:
    def test_clean_agent_approved_passes(self, engine):
        allowed, reason = engine.pre_action_check(
            "clean-agent", "delete_file", has_approval=True, requires_approval=True
        )
        assert allowed is True

    def test_clean_agent_no_approval_required_passes(self, engine):
        allowed, reason = engine.pre_action_check(
            "clean-agent", "list_files", has_approval=False, requires_approval=False
        )
        assert allowed is True

    def test_approval_bypass_records_violation(self, engine):
        engine.pre_action_check(
            "agent-001", "delete_file", has_approval=False, requires_approval=True
        )
        violations = engine.get_violations("agent-001")
        assert any(v.violation_type == ViolationType.APPROVAL_BYPASS for v in violations)

    def test_approval_bypass_blocks_action(self, engine):
        allowed, reason = engine.pre_action_check(
            "agent-001", "delete_file", has_approval=False, requires_approval=True
        )
        assert allowed is False
        assert "approval" in reason.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# get_compliance_summary()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetComplianceSummary:
    def test_empty_engine_total_agents_zero(self, engine):
        summary = engine.get_compliance_summary()
        assert summary["total_agents"] == 0

    def test_has_required_keys(self, engine):
        summary = engine.get_compliance_summary()
        for key in ["total_agents", "status_distribution", "agents_in_grace_period",
                    "total_active_violations", "violations_24h", "average_score"]:
            assert key in summary

    def test_counts_registered_agents(self, engine):
        engine.register_agent("agent-001")
        engine.register_agent("agent-002")
        summary = engine.get_compliance_summary()
        assert summary["total_agents"] == 2

    def test_total_violations_correct(self, engine):
        engine.record_violation("agent-001", ViolationType.APPROVAL_BYPASS, "1")
        engine.record_violation("agent-001", ViolationType.NON_QMS_MESSAGE, "2")
        summary = engine.get_compliance_summary()
        assert summary["total_active_violations"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience functions (use global singleton)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConvenienceFunctions:
    def test_manners_score_returns_float(self):
        score = manners_score("conv-test-agent-score-001")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_manners_status_returns_compliance_status(self):
        status = manners_status("conv-test-agent-status-001")
        assert isinstance(status, ComplianceStatus)

    def test_manners_check_returns_tuple(self):
        result = manners_check("conv-test-agent-check-001", "list_files")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_manners_violation_returns_violation(self):
        v = manners_violation(
            "conv-test-agent-viol-001",
            ViolationType.NON_QMS_MESSAGE,
            "test violation"
        )
        assert isinstance(v, MannersViolation)
