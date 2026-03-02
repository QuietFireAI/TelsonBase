# TelsonBase/api/compliance_routes.py
# REM: =======================================================================================
# REM: COMPLIANCE API ENDPOINTS FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Expose compliance subsystems (legal holds, breach assessment,
# REM: retention policies, sanctions, training, contingency, BAA, HITRUST, PHI disclosure)
# REM: as REST API endpoints with full QMS audit logging.
# REM:
# REM: QMS Protocol:
# REM:   Success: "Thank_You"
# REM:   Failure: "Thank_You_But_No"
# REM: =======================================================================================

import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth import authenticate_request, AuthResult, require_permission
from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/compliance", tags=["Compliance"])


# REM: =======================================================================================
# REM: PYDANTIC MODELS — LEGAL HOLDS
# REM: =======================================================================================

class LegalHoldCreateRequest(BaseModel):
    """REM: Request to create a legal hold."""
    tenant_id: str
    name: str
    scope: List[str]
    created_by: str
    matter_id: Optional[str] = None


class LegalHoldReleaseRequest(BaseModel):
    """REM: Request to release a legal hold."""
    released_by: str
    reason: str = "Administrative release"


class LegalHoldCustodianRequest(BaseModel):
    """REM: Request to add a custodian to a legal hold."""
    user_id: str


class LegalHoldAcknowledgeRequest(BaseModel):
    """REM: Request to acknowledge a legal hold."""
    user_id: str


# REM: =======================================================================================
# REM: PYDANTIC MODELS — BREACH
# REM: =======================================================================================

class BreachCreateRequest(BaseModel):
    """REM: Request to create a breach assessment."""
    severity: str
    description: str
    data_types_exposed: List[str]
    affected_count: Optional[int] = None
    discovered_by: Optional[str] = None
    discovery_date: Optional[str] = None


class BreachNotifyRequest(BaseModel):
    """REM: Request to send a breach notification."""
    recipient_type: str
    sent_to: str


# REM: =======================================================================================
# REM: PYDANTIC MODELS — RETENTION
# REM: =======================================================================================

class RetentionPolicyCreateRequest(BaseModel):
    """REM: Request to create a retention policy."""
    name: str
    tenant_id: str
    retention_days: int
    data_types: List[str]
    auto_delete: bool = False


# REM: =======================================================================================
# REM: PYDANTIC MODELS — SANCTIONS
# REM: =======================================================================================

class SanctionCreateRequest(BaseModel):
    """REM: Request to impose a sanction."""
    user_id: str
    violation: str
    severity: str
    imposed_by: str


class SanctionResolveRequest(BaseModel):
    """REM: Request to resolve a sanction."""
    resolved_by: str
    notes: Optional[str] = None


# REM: =======================================================================================
# REM: PYDANTIC MODELS — TRAINING
# REM: =======================================================================================

class TrainingCompletionRequest(BaseModel):
    """REM: Request to record training completion."""
    user_id: str
    training_type: str
    score: float
    passed: bool


class TrainingOverdueRequest(BaseModel):
    """REM: Request body for checking overdue training."""
    user_roles: List[str]


# REM: =======================================================================================
# REM: PYDANTIC MODELS — CONTINGENCY
# REM: =======================================================================================

class ContingencyTestRequest(BaseModel):
    """REM: Request to record a contingency test."""
    test_type: str
    conducted_by: str
    duration: int = Field(..., description="Duration in minutes")
    passed: bool
    findings: Optional[str] = None
    corrective_actions: Optional[str] = None


# REM: =======================================================================================
# REM: PYDANTIC MODELS — BAA
# REM: =======================================================================================

class BAACreateRequest(BaseModel):
    """REM: Request to create a Business Associate Agreement record."""
    name: str
    contact_email: str
    services: List[str]
    phi_access_level: str


class BAAActivateRequest(BaseModel):
    """REM: Request to activate a BAA."""
    effective_date: str
    expiration_date: str
    reviewed_by: str


class BAAReviewRequest(BaseModel):
    """REM: Request to review a BAA."""
    reviewed_by: str
    notes: Optional[str] = None


class BAATerminateRequest(BaseModel):
    """REM: Request to terminate a BAA."""
    terminated_by: str
    reason: str


# REM: =======================================================================================
# REM: PYDANTIC MODELS — HITRUST
# REM: =======================================================================================

class HITRUSTControlStatusRequest(BaseModel):
    """REM: Request to update a HITRUST control status."""
    status: str
    evidence: Optional[str] = None
    assessed_by: str


class HITRUSTRiskAssessmentRequest(BaseModel):
    """REM: Request to create a HITRUST risk assessment."""
    title: str
    scope: str
    findings: List[str]
    risk_level: str
    assessed_by: Optional[str] = None
    recommendations: Optional[List[str]] = None


# REM: =======================================================================================
# REM: PYDANTIC MODELS — PHI
# REM: =======================================================================================

class PHIDisclosureRequest(BaseModel):
    """REM: Request to record a PHI disclosure."""
    patient_id: str
    recipient: str
    purpose: str
    phi_description: str
    recorded_by: str


# REM: =======================================================================================
# REM: LEGAL HOLD ENDPOINTS
# REM: =======================================================================================

@router.post("/legal-holds")
async def legal_hold_create(
    request: LegalHoldCreateRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Create a new legal hold.
    REM: QMS: LegalHold_Create_Please with ::tenant_id:: ::name::
    """
    try:
        from core.legal_holds import legal_hold_manager

        hold = legal_hold_manager.create_hold(
            tenant_id=request.tenant_id,
            matter_id=request.matter_id,
            name=request.name,
            reason=getattr(request, 'reason', request.name),
            scope=request.scope,
            created_by=request.created_by
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Legal hold created: ::{request.name}:: for tenant ::{request.tenant_id}::",
            actor=auth.actor,
            details={"tenant_id": request.tenant_id, "name": request.name, "scope": request.scope}
        )

        return {
            "qms_status": "Thank_You",
            **hold.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legal hold creation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/legal-holds")
async def legal_hold_list(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: List legal holds with optional filters.
    REM: QMS: LegalHold_List_Please
    """
    try:
        from core.legal_holds import legal_hold_manager

        holds = legal_hold_manager.list_holds(
            tenant_id=tenant_id,
            status=status or "active"
        )

        return {
            "qms_status": "Thank_You",
            "holds": [h.to_dict() for h in holds]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legal hold list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/legal-holds/{hold_id}")
async def legal_hold_get(
    hold_id: str,
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Get details of a specific legal hold.
    REM: QMS: LegalHold_Get_Please with ::hold_id::
    """
    try:
        from core.legal_holds import legal_hold_manager

        hold = legal_hold_manager.get_hold(hold_id=hold_id)

        if not hold:
            raise HTTPException(status_code=404, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Legal hold '{hold_id}' not found"
            })

        return {
            "qms_status": "Thank_You",
            **hold.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legal hold get failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/legal-holds/{hold_id}/release")
async def legal_hold_release(
    hold_id: str,
    request: LegalHoldReleaseRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Release a legal hold.
    REM: QMS: LegalHold_Release_Please with ::hold_id:: ::released_by::
    """
    try:
        from core.legal_holds import legal_hold_manager

        released = legal_hold_manager.release_hold(
            hold_id=hold_id,
            released_by=request.released_by,
            reason=request.reason
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Legal hold ::{hold_id}:: released by ::{request.released_by}::",
            actor=auth.actor,
            details={"hold_id": hold_id, "released_by": request.released_by}
        )

        return {
            "qms_status": "Thank_You" if released else "Thank_You_But_No",
            "released": released
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legal hold release failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/legal-holds/{hold_id}/custodian")
async def legal_hold_add_custodian(
    hold_id: str,
    request: LegalHoldCustodianRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Add a custodian to a legal hold.
    REM: QMS: LegalHold_AddCustodian_Please with ::hold_id:: ::user_id::
    """
    try:
        from core.legal_holds import legal_hold_manager

        added = legal_hold_manager.add_custodian(
            hold_id=hold_id,
            user_id=request.user_id
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Custodian ::{request.user_id}:: added to legal hold ::{hold_id}::",
            actor=auth.actor,
            details={"hold_id": hold_id, "user_id": request.user_id}
        )

        return {
            "qms_status": "Thank_You" if added else "Thank_You_But_No",
            "added": added
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legal hold add custodian failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/legal-holds/{hold_id}/acknowledge")
async def legal_hold_acknowledge(
    hold_id: str,
    request: LegalHoldAcknowledgeRequest,
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Acknowledge a legal hold.
    REM: QMS: LegalHold_Acknowledge_Please with ::hold_id:: ::user_id::
    """
    try:
        from core.legal_holds import legal_hold_manager

        acknowledged = legal_hold_manager.acknowledge_hold(
            hold_id=hold_id,
            user_id=request.user_id
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Legal hold ::{hold_id}:: acknowledged by ::{request.user_id}::",
            actor=auth.actor,
            details={"hold_id": hold_id, "user_id": request.user_id}
        )

        return {
            "qms_status": "Thank_You" if acknowledged else "Thank_You_But_No",
            "acknowledged": acknowledged
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legal hold acknowledge failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: BREACH ASSESSMENT ENDPOINTS
# REM: =======================================================================================

@router.post("/breach")
async def breach_create(
    request: BreachCreateRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Create a breach assessment.
    REM: QMS: Breach_Assess_Please with ::severity:: ::description::
    """
    try:
        from core.breach import breach_manager, BreachSeverity

        try:
            severity = BreachSeverity(request.severity) if isinstance(request.severity, str) else request.severity
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid severity '{request.severity}'. Must be one of: {[e.value for e in BreachSeverity]}")

        assessment = breach_manager.create_assessment(
            detected_at=getattr(request, 'discovery_date', None) or datetime.now(timezone.utc),
            assessed_by=getattr(request, 'discovered_by', auth.actor),
            severity=severity,
            description=request.description,
            affected_tenants=getattr(request, 'affected_tenants', []),
            affected_records_count=getattr(request, 'affected_count', 0),
            data_types_exposed=request.data_types_exposed,
            attack_vector=getattr(request, 'attack_vector', "unknown")
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Breach assessment created — severity: ::{request.severity}::",
            actor=auth.actor,
            details={"severity": request.severity, "data_types_exposed": request.data_types_exposed}
        )

        return {
            "qms_status": "Thank_You",
            **assessment.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Breach assessment creation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/breach")
async def breach_list(
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: List all breach assessments.
    REM: QMS: Breach_List_Please
    """
    try:
        from core.breach import breach_manager

        assessments = breach_manager.list_assessments()

        return {
            "qms_status": "Thank_You",
            "assessments": [a.to_dict() for a in assessments]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Breach list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/breach/{assessment_id}")
async def breach_get(
    assessment_id: str,
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Get details of a specific breach assessment.
    REM: QMS: Breach_Get_Please with ::assessment_id::
    """
    try:
        from core.breach import breach_manager

        assessment = breach_manager.get_assessment(assessment_id=assessment_id)

        if not assessment:
            raise HTTPException(status_code=404, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Breach assessment '{assessment_id}' not found"
            })

        return {
            "qms_status": "Thank_You",
            **assessment.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Breach get failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/breach/{assessment_id}/notify")
async def breach_notify(
    assessment_id: str,
    request: BreachNotifyRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Send a breach notification.
    REM: QMS: Breach_Notify_Please with ::assessment_id:: ::recipient_type::
    """
    try:
        from core.breach import breach_manager

        notification = breach_manager.create_notification(
            assessment_id=assessment_id,
            recipient_type=request.recipient_type,
            recipient=request.sent_to,
            method=getattr(request, 'method', 'email')
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Breach notification sent for ::{assessment_id}:: to ::{request.sent_to}::",
            actor=auth.actor,
            details={
                "assessment_id": assessment_id,
                "recipient_type": request.recipient_type,
                "sent_to": request.sent_to
            }
        )

        return {
            "qms_status": "Thank_You",
            **notification.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Breach notification failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/breach/overdue")
async def breach_overdue(
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: List overdue breach notifications.
    REM: QMS: Breach_Overdue_Please
    """
    try:
        from core.breach import breach_manager

        overdue = breach_manager.get_overdue_notifications()

        return {
            "qms_status": "Thank_You",
            "overdue": overdue
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Breach overdue check failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: RETENTION POLICY ENDPOINTS
# REM: =======================================================================================

@router.post("/retention/policies")
async def retention_policy_create(
    request: RetentionPolicyCreateRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Create a retention policy.
    REM: QMS: Retention_Create_Please with ::name:: ::tenant_id::
    """
    try:
        from core.retention import retention_manager

        policy = retention_manager.create_policy(
            name=request.name,
            tenant_id=request.tenant_id,
            retention_days=request.retention_days,
            data_types=request.data_types,
            auto_delete=request.auto_delete,
            created_by=getattr(request, 'created_by', auth.actor)
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Retention policy created: ::{request.name}:: for tenant ::{request.tenant_id}::",
            actor=auth.actor,
            details={"name": request.name, "retention_days": request.retention_days}
        )

        return {
            "qms_status": "Thank_You",
            **policy.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retention policy creation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/retention/policies")
async def retention_policy_list(
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: List all retention policies.
    REM: QMS: Retention_List_Please
    """
    try:
        from core.retention import retention_manager

        policies = retention_manager.get_policies()

        return {
            "qms_status": "Thank_You",
            "policies": [p.to_dict() for p in policies]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retention policy list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: SANCTIONS ENDPOINTS
# REM: =======================================================================================

@router.post("/sanctions")
async def sanction_create(
    request: SanctionCreateRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Impose a sanction on a user.
    REM: QMS: Sanction_Create_Please with ::user_id:: ::violation:: ::severity::
    """
    try:
        from core.sanctions import sanctions_manager, SanctionSeverity

        try:
            severity = SanctionSeverity(request.severity) if isinstance(request.severity, str) else request.severity
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid severity '{request.severity}'. Must be one of: {[e.value for e in SanctionSeverity]}")

        sanction = sanctions_manager.impose_sanction(
            user_id=request.user_id,
            violation=request.violation,
            severity=severity,
            imposed_by=request.imposed_by
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Sanction imposed on ::{request.user_id}:: — ::{request.violation}:: severity: ::{request.severity}::",
            actor=auth.actor,
            details={
                "user_id": request.user_id,
                "violation": request.violation,
                "severity": request.severity,
                "imposed_by": request.imposed_by
            }
        )

        return {
            "qms_status": "Thank_You",
            **sanction.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sanction creation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/sanctions/{sanction_id}/resolve")
async def sanction_resolve(
    sanction_id: str,
    request: SanctionResolveRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Resolve an active sanction.
    REM: QMS: Sanction_Resolve_Please with ::sanction_id:: ::resolved_by::
    """
    try:
        from core.sanctions import sanctions_manager

        resolved = sanctions_manager.resolve_sanction(
            sanction_id=sanction_id,
            resolved_by=request.resolved_by,
            notes=request.notes
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Sanction ::{sanction_id}:: resolved by ::{request.resolved_by}::",
            actor=auth.actor,
            details={"sanction_id": sanction_id, "resolved_by": request.resolved_by, "notes": request.notes}
        )

        return {
            "qms_status": "Thank_You" if resolved else "Thank_You_But_No",
            "resolved": resolved
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sanction resolve failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/sanctions")
async def sanction_list(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: List sanctions with optional user filter.
    REM: QMS: Sanction_List_Please
    """
    try:
        from core.sanctions import sanctions_manager

        sanctions = sanctions_manager.list_sanctions(user_id=user_id)

        return {
            "qms_status": "Thank_You",
            "sanctions": sanctions
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sanctions list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/sanctions/user/{user_id}/active")
async def sanction_active(
    user_id: str,
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Check if a user has active sanctions.
    REM: QMS: Sanction_ActiveCheck_Please with ::user_id::
    """
    try:
        from core.sanctions import sanctions_manager

        result = sanctions_manager.get_active_sanctions(user_id=user_id)

        return {
            "qms_status": "Thank_You",
            "has_active": result.get("has_active", False),
            "sanctions": result.get("sanctions", [])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Active sanctions check failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: TRAINING COMPLIANCE ENDPOINTS
# REM: =======================================================================================

@router.post("/training/completion")
async def training_completion(
    request: TrainingCompletionRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Record a training completion.
    REM: QMS: Training_Complete_Please with ::user_id:: ::training_type::
    """
    try:
        from core.training import training_manager, TrainingType

        try:
            training_type = TrainingType(request.training_type) if isinstance(request.training_type, str) else request.training_type
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid training_type '{request.training_type}'. Must be one of: {[e.value for e in TrainingType]}")

        record = training_manager.record_completion(
            user_id=request.user_id,
            training_type=training_type,
            score=request.score,
            passed=request.passed
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Training completed by ::{request.user_id}:: — type: ::{request.training_type}:: passed: ::{request.passed}::",
            actor=auth.actor,
            details={
                "user_id": request.user_id,
                "training_type": request.training_type,
                "score": request.score,
                "passed": request.passed
            }
        )

        return {
            "qms_status": "Thank_You",
            **record.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Training completion recording failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/training/{user_id}")
async def training_status(
    user_id: str,
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Get compliance training status for a user.
    REM: QMS: Training_Status_Please with ::user_id::
    """
    try:
        from core.training import training_manager

        status = training_manager.get_compliance_status(user_id=user_id)

        return {
            "qms_status": "Thank_You",
            **status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Training status check failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/training/{user_id}/overdue")
async def training_overdue(
    user_id: str,
    request: TrainingOverdueRequest = Depends(),
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Get overdue training types for a user.
    REM: QMS: Training_Overdue_Please with ::user_id::
    """
    try:
        from core.training import training_manager

        overdue = training_manager.get_overdue_training(
            user_id=user_id,
            user_roles=request.user_roles
        )

        return {
            "qms_status": "Thank_You",
            "overdue": overdue
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Training overdue check failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/training/report")
async def training_report(
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Get compliance training report.
    REM: QMS: Training_Report_Please
    """
    try:
        from core.training import training_manager

        report = training_manager.get_compliance_report()

        return {
            "qms_status": "Thank_You",
            **report
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Training report generation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: CONTINGENCY PLAN ENDPOINTS
# REM: =======================================================================================

@router.post("/contingency/test")
async def contingency_test_record(
    request: ContingencyTestRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Record a contingency plan test.
    REM: QMS: Contingency_Test_Please with ::test_type:: ::conducted_by::
    """
    try:
        from core.contingency import contingency_manager

        from core.contingency_testing import TestType as ContingencyTestType
        try:
            test_type = ContingencyTestType(request.test_type) if isinstance(request.test_type, str) else request.test_type
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid test_type '{request.test_type}'. Must be one of: {[e.value for e in ContingencyTestType]}")

        record = contingency_manager.record_test_result(
            test_type=test_type,
            conducted_by=request.conducted_by,
            duration=request.duration,
            passed=request.passed,
            findings=request.findings,
            corrective_actions=request.corrective_actions
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Contingency test recorded — type: ::{request.test_type}:: passed: ::{request.passed}::",
            actor=auth.actor,
            details={
                "test_type": request.test_type,
                "conducted_by": request.conducted_by,
                "passed": request.passed
            }
        )

        return {
            "qms_status": "Thank_You",
            **record.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contingency test recording failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/contingency/tests")
async def contingency_test_list(
    test_type: Optional[str] = Query(None, description="Filter by test type"),
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: List contingency plan tests.
    REM: QMS: Contingency_TestList_Please
    """
    try:
        from core.contingency import contingency_manager

        from core.contingency_testing import TestType as ContTestType
        test_type_enum = ContTestType(test_type) if test_type else None
        tests = contingency_manager.get_test_history(test_type=test_type_enum)

        return {
            "qms_status": "Thank_You",
            "tests": [t.to_dict() for t in tests]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contingency test list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/contingency/overdue")
async def contingency_overdue(
    interval_days: Optional[int] = Query(None, description="Override default interval in days"),
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Check for overdue contingency tests.
    REM: QMS: Contingency_Overdue_Please
    """
    try:
        from core.contingency import contingency_manager

        overdue = contingency_manager.get_overdue_tests(interval_days=interval_days)

        return {
            "qms_status": "Thank_You",
            "overdue": overdue
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contingency overdue check failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/contingency/summary")
async def contingency_summary(
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Get contingency plan compliance summary.
    REM: QMS: Contingency_Summary_Please
    """
    try:
        from core.contingency import contingency_manager

        summary = contingency_manager.get_compliance_summary()

        return {
            "qms_status": "Thank_You",
            **summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contingency summary failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: BUSINESS ASSOCIATE AGREEMENT (BAA) ENDPOINTS
# REM: =======================================================================================

@router.post("/baa")
async def baa_create(
    request: BAACreateRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Create a Business Associate Agreement record.
    REM: QMS: BAA_Create_Please with ::name:: ::contact_email::
    """
    try:
        from core.baa import baa_manager

        baa = baa_manager.register_ba(
            name=request.name,
            email=request.contact_email,
            services=request.services,
            phi_access_level=request.phi_access_level
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"BAA created for ::{request.name}:: — contact: ::{request.contact_email}::",
            actor=auth.actor,
            details={"name": request.name, "services": request.services}
        )

        return {
            "qms_status": "Thank_You",
            **baa.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BAA creation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/baa")
async def baa_list(
    status: Optional[str] = Query(None, description="Filter by status"),
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: List Business Associate Agreements.
    REM: QMS: BAA_List_Please
    """
    try:
        from core.baa import baa_manager

        from core.baa_tracking import BAAStatus
        status_filter = BAAStatus(status) if status else None
        baas = baa_manager.get_all_baas(status_filter=status_filter)

        return {
            "qms_status": "Thank_You",
            "baas": [b.to_dict() for b in baas]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BAA list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/baa/{ba_id}/activate")
async def baa_activate(
    ba_id: str,
    request: BAAActivateRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Activate a BAA.
    REM: QMS: BAA_Activate_Please with ::ba_id:: ::reviewed_by::
    """
    try:
        from core.baa import baa_manager

        activated = baa_manager.activate_baa(
            ba_id=ba_id,
            effective_date=request.effective_date,
            expiration_date=request.expiration_date,
            reviewed_by=request.reviewed_by
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"BAA ::{ba_id}:: activated by ::{request.reviewed_by}::",
            actor=auth.actor,
            details={
                "ba_id": ba_id,
                "effective_date": request.effective_date,
                "expiration_date": request.expiration_date
            }
        )

        return {
            "qms_status": "Thank_You" if activated else "Thank_You_But_No",
            "activated": activated
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BAA activation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/baa/{ba_id}/review")
async def baa_review(
    ba_id: str,
    request: BAAReviewRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Review a BAA.
    REM: QMS: BAA_Review_Please with ::ba_id:: ::reviewed_by::
    """
    try:
        from core.baa import baa_manager

        reviewed = baa_manager.review_baa(
            ba_id=ba_id,
            reviewed_by=request.reviewed_by,
            notes=request.notes
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"BAA ::{ba_id}:: reviewed by ::{request.reviewed_by}::",
            actor=auth.actor,
            details={"ba_id": ba_id, "reviewed_by": request.reviewed_by, "notes": request.notes}
        )

        return {
            "qms_status": "Thank_You" if reviewed else "Thank_You_But_No",
            "reviewed": reviewed
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BAA review failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/baa/{ba_id}/terminate")
async def baa_terminate(
    ba_id: str,
    request: BAATerminateRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Terminate a BAA.
    REM: QMS: BAA_Terminate_Please with ::ba_id:: ::terminated_by::
    """
    try:
        from core.baa import baa_manager

        terminated = baa_manager.terminate_baa(
            ba_id=ba_id,
            terminated_by=request.terminated_by,
            reason=request.reason
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"BAA ::{ba_id}:: terminated by ::{request.terminated_by}:: — reason: ::{request.reason}::",
            actor=auth.actor,
            details={"ba_id": ba_id, "terminated_by": request.terminated_by, "reason": request.reason}
        )

        return {
            "qms_status": "Thank_You" if terminated else "Thank_You_But_No",
            "terminated": terminated
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BAA termination failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/baa/expiring")
async def baa_expiring(
    within_days: Optional[int] = Query(90, description="Days until expiration"),
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: List BAAs expiring within a given timeframe.
    REM: QMS: BAA_Expiring_Please
    """
    try:
        from core.baa import baa_manager

        expiring = baa_manager.get_expiring_baas(within_days=within_days)

        return {
            "qms_status": "Thank_You",
            "expiring": expiring
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BAA expiring check failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: HITRUST CONTROL ENDPOINTS
# REM: =======================================================================================

@router.get("/hitrust/controls")
async def hitrust_controls_list(
    domain: Optional[str] = Query(None, description="Filter by HITRUST domain"),
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: List HITRUST controls with optional domain filter.
    REM: QMS: HITRUST_Controls_Please
    """
    try:
        from core.hitrust import hitrust_manager

        if domain:
            from core.hitrust_controls import HITRUSTDomain
            try:
                domain_enum = HITRUSTDomain(domain)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid domain '{domain}'. Must be one of: {[e.value for e in HITRUSTDomain]}")
            controls = hitrust_manager.get_controls_by_domain(domain=domain_enum)
        else:
            controls = list(hitrust_manager._controls.values())

        return {
            "qms_status": "Thank_You",
            "controls": [c.to_dict() for c in controls]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITRUST controls list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/hitrust/controls/{control_id}")
async def hitrust_control_get(
    control_id: str,
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Get details of a specific HITRUST control.
    REM: QMS: HITRUST_Control_Get_Please with ::control_id::
    """
    try:
        from core.hitrust import hitrust_manager

        control = hitrust_manager.get_control(control_id=control_id)

        if not control:
            raise HTTPException(status_code=404, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"HITRUST control '{control_id}' not found"
            })

        return {
            "qms_status": "Thank_You",
            **control.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITRUST control get failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/hitrust/controls/{control_id}/status")
async def hitrust_control_update_status(
    control_id: str,
    request: HITRUSTControlStatusRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Update the status of a HITRUST control.
    REM: QMS: HITRUST_ControlStatus_Please with ::control_id:: ::status::
    """
    try:
        from core.hitrust import hitrust_manager

        updated = hitrust_manager.update_control_status(
            control_id=control_id,
            status=request.status,
            evidence=request.evidence,
            assessed_by=request.assessed_by
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"HITRUST control ::{control_id}:: status updated to ::{request.status}:: by ::{request.assessed_by}::",
            actor=auth.actor,
            details={"control_id": control_id, "status": request.status, "assessed_by": request.assessed_by}
        )

        return {
            "qms_status": "Thank_You" if updated else "Thank_You_But_No",
            "updated": updated
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITRUST control status update failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/hitrust/posture")
async def hitrust_posture(
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Get overall HITRUST compliance posture.
    REM: QMS: HITRUST_Posture_Please
    """
    try:
        from core.hitrust import hitrust_manager

        posture = hitrust_manager.get_compliance_posture()

        return {
            "qms_status": "Thank_You",
            **posture
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITRUST posture check failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/hitrust/risk-assessment")
async def hitrust_risk_assessment(
    request: HITRUSTRiskAssessmentRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Create a HITRUST risk assessment.
    REM: QMS: HITRUST_RiskAssessment_Please with ::title:: ::risk_level::
    """
    try:
        from core.hitrust import hitrust_manager

        assessment = hitrust_manager.record_risk_assessment(
            title=request.title,
            scope=request.scope,
            conducted_by=request.assessed_by,
            findings=request.findings,
            risk_level=request.risk_level,
            mitigation=request.recommendations
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"HITRUST risk assessment created: ::{request.title}:: — risk: ::{request.risk_level}::",
            actor=auth.actor,
            details={"title": request.title, "risk_level": request.risk_level}
        )

        return {
            "qms_status": "Thank_You",
            **assessment.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITRUST risk assessment failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: PHI DISCLOSURE ENDPOINTS
# REM: =======================================================================================

@router.post("/phi/disclosure")
async def phi_disclosure_record(
    request: PHIDisclosureRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Record a PHI disclosure.
    REM: QMS: PHI_Disclosure_Please with ::patient_id:: ::recipient:: ::purpose::
    """
    try:
        from core.phi import phi_manager

        record = phi_manager.record_disclosure(
            patient_id=request.patient_id,
            recipient=request.recipient,
            purpose=request.purpose,
            phi_description=request.phi_description,
            recorded_by=request.recorded_by
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"PHI disclosure recorded for patient ::{request.patient_id}:: to ::{request.recipient}:: — purpose: ::{request.purpose}::",
            actor=auth.actor,
            details={
                "patient_id": request.patient_id,
                "recipient": request.recipient,
                "purpose": request.purpose
            }
        )

        return {
            "qms_status": "Thank_You",
            **record.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PHI disclosure recording failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/phi/disclosures/{patient_id}")
async def phi_disclosures_list(
    patient_id: str,
    from_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    to_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: List PHI disclosures for a patient.
    REM: QMS: PHI_Disclosures_List_Please with ::patient_id::
    """
    try:
        from core.phi import phi_manager

        # REM: v7.2.0CC: Convert string dates to datetime, handle "null" from schemathesis
        parsed_from = None
        parsed_to = None
        if from_date and from_date != "null":
            try:
                parsed_from = datetime.fromisoformat(from_date)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid from_date format: '{from_date}'. Use ISO 8601.")
        if to_date and to_date != "null":
            try:
                parsed_to = datetime.fromisoformat(to_date)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid to_date format: '{to_date}'. Use ISO 8601.")

        disclosures = phi_manager.get_disclosures_for_patient(
            patient_id=patient_id,
            from_date=parsed_from,
            to_date=parsed_to
        )

        return {
            "qms_status": "Thank_You",
            "disclosures": [d.to_dict() for d in disclosures]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PHI disclosures list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/phi/disclosures/{patient_id}/report")
async def phi_disclosures_report(
    patient_id: str,
    auth: AuthResult = Depends(require_permission("view:audit"))
):
    """
    REM: Get PHI accounting of disclosures report for a patient.
    REM: QMS: PHI_Disclosures_Report_Please with ::patient_id::
    """
    try:
        from core.phi import phi_manager

        report = phi_manager.get_accounting_report(patient_id=patient_id)

        return {
            "qms_status": "Thank_You",
            **report
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PHI disclosures report failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })
