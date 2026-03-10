# TelsonBase/api/tenancy_routes.py
# REM: =======================================================================================
# REM: MULTI-TENANCY API ENDPOINTS FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Expose multi-tenancy and client-matter management as REST API
# REM: endpoints. Supports tenant lifecycle (create, list, get, deactivate) and
# REM: client-matter operations (create, list, close, litigation hold, release hold).
# REM: Every mutation is audit-logged with full QMS protocol compliance.
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

router = APIRouter(prefix="/v1/tenancy", tags=["Tenancy"])


# REM: =======================================================================================
# REM: PYDANTIC MODELS — TENANTS
# REM: =======================================================================================

class TenantCreateRequest(BaseModel):
    """REM: Request to create a new tenant organization."""
    name: str
    tenant_type: str = Field(..., description="One of: law_firm, insurance, real_estate, healthcare, small_business, personal, general")
    created_by: Optional[str] = "system"


class TenantDeactivateRequest(BaseModel):
    """REM: Request to deactivate a tenant."""
    deactivated_by: str


# REM: =======================================================================================
# REM: PYDANTIC MODELS — CLIENT-MATTERS
# REM: =======================================================================================

class MatterCreateRequest(BaseModel):
    """REM: Request to create a new client-matter under a tenant."""
    name: str
    matter_type: str = Field(..., description="e.g. transaction, litigation, client_file")
    created_by: Optional[str] = "system"


class MatterCloseRequest(BaseModel):
    """REM: Request to close a matter."""
    closed_by: str


class MatterHoldRequest(BaseModel):
    """REM: Request to place a litigation hold on a matter."""
    hold_by: str


class MatterReleaseHoldRequest(BaseModel):
    """REM: Request to release a litigation hold on a matter."""
    released_by: str


class GrantAccessRequest(BaseModel):
    """REM: v9.0.0B — Request to grant a user access to a specific tenant."""
    user_id: str


# REM: =======================================================================================
# REM: v9.0.0B — TENANT ACCESS CONTROL HELPER
# REM: =======================================================================================

def _require_tenant_access(tenant_id: str, auth: AuthResult):
    """
    REM: v9.0.0B — Verify the requesting actor has access to the specified tenant.
    REM: Admins (admin:config or *) bypass — they can see all tenants.
    REM: All other actors must be in tenant.allowed_actors.
    REM: Returns the Tenant if authorized.
    REM: Raises HTTP 404 if tenant not found. Raises HTTP 403 if access denied.
    """
    from core.tenancy import tenant_manager

    tenant = tenant_manager.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail={
            "qms_status": "Thank_You_But_No",
            "error": f"Tenant '{tenant_id}' not found"
        })
    # REM: Admin bypass — full access to all tenants
    if "admin:config" in auth.permissions or "*" in auth.permissions:
        return tenant
    # REM: Non-admin must be in allowed_actors
    if auth.actor not in tenant.allowed_actors:
        audit.log(
            AuditEventType.AUTH_FAILURE,
            f"Tenant access denied: ::{auth.actor}:: → ::{tenant_id}::",
            actor=auth.actor,
            resource=tenant_id,
            details={"action": "tenant_access_denied"},
            qms_status="Thank_You_But_No"
        )
        raise HTTPException(status_code=403, detail={
            "qms_status": "Thank_You_But_No",
            "error": "Access denied: you do not have access to this tenant."
        })
    return tenant


# REM: =======================================================================================
# REM: TENANT ENDPOINTS
# REM: =======================================================================================

@router.post("/tenants", summary="Create a tenant organization",
    description="**Requires admin:config.** Creates a new tenant. The authenticated actor is stored as `created_by` and seeded into `allowed_actors`. Non-admin users can only access tenants they created or were explicitly granted access to via the grant-access endpoint.")
async def tenant_create(
    request: TenantCreateRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Create a new tenant organization.
    REM: QMS: Tenant_Create_Please with ::name:: ::tenant_type::
    """
    try:
        from core.tenancy import tenant_manager

        # REM: Validate tenant_type before passing to manager
        valid_types = ["law_firm", "insurance", "real_estate", "healthcare", "small_business", "personal", "general"]
        if request.tenant_type not in valid_types:
            raise HTTPException(status_code=400, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Invalid tenant_type '{request.tenant_type}'. Must be one of: {valid_types}"
            })

        # REM: v9.0.0B — creator is always the authenticated actor, not user-supplied
        tenant = tenant_manager.create_tenant(
            name=request.name,
            tenant_type=request.tenant_type,
            created_by=auth.actor
        )

        return {
            "qms_status": "Thank_You",
            "tenant": tenant.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tenant creation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/tenants", summary="List tenants",
    description="**Requires view:dashboard.** Admins (`admin:config` or `*`) see all tenants. All other actors see only tenants where they appear in `allowed_actors`.")
async def tenant_list(
    active_only: bool = Query(False, description="If true, return only active tenants"),
    auth: AuthResult = Depends(require_permission("view:dashboard"))
):
    """
    REM: List all tenants, optionally filtered to active only.
    REM: QMS: Tenant_List_Please
    """
    try:
        from core.tenancy import tenant_manager

        # REM: v9.0.0B — Admins see all tenants; others see only their own
        is_admin = "admin:config" in auth.permissions or "*" in auth.permissions
        actor_filter = None if is_admin else auth.actor
        tenants = tenant_manager.list_tenants(actor_filter=actor_filter)

        if active_only:
            tenants = [t for t in tenants if t.is_active]

        return {
            "qms_status": "Thank_You",
            "tenants": [t.to_dict() for t in tenants],
            "count": len(tenants)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tenant list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/tenants/{tenant_id}", summary="Get a tenant",
    description="**Requires view:dashboard.** Returns 403 if the actor is not in the tenant's `allowed_actors` (unless admin). Access denial is written to the tamper-evident audit chain.")
async def tenant_get(
    tenant_id: str,
    auth: AuthResult = Depends(require_permission("view:dashboard"))
):
    """
    REM: Get details for a specific tenant.
    REM: QMS: Tenant_Get_Please with ::tenant_id::
    """
    try:
        # REM: v9.0.0B — _require_tenant_access raises 404 or 403 as appropriate
        tenant = _require_tenant_access(tenant_id, auth)

        return {
            "qms_status": "Thank_You",
            "tenant": tenant.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tenant get failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/tenants/{tenant_id}/deactivate")
async def tenant_deactivate(
    tenant_id: str,
    request: TenantDeactivateRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Deactivate a tenant. Does not delete data — just prevents access.
    REM: QMS: Tenant_Deactivate_Please with ::tenant_id:: ::deactivated_by::
    """
    try:
        from core.tenancy import tenant_manager

        # REM: v9.0.0B — Verify existence and access (admin:config still required by Depends)
        _require_tenant_access(tenant_id, auth)

        deactivated = tenant_manager.deactivate_tenant(
            tenant_id=tenant_id,
            deactivated_by=request.deactivated_by
        )

        return {
            "qms_status": "Thank_You" if deactivated else "Thank_You_But_No",
            "deactivated": deactivated
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tenant deactivation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: CLIENT-MATTER ENDPOINTS (TENANT-SCOPED)
# REM: =======================================================================================

@router.post("/tenants/{tenant_id}/matters")
async def matter_create(
    tenant_id: str,
    request: MatterCreateRequest,
    auth: AuthResult = Depends(require_permission("manage:agents"))
):
    """
    REM: Create a new client-matter record under a tenant.
    REM: QMS: Matter_Create_Please with ::tenant_id:: ::name:: ::matter_type::
    """
    try:
        from core.tenancy import tenant_manager

        # REM: v9.0.0B — Must have access to the parent tenant to create a matter under it
        _require_tenant_access(tenant_id, auth)

        matter = tenant_manager.create_matter(
            tenant_id=tenant_id,
            name=request.name,
            matter_type=request.matter_type,
            created_by=auth.actor
        )

        if not matter:
            raise HTTPException(status_code=400, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Cannot create matter — tenant '{tenant_id}' not found or is deactivated"
            })

        return {
            "qms_status": "Thank_You",
            "matter": matter.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Matter creation failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.get("/tenants/{tenant_id}/matters")
async def matter_list(
    tenant_id: str,
    status: Optional[str] = Query(None, description="Filter by status: active, closed, hold"),
    auth: AuthResult = Depends(require_permission("view:dashboard"))
):
    """
    REM: List all matters for a tenant, optionally filtered by status.
    REM: QMS: Matter_List_Please with ::tenant_id::
    """
    try:
        from core.tenancy import tenant_manager

        # REM: v9.0.0B — Access check covers 404 and 403
        _require_tenant_access(tenant_id, auth)

        matters = tenant_manager.list_matters(
            tenant_id=tenant_id,
            status_filter=status
        )

        return {
            "qms_status": "Thank_You",
            "matters": [m.to_dict() for m in matters],
            "count": len(matters)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Matter list failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: CLIENT-MATTER ENDPOINTS (DIRECT BY MATTER ID)
# REM: =======================================================================================

@router.get("/matters/{matter_id}")
async def matter_get(
    matter_id: str,
    auth: AuthResult = Depends(require_permission("view:dashboard"))
):
    """
    REM: Get details for a specific matter.
    REM: QMS: Matter_Get_Please with ::matter_id::
    """
    try:
        from core.tenancy import tenant_manager

        matter = tenant_manager.get_matter(matter_id=matter_id)
        if not matter:
            raise HTTPException(status_code=404, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Matter '{matter_id}' not found"
            })

        # REM: v9.0.0B — Check access to the parent tenant
        _require_tenant_access(matter.tenant_id, auth)

        return {
            "qms_status": "Thank_You",
            "matter": matter.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Matter get failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/matters/{matter_id}/close")
async def matter_close(
    matter_id: str,
    request: MatterCloseRequest,
    auth: AuthResult = Depends(require_permission("manage:agents"))
):
    """
    REM: Close a matter. Cannot close a matter under litigation hold.
    REM: QMS: Matter_Close_Please with ::matter_id:: ::closed_by::
    """
    try:
        from core.tenancy import tenant_manager

        matter = tenant_manager.get_matter(matter_id=matter_id)
        if not matter:
            raise HTTPException(status_code=404, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Matter '{matter_id}' not found"
            })

        # REM: v9.0.0B — Must have access to the parent tenant
        _require_tenant_access(matter.tenant_id, auth)

        closed = tenant_manager.close_matter(
            matter_id=matter_id,
            closed_by=request.closed_by
        )

        if not closed:
            raise HTTPException(status_code=400, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Cannot close matter '{matter_id}' — may be under litigation hold"
            })

        return {
            "qms_status": "Thank_You",
            "closed": closed
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Matter close failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/matters/{matter_id}/hold")
async def matter_hold(
    matter_id: str,
    request: MatterHoldRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Place a litigation hold on a matter.
    REM: Data under hold MUST be preserved — no deletion, no modification.
    REM: QMS: Matter_Hold_Please with ::matter_id:: ::hold_by::
    """
    try:
        from core.tenancy import tenant_manager

        matter = tenant_manager.get_matter(matter_id=matter_id)
        if not matter:
            raise HTTPException(status_code=404, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Matter '{matter_id}' not found"
            })

        # REM: v9.0.0B — Must have access to the parent tenant
        _require_tenant_access(matter.tenant_id, auth)

        held = tenant_manager.set_matter_hold(
            matter_id=matter_id,
            hold_by=request.hold_by
        )

        if not held:
            raise HTTPException(status_code=400, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Cannot place hold on matter '{matter_id}' — may already be closed"
            })

        return {
            "qms_status": "Thank_You",
            "held": held
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Matter hold failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


@router.post("/matters/{matter_id}/release-hold")
async def matter_release_hold(
    matter_id: str,
    request: MatterReleaseHoldRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: Release a litigation hold on a matter, returning it to active status.
    REM: QMS: Matter_ReleaseHold_Please with ::matter_id:: ::released_by::
    """
    try:
        from core.tenancy import tenant_manager

        matter = tenant_manager.get_matter(matter_id=matter_id)
        if not matter:
            raise HTTPException(status_code=404, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Matter '{matter_id}' not found"
            })

        # REM: v9.0.0B — Must have access to the parent tenant
        _require_tenant_access(matter.tenant_id, auth)

        released = tenant_manager.release_matter_hold(
            matter_id=matter_id,
            released_by=request.released_by
        )

        if not released:
            raise HTTPException(status_code=400, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Cannot release hold on matter '{matter_id}' — matter is not on hold"
            })

        return {
            "qms_status": "Thank_You",
            "released": released
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Matter hold release failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })


# REM: =======================================================================================
# REM: v9.0.0B — TENANT ACCESS GRANT ENDPOINT (ADMIN ONLY)
# REM: =======================================================================================

@router.post("/tenants/{tenant_id}/grant-access", summary="Grant tenant access to a user",
    description="**Admin only (admin:config required).** Adds the specified `user_id` to the tenant's `allowed_actors` list. Idempotent — granting access twice is a no-op. The granted actor can then call GET /tenants/{id}, GET /tenants/{id}/matters, and all matter-scoped routes for this tenant. Access grant is written to the tamper-evident audit chain.")
async def tenant_grant_access(
    tenant_id: str,
    request: GrantAccessRequest,
    auth: AuthResult = Depends(require_permission("admin:config"))
):
    """
    REM: v9.0.0B — Grant a user access to a specific tenant.
    REM: Admin-only. Idempotent — granting access twice is safe.
    REM: QMS: Tenant_GrantAccess_Please with ::tenant_id:: ::user_id::
    """
    try:
        from core.tenancy import tenant_manager

        granted = tenant_manager.grant_tenant_access(
            tenant_id=tenant_id,
            actor_id=request.user_id,
            granted_by=auth.actor
        )

        if not granted:
            raise HTTPException(status_code=404, detail={
                "qms_status": "Thank_You_But_No",
                "error": f"Tenant '{tenant_id}' not found"
            })

        return {
            "qms_status": "Thank_You",
            "granted": True,
            "tenant_id": tenant_id,
            "user_id": request.user_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tenant grant-access failed: {e}")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": str(e)
        })
