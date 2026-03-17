# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_anomaly_depth.py
# REM: Depth coverage for core/anomaly.py
# REM: Enums, AgentBaseline, BehaviorMonitor — all in-memory.

import pytest
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from core.anomaly import (
    AgentBaseline,
    AgentBehaviorRecord,
    Anomaly,
    AnomalySeverity,
    AnomalyType,
    BehaviorMonitor,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Enum tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnomalyType:
    def test_rate_spike(self):
        assert AnomalyType.RATE_SPIKE == "rate_spike"

    def test_new_resource(self):
        assert AnomalyType.NEW_RESOURCE == "new_resource"

    def test_new_action(self):
        assert AnomalyType.NEW_ACTION == "new_action"

    def test_unusual_timing(self):
        assert AnomalyType.UNUSUAL_TIMING == "unusual_timing"

    def test_sequential_access(self):
        assert AnomalyType.SEQUENTIAL_ACCESS == "sequential_access"

    def test_error_spike(self):
        assert AnomalyType.ERROR_SPIKE == "error_spike"

    def test_capability_probe(self):
        assert AnomalyType.CAPABILITY_PROBE == "capability_probe"

    def test_all_unique(self):
        vals = [a.value for a in AnomalyType]
        assert len(vals) == len(set(vals))


class TestAnomalySeverity:
    def test_low(self):
        assert AnomalySeverity.LOW == "low"

    def test_medium(self):
        assert AnomalySeverity.MEDIUM == "medium"

    def test_high(self):
        assert AnomalySeverity.HIGH == "high"

    def test_critical(self):
        assert AnomalySeverity.CRITICAL == "critical"

    def test_all_unique(self):
        vals = [s.value for s in AnomalySeverity]
        assert len(vals) == len(set(vals))


# ═══════════════════════════════════════════════════════════════════════════════
# AgentBaseline
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentBaseline:
    def test_is_mature_below_threshold(self):
        b = AgentBaseline(agent_id="a")
        b.total_observations = 50
        assert b.is_mature(min_observations=100) is False

    def test_is_mature_at_threshold(self):
        b = AgentBaseline(agent_id="a")
        b.total_observations = 100
        assert b.is_mature(min_observations=100) is True

    def test_is_mature_above_threshold(self):
        b = AgentBaseline(agent_id="a")
        b.total_observations = 150
        assert b.is_mature(min_observations=100) is True

    def test_is_mature_default_threshold(self):
        b = AgentBaseline(agent_id="a")
        b.total_observations = 99
        assert b.is_mature() is False

    def test_known_resources_initially_empty(self):
        b = AgentBaseline(agent_id="a")
        assert len(b.known_resources) == 0

    def test_known_actions_initially_empty(self):
        b = AgentBaseline(agent_id="a")
        assert len(b.known_actions) == 0

    def test_total_observations_initially_zero(self):
        b = AgentBaseline(agent_id="a")
        assert b.total_observations == 0


# ═══════════════════════════════════════════════════════════════════════════════
# BehaviorMonitor fixture
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def monitor():
    return BehaviorMonitor()


def _seed_mature_baseline(monitor, agent_id, resource="res-A", action="action-A"):
    """Create a mature baseline directly without needing 100 record() calls."""
    b = AgentBaseline(
        agent_id=agent_id,
        total_observations=100,
        avg_actions_per_minute=2.0,
        std_actions_per_minute=0.5,
        max_observed_rate=4.0,
        avg_error_rate=0.05,
        baseline_start=datetime.now(timezone.utc) - timedelta(days=1),
        last_updated=datetime.now(timezone.utc),
    )
    b.known_resources = {resource}
    b.known_actions = {action}
    b.hourly_distribution = defaultdict(int)
    for h in range(24):
        b.hourly_distribution[h] = 20  # Even distribution
    monitor._baselines[agent_id] = b
    monitor._recent_records[agent_id] = []
    return b


# ═══════════════════════════════════════════════════════════════════════════════
# BehaviorMonitor.record() — basic behavior
# ═══════════════════════════════════════════════════════════════════════════════

class TestBehaviorMonitorRecord:
    def test_record_returns_list(self, monitor):
        result = monitor.record("agent-001", "read", "/data/file", success=True)
        assert isinstance(result, list)

    def test_record_creates_baseline(self, monitor):
        monitor.record("agent-001", "read", "/data/file")
        assert "agent-001" in monitor._baselines

    def test_record_stores_in_recent_records(self, monitor):
        monitor.record("agent-001", "read", "/data/file")
        assert len(monitor._recent_records["agent-001"]) == 1

    def test_immature_baseline_no_anomalies(self, monitor):
        # Fresh agent — baseline not mature → no anomalies except capability probe
        for _ in range(5):
            anomalies = monitor.record("agent-001", "read", "/data/file", success=True)
        assert all(a.anomaly_type != AnomalyType.RATE_SPIKE for a in anomalies)

    def test_updates_known_resources(self, monitor):
        monitor.record("agent-001", "read", "/data/file")
        assert "/data/file" in monitor._baselines["agent-001"].known_resources

    def test_updates_known_actions(self, monitor):
        monitor.record("agent-001", "read", "/data/file")
        assert "read" in monitor._baselines["agent-001"].known_actions

    def test_updates_hourly_distribution(self, monitor):
        monitor.record("agent-001", "read", "/data/file")
        baseline = monitor._baselines["agent-001"]
        hour = datetime.now(timezone.utc).hour
        assert baseline.hourly_distribution[hour] >= 1

    def test_updates_total_observations(self, monitor):
        for _ in range(3):
            monitor.record("agent-001", "read", "/data/file")
        assert monitor._baselines["agent-001"].total_observations == 3

    def test_failure_updates_error_rate(self, monitor):
        monitor.record("agent-001", "read", "/data/file", success=True)
        monitor.record("agent-001", "read", "/data/file", success=False)
        assert monitor._baselines["agent-001"].avg_error_rate > 0


# ═══════════════════════════════════════════════════════════════════════════════
# _check_capability_probe()
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckCapabilityProbe:
    def test_no_anomaly_below_threshold(self, monitor):
        for _ in range(4):
            anomalies = monitor.record("agent-001", "read", "/restricted", success=False)
        probe_anomalies = [a for a in monitor._anomalies if a.anomaly_type == AnomalyType.CAPABILITY_PROBE]
        assert len(probe_anomalies) == 0

    def test_anomaly_at_threshold(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        probe_anomalies = [a for a in monitor._anomalies if a.anomaly_type == AnomalyType.CAPABILITY_PROBE]
        assert len(probe_anomalies) >= 1

    def test_probe_anomaly_is_critical(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        probe_anomalies = [a for a in monitor._anomalies if a.anomaly_type == AnomalyType.CAPABILITY_PROBE]
        if probe_anomalies:
            assert probe_anomalies[0].severity == AnomalySeverity.CRITICAL

    def test_probe_anomaly_requires_review(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        probe_anomalies = [a for a in monitor._anomalies if a.anomaly_type == AnomalyType.CAPABILITY_PROBE]
        if probe_anomalies:
            assert probe_anomalies[0].requires_human_review is True


# ═══════════════════════════════════════════════════════════════════════════════
# _check_new_resource() — with mature baseline
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckNewResource:
    def test_known_resource_no_anomaly(self, monitor):
        baseline = _seed_mature_baseline(monitor, "agent-001", resource="known-res")
        anomalies = monitor._check_new_resource("agent-001", "known-res", baseline)
        assert anomalies == []

    def test_new_resource_triggers_anomaly(self, monitor):
        baseline = _seed_mature_baseline(monitor, "agent-001", resource="known-res")
        anomalies = monitor._check_new_resource("agent-001", "never-seen", baseline)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.NEW_RESOURCE

    def test_new_resource_anomaly_is_medium(self, monitor):
        baseline = _seed_mature_baseline(monitor, "agent-001", resource="known-res")
        anomalies = monitor._check_new_resource("agent-001", "never-seen", baseline)
        if anomalies:
            assert anomalies[0].severity == AnomalySeverity.MEDIUM

    def test_new_resource_anomaly_does_not_require_review(self, monitor):
        baseline = _seed_mature_baseline(monitor, "agent-001", resource="known-res")
        anomalies = monitor._check_new_resource("agent-001", "never-seen", baseline)
        if anomalies:
            assert anomalies[0].requires_human_review is False


# ═══════════════════════════════════════════════════════════════════════════════
# _check_new_action() — with mature baseline
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckNewAction:
    def test_known_action_no_anomaly(self, monitor):
        baseline = _seed_mature_baseline(monitor, "agent-001", action="known-action")
        anomalies = monitor._check_new_action("agent-001", "known-action", baseline)
        assert anomalies == []

    def test_new_action_triggers_anomaly(self, monitor):
        baseline = _seed_mature_baseline(monitor, "agent-001", action="known-action")
        anomalies = monitor._check_new_action("agent-001", "never-done", baseline)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.NEW_ACTION

    def test_new_action_evidence_has_known_actions(self, monitor):
        baseline = _seed_mature_baseline(monitor, "agent-001", action="known-action")
        anomalies = monitor._check_new_action("agent-001", "never-done", baseline)
        if anomalies:
            assert "new_action" in anomalies[0].evidence


# ═══════════════════════════════════════════════════════════════════════════════
# _create_anomaly()
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateAnomaly:
    def test_anomaly_id_format(self, monitor):
        anomaly = monitor._create_anomaly(
            "agent-001", AnomalyType.RATE_SPIKE, AnomalySeverity.HIGH,
            "rate spike", {}, False
        )
        assert anomaly.anomaly_id.startswith("ANOM-")

    def test_anomaly_id_increments(self, monitor):
        a1 = monitor._create_anomaly("agent-001", AnomalyType.RATE_SPIKE, AnomalySeverity.LOW, "1", {}, False)
        a2 = monitor._create_anomaly("agent-001", AnomalyType.NEW_RESOURCE, AnomalySeverity.LOW, "2", {}, False)
        id1 = int(a1.anomaly_id.split("-")[1])
        id2 = int(a2.anomaly_id.split("-")[1])
        assert id2 == id1 + 1

    def test_anomaly_has_correct_type(self, monitor):
        a = monitor._create_anomaly(
            "agent-001", AnomalyType.SEQUENTIAL_ACCESS, AnomalySeverity.HIGH,
            "sequential", {}, True
        )
        assert a.anomaly_type == AnomalyType.SEQUENTIAL_ACCESS

    def test_anomaly_has_correct_severity(self, monitor):
        a = monitor._create_anomaly(
            "agent-001", AnomalyType.RATE_SPIKE, AnomalySeverity.CRITICAL,
            "critical spike", {}, True
        )
        assert a.severity == AnomalySeverity.CRITICAL

    def test_anomaly_requires_review_set(self, monitor):
        a = monitor._create_anomaly("agent-001", AnomalyType.RATE_SPIKE, AnomalySeverity.HIGH,
                                    "spike", {}, requires_human_review=True)
        assert a.requires_human_review is True

    def test_anomaly_not_resolved_by_default(self, monitor):
        a = monitor._create_anomaly("agent-001", AnomalyType.ERROR_SPIKE, AnomalySeverity.MEDIUM,
                                    "errors", {}, False)
        assert a.resolved is False


# ═══════════════════════════════════════════════════════════════════════════════
# get_unresolved_anomalies()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUnresolvedAnomalies:
    def test_empty_monitor_returns_empty(self, monitor):
        assert monitor.get_unresolved_anomalies() == []

    def test_returns_unresolved(self, monitor):
        # Trigger a capability probe anomaly
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        unresolved = monitor.get_unresolved_anomalies()
        assert len(unresolved) >= 1

    def test_filter_by_agent_id(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        for _ in range(5):
            monitor.record("agent-002", "read", "/restricted", success=False)
        unresolved = monitor.get_unresolved_anomalies(agent_id="agent-001")
        assert all(a.agent_id == "agent-001" for a in unresolved)

    def test_filter_by_severity(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        critical = monitor.get_unresolved_anomalies(severity=AnomalySeverity.CRITICAL)
        assert all(a.severity == AnomalySeverity.CRITICAL for a in critical)

    def test_filter_requires_review(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        reviewing = monitor.get_unresolved_anomalies(requires_review=True)
        assert all(a.requires_human_review is True for a in reviewing)

    def test_resolved_excluded(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        anomalies = monitor.get_unresolved_anomalies()
        if anomalies:
            monitor.resolve_anomaly(anomalies[0].anomaly_id, "false positive")
        remaining = monitor.get_unresolved_anomalies()
        assert all(not a.resolved for a in remaining)


# ═══════════════════════════════════════════════════════════════════════════════
# resolve_anomaly()
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveAnomaly:
    def test_resolve_existing_returns_true(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        anomalies = monitor.get_unresolved_anomalies()
        if anomalies:
            result = monitor.resolve_anomaly(anomalies[0].anomaly_id, "resolved")
            assert result is True

    def test_resolve_nonexistent_returns_false(self, monitor):
        result = monitor.resolve_anomaly("ANOM-999999", "notes")
        assert result is False

    def test_resolve_sets_resolution_notes(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        anomalies = monitor.get_unresolved_anomalies()
        if anomalies:
            monitor.resolve_anomaly(anomalies[0].anomaly_id, "false alarm")
            target = next(a for a in monitor._anomalies if a.anomaly_id == anomalies[0].anomaly_id)
            assert target.resolution_notes == "false alarm"

    def test_resolve_marks_resolved(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        anomalies = monitor.get_unresolved_anomalies()
        if anomalies:
            monitor.resolve_anomaly(anomalies[0].anomaly_id, "ok")
            target = next(a for a in monitor._anomalies if a.anomaly_id == anomalies[0].anomaly_id)
            assert target.resolved is True


# ═══════════════════════════════════════════════════════════════════════════════
# get_dashboard_summary()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetDashboardSummary:
    def test_empty_monitor_summary(self, monitor):
        summary = monitor.get_dashboard_summary()
        assert summary["total_unresolved"] == 0
        assert summary["requires_human_review"] == 0

    def test_has_required_keys(self, monitor):
        summary = monitor.get_dashboard_summary()
        for key in ["total_unresolved", "requires_human_review", "by_severity", "by_type"]:
            assert key in summary

    def test_counts_unresolved(self, monitor):
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        summary = monitor.get_dashboard_summary()
        assert summary["total_unresolved"] >= 1

    def test_by_severity_structure(self, monitor):
        summary = monitor.get_dashboard_summary()
        for level in ("critical", "high", "medium", "low"):
            assert level in summary["by_severity"]

    def test_counts_review_required(self, monitor):
        # Probe anomalies require human review
        for _ in range(5):
            monitor.record("agent-001", "read", "/restricted", success=False)
        summary = monitor.get_dashboard_summary()
        assert summary["requires_human_review"] >= 1
