# TelsonBase/core/approval.py
# REM: =======================================================================================
# REM: HUMAN-IN-THE-LOOP APPROVAL GATES
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Some operations are too sensitive for fully autonomous execution.
# REM: This system creates approval gates where agent tasks pause and wait for human
# REM: authorization before proceeding. Critical for:
# REM:   - Financial transactions above threshold
# REM:   - External communications to new parties
# REM:   - Data deletion or modification
# REM:   - First-time actions by new agents
# REM:   - Actions flagged by anomaly detection
# REM:
# REM: The human can approve, reject, or request more information.
# REM:
# REM: v4.1.0CC: Added Redis persistence for approval requests
# REM: =======================================================================================

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field, asdict
import logging
import uuid
import threading

from pydantic import BaseModel, Field

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)

# REM: Import persistence store (lazy to avoid circular imports)
_approval_store = None

def _get_store():
    """REM: Lazy-load the approval store to avoid circular imports."""
    global _approval_store
    if _approval_store is None:
        try:
            from core.persistence import approval_store
            _approval_store = approval_store
        except Exception as e:
            logger.warning(f"REM: Redis persistence unavailable, using in-memory: {e}")
            _approval_store = False
    return _approval_store if _approval_store else None


class ApprovalStatus(str, Enum):
    """REM: Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    MORE_INFO_REQUESTED = "more_info_requested"


class ApprovalPriority(str, Enum):
    """REM: Priority levels for approval requests."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ApprovalRequest:
    """
    REM: A request for human approval of an agent action.
    """
    request_id: str
    agent_id: str
    action: str
    description: str
    payload: Dict[str, Any]
    
    # REM: Request metadata
    priority: ApprovalPriority = ApprovalPriority.NORMAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    
    # REM: Status tracking
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision_notes: Optional[str] = None
    
    # REM: Additional context
    risk_factors: List[str] = field(default_factory=list)
    anomaly_ids: List[str] = field(default_factory=list)
    
    # REM: For waiting tasks
    _event: threading.Event = field(default_factory=threading.Event, repr=False)


class ApprovalRule(BaseModel):
    """
    REM: A rule that determines when approval is required.
    """
    rule_id: str
    name: str
    description: str
    
    # REM: Matching criteria
    agent_pattern: str = "*"  # Glob pattern for agent IDs
    action_pattern: str = "*"  # Glob pattern for actions
    
    # REM: Conditions (any match triggers the rule)
    conditions: List[str] = Field(default_factory=list)
    
    # REM: Rule configuration
    priority: ApprovalPriority = ApprovalPriority.NORMAL
    timeout_seconds: int = 3600  # 1 hour default
    auto_reject_on_timeout: bool = True
    
    enabled: bool = True


# REM: =======================================================================================
# REM: PREDEFINED APPROVAL RULES
# REM: =======================================================================================

DEFAULT_APPROVAL_RULES = [
    ApprovalRule(
        rule_id="rule-external-new-domain",
        name="New External Domain",
        description="Require approval for first-time contact with external domain",
        action_pattern="external.*",
        conditions=["first_time_domain"],
        priority=ApprovalPriority.HIGH,
        timeout_seconds=7200
    ),
    ApprovalRule(
        rule_id="rule-filesystem-delete",
        name="File Deletion",
        description="Require approval for any file deletion",
        action_pattern="filesystem.delete*",
        priority=ApprovalPriority.HIGH,
        timeout_seconds=3600
    ),
    ApprovalRule(
        rule_id="rule-anomaly-flagged",
        name="Anomaly Flagged Action",
        description="Require approval when anomaly detection flags the agent",
        conditions=["anomaly_flagged"],
        priority=ApprovalPriority.URGENT,
        timeout_seconds=1800
    ),
    ApprovalRule(
        rule_id="rule-new-agent-first-action",
        name="New Agent First Action",
        description="Require approval for first action by newly registered agent",
        conditions=["first_agent_action"],
        priority=ApprovalPriority.NORMAL,
        timeout_seconds=86400  # 24 hours
    ),
    ApprovalRule(
        rule_id="rule-high-value-transaction",
        name="High Value Transaction",
        description="Require approval for transactions above threshold",
        conditions=["value_above_threshold:1000"],
        priority=ApprovalPriority.URGENT,
        timeout_seconds=3600,
        auto_reject_on_timeout=False  # Don't auto-reject financial stuff
    ),
    # REM: v7.3.0CC — Identiclaw DID agent identity rules
    ApprovalRule(
        rule_id="rule-did-first-registration",
        name="DID Agent First Registration",
        description="Require approval when a new DID agent registers with TelsonBase",
        action_pattern="identity.register",
        conditions=["first_did_registration"],
        priority=ApprovalPriority.HIGH,
        timeout_seconds=86400  # 24 hours
    ),
    ApprovalRule(
        rule_id="rule-did-scope-change",
        name="DID Credential Scope Change",
        description="Require approval when a DID agent presents credentials with expanded scopes",
        action_pattern="identity.credential_update",
        conditions=["scope_expansion"],
        priority=ApprovalPriority.HIGH,
        timeout_seconds=7200  # 2 hours
    ),
    # REM: v7.4.0CC — OpenClaw governance rules ("Control Your Claw")
    ApprovalRule(
        rule_id="rule-openclaw-quarantine-action",
        name="OpenClaw Quarantine Action",
        description="All actions by quarantined OpenClaw instances require human approval",
        agent_pattern="openclaw:*",
        conditions=["openclaw_trust_quarantine"],
        priority=ApprovalPriority.URGENT,
        timeout_seconds=7200  # 2 hours
    ),
    ApprovalRule(
        rule_id="rule-openclaw-external-action",
        name="OpenClaw External Action",
        description="External calls by non-citizen OpenClaw instances require approval",
        agent_pattern="openclaw:*",
        action_pattern="external.*",
        conditions=["openclaw_trust_below_citizen"],
        priority=ApprovalPriority.HIGH,
        timeout_seconds=3600  # 1 hour
    ),
    ApprovalRule(
        rule_id="rule-openclaw-destructive-action",
        name="OpenClaw Destructive Action",
        description="Destructive actions by non-resident+ OpenClaw instances require approval",
        agent_pattern="openclaw:*",
        action_pattern="filesystem.delete*",
        conditions=["openclaw_trust_below_resident"],
        priority=ApprovalPriority.HIGH,
        timeout_seconds=3600  # 1 hour
    ),
]


class ApprovalGate:
    """
    REM: The approval gate system.
    REM: Tasks submit requests here and wait for human decision.
    REM: v4.1.0CC: Now persists to Redis across restarts.
    """

    def __init__(self):
        self._rules: Dict[str, ApprovalRule] = {}
        self._pending_requests: Dict[str, ApprovalRequest] = {}
        self._completed_requests: Dict[str, ApprovalRequest] = {}

        # REM: Track first-time actions for rules
        self._known_domains: set = set()
        self._known_agents: set = set()
        self._known_dids: set = set()  # v7.3.0CC: Track registered DID agents

        # REM: Callbacks for notifications
        self._notification_callbacks: List[Callable] = []

        # REM: Load default rules
        for rule in DEFAULT_APPROVAL_RULES:
            self._rules[rule.rule_id] = rule

        # REM: Load pending requests from persistence
        self._load_from_persistence()

    def _load_from_persistence(self):
        """REM: Load pending requests from Redis on startup."""
        store = _get_store()
        if store:
            try:
                pending = store.get_pending_requests(limit=200)
                for req_data in pending:
                    # REM: Reconstruct ApprovalRequest from stored data
                    request = self._dict_to_request(req_data)
                    if request:
                        self._pending_requests[request.request_id] = request
                logger.info(f"REM: Loaded {len(self._pending_requests)} pending approvals from persistence_Thank_You")
            except Exception as e:
                logger.warning(f"REM: Failed to load approvals from persistence: {e}")

    def _dict_to_request(self, data: Dict) -> Optional[ApprovalRequest]:
        """REM: Convert stored dict back to ApprovalRequest."""
        try:
            return ApprovalRequest(
                request_id=data["request_id"],
                agent_id=data["agent_id"],
                action=data["action"],
                description=data["description"],
                payload=data.get("payload", {}),
                priority=ApprovalPriority(data.get("priority", "normal")),
                created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now(timezone.utc)),
                expires_at=datetime.fromisoformat(data["expires_at"]) if isinstance(data.get("expires_at"), str) and data.get("expires_at") else None,
                status=ApprovalStatus(data.get("status", "pending")),
                risk_factors=data.get("risk_factors", []),
                anomaly_ids=data.get("anomaly_ids", [])
            )
        except Exception as e:
            logger.warning(f"REM: Failed to reconstruct approval request: {e}")
            return None

    def _request_to_dict(self, request: ApprovalRequest) -> Dict:
        """REM: Convert ApprovalRequest to storable dict."""
        return {
            "request_id": request.request_id,
            "agent_id": request.agent_id,
            "action": request.action,
            "description": request.description,
            "payload": request.payload,
            "priority": request.priority.value,
            "created_at": request.created_at.isoformat() if request.created_at else None,
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
            "status": request.status.value,
            "decided_at": request.decided_at.isoformat() if request.decided_at else None,
            "decided_by": request.decided_by,
            "decision_notes": request.decision_notes,
            "risk_factors": request.risk_factors,
            "anomaly_ids": request.anomaly_ids
        }

    def _persist_request(self, request: ApprovalRequest):
        """REM: Persist a request to Redis."""
        store = _get_store()
        if store:
            try:
                store.store_request(self._request_to_dict(request))
            except Exception as e:
                logger.warning(f"REM: Failed to persist approval request: {e}")

    def _update_persisted_request(self, request_id: str, updates: Dict):
        """REM: Update a persisted request in Redis."""
        store = _get_store()
        if store:
            try:
                store.update_request(request_id, updates)
            except Exception as e:
                logger.warning(f"REM: Failed to update persisted request: {e}")
    
    def add_rule(self, rule: ApprovalRule):
        """REM: Add or update an approval rule."""
        self._rules[rule.rule_id] = rule
        logger.info(f"REM: Approval rule registered: ::{rule.rule_id}:: - {rule.name}_Thank_You")
    
    def remove_rule(self, rule_id: str) -> bool:
        """REM: Remove an approval rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False
    
    def check_requires_approval(
        self,
        agent_id: str,
        action: str,
        payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[ApprovalRule]:
        """
        REM: Check if an action requires approval based on configured rules.
        
        Returns:
            The matching rule if approval is required, None otherwise
        """
        import fnmatch
        
        context = context or {}
        
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            # REM: Check agent pattern
            if not fnmatch.fnmatch(agent_id, rule.agent_pattern):
                continue
            
            # REM: Check action pattern
            if not fnmatch.fnmatch(action, rule.action_pattern):
                continue
            
            # REM: Check conditions
            if rule.conditions:
                condition_met = False
                for condition in rule.conditions:
                    if self._evaluate_condition(condition, agent_id, action, payload, context):
                        condition_met = True
                        break
                
                if not condition_met:
                    continue
            
            # REM: Rule matches
            return rule
        
        return None
    
    def _evaluate_condition(
        self,
        condition: str,
        agent_id: str,
        action: str,
        payload: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """REM: Evaluate a condition string."""
        
        if condition == "first_time_domain":
            domain = payload.get("domain") or context.get("domain")
            if domain and domain not in self._known_domains:
                return True
        
        elif condition == "first_agent_action":
            if agent_id not in self._known_agents:
                return True
        
        elif condition == "anomaly_flagged":
            return context.get("anomaly_flagged", False)
        
        elif condition.startswith("value_above_threshold:"):
            threshold = float(condition.split(":")[1])
            value = payload.get("value") or payload.get("amount") or 0
            if float(value) > threshold:
                return True

        # REM: v7.3.0CC — Identiclaw DID conditions
        elif condition == "first_did_registration":
            did = payload.get("did")
            if did and did not in self._known_dids:
                return True

        elif condition == "scope_expansion":
            new_scopes = set(payload.get("new_scopes", []))
            old_scopes = set(payload.get("old_scopes", []))
            if new_scopes - old_scopes:  # New scopes beyond previous
                return True

        return False
    
    def create_request(
        self,
        agent_id: str,
        action: str,
        description: str,
        payload: Dict[str, Any],
        rule: ApprovalRule,
        risk_factors: Optional[List[str]] = None,
        anomaly_ids: Optional[List[str]] = None
    ) -> ApprovalRequest:
        """
        REM: Create a new approval request.
        """
        request_id = f"APPR-{uuid.uuid4().hex[:12].upper()}"
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=rule.timeout_seconds)
        
        request = ApprovalRequest(
            request_id=request_id,
            agent_id=agent_id,
            action=action,
            description=description,
            payload=payload,
            priority=rule.priority,
            expires_at=expires_at,
            risk_factors=risk_factors or [],
            anomaly_ids=anomaly_ids or []
        )
        
        self._pending_requests[request_id] = request
        self._persist_request(request)  # Persist to Redis

        logger.info(
            f"REM: Approval request created ::{request_id}:: - "
            f"Agent ::{agent_id}:: Action ::{action}:: "
            f"Priority ::{rule.priority.value}::_Please"
        )
        
        audit.log(
            AuditEventType.TASK_DISPATCHED,
            f"Approval required for action ::{action}:: by agent ::{agent_id}::",
            actor=agent_id,
            resource=request_id,
            details={
                "rule_id": rule.rule_id,
                "priority": rule.priority.value,
                "expires_at": expires_at.isoformat()
            },
            qms_status="Please"
        )
        
        # REM: Notify callbacks
        for callback in self._notification_callbacks:
            try:
                callback("new_request", request)
            except Exception as e:
                logger.error(f"REM: Notification callback failed: {e}")
        
        return request
    
    def wait_for_decision(
        self,
        request_id: str,
        timeout: Optional[float] = None
    ) -> ApprovalRequest:
        """
        REM: Block until approval decision is made or timeout occurs.
        
        Args:
            request_id: The approval request ID
            timeout: Maximum seconds to wait (None = use request's expiry)
        
        Returns:
            The approval request with final status
        """
        request = self._pending_requests.get(request_id)
        if not request:
            raise ValueError(f"Unknown approval request: {request_id}")
        
        # REM: Calculate timeout
        if timeout is None and request.expires_at:
            remaining = (request.expires_at - datetime.now(timezone.utc)).total_seconds()
            timeout = max(0, remaining)
        
        # REM: Wait for decision
        logger.info(f"REM: Waiting for decision on ::{request_id}::_Please")
        decided = request._event.wait(timeout=timeout)
        
        if not decided and request.status == ApprovalStatus.PENDING:
            # REM: Timeout - check rule for auto-reject behavior
            request.status = ApprovalStatus.EXPIRED
            request.decided_at = datetime.now(timezone.utc)
            request.decision_notes = "Request expired without decision"
            
            self._move_to_completed(request_id)
            
            logger.warning(f"REM: Approval request ::{request_id}:: expired_Thank_You_But_No")
            audit.log(
                AuditEventType.TASK_FAILED,
                f"Approval request ::{request_id}:: expired",
                actor="system",
                resource=request_id,
                qms_status="Thank_You_But_No"
            )
        
        return request
    
    def approve(
        self,
        request_id: str,
        decided_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        REM: Approve a pending request.
        """
        request = self._pending_requests.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return False
        
        request.status = ApprovalStatus.APPROVED
        request.decided_at = datetime.now(timezone.utc)
        request.decided_by = decided_by
        request.decision_notes = notes
        
        # REM: Update known entities (for first-time conditions)
        if "domain" in request.payload:
            self._known_domains.add(request.payload["domain"])
        self._known_agents.add(request.agent_id)
        
        # REM: Signal waiting task
        request._event.set()

        self._move_to_completed(request_id)

        # REM: Update persisted state
        self._update_persisted_request(request_id, {
            "status": ApprovalStatus.APPROVED.value,
            "decided_at": request.decided_at.isoformat(),
            "decided_by": decided_by,
            "decision_notes": notes
        })

        logger.info(
            f"REM: Approval request ::{request_id}:: APPROVED by ::{decided_by}::_Thank_You"
        )
        audit.log(
            AuditEventType.TASK_COMPLETED,
            f"Approval request ::{request_id}:: approved by ::{decided_by}::",
            actor=decided_by,
            resource=request_id,
            details={"notes": notes},
            qms_status="Thank_You"
        )

        return True

    def reject(
        self,
        request_id: str,
        decided_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        REM: Reject a pending request.
        """
        request = self._pending_requests.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return False
        
        request.status = ApprovalStatus.REJECTED
        request.decided_at = datetime.now(timezone.utc)
        request.decided_by = decided_by
        request.decision_notes = notes
        
        # REM: Signal waiting task
        request._event.set()

        self._move_to_completed(request_id)

        # REM: Update persisted state
        self._update_persisted_request(request_id, {
            "status": ApprovalStatus.REJECTED.value,
            "decided_at": request.decided_at.isoformat(),
            "decided_by": decided_by,
            "decision_notes": notes
        })

        logger.info(
            f"REM: Approval request ::{request_id}:: REJECTED by ::{decided_by}::_Thank_You_But_No"
        )
        audit.log(
            AuditEventType.TASK_FAILED,
            f"Approval request ::{request_id}:: rejected by ::{decided_by}::",
            actor=decided_by,
            resource=request_id,
            details={"notes": notes},
            qms_status="Thank_You_But_No"
        )

        return True
    
    def request_more_info(
        self,
        request_id: str,
        decided_by: str,
        questions: List[str]
    ) -> bool:
        """
        REM: Request more information before making decision.
        """
        request = self._pending_requests.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return False
        
        request.status = ApprovalStatus.MORE_INFO_REQUESTED
        request.decision_notes = f"Questions: {'; '.join(questions)}"
        
        logger.info(
            f"REM: More info requested for ::{request_id}:: by ::{decided_by}::_Excuse_Me"
        )
        
        return True
    
    def _move_to_completed(self, request_id: str):
        """REM: Move request from pending to completed."""
        if request_id in self._pending_requests:
            self._completed_requests[request_id] = self._pending_requests.pop(request_id)
    
    def get_approval_status(self, request_id: str) -> Optional[Dict]:
        """
        REM: v4.6.0CC: Public method for checking approval status.
        REM: Checks in-memory first (fast path), falls back to Redis (durable path).
        REM: This is the ONLY correct way for external code (Foreman, Celery tasks)
        REM: to verify approval state. Never access _pending_requests directly.
        REM:
        REM: Returns dict with keys: request_id, status, decided_by, decided_at
        REM: Returns None if request_id not found anywhere.
        REM:
        REM: QMS: Approval_Status_Check_Please ::request_id::
        """
        # REM: Fast path — check in-memory caches first
        request = self._pending_requests.get(request_id)
        if request:
            return {
                "request_id": request_id,
                "status": request.status.value if hasattr(request.status, 'value') else str(request.status),
                "decided_by": getattr(request, 'decided_by', None),
                "decided_at": getattr(request, 'decided_at', None),
                "agent_id": request.agent_id,
                "action": request.action,
            }

        request = self._completed_requests.get(request_id)
        if request:
            return {
                "request_id": request_id,
                "status": request.status.value if hasattr(request.status, 'value') else str(request.status),
                "decided_by": getattr(request, 'decided_by', None),
                "decided_at": getattr(request, 'decided_at', None),
                "agent_id": request.agent_id,
                "action": request.action,
            }

        # REM: Durable path — check Redis (survives worker restarts)
        store = _get_store()
        if store:
            try:
                persisted = store.get_request(request_id)
                if persisted:
                    return {
                        "request_id": request_id,
                        "status": persisted.get("status", "unknown"),
                        "decided_by": persisted.get("decided_by"),
                        "decided_at": persisted.get("decided_at"),
                        "agent_id": persisted.get("agent_id", ""),
                        "action": persisted.get("action", ""),
                    }
            except Exception as e:
                logger.warning(f"REM: Redis lookup failed for approval ::{request_id}::: {e}")

        return None

    def get_pending_requests(
        self,
        agent_id: Optional[str] = None,
        priority: Optional[ApprovalPriority] = None
    ) -> List[ApprovalRequest]:
        """REM: Get list of pending approval requests."""
        results = list(self._pending_requests.values())
        
        if agent_id:
            results = [r for r in results if r.agent_id == agent_id]
        if priority:
            results = [r for r in results if r.priority == priority]
        
        # REM: Sort by priority (urgent first) then by creation time
        priority_order = {
            ApprovalPriority.URGENT: 0,
            ApprovalPriority.HIGH: 1,
            ApprovalPriority.NORMAL: 2,
            ApprovalPriority.LOW: 3
        }
        results.sort(key=lambda r: (priority_order[r.priority], r.created_at))
        
        return results
    
    def register_notification_callback(self, callback: Callable):
        """REM: Register callback for approval events."""
        self._notification_callbacks.append(callback)


# REM: Global approval gate instance
approval_gate = ApprovalGate()


# REM: =======================================================================================
# REM: DECORATOR FOR REQUIRING APPROVAL
# REM: =======================================================================================

def requires_approval(description: str = "", risk_factors: List[str] = None):
    """
    REM: Decorator that wraps a Celery task to require human approval.
    
    Usage:
        @app.task
        @requires_approval(description="Delete customer data", risk_factors=["data_loss"])
        def delete_customer_data(customer_id: str):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # REM: Extract agent context from task
            from celery import current_task
            agent_id = getattr(current_task, 'request', {}).get('hostname', 'unknown')
            action = func.__name__
            
            # REM: Check if approval is required
            payload = {"args": args, "kwargs": kwargs}
            rule = approval_gate.check_requires_approval(
                agent_id=agent_id,
                action=action,
                payload=payload
            )
            
            if rule:
                # REM: Create approval request and wait
                request = approval_gate.create_request(
                    agent_id=agent_id,
                    action=action,
                    description=description or f"Execute {action}",
                    payload=payload,
                    rule=rule,
                    risk_factors=risk_factors
                )
                
                # REM: Wait for decision
                request = approval_gate.wait_for_decision(request.request_id)
                
                if request.status != ApprovalStatus.APPROVED:
                    raise PermissionError(
                        f"Action ::{action}:: not approved. "
                        f"Status: {request.status.value}. "
                        f"Notes: {request.decision_notes}"
                    )
            
            # REM: Approved or no approval required - execute
            return func(*args, **kwargs)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator
