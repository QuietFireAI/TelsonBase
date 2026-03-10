# TelsonBase/core/data_retention.py
# REM: =======================================================================================
# REM: DATA RETENTION AND DELETION ENGINE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: CCPA and state privacy law compliance through structured data
# REM: retention policies and auditable deletion workflows. Real estate and legal
# REM: professionals must demonstrate they only keep data as long as legally required,
# REM: and that deletion requests are handled properly.
#
# REM: Features:
# REM:   - Configurable retention policies per tenant or global
# REM:   - Auditable deletion request workflow (request -> approve -> execute)
# REM:   - Legal hold integration check before any deletion
# REM:   - Scheduled retention expiry detection
# REM:   - QMS-formatted logging throughout
# REM: =======================================================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


@dataclass
class RetentionPolicy:
    """REM: A data retention policy defining how long specific data types are kept."""
    policy_id: str
    name: str
    tenant_id: Optional[str]  # REM: None = global policy applying to all tenants
    retention_days: int
    data_types: List[str]  # REM: e.g., ["client_data", "transaction", "communication"]
    auto_delete: bool  # REM: Whether to automatically purge data on expiry
    created_at: datetime
    created_by: str

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "tenant_id": self.tenant_id,
            "retention_days": self.retention_days,
            "data_types": self.data_types,
            "auto_delete": self.auto_delete,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by
        }


@dataclass
class DeletionRequest:
    """REM: A request to delete data, tracked through an approval workflow."""
    request_id: str
    tenant_id: str
    matter_id: Optional[str]
    requested_by: str
    reason: str  # REM: e.g., "ccpa_deletion", "engagement_termination", "retention_expired"
    status: str  # REM: "pending", "approved", "executing", "completed", "blocked_by_hold"
    created_at: datetime
    completed_at: Optional[datetime] = None
    deleted_keys: List[str] = field(default_factory=list)  # REM: Record of what was deleted

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "matter_id": self.matter_id,
            "requested_by": self.requested_by,
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "deleted_keys": self.deleted_keys
        }


class RetentionManager:
    """
    REM: Manages data retention policies and deletion workflows.
    REM: All mutations are audit-logged for compliance evidence.
    """

    def __init__(self):
        # REM: In-memory storage for policies and deletion requests
        self._policies: Dict[str, RetentionPolicy] = {}
        self._deletion_requests: Dict[str, DeletionRequest] = {}
        # REM: Simulated data store tracking creation timestamps per key
        # REM: In production, this would query actual data stores
        self._data_registry: Dict[str, Dict[str, Any]] = {}
        # REM: Callback hook for checking legal holds (set externally if needed)
        self._legal_hold_checker = None

        # REM: Load persisted records from Redis
        self._load_from_redis()

        logger.info("REM: RetentionManager initialized_Thank_You")

    def create_policy(
        self,
        name: str,
        tenant_id: Optional[str],
        retention_days: int,
        data_types: List[str],
        auto_delete: bool,
        created_by: str
    ) -> RetentionPolicy:
        """REM: Create a new retention policy."""
        policy_id = f"rpol_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        policy = RetentionPolicy(
            policy_id=policy_id,
            name=name,
            tenant_id=tenant_id,
            retention_days=retention_days,
            data_types=data_types,
            auto_delete=auto_delete,
            created_at=now,
            created_by=created_by
        )

        self._policies[policy_id] = policy

        logger.info(
            f"REM: Retention policy created - ::{name}:: "
            f"({retention_days} days) by ::{created_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Retention policy created: {name}",
            actor=created_by,
            resource=policy_id,
            details={
                "tenant_id": tenant_id,
                "retention_days": retention_days,
                "data_types": data_types,
                "auto_delete": auto_delete
            },
            qms_status="Thank_You"
        )

        self._save_policy(policy_id)

        return policy

    def get_policies(self, tenant_id: Optional[str] = None) -> List[RetentionPolicy]:
        """REM: Get retention policies, optionally filtered by tenant."""
        if tenant_id is None:
            return list(self._policies.values())
        # REM: Return tenant-specific policies plus global policies (tenant_id=None)
        return [
            p for p in self._policies.values()
            if p.tenant_id == tenant_id or p.tenant_id is None
        ]

    def request_deletion(
        self,
        tenant_id: str,
        matter_id: Optional[str],
        requested_by: str,
        reason: str
    ) -> DeletionRequest:
        """REM: Create a deletion request. Must be approved before execution."""
        request_id = f"del_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        request = DeletionRequest(
            request_id=request_id,
            tenant_id=tenant_id,
            matter_id=matter_id,
            requested_by=requested_by,
            reason=reason,
            status="pending",
            created_at=now
        )

        self._deletion_requests[request_id] = request

        logger.info(
            f"REM: Deletion request created - ::{request_id}:: "
            f"by ::{requested_by}:: reason: ::{reason}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Deletion request created: {reason}",
            actor=requested_by,
            resource=request_id,
            details={
                "tenant_id": tenant_id,
                "matter_id": matter_id,
                "reason": reason
            },
            qms_status="Thank_You"
        )

        self._save_deletion_request(request_id)

        return request

    def approve_deletion(self, request_id: str, approved_by: str) -> bool:
        """REM: Approve a pending deletion request."""
        request = self._deletion_requests.get(request_id)
        if not request:
            logger.warning(f"REM: Deletion request ::{request_id}:: not found_Thank_You_But_No")
            return False

        if request.status != "pending":
            logger.warning(
                f"REM: Deletion request ::{request_id}:: is not pending "
                f"(status: {request.status})_Thank_You_But_No"
            )
            return False

        request.status = "approved"

        logger.info(
            f"REM: Deletion request ::{request_id}:: approved "
            f"by ::{approved_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Deletion request approved: {request_id}",
            actor=approved_by,
            resource=request_id,
            details={
                "tenant_id": request.tenant_id,
                "matter_id": request.matter_id,
                "reason": request.reason
            },
            qms_status="Thank_You"
        )

        self._save_deletion_request(request_id)

        return True

    def execute_deletion(self, request_id: str) -> dict:
        """
        REM: Execute an approved deletion request.
        REM: Checks for legal holds first. If data is under hold, deletion is blocked.
        """
        request = self._deletion_requests.get(request_id)
        if not request:
            logger.warning(f"REM: Deletion request ::{request_id}:: not found_Thank_You_But_No")
            return {"status": "error", "keys_deleted": 0}

        if request.status != "approved":
            logger.warning(
                f"REM: Deletion request ::{request_id}:: is not approved "
                f"(status: {request.status})_Thank_You_But_No"
            )
            return {"status": "error", "keys_deleted": 0}

        # REM: Check for legal holds before proceeding
        if self._legal_hold_checker and self._legal_hold_checker(
            request.tenant_id, request.matter_id
        ):
            request.status = "blocked_by_hold"

            logger.warning(
                f"REM: Deletion request ::{request_id}:: blocked by legal hold_Thank_You_But_No"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Deletion blocked by legal hold: {request_id}",
                actor="system",
                resource=request_id,
                details={
                    "tenant_id": request.tenant_id,
                    "matter_id": request.matter_id,
                    "reason": "active_legal_hold"
                },
                qms_status="Thank_You_But_No"
            )

            self._save_deletion_request(request_id)

            return {"status": "blocked_by_hold", "keys_deleted": 0}

        # REM: Execute the deletion
        request.status = "executing"
        keys_deleted = []

        # REM: Find and remove matching data from the registry
        keys_to_delete = [
            key for key, meta in self._data_registry.items()
            if meta.get("tenant_id") == request.tenant_id
            and (request.matter_id is None or meta.get("matter_id") == request.matter_id)
        ]

        for key in keys_to_delete:
            del self._data_registry[key]
            keys_deleted.append(key)

        request.status = "completed"
        request.completed_at = datetime.now(timezone.utc)
        request.deleted_keys = keys_deleted

        logger.info(
            f"REM: Deletion request ::{request_id}:: completed - "
            f"{len(keys_deleted)} keys deleted_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Deletion executed: {request_id}",
            actor="system",
            resource=request_id,
            details={
                "tenant_id": request.tenant_id,
                "matter_id": request.matter_id,
                "keys_deleted": len(keys_deleted),
                "deleted_key_ids": keys_deleted
            },
            qms_status="Thank_You"
        )

        self._save_deletion_request(request_id)

        return {"status": "completed", "keys_deleted": len(keys_deleted)}

    def get_deletion_requests(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[DeletionRequest]:
        """REM: Get deletion requests, optionally filtered by tenant and/or status."""
        results = list(self._deletion_requests.values())
        if tenant_id is not None:
            results = [r for r in results if r.tenant_id == tenant_id]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results

    def check_retention_expiry(self) -> List[dict]:
        """
        REM: Find data that has passed its retention period.
        REM: Intended to be called by a scheduled job.
        """
        now = datetime.now(timezone.utc)
        expired_items = []

        for key, meta in self._data_registry.items():
            created_at = meta.get("created_at")
            tenant_id = meta.get("tenant_id")
            data_type = meta.get("data_type")

            if not created_at or not tenant_id:
                continue

            # REM: Find applicable policies for this data
            applicable_policies = [
                p for p in self._policies.values()
                if (p.tenant_id == tenant_id or p.tenant_id is None)
                and data_type in p.data_types
            ]

            for policy in applicable_policies:
                expiry_date = created_at + timedelta(days=policy.retention_days)
                if now > expiry_date:
                    expired_items.append({
                        "key": key,
                        "tenant_id": tenant_id,
                        "data_type": data_type,
                        "created_at": created_at.isoformat(),
                        "expired_at": expiry_date.isoformat(),
                        "policy_id": policy.policy_id,
                        "auto_delete": policy.auto_delete
                    })

        logger.info(
            f"REM: Retention expiry check complete - "
            f"{len(expired_items)} items past retention_Thank_You"
        )

        return expired_items

    def _load_from_redis(self):
        """REM: Load retention policies and deletion requests from Redis on startup."""
        try:
            from core.persistence import compliance_store

            # REM: Load retention policies
            all_policies = compliance_store.list_records("retention_policies")
            for record_id, record_data in all_policies.items():
                self._policies[record_id] = RetentionPolicy(
                    policy_id=record_data["policy_id"],
                    name=record_data["name"],
                    tenant_id=record_data.get("tenant_id"),
                    retention_days=record_data["retention_days"],
                    data_types=record_data["data_types"],
                    auto_delete=record_data["auto_delete"],
                    created_at=datetime.fromisoformat(record_data["created_at"]),
                    created_by=record_data["created_by"]
                )
            if self._policies:
                logger.info(f"REM: Loaded {len(self._policies)} retention policies from Redis_Thank_You")

            # REM: Load deletion requests
            all_requests = compliance_store.list_records("deletion_requests")
            for record_id, record_data in all_requests.items():
                self._deletion_requests[record_id] = DeletionRequest(
                    request_id=record_data["request_id"],
                    tenant_id=record_data["tenant_id"],
                    matter_id=record_data.get("matter_id"),
                    requested_by=record_data["requested_by"],
                    reason=record_data["reason"],
                    status=record_data["status"],
                    created_at=datetime.fromisoformat(record_data["created_at"]),
                    completed_at=datetime.fromisoformat(record_data["completed_at"]) if record_data.get("completed_at") else None,
                    deleted_keys=record_data.get("deleted_keys", [])
                )
            if self._deletion_requests:
                logger.info(f"REM: Loaded {len(self._deletion_requests)} deletion requests from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Could not load retention data from Redis: {e}_Excuse_Me")

    def _save_policy(self, record_id: str):
        """REM: Persist a single retention policy to Redis."""
        try:
            from core.persistence import compliance_store
            record = self._policies.get(record_id)
            if record:
                data = record.to_dict()
                compliance_store.store_record("retention_policies", record_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save retention policy to Redis: {e}_Excuse_Me")

    def _save_deletion_request(self, record_id: str):
        """REM: Persist a single deletion request to Redis."""
        try:
            from core.persistence import compliance_store
            record = self._deletion_requests.get(record_id)
            if record:
                data = record.to_dict()
                compliance_store.store_record("deletion_requests", record_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save deletion request to Redis: {e}_Excuse_Me")
