# TelsonBase/core/threat_response.py
# REM: =======================================================================================
# REM: AUTOMATED THREAT RESPONSE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.3.0CC: New feature - Automatic response to security threats
#
# REM: Mission Statement: Respond to security threats automatically without waiting for
# REM: human intervention. Critical threats trigger immediate quarantine; lesser threats
# REM: trigger alerts and prepare for human review.
#
# REM: Features:
# REM:   - Automatic quarantine on critical anomalies
# REM:   - Configurable response policies
# REM:   - Escalation paths for different threat levels
# REM:   - Audit trail for all automated actions
# REM:   - Human override capabilities
# REM: =======================================================================================

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


class ThreatLevel(str, Enum):
    """REM: Threat severity levels."""
    CRITICAL = "critical"   # Immediate action required
    HIGH = "high"           # Action required soon
    MEDIUM = "medium"       # Monitor closely
    LOW = "low"             # Log and monitor
    INFO = "info"           # Informational only


class ResponseAction(str, Enum):
    """REM: Possible automated response actions."""
    QUARANTINE = "quarantine"           # Immediately quarantine agent
    DEMOTE = "demote"                   # Demote agent trust level
    RATE_LIMIT = "rate_limit"           # Apply aggressive rate limiting
    REVOKE_DELEGATIONS = "revoke_delegations"  # Revoke all delegations
    BLOCK_EXTERNAL = "block_external"   # Block external access
    ALERT = "alert"                     # Alert only, no action
    LOG = "log"                         # Log only


@dataclass
class ThreatIndicator:
    """REM: A specific threat indicator pattern."""
    indicator_id: str
    name: str
    description: str
    threat_level: ThreatLevel
    pattern: Dict[str, Any]  # Pattern to match against events
    response_actions: List[ResponseAction]
    enabled: bool = True
    cooldown_minutes: int = 5  # Don't trigger again within this window


@dataclass
class ThreatEvent:
    """REM: A detected threat event."""
    event_id: str
    indicator_id: str
    threat_level: ThreatLevel
    agent_id: Optional[str]
    description: str
    evidence: Dict[str, Any]
    detected_at: datetime
    response_actions_taken: List[str] = field(default_factory=list)
    human_reviewed: bool = False
    resolved: bool = False


@dataclass
class ResponsePolicy:
    """REM: Policy for automated threat response."""
    policy_id: str
    name: str
    threat_level: ThreatLevel
    actions: List[ResponseAction]
    require_confirmation: bool = False
    notify_admins: bool = True
    cooldown_minutes: int = 10
    enabled: bool = True


# REM: Default threat indicators
DEFAULT_INDICATORS: List[ThreatIndicator] = [
    ThreatIndicator(
        indicator_id="ti_critical_anomaly_burst",
        name="Critical Anomaly Burst",
        description="Multiple critical anomalies from same agent in short period",
        threat_level=ThreatLevel.CRITICAL,
        pattern={
            "anomaly_severity": "critical",
            "count_threshold": 3,
            "window_minutes": 5
        },
        response_actions=[ResponseAction.QUARANTINE, ResponseAction.REVOKE_DELEGATIONS]
    ),
    ThreatIndicator(
        indicator_id="ti_capability_probing",
        name="Capability Probing Detected",
        description="Agent systematically testing unauthorized capabilities",
        threat_level=ThreatLevel.HIGH,
        pattern={
            "anomaly_type": "capability_probe",
            "count_threshold": 5,
            "window_minutes": 10
        },
        response_actions=[ResponseAction.DEMOTE, ResponseAction.BLOCK_EXTERNAL]
    ),
    ThreatIndicator(
        indicator_id="ti_approval_bypass_attempt",
        name="Approval Bypass Attempt",
        description="Agent attempting to bypass approval gates",
        threat_level=ThreatLevel.CRITICAL,
        pattern={
            "anomaly_type": "approval_bypass",
            "count_threshold": 1
        },
        response_actions=[ResponseAction.QUARANTINE]
    ),
    ThreatIndicator(
        indicator_id="ti_excessive_failures",
        name="Excessive Action Failures",
        description="Agent experiencing unusually high failure rate",
        threat_level=ThreatLevel.MEDIUM,
        pattern={
            "failure_rate_threshold": 0.5,
            "min_actions": 20,
            "window_minutes": 30
        },
        response_actions=[ResponseAction.RATE_LIMIT, ResponseAction.ALERT]
    ),
    ThreatIndicator(
        indicator_id="ti_signature_failure",
        name="Signature Verification Failures",
        description="Messages failing signature verification",
        threat_level=ThreatLevel.CRITICAL,
        pattern={
            "event_type": "signature_failure",
            "count_threshold": 2,
            "window_minutes": 5
        },
        response_actions=[ResponseAction.QUARANTINE, ResponseAction.REVOKE_DELEGATIONS]
    ),
]


# REM: Default response policies by threat level
DEFAULT_POLICIES: Dict[ThreatLevel, ResponsePolicy] = {
    ThreatLevel.CRITICAL: ResponsePolicy(
        policy_id="pol_critical",
        name="Critical Threat Response",
        threat_level=ThreatLevel.CRITICAL,
        actions=[ResponseAction.QUARANTINE, ResponseAction.REVOKE_DELEGATIONS],
        require_confirmation=False,  # Act immediately
        notify_admins=True,
        cooldown_minutes=0  # Always respond
    ),
    ThreatLevel.HIGH: ResponsePolicy(
        policy_id="pol_high",
        name="High Threat Response",
        threat_level=ThreatLevel.HIGH,
        actions=[ResponseAction.DEMOTE, ResponseAction.RATE_LIMIT],
        require_confirmation=False,
        notify_admins=True,
        cooldown_minutes=5
    ),
    ThreatLevel.MEDIUM: ResponsePolicy(
        policy_id="pol_medium",
        name="Medium Threat Response",
        threat_level=ThreatLevel.MEDIUM,
        actions=[ResponseAction.RATE_LIMIT, ResponseAction.ALERT],
        require_confirmation=True,  # Wait for human
        notify_admins=True,
        cooldown_minutes=15
    ),
    ThreatLevel.LOW: ResponsePolicy(
        policy_id="pol_low",
        name="Low Threat Response",
        threat_level=ThreatLevel.LOW,
        actions=[ResponseAction.ALERT],
        require_confirmation=False,
        notify_admins=False,
        cooldown_minutes=30
    ),
}


class ThreatResponseEngine:
    """
    REM: Automated threat detection and response engine.
    """

    def __init__(self):
        self._indicators = {i.indicator_id: i for i in DEFAULT_INDICATORS}
        self._policies = DEFAULT_POLICIES.copy()
        self._events: List[ThreatEvent] = []
        self._last_trigger: Dict[str, datetime] = {}  # indicator_id:agent_id -> last trigger time
        self._action_handlers: Dict[ResponseAction, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """REM: Register default action handlers."""
        self._action_handlers[ResponseAction.QUARANTINE] = self._handle_quarantine
        self._action_handlers[ResponseAction.DEMOTE] = self._handle_demote
        self._action_handlers[ResponseAction.RATE_LIMIT] = self._handle_rate_limit
        self._action_handlers[ResponseAction.REVOKE_DELEGATIONS] = self._handle_revoke_delegations
        self._action_handlers[ResponseAction.BLOCK_EXTERNAL] = self._handle_block_external
        self._action_handlers[ResponseAction.ALERT] = self._handle_alert
        self._action_handlers[ResponseAction.LOG] = self._handle_log

    def _handle_quarantine(self, agent_id: str, event: ThreatEvent) -> bool:
        """REM: Quarantine an agent."""
        try:
            from core.trust_levels import trust_manager
            trust_manager.quarantine(
                agent_id,
                quarantined_by="threat_response:auto",
                reason=f"Automated response to {event.indicator_id}: {event.description}"
            )
            return True
        except Exception as e:
            logger.error(f"REM: Quarantine failed for {agent_id}: {e}_Thank_You_But_No")
            return False

    def _handle_demote(self, agent_id: str, event: ThreatEvent) -> bool:
        """REM: Demote an agent's trust level."""
        try:
            from core.trust_levels import trust_manager
            success, _ = trust_manager.demote(
                agent_id,
                demoted_by="threat_response:auto",
                reason=f"Threat response: {event.description}",
                block_promotion_days=7
            )
            return success
        except Exception as e:
            logger.error(f"REM: Demotion failed for {agent_id}: {e}_Thank_You_But_No")
            return False

    def _handle_rate_limit(self, agent_id: str, event: ThreatEvent) -> bool:
        """REM: Apply aggressive rate limiting."""
        try:
            from core.rate_limiting import rate_limiter, RateLimitTier
            # REM: Force agent to minimal tier temporarily
            state = rate_limiter._get_or_create_state(agent_id, RateLimitTier.MINIMAL)
            state.tier = RateLimitTier.MINIMAL
            return True
        except Exception as e:
            logger.error(f"REM: Rate limit failed for {agent_id}: {e}_Thank_You_But_No")
            return False

    def _handle_revoke_delegations(self, agent_id: str, event: ThreatEvent) -> bool:
        """REM: Revoke all delegations for an agent."""
        try:
            from core.delegation import delegation_manager

            # REM: Revoke all delegations where this agent is grantor
            # REM: v5.3.0CC — Use public API instead of private attributes
            for did in list(delegation_manager.get_delegation_ids_by_grantor(agent_id)):
                delegation_manager.revoke(
                    did,
                    revoked_by="threat_response:auto",
                    reason=f"Threat response: {event.description}"
                )

            # REM: Revoke all delegations where this agent is grantee
            for did in list(delegation_manager.get_delegation_ids_by_grantee(agent_id)):
                delegation_manager.revoke(
                    did,
                    revoked_by="threat_response:auto",
                    reason=f"Grantee threat: {event.description}"
                )

            return True
        except Exception as e:
            logger.error(f"REM: Revoke delegations failed for {agent_id}: {e}_Thank_You_But_No")
            return False

    def _handle_block_external(self, agent_id: str, event: ThreatEvent) -> bool:
        """REM: Block external access for an agent."""
        # REM: v5.3.0CC — Stub: egress gateway integration not yet implemented.
        # REM: Returns False so callers know the action was NOT actually taken.
        logger.warning(
            f"REM: External blocking NOT YET IMPLEMENTED for ::{agent_id}:: "
            f"— egress gateway integration required_Thank_You_But_No"
        )
        return False

    def _handle_alert(self, agent_id: str, event: ThreatEvent) -> bool:
        """REM: Generate alert without action."""
        logger.warning(
            f"REM: THREAT ALERT for ::{agent_id}:: - {event.threat_level.value}: "
            f"{event.description}_Thank_You_But_No"
        )
        return True

    def _handle_log(self, agent_id: str, event: ThreatEvent) -> bool:
        """REM: Log the threat."""
        logger.info(
            f"REM: Threat logged for ::{agent_id}:: - {event.description}_Thank_You"
        )
        return True

    def evaluate_anomaly(
        self,
        agent_id: str,
        anomaly_type: str,
        severity: str,
        evidence: Dict[str, Any]
    ) -> Optional[ThreatEvent]:
        """
        REM: Evaluate an anomaly for threat indicators.

        Args:
            agent_id: The agent that triggered the anomaly
            anomaly_type: Type of anomaly
            severity: Severity level
            evidence: Supporting evidence

        Returns:
            ThreatEvent if a threat was detected, None otherwise
        """
        import uuid

        for indicator in self._indicators.values():
            if not indicator.enabled:
                continue

            # REM: Check cooldown
            cooldown_key = f"{indicator.indicator_id}:{agent_id}"
            last_trigger = self._last_trigger.get(cooldown_key)
            if last_trigger:
                cooldown_expires = last_trigger + timedelta(minutes=indicator.cooldown_minutes)
                if datetime.now(timezone.utc) < cooldown_expires:
                    continue

            # REM: Match pattern
            if self._matches_pattern(indicator.pattern, anomaly_type, severity, evidence):
                event = ThreatEvent(
                    event_id=f"threat_{uuid.uuid4().hex[:12]}",
                    indicator_id=indicator.indicator_id,
                    threat_level=indicator.threat_level,
                    agent_id=agent_id,
                    description=indicator.description,
                    evidence=evidence,
                    detected_at=datetime.now(timezone.utc)
                )

                # REM: Execute response
                self._execute_response(event, indicator.response_actions)

                # REM: Record
                self._events.append(event)
                self._last_trigger[cooldown_key] = datetime.now(timezone.utc)

                return event

        return None

    def _matches_pattern(
        self,
        pattern: Dict[str, Any],
        anomaly_type: str,
        severity: str,
        evidence: Dict[str, Any]
    ) -> bool:
        """REM: Check if anomaly matches indicator pattern."""
        # REM: Simple pattern matching - can be extended
        if "anomaly_type" in pattern and pattern["anomaly_type"] != anomaly_type:
            return False

        if "anomaly_severity" in pattern and pattern["anomaly_severity"] != severity:
            return False

        # REM: For now, just check if critical severity matches critical pattern
        if pattern.get("anomaly_severity") == "critical" and severity == "critical":
            return True

        return False

    def _execute_response(self, event: ThreatEvent, actions: List[ResponseAction]):
        """REM: Execute response actions for a threat."""
        agent_id = event.agent_id
        if not agent_id:
            return

        policy = self._policies.get(event.threat_level)
        if policy and policy.require_confirmation:
            logger.info(
                f"REM: Threat response pending confirmation for ::{agent_id}::_Thank_You"
            )
            return

        for action in actions:
            handler = self._action_handlers.get(action)
            if handler:
                success = handler(agent_id, event)
                if success:
                    event.response_actions_taken.append(action.value)

        # REM: Audit the response
        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Automated threat response: {event.threat_level.value}",
            actor="threat_response:auto",
            resource=agent_id,
            details={
                "event_id": event.event_id,
                "indicator_id": event.indicator_id,
                "actions_taken": event.response_actions_taken
            },
            qms_status="Thank_You_But_No"
        )

        logger.warning(
            f"REM: Threat response executed for ::{agent_id}:: - "
            f"Actions: {event.response_actions_taken}_Thank_You"
        )

    def get_recent_threats(self, limit: int = 50) -> List[Dict[str, Any]]:
        """REM: Get recent threat events."""
        return [
            {
                "event_id": e.event_id,
                "indicator_id": e.indicator_id,
                "threat_level": e.threat_level.value,
                "agent_id": e.agent_id,
                "description": e.description,
                "detected_at": e.detected_at.isoformat(),
                "actions_taken": e.response_actions_taken,
                "resolved": e.resolved
            }
            for e in sorted(self._events, key=lambda x: x.detected_at, reverse=True)[:limit]
        ]

    def get_threat_stats(self) -> Dict[str, Any]:
        """REM: Get threat statistics."""
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)

        recent = [e for e in self._events if e.detected_at >= last_24h]

        return {
            "total_threats": len(self._events),
            "last_24h": len(recent),
            "by_level": {
                level.value: len([e for e in recent if e.threat_level == level])
                for level in ThreatLevel
            },
            "unresolved": len([e for e in self._events if not e.resolved]),
            "auto_responses": len([e for e in self._events if e.response_actions_taken])
        }

    def add_indicator(self, indicator: ThreatIndicator):
        """REM: Add a custom threat indicator."""
        self._indicators[indicator.indicator_id] = indicator
        logger.info(f"REM: Added threat indicator ::{indicator.indicator_id}::_Thank_You")

    def disable_indicator(self, indicator_id: str):
        """REM: Disable a threat indicator."""
        if indicator_id in self._indicators:
            self._indicators[indicator_id].enabled = False
            logger.warning(f"REM: Disabled threat indicator ::{indicator_id}::_Thank_You")

    def enable_indicator(self, indicator_id: str):
        """REM: Enable a threat indicator."""
        if indicator_id in self._indicators:
            self._indicators[indicator_id].enabled = True
            logger.info(f"REM: Enabled threat indicator ::{indicator_id}::_Thank_You")


# REM: Global threat response engine instance
threat_response = ThreatResponseEngine()
