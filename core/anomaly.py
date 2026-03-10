# TelsonBase/core/anomaly.py
# REM: =======================================================================================
# REM: BEHAVIORAL ANOMALY DETECTION FOR AGENTS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Even with capabilities enforced, we need to detect when an
# REM: agent is behaving unusually. A compromised agent might stay within its permissions
# REM: but exhibit patterns that indicate something is wrong:
# REM:   - Sudden spike in activity
# REM:   - Accessing resources it never accessed before
# REM:   - Unusual timing patterns
# REM:   - Sequential access patterns (enumeration)
# REM:
# REM: This system builds behavioral baselines and flags deviations for human review.
# REM:
# REM: v4.1.0CC: Added Redis persistence for baselines and anomalies
# REM: =======================================================================================

import json
import logging
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)

# REM: Import persistence store (lazy to avoid circular imports)
_anomaly_store = None

def _get_store():
    """REM: Lazy-load the anomaly store to avoid circular imports."""
    global _anomaly_store
    if _anomaly_store is None:
        try:
            from core.persistence import anomaly_store
            _anomaly_store = anomaly_store
        except Exception as e:
            logger.warning(f"REM: Redis persistence unavailable, using in-memory: {e}")
            _anomaly_store = False
    return _anomaly_store if _anomaly_store else None


class AnomalyType(str, Enum):
    """REM: Types of anomalies we can detect."""
    RATE_SPIKE = "rate_spike"
    NEW_RESOURCE = "new_resource"
    NEW_ACTION = "new_action"
    UNUSUAL_TIMING = "unusual_timing"
    SEQUENTIAL_ACCESS = "sequential_access"
    ERROR_SPIKE = "error_spike"
    CAPABILITY_PROBE = "capability_probe"  # Repeatedly hitting permission denials


class AnomalySeverity(str, Enum):
    """REM: Severity levels for anomalies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AgentBehaviorRecord:
    """
    REM: A single recorded action by an agent.
    """
    timestamp: datetime
    action: str
    resource: str
    success: bool
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Anomaly:
    """
    REM: A detected anomaly.
    """
    anomaly_id: str
    agent_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    description: str
    detected_at: datetime
    evidence: Dict[str, Any]
    requires_human_review: bool = False
    resolved: bool = False
    resolution_notes: Optional[str] = None


@dataclass
class AgentBaseline:
    """
    REM: Behavioral baseline for an agent.
    REM: Built up over time from observed behavior.
    """
    agent_id: str
    
    # REM: Rate metrics (actions per minute)
    avg_actions_per_minute: float = 0.0
    std_actions_per_minute: float = 0.0
    max_observed_rate: float = 0.0
    
    # REM: Resource access patterns
    known_resources: Set[str] = field(default_factory=set)
    known_actions: Set[str] = field(default_factory=set)
    
    # REM: Timing patterns (hour of day distribution)
    hourly_distribution: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    
    # REM: Error rates
    avg_error_rate: float = 0.0
    
    # REM: Baseline quality
    total_observations: int = 0
    baseline_start: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    
    def is_mature(self, min_observations: int = 100) -> bool:
        """REM: Check if we have enough data for reliable anomaly detection."""
        return self.total_observations >= min_observations


class BehaviorMonitor:
    """
    REM: Monitors agent behavior and detects anomalies.
    REM: v4.1.0CC: Now persists baselines and anomalies to Redis.
    """

    # REM: Configuration thresholds
    RATE_SPIKE_THRESHOLD = 3.0  # Standard deviations above mean
    ERROR_SPIKE_THRESHOLD = 2.0  # Times the baseline error rate
    NEW_RESOURCE_SEVERITY = AnomalySeverity.MEDIUM
    SEQUENTIAL_ACCESS_WINDOW = 60  # Seconds to look for sequential patterns
    SEQUENTIAL_ACCESS_THRESHOLD = 10  # Number of sequential accesses to flag
    CAPABILITY_PROBE_THRESHOLD = 5  # Permission denials in short window

    def __init__(self):
        self._baselines: Dict[str, AgentBaseline] = {}
        self._recent_records: Dict[str, List[AgentBehaviorRecord]] = defaultdict(list)
        self._anomalies: List[Anomaly] = []
        self._anomaly_counter = 0

        # REM: Track recent permission denials for probe detection
        self._recent_denials: Dict[str, List[datetime]] = defaultdict(list)

        # REM: Load baselines from persistence
        self._load_from_persistence()

    def _load_from_persistence(self):
        """REM: Load baselines from Redis on startup."""
        store = _get_store()
        if store:
            try:
                # REM: Load unresolved anomalies
                unresolved = store.get_unresolved_anomalies(limit=500)
                for anom_data in unresolved:
                    self._anomalies.append(self._dict_to_anomaly(anom_data))
                    self._anomaly_counter = max(self._anomaly_counter,
                        int(anom_data.get("anomaly_id", "ANOM-0").split("-")[1]) if "-" in anom_data.get("anomaly_id", "") else 0)
                logger.info(f"REM: Loaded {len(self._anomalies)} unresolved anomalies from persistence_Thank_You")
            except Exception as e:
                logger.warning(f"REM: Failed to load anomalies from persistence: {e}")

    def _dict_to_anomaly(self, data: Dict) -> Anomaly:
        """REM: Convert stored dict back to Anomaly."""
        return Anomaly(
            anomaly_id=data.get("anomaly_id", "ANOM-UNKNOWN"),
            agent_id=data.get("agent_id", "unknown"),
            anomaly_type=AnomalyType(data.get("anomaly_type", "rate_spike")),
            severity=AnomalySeverity(data.get("severity", "medium")),
            description=data.get("description", ""),
            detected_at=datetime.fromisoformat(data["detected_at"]) if isinstance(data.get("detected_at"), str) else datetime.now(timezone.utc),
            evidence=data.get("evidence", {}),
            requires_human_review=data.get("requires_human_review", False),
            resolved=data.get("resolved", False),
            resolution_notes=data.get("resolution_notes")
        )

    def _anomaly_to_dict(self, anomaly: Anomaly) -> Dict:
        """REM: Convert Anomaly to storable dict."""
        return {
            "anomaly_id": anomaly.anomaly_id,
            "agent_id": anomaly.agent_id,
            "anomaly_type": anomaly.anomaly_type.value,
            "severity": anomaly.severity.value,
            "description": anomaly.description,
            "detected_at": anomaly.detected_at.isoformat(),
            "evidence": anomaly.evidence,
            "requires_human_review": anomaly.requires_human_review,
            "resolved": anomaly.resolved,
            "resolution_notes": anomaly.resolution_notes
        }

    def _persist_anomaly(self, anomaly: Anomaly):
        """REM: Persist an anomaly to Redis."""
        store = _get_store()
        if store:
            try:
                store.store_anomaly(self._anomaly_to_dict(anomaly))
            except Exception as e:
                logger.warning(f"REM: Failed to persist anomaly: {e}")

    def _persist_baseline(self, agent_id: str, baseline: AgentBaseline):
        """REM: Persist a baseline to Redis."""
        store = _get_store()
        if store:
            try:
                baseline_dict = {
                    "agent_id": baseline.agent_id,
                    "avg_actions_per_minute": baseline.avg_actions_per_minute,
                    "std_actions_per_minute": baseline.std_actions_per_minute,
                    "max_observed_rate": baseline.max_observed_rate,
                    "known_resources": list(baseline.known_resources),
                    "known_actions": list(baseline.known_actions),
                    "hourly_distribution": dict(baseline.hourly_distribution),
                    "avg_error_rate": baseline.avg_error_rate,
                    "total_observations": baseline.total_observations,
                    "baseline_start": baseline.baseline_start.isoformat() if baseline.baseline_start else None,
                    "last_updated": baseline.last_updated.isoformat() if baseline.last_updated else None
                }
                store.store_baseline(agent_id, baseline_dict)
            except Exception as e:
                logger.warning(f"REM: Failed to persist baseline: {e}")
    
    def record(
        self,
        agent_id: str,
        action: str,
        resource: str,
        success: bool = True,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Anomaly]:
        """
        REM: Record an agent action and check for anomalies.
        
        Returns:
            List of any anomalies detected
        """
        now = datetime.now(timezone.utc)
        
        record = AgentBehaviorRecord(
            timestamp=now,
            action=action,
            resource=resource,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata or {}
        )
        
        # REM: Store record
        self._recent_records[agent_id].append(record)
        
        # REM: Cleanup old records (keep last hour)
        cutoff = now - timedelta(hours=1)
        self._recent_records[agent_id] = [
            r for r in self._recent_records[agent_id]
            if r.timestamp > cutoff
        ]
        
        # REM: Get or create baseline
        if agent_id not in self._baselines:
            self._baselines[agent_id] = AgentBaseline(
                agent_id=agent_id,
                baseline_start=now
            )
        
        baseline = self._baselines[agent_id]
        
        # REM: Detect anomalies
        anomalies = []
        
        # REM: Only flag anomalies if baseline is mature
        if baseline.is_mature():
            anomalies.extend(self._check_rate_spike(agent_id, baseline))
            anomalies.extend(self._check_new_resource(agent_id, resource, baseline))
            anomalies.extend(self._check_new_action(agent_id, action, baseline))
            anomalies.extend(self._check_unusual_timing(agent_id, now, baseline))
            anomalies.extend(self._check_sequential_access(agent_id))
            anomalies.extend(self._check_error_spike(agent_id, baseline))
        
        # REM: Always check for capability probing (doesn't need mature baseline)
        if not success:
            anomalies.extend(self._check_capability_probe(agent_id, now))
        
        # REM: Update baseline with this observation
        self._update_baseline(baseline, record)
        
        # REM: Store detected anomalies
        self._anomalies.extend(anomalies)
        
        # REM: Log and audit anomalies
        for anomaly in anomalies:
            self._handle_anomaly(anomaly)
        
        return anomalies
    
    def _check_rate_spike(self, agent_id: str, baseline: AgentBaseline) -> List[Anomaly]:
        """REM: Check for sudden spike in activity rate."""
        records = self._recent_records[agent_id]
        if len(records) < 2:
            return []
        
        # REM: Calculate current rate (actions per minute over last 5 minutes)
        five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        recent = [r for r in records if r.timestamp > five_min_ago]
        current_rate = len(recent) / 5.0
        
        if baseline.std_actions_per_minute == 0:
            return []
        
        z_score = (current_rate - baseline.avg_actions_per_minute) / baseline.std_actions_per_minute
        
        if z_score > self.RATE_SPIKE_THRESHOLD:
            return [self._create_anomaly(
                agent_id=agent_id,
                anomaly_type=AnomalyType.RATE_SPIKE,
                severity=AnomalySeverity.HIGH if z_score > 5 else AnomalySeverity.MEDIUM,
                description=f"Activity rate {current_rate:.1f}/min is {z_score:.1f} std devs above baseline {baseline.avg_actions_per_minute:.1f}/min",
                evidence={
                    "current_rate": current_rate,
                    "baseline_avg": baseline.avg_actions_per_minute,
                    "baseline_std": baseline.std_actions_per_minute,
                    "z_score": z_score
                },
                requires_human_review=z_score > 5
            )]
        
        return []
    
    def _check_new_resource(self, agent_id: str, resource: str, baseline: AgentBaseline) -> List[Anomaly]:
        """REM: Check if agent is accessing a resource it's never accessed before."""
        if resource not in baseline.known_resources:
            return [self._create_anomaly(
                agent_id=agent_id,
                anomaly_type=AnomalyType.NEW_RESOURCE,
                severity=self.NEW_RESOURCE_SEVERITY,
                description=f"Agent accessing new resource: ::{resource}::. Not in baseline of {len(baseline.known_resources)} known resources.",
                evidence={
                    "new_resource": resource,
                    "known_resources_count": len(baseline.known_resources)
                },
                requires_human_review=False
            )]
        return []
    
    def _check_new_action(self, agent_id: str, action: str, baseline: AgentBaseline) -> List[Anomaly]:
        """REM: Check if agent is performing an action it's never performed before."""
        if action not in baseline.known_actions:
            return [self._create_anomaly(
                agent_id=agent_id,
                anomaly_type=AnomalyType.NEW_ACTION,
                severity=AnomalySeverity.MEDIUM,
                description=f"Agent performing new action: ::{action}::. Not in baseline of {len(baseline.known_actions)} known actions.",
                evidence={
                    "new_action": action,
                    "known_actions": list(baseline.known_actions)
                },
                requires_human_review=False
            )]
        return []
    
    def _check_unusual_timing(self, agent_id: str, timestamp: datetime, baseline: AgentBaseline) -> List[Anomaly]:
        """REM: Check if agent is active at unusual times."""
        hour = timestamp.hour
        total_actions = sum(baseline.hourly_distribution.values())
        
        if total_actions < 100:
            return []
        
        # REM: Calculate expected vs actual for this hour
        expected_pct = baseline.hourly_distribution.get(hour, 0) / total_actions
        
        # REM: Flag if this hour has <1% of historical activity
        if expected_pct < 0.01 and total_actions > 500:
            return [self._create_anomaly(
                agent_id=agent_id,
                anomaly_type=AnomalyType.UNUSUAL_TIMING,
                severity=AnomalySeverity.LOW,
                description=f"Agent active at unusual hour ({hour}:00 UTC). Only {expected_pct*100:.1f}% of historical activity occurs at this time.",
                evidence={
                    "hour": hour,
                    "historical_pct": expected_pct,
                    "hourly_distribution": dict(baseline.hourly_distribution)
                },
                requires_human_review=False
            )]
        return []
    
    def _check_sequential_access(self, agent_id: str) -> List[Anomaly]:
        """REM: Check for sequential/enumeration access patterns."""
        records = self._recent_records[agent_id]
        
        if len(records) < self.SEQUENTIAL_ACCESS_THRESHOLD:
            return []
        
        # REM: Look at recent records within window
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.SEQUENTIAL_ACCESS_WINDOW)
        recent = [r for r in records if r.timestamp > cutoff]
        
        if len(recent) < self.SEQUENTIAL_ACCESS_THRESHOLD:
            return []
        
        # REM: Check for sequential patterns in resource names
        resources = [r.resource for r in recent]
        
        # REM: Simple pattern: incrementing numbers
        import re
        numbers = []
        for res in resources:
            match = re.search(r'(\d+)', res)
            if match:
                numbers.append(int(match.group(1)))
        
        if len(numbers) >= self.SEQUENTIAL_ACCESS_THRESHOLD:
            # REM: Check if numbers are sequential
            sorted_nums = sorted(numbers)
            is_sequential = all(
                sorted_nums[i+1] - sorted_nums[i] == 1
                for i in range(len(sorted_nums)-1)
            )
            
            if is_sequential:
                return [self._create_anomaly(
                    agent_id=agent_id,
                    anomaly_type=AnomalyType.SEQUENTIAL_ACCESS,
                    severity=AnomalySeverity.HIGH,
                    description=f"Sequential access pattern detected. Possible enumeration attack.",
                    evidence={
                        "resources": resources[-10:],
                        "detected_sequence": sorted_nums
                    },
                    requires_human_review=True
                )]
        
        return []
    
    def _check_error_spike(self, agent_id: str, baseline: AgentBaseline) -> List[Anomaly]:
        """REM: Check for spike in error rate."""
        records = self._recent_records[agent_id]
        
        if len(records) < 10:
            return []
        
        # REM: Calculate recent error rate
        recent_errors = sum(1 for r in records[-50:] if not r.success)
        recent_error_rate = recent_errors / min(50, len(records))
        
        if baseline.avg_error_rate == 0:
            threshold = 0.1  # 10% error rate if no baseline
        else:
            threshold = baseline.avg_error_rate * self.ERROR_SPIKE_THRESHOLD
        
        if recent_error_rate > threshold and recent_error_rate > 0.1:
            return [self._create_anomaly(
                agent_id=agent_id,
                anomaly_type=AnomalyType.ERROR_SPIKE,
                severity=AnomalySeverity.MEDIUM,
                description=f"Error rate {recent_error_rate*100:.1f}% exceeds threshold {threshold*100:.1f}%",
                evidence={
                    "current_error_rate": recent_error_rate,
                    "baseline_error_rate": baseline.avg_error_rate,
                    "recent_errors": recent_errors
                },
                requires_human_review=recent_error_rate > 0.5
            )]
        return []
    
    def _check_capability_probe(self, agent_id: str, timestamp: datetime) -> List[Anomaly]:
        """REM: Check for repeated permission denials (probing for capabilities)."""
        self._recent_denials[agent_id].append(timestamp)
        
        # REM: Cleanup old denials
        cutoff = timestamp - timedelta(minutes=5)
        self._recent_denials[agent_id] = [
            t for t in self._recent_denials[agent_id]
            if t > cutoff
        ]
        
        if len(self._recent_denials[agent_id]) >= self.CAPABILITY_PROBE_THRESHOLD:
            return [self._create_anomaly(
                agent_id=agent_id,
                anomaly_type=AnomalyType.CAPABILITY_PROBE,
                severity=AnomalySeverity.CRITICAL,
                description=f"Agent hit {len(self._recent_denials[agent_id])} permission denials in 5 minutes. Possible capability probing.",
                evidence={
                    "denial_count": len(self._recent_denials[agent_id]),
                    "denial_timestamps": [t.isoformat() for t in self._recent_denials[agent_id]]
                },
                requires_human_review=True
            )]
        return []
    
    def _update_baseline(self, baseline: AgentBaseline, record: AgentBehaviorRecord):
        """REM: Update baseline with new observation."""
        baseline.total_observations += 1
        baseline.last_updated = record.timestamp

        # REM: Update known resources and actions
        baseline.known_resources.add(record.resource)
        baseline.known_actions.add(record.action)

        # REM: Update hourly distribution
        baseline.hourly_distribution[record.timestamp.hour] += 1

        # REM: Update rate metrics (exponential moving average)
        # REM: Simplified - in production you'd use proper time-series analysis
        if baseline.total_observations > 1:
            alpha = 0.1  # Smoothing factor
            baseline.avg_error_rate = (
                alpha * (0 if record.success else 1) +
                (1 - alpha) * baseline.avg_error_rate
            )

        # REM: Persist baseline every 50 observations to reduce Redis writes
        if baseline.total_observations % 50 == 0:
            self._persist_baseline(baseline.agent_id, baseline)
    
    def _create_anomaly(
        self,
        agent_id: str,
        anomaly_type: AnomalyType,
        severity: AnomalySeverity,
        description: str,
        evidence: Dict[str, Any],
        requires_human_review: bool
    ) -> Anomaly:
        """REM: Create an anomaly record."""
        self._anomaly_counter += 1
        return Anomaly(
            anomaly_id=f"ANOM-{self._anomaly_counter:06d}",
            agent_id=agent_id,
            anomaly_type=anomaly_type,
            severity=severity,
            description=description,
            detected_at=datetime.now(timezone.utc),
            evidence=evidence,
            requires_human_review=requires_human_review
        )
    
    def _handle_anomaly(self, anomaly: Anomaly):
        """REM: Log, audit, and persist the anomaly."""
        severity_to_log = {
            AnomalySeverity.LOW: logging.INFO,
            AnomalySeverity.MEDIUM: logging.WARNING,
            AnomalySeverity.HIGH: logging.WARNING,
            AnomalySeverity.CRITICAL: logging.ERROR,
        }

        logger.log(
            severity_to_log[anomaly.severity],
            f"REM: ANOMALY DETECTED ::{anomaly.anomaly_id}:: - "
            f"Agent ::{anomaly.agent_id}:: - Type ::{anomaly.anomaly_type.value}:: - "
            f"Severity ::{anomaly.severity.value}:: - {anomaly.description}_Thank_You_But_No"
        )

        # REM: Persist anomaly to Redis
        self._persist_anomaly(anomaly)

        audit.log(
            AuditEventType.AGENT_ERROR,
            f"Anomaly detected: {anomaly.anomaly_type.value} for agent ::{anomaly.agent_id}::",
            actor=anomaly.agent_id,
            details={
                "anomaly_id": anomaly.anomaly_id,
                "type": anomaly.anomaly_type.value,
                "severity": anomaly.severity.value,
                "evidence": anomaly.evidence,
                "requires_human_review": anomaly.requires_human_review
            },
            qms_status="Thank_You_But_No"
        )
    
    def get_unresolved_anomalies(
        self,
        agent_id: Optional[str] = None,
        severity: Optional[AnomalySeverity] = None,
        requires_review: Optional[bool] = None
    ) -> List[Anomaly]:
        """REM: Get list of unresolved anomalies with optional filters."""
        results = [a for a in self._anomalies if not a.resolved]
        
        if agent_id:
            results = [a for a in results if a.agent_id == agent_id]
        if severity:
            results = [a for a in results if a.severity == severity]
        if requires_review is not None:
            results = [a for a in results if a.requires_human_review == requires_review]
        
        return results
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """REM: Summary for system analysis and monitoring dashboards."""
        unresolved = [a for a in self._anomalies if not a.resolved]
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_type: Dict[str, int] = {}
        requires_review = 0

        for a in unresolved:
            by_severity[a.severity.value] = by_severity.get(a.severity.value, 0) + 1
            by_type[a.anomaly_type.value] = by_type.get(a.anomaly_type.value, 0) + 1
            if a.requires_human_review:
                requires_review += 1

        return {
            "total_unresolved": len(unresolved),
            "requires_human_review": requires_review,
            "by_severity": by_severity,
            "by_type": by_type,
        }

    def resolve_anomaly(self, anomaly_id: str, resolution_notes: str) -> bool:
        """REM: Mark an anomaly as resolved."""
        for anomaly in self._anomalies:
            if anomaly.anomaly_id == anomaly_id:
                anomaly.resolved = True
                anomaly.resolution_notes = resolution_notes

                # REM: Persist resolution to Redis
                store = _get_store()
                if store:
                    try:
                        store.resolve_anomaly(anomaly_id, resolution_notes)
                    except Exception as e:
                        logger.warning(f"REM: Failed to persist anomaly resolution: {e}")

                logger.info(f"REM: Anomaly ::{anomaly_id}:: resolved: {resolution_notes}_Thank_You")
                return True
        return False


# REM: Global monitor instance
behavior_monitor = BehaviorMonitor()
