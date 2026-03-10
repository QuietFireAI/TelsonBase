# TelsonBase/api/identiclaw_routes.py
# REM: =======================================================================================
# REM: W3C DID IDENTITY MANAGEMENT API
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v7.3.0CC: REST endpoints for W3C DID-based agent identity management.
#
# REM: Mission Statement: Provide the administrative interface for registering,
# REM: verifying, revoking, and managing DID-authenticated agents on TelsonBase.
# REM: These endpoints let the operator control which agents get through the gate,
# REM: verify their credentials, and hit the kill switch when needed.
#
# REM: QMS Protocol:
# REM:   Register:   Identity_Register_Please with ::did:: ::display_name::
# REM:   Success:    Identity_Register_Thank_You with ::agent_record::
# REM:   Revoke:     Identity_Revoke_Please with ::did:: ::reason::
# REM:   Failure:    Identity_*_Thank_You_But_No with ::error::
# REM: =======================================================================================

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.audit import AuditEventType, audit
from core.auth import AuthResult, authenticate_request, require_permission
from core.config import get_settings
from core.qms import QMSStatus, format_qms

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/identity", tags=["Agent Identity"])


# REM: =======================================================================================
# REM: REQUEST/RESPONSE MODELS
# REM: =======================================================================================

class RegisterAgentRequest(BaseModel):
    """REM: Request to register a DID agent on TelsonBase."""
    did: str = Field(..., description="The agent's Decentralized Identifier (e.g., did:key:z6Mk...)")
    display_name: str = Field(default="", description="Human-readable agent name")
    credentials: List[Dict[str, Any]] = Field(default_factory=list, description="W3C Verifiable Credentials")
    manners_md_path: Optional[str] = Field(default=None, description="Path to MANNERS.md ethics file")
    profession_md_path: Optional[str] = Field(default=None, description="Path to Profession.md job description")


class RevokeAgentRequest(BaseModel):
    """REM: Request to revoke (kill switch) a DID agent."""
    reason: str = Field(default="", description="Reason for revocation")


class ReinstateAgentRequest(BaseModel):
    """REM: Request to reinstate a previously revoked DID agent."""
    reason: str = Field(default="", description="Reason for reinstatement")


class RefreshCredentialsRequest(BaseModel):
    """REM: Request to force refresh an agent's DID document and credentials."""
    did: str = Field(..., description="The agent's DID to refresh")


class AgentIdentityResponse(BaseModel):
    """REM: Response containing agent identity details."""
    did: str
    display_name: str = ""
    trust_level: str = "quarantine"
    telsonbase_permissions: List[str] = []
    revoked: bool = False
    registered_at: Optional[str] = None
    last_verified_at: Optional[str] = None
    qms_status: str = "Thank_You"


# REM: =======================================================================================
# REM: ENDPOINTS
# REM: =======================================================================================

@router.post("/register", response_model=AgentIdentityResponse)
async def register_did_agent(
    request: RegisterAgentRequest,
    auth: AuthResult = Depends(require_permission("admin"))
):
    """
    REM: Register a new DID agent on TelsonBase.
    REM: Resolves the DID, validates credentials, maps permissions.
    REM: Agent starts at QUARANTINE trust level.
    """
    settings = get_settings()
    if not settings.identiclaw_enabled:
        raise HTTPException(
            status_code=503,
            detail=format_qms(
                "Identity_Register", QMSStatus.THANK_YOU_BUT_NO,
                error="W3C DID identity integration is disabled (set IDENTICLAW_ENABLED=true)"
            )
        )

    if not request.did or not request.did.startswith("did:"):
        raise HTTPException(
            status_code=422,
            detail=format_qms(
                "Identity_Register", QMSStatus.THANK_YOU_BUT_NO,
                error="Invalid DID format — must start with 'did:'"
            )
        )

    from core.identiclaw import identiclaw_manager

    record = identiclaw_manager.register_agent(
        did=request.did,
        credentials=request.credentials,
        display_name=request.display_name,
        manners_md_path=request.manners_md_path,
        profession_md_path=request.profession_md_path,
        registered_by=auth.actor,
    )

    if not record:
        raise HTTPException(
            status_code=400,
            detail=format_qms(
                "Identity_Register", QMSStatus.THANK_YOU_BUT_NO,
                error=f"Failed to register DID: {request.did}"
            )
        )

    logger.info(
        f"REM: {format_qms('Identity_Register', QMSStatus.THANK_YOU, did=request.did, display_name=request.display_name)}"
    )

    return AgentIdentityResponse(
        did=record.did,
        display_name=record.display_name,
        trust_level=record.trust_level,
        telsonbase_permissions=record.telsonbase_permissions,
        revoked=record.revoked,
        registered_at=record.registered_at.isoformat() if record.registered_at else None,
        last_verified_at=record.last_verified_at.isoformat() if record.last_verified_at else None,
        qms_status="Thank_You",
    )


@router.get("/list")
async def list_did_agents(
    auth: AuthResult = Depends(require_permission("admin"))
):
    """REM: List all registered DID agents."""
    settings = get_settings()
    if not settings.identiclaw_enabled:
        raise HTTPException(status_code=503, detail="W3C DID identity integration is disabled")

    from core.identiclaw import identiclaw_manager

    agents = identiclaw_manager.list_agents()
    return {
        "agents": [
            {
                "did": a.did,
                "display_name": a.display_name,
                "trust_level": a.trust_level,
                "permissions": a.telsonbase_permissions,
                "revoked": a.revoked,
                "registered_at": a.registered_at.isoformat() if a.registered_at else None,
                "last_verified_at": a.last_verified_at.isoformat() if a.last_verified_at else None,
            }
            for a in agents
        ],
        "total": len(agents),
        "qms_status": "Thank_You",
    }


@router.get("/{did:path}")
async def get_did_agent(
    did: str,
    auth: AuthResult = Depends(require_permission("admin"))
):
    """REM: Get a specific DID agent's identity record."""
    settings = get_settings()
    if not settings.identiclaw_enabled:
        raise HTTPException(status_code=503, detail="W3C DID identity integration is disabled")

    from core.identiclaw import identiclaw_manager

    record = identiclaw_manager.get_agent(did)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=format_qms("Identity_Get", QMSStatus.THANK_YOU_BUT_NO, error="Agent not found")
        )

    return {
        "did": record.did,
        "display_name": record.display_name,
        "public_key_hex": record.public_key_hex,
        "trust_level": record.trust_level,
        "telsonbase_permissions": record.telsonbase_permissions,
        "active_credential_ids": record.active_credential_ids,
        "revoked": record.revoked,
        "revoked_by": record.revoked_by,
        "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
        "revocation_reason": record.revocation_reason,
        "manners_md_path": record.manners_md_path,
        "profession_md_path": record.profession_md_path,
        "registered_at": record.registered_at.isoformat() if record.registered_at else None,
        "last_verified_at": record.last_verified_at.isoformat() if record.last_verified_at else None,
        "qms_status": "Thank_You",
    }


@router.post("/revoke/{did:path}")
async def revoke_did_agent(
    did: str,
    request: RevokeAgentRequest,
    auth: AuthResult = Depends(require_permission("admin"))
):
    """
    REM: KILL SWITCH — Immediately revoke a DID agent.
    REM: Overrides identity provider status. All subsequent auth attempts fail instantly.
    """
    settings = get_settings()
    if not settings.identiclaw_enabled:
        raise HTTPException(status_code=503, detail="W3C DID identity integration is disabled")

    from core.identiclaw import identiclaw_manager

    success = identiclaw_manager.revoke_agent(
        did=did,
        revoked_by=auth.actor,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail=format_qms("Identity_Revoke", QMSStatus.THANK_YOU_BUT_NO, error="Revocation failed")
        )

    logger.warning(
        f"REM: {format_qms('Identity_Revoke', QMSStatus.THANK_YOU, did=did, revoked_by=auth.actor)}"
    )

    return {
        "did": did,
        "revoked": True,
        "revoked_by": auth.actor,
        "reason": request.reason,
        "qms_status": "Thank_You",
    }


@router.post("/reinstate/{did:path}")
async def reinstate_did_agent(
    did: str,
    request: ReinstateAgentRequest,
    auth: AuthResult = Depends(require_permission("admin"))
):
    """REM: Reinstate a previously revoked DID agent after human review."""
    settings = get_settings()
    if not settings.identiclaw_enabled:
        raise HTTPException(status_code=503, detail="W3C DID identity integration is disabled")

    from core.identiclaw import identiclaw_manager

    success = identiclaw_manager.reinstate_agent(
        did=did,
        reinstated_by=auth.actor,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail=format_qms(
                "Identity_Reinstate", QMSStatus.THANK_YOU_BUT_NO,
                error="Agent not found or not revoked"
            )
        )

    return {
        "did": did,
        "reinstated": True,
        "reinstated_by": auth.actor,
        "reason": request.reason,
        "qms_status": "Thank_You",
    }


@router.post("/refresh-credentials")
async def refresh_did_credentials(
    request: RefreshCredentialsRequest,
    auth: AuthResult = Depends(require_permission("admin"))
):
    """REM: Force refresh of DID document and credentials from identity provider."""
    settings = get_settings()
    if not settings.identiclaw_enabled:
        raise HTTPException(status_code=503, detail="W3C DID identity integration is disabled")

    from core.identiclaw import identiclaw_manager

    record = identiclaw_manager.refresh_credentials(request.did)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=format_qms("Identity_Refresh", QMSStatus.THANK_YOU_BUT_NO, error="Agent not found")
        )

    audit.log(
        AuditEventType.IDENTITY_CREDENTIAL_UPDATED,
        f"DID credentials refreshed: {request.did[:32]}...",
        actor=auth.actor,
        details={"did": request.did},
        qms_status="Thank_You"
    )

    return {
        "did": record.did,
        "display_name": record.display_name,
        "refreshed": True,
        "last_verified_at": record.last_verified_at.isoformat() if record.last_verified_at else None,
        "qms_status": "Thank_You",
    }
