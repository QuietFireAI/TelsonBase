# TelsonBase/api/openclaw_routes.py
# REM: =======================================================================================
# REM: OPENCLAW GOVERNANCE API — "CONTROL YOUR CLAW"
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v7.4.0CC: REST endpoints for governed OpenClaw instance management.
#
# REM: Mission Statement: Provide the administrative interface for registering,
# REM: governing, promoting, demoting, suspending, and monitoring OpenClaw
# REM: instances under TelsonBase governance. The trust level model is the
# REM: "secret sauce" — degraded permissions that earn their way up.
#
# REM: QMS Protocol:
# REM:   Register:   OpenClaw_Register_Please with ::name:: ::api_key::
# REM:   Action:     OpenClaw_Action_Please with ::tool_name:: ::tool_args::
# REM:   Promote:    OpenClaw_Promote_Please with ::instance_id:: ::new_level::
# REM:   Suspend:    OpenClaw_Suspend_Please with ::instance_id:: ::reason::
# REM: =======================================================================================

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, model_validator

from core.auth import authenticate_request, require_permission, AuthResult
from core.audit import audit, AuditEventType
from core.config import get_settings
from core.qms import format_qms, QMSStatus
from core.rate_limiting import agent_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/openclaw", tags=["OpenClaw Governance"])


# REM: =======================================================================================
# REM: REQUEST/RESPONSE MODELS
# REM: =======================================================================================

_TRUST_LADDER = ["quarantine", "probation", "resident", "citizen", "agent"]
_OVERRIDE_REASON_MIN_LEN = 10


class RegisterClawRequest(BaseModel):
    """REM: Request to register a new OpenClaw instance under governance."""
    name: str = Field(..., description="Human-readable name for the claw instance")
    api_key: str = Field(..., description="The claw's API key (hashed before storage)")
    allowed_tools: List[str] = Field(default_factory=list, description="Explicit tool whitelist (empty = all)")
    blocked_tools: List[str] = Field(default_factory=list, description="Explicit tool blacklist")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    initial_trust_level: str = Field(
        default="quarantine",
        description="Starting trust level — defaults to quarantine. Override is audit-logged and requires justification."
    )
    override_reason: Optional[str] = Field(
        default=None,
        description="Required (min 10 chars) when initial_trust_level > quarantine. Appears verbatim in audit log."
    )

    @model_validator(mode="after")
    def validate_trust_override(self) -> "RegisterClawRequest":
        """
        REM: Enforce trust-override rules at the model layer so FastAPI returns
        REM: a 422 with a clear message before the handler runs.
        REM:
        REM: Rules:
        REM:   1. initial_trust_level must be a recognised level (normalised to lowercase).
        REM:   2. override_reason is REQUIRED and must be substantive (>= 10 chars)
        REM:      when initial_trust_level is anything above quarantine.
        REM:   3. override_reason is silently ignored when initial_trust_level is quarantine
        REM:      (no noise in the audit log for default registrations).
        """
        level = (self.initial_trust_level or "quarantine").lower().strip()

        if level not in _TRUST_LADDER:
            raise ValueError(
                f"invalid initial_trust_level '{self.initial_trust_level}' — "
                f"valid values: {_TRUST_LADDER}"
            )

        # REM: Normalise in place so the handler always receives a clean value.
        self.initial_trust_level = level

        if level != "quarantine":
            reason = (self.override_reason or "").strip()
            if not reason:
                raise ValueError(
                    f"override_reason is required when initial_trust_level is '{level}'. "
                    "Provide a substantive justification — it is written verbatim to the audit log."
                )
            if len(reason) < _OVERRIDE_REASON_MIN_LEN:
                raise ValueError(
                    f"override_reason must be at least {_OVERRIDE_REASON_MIN_LEN} characters — "
                    "a one-word reason does not constitute a governance record."
                )
            # REM: Normalise the reason so the handler always has clean whitespace.
            self.override_reason = reason

        return self


class ActionRequest(BaseModel):
    """REM: Request to evaluate an OpenClaw action through the governance pipeline."""
    tool_name: str = Field(..., description="The tool/action the claw wants to execute")
    tool_args: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    nonce: Optional[str] = Field(default=None, description="Unique nonce for replay protection")


class PromoteRequest(BaseModel):
    """REM: Request to promote a claw's trust level."""
    new_level: str = Field(..., description="Target trust level (probation, resident, citizen)")
    reason: str = Field(default="", description="Reason for promotion")


class DemoteRequest(BaseModel):
    """REM: Request to demote a claw's trust level."""
    new_level: str = Field(..., description="Target trust level (quarantine, probation, resident)")
    reason: str = Field(default="", description="Reason for demotion")


class SuspendRequest(BaseModel):
    """REM: Request to suspend (kill switch) a claw instance."""
    reason: str = Field(default="", description="Reason for suspension")


class ReinstateRequest(BaseModel):
    """REM: Request to reinstate a suspended claw instance."""
    reason: str = Field(default="", description="Reason for reinstatement")


class ClearReviewRequest(BaseModel):
    """REM: Request to clear a demotion review flag after human sign-off on last-N-actions audit."""
    notes: str = Field(
        default="",
        description="Notes from the reviewer acknowledging the audit (written to audit trail)."
    )


class ClawInstanceResponse(BaseModel):
    """REM: Response containing claw instance details."""
    instance_id: str
    name: str = ""
    trust_level: str = "quarantine"
    manners_score: float = 1.0
    action_count: int = 0
    actions_allowed: int = 0
    actions_blocked: int = 0
    actions_gated: int = 0
    suspended: bool = False
    registered_at: Optional[str] = None
    last_action_at: Optional[str] = None
    qms_status: str = "Thank_You"


class ActionResultResponse(BaseModel):
    """REM: Response containing the governance decision for an action."""
    allowed: bool = False
    reason: str = ""
    action_category: str = ""
    trust_level_at_decision: str = ""
    approval_required: bool = False
    approval_id: Optional[str] = None
    manners_score_at_decision: float = 1.0
    anomaly_flagged: bool = False
    qms_status: str = "Thank_You"


# REM: =======================================================================================
# REM: HELPER — Feature gate check
# REM: =======================================================================================

def _check_enabled():
    """REM: Verify OpenClaw integration is enabled. Raises 404 if not."""
    settings = get_settings()
    if not settings.openclaw_enabled:
        raise HTTPException(
            status_code=404,
            detail="OpenClaw governance is not enabled. Set OPENCLAW_ENABLED=true."
        )


def _get_manager():
    """REM: Lazy import to avoid circular imports."""
    from core.openclaw import openclaw_manager
    return openclaw_manager


# REM: =======================================================================================
# REM: ENDPOINTS
# REM: =======================================================================================
# REM: IMPORTANT — Route ordering: all static GET routes (/list, /register) MUST be
# REM: declared before any parameterized GET routes (/{instance_id}) to prevent Starlette
# REM: from matching the static path as a path parameter.

@router.get("/list", response_model=List[ClawInstanceResponse])
async def list_claws(
    auth: AuthResult = Depends(authenticate_request),
):
    """REM: List all registered OpenClaw instances."""
    _check_enabled()

    manager = _get_manager()
    instances = manager.list_instances()

    return [
        ClawInstanceResponse(
            instance_id=i.instance_id,
            name=i.name,
            trust_level=i.trust_level,
            manners_score=i.manners_score,
            action_count=i.action_count,
            actions_allowed=i.actions_allowed,
            actions_blocked=i.actions_blocked,
            actions_gated=i.actions_gated,
            suspended=i.suspended,
            registered_at=i.registered_at.isoformat(),
            last_action_at=i.last_action_at.isoformat() if i.last_action_at else None,
        )
        for i in instances
    ]


@router.post("/register", response_model=ClawInstanceResponse)
async def register_claw(
    request: RegisterClawRequest,
    auth: AuthResult = Depends(authenticate_request),
):
    """
    REM: Register a new OpenClaw instance under TelsonBase governance.
    REM: Default trust level is QUARANTINE — trust must be earned.
    REM: Trust override (initial_trust_level > quarantine) is permitted for agents with a
    REM: proven track record; requires a substantive override_reason (>= 10 chars) that
    REM: is written verbatim to the audit log. Validated by RegisterClawRequest model.
    """
    _check_enabled()

    manager = _get_manager()
    instance = manager.register_instance(
        name=request.name,
        api_key=request.api_key,
        allowed_tools=request.allowed_tools,
        blocked_tools=request.blocked_tools,
        registered_by=auth.actor,
        metadata=request.metadata,
    )

    if not instance:
        raise HTTPException(
            status_code=400,
            detail=format_qms(
                "OpenClaw registration failed (max instances reached or duplicate)",
                QMSStatus.THANK_YOU_BUT_NO
            )
        )

    # REM: Trust override — model validator has already guaranteed:
    # REM:   • initial_trust_level is a valid, normalised level
    # REM:   • override_reason is present and substantive if level > quarantine
    # REM: Walk the ladder one step at a time (promote_trust enforces valid transitions).
    # REM: Each step produces its own audit entry with the operator-supplied reason.
    if request.initial_trust_level != "quarantine":
        target_idx = _TRUST_LADDER.index(request.initial_trust_level)
        for step_level in _TRUST_LADDER[1:target_idx + 1]:
            manager.promote_trust(
                instance_id=instance.instance_id,
                new_level=step_level,
                promoted_by=auth.actor,
                reason=request.override_reason,  # guaranteed non-empty by model validator
            )
        refreshed = manager.get_instance(instance.instance_id)
        if refreshed:
            instance = refreshed

    return ClawInstanceResponse(
        instance_id=instance.instance_id,
        name=instance.name,
        trust_level=instance.trust_level,
        manners_score=instance.manners_score,
        registered_at=instance.registered_at.isoformat(),
    )


@router.post("/{instance_id}/action", response_model=ActionResultResponse)
async def evaluate_action(
    instance_id: str,
    request: ActionRequest,
    auth: AuthResult = Depends(authenticate_request),
    _rl: None = Depends(agent_rate_limit),
):
    """
    REM: Submit an OpenClaw action for governance evaluation.
    REM: The governance pipeline determines if the action is allowed, gated, or blocked.
    """
    _check_enabled()

    manager = _get_manager()
    result = manager.evaluate_action(
        instance_id=instance_id,
        tool_name=request.tool_name,
        tool_args=request.tool_args,
        nonce=request.nonce,
    )

    qms_status = "Thank_You" if result.allowed else (
        "Excuse_Me" if result.approval_required else "Thank_You_But_No"
    )

    return ActionResultResponse(
        allowed=result.allowed,
        reason=result.reason,
        action_category=result.action_category,
        trust_level_at_decision=result.trust_level_at_decision,
        approval_required=result.approval_required,
        approval_id=result.approval_id,
        manners_score_at_decision=result.manners_score_at_decision,
        anomaly_flagged=result.anomaly_flagged,
        qms_status=qms_status,
    )


@router.get("/{instance_id}/status")
async def get_instance_status(
    instance_id: str,
    auth: AuthResult = Depends(authenticate_request),
):
    """
    REM: Pre-flight status check for agent-to-agent communication.
    REM: Returns trust tier, suspended state, full capability matrix, Manners score,
    REM: and whether a demotion review is pending.
    REM: Agent B should call this before delegating to Agent A — allows routing around
    REM: capability gaps rather than experiencing silent blocking.
    """
    _check_enabled()

    from core.openclaw import TRUST_PERMISSION_MATRIX, TrustLevel as _TrustLevel
    manager = _get_manager()
    instance = manager.get_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="OpenClaw instance not found")

    trust_level = _TrustLevel(instance.trust_level)
    perms = TRUST_PERMISSION_MATRIX[trust_level]
    review_status = manager.get_review_status(instance_id)

    return {
        "instance_id": instance_id,
        "name": instance.name,
        "trust_level": instance.trust_level,
        "suspended": instance.suspended,
        "review_required": review_status is not None,
        "review_details": review_status,
        "manners_score": instance.manners_score,
        "capability_matrix": {
            "autonomous": [c.value for c in perms["autonomous"]],
            "gated": [c.value for c in perms["gated"]],
            "blocked": [c.value for c in perms["blocked"]],
        },
        "last_action_at": instance.last_action_at.isoformat() if instance.last_action_at else None,
        "action_count": instance.action_count,
        "qms_status": "Thank_You",
    }


@router.post("/{instance_id}/clear-review")
async def clear_demotion_review(
    instance_id: str,
    request: ClearReviewRequest,
    auth: AuthResult = Depends(authenticate_request),
):
    """
    REM: Clear the demotion review flag after human sign-off on last-N-actions audit.
    REM: Required acknowledgment before re-promotion advisory is lifted.
    REM: Admin-only (admin:config permission required).
    REM: Idempotent: calling when no review is pending returns 400 with clear message.
    """
    _check_enabled()
    require_permission(auth, "admin:config")

    manager = _get_manager()
    review = manager.get_review_status(instance_id)
    if not review:
        raise HTTPException(
            status_code=400,
            detail=format_qms(
                "No demotion review pending for this instance",
                QMSStatus.THANK_YOU_BUT_NO
            )
        )

    success = manager.clear_review(
        instance_id=instance_id,
        cleared_by=auth.actor,
        notes=request.notes,
    )

    if not success:
        raise HTTPException(status_code=404, detail="OpenClaw instance not found")

    return {
        "instance_id": instance_id,
        "review_cleared": True,
        "cleared_by": auth.actor,
        "actions_reviewed": review.get("actions_to_review", 0),
        "notes": request.notes,
        "qms_status": "Thank_You",
    }


@router.get("/{instance_id}", response_model=ClawInstanceResponse)
async def get_claw(
    instance_id: str,
    auth: AuthResult = Depends(authenticate_request),
):
    """REM: Get details of a registered OpenClaw instance."""
    _check_enabled()

    manager = _get_manager()
    instance = manager.get_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="OpenClaw instance not found")

    return ClawInstanceResponse(
        instance_id=instance.instance_id,
        name=instance.name,
        trust_level=instance.trust_level,
        manners_score=instance.manners_score,
        action_count=instance.action_count,
        actions_allowed=instance.actions_allowed,
        actions_blocked=instance.actions_blocked,
        actions_gated=instance.actions_gated,
        suspended=instance.suspended,
        registered_at=instance.registered_at.isoformat(),
        last_action_at=instance.last_action_at.isoformat() if instance.last_action_at else None,
    )


@router.post("/{instance_id}/promote")
async def promote_trust(
    instance_id: str,
    request: PromoteRequest,
    auth: AuthResult = Depends(authenticate_request),
):
    """
    REM: Promote a claw's trust level. Must follow valid path:
    REM: QUARANTINE → PROBATION → RESIDENT → CITIZEN
    """
    _check_enabled()

    manager = _get_manager()
    success = manager.promote_trust(
        instance_id=instance_id,
        new_level=request.new_level,
        promoted_by=auth.actor,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail=format_qms(
                "Trust promotion failed (invalid transition or instance not found)",
                QMSStatus.THANK_YOU_BUT_NO
            )
        )

    return {
        "instance_id": instance_id,
        "new_trust_level": request.new_level,
        "promoted_by": auth.actor,
        "qms_status": "Thank_You",
    }


@router.post("/{instance_id}/demote")
async def demote_trust(
    instance_id: str,
    request: DemoteRequest,
    auth: AuthResult = Depends(authenticate_request),
):
    """
    REM: Demote a claw's trust level. Can skip levels (instant consequences).
    """
    _check_enabled()

    manager = _get_manager()
    success = manager.demote_trust(
        instance_id=instance_id,
        new_level=request.new_level,
        demoted_by=auth.actor,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail=format_qms(
                "Trust demotion failed (invalid transition or instance not found)",
                QMSStatus.THANK_YOU_BUT_NO
            )
        )

    return {
        "instance_id": instance_id,
        "new_trust_level": request.new_level,
        "demoted_by": auth.actor,
        "qms_status": "Thank_You",
    }


@router.post("/{instance_id}/suspend")
async def suspend_claw(
    instance_id: str,
    request: SuspendRequest,
    auth: AuthResult = Depends(authenticate_request),
):
    """
    REM: Kill switch — immediately suspend an OpenClaw instance.
    REM: All subsequent actions are rejected until reinstatement.
    """
    _check_enabled()

    manager = _get_manager()
    success = manager.suspend_instance(
        instance_id=instance_id,
        suspended_by=auth.actor,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(status_code=404, detail="OpenClaw instance not found")

    return {
        "instance_id": instance_id,
        "suspended": True,
        "suspended_by": auth.actor,
        "reason": request.reason,
        "qms_status": "Thank_You",
    }


@router.post("/{instance_id}/reinstate")
async def reinstate_claw(
    instance_id: str,
    request: ReinstateRequest,
    auth: AuthResult = Depends(authenticate_request),
):
    """REM: Clear suspension after human review."""
    _check_enabled()

    manager = _get_manager()
    success = manager.reinstate_instance(
        instance_id=instance_id,
        reinstated_by=auth.actor,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Instance not found or not suspended"
        )

    return {
        "instance_id": instance_id,
        "suspended": False,
        "reinstated_by": auth.actor,
        "qms_status": "Thank_You",
    }


@router.get("/{instance_id}/trust-report")
async def trust_report(
    instance_id: str,
    auth: AuthResult = Depends(authenticate_request),
):
    """REM: Get the full trust report: history, action summary, current status."""
    _check_enabled()

    manager = _get_manager()
    report = manager.get_trust_report(instance_id)

    if not report:
        raise HTTPException(status_code=404, detail="OpenClaw instance not found")

    return report


@router.get("/{instance_id}/actions")
async def recent_actions(
    instance_id: str,
    limit: int = 50,
    auth: AuthResult = Depends(authenticate_request),
):
    """REM: Get recent action log with governance decisions."""
    _check_enabled()

    manager = _get_manager()
    instance = manager.get_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="OpenClaw instance not found")

    actions = manager.get_recent_actions(instance_id, limit=limit)

    return {
        "instance_id": instance_id,
        "name": instance.name,
        "trust_level": instance.trust_level,
        "actions": actions,
        "total_count": instance.action_count,
    }
