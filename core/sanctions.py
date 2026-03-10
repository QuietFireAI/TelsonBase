# TelsonBase/core/sanctions.py
# REM: =======================================================================================
# REM: HIPAA SANCTIONS POLICY TRACKING
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.3.0CC: HIPAA 45 CFR 164.308(a)(1)(ii)(C) — Sanctions Policy
#
# REM: Mission Statement: Workforce sanctions tracking for HIPAA compliance. The Security
# REM: Rule requires covered entities to apply appropriate sanctions against workforce
# REM: members who fail to comply with security policies and procedures. This module
# REM: provides structured sanction imposition, resolution, and full audit trail.
#
# REM: Features:
# REM:   - Sanction severity classification (WARNING through REFERRAL)
# REM:   - Sanction imposition with mandatory audit logging
# REM:   - Sanction resolution workflow with notes
# REM:   - Active sanction queries per user or system-wide
# REM:   - QMS-formatted logging throughout
# REM: =======================================================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


class SanctionSeverity(str, Enum):
    """REM: Classification of sanction severity per HIPAA workforce policy."""
    WARNING = "warning"
    REPRIMAND = "reprimand"
    SUSPENSION = "suspension"
    TERMINATION = "termination"
    REFERRAL = "referral"


@dataclass
class SanctionRecord:
    """REM: A single sanction imposed against a workforce member."""
    sanction_id: str
    user_id: str
    violation_description: str
    severity: SanctionSeverity
    imposed_by: str
    imposed_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "sanction_id": self.sanction_id,
            "user_id": self.user_id,
            "violation_description": self.violation_description,
            "severity": self.severity.value,
            "imposed_by": self.imposed_by,
            "imposed_at": self.imposed_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes,
            "is_active": self.is_active
        }


class SanctionsManager:
    """
    REM: Manages workforce sanctions for HIPAA 45 CFR 164.308(a)(1)(ii)(C).
    REM: All mutations are audit-logged for regulatory evidence.
    """

    def __init__(self):
        # REM: In-memory storage for sanction records
        self._sanctions: Dict[str, SanctionRecord] = {}

        # REM: Load persisted records from Redis
        self._load_from_redis()

        logger.info("REM: SanctionsManager initialized_Thank_You")

    def impose_sanction(
        self,
        user_id: str,
        violation: str,
        severity,
        imposed_by: str
    ) -> SanctionRecord:
        """REM: Impose a new sanction against a workforce member."""
        # REM: v7.2.0CC: Accept both SanctionSeverity enum and raw string
        if isinstance(severity, str) and not isinstance(severity, SanctionSeverity):
            severity = SanctionSeverity(severity)
        sanction_id = f"sanc_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        record = SanctionRecord(
            sanction_id=sanction_id,
            user_id=user_id,
            violation_description=violation,
            severity=severity,
            imposed_by=imposed_by,
            imposed_at=now,
            is_active=True
        )

        self._sanctions[sanction_id] = record

        logger.info(
            f"REM: Sanction imposed - ::{sanction_id}:: "
            f"user ::{user_id}:: severity ::{severity.value}:: by ::{imposed_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Sanction imposed: {severity.value} against {user_id}",
            actor=imposed_by,
            resource=sanction_id,
            details={
                "user_id": user_id,
                "violation": violation,
                "severity": severity.value,
                "imposed_at": now.isoformat()
            },
            qms_status="Thank_You"
        )

        self._save_record(sanction_id)

        return record

    def resolve_sanction(
        self,
        sanction_id: str,
        resolved_by: str,
        notes: str
    ) -> bool:
        """REM: Resolve an active sanction with resolution notes."""
        record = self._sanctions.get(sanction_id)
        if not record:
            logger.warning(f"REM: Sanction ::{sanction_id}:: not found_Thank_You_But_No")
            return False

        if not record.is_active:
            logger.warning(f"REM: Sanction ::{sanction_id}:: already resolved_Thank_You_But_No")
            return False

        now = datetime.now(timezone.utc)
        record.resolved_at = now
        record.resolution_notes = notes
        record.is_active = False

        logger.info(
            f"REM: Sanction ::{sanction_id}:: resolved "
            f"by ::{resolved_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Sanction resolved: {sanction_id} for user {record.user_id}",
            actor=resolved_by,
            resource=sanction_id,
            details={
                "user_id": record.user_id,
                "severity": record.severity.value,
                "resolution_notes": notes,
                "resolved_at": now.isoformat()
            },
            qms_status="Thank_You"
        )

        self._save_record(sanction_id)

        return True

    def get_user_sanctions(self, user_id: str) -> List[SanctionRecord]:
        """REM: Get all sanctions for a specific user."""
        return [s for s in self._sanctions.values() if s.user_id == user_id]

    def get_active_sanctions(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """REM: Get active sanctions, optionally filtered by user. Returns dict for route unpacking."""
        if user_id:
            sanctions = [s for s in self._sanctions.values() if s.is_active and s.user_id == user_id]
        else:
            sanctions = [s for s in self._sanctions.values() if s.is_active]
        return {
            "has_active": len(sanctions) > 0,
            "sanctions": [s.to_dict() for s in sanctions]
        }

    def list_sanctions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """REM: v7.2.0CC: List sanctions with optional user filter. Returns dicts for JSON serialization."""
        if user_id:
            sanctions = [s for s in self._sanctions.values() if s.user_id == user_id]
        else:
            sanctions = list(self._sanctions.values())
        return [s.to_dict() for s in sanctions]

    def has_active_sanctions(self, user_id: str) -> bool:
        """REM: Check whether a user has any active sanctions."""
        return any(
            s.is_active for s in self._sanctions.values()
            if s.user_id == user_id
        )

    def _load_from_redis(self):
        """REM: Load sanction records from Redis on startup."""
        try:
            from core.persistence import compliance_store
            all_data = compliance_store.list_records("sanctions")
            for record_id, record_data in all_data.items():
                self._sanctions[record_id] = SanctionRecord(
                    sanction_id=record_data["sanction_id"],
                    user_id=record_data["user_id"],
                    violation_description=record_data["violation_description"],
                    severity=SanctionSeverity(record_data["severity"]),
                    imposed_by=record_data["imposed_by"],
                    imposed_at=datetime.fromisoformat(record_data["imposed_at"]),
                    resolved_at=datetime.fromisoformat(record_data["resolved_at"]) if record_data.get("resolved_at") else None,
                    resolution_notes=record_data.get("resolution_notes"),
                    is_active=record_data.get("is_active", True)
                )
            if self._sanctions:
                logger.info(f"REM: Loaded {len(self._sanctions)} sanctions from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Could not load sanctions from Redis: {e}_Excuse_Me")

    def _save_record(self, record_id: str):
        """REM: Persist a single sanction record to Redis."""
        try:
            from core.persistence import compliance_store
            record = self._sanctions.get(record_id)
            if record:
                data = record.to_dict()
                compliance_store.store_record("sanctions", record_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save sanction to Redis: {e}_Excuse_Me")


# REM: Module-level singleton for import convenience
sanctions_manager = SanctionsManager()
