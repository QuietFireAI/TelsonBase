# TelsonBase/core/tenancy.py
# REM: =======================================================================================
# REM: MULTI-TENANCY & CLIENT-MATTER ISOLATION MODULE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v5.3.0CC: New feature - Multi-tenancy for real estate & legal professionals
#
# REM: Mission Statement: Zero-trust tenant isolation for legal, insurance, real estate,
# REM: healthcare, small business, and personal tenants. Each tenant's data is namespaced
# REM: and access-controlled. Client-matter structures allow professionals to organize
# REM: work under ethical walls and litigation holds. Every mutation is audit-logged.
#
# REM: Features:
# REM:   - Tenant creation, deactivation, and listing
# REM:   - Client/Matter lifecycle (create, close, hold, release)
# REM:   - TenantContext for scoping all data operations
# REM:   - Redis key namespacing via tenant_scoped_key()
# REM:   - In-memory storage (Redis persistence can come later)
# REM: =======================================================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: ENUMS
# REM: =======================================================================================

class TenantType(str, Enum):
    """REM: Classification of tenant organizations."""
    LAW_FIRM = "law_firm"
    INSURANCE = "insurance"
    REAL_ESTATE = "real_estate"
    HEALTHCARE = "healthcare"
    SMALL_BUSINESS = "small_business"
    PERSONAL = "personal"
    GENERAL = "general"


# REM: =======================================================================================
# REM: DATA MODELS
# REM: =======================================================================================

@dataclass
class Tenant:
    """REM: A tenant organization in the system."""
    tenant_id: str
    name: str
    tenant_type: TenantType
    created_at: datetime
    is_active: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)
    data_classification_default: str = "internal"
    # REM: v9.0.0B — Access control: creator and explicitly granted actors only
    created_by: str = "system"
    allowed_actors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "tenant_type": self.tenant_type.value,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            "settings": self.settings,
            "data_classification_default": self.data_classification_default,
            "created_by": self.created_by,
            "allowed_actors": self.allowed_actors,
        }


@dataclass
class ClientMatter:
    """
    REM: A client-matter record for organizing work within a tenant.
    REM: Used by law firms and brokerages to scope data under ethical walls.
    REM: status="hold" indicates a litigation hold is active — data must be preserved.
    """
    matter_id: str
    tenant_id: str
    name: str
    matter_type: str  # REM: e.g. "transaction", "litigation", "client_file"
    status: str = "active"  # REM: "active", "closed", "hold"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "matter_id": self.matter_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "matter_type": self.matter_type,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "metadata": self.metadata,
        }


@dataclass
class TenantContext:
    """
    REM: Lightweight context object passed through request handling.
    REM: Scopes all data operations to a specific tenant (and optionally a matter).
    """
    tenant_id: str
    user_id: str
    matter_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "matter_id": self.matter_id,
        }


# REM: =======================================================================================
# REM: UTILITY FUNCTIONS
# REM: =======================================================================================

def tenant_scoped_key(tenant_id: str, key: str) -> str:
    """
    REM: Build a Redis key namespaced to a specific tenant.
    REM: All tenant-scoped data MUST use this function for key generation
    REM: to guarantee isolation between tenants.
    """
    return f"tenant:{tenant_id}:{key}"


# REM: =======================================================================================
# REM: TENANT MANAGER
# REM: =======================================================================================

class TenantManager:
    """
    REM: Manages tenant lifecycle and client-matter records.
    REM: In-memory storage for now — Redis persistence can come later.
    """

    def __init__(self):
        self._tenants: Dict[str, Tenant] = {}
        self._matters: Dict[str, ClientMatter] = {}
        self._load_from_redis()

    def _load_from_redis(self) -> None:
        """REM: Load tenant and matter records from Redis on startup."""
        try:
            from core.persistence import tenancy_store

            # REM: Load tenants
            all_tenants = tenancy_store.list_tenants()
            for tenant_id, tenant_data in all_tenants.items():
                try:
                    tenant = Tenant(
                        tenant_id=tenant_data["tenant_id"],
                        name=tenant_data["name"],
                        tenant_type=TenantType(tenant_data["tenant_type"]),
                        created_at=datetime.fromisoformat(tenant_data["created_at"]),
                        is_active=tenant_data.get("is_active", True),
                        settings=tenant_data.get("settings", {}),
                        data_classification_default=tenant_data.get("data_classification_default", "internal"),
                        # REM: v9.0.0B — Restore access control fields from persistence
                        created_by=tenant_data.get("created_by", "system"),
                        allowed_actors=tenant_data.get("allowed_actors", []),
                    )
                    self._tenants[tenant_id] = tenant
                except Exception as e:
                    logger.warning(
                        f"REM: Failed to load tenant ::{tenant_id}:: from Redis: {e}_Thank_You_But_No"
                    )
            # REM: Load matters for each tenant
            for tenant_id in self._tenants:
                try:
                    matters = tenancy_store.list_tenant_matters(tenant_id)
                    for matter_data in matters:
                        try:
                            matter = ClientMatter(
                                matter_id=matter_data["matter_id"],
                                tenant_id=matter_data["tenant_id"],
                                name=matter_data["name"],
                                matter_type=matter_data["matter_type"],
                                status=matter_data.get("status", "active"),
                                created_at=datetime.fromisoformat(matter_data["created_at"]),
                                closed_at=(
                                    datetime.fromisoformat(matter_data["closed_at"])
                                    if matter_data.get("closed_at") else None
                                ),
                                metadata=matter_data.get("metadata", {}),
                            )
                            self._matters[matter.matter_id] = matter
                        except Exception as e:
                            logger.warning(
                                f"REM: Failed to load matter from Redis: {e}_Thank_You_But_No"
                            )
                except Exception as e:
                    logger.warning(
                        f"REM: Failed to load matters for tenant ::{tenant_id}:: from Redis: {e}_Thank_You_But_No"
                    )
            if all_tenants:
                logger.info(
                    f"REM: Loaded {len(self._tenants)} tenants and {len(self._matters)} matters from Redis_Thank_You"
                )
        except Exception as e:
            logger.warning(f"REM: Redis unavailable for tenancy load: {e}_Thank_You_But_No")

    def _save_tenant(self, tenant_id: str) -> None:
        """REM: Write-through save of a single tenant record to Redis."""
        try:
            from core.persistence import tenancy_store
            tenant = self._tenants.get(tenant_id)
            if not tenant:
                return
            tenancy_store.store_tenant(tenant_id, tenant.to_dict())
        except Exception as e:
            logger.warning(f"REM: Failed to save tenant to Redis for ::{tenant_id}::: {e}_Thank_You_But_No")

    def _save_matter(self, matter_id: str) -> None:
        """REM: Write-through save of a single matter record to Redis."""
        try:
            from core.persistence import tenancy_store
            matter = self._matters.get(matter_id)
            if not matter:
                return
            tenancy_store.store_matter(matter_id, matter.to_dict())
        except Exception as e:
            logger.warning(f"REM: Failed to save matter to Redis for ::{matter_id}::: {e}_Thank_You_But_No")

    # REM: ---------------------------------------------------------------------------------
    # REM: TENANT OPERATIONS
    # REM: ---------------------------------------------------------------------------------

    def create_tenant(
        self,
        name: str,
        tenant_type: str,
        created_by: str = "system"
    ) -> Tenant:
        """REM: Create a new tenant organization."""
        tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # REM: Resolve tenant type enum
        try:
            tt = TenantType(tenant_type)
        except ValueError:
            logger.warning(
                f"REM: Unknown tenant type ::{tenant_type}::, "
                f"defaulting to general_Thank_You_But_No"
            )
            tt = TenantType.GENERAL

        # REM: Law firms default to CONFIDENTIAL classification
        if tt == TenantType.LAW_FIRM:
            classification_default = "confidential"
        else:
            classification_default = "internal"

        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            tenant_type=tt,
            created_at=now,
            is_active=True,
            settings={},
            data_classification_default=classification_default,
            # REM: v9.0.0B — Store creator; initialize allowed_actors so creator has access
            created_by=created_by,
            allowed_actors=[created_by],
        )

        self._tenants[tenant_id] = tenant
        self._save_tenant(tenant_id)

        logger.info(
            f"REM: Tenant created - ::{name}:: type={tt.value} "
            f"classification={classification_default}_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Tenant created: {name} ({tt.value})",
            actor=created_by,
            resource=tenant_id,
            details={
                "tenant_type": tt.value,
                "data_classification_default": classification_default,
            },
            qms_status="Thank_You"
        )

        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """
        REM: Get a tenant by ID — checks in-memory first, falls back to Redis.
        REM: v9.0.0B — Redis fallback prevents 404s under multi-worker Gunicorn
        REM: when a tenant was created on a different worker (same pattern as OpenClaw get_instance).
        """
        # REM: Fast path — in-memory cache
        tenant = self._tenants.get(tenant_id)
        if tenant:
            return tenant
        # REM: Multi-worker fallback — check Redis for tenant created on another worker
        try:
            from core.persistence import tenancy_store
            tenant_data = tenancy_store.get_tenant(tenant_id)
            if tenant_data:
                tenant = Tenant(
                    tenant_id=tenant_data["tenant_id"],
                    name=tenant_data["name"],
                    tenant_type=TenantType(tenant_data["tenant_type"]),
                    created_at=datetime.fromisoformat(tenant_data["created_at"]),
                    is_active=tenant_data.get("is_active", True),
                    settings=tenant_data.get("settings", {}),
                    data_classification_default=tenant_data.get("data_classification_default", "internal"),
                    created_by=tenant_data.get("created_by", "system"),
                    allowed_actors=tenant_data.get("allowed_actors", []),
                )
                # REM: Cache in this worker's memory for subsequent requests
                self._tenants[tenant_id] = tenant
                logger.debug(
                    f"REM: Tenant ::{tenant_id}:: loaded from Redis fallback (cross-worker)_Thank_You"
                )
                return tenant
        except Exception as e:
            logger.warning(
                f"REM: Redis fallback for tenant ::{tenant_id}:: failed: {e}_Thank_You_But_No"
            )
        return None

    def list_tenants(self, actor_filter: Optional[str] = None) -> List[Tenant]:
        """
        REM: List all tenants.
        REM: When actor_filter is provided, returns only tenants where the actor
        REM: is in allowed_actors. Pass None to get all tenants (admin use only).
        """
        all_tenants = list(self._tenants.values())
        if actor_filter is None:
            return all_tenants
        return [t for t in all_tenants if actor_filter in t.allowed_actors]

    def grant_tenant_access(self, tenant_id: str, actor_id: str, granted_by: str = "system") -> bool:
        """
        REM: v9.0.0B — Grant an actor access to a tenant.
        REM: Admin-only operation. Idempotent (no-op if already granted).
        """
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            logger.warning(
                f"REM: grant_tenant_access — tenant ::{tenant_id}:: not found_Thank_You_But_No"
            )
            return False
        if actor_id not in tenant.allowed_actors:
            tenant.allowed_actors.append(actor_id)
            self._save_tenant(tenant_id)
            logger.info(
                f"REM: Tenant access granted — actor ::{actor_id}:: → tenant ::{tenant_id}:: "
                f"by ::{granted_by}::_Thank_You"
            )
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Tenant access granted: {actor_id} → {tenant_id}",
                actor=granted_by,
                resource=tenant_id,
                details={"actor_id": actor_id},
                qms_status="Thank_You"
            )
        return True

    def deactivate_tenant(
        self,
        tenant_id: str,
        deactivated_by: str = "system"
    ) -> bool:
        """REM: Deactivate a tenant. Does not delete data — just prevents access."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False

        tenant.is_active = False
        self._save_tenant(tenant_id)

        logger.warning(
            f"REM: Tenant ::{tenant.name}:: deactivated "
            f"by ::{deactivated_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Tenant deactivated: {tenant.name}",
            actor=deactivated_by,
            resource=tenant_id,
            details={"tenant_name": tenant.name},
            qms_status="Thank_You"
        )

        return True

    # REM: ---------------------------------------------------------------------------------
    # REM: CLIENT-MATTER OPERATIONS
    # REM: ---------------------------------------------------------------------------------

    def create_matter(
        self,
        tenant_id: str,
        name: str,
        matter_type: str,
        created_by: str = "system"
    ) -> Optional[ClientMatter]:
        """REM: Create a new client-matter record under a tenant."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            logger.warning(
                f"REM: Cannot create matter — tenant ::{tenant_id}:: "
                f"not found_Thank_You_But_No"
            )
            return None

        if not tenant.is_active:
            logger.warning(
                f"REM: Cannot create matter — tenant ::{tenant.name}:: "
                f"is deactivated_Thank_You_But_No"
            )
            return None

        matter_id = f"matter_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        matter = ClientMatter(
            matter_id=matter_id,
            tenant_id=tenant_id,
            name=name,
            matter_type=matter_type,
            status="active",
            created_at=now,
            metadata={},
        )

        self._matters[matter_id] = matter
        self._save_matter(matter_id)

        logger.info(
            f"REM: Matter created - ::{name}:: type={matter_type} "
            f"tenant=::{tenant.name}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Matter created: {name} ({matter_type}) under tenant {tenant.name}",
            actor=created_by,
            resource=matter_id,
            details={
                "tenant_id": tenant_id,
                "matter_type": matter_type,
            },
            qms_status="Thank_You"
        )

        return matter

    def get_matter(self, matter_id: str) -> Optional[ClientMatter]:
        """REM: Get a matter by ID."""
        return self._matters.get(matter_id)

    def list_matters(
        self,
        tenant_id: str,
        status_filter: Optional[str] = None
    ) -> List[ClientMatter]:
        """REM: List all matters for a tenant, optionally filtered by status."""
        results = []
        for matter in self._matters.values():
            if matter.tenant_id != tenant_id:
                continue
            if status_filter and matter.status != status_filter:
                continue
            results.append(matter)
        return results

    def close_matter(
        self,
        matter_id: str,
        closed_by: str = "system"
    ) -> bool:
        """REM: Close a matter. Sets status to closed and records closure time."""
        matter = self._matters.get(matter_id)
        if not matter:
            return False

        # REM: Cannot close a matter under litigation hold
        if matter.status == "hold":
            logger.warning(
                f"REM: Cannot close matter ::{matter.name}:: — "
                f"litigation hold active_Thank_You_But_No"
            )
            return False

        now = datetime.now(timezone.utc)
        matter.status = "closed"
        matter.closed_at = now
        self._save_matter(matter_id)

        logger.info(
            f"REM: Matter ::{matter.name}:: closed "
            f"by ::{closed_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Matter closed: {matter.name}",
            actor=closed_by,
            resource=matter_id,
            details={
                "tenant_id": matter.tenant_id,
                "closed_at": now.isoformat(),
            },
            qms_status="Thank_You"
        )

        return True

    def set_matter_hold(
        self,
        matter_id: str,
        hold_by: str = "system"
    ) -> bool:
        """
        REM: Place a litigation hold on a matter.
        REM: Data under hold MUST be preserved — no deletion, no modification.
        """
        matter = self._matters.get(matter_id)
        if not matter:
            return False

        if matter.status == "closed":
            logger.warning(
                f"REM: Cannot hold closed matter ::{matter.name}::_Thank_You_But_No"
            )
            return False

        matter.status = "hold"
        self._save_matter(matter_id)

        logger.warning(
            f"REM: LITIGATION HOLD placed on matter ::{matter.name}:: "
            f"by ::{hold_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Litigation hold placed: {matter.name}",
            actor=hold_by,
            resource=matter_id,
            details={
                "tenant_id": matter.tenant_id,
                "previous_status": "active",
            },
            qms_status="Thank_You"
        )

        return True

    def release_matter_hold(
        self,
        matter_id: str,
        released_by: str = "system"
    ) -> bool:
        """
        REM: Release a litigation hold on a matter.
        REM: Returns the matter to active status.
        """
        matter = self._matters.get(matter_id)
        if not matter:
            return False

        if matter.status != "hold":
            logger.warning(
                f"REM: Matter ::{matter.name}:: is not on hold — "
                f"cannot release_Thank_You_But_No"
            )
            return False

        matter.status = "active"
        self._save_matter(matter_id)

        logger.info(
            f"REM: Litigation hold released on matter ::{matter.name}:: "
            f"by ::{released_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Litigation hold released: {matter.name}",
            actor=released_by,
            resource=matter_id,
            details={"tenant_id": matter.tenant_id},
            qms_status="Thank_You"
        )

        return True


# REM: =======================================================================================
# REM: GLOBAL TENANT MANAGER INSTANCE
# REM: =======================================================================================

tenant_manager = TenantManager()
