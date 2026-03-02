# TelsonBase/core/legal_hold.py
# REM: =======================================================================================
# REM: LITIGATION HOLD / LEGAL HOLD SYSTEM
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: FRCP Rule 37(e) and eDiscovery compliance through structured
# REM: legal hold management. When litigation is anticipated, all potentially relevant
# REM: data must be preserved. Failure to do so can result in sanctions, adverse
# REM: inference instructions, or case dismissal.
#
# REM: Features:
# REM:   - Legal hold creation with scope definition
# REM:   - Custodian notification and acknowledgment tracking
# REM:   - Hold release with audit trail
# REM:   - Data hold status checking (integrates with deletion engine)
# REM:   - QMS-formatted logging throughout
# REM: =======================================================================================

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


@dataclass
class LegalHold:
    """REM: A litigation hold preserving data from deletion or modification."""
    hold_id: str
    tenant_id: str
    matter_id: Optional[str]  # REM: Specific matter, or None for tenant-wide hold
    name: str  # REM: e.g., "Smith v. Jones litigation hold"
    reason: str
    scope: List[str]  # REM: Data types covered: ["all", "communications", "documents", "transactions"]
    status: str  # REM: "active" or "released"
    created_at: datetime
    created_by: str
    released_at: Optional[datetime] = None
    released_by: Optional[str] = None
    custodians: List[str] = field(default_factory=list)  # REM: User IDs who have been notified
    acknowledgments: Dict[str, datetime] = field(default_factory=dict)  # REM: user_id -> ack timestamp

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "hold_id": self.hold_id,
            "tenant_id": self.tenant_id,
            "matter_id": self.matter_id,
            "name": self.name,
            "reason": self.reason,
            "scope": self.scope,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "released_at": self.released_at.isoformat() if self.released_at else None,
            "released_by": self.released_by,
            "custodians": self.custodians,
            "acknowledgments": {
                uid: ts.isoformat() for uid, ts in self.acknowledgments.items()
            }
        }


class HoldManager:
    """
    REM: Manages legal holds for litigation preservation and eDiscovery compliance.
    REM: All mutations are audit-logged for FRCP Rule 37(e) evidence.
    """

    def __init__(self):
        # REM: In-memory storage for legal holds
        self._holds: Dict[str, LegalHold] = {}

        # REM: Load persisted records from Redis
        self._load_from_redis()

        logger.info("REM: HoldManager initialized_Thank_You")

    def create_hold(
        self,
        tenant_id: str,
        matter_id: Optional[str],
        name: str,
        reason: str,
        scope: List[str],
        created_by: str
    ) -> LegalHold:
        """REM: Create a new legal hold. All matching data is preserved from this point."""
        hold_id = f"hold_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        hold = LegalHold(
            hold_id=hold_id,
            tenant_id=tenant_id,
            matter_id=matter_id,
            name=name,
            reason=reason,
            scope=scope,
            status="active",
            created_at=now,
            created_by=created_by
        )

        self._holds[hold_id] = hold

        logger.info(
            f"REM: Legal hold created - ::{name}:: "
            f"for tenant ::{tenant_id}:: by ::{created_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Legal hold created: {name}",
            actor=created_by,
            resource=hold_id,
            details={
                "tenant_id": tenant_id,
                "matter_id": matter_id,
                "scope": scope,
                "reason": reason
            },
            qms_status="Thank_You"
        )

        self._save_record(hold_id)

        return hold

    def get_hold(self, hold_id: str) -> Optional[LegalHold]:
        """REM: Get a legal hold by ID."""
        return self._holds.get(hold_id)

    def list_holds(
        self,
        tenant_id: Optional[str] = None,
        status: str = "active"
    ) -> List[LegalHold]:
        """REM: List legal holds, optionally filtered by tenant and status."""
        results = list(self._holds.values())
        if tenant_id is not None:
            results = [h for h in results if h.tenant_id == tenant_id]
        results = [h for h in results if h.status == status]
        return results

    def release_hold(self, hold_id: str, released_by: str, reason: str) -> bool:
        """
        REM: Release a legal hold. Requires SECURITY_OFFICER or SUPER_ADMIN level.
        REM: Caller must verify authorization before invoking this method.
        """
        hold = self._holds.get(hold_id)
        if not hold:
            logger.warning(f"REM: Legal hold ::{hold_id}:: not found_Thank_You_But_No")
            return False

        if hold.status != "active":
            logger.warning(
                f"REM: Legal hold ::{hold_id}:: is not active "
                f"(status: {hold.status})_Thank_You_But_No"
            )
            return False

        now = datetime.now(timezone.utc)
        hold.status = "released"
        hold.released_at = now
        hold.released_by = released_by

        logger.info(
            f"REM: Legal hold ::{hold.name}:: released "
            f"by ::{released_by}:: reason: ::{reason}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Legal hold released: {hold.name}",
            actor=released_by,
            resource=hold_id,
            details={
                "tenant_id": hold.tenant_id,
                "matter_id": hold.matter_id,
                "release_reason": reason,
                "held_since": hold.created_at.isoformat(),
                "custodian_count": len(hold.custodians),
                "acknowledgment_count": len(hold.acknowledgments)
            },
            qms_status="Thank_You"
        )

        self._save_record(hold_id)

        return True

    def is_data_held(self, tenant_id: str, matter_id: Optional[str] = None) -> bool:
        """
        REM: Check if any active legal hold covers this data.
        REM: Returns True if deletion should be blocked.
        """
        for hold in self._holds.values():
            if hold.status != "active":
                continue
            if hold.tenant_id != tenant_id:
                continue
            # REM: Tenant-wide hold (matter_id=None) covers all matters
            if hold.matter_id is None:
                return True
            # REM: Matter-specific hold matches if matter_id matches or query is tenant-wide
            if matter_id is None or hold.matter_id == matter_id:
                return True
        return False

    def add_custodian(self, hold_id: str, user_id: str) -> bool:
        """REM: Add a custodian to a legal hold for notification tracking."""
        hold = self._holds.get(hold_id)
        if not hold:
            logger.warning(f"REM: Legal hold ::{hold_id}:: not found_Thank_You_But_No")
            return False

        if hold.status != "active":
            logger.warning(
                f"REM: Cannot add custodian to released hold ::{hold_id}::_Thank_You_But_No"
            )
            return False

        if user_id in hold.custodians:
            logger.info(
                f"REM: Custodian ::{user_id}:: already on hold ::{hold_id}::_Thank_You"
            )
            return True

        hold.custodians.append(user_id)

        logger.info(
            f"REM: Custodian ::{user_id}:: added to hold ::{hold.name}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Custodian added to legal hold: {hold.name}",
            actor="system",
            resource=hold_id,
            details={
                "user_id": user_id,
                "tenant_id": hold.tenant_id,
                "hold_name": hold.name
            },
            qms_status="Thank_You"
        )

        self._save_record(hold_id)

        return True

    def acknowledge_hold(self, hold_id: str, user_id: str) -> bool:
        """REM: Record a custodian's acknowledgment of a legal hold."""
        hold = self._holds.get(hold_id)
        if not hold:
            logger.warning(f"REM: Legal hold ::{hold_id}:: not found_Thank_You_But_No")
            return False

        if user_id not in hold.custodians:
            logger.warning(
                f"REM: User ::{user_id}:: is not a custodian on hold ::{hold_id}::_Thank_You_But_No"
            )
            return False

        now = datetime.now(timezone.utc)
        hold.acknowledgments[user_id] = now

        logger.info(
            f"REM: Custodian ::{user_id}:: acknowledged hold ::{hold.name}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Legal hold acknowledged: {hold.name}",
            actor=user_id,
            resource=hold_id,
            details={
                "tenant_id": hold.tenant_id,
                "hold_name": hold.name,
                "acknowledged_at": now.isoformat()
            },
            qms_status="Thank_You"
        )

        self._save_record(hold_id)

        return True

    def get_unacknowledged(self, hold_id: str) -> List[str]:
        """REM: Get custodians who have not yet acknowledged a legal hold."""
        hold = self._holds.get(hold_id)
        if not hold:
            logger.warning(f"REM: Legal hold ::{hold_id}:: not found_Thank_You_But_No")
            return []

        return [
            uid for uid in hold.custodians
            if uid not in hold.acknowledgments
        ]

    def _load_from_redis(self):
        """REM: Load legal hold records from Redis on startup."""
        try:
            from core.persistence import compliance_store
            all_data = compliance_store.list_records("legal_holds")
            for record_id, record_data in all_data.items():
                self._holds[record_id] = LegalHold(
                    hold_id=record_data["hold_id"],
                    tenant_id=record_data["tenant_id"],
                    matter_id=record_data.get("matter_id"),
                    name=record_data["name"],
                    reason=record_data["reason"],
                    scope=record_data["scope"],
                    status=record_data["status"],
                    created_at=datetime.fromisoformat(record_data["created_at"]),
                    created_by=record_data["created_by"],
                    released_at=datetime.fromisoformat(record_data["released_at"]) if record_data.get("released_at") else None,
                    released_by=record_data.get("released_by"),
                    custodians=record_data.get("custodians", []),
                    acknowledgments={
                        uid: datetime.fromisoformat(ts)
                        for uid, ts in record_data.get("acknowledgments", {}).items()
                    }
                )
            if self._holds:
                logger.info(f"REM: Loaded {len(self._holds)} legal holds from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Could not load legal holds from Redis: {e}_Excuse_Me")

    def _save_record(self, record_id: str):
        """REM: Persist a single legal hold record to Redis."""
        try:
            from core.persistence import compliance_store
            record = self._holds.get(record_id)
            if record:
                data = record.to_dict()
                compliance_store.store_record("legal_holds", record_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save legal hold to Redis: {e}_Excuse_Me")
