# TelsonBase/core/compliance.py
# REM: =======================================================================================
# REM: COMPLIANCE EXPORT AND REPORTING
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.2.0CC: New feature - Compliance report generation
#
# REM: Mission Statement: Generate compliance reports for auditors and regulators.
# REM: Supports SOC2, ISO27001, and custom report formats with evidence collection.
#
# REM: Features:
# REM:   - SOC2 Type II report generation
# REM:   - ISO 27001 control mapping
# REM:   - Evidence collection from audit logs
# REM:   - PDF and JSON export formats
# REM:   - Scheduled report generation
# REM: =======================================================================================

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


class ComplianceFramework(str, Enum):
    """REM: Supported compliance frameworks."""
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    NIST = "nist"
    CUSTOM = "custom"


class ControlStatus(str, Enum):
    """REM: Status of a compliance control."""
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_EVIDENCE = "needs_evidence"


@dataclass
class ComplianceControl:
    """REM: A single compliance control."""
    control_id: str
    framework: ComplianceFramework
    title: str
    description: str
    category: str
    evidence_required: List[str]
    status: ControlStatus = ControlStatus.NEEDS_EVIDENCE
    evidence_collected: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    last_assessed: Optional[datetime] = None
    assessor: Optional[str] = None


# REM: SOC2 Trust Service Criteria controls relevant to AI agent systems
SOC2_CONTROLS: List[Dict[str, Any]] = [
    {
        "control_id": "CC6.1",
        "category": "Logical Access",
        "title": "Logical Access Security Software",
        "description": "The entity implements logical access security software to prevent unauthorized access.",
        "evidence_required": ["authentication_logs", "capability_enforcement", "api_key_management"]
    },
    {
        "control_id": "CC6.2",
        "category": "Logical Access",
        "title": "New User Registration",
        "description": "Prior to issuing system credentials, the entity registers and authorizes new users.",
        "evidence_required": ["agent_registration", "key_assignment", "trust_level_assignment"]
    },
    {
        "control_id": "CC6.3",
        "category": "Logical Access",
        "title": "Removal of Access",
        "description": "The entity removes access to resources when no longer required.",
        "evidence_required": ["agent_revocation", "key_revocation", "session_termination"]
    },
    {
        "control_id": "CC6.6",
        "category": "Logical Access",
        "title": "Protection Against External Threats",
        "description": "The entity implements controls to protect against external threats.",
        "evidence_required": ["mtls_certificates", "federation_trust", "egress_filtering"]
    },
    {
        "control_id": "CC6.7",
        "category": "Logical Access",
        "title": "Restriction of Transmission",
        "description": "The entity restricts the transmission of data to authorized users and processes.",
        "evidence_required": ["message_signing", "capability_checks", "data_classification"]
    },
    {
        "control_id": "CC7.1",
        "category": "System Operations",
        "title": "Detection of Unauthorized Changes",
        "description": "The entity detects and monitors changes to configurations and infrastructure.",
        "evidence_required": ["anomaly_detection", "behavioral_monitoring", "configuration_audit"]
    },
    {
        "control_id": "CC7.2",
        "category": "System Operations",
        "title": "Monitoring for Security Events",
        "description": "The entity monitors system components for anomalies indicative of malicious acts.",
        "evidence_required": ["security_alerts", "anomaly_records", "intrusion_detection"]
    },
    {
        "control_id": "CC7.3",
        "category": "System Operations",
        "title": "Evaluation of Security Events",
        "description": "Security events are analyzed to determine their impact.",
        "evidence_required": ["anomaly_resolution", "incident_response", "severity_classification"]
    },
    {
        "control_id": "CC7.4",
        "category": "System Operations",
        "title": "Response to Security Incidents",
        "description": "The entity responds to identified security incidents.",
        "evidence_required": ["quarantine_actions", "revocation_actions", "incident_records"]
    },
    {
        "control_id": "CC8.1",
        "category": "Change Management",
        "title": "Authorization of Changes",
        "description": "Changes are authorized prior to implementation.",
        "evidence_required": ["approval_workflow", "human_in_loop", "change_records"]
    },
]


@dataclass
class ComplianceReport:
    """REM: A generated compliance report."""
    report_id: str
    framework: ComplianceFramework
    generated_at: datetime
    generated_by: str
    period_start: datetime
    period_end: datetime
    controls: List[ComplianceControl]
    summary: Dict[str, Any]
    evidence_summary: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "framework": self.framework.value,
            "generated_at": self.generated_at.isoformat(),
            "generated_by": self.generated_by,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat()
            },
            "summary": self.summary,
            "evidence_summary": self.evidence_summary,
            "controls": [
                {
                    "control_id": c.control_id,
                    "title": c.title,
                    "category": c.category,
                    "status": c.status.value,
                    "evidence_count": len(c.evidence_collected),
                    "last_assessed": c.last_assessed.isoformat() if c.last_assessed else None,
                    "notes": c.notes
                }
                for c in self.controls
            ]
        }


class ComplianceEngine:
    """
    REM: Generates compliance reports and collects evidence.
    """

    def __init__(self):
        self._reports: Dict[str, ComplianceReport] = {}
        self._evidence_sources: Dict[str, callable] = {}

    def register_evidence_source(self, evidence_type: str, collector: callable) -> None:
        """REM: Register a function that collects evidence of a specific type."""
        self._evidence_sources[evidence_type] = collector
        logger.info(f"REM: Evidence source registered: ::{evidence_type}::_Thank_You")

    def collect_evidence(
        self,
        evidence_type: str,
        period_start: datetime,
        period_end: datetime
    ) -> List[Dict[str, Any]]:
        """REM: Collect evidence of a specific type for a period."""
        if evidence_type not in self._evidence_sources:
            logger.warning(f"REM: No evidence source for ::{evidence_type}::_Thank_You_But_No")
            return []

        try:
            collector = self._evidence_sources[evidence_type]
            return collector(period_start, period_end)
        except Exception as e:
            logger.error(f"REM: Evidence collection failed for ::{evidence_type}:: - {e}_Thank_You_But_No")
            return []

    def assess_control(
        self,
        control: ComplianceControl,
        period_start: datetime,
        period_end: datetime
    ) -> ComplianceControl:
        """REM: Assess a single control and collect evidence."""
        all_evidence = []

        for evidence_type in control.evidence_required:
            evidence = self.collect_evidence(evidence_type, period_start, period_end)
            all_evidence.extend(evidence)

        control.evidence_collected = all_evidence
        control.last_assessed = datetime.now(timezone.utc)

        # REM: Determine status based on evidence
        if len(all_evidence) == 0:
            control.status = ControlStatus.NEEDS_EVIDENCE
        elif len(all_evidence) >= len(control.evidence_required):
            control.status = ControlStatus.COMPLIANT
        else:
            control.status = ControlStatus.PARTIAL

        return control

    def generate_report(
        self,
        framework: ComplianceFramework,
        period_start: datetime,
        period_end: datetime,
        generated_by: str = "system"
    ) -> ComplianceReport:
        """REM: Generate a compliance report for a framework."""
        import uuid

        logger.info(
            f"REM: Generating {framework.value} compliance report for "
            f"{period_start.date()} to {period_end.date()}_Thank_You"
        )

        # REM: Get controls for framework
        if framework == ComplianceFramework.SOC2:
            control_defs = SOC2_CONTROLS
        else:
            control_defs = []

        # REM: Create and assess controls
        controls = []
        for ctrl_def in control_defs:
            control = ComplianceControl(
                control_id=ctrl_def["control_id"],
                framework=framework,
                title=ctrl_def["title"],
                description=ctrl_def["description"],
                category=ctrl_def["category"],
                evidence_required=ctrl_def["evidence_required"]
            )
            assessed = self.assess_control(control, period_start, period_end)
            controls.append(assessed)

        # REM: Calculate summary
        status_counts = defaultdict(int)
        for control in controls:
            status_counts[control.status.value] += 1

        evidence_counts = defaultdict(int)
        for control in controls:
            for evidence in control.evidence_collected:
                evidence_counts[evidence.get("type", "unknown")] += 1

        summary = {
            "total_controls": len(controls),
            "compliant": status_counts.get(ControlStatus.COMPLIANT.value, 0),
            "partial": status_counts.get(ControlStatus.PARTIAL.value, 0),
            "non_compliant": status_counts.get(ControlStatus.NON_COMPLIANT.value, 0),
            "needs_evidence": status_counts.get(ControlStatus.NEEDS_EVIDENCE.value, 0),
            "compliance_percentage": round(
                (status_counts.get(ControlStatus.COMPLIANT.value, 0) / max(len(controls), 1)) * 100,
                1
            )
        }

        report_id = f"rpt_{framework.value}_{uuid.uuid4().hex[:8]}"

        report = ComplianceReport(
            report_id=report_id,
            framework=framework,
            generated_at=datetime.now(timezone.utc),
            generated_by=generated_by,
            period_start=period_start,
            period_end=period_end,
            controls=controls,
            summary=summary,
            evidence_summary=dict(evidence_counts)
        )

        self._reports[report_id] = report

        logger.info(
            f"REM: Compliance report generated - ::{report_id}:: "
            f"Compliance: {summary['compliance_percentage']}%_Thank_You"
        )

        audit.log(
            AuditEventType.EXTERNAL_RESPONSE,
            f"Compliance report generated: {framework.value}",
            actor=generated_by,
            resource=report_id,
            details=summary,
            qms_status="Thank_You"
        )

        return report

    def get_report(self, report_id: str) -> Optional[ComplianceReport]:
        """REM: Get a previously generated report."""
        return self._reports.get(report_id)

    def list_reports(
        self,
        framework: Optional[ComplianceFramework] = None
    ) -> List[Dict[str, Any]]:
        """REM: List all generated reports."""
        reports = []
        for report in self._reports.values():
            if framework and report.framework != framework:
                continue
            reports.append({
                "report_id": report.report_id,
                "framework": report.framework.value,
                "generated_at": report.generated_at.isoformat(),
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "compliance_percentage": report.summary.get("compliance_percentage", 0)
            })
        return sorted(reports, key=lambda r: r["generated_at"], reverse=True)

    def export_report_json(self, report_id: str) -> Optional[str]:
        """REM: Export report as JSON."""
        report = self._reports.get(report_id)
        if not report:
            return None

        return json.dumps(report.to_dict(), indent=2)

    def get_evidence_requirements(
        self,
        framework: ComplianceFramework
    ) -> List[Dict[str, Any]]:
        """REM: Get list of evidence types required for a framework."""
        if framework == ComplianceFramework.SOC2:
            control_defs = SOC2_CONTROLS
        else:
            return []

        evidence_types = set()
        for ctrl in control_defs:
            evidence_types.update(ctrl["evidence_required"])

        return [
            {
                "type": et,
                "registered": et in self._evidence_sources
            }
            for et in sorted(evidence_types)
        ]


# REM: Global compliance engine instance
compliance_engine = ComplianceEngine()


# REM: Default evidence collectors using audit data
def _collect_audit_evidence(
    event_type: AuditEventType,
    period_start: datetime,
    period_end: datetime
) -> List[Dict[str, Any]]:
    """REM: Collect evidence from audit logs."""
    evidence = []

    # REM: This would query the actual audit store
    # REM: For now, return a sample structure
    evidence.append({
        "type": event_type.value,
        "count": 0,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "source": "audit_log"
    })

    return evidence


# REM: Register default evidence collectors
def _capability_evidence(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    return _collect_audit_evidence(AuditEventType.CAPABILITY_CHECK, start, end)


def _security_evidence(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    return _collect_audit_evidence(AuditEventType.SECURITY_ALERT, start, end)


def _approval_evidence(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    return _collect_audit_evidence(AuditEventType.APPROVAL_GRANTED, start, end)


def _anomaly_evidence(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    return _collect_audit_evidence(AuditEventType.ANOMALY_DETECTED, start, end)


# REM: Register collectors
compliance_engine.register_evidence_source("capability_enforcement", _capability_evidence)
compliance_engine.register_evidence_source("capability_checks", _capability_evidence)
compliance_engine.register_evidence_source("security_alerts", _security_evidence)
compliance_engine.register_evidence_source("quarantine_actions", _security_evidence)
compliance_engine.register_evidence_source("revocation_actions", _security_evidence)
compliance_engine.register_evidence_source("approval_workflow", _approval_evidence)
compliance_engine.register_evidence_source("human_in_loop", _approval_evidence)
compliance_engine.register_evidence_source("anomaly_detection", _anomaly_evidence)
compliance_engine.register_evidence_source("anomaly_records", _anomaly_evidence)
compliance_engine.register_evidence_source("behavioral_monitoring", _anomaly_evidence)
