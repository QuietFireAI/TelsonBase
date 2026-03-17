# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# TelsonBase/api/security_routes.py
# REM: =======================================================================================
# REM: SECURITY API ENDPOINTS FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Expose security subsystems (MFA, sessions, email verification,
# REM: CAPTCHA, emergency access) as REST API endpoints with full QMS audit logging.
# REM:
# REM: QMS Protocol:
# REM:   Success: "Thank_You"
# REM:   Failure: "Thank_You_But_No"
# REM: =======================================================================================

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.audit import AuditEventType, audit
from core.auth import AuthResult, authenticate_request, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/security", tags=["Security"])


# REM: =======================================================================================
# REM: PYDANTIC MODELS — MFA
# REM: =======================================================================================

class MFAEnrollRequest(BaseModel):
    """REM: Request to enroll a user in MFA."""
    user_id: str
    username: str


class MFAVerifyRequest(BaseModel):
    """REM: Request to verify an MFA token."""
    user_id: str
    token: str


class MFABackupCodeRequest(BaseModel):
    """REM: Request to verify a backup code."""
    user_id: str
    code: str


# REM: =======================================================================================
# REM: PYDANTIC MODELS — SESSIONS
# REM: =======================================================================================

class SessionCreateRequest(BaseModel):
    """REM: Request to create a new session."""
    user_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


# REM: =======================================================================================
# REM: PYDANTIC MODELS — EMAIL VERIFICATION
# REM: =======================================================================================

class EmailVerificationRequest(BaseModel):
    """REM: Request to send a verification email."""
    user_id: str
    email: str


class EmailVerifyRequest(BaseModel):
    """REM: Request to verify an email token."""
    user_id: str
    token: str


# REM: =======================================================================================
# REM: PYDANTIC MODELS — CAPTCHA
# REM: =======================================================================================

class CaptchaGenerateRequest(BaseModel):
    """REM: Request to generate a CAPTCHA challenge."""
    challenge_type: Optional[str] = None


class CaptchaVerifyRequest(BaseModel):
    """REM: Request to verify a CAPTCHA answer."""
    challenge_id: str
    answer: str


# REM: =======================================================================================
# REM: PYDANTIC MODELS — EMERGENCY ACCESS
# REM: =======================================================================================

class EmergencyAccessRequest(BaseModel):
    """REM: Request emergency access."""
    user_id: str
    reason: str
    duration_minutes: Optional[int] = Field(default=60, description="Duration in minutes")


class EmergencyApproveRequest(BaseModel):
    """REM: Approve an emergency access request."""
    approved_by: str


class EmergencyRevokeRequest(BaseModel):
    """REM: Revoke an emergency access grant."""
    revoked_by: str


# REM: =======================================================================================
# REM: MFA ENDPOINTS
# REM: =======================================================================================

@router.post("/mfa/enroll")
async def mfa_enroll(
    request: MFAEnrollRequest,
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Enroll a user in multi-factor authentication.
    REM: QMS: MFA_Enroll_Please with ::user_id:: ::username::
    """
    try:
        from core.mfa import mfa_manager

        result = mfa_manager.enroll_mfa(
            user_id=request.user_id,
            username=request.username
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"MFA enrolled for user ::{request.user_id}::",
            actor=auth.actor,
            details={"user_id": request.user_id, "username": request.username}
        )

        return {
            "qms_status": "Thank_You",
            "secret": result.get("secret"),
            "provisioning_uri": result.get("provisioning_uri"),
            "backup_codes": result.get("backup_codes", [])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA enrollment failed: {e}")
        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"MFA enrollment failed for ::{request.user_id}:: — ::{e}::",
            actor=auth.actor,
            details={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/mfa/verify")
async def mfa_verify(
    request: MFAVerifyRequest,
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Verify a user's MFA token.
    REM: QMS: MFA_Verify_Please with ::user_id::
    """
    try:
        from core.mfa import mfa_manager

        verified = mfa_manager.verify_mfa(
            user_id=request.user_id,
            token=request.token
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"MFA verification {'succeeded' if verified else 'failed'} for ::{request.user_id}::",
            actor=auth.actor,
            details={"user_id": request.user_id, "verified": verified}
        )

        return {
            "qms_status": "Thank_You" if verified else "Thank_You_But_No",
            "verified": verified
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA verification error: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/mfa/backup-code")
async def mfa_backup_code(
    request: MFABackupCodeRequest,
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Verify a backup code for MFA recovery.
    REM: QMS: MFA_BackupCode_Please with ::user_id::
    """
    try:
        from core.mfa import mfa_manager

        verified = mfa_manager.verify_backup_code(
            user_id=request.user_id,
            code=request.code
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"MFA backup code {'accepted' if verified else 'rejected'} for ::{request.user_id}::",
            actor=auth.actor,
            details={"user_id": request.user_id, "verified": verified}
        )

        return {
            "qms_status": "Thank_You" if verified else "Thank_You_But_No",
            "verified": verified
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA backup code error: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/mfa/status/{user_id}")
async def mfa_status(
    user_id: str,
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Get MFA enrollment status for a user.
    REM: QMS: MFA_Status_Please with ::user_id::
    """
    try:
        from core.mfa import mfa_manager

        status = mfa_manager.get_mfa_status(user_id=user_id)

        return {
            "qms_status": "Thank_You",
            **status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA status check failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.delete("/mfa/{user_id}")
async def mfa_disable(
    user_id: str,
    disabled_by: str = Query(..., description="User who is disabling MFA"),
    auth: AuthResult = Depends(require_permission("security:override"))
):
    """
    REM: Disable MFA for a user.
    REM: QMS: MFA_Disable_Please with ::user_id:: ::disabled_by::
    """
    try:
        from core.mfa import mfa_manager

        disabled = mfa_manager.disable_mfa(
            user_id=user_id,
            disabled_by=disabled_by
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"MFA disabled for ::{user_id}:: by ::{disabled_by}::",
            actor=auth.actor,
            details={"user_id": user_id, "disabled_by": disabled_by}
        )

        return {
            "qms_status": "Thank_You" if disabled else "Thank_You_But_No",
            "disabled": disabled
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA disable failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: SESSION ENDPOINTS
# REM: =======================================================================================

@router.post("/sessions")
async def session_create(
    request: SessionCreateRequest,
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Create a new user session.
    REM: QMS: Session_Create_Please with ::user_id::
    """
    try:
        from core.sessions import session_manager

        session = session_manager.create_session(
            user_id=request.user_id,
            ip_address=request.ip_address,
            user_agent=request.user_agent
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Session created for ::{request.user_id}::",
            actor=auth.actor,
            details={"user_id": request.user_id, "ip_address": request.ip_address}
        )

        return {
            "qms_status": "Thank_You",
            **session.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session creation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/sessions")
async def session_list(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: List active sessions, optionally filtered by user.
    REM: QMS: Session_List_Please
    """
    try:
        from core.sessions import session_manager

        sessions = session_manager.get_active_sessions(user_id=user_id)

        return {
            "qms_status": "Thank_You",
            "sessions": [s.to_dict() for s in sessions]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/sessions/{session_id}")
async def session_get(
    session_id: str,
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Get details for a specific session.
    REM: QMS: Session_Get_Please with ::session_id::
    """
    try:
        from core.sessions import session_manager

        session = session_manager.get_session(session_id=session_id)

        if not session:
            raise HTTPException(status_code=404, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Session '{session_id}' not found"
            })

        return {
            "qms_status": "Thank_You",
            **session.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session get failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.delete("/sessions/{session_id}")
async def session_terminate(
    session_id: str,
    reason: str = Query("manual_termination", description="Reason for termination"),
    auth: AuthResult = Depends(require_permission("security:override"))
):
    """
    REM: Terminate a specific session.
    REM: QMS: Session_Terminate_Please with ::session_id:: ::reason::
    """
    try:
        from core.sessions import session_manager

        terminated = session_manager.terminate_session(
            session_id=session_id,
            reason=reason
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Session ::{session_id}:: terminated — reason: ::{reason}::",
            actor=auth.actor,
            details={"session_id": session_id, "reason": reason}
        )

        return {
            "qms_status": "Thank_You" if terminated else "Thank_You_But_No",
            "terminated": terminated
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session terminate failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.delete("/sessions/user/{user_id}")
async def session_terminate_all(
    user_id: str,
    reason: str = Query("bulk_termination", description="Reason for termination"),
    auth: AuthResult = Depends(require_permission("security:override"))
):
    """
    REM: Terminate all sessions for a user.
    REM: QMS: Session_TerminateAll_Please with ::user_id:: ::reason::
    """
    try:
        from core.sessions import session_manager

        count = session_manager.terminate_all_user_sessions(
            user_id=user_id,
            reason=reason
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"All sessions terminated for ::{user_id}:: — count: ::{count}:: reason: ::{reason}::",
            actor=auth.actor,
            details={"user_id": user_id, "terminated_count": count, "reason": reason}
        )

        return {
            "qms_status": "Thank_You",
            "terminated_count": count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session terminate all failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/sessions/cleanup")
async def session_cleanup(
    auth: AuthResult = Depends(require_permission("security:override"))
):
    """
    REM: Clean up expired sessions.
    REM: QMS: Session_Cleanup_Please
    """
    try:
        from core.sessions import session_manager

        cleaned = session_manager.cleanup_expired()

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Expired sessions cleaned up — count: ::{cleaned}::",
            actor=auth.actor,
            details={"cleaned": cleaned}
        )

        return {
            "qms_status": "Thank_You",
            "cleaned": cleaned
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session cleanup failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: EMAIL VERIFICATION ENDPOINTS
# REM: =======================================================================================

@router.post("/email/request-verification")
async def email_request_verification(
    request: EmailVerificationRequest,
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Request email verification for a user.
    REM: QMS: Email_Verify_Request_Please with ::user_id:: ::email::
    """
    try:
        from core.email_verification import email_verification

        result = email_verification.create_verification(
            user_id=request.user_id,
            email=request.email
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Email verification requested for ::{request.user_id}:: at ::{request.email}::",
            actor=auth.actor,
            details={"action": "email_verification_sent", "user_id": request.user_id, "email": request.email}
        )

        return {
            "qms_status": "Thank_You",
            "token_id": result.token_id,
            "expires_at": str(result.expires_at)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification request failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/email/verify")
async def email_verify(
    request: EmailVerifyRequest,
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Verify an email token.
    REM: QMS: Email_Verify_Please with ::user_id::
    """
    try:
        from core.email_verification import email_verification

        verified = email_verification.verify_email(
            user_id=request.user_id,
            token=request.token
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Email verification {'succeeded' if verified else 'failed'} for ::{request.user_id}::",
            actor=auth.actor,
            details={"user_id": request.user_id, "verified": verified}
        )

        return {
            "qms_status": "Thank_You" if verified else "Thank_You_But_No",
            "verified": verified
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: CAPTCHA ENDPOINTS
# REM: =======================================================================================

@router.post("/captcha/generate")
async def captcha_generate(
    request: CaptchaGenerateRequest = CaptchaGenerateRequest(),
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Generate a CAPTCHA challenge.
    REM: QMS: CAPTCHA_Generate_Please
    REM: NOTE: Response does NOT include the answer — only challenge_id and question.
    """
    try:
        from core.captcha import captcha_manager

        from core.captcha import ChallengeType as _CT
        ct = None
        if request.challenge_type:
            try:
                ct = _CT(request.challenge_type)
            except ValueError:
                ct = None

        challenge = captcha_manager.generate_challenge(challenge_type=ct)

        return {
            "qms_status": "Thank_You",
            "challenge_id": challenge.challenge_id,
            "question": challenge.question
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CAPTCHA generation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/captcha/verify")
async def captcha_verify(
    request: CaptchaVerifyRequest,
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Verify a CAPTCHA challenge answer.
    REM: QMS: CAPTCHA_Verify_Please with ::challenge_id::
    """
    try:
        from core.captcha import captcha_manager

        solved = captcha_manager.verify_challenge(
            challenge_id=request.challenge_id,
            user_answer=request.answer
        )

        return {
            "qms_status": "Thank_You" if solved else "Thank_You_But_No",
            "solved": solved
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CAPTCHA verification failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: EMERGENCY ACCESS ENDPOINTS
# REM: =======================================================================================

@router.post("/emergency/request")
async def emergency_request(
    request: EmergencyAccessRequest,
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: Request emergency access.
    REM: QMS: Emergency_Request_Please with ::user_id:: ::reason::
    """
    try:
        from core.emergency_access import emergency_access_manager

        result = emergency_access_manager.request_emergency_access(
            user_id=request.user_id,
            reason=request.reason,
            duration_minutes=min(request.duration_minutes or 60, 1440)
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Emergency access requested by ::{request.user_id}:: — reason: ::{request.reason}::",
            actor=auth.actor,
            details={
                "user_id": request.user_id,
                "reason": request.reason,
                "duration_minutes": request.duration_minutes
            }
        )

        return {
            "qms_status": "Thank_You",
            **result.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emergency access request failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/emergency/{request_id}/approve")
async def emergency_approve(
    request_id: str,
    request: EmergencyApproveRequest,
    auth: AuthResult = Depends(require_permission("security:override"))
):
    """
    REM: Approve an emergency access request.
    REM: QMS: Emergency_Approve_Please with ::request_id:: ::approved_by::
    """
    try:
        from core.emergency_access import emergency_access_manager

        approved = emergency_access_manager.approve_emergency_access(
            request_id=request_id,
            approved_by=request.approved_by
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Emergency access ::{request_id}:: approved by ::{request.approved_by}::",
            actor=auth.actor,
            details={"request_id": request_id, "approved_by": request.approved_by}
        )

        return {
            "qms_status": "Thank_You" if approved else "Thank_You_But_No",
            "approved": approved
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emergency access approval failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/emergency/{request_id}/revoke")
async def emergency_revoke(
    request_id: str,
    request: EmergencyRevokeRequest,
    auth: AuthResult = Depends(require_permission("security:override"))
):
    """
    REM: Revoke an emergency access grant.
    REM: QMS: Emergency_Revoke_Please with ::request_id:: ::revoked_by::
    """
    try:
        from core.emergency_access import emergency_access_manager

        revoked = emergency_access_manager.revoke_emergency_access(
            request_id=request_id,
            revoked_by=request.revoked_by
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Emergency access ::{request_id}:: revoked by ::{request.revoked_by}::",
            actor=auth.actor,
            details={"request_id": request_id, "revoked_by": request.revoked_by}
        )

        return {
            "qms_status": "Thank_You" if revoked else "Thank_You_But_No",
            "revoked": revoked
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emergency access revocation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/emergency/active")
async def emergency_active(
    auth: AuthResult = Depends(require_permission("security:audit"))
):
    """
    REM: List all active emergency access grants.
    REM: QMS: Emergency_Active_Please
    """
    try:
        from core.emergency_access import emergency_access_manager

        emergencies = emergency_access_manager.get_active_emergencies()

        return {
            "qms_status": "Thank_You",
            "emergencies": emergencies
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emergency access list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })
