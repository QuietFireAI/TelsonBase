# TelsonBase/core/hitrust_controls.py
# REM: =======================================================================================
# REM: HITRUST CSF COMPLIANCE TRACKING
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.3.0CC: New feature - HITRUST CSF control tracking and risk assessment
#
# REM: Mission Statement: Track HITRUST Common Security Framework controls and their
# REM: implementation status across the TelsonBase platform. Provides compliance posture
# REM: reporting, risk assessment records, and evidence mapping for HITRUST certification
# REM: readiness.
#
# REM: Features:
# REM:   - HITRUST CSF domain and control registry
# REM:   - Control status lifecycle tracking
# REM:   - Risk assessment recording with mitigation plans
# REM:   - Compliance posture percentage by domain
# REM:   - Baseline controls pre-registered from existing TelsonBase features
# REM:   - Full audit trail of status changes and assessments
# REM: =======================================================================================

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


class HITRUSTDomain(str, Enum):
    """
    REM: HITRUST CSF control domains. Each domain represents a category
    REM: of security controls within the HITRUST Common Security Framework.
    """
    ACCESS_CONTROL = "access_control"
    AUDIT_LOGGING = "audit_logging"
    RISK_MANAGEMENT = "risk_management"
    VULNERABILITY_MANAGEMENT = "vulnerability_management"
    INCIDENT_MANAGEMENT = "incident_management"
    MEDIA_HANDLING = "media_handling"
    INFORMATION_EXCHANGE = "information_exchange"
    ASSET_MANAGEMENT = "asset_management"
    PHYSICAL_SECURITY = "physical_security"
    NETWORK_SECURITY = "network_security"
    ENCRYPTION = "encryption"
    BUSINESS_CONTINUITY = "business_continuity"


class ControlStatus(str, Enum):
    """
    REM: Lifecycle status of a HITRUST control implementation.
    REM: Tracks from initial registration through validation.
    """
    NOT_IMPLEMENTED = "not_implemented"
    PARTIAL = "partial"
    IMPLEMENTED = "implemented"
    VALIDATED = "validated"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class HITRUSTControl:
    """
    REM: A single HITRUST CSF control with implementation tracking.
    REM: Each control maps to a specific domain and tracks assessment history.
    """
    control_id: str  # e.g., "01.a", "09.ab"
    domain: HITRUSTDomain
    title: str
    description: str
    status: ControlStatus = ControlStatus.NOT_IMPLEMENTED
    evidence_references: List[str] = field(default_factory=list)
    last_assessed: Optional[datetime] = None
    assessed_by: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """REM: v7.2.0CC: Convert to dictionary for JSON serialization."""
        return {
            "control_id": self.control_id,
            "domain": self.domain.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "evidence_references": self.evidence_references,
            "last_assessed": self.last_assessed.isoformat() if self.last_assessed else None,
            "assessed_by": self.assessed_by,
            "notes": self.notes,
        }


@dataclass
class RiskAssessment:
    """
    REM: A formal risk assessment record with findings and mitigation plan.
    REM: Required for HITRUST certification and ongoing compliance.
    """
    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    scope: str = ""
    conducted_by: str = ""
    conducted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    findings: List[Dict[str, Any]] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high, critical
    mitigation_plan: str = ""
    next_review: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=90))

    def to_dict(self) -> Dict[str, Any]:
        """REM: v7.2.0CC: Convert to dictionary for JSON serialization."""
        return {
            "assessment_id": self.assessment_id,
            "title": self.title,
            "scope": self.scope,
            "conducted_by": self.conducted_by,
            "conducted_at": self.conducted_at.isoformat(),
            "findings": self.findings,
            "risk_level": self.risk_level,
            "mitigation_plan": self.mitigation_plan,
            "next_review": self.next_review.isoformat(),
        }


class HITRUSTManager:
    """
    REM: Manages HITRUST CSF control registration, status tracking, and
    REM: risk assessments. Provides compliance posture reporting and
    REM: evidence mapping for audit readiness.
    """

    def __init__(self):
        self._controls: Dict[str, HITRUSTControl] = {}
        self._risk_assessments: List[RiskAssessment] = []
        self._register_baseline_controls()

        # REM: Load persisted records from Redis (overrides baseline with saved state)
        self._load_from_redis()

        # REM: Save baseline controls that weren't already in Redis
        self._save_all_controls()

        logger.info("REM: HITRUSTManager initialized with %d baseline controls_Thank_You",
                     len(self._controls))

    def _register_baseline_controls(self):
        """
        REM: Pre-register baseline controls that map to existing TelsonBase features.
        REM: These represent controls already partially or fully addressed by the platform.
        """
        baseline = [
            ("01.a", HITRUSTDomain.ACCESS_CONTROL,
             "Access Control Policy",
             "Policy for role-based access control enforcement (maps to core.rbac)"),
            ("01.b", HITRUSTDomain.ACCESS_CONTROL,
             "User Registration and De-registration",
             "Formal user registration and removal process (maps to core.auth)"),
            ("01.c", HITRUSTDomain.ACCESS_CONTROL,
             "Privilege Management",
             "Restriction and control of privilege allocation (maps to core.capabilities)"),
            ("09.aa", HITRUSTDomain.AUDIT_LOGGING,
             "Audit Logging",
             "Cryptographic hash-chained audit trail (maps to core.audit)"),
            ("09.ab", HITRUSTDomain.AUDIT_LOGGING,
             "Monitoring System Use",
             "Anomaly detection and behavioral monitoring (maps to core.anomaly)"),
            ("06.a", HITRUSTDomain.ENCRYPTION,
             "Encryption of Sensitive Data",
             "AES-256-GCM encryption at rest (maps to core.secure_storage)"),
            ("06.b", HITRUSTDomain.ENCRYPTION,
             "Key Management",
             "Encryption key derivation and rotation (maps to core.rotation)"),
            ("03.a", HITRUSTDomain.RISK_MANAGEMENT,
             "Risk Assessment Process",
             "Formal risk assessment and mitigation tracking"),
            ("11.a", HITRUSTDomain.INCIDENT_MANAGEMENT,
             "Incident Response Planning",
             "Security incident detection and response (maps to core.threat_response)"),
            ("11.b", HITRUSTDomain.INCIDENT_MANAGEMENT,
             "Breach Notification",
             "HIPAA breach notification procedures (maps to core.breach_notification)"),
            ("10.a", HITRUSTDomain.NETWORK_SECURITY,
             "Network Controls",
             "Network segmentation and traffic controls (maps to core.middleware)"),
            ("05.a", HITRUSTDomain.VULNERABILITY_MANAGEMENT,
             "Vulnerability Scanning",
             "Regular vulnerability assessment and remediation"),
            ("08.a", HITRUSTDomain.MEDIA_HANDLING,
             "Media Protection",
             "Data classification and handling policies (maps to core.data_classification)"),
            ("07.a", HITRUSTDomain.INFORMATION_EXCHANGE,
             "Information Exchange Policies",
             "Controlled external communication (maps to core.phi_disclosure)"),
            ("04.a", HITRUSTDomain.ASSET_MANAGEMENT,
             "Asset Inventory",
             "System and data asset inventory management"),
            ("02.a", HITRUSTDomain.PHYSICAL_SECURITY,
             "Physical Security Perimeter",
             "Physical access controls for hosting infrastructure"),
            ("12.a", HITRUSTDomain.BUSINESS_CONTINUITY,
             "Business Continuity Planning",
             "Backup and disaster recovery procedures"),
        ]

        for control_id, domain, title, description in baseline:
            self._controls[control_id] = HITRUSTControl(
                control_id=control_id,
                domain=domain,
                title=title,
                description=description,
                status=ControlStatus.PARTIAL,
                notes="Baseline control - mapped to existing TelsonBase feature"
            )

    def register_control(
        self,
        control_id: str,
        domain: HITRUSTDomain,
        title: str,
        description: str
    ) -> HITRUSTControl:
        """
        REM: Register a new HITRUST control for tracking.

        Args:
            control_id: HITRUST control identifier (e.g., "01.a")
            domain: HITRUST domain classification
            title: Human-readable control title
            description: Detailed control description

        Returns:
            The registered HITRUSTControl
        """
        control = HITRUSTControl(
            control_id=control_id,
            domain=domain,
            title=title,
            description=description
        )
        self._controls[control_id] = control

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"HITRUST control registered: ::{control_id}:: - ::{title}::",
            actor="system",
            resource=control_id,
            details={"domain": domain.value, "title": title},
            qms_status="Thank_You"
        )
        logger.info("REM: Registered HITRUST control ::%s:: - ::%s::_Thank_You",
                     control_id, title)

        self._save_control(control_id)

        return control

    def update_control_status(
        self,
        control_id: str,
        status: ControlStatus,
        evidence: Optional[List[str]] = None,
        assessed_by: str = "system"
    ) -> bool:
        """
        REM: Update the implementation status of a tracked control.

        Args:
            control_id: HITRUST control identifier
            status: New control status
            evidence: Optional list of evidence references (document IDs, URLs)
            assessed_by: Identifier of the assessor

        Returns:
            True if control was found and updated, False otherwise
        """
        control = self._controls.get(control_id)
        if not control:
            logger.warning("REM: Control ::%s:: not found for status update_Thank_You_But_No",
                           control_id)
            return False

        old_status = control.status
        control.status = status
        control.last_assessed = datetime.now(timezone.utc)
        control.assessed_by = assessed_by

        if evidence:
            control.evidence_references.extend(evidence)

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"HITRUST control ::{control_id}:: status changed: ::{old_status.value}:: -> ::{status.value}::",
            actor=assessed_by,
            resource=control_id,
            details={
                "old_status": old_status.value,
                "new_status": status.value,
                "evidence_count": len(evidence) if evidence else 0
            },
            qms_status="Thank_You"
        )
        logger.info("REM: Control ::%s:: updated to ::%s:: by ::%s::_Thank_You",
                     control_id, status.value, assessed_by)

        self._save_control(control_id)

        return True

    def record_risk_assessment(
        self,
        title: str,
        scope: str,
        conducted_by: str,
        findings: List[Dict[str, Any]],
        risk_level: str,
        mitigation: str,
        next_review: Optional[datetime] = None
    ) -> RiskAssessment:
        """
        REM: Record a formal risk assessment with findings and mitigation plan.

        Args:
            title: Assessment title
            scope: Scope of the assessment
            conducted_by: Assessor identifier
            findings: List of finding dictionaries
            risk_level: Overall risk level (low, medium, high, critical)
            mitigation: Mitigation plan description
            next_review: Optional next review date (defaults to 90 days)

        Returns:
            The recorded RiskAssessment
        """
        assessment = RiskAssessment(
            title=title,
            scope=scope,
            conducted_by=conducted_by,
            findings=findings,
            risk_level=risk_level,
            mitigation_plan=mitigation,
            next_review=next_review or (datetime.now(timezone.utc) + timedelta(days=90))
        )
        self._risk_assessments.append(assessment)

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Risk assessment recorded: ::{title}:: - Level: ::{risk_level}::",
            actor=conducted_by,
            resource=assessment.assessment_id,
            details={
                "scope": scope,
                "risk_level": risk_level,
                "findings_count": len(findings),
                "next_review": assessment.next_review.isoformat()
            },
            qms_status="Thank_You"
        )
        logger.info("REM: Risk assessment ::%s:: recorded by ::%s:: - level ::%s::_Thank_You",
                     assessment.assessment_id, conducted_by, risk_level)

        self._save_risk_assessment(assessment.assessment_id)

        return assessment

    def get_compliance_posture(self) -> Dict[str, Any]:
        """
        REM: Calculate compliance posture as implementation percentage by domain.

        Returns:
            Dict with per-domain percentages and overall compliance score
        """
        domain_counts: Dict[str, Dict[str, int]] = {}

        for control in self._controls.values():
            domain_key = control.domain.value
            if domain_key not in domain_counts:
                domain_counts[domain_key] = {"total": 0, "compliant": 0}

            domain_counts[domain_key]["total"] += 1

            if control.status in (ControlStatus.IMPLEMENTED, ControlStatus.VALIDATED,
                                  ControlStatus.NOT_APPLICABLE):
                domain_counts[domain_key]["compliant"] += 1

        posture: Dict[str, Any] = {}
        total_all = 0
        compliant_all = 0

        for domain_key, counts in domain_counts.items():
            total = counts["total"]
            compliant = counts["compliant"]
            total_all += total
            compliant_all += compliant
            posture[domain_key] = {
                "total_controls": total,
                "compliant_controls": compliant,
                "percentage": round((compliant / total * 100) if total > 0 else 0, 1)
            }

        posture["overall"] = {
            "total_controls": total_all,
            "compliant_controls": compliant_all,
            "percentage": round((compliant_all / total_all * 100) if total_all > 0 else 0, 1)
        }

        return posture

    def get_control(self, control_id: str) -> Optional[HITRUSTControl]:
        """REM: v7.2.0CC: Get a single HITRUST control by ID."""
        return self._controls.get(control_id)

    def get_controls_by_domain(self, domain: HITRUSTDomain) -> List[HITRUSTControl]:
        """
        REM: Retrieve all controls within a specific HITRUST domain.

        Args:
            domain: HITRUST domain to filter by

        Returns:
            List of HITRUSTControl objects in the domain
        """
        return [c for c in self._controls.values() if c.domain == domain]

    def get_controls_by_status(self, status: ControlStatus) -> List[HITRUSTControl]:
        """
        REM: Retrieve all controls with a specific implementation status.

        Args:
            status: ControlStatus to filter by

        Returns:
            List of HITRUSTControl objects with the given status
        """
        return [c for c in self._controls.values() if c.status == status]

    def get_risk_assessments(self) -> List[RiskAssessment]:
        """
        REM: Retrieve all recorded risk assessments.

        Returns:
            List of RiskAssessment objects ordered by most recent first
        """
        return sorted(self._risk_assessments, key=lambda a: a.conducted_at, reverse=True)

    def _load_from_redis(self):
        """REM: Load HITRUST controls and risk assessments from Redis on startup."""
        try:
            from core.persistence import compliance_store
            # REM: Load controls (overrides baseline with persisted state)
            all_controls = compliance_store.list_records("hitrust_controls")
            for record_id, record_data in all_controls.items():
                self._controls[record_id] = HITRUSTControl(
                    control_id=record_data["control_id"],
                    domain=HITRUSTDomain(record_data["domain"]),
                    title=record_data["title"],
                    description=record_data["description"],
                    status=ControlStatus(record_data["status"]),
                    evidence_references=record_data.get("evidence_references", []),
                    last_assessed=datetime.fromisoformat(record_data["last_assessed"]) if record_data.get("last_assessed") else None,
                    assessed_by=record_data.get("assessed_by", ""),
                    notes=record_data.get("notes", "")
                )
            if all_controls:
                logger.info(f"REM: Loaded {len(all_controls)} HITRUST controls from Redis_Thank_You")

            # REM: Load risk assessments
            all_assessments = compliance_store.list_records("risk_assessments")
            loaded_ids = set()
            for record_id, record_data in all_assessments.items():
                ra = RiskAssessment(
                    assessment_id=record_data["assessment_id"],
                    title=record_data["title"],
                    scope=record_data["scope"],
                    conducted_by=record_data["conducted_by"],
                    conducted_at=datetime.fromisoformat(record_data["conducted_at"]),
                    findings=record_data.get("findings", []),
                    risk_level=record_data.get("risk_level", "low"),
                    mitigation_plan=record_data.get("mitigation_plan", ""),
                    next_review=datetime.fromisoformat(record_data["next_review"]) if record_data.get("next_review") else datetime.now(timezone.utc) + timedelta(days=90)
                )
                if ra.assessment_id not in loaded_ids:
                    self._risk_assessments.append(ra)
                    loaded_ids.add(ra.assessment_id)
            if loaded_ids:
                logger.info(f"REM: Loaded {len(loaded_ids)} risk assessments from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Could not load HITRUST data from Redis: {e}_Excuse_Me")

    def _save_control(self, control_id: str):
        """REM: Persist a single HITRUST control to Redis."""
        try:
            from core.persistence import compliance_store
            control = self._controls.get(control_id)
            if control:
                data = {
                    "control_id": control.control_id,
                    "domain": control.domain.value,
                    "title": control.title,
                    "description": control.description,
                    "status": control.status.value,
                    "evidence_references": control.evidence_references,
                    "last_assessed": control.last_assessed.isoformat() if control.last_assessed else None,
                    "assessed_by": control.assessed_by,
                    "notes": control.notes
                }
                compliance_store.store_record("hitrust_controls", control_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save HITRUST control to Redis: {e}_Excuse_Me")

    def _save_all_controls(self):
        """REM: Persist all HITRUST controls to Redis (used for baseline initialization)."""
        try:
            from core.persistence import compliance_store
            for control_id in self._controls:
                self._save_control(control_id)
        except Exception as e:
            logger.warning(f"REM: Could not save baseline HITRUST controls to Redis: {e}_Excuse_Me")

    def _save_risk_assessment(self, assessment_id: str):
        """REM: Persist a single risk assessment to Redis."""
        try:
            from core.persistence import compliance_store
            record = next((r for r in self._risk_assessments if r.assessment_id == assessment_id), None)
            if record:
                data = {
                    "assessment_id": record.assessment_id,
                    "title": record.title,
                    "scope": record.scope,
                    "conducted_by": record.conducted_by,
                    "conducted_at": record.conducted_at.isoformat(),
                    "findings": record.findings,
                    "risk_level": record.risk_level,
                    "mitigation_plan": record.mitigation_plan,
                    "next_review": record.next_review.isoformat()
                }
                compliance_store.store_record("risk_assessments", assessment_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save risk assessment to Redis: {e}_Excuse_Me")


# REM: Global HITRUST manager instance
hitrust_manager = HITRUSTManager()
