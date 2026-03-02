# TelsonBase/core/trust_levels.py
# REM: =======================================================================================
# REM: AGENT TRUST LEVEL MANAGEMENT SYSTEM
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.3.0CC: Enhanced with periodic citizen re-verification
# REM: v4.2.0CC: New feature - Agent quarantine and promotion system
#
# REM: Mission Statement: Not all agents deserve equal trust. New agents and external
# REM: framework integrations (LangChain, etc.) start in QUARANTINE with limited
# REM: capabilities. They must earn trust through observed behavior before promotion.
#
# REM: Trust Levels:
# REM:   QUARANTINE - Sandbox only, no external access, extra logging
# REM:   PROBATION  - Limited capabilities, human approval for sensitive ops
# REM:   RESIDENT   - Normal capabilities as declared
# REM:   CITIZEN    - Full trust, can spawn sub-agents, elevated permissions
# REM:   AGENT      - Apex tier, fully verified autonomous designation
#
# REM: Citizen Re-verification:
# REM:   Citizens must periodically re-verify their status. If behavioral metrics
# REM:   degrade below thresholds, they are automatically demoted. This prevents
# REM:   "promote and forget" security gaps.
# REM: =======================================================================================

import logging
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


class AgentTrustLevel(str, Enum):
    """REM: Trust levels for agents in the system."""
    QUARANTINE = "quarantine"   # Sandbox only, no external access
    PROBATION = "probation"     # Limited capabilities, extra oversight
    RESIDENT = "resident"       # Normal declared capabilities
    CITIZEN = "citizen"         # Elevated trust, can spawn sub-agents
    AGENT = "agent"             # Apex tier — fully verified autonomous AI agent designation


@dataclass
class TrustLevelConstraints:
    """REM: Constraints applied at each trust level."""
    can_access_external: bool = False
    can_spawn_agents: bool = False
    can_access_filesystem: bool = False
    requires_approval_for_all: bool = True
    max_actions_per_minute: int = 10
    allowed_capability_patterns: List[str] = field(default_factory=list)
    denied_capability_patterns: List[str] = field(default_factory=list)


# REM: Default constraints per trust level
TRUST_LEVEL_CONSTRAINTS: Dict[AgentTrustLevel, TrustLevelConstraints] = {
    AgentTrustLevel.QUARANTINE: TrustLevelConstraints(
        can_access_external=False,
        can_spawn_agents=False,
        can_access_filesystem=False,
        requires_approval_for_all=True,
        max_actions_per_minute=5,
        allowed_capability_patterns=["internal.*"],
        denied_capability_patterns=["external.*", "filesystem.*", "agent.spawn"]
    ),
    AgentTrustLevel.PROBATION: TrustLevelConstraints(
        can_access_external=False,
        can_spawn_agents=False,
        can_access_filesystem=True,
        requires_approval_for_all=False,
        max_actions_per_minute=30,
        allowed_capability_patterns=["internal.*", "filesystem.read:*"],
        denied_capability_patterns=["external.*", "filesystem.write:*", "filesystem.delete:*", "agent.spawn"]
    ),
    AgentTrustLevel.RESIDENT: TrustLevelConstraints(
        can_access_external=True,
        can_spawn_agents=False,
        can_access_filesystem=True,
        requires_approval_for_all=False,
        max_actions_per_minute=60,
        allowed_capability_patterns=["*"],
        denied_capability_patterns=["agent.spawn"]
    ),
    AgentTrustLevel.CITIZEN: TrustLevelConstraints(
        can_access_external=True,
        can_spawn_agents=True,
        can_access_filesystem=True,
        requires_approval_for_all=False,
        max_actions_per_minute=120,
        allowed_capability_patterns=["*"],
        denied_capability_patterns=[]
    ),
    AgentTrustLevel.AGENT: TrustLevelConstraints(
        can_access_external=True,
        can_spawn_agents=True,
        can_access_filesystem=True,
        requires_approval_for_all=False,
        max_actions_per_minute=300,
        allowed_capability_patterns=["*"],
        denied_capability_patterns=[]
    ),
}


@dataclass
class ReVerificationConfig:
    """REM: Configuration for periodic re-verification."""
    interval_days: int = 7              # How often to re-verify
    min_success_rate: float = 0.90      # Minimum success rate to maintain status
    max_anomalies_per_period: int = 2   # Max anomalies allowed per period
    max_failures_per_period: int = 10   # Max failures allowed per period
    require_activity: bool = True       # Must have some activity in period
    min_actions_per_period: int = 10    # Minimum actions to demonstrate activity


# REM: Re-verification config per trust level (only CITIZEN requires periodic re-verification)
REVERIFICATION_CONFIG: Dict[AgentTrustLevel, Optional[ReVerificationConfig]] = {
    AgentTrustLevel.QUARANTINE: None,  # No re-verification needed
    AgentTrustLevel.PROBATION: None,   # Promotion checks are sufficient
    AgentTrustLevel.RESIDENT: ReVerificationConfig(
        interval_days=14,
        min_success_rate=0.85,
        max_anomalies_per_period=3,
        max_failures_per_period=20,
        require_activity=False,
        min_actions_per_period=5
    ),
    AgentTrustLevel.CITIZEN: ReVerificationConfig(
        interval_days=7,
        min_success_rate=0.95,
        max_anomalies_per_period=1,
        max_failures_per_period=5,
        require_activity=True,
        min_actions_per_period=20
    ),
    AgentTrustLevel.AGENT: ReVerificationConfig(
        interval_days=3,
        min_success_rate=0.99,
        max_anomalies_per_period=0,
        max_failures_per_period=2,
        require_activity=True,
        min_actions_per_period=50
    ),
}


@dataclass
class AgentTrustRecord:
    """REM: Trust status record for an agent."""
    agent_id: str
    trust_level: AgentTrustLevel

    # REM: Tracking metrics
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_promotion: Optional[datetime] = None
    last_demotion: Optional[datetime] = None

    # REM: Behavioral metrics for promotion decisions
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    anomalies_triggered: int = 0
    approvals_granted: int = 0
    approvals_denied: int = 0

    # REM: Promotion requirements tracking
    days_at_current_level: int = 0
    promotion_blocked_until: Optional[datetime] = None
    promotion_blocked_reason: Optional[str] = None

    # REM: Re-verification tracking (v4.3.0CC)
    last_reverification: Optional[datetime] = None
    reverification_passed: bool = True
    reverification_failures: int = 0
    period_actions: int = 0          # Actions since last reverification
    period_successes: int = 0        # Successes since last reverification
    period_failures: int = 0         # Failures since last reverification
    period_anomalies: int = 0        # Anomalies since last reverification

    def success_rate(self) -> float:
        """REM: Calculate action success rate."""
        if self.total_actions == 0:
            return 0.0
        return self.successful_actions / self.total_actions

    def period_success_rate(self) -> float:
        """REM: Calculate success rate for current period."""
        if self.period_actions == 0:
            return 1.0  # No actions = no failures
        return self.period_successes / self.period_actions

    def reset_period_metrics(self):
        """REM: Reset period metrics after re-verification."""
        self.period_actions = 0
        self.period_successes = 0
        self.period_failures = 0
        self.period_anomalies = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "trust_level": self.trust_level.value,
            "registered_at": self.registered_at.isoformat(),
            "last_promotion": self.last_promotion.isoformat() if self.last_promotion else None,
            "last_demotion": self.last_demotion.isoformat() if self.last_demotion else None,
            "total_actions": self.total_actions,
            "successful_actions": self.successful_actions,
            "failed_actions": self.failed_actions,
            "anomalies_triggered": self.anomalies_triggered,
            "success_rate": self.success_rate(),
            "days_at_current_level": self.days_at_current_level,
            "last_reverification": self.last_reverification.isoformat() if self.last_reverification else None,
            "reverification_passed": self.reverification_passed,
            "period_success_rate": self.period_success_rate(),
            "period_actions": self.period_actions,
            "period_anomalies": self.period_anomalies,
        }


class PromotionRequirements(BaseModel):
    """REM: Requirements for promotion to next trust level."""
    min_days_at_level: int = 7
    min_successful_actions: int = 100
    min_success_rate: float = 0.95
    max_anomalies: int = 0
    max_denied_approvals: int = 2
    requires_human_approval: bool = True


# REM: Promotion requirements per level transition
PROMOTION_REQUIREMENTS: Dict[AgentTrustLevel, PromotionRequirements] = {
    AgentTrustLevel.QUARANTINE: PromotionRequirements(
        min_days_at_level=3,
        min_successful_actions=50,
        min_success_rate=0.98,
        max_anomalies=0,
        max_denied_approvals=0,
        requires_human_approval=True
    ),
    AgentTrustLevel.PROBATION: PromotionRequirements(
        min_days_at_level=7,
        min_successful_actions=200,
        min_success_rate=0.95,
        max_anomalies=1,
        max_denied_approvals=1,
        requires_human_approval=True
    ),
    AgentTrustLevel.RESIDENT: PromotionRequirements(
        min_days_at_level=30,
        min_successful_actions=1000,
        min_success_rate=0.99,
        max_anomalies=0,
        max_denied_approvals=0,
        requires_human_approval=True
    ),
    AgentTrustLevel.CITIZEN: PromotionRequirements(
        min_days_at_level=90,
        min_successful_actions=5000,
        min_success_rate=0.999,
        max_anomalies=0,
        max_denied_approvals=0,
        requires_human_approval=True
    ),
}


class TrustLevelManager:
    """
    REM: Manages agent trust levels and promotions/demotions.
    """

    def __init__(self):
        self._records: Dict[str, AgentTrustRecord] = {}
        self._load_from_persistence()

    def _load_from_persistence(self):
        """REM: Load trust records from Redis."""
        try:
            from core.persistence import RedisStore
            # REM: Will be implemented with Redis store
            pass
        except Exception as e:
            logger.warning(f"REM: Failed to load trust records: {e}")

    def register_agent(
        self,
        agent_id: str,
        initial_level: AgentTrustLevel = AgentTrustLevel.QUARANTINE,
        skip_quarantine: bool = False
    ) -> AgentTrustRecord:
        """
        REM: Register a new agent with initial trust level.
        REM: New agents start in QUARANTINE unless explicitly trusted.
        """
        if skip_quarantine and initial_level == AgentTrustLevel.QUARANTINE:
            initial_level = AgentTrustLevel.RESIDENT
            logger.warning(
                f"REM: Agent ::{agent_id}:: registered with skip_quarantine - "
                f"Starting at RESIDENT level_Thank_You"
            )

        record = AgentTrustRecord(
            agent_id=agent_id,
            trust_level=initial_level
        )
        self._records[agent_id] = record

        logger.info(
            f"REM: Agent ::{agent_id}:: registered at trust level "
            f"::{initial_level.value}::_Thank_You"
        )

        audit.log(
            AuditEventType.AGENT_REGISTERED,
            f"Agent registered with trust level ::{initial_level.value}::",
            actor="system",
            resource=agent_id,
            details={"trust_level": initial_level.value},
            qms_status="Thank_You"
        )

        return record

    def get_trust_level(self, agent_id: str) -> Optional[AgentTrustLevel]:
        """REM: Get current trust level for an agent."""
        record = self._records.get(agent_id)
        return record.trust_level if record else None

    def get_constraints(self, agent_id: str) -> TrustLevelConstraints:
        """REM: Get constraints for an agent based on trust level."""
        level = self.get_trust_level(agent_id)
        if level is None:
            # REM: Unknown agents get QUARANTINE constraints
            return TRUST_LEVEL_CONSTRAINTS[AgentTrustLevel.QUARANTINE]
        return TRUST_LEVEL_CONSTRAINTS[level]

    def record_action(
        self,
        agent_id: str,
        success: bool,
        triggered_anomaly: bool = False
    ):
        """REM: Record an action outcome for trust tracking."""
        record = self._records.get(agent_id)
        if not record:
            return

        record.total_actions += 1
        record.period_actions += 1

        if success:
            record.successful_actions += 1
            record.period_successes += 1
        else:
            record.failed_actions += 1
            record.period_failures += 1

        if triggered_anomaly:
            record.anomalies_triggered += 1
            record.period_anomalies += 1
            # REM: Consider automatic demotion for anomalies
            if record.anomalies_triggered >= 3:
                self._auto_demote(agent_id, "Excessive anomalies triggered")

    def record_approval_decision(self, agent_id: str, approved: bool):
        """REM: Record an approval decision for trust tracking."""
        record = self._records.get(agent_id)
        if not record:
            return

        if approved:
            record.approvals_granted += 1
        else:
            record.approvals_denied += 1
            # REM: Too many denials may trigger demotion
            if record.approvals_denied >= 5:
                self._auto_demote(agent_id, "Excessive approval denials")

    def check_promotion_eligibility(self, agent_id: str) -> tuple[bool, str]:
        """
        REM: Check if an agent is eligible for promotion.

        Returns:
            Tuple of (eligible, reason)
        """
        record = self._records.get(agent_id)
        if not record:
            return False, "Agent not found"

        if record.trust_level == AgentTrustLevel.AGENT:
            return False, "Already at highest trust level"

        if record.promotion_blocked_until:
            if datetime.now(timezone.utc) < record.promotion_blocked_until:
                return False, f"Promotion blocked: {record.promotion_blocked_reason}"

        requirements = PROMOTION_REQUIREMENTS.get(record.trust_level)
        if not requirements:
            return False, "No promotion path from current level"

        # REM: Check all requirements
        if record.days_at_current_level < requirements.min_days_at_level:
            return False, f"Need {requirements.min_days_at_level} days at current level"

        if record.successful_actions < requirements.min_successful_actions:
            return False, f"Need {requirements.min_successful_actions} successful actions"

        if record.success_rate() < requirements.min_success_rate:
            return False, f"Need {requirements.min_success_rate*100}% success rate"

        if record.anomalies_triggered > requirements.max_anomalies:
            return False, f"Too many anomalies ({record.anomalies_triggered})"

        if record.approvals_denied > requirements.max_denied_approvals:
            return False, f"Too many denied approvals ({record.approvals_denied})"

        return True, "Eligible for promotion"

    def promote(
        self,
        agent_id: str,
        promoted_by: str,
        skip_eligibility_check: bool = False
    ) -> tuple[bool, str]:
        """
        REM: Promote an agent to the next trust level.
        """
        record = self._records.get(agent_id)
        if not record:
            return False, "Agent not found"

        if not skip_eligibility_check:
            eligible, reason = self.check_promotion_eligibility(agent_id)
            if not eligible:
                return False, reason

        # REM: Determine next level
        level_order = [
            AgentTrustLevel.QUARANTINE,
            AgentTrustLevel.PROBATION,
            AgentTrustLevel.RESIDENT,
            AgentTrustLevel.CITIZEN,
            AgentTrustLevel.AGENT
        ]
        current_idx = level_order.index(record.trust_level)
        if current_idx >= len(level_order) - 1:
            return False, "Already at highest level"

        old_level = record.trust_level
        new_level = level_order[current_idx + 1]

        record.trust_level = new_level
        record.last_promotion = datetime.now(timezone.utc)
        record.days_at_current_level = 0

        logger.info(
            f"REM: Agent ::{agent_id}:: PROMOTED from ::{old_level.value}:: "
            f"to ::{new_level.value}:: by ::{promoted_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Agent promoted from {old_level.value} to {new_level.value}",
            actor=promoted_by,
            resource=agent_id,
            details={
                "old_level": old_level.value,
                "new_level": new_level.value,
                "metrics": record.to_dict()
            },
            qms_status="Thank_You"
        )

        return True, f"Promoted to {new_level.value}"

    def demote(
        self,
        agent_id: str,
        demoted_by: str,
        reason: str,
        block_promotion_days: int = 7
    ) -> tuple[bool, str]:
        """
        REM: Demote an agent to a lower trust level.
        """
        record = self._records.get(agent_id)
        if not record:
            return False, "Agent not found"

        level_order = [
            AgentTrustLevel.QUARANTINE,
            AgentTrustLevel.PROBATION,
            AgentTrustLevel.RESIDENT,
            AgentTrustLevel.CITIZEN,
            AgentTrustLevel.AGENT
        ]
        current_idx = level_order.index(record.trust_level)
        if current_idx == 0:
            return False, "Already at lowest level"

        old_level = record.trust_level
        new_level = level_order[current_idx - 1]

        record.trust_level = new_level
        record.last_demotion = datetime.now(timezone.utc)
        record.days_at_current_level = 0
        record.promotion_blocked_until = datetime.now(timezone.utc) + timedelta(days=block_promotion_days)
        record.promotion_blocked_reason = reason

        logger.warning(
            f"REM: Agent ::{agent_id}:: DEMOTED from ::{old_level.value}:: "
            f"to ::{new_level.value}:: - Reason: ::{reason}::_Thank_You_But_No"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Agent demoted from {old_level.value} to {new_level.value}",
            actor=demoted_by,
            resource=agent_id,
            details={
                "old_level": old_level.value,
                "new_level": new_level.value,
                "reason": reason,
                "blocked_until": record.promotion_blocked_until.isoformat()
            },
            qms_status="Thank_You_But_No"
        )

        return True, f"Demoted to {new_level.value}"

    def _auto_demote(self, agent_id: str, reason: str):
        """REM: Automatic demotion triggered by system."""
        self.demote(agent_id, "system:auto", reason, block_promotion_days=14)

    def quarantine(self, agent_id: str, quarantined_by: str, reason: str) -> bool:
        """
        REM: Immediately quarantine an agent (emergency response).
        """
        record = self._records.get(agent_id)
        if not record:
            return False

        old_level = record.trust_level
        record.trust_level = AgentTrustLevel.QUARANTINE
        record.last_demotion = datetime.now(timezone.utc)
        record.promotion_blocked_until = datetime.now(timezone.utc) + timedelta(days=30)
        record.promotion_blocked_reason = f"Emergency quarantine: {reason}"

        logger.error(
            f"REM: Agent ::{agent_id}:: QUARANTINED from ::{old_level.value}:: "
            f"Reason: ::{reason}::_Thank_You_But_No"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Agent emergency quarantined from {old_level.value}",
            actor=quarantined_by,
            resource=agent_id,
            details={"reason": reason},
            qms_status="Thank_You_But_No"
        )

        return True

    def get_all_records(self) -> List[AgentTrustRecord]:
        """REM: Get all trust records."""
        return list(self._records.values())

    def get_agents_by_level(self, level: AgentTrustLevel) -> List[str]:
        """REM: Get all agents at a specific trust level."""
        return [
            record.agent_id
            for record in self._records.values()
            if record.trust_level == level
        ]

    # REM: ====================================================================================
    # REM: PERIODIC RE-VERIFICATION (v4.3.0CC)
    # REM: ====================================================================================

    def needs_reverification(self, agent_id: str) -> tuple[bool, str]:
        """
        REM: Check if an agent needs re-verification.

        Returns:
            Tuple of (needs_reverification, reason)
        """
        record = self._records.get(agent_id)
        if not record:
            return False, "Agent not found"

        config = REVERIFICATION_CONFIG.get(record.trust_level)
        if config is None:
            return False, "Trust level does not require re-verification"

        now = datetime.now(timezone.utc)

        # REM: First-time verification
        if record.last_reverification is None:
            if record.last_promotion:
                days_since = (now - record.last_promotion).days
                if days_since >= config.interval_days:
                    return True, "Initial re-verification due"
            return False, "Not yet due for re-verification"

        # REM: Check interval
        days_since = (now - record.last_reverification).days
        if days_since >= config.interval_days:
            return True, f"Re-verification due ({days_since} days since last)"

        return False, f"Re-verification not due for {config.interval_days - days_since} days"

    def perform_reverification(self, agent_id: str) -> tuple[bool, str, Dict[str, Any]]:
        """
        REM: Perform re-verification for an agent.

        Returns:
            Tuple of (passed, reason, details)
        """
        record = self._records.get(agent_id)
        if not record:
            return False, "Agent not found", {}

        config = REVERIFICATION_CONFIG.get(record.trust_level)
        if config is None:
            return True, "No re-verification required for this trust level", {}

        now = datetime.now(timezone.utc)
        details = {
            "agent_id": agent_id,
            "trust_level": record.trust_level.value,
            "period_actions": record.period_actions,
            "period_success_rate": record.period_success_rate(),
            "period_failures": record.period_failures,
            "period_anomalies": record.period_anomalies,
            "thresholds": {
                "min_success_rate": config.min_success_rate,
                "max_failures": config.max_failures_per_period,
                "max_anomalies": config.max_anomalies_per_period,
                "min_actions": config.min_actions_per_period if config.require_activity else 0
            }
        }

        failures = []

        # REM: Check activity requirement
        if config.require_activity and record.period_actions < config.min_actions_per_period:
            failures.append(f"Insufficient activity: {record.period_actions} < {config.min_actions_per_period}")

        # REM: Check success rate (only if there were actions)
        if record.period_actions > 0 and record.period_success_rate() < config.min_success_rate:
            failures.append(f"Success rate too low: {record.period_success_rate():.1%} < {config.min_success_rate:.1%}")

        # REM: Check anomalies
        if record.period_anomalies > config.max_anomalies_per_period:
            failures.append(f"Too many anomalies: {record.period_anomalies} > {config.max_anomalies_per_period}")

        # REM: Check failures
        if record.period_failures > config.max_failures_per_period:
            failures.append(f"Too many failures: {record.period_failures} > {config.max_failures_per_period}")

        details["failures"] = failures
        passed = len(failures) == 0

        # REM: Update record
        record.last_reverification = now
        record.reverification_passed = passed
        record.reset_period_metrics()

        if passed:
            logger.info(
                f"REM: Agent ::{agent_id}:: passed re-verification at "
                f"::{record.trust_level.value}:: level_Thank_You"
            )
            audit.log(
                AuditEventType.AGENT_ACTION,
                f"Agent passed re-verification at {record.trust_level.value}",
                actor="system:reverification",
                resource=agent_id,
                details=details,
                qms_status="Thank_You"
            )
            return True, "Re-verification passed", details
        else:
            record.reverification_failures += 1

            logger.warning(
                f"REM: Agent ::{agent_id}:: FAILED re-verification - "
                f"Reasons: {failures}_Thank_You_But_No"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Agent failed re-verification at {record.trust_level.value}",
                actor="system:reverification",
                resource=agent_id,
                details=details,
                qms_status="Thank_You_But_No"
            )

            # REM: Demote on failure
            self.demote(
                agent_id,
                demoted_by="system:reverification",
                reason=f"Failed re-verification: {', '.join(failures)}",
                block_promotion_days=14
            )

            return False, f"Re-verification failed: {', '.join(failures)}", details

    def run_system_reverification(self) -> Dict[str, Any]:
        """
        REM: Run re-verification for all agents that need it.

        Returns:
            Summary of re-verification results
        """
        logger.info("REM: Starting system-wide re-verification_Please")

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checked": 0,
            "verified": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }

        for agent_id, record in self._records.items():
            results["checked"] += 1

            needs, reason = self.needs_reverification(agent_id)
            if not needs:
                results["skipped"] += 1
                continue

            results["verified"] += 1
            passed, msg, details = self.perform_reverification(agent_id)

            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

            results["details"].append({
                "agent_id": agent_id,
                "passed": passed,
                "message": msg
            })

        logger.info(
            f"REM: System re-verification complete - "
            f"Checked: {results['checked']}, Verified: {results['verified']}, "
            f"Passed: {results['passed']}, Failed: {results['failed']}_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            "System-wide re-verification completed",
            actor="system:reverification",
            details={
                "verified": results["verified"],
                "passed": results["passed"],
                "failed": results["failed"]
            },
            qms_status="Thank_You"
        )

        return results

    def get_reverification_status(self) -> Dict[str, Any]:
        """REM: Get re-verification status for all agents."""
        status = {
            "total_agents": len(self._records),
            "requiring_reverification": 0,
            "due_for_reverification": 0,
            "recently_failed": 0,
            "agents": []
        }

        now = datetime.now(timezone.utc)

        for agent_id, record in self._records.items():
            config = REVERIFICATION_CONFIG.get(record.trust_level)
            agent_status = {
                "agent_id": agent_id,
                "trust_level": record.trust_level.value,
                "requires_reverification": config is not None,
                "last_reverification": record.last_reverification.isoformat() if record.last_reverification else None,
                "passed": record.reverification_passed,
                "failure_count": record.reverification_failures
            }

            if config is not None:
                status["requiring_reverification"] += 1
                needs, _ = self.needs_reverification(agent_id)
                agent_status["due"] = needs
                if needs:
                    status["due_for_reverification"] += 1

            if not record.reverification_passed:
                status["recently_failed"] += 1

            status["agents"].append(agent_status)

        return status


# REM: Global trust level manager instance
trust_manager = TrustLevelManager()
