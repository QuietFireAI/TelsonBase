# TelsonBase/core/phi_disclosure.py
# REM: =======================================================================================
# REM: HIPAA ACCOUNTING OF PHI DISCLOSURES
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: HIPAA 45 CFR 164.528 requires covered entities to maintain an
# REM: accounting of disclosures of protected health information (PHI) for each individual.
# REM: Patients have the right to request this accounting for disclosures made in the
# REM: six years prior to the request. This module provides structured tracking of all
# REM: PHI disclosures with full audit trail for compliance evidence.
#
# REM: Features:
# REM:   - Structured PHI disclosure recording with all required HIPAA fields
# REM:   - Six-year retention window per 45 CFR 164.528(a)
# REM:   - Date-range filtering for patient disclosure queries
# REM:   - Accounting report generation for patient right-of-access requests
# REM:   - Full audit trail via cryptographic hash-chained audit log
# REM:   - QMS-formatted logging throughout
#
# REM: v6.3.0CC: Initial implementation for HIPAA healthcare compliance infrastructure
# REM: =======================================================================================

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


# REM: HIPAA requires a 6-year retention window for disclosure accounting
HIPAA_RETENTION_YEARS = 6


@dataclass
class PHIDisclosureRecord:
    """
    REM: A single record of PHI disclosure per 45 CFR 164.528.
    REM: Each disclosure must capture who received PHI, why, and what was disclosed.
    """
    disclosure_id: str
    patient_id: str
    recipient: str
    purpose: str
    phi_description: str
    date_of_disclosure: datetime
    recorded_by: str

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "disclosure_id": self.disclosure_id,
            "patient_id": self.patient_id,
            "recipient": self.recipient,
            "purpose": self.purpose,
            "phi_description": self.phi_description,
            "date_of_disclosure": self.date_of_disclosure.isoformat(),
            "recorded_by": self.recorded_by
        }


class PHIDisclosureManager:
    """
    REM: Manages the accounting of PHI disclosures per HIPAA 45 CFR 164.528.
    REM: Maintains an in-memory store keyed by patient_id for efficient retrieval.
    REM: All mutations are audit-logged for regulatory evidence.
    """

    def __init__(self):
        # REM: In-memory storage — Dict[patient_id, List[PHIDisclosureRecord]]
        self._disclosures: Dict[str, List[PHIDisclosureRecord]] = {}
        self._load_from_redis()

        logger.info("REM: PHIDisclosureManager initialized_Thank_You")

    def _load_from_redis(self) -> None:
        """REM: Load PHI disclosure records from Redis on startup. Reconstructs per-patient lists."""
        try:
            from core.persistence import compliance_store
            all_records = compliance_store.list_records("phi_disclosures")
            for disclosure_id, record_data in all_records.items():
                try:
                    rec = PHIDisclosureRecord(
                        disclosure_id=record_data["disclosure_id"],
                        patient_id=record_data["patient_id"],
                        recipient=record_data["recipient"],
                        purpose=record_data["purpose"],
                        phi_description=record_data["phi_description"],
                        date_of_disclosure=datetime.fromisoformat(record_data["date_of_disclosure"]),
                        recorded_by=record_data["recorded_by"],
                    )
                    patient_id = rec.patient_id
                    if patient_id not in self._disclosures:
                        self._disclosures[patient_id] = []
                    self._disclosures[patient_id].append(rec)
                except Exception as e:
                    logger.warning(
                        f"REM: Failed to load PHI disclosure ::{disclosure_id}:: from Redis: {e}_Thank_You_But_No"
                    )
            if all_records:
                total = sum(len(v) for v in self._disclosures.values())
                logger.info(f"REM: Loaded {total} PHI disclosure records from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Redis unavailable for PHI disclosure load: {e}_Thank_You_But_No")

    def _save_record(self, disclosure_id: str, patient_id: str) -> None:
        """REM: Write-through save of a single PHI disclosure record to Redis."""
        try:
            from core.persistence import compliance_store
            # REM: Find the record by disclosure_id in the patient's list
            records = self._disclosures.get(patient_id, [])
            record = None
            for r in records:
                if r.disclosure_id == disclosure_id:
                    record = r
                    break
            if not record:
                return
            data = record.to_dict()
            # REM: Add patient_id to data for reconstruction on load
            data["patient_id"] = patient_id
            compliance_store.store_record("phi_disclosures", disclosure_id, data)
        except Exception as e:
            logger.warning(f"REM: Failed to save PHI disclosure to Redis for ::{disclosure_id}::: {e}_Thank_You_But_No")

    def record_disclosure(
        self,
        patient_id: str,
        recipient: str,
        purpose: str,
        phi_description: str,
        recorded_by: str,
        date_of_disclosure: Optional[datetime] = None
    ) -> PHIDisclosureRecord:
        """
        REM: Record a new PHI disclosure event.
        REM: Per 45 CFR 164.528, each disclosure must be tracked with recipient,
        REM: purpose, description of PHI disclosed, and date.
        """
        disclosure_id = f"phi_disc_{uuid.uuid4().hex[:12]}"
        now = date_of_disclosure or datetime.now(timezone.utc)

        record = PHIDisclosureRecord(
            disclosure_id=disclosure_id,
            patient_id=patient_id,
            recipient=recipient,
            purpose=purpose,
            phi_description=phi_description,
            date_of_disclosure=now,
            recorded_by=recorded_by
        )

        # REM: Store under patient_id for efficient lookup
        if patient_id not in self._disclosures:
            self._disclosures[patient_id] = []
        self._disclosures[patient_id].append(record)
        self._save_record(disclosure_id, patient_id)

        logger.info(
            f"REM: PHI disclosure recorded - ::{disclosure_id}:: "
            f"patient ::{patient_id}:: to ::{recipient}:: "
            f"purpose ::{purpose}:: by ::{recorded_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"PHI disclosure recorded: {patient_id} to {recipient}",
            actor=recorded_by,
            resource=disclosure_id,
            details={
                "patient_id": patient_id,
                "recipient": recipient,
                "purpose": purpose,
                "phi_description": phi_description,
                "date_of_disclosure": now.isoformat()
            },
            qms_status="Thank_You"
        )

        return record

    def get_disclosures_for_patient(
        self,
        patient_id: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[PHIDisclosureRecord]:
        """
        REM: Retrieve disclosures for a specific patient within the HIPAA retention window.
        REM: Optionally filter by date range. Per 45 CFR 164.528(a), the accounting
        REM: must cover disclosures made in the six years prior to the request.
        """
        records = self._disclosures.get(patient_id, [])

        # REM: Apply the 6-year HIPAA retention window as the outer boundary
        now = datetime.now(timezone.utc)
        retention_boundary = now - timedelta(days=HIPAA_RETENTION_YEARS * 365)

        # REM: Use from_date if provided, but never go beyond the retention window
        effective_from = from_date if from_date and from_date > retention_boundary else retention_boundary
        effective_to = to_date if to_date else now

        filtered = [
            r for r in records
            if effective_from <= r.date_of_disclosure <= effective_to
        ]

        logger.info(
            f"REM: Retrieved {len(filtered)} disclosures for patient ::{patient_id}:: "
            f"from ::{effective_from.isoformat()}:: to ::{effective_to.isoformat()}::_Thank_You"
        )

        return filtered

    def generate_accounting_report(self, patient_id: str) -> Dict[str, Any]:
        """
        REM: Generate a full accounting of disclosures report for a patient.
        REM: This is the formal response to a patient's 45 CFR 164.528 request.
        REM: Covers the full 6-year HIPAA retention window.
        """
        now = datetime.now(timezone.utc)
        retention_boundary = now - timedelta(days=HIPAA_RETENTION_YEARS * 365)

        disclosures = self.get_disclosures_for_patient(patient_id)

        report = {
            "report_id": f"phi_rpt_{uuid.uuid4().hex[:12]}",
            "patient_id": patient_id,
            "generated_at": now.isoformat(),
            "retention_window_start": retention_boundary.isoformat(),
            "retention_window_end": now.isoformat(),
            "total_disclosures": len(disclosures),
            "disclosures": [d.to_dict() for d in disclosures],
            "hipaa_reference": "45 CFR 164.528 — Accounting of Disclosures of PHI",
            "retention_years": HIPAA_RETENTION_YEARS
        }

        logger.info(
            f"REM: Accounting report generated for patient ::{patient_id}:: "
            f"— {len(disclosures)} disclosures in retention window_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"PHI accounting report generated for patient: {patient_id}",
            actor="system",
            resource=report["report_id"],
            details={
                "patient_id": patient_id,
                "total_disclosures": len(disclosures),
                "retention_window_start": retention_boundary.isoformat()
            },
            qms_status="Thank_You"
        )

        return report

    def get_accounting_report(self, patient_id: str) -> Dict[str, Any]:
        """REM: v7.2.0CC: Alias for generate_accounting_report — routes use this name."""
        return self.generate_accounting_report(patient_id)

    def get_disclosure_count(self) -> Dict[str, Any]:
        """
        REM: Get summary counts of all PHI disclosures in the system.
        REM: Useful for compliance dashboards and monitoring.
        """
        now = datetime.now(timezone.utc)
        retention_boundary = now - timedelta(days=HIPAA_RETENTION_YEARS * 365)

        total_disclosures = 0
        total_patients = len(self._disclosures)
        within_retention = 0

        for patient_id, records in self._disclosures.items():
            total_disclosures += len(records)
            within_retention += len([
                r for r in records
                if r.date_of_disclosure >= retention_boundary
            ])

        return {
            "total_patients_with_disclosures": total_patients,
            "total_disclosure_records": total_disclosures,
            "within_retention_window": within_retention,
            "retention_window_years": HIPAA_RETENTION_YEARS,
            "as_of": now.isoformat()
        }

    def get_disclosure(self, disclosure_id: str) -> Optional[PHIDisclosureRecord]:
        """REM: Look up a specific disclosure record by ID."""
        for records in self._disclosures.values():
            for record in records:
                if record.disclosure_id == disclosure_id:
                    return record
        return None


# REM: Global instance for import throughout the application
phi_disclosure_manager = PHIDisclosureManager()
