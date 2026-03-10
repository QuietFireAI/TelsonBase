# TelsonBase/core/manners.py
# REM: =======================================================================================
# REM: MANNERS COMPLIANCE ENGINE — RUNTIME PRINCIPLE ENFORCEMENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Runtime evaluation engine for MANNERS.md principles. Every agent
# REM: receives a Manners Compliance Score (0.0–1.0) computed from five Anthropic-aligned
# REM: principles. Scores determine operational status:
# REM:   EXEMPLARY (0.90+) — full autonomous operation
# REM:   COMPLIANT (0.75+) — normal operation
# REM:   DEGRADED  (0.50+) — increased monitoring
# REM:   NON_COMPLIANT (0.25+) — restricted to read-only
# REM:   SUSPENDED (0.00+) — quarantined, human review required
# REM:
# REM: Aligned with:
# REM:   - Anthropic: "Framework for Developing Safe and Trustworthy Agents" (2025)
# REM:   - Anthropic: "Core Views on AI Safety" (2025)
# REM:   - Anthropic: Responsible Scaling Policy (RSP) v2.0
# REM:
# REM: v7.2.0CC: Initial implementation
# REM: =======================================================================================

import logging
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
import json

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)

# REM: Lazy-load persistence to avoid circular imports
_manners_store = None

def _get_store():
    """REM: Lazy-load Redis store for Manners compliance data."""
    global _manners_store
    if _manners_store is None:
        try:
            from core.persistence import security_store
            _manners_store = security_store
        except Exception as e:
            logger.warning(f"REM: Redis persistence unavailable for Manners engine: {e}")
            _manners_store = False
    return _manners_store if _manners_store else None


# REM: =======================================================================================
# REM: MANNERS PRINCIPLES — THE FIVE PILLARS
# REM: =======================================================================================

class MannersPrinciple(str, Enum):
    """REM: The five Manners principles aligned with Anthropic's framework."""
    HUMAN_CONTROL = "manners_1_human_control"
    TRANSPARENCY = "manners_2_transparency"
    VALUE_ALIGNMENT = "manners_3_value_alignment"
    PRIVACY = "manners_4_privacy"
    SECURITY = "manners_5_security"


class ComplianceStatus(str, Enum):
    """REM: Agent compliance status derived from Manners score."""
    EXEMPLARY = "exemplary"         # 0.90 — 1.00
    COMPLIANT = "compliant"         # 0.75 — 0.89
    DEGRADED = "degraded"           # 0.50 — 0.74
    NON_COMPLIANT = "non_compliant" # 0.25 — 0.49
    SUSPENDED = "suspended"         # 0.00 — 0.24


class ViolationType(str, Enum):
    """REM: Types of Manners violations."""
    # MANNERS-1: Human Control
    APPROVAL_BYPASS = "approval_bypass"
    TRUST_ESCALATION = "trust_escalation"
    UNAUTHORIZED_DESTRUCTIVE = "unauthorized_destructive"
    # MANNERS-2: Transparency
    UNAUDITED_ACTION = "unaudited_action"
    NON_QMS_MESSAGE = "non_qms_message"
    MISSING_JUSTIFICATION = "missing_justification"
    # MANNERS-3: Value Alignment
    CAPABILITY_VIOLATION = "capability_violation"
    OUT_OF_ROLE_ACTION = "out_of_role_action"
    BEHAVIORAL_ANOMALY = "behavioral_anomaly"
    # MANNERS-4: Privacy
    CROSS_TENANT_ACCESS = "cross_tenant_access"
    UNAUTHORIZED_TRANSMISSION = "unauthorized_transmission"
    CLASSIFICATION_VIOLATION = "classification_violation"
    # MANNERS-5: Security
    UNSIGNED_MESSAGE = "unsigned_message"
    RATE_LIMIT_BYPASS = "rate_limit_bypass"
    INJECTION_ATTEMPT = "injection_attempt"


# REM: Map violations to their principle
VIOLATION_PRINCIPLE_MAP: Dict[ViolationType, MannersPrinciple] = {
    ViolationType.APPROVAL_BYPASS: MannersPrinciple.HUMAN_CONTROL,
    ViolationType.TRUST_ESCALATION: MannersPrinciple.HUMAN_CONTROL,
    ViolationType.UNAUTHORIZED_DESTRUCTIVE: MannersPrinciple.HUMAN_CONTROL,
    ViolationType.UNAUDITED_ACTION: MannersPrinciple.TRANSPARENCY,
    ViolationType.NON_QMS_MESSAGE: MannersPrinciple.TRANSPARENCY,
    ViolationType.MISSING_JUSTIFICATION: MannersPrinciple.TRANSPARENCY,
    ViolationType.CAPABILITY_VIOLATION: MannersPrinciple.VALUE_ALIGNMENT,
    ViolationType.OUT_OF_ROLE_ACTION: MannersPrinciple.VALUE_ALIGNMENT,
    ViolationType.BEHAVIORAL_ANOMALY: MannersPrinciple.VALUE_ALIGNMENT,
    ViolationType.CROSS_TENANT_ACCESS: MannersPrinciple.PRIVACY,
    ViolationType.UNAUTHORIZED_TRANSMISSION: MannersPrinciple.PRIVACY,
    ViolationType.CLASSIFICATION_VIOLATION: MannersPrinciple.PRIVACY,
    ViolationType.UNSIGNED_MESSAGE: MannersPrinciple.SECURITY,
    ViolationType.RATE_LIMIT_BYPASS: MannersPrinciple.SECURITY,
    ViolationType.INJECTION_ATTEMPT: MannersPrinciple.SECURITY,
}

# REM: Violation severity weights (higher = more impact on score)
VIOLATION_SEVERITY: Dict[ViolationType, float] = {
    ViolationType.APPROVAL_BYPASS: 0.30,
    ViolationType.TRUST_ESCALATION: 0.25,
    ViolationType.UNAUTHORIZED_DESTRUCTIVE: 0.35,
    ViolationType.UNAUDITED_ACTION: 0.10,
    ViolationType.NON_QMS_MESSAGE: 0.05,
    ViolationType.MISSING_JUSTIFICATION: 0.10,
    ViolationType.CAPABILITY_VIOLATION: 0.25,
    ViolationType.OUT_OF_ROLE_ACTION: 0.20,
    ViolationType.BEHAVIORAL_ANOMALY: 0.15,
    ViolationType.CROSS_TENANT_ACCESS: 0.35,
    ViolationType.UNAUTHORIZED_TRANSMISSION: 0.30,
    ViolationType.CLASSIFICATION_VIOLATION: 0.20,
    ViolationType.UNSIGNED_MESSAGE: 0.15,
    ViolationType.RATE_LIMIT_BYPASS: 0.10,
    ViolationType.INJECTION_ATTEMPT: 0.25,
}

# REM: Auto-suspension threshold: 3+ violations in 24 hours
AUTO_SUSPEND_THRESHOLD = 3
AUTO_SUSPEND_WINDOW_HOURS = 24

# REM: New agent grace period (default to DEGRADED monitoring)
NEW_AGENT_GRACE_HOURS = 24


# REM: =======================================================================================
# REM: DATA MODELS
# REM: =======================================================================================

@dataclass
class MannersViolation:
    """REM: A recorded Manners violation for an agent."""
    agent_name: str
    violation_type: ViolationType
    principle: MannersPrinciple
    severity: float
    timestamp: datetime
    details: str
    action: Optional[str] = None
    resource: Optional[str] = None
    auto_resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "violation_type": self.violation_type.value,
            "principle": self.principle.value,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "action": self.action,
            "resource": self.resource,
            "auto_resolved": self.auto_resolved,
        }


@dataclass
class PrincipleScore:
    """REM: Score for a single Manners principle."""
    principle: MannersPrinciple
    score: float  # 0.0 — 1.0
    violations_count: int
    last_violation: Optional[datetime] = None
    details: str = ""


@dataclass
class MannersComplianceReport:
    """REM: Full Manners compliance report for an agent."""
    agent_name: str
    overall_score: float
    status: ComplianceStatus
    principle_scores: Dict[str, PrincipleScore]
    total_violations: int
    violations_24h: int
    evaluated_at: datetime
    first_seen: Optional[datetime] = None
    is_grace_period: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "overall_score": round(self.overall_score, 3),
            "status": self.status.value,
            "principle_scores": {
                k: {
                    "principle": v.principle.value,
                    "score": round(v.score, 3),
                    "violations_count": v.violations_count,
                    "last_violation": v.last_violation.isoformat() if v.last_violation else None,
                    "details": v.details,
                }
                for k, v in self.principle_scores.items()
            },
            "total_violations": self.total_violations,
            "violations_24h": self.violations_24h,
            "evaluated_at": self.evaluated_at.isoformat(),
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "is_grace_period": self.is_grace_period,
        }


# REM: =======================================================================================
# REM: MANNERS COMPLIANCE ENGINE
# REM: =======================================================================================

class MannersEngine:
    """
    REM: Runtime Manners compliance evaluator.
    REM: Tracks violations per agent, computes principle scores, determines compliance status.
    REM: Integrates with anomaly detection, audit chain, and trust level systems.
    """

    def __init__(self):
        # REM: In-memory violation store (persisted to Redis when available)
        self._violations: Dict[str, List[MannersViolation]] = {}
        # REM: Agent first-seen timestamps for grace period
        self._first_seen: Dict[str, datetime] = {}
        # REM: Cached compliance reports
        self._cached_reports: Dict[str, Tuple[datetime, MannersComplianceReport]] = {}
        self._cache_ttl_seconds = 60  # REM: Re-evaluate every 60 seconds max
        logger.info("REM: Manners Compliance Engine initialized")

    def register_agent(self, agent_name: str) -> None:
        """REM: Register an agent with the Manners engine. Sets first-seen timestamp."""
        now = datetime.now(timezone.utc)
        if agent_name not in self._first_seen:
            self._first_seen[agent_name] = now
            self._violations.setdefault(agent_name, [])
            logger.info(f"REM: Manners registered agent: {agent_name}")
            self._persist_first_seen(agent_name, now)

    def record_violation(
        self,
        agent_name: str,
        violation_type: ViolationType,
        details: str,
        action: Optional[str] = None,
        resource: Optional[str] = None,
    ) -> MannersViolation:
        """
        REM: Record a Manners violation for an agent.
        REM: Returns the violation record. Triggers auto-suspension if threshold exceeded.
        """
        self._violations.setdefault(agent_name, [])

        principle = VIOLATION_PRINCIPLE_MAP[violation_type]
        severity = VIOLATION_SEVERITY[violation_type]
        now = datetime.now(timezone.utc)

        violation = MannersViolation(
            agent_name=agent_name,
            violation_type=violation_type,
            principle=principle,
            severity=severity,
            timestamp=now,
            details=details,
            action=action,
            resource=resource,
        )

        self._violations[agent_name].append(violation)

        # REM: Invalidate cache immediately — must happen before any fallible calls
        self._cached_reports.pop(agent_name, None)

        self._persist_violation(violation)

        # REM: Audit the violation
        audit.log(
            event_type=AuditEventType.SECURITY_ALERT,
            agent_name=agent_name,
            action=f"manners_violation:{violation_type.value}",
            resource=resource or "n/a",
            details={
                "principle": principle.value,
                "severity": severity,
                "details": details,
                "action": action,
            },
        )

        logger.warning(
            f"REM: Manners violation — {agent_name}: {violation_type.value} "
            f"(principle={principle.value}, severity={severity})"
        )

        # REM: Check for auto-suspension
        self._check_auto_suspend(agent_name)

        return violation

    def evaluate(self, agent_name: str) -> MannersComplianceReport:
        """
        REM: Evaluate an agent's Manners compliance.
        REM: Returns a full compliance report with per-principle scores.
        """
        now = datetime.now(timezone.utc)

        # REM: Check cache
        if agent_name in self._cached_reports:
            cached_time, cached_report = self._cached_reports[agent_name]
            if (now - cached_time).total_seconds() < self._cache_ttl_seconds:
                return cached_report

        self._violations.setdefault(agent_name, [])
        violations = self._violations[agent_name]

        # REM: Calculate per-principle scores
        principle_scores = {}
        for principle in MannersPrinciple:
            principle_violations = [
                v for v in violations
                if v.principle == principle and not v.auto_resolved
            ]
            # REM: Score starts at 1.0, each violation reduces by its severity
            # REM: Violations decay over time (older = less impact)
            score = 1.0
            last_violation = None
            for v in principle_violations:
                age_hours = (now - v.timestamp).total_seconds() / 3600
                # REM: Violations decay: full impact for 24h, then 50% at 72h, 25% at 168h
                if age_hours <= 24:
                    decay = 1.0
                elif age_hours <= 72:
                    decay = 0.5
                elif age_hours <= 168:
                    decay = 0.25
                else:
                    decay = 0.1
                score -= v.severity * decay
                if last_violation is None or v.timestamp > last_violation:
                    last_violation = v.timestamp

            score = max(0.0, min(1.0, score))
            principle_scores[principle.value] = PrincipleScore(
                principle=principle,
                score=score,
                violations_count=len(principle_violations),
                last_violation=last_violation,
                details=f"{len(principle_violations)} active violations" if principle_violations else "Clean",
            )

        # REM: Overall score is equal-weighted average of 5 principles
        overall_score = sum(ps.score for ps in principle_scores.values()) / 5.0

        # REM: Count 24-hour violations
        cutoff_24h = now - timedelta(hours=24)
        violations_24h = len([
            v for v in violations
            if v.timestamp >= cutoff_24h and not v.auto_resolved
        ])

        # REM: Determine status
        first_seen = self._first_seen.get(agent_name)
        is_grace = False
        if first_seen and (now - first_seen).total_seconds() < NEW_AGENT_GRACE_HOURS * 3600:
            is_grace = True
            # REM: New agents default to DEGRADED at best
            status = self._score_to_status(min(overall_score, 0.74))
        else:
            status = self._score_to_status(overall_score)

        report = MannersComplianceReport(
            agent_name=agent_name,
            overall_score=overall_score,
            status=status,
            principle_scores=principle_scores,
            total_violations=len([v for v in violations if not v.auto_resolved]),
            violations_24h=violations_24h,
            evaluated_at=now,
            first_seen=first_seen,
            is_grace_period=is_grace,
        )

        # REM: Cache the report
        self._cached_reports[agent_name] = (now, report)

        return report

    def evaluate_all(self) -> List[MannersComplianceReport]:
        """REM: Evaluate Manners compliance for all known agents."""
        agents = set(list(self._violations.keys()) + list(self._first_seen.keys()))
        return [self.evaluate(agent) for agent in sorted(agents)]

    def get_violations(
        self,
        agent_name: str,
        principle: Optional[MannersPrinciple] = None,
        since: Optional[datetime] = None,
        include_resolved: bool = False,
    ) -> List[MannersViolation]:
        """REM: Get violations for an agent with optional filters."""
        violations = self._violations.get(agent_name, [])
        if principle:
            violations = [v for v in violations if v.principle == principle]
        if since:
            violations = [v for v in violations if v.timestamp >= since]
        if not include_resolved:
            violations = [v for v in violations if not v.auto_resolved]
        return sorted(violations, key=lambda v: v.timestamp, reverse=True)

    def resolve_violation(self, agent_name: str, violation_index: int) -> bool:
        """REM: Manually resolve a violation. Returns True if successful."""
        violations = self._violations.get(agent_name, [])
        active = [v for v in violations if not v.auto_resolved]
        if 0 <= violation_index < len(active):
            active[violation_index].auto_resolved = True
            self._cached_reports.pop(agent_name, None)
            logger.info(f"REM: Manners violation resolved for {agent_name}")
            return True
        return False

    def get_compliance_summary(self) -> Dict[str, Any]:
        """REM: Get a summary of Manners compliance across all agents."""
        reports = self.evaluate_all()
        status_counts = {s.value: 0 for s in ComplianceStatus}
        for r in reports:
            status_counts[r.status.value] += 1

        return {
            "total_agents": len(reports),
            "status_distribution": status_counts,
            "agents_in_grace_period": len([r for r in reports if r.is_grace_period]),
            "total_active_violations": sum(r.total_violations for r in reports),
            "violations_24h": sum(r.violations_24h for r in reports),
            "average_score": round(
                sum(r.overall_score for r in reports) / max(len(reports), 1), 3
            ),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    # REM: =======================================================================================
    # REM: INLINE CHECKS — Call these from agent execution paths
    # REM: =======================================================================================

    def check_action_allowed(self, agent_name: str, action: str) -> Tuple[bool, str]:
        """
        REM: Check if an agent is allowed to execute an action based on Manners status.
        REM: Called by SecureBaseAgent before action execution.
        REM: Returns (allowed, reason).
        """
        report = self.evaluate(agent_name)

        if report.status == ComplianceStatus.SUSPENDED:
            return False, f"Agent {agent_name} is SUSPENDED (Manners score: {report.overall_score:.2f}). Human review required."

        if report.status == ComplianceStatus.NON_COMPLIANT:
            # REM: Non-compliant agents can only execute read-only actions
            read_only_prefixes = ("get_", "list_", "check_", "verify_", "health", "status")
            if not any(action.startswith(p) for p in read_only_prefixes):
                return False, (
                    f"Agent {agent_name} is NON_COMPLIANT (Manners score: {report.overall_score:.2f}). "
                    f"Only read-only actions are allowed."
                )

        return True, "OK"

    def pre_action_check(
        self,
        agent_name: str,
        action: str,
        has_approval: bool = False,
        requires_approval: bool = False,
    ) -> Tuple[bool, str]:
        """
        REM: Combined pre-action Manners check.
        REM: Validates Manners status AND approval compliance.
        """
        # REM: Check Manners status
        allowed, reason = self.check_action_allowed(agent_name, action)
        if not allowed:
            return False, reason

        # REM: MANNERS-1: Check approval gate compliance
        if requires_approval and not has_approval:
            self.record_violation(
                agent_name=agent_name,
                violation_type=ViolationType.APPROVAL_BYPASS,
                details=f"Action '{action}' requires approval but none provided",
                action=action,
            )
            return False, f"Action '{action}' requires approval (MANNERS-1: Human Control)"

        return True, "OK"

    # REM: =======================================================================================
    # REM: INTERNAL HELPERS
    # REM: =======================================================================================

    @staticmethod
    def _score_to_status(score: float) -> ComplianceStatus:
        """REM: Convert a numeric score to a compliance status."""
        if score >= 0.90:
            return ComplianceStatus.EXEMPLARY
        elif score >= 0.75:
            return ComplianceStatus.COMPLIANT
        elif score >= 0.50:
            return ComplianceStatus.DEGRADED
        elif score >= 0.25:
            return ComplianceStatus.NON_COMPLIANT
        else:
            return ComplianceStatus.SUSPENDED

    def _check_auto_suspend(self, agent_name: str) -> None:
        """REM: Check if agent should be auto-suspended due to repeated violations."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=AUTO_SUSPEND_WINDOW_HOURS)
        recent = [
            v for v in self._violations.get(agent_name, [])
            if v.timestamp >= cutoff and not v.auto_resolved
        ]
        if len(recent) >= AUTO_SUSPEND_THRESHOLD:
            logger.critical(
                f"REM: MANNERS AUTO-SUSPEND — {agent_name} has {len(recent)} violations "
                f"in {AUTO_SUSPEND_WINDOW_HOURS}h (threshold: {AUTO_SUSPEND_THRESHOLD})"
            )
            audit.log(
                event_type=AuditEventType.SECURITY_ALERT,
                agent_name="manners_engine",
                action="auto_suspend",
                resource=agent_name,
                details={
                    "reason": "Manners violation threshold exceeded",
                    "violations_count": len(recent),
                    "threshold": AUTO_SUSPEND_THRESHOLD,
                    "window_hours": AUTO_SUSPEND_WINDOW_HOURS,
                },
            )
            # REM: Trigger trust level reduction if trust_manager is available
            try:
                from core.trust_levels import trust_manager, AgentTrustLevel
                current = trust_manager.get_trust_level(agent_name)
                if current != AgentTrustLevel.QUARANTINE:
                    trust_manager.demote_agent(
                        agent_name,
                        reason=f"Manners auto-suspension: {len(recent)} violations in {AUTO_SUSPEND_WINDOW_HOURS}h"
                    )
            except Exception as e:
                logger.error(f"REM: Failed to demote agent via trust_manager: {e}")

    def _persist_violation(self, violation: MannersViolation) -> None:
        """REM: Persist violation to Redis if available."""
        store = _get_store()
        if store:
            try:
                key = f"manners:violations:{violation.agent_name}"
                store.rpush(key, json.dumps(violation.to_dict()))
                # REM: Keep last 1000 violations per agent
                store.ltrim(key, -1000, -1)
            except Exception as e:
                logger.warning(f"REM: Failed to persist Manners violation: {e}")

    def _persist_first_seen(self, agent_name: str, timestamp: datetime) -> None:
        """REM: Persist first-seen timestamp to Redis."""
        store = _get_store()
        if store:
            try:
                store.hset("manners:first_seen", agent_name, timestamp.isoformat())
            except Exception as e:
                logger.warning(f"REM: Failed to persist Manners first_seen: {e}")

    def load_from_persistence(self) -> None:
        """REM: Load Manners state from Redis on startup."""
        store = _get_store()
        if not store:
            return
        try:
            # REM: Load first-seen timestamps
            first_seen = store.hgetall("manners:first_seen")
            if first_seen:
                for agent_name, ts_str in first_seen.items():
                    if isinstance(agent_name, bytes):
                        agent_name = agent_name.decode()
                    if isinstance(ts_str, bytes):
                        ts_str = ts_str.decode()
                    self._first_seen[agent_name] = datetime.fromisoformat(ts_str)
            logger.info(f"REM: Manners loaded {len(self._first_seen)} agent records from persistence")
        except Exception as e:
            logger.warning(f"REM: Failed to load Manners state from Redis: {e}")


# REM: =======================================================================================
# REM: SINGLETON INSTANCE
# REM: =======================================================================================

manners_engine = MannersEngine()


# REM: =======================================================================================
# REM: CONVENIENCE FUNCTIONS
# REM: =======================================================================================

def manners_check(agent_name: str, action: str, has_approval: bool = False, requires_approval: bool = False) -> Tuple[bool, str]:
    """REM: Quick Manners pre-action check. Use in agent execution paths."""
    return manners_engine.pre_action_check(agent_name, action, has_approval, requires_approval)


def manners_violation(agent_name: str, violation_type: ViolationType, details: str, **kwargs) -> MannersViolation:
    """REM: Quick violation recorder. Use when detecting Manners violations."""
    return manners_engine.record_violation(agent_name, violation_type, details, **kwargs)


def manners_score(agent_name: str) -> float:
    """REM: Quick score lookup. Returns 0.0–1.0."""
    return manners_engine.evaluate(agent_name).overall_score


def manners_status(agent_name: str) -> ComplianceStatus:
    """REM: Quick status lookup."""
    return manners_engine.evaluate(agent_name).status
