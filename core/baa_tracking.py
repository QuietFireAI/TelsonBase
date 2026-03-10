# TelsonBase/core/baa_tracking.py
# REM: =======================================================================================
# REM: HIPAA BUSINESS ASSOCIATE AGREEMENT TRACKING
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.3.0CC: HIPAA 45 CFR 164.308(b)(1) — Business Associate Contracts
#
# REM: Mission Statement: Business Associate Agreement lifecycle management for HIPAA
# REM: compliance. The Security Rule requires covered entities to obtain satisfactory
# REM: assurances from business associates that they will appropriately safeguard ePHI.
# REM: This module tracks BAA registration, activation, review, expiration, and
# REM: termination with full audit trail.
#
# REM: Features:
# REM:   - BAA status lifecycle (DRAFT -> ACTIVE -> EXPIRED/TERMINATED)
# REM:   - Business associate registration with PHI access level tracking
# REM:   - BAA activation, review, and termination workflows
# REM:   - Expiring BAA detection with configurable lookahead
# REM:   - Status-filtered listing
# REM:   - QMS-formatted logging throughout
# REM: =======================================================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


class BAAStatus(str, Enum):
    """REM: Lifecycle status of a Business Associate Agreement."""
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    UNDER_REVIEW = "under_review"


@dataclass
class BusinessAssociate:
    """REM: A business associate entity with BAA lifecycle tracking."""
    ba_id: str
    name: str
    contact_email: str
    services_provided: List[str]
    phi_access_level: str
    baa_status: BAAStatus
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    last_reviewed: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "ba_id": self.ba_id,
            "name": self.name,
            "contact_email": self.contact_email,
            "services_provided": self.services_provided,
            "phi_access_level": self.phi_access_level,
            "baa_status": self.baa_status.value,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
            "last_reviewed": self.last_reviewed.isoformat() if self.last_reviewed else None,
            "reviewed_by": self.reviewed_by,
            "notes": self.notes
        }


class BAAManager:
    """
    REM: Manages Business Associate Agreements for HIPAA 45 CFR 164.308(b)(1).
    REM: All BAA state changes are audit-logged for regulatory evidence.
    """

    def __init__(self):
        # REM: In-memory storage for business associate records
        self._associates: Dict[str, BusinessAssociate] = {}

        # REM: Load persisted records from Redis
        self._load_from_redis()

        logger.info("REM: BAAManager initialized_Thank_You")

    def register_ba(
        self,
        name: str,
        email: str,
        services: List[str],
        phi_access_level: str
    ) -> BusinessAssociate:
        """REM: Register a new business associate in DRAFT status."""
        ba_id = f"ba_{uuid.uuid4().hex[:12]}"

        ba = BusinessAssociate(
            ba_id=ba_id,
            name=name,
            contact_email=email,
            services_provided=services,
            phi_access_level=phi_access_level,
            baa_status=BAAStatus.DRAFT
        )

        self._associates[ba_id] = ba

        logger.info(
            f"REM: Business associate registered - ::{ba_id}:: "
            f"name ::{name}:: PHI level ::{phi_access_level}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Business associate registered: {name}",
            actor="system",
            resource=ba_id,
            details={
                "name": name,
                "contact_email": email,
                "services_provided": services,
                "phi_access_level": phi_access_level,
                "baa_status": BAAStatus.DRAFT.value
            },
            qms_status="Thank_You"
        )

        self._save_record(ba_id)

        return ba

    def activate_baa(
        self,
        ba_id: str,
        effective_date: datetime,
        expiration_date: datetime,
        reviewed_by: str
    ) -> bool:
        """REM: Activate a BAA with effective and expiration dates."""
        ba = self._associates.get(ba_id)
        if not ba:
            logger.warning(f"REM: Business associate ::{ba_id}:: not found_Thank_You_But_No")
            return False

        old_status = ba.baa_status
        ba.baa_status = BAAStatus.ACTIVE
        ba.effective_date = effective_date
        ba.expiration_date = expiration_date
        ba.last_reviewed = datetime.now(timezone.utc)
        ba.reviewed_by = reviewed_by

        logger.info(
            f"REM: BAA activated - ::{ba_id}:: ::{ba.name}:: "
            f"::{old_status.value}:: -> ::active:: by ::{reviewed_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"BAA activated: {ba.name} by {reviewed_by}",
            actor=reviewed_by,
            resource=ba_id,
            details={
                "name": ba.name,
                "old_status": old_status.value,
                "new_status": BAAStatus.ACTIVE.value,
                "effective_date": effective_date.isoformat(),
                "expiration_date": expiration_date.isoformat()
            },
            qms_status="Thank_You"
        )

        self._save_record(ba_id)

        return True

    def review_baa(
        self,
        ba_id: str,
        reviewed_by: str,
        notes: str
    ) -> bool:
        """REM: Record a periodic review of a BAA."""
        ba = self._associates.get(ba_id)
        if not ba:
            logger.warning(f"REM: Business associate ::{ba_id}:: not found_Thank_You_But_No")
            return False

        now = datetime.now(timezone.utc)
        ba.last_reviewed = now
        ba.reviewed_by = reviewed_by
        ba.notes = notes
        ba.baa_status = BAAStatus.UNDER_REVIEW

        logger.info(
            f"REM: BAA reviewed - ::{ba_id}:: ::{ba.name}:: "
            f"by ::{reviewed_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"BAA reviewed: {ba.name} by {reviewed_by}",
            actor=reviewed_by,
            resource=ba_id,
            details={
                "name": ba.name,
                "reviewed_at": now.isoformat(),
                "notes": notes
            },
            qms_status="Thank_You"
        )

        self._save_record(ba_id)

        return True

    def terminate_baa(
        self,
        ba_id: str,
        terminated_by: str,
        reason: str
    ) -> bool:
        """REM: Terminate a BAA with reason documentation."""
        ba = self._associates.get(ba_id)
        if not ba:
            logger.warning(f"REM: Business associate ::{ba_id}:: not found_Thank_You_But_No")
            return False

        old_status = ba.baa_status
        ba.baa_status = BAAStatus.TERMINATED
        ba.notes = f"Terminated: {reason}"

        logger.info(
            f"REM: BAA terminated - ::{ba_id}:: ::{ba.name}:: "
            f"::{old_status.value}:: -> ::terminated:: by ::{terminated_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"BAA terminated: {ba.name} by {terminated_by}",
            actor=terminated_by,
            resource=ba_id,
            details={
                "name": ba.name,
                "old_status": old_status.value,
                "new_status": BAAStatus.TERMINATED.value,
                "reason": reason
            },
            qms_status="Thank_You"
        )

        self._save_record(ba_id)

        return True

    def get_expiring_baas(self, within_days: int = 90) -> List[BusinessAssociate]:
        """REM: Find BAAs that will expire within the specified number of days."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=within_days)
        expiring: List[BusinessAssociate] = []

        for ba in self._associates.values():
            if ba.baa_status != BAAStatus.ACTIVE:
                continue
            if ba.expiration_date and ba.expiration_date <= cutoff:
                expiring.append(ba)

        return expiring

    def get_all_baas(self, status_filter: Optional[BAAStatus] = None) -> List[BusinessAssociate]:
        """REM: List all business associates, optionally filtered by BAA status."""
        results = list(self._associates.values())
        if status_filter is not None:
            results = [ba for ba in results if ba.baa_status == status_filter]
        return results

    def is_baa_active(self, ba_id: str) -> bool:
        """REM: Check whether a specific BAA is currently active."""
        ba = self._associates.get(ba_id)
        if not ba:
            return False
        return ba.baa_status == BAAStatus.ACTIVE

    def _load_from_redis(self):
        """REM: Load business associate records from Redis on startup."""
        try:
            from core.persistence import compliance_store
            all_data = compliance_store.list_records("baas")
            for record_id, record_data in all_data.items():
                self._associates[record_id] = BusinessAssociate(
                    ba_id=record_data["ba_id"],
                    name=record_data["name"],
                    contact_email=record_data["contact_email"],
                    services_provided=record_data["services_provided"],
                    phi_access_level=record_data["phi_access_level"],
                    baa_status=BAAStatus(record_data["baa_status"]),
                    effective_date=datetime.fromisoformat(record_data["effective_date"]) if record_data.get("effective_date") else None,
                    expiration_date=datetime.fromisoformat(record_data["expiration_date"]) if record_data.get("expiration_date") else None,
                    last_reviewed=datetime.fromisoformat(record_data["last_reviewed"]) if record_data.get("last_reviewed") else None,
                    reviewed_by=record_data.get("reviewed_by"),
                    notes=record_data.get("notes")
                )
            if self._associates:
                logger.info(f"REM: Loaded {len(self._associates)} business associates from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Could not load BAA data from Redis: {e}_Excuse_Me")

    def _save_record(self, record_id: str):
        """REM: Persist a single business associate record to Redis."""
        try:
            from core.persistence import compliance_store
            record = self._associates.get(record_id)
            if record:
                data = record.to_dict()
                compliance_store.store_record("baas", record_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save BAA record to Redis: {e}_Excuse_Me")


# REM: Module-level singleton for import convenience
baa_manager = BAAManager()
