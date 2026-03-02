# TelsonBase/core/auth_dependencies.py
# REM: =======================================================================================
# REM: COMPOSABLE FASTAPI DEPENDENCIES FOR MFA & SESSION ENFORCEMENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.4.0CC: Priority 3 — Composable auth dependencies
#
# REM: Mission Statement: Provide reusable FastAPI Depends() callables that layer MFA
# REM: enrollment checks and active-session enforcement on top of the existing
# REM: authenticate_request dependency. Each dependency is self-contained and can be
# REM: composed freely in endpoint signatures.
#
# REM: Dependencies:
# REM:   require_mfa              — Ensures MFA enrollment for privileged roles
# REM:   require_active_session   — Ensures a valid, non-expired session is attached
# REM:   require_mfa_and_session  — Combines both checks in a single dependency
#
# REM: QMS Protocol:
# REM:   Success: "Thank_You"
# REM:   Failure: "Thank_You_But_No"
# REM: =======================================================================================

import logging
from fastapi import Depends, HTTPException

from core.auth import authenticate_request, AuthResult
from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: DEPENDENCY: require_mfa
# REM: =======================================================================================
# REM: Verifies that users holding privileged roles (Admin, Security Officer, Super Admin)
# REM: have completed MFA enrollment. Pure API-key auth without RBAC context is allowed
# REM: through for backward compatibility.
# REM: =======================================================================================

async def require_mfa(
    auth: AuthResult = Depends(authenticate_request),
) -> AuthResult:
    """
    REM: FastAPI dependency — enforce MFA enrollment for privileged roles.

    Usage:
        @app.get("/admin/secure-endpoint")
        async def secure_endpoint(auth: AuthResult = Depends(require_mfa)):
            ...
    """
    # REM: Lazy import to avoid circular dependencies at module load time
    from core.mfa import mfa_manager, MFAManager
    from core.rbac import rbac_manager

    # REM: Resolve the RBAC user from the auth actor identity.
    # REM: If no RBAC user is found (pure API-key auth with no linked user),
    # REM: skip MFA check — backward compatible with pre-RBAC deployments.
    user = _resolve_rbac_user(auth, rbac_manager)
    if user is None:
        logger.debug(
            "REM: No RBAC context for actor ::%s:: — MFA check skipped_Thank_You",
            auth.actor,
        )
        return auth

    # REM: Check if this user's roles require MFA
    if not mfa_manager.is_mfa_required(user):
        return auth

    # REM: User holds a privileged role — MFA enrollment is mandatory
    if not mfa_manager.is_enrolled(user.user_id):
        logger.warning(
            "REM: MFA enrollment required but missing for user ::%s::_Thank_You_But_No",
            user.user_id,
        )
        audit.log(
            AuditEventType.AUTH_FAILURE,
            f"MFA enrollment required but not enrolled: {user.username}",
            actor=auth.actor,
            details={
                "user_id": user.user_id,
                "roles": [r.value for r in user.roles],
                "check": "require_mfa",
            },
            qms_status="Thank_You_But_No",
        )
        raise HTTPException(
            status_code=403,
            detail="MFA enrollment required",
        )

    logger.debug(
        "REM: MFA enrollment verified for user ::%s::_Thank_You",
        user.user_id,
    )
    return auth


# REM: =======================================================================================
# REM: DEPENDENCY: require_active_session
# REM: =======================================================================================
# REM: Ensures an active, non-expired session is associated with the request.
# REM: Looks for session ID in the auth permissions context. Touches the session to
# REM: update last_activity and checks expiry/idle in one step.
# REM: =======================================================================================

async def require_active_session(
    auth: AuthResult = Depends(authenticate_request),
) -> AuthResult:
    """
    REM: FastAPI dependency — enforce an active, valid session.

    Usage:
        @app.get("/phi/records")
        async def phi_records(auth: AuthResult = Depends(require_active_session)):
            ...
    """
    # REM: Lazy import to avoid circular dependencies
    from core.session_management import session_manager

    # REM: Extract session ID from auth context.
    # REM: Convention: session ID is carried as "session:<id>" in the permissions list.
    session_id = _extract_session_id(auth)

    if not session_id:
        logger.warning(
            "REM: Active session required but no X-Session-ID for actor ::%s::_Thank_You_But_No",
            auth.actor,
        )
        audit.log(
            AuditEventType.AUTH_FAILURE,
            f"Active session required but none provided by {auth.actor}",
            actor=auth.actor,
            details={"check": "require_active_session"},
            qms_status="Thank_You_But_No",
        )
        raise HTTPException(
            status_code=401,
            detail="Active session required",
        )

    # REM: Touch the session (update last_activity) and then validate
    touched = session_manager.touch_session(session_id)
    if not touched:
        # REM: Session not found or already inactive
        logger.warning(
            "REM: Session ::%s:: not found or inactive for actor ::%s::_Thank_You_But_No",
            session_id,
            auth.actor,
        )
        audit.log(
            AuditEventType.AUTH_FAILURE,
            f"Session expired or invalid: {session_id}",
            actor=auth.actor,
            details={"session_id": session_id, "check": "require_active_session"},
            qms_status="Thank_You_But_No",
        )
        raise HTTPException(
            status_code=401,
            detail="Session expired",
        )

    # REM: Validate idle timeout and max duration
    is_valid = session_manager.check_session(session_id)
    if not is_valid:
        logger.warning(
            "REM: Session ::%s:: expired (idle or max duration) for actor ::%s::_Thank_You_But_No",
            session_id,
            auth.actor,
        )
        audit.log(
            AuditEventType.AUTH_FAILURE,
            f"Session expired after validation: {session_id}",
            actor=auth.actor,
            details={"session_id": session_id, "check": "require_active_session"},
            qms_status="Thank_You_But_No",
        )
        raise HTTPException(
            status_code=401,
            detail="Session expired",
        )

    logger.debug(
        "REM: Active session ::%s:: validated for actor ::%s::_Thank_You",
        session_id,
        auth.actor,
    )
    return auth


# REM: =======================================================================================
# REM: DEPENDENCY: require_mfa_and_session
# REM: =======================================================================================
# REM: Combines MFA enrollment check and active session enforcement into a single
# REM: dependency for endpoints that need both guarantees.
# REM: =======================================================================================

async def require_mfa_and_session(
    auth: AuthResult = Depends(authenticate_request),
) -> AuthResult:
    """
    REM: FastAPI dependency — enforce both MFA enrollment and active session.

    Usage:
        @app.post("/phi/sensitive-action")
        async def sensitive_action(auth: AuthResult = Depends(require_mfa_and_session)):
            ...
    """
    # REM: Run MFA check first (enrollment gate)
    auth = await require_mfa(auth)

    # REM: Then run session check (active session gate)
    auth = await require_active_session(auth)

    logger.debug(
        "REM: MFA + session validated for actor ::%s::_Thank_You",
        auth.actor,
    )
    return auth


# REM: =======================================================================================
# REM: INTERNAL HELPERS
# REM: =======================================================================================

def _resolve_rbac_user(auth: AuthResult, rbac_manager):
    """
    REM: Attempt to resolve an RBAC User from the AuthResult actor identity.
    REM: Checks by username first (actor often contains "owner:label" or a username),
    REM: then by user_id. Returns None if no RBAC user is found.
    """
    from core.rbac import User

    # REM: Try parsing "owner:label" format from API key auth
    actor_parts = auth.actor.split(":")
    actor_name = actor_parts[0] if actor_parts else auth.actor

    # REM: Look up by username
    user = rbac_manager.get_user_by_username(actor_name)
    if user:
        return user

    # REM: Look up by user_id directly
    user = rbac_manager.get_user(actor_name)
    if user:
        return user

    # REM: Try the full actor string as user_id
    if actor_name != auth.actor:
        user = rbac_manager.get_user(auth.actor)
        if user:
            return user

    return None


def _extract_session_id(auth: AuthResult) -> str:
    """
    REM: Extract session ID from the auth context.
    REM: Convention: session ID is passed as a "session:<id>" entry in permissions,
    REM: or as an X-Session-ID header value propagated through the auth pipeline.
    """
    # REM: Check permissions list for "session:<id>" entries
    for perm in auth.permissions:
        if perm.startswith("session:"):
            return perm[len("session:"):]

    return ""
