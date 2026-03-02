# TelsonBase/core/breach_notification.py
# REM: =======================================================================================
# REM: BREACH ASSESSMENT AND NOTIFICATION TRACKING
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: State breach notification law compliance through structured
# REM: breach assessment, notification tracking, and deadline management. All 50 states
# REM: have breach notification laws; this module tracks the assessment-to-notification
# REM: pipeline to ensure deadlines are met and regulators are properly informed.
#
# REM: HITECH Act compliance: Section 13402 (45 CFR Part 164, Subpart D) mandates
# REM: breach notification to affected individuals, HHS, and media (500+ individuals)
# REM: within 60 days of discovery. Encryption safe harbor: AES-256 encrypted data
# REM: at time of breach may exempt from notification (45 CFR 164.402).
#
# REM: Features:
# REM:   - Breach severity classification
# REM:   - Automatic notification requirement determination based on data types
# REM:   - Notification deadline tracking (HITECH 60-day deadline, state law varies: 30-60 days)
# REM:   - Overdue notification detection
# REM:   - Full audit trail for regulatory evidence
# REM:   - QMS-formatted logging throughout
# REM: =======================================================================================

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


class BreachSeverity(str, Enum):
    """REM: Classification of breach severity for triage and response prioritization."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class BreachAssessment:
    """REM: An assessed data breach incident with notification tracking."""
    assessment_id: str
    detected_at: datetime
    assessed_by: str
    severity: BreachSeverity
    description: str
    affected_tenants: List[str]
    affected_records_count: int
    data_types_exposed: List[str]  # REM: e.g., ["ssn", "financial", "pii", "privileged"]
    attack_vector: str
    containment_status: str  # REM: "investigating", "contained", "remediated"
    notification_required: bool  # REM: Determined by data types exposed
    notification_deadline: Optional[datetime]  # REM: Calculated from state law
    status: str  # REM: "assessing", "notifying", "closed"

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "assessment_id": self.assessment_id,
            "detected_at": self.detected_at.isoformat(),
            "assessed_by": self.assessed_by,
            "severity": self.severity.value,
            "description": self.description,
            "affected_tenants": self.affected_tenants,
            "affected_records_count": self.affected_records_count,
            "data_types_exposed": self.data_types_exposed,
            "attack_vector": self.attack_vector,
            "containment_status": self.containment_status,
            "notification_required": self.notification_required,
            "notification_deadline": self.notification_deadline.isoformat() if self.notification_deadline else None,
            "status": self.status
        }


@dataclass
class NotificationRecord:
    """REM: A single notification sent as part of breach response."""
    notification_id: str
    assessment_id: str
    recipient_type: str  # REM: "regulator", "affected_individual", "tenant", "law_enforcement"
    recipient: str
    sent_at: Optional[datetime] = None
    method: str = "email"  # REM: "email", "mail", "portal"
    status: str = "pending"  # REM: "pending", "sent", "acknowledged"

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "notification_id": self.notification_id,
            "assessment_id": self.assessment_id,
            "recipient_type": self.recipient_type,
            "recipient": self.recipient,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "method": self.method,
            "status": self.status
        }


# REM: Notification requirement rules based on data types exposed
# REM: Maps data type to whether notification is required and the deadline in days
NOTIFICATION_RULES: Dict[str, Dict[str, Any]] = {
    "ssn": {"required": True, "reason": "Social Security numbers exposed — mandatory notification", "deadline_days": 30},
    "financial": {"required": True, "reason": "Financial data exposed — mandatory notification", "deadline_days": 60},
    "pii": {"required": True, "reason": "Personally identifiable information exposed — mandatory notification", "deadline_days": 60},
    "privileged": {"required": True, "reason": "Attorney-client privileged data exposed — mandatory notification", "deadline_days": 60},
    "medical": {"required": True, "reason": "Protected health information exposed — HIPAA notification required", "deadline_days": 60},
}


class BreachManager:
    """
    REM: Manages breach assessment, notification tracking, and deadline compliance.
    REM: All mutations are audit-logged for regulatory evidence.
    """

    def __init__(self):
        # REM: In-memory storage for assessments and notifications
        self._assessments: Dict[str, BreachAssessment] = {}
        self._notifications: Dict[str, NotificationRecord] = {}

        # REM: Load persisted records from Redis
        self._load_from_redis()

        logger.info("REM: BreachManager initialized_Thank_You")

    def create_assessment(
        self,
        detected_at: datetime,
        assessed_by: str,
        severity: BreachSeverity,
        description: str,
        affected_tenants: List[str],
        affected_records_count: int,
        data_types_exposed: List[str],
        attack_vector: str
    ) -> BreachAssessment:
        """REM: Create a new breach assessment. Automatically determines notification requirements."""
        assessment_id = f"breach_{uuid.uuid4().hex[:12]}"

        # REM: Determine notification requirement based on data types
        notif_info = self.determine_notification_requirement(data_types_exposed)
        notification_required = notif_info["required"]
        notification_deadline = None

        if notification_required:
            notification_deadline = detected_at + timedelta(days=notif_info["deadline_days"])

        assessment = BreachAssessment(
            assessment_id=assessment_id,
            detected_at=detected_at,
            assessed_by=assessed_by,
            severity=severity,
            description=description,
            affected_tenants=affected_tenants,
            affected_records_count=affected_records_count,
            data_types_exposed=data_types_exposed,
            attack_vector=attack_vector,
            containment_status="investigating",
            notification_required=notification_required,
            notification_deadline=notification_deadline,
            status="assessing"
        )

        self._assessments[assessment_id] = assessment

        logger.info(
            f"REM: Breach assessment created - ::{assessment_id}:: "
            f"severity ::{severity.value}:: by ::{assessed_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Breach assessment created: {severity.value} severity",
            actor=assessed_by,
            resource=assessment_id,
            details={
                "severity": severity.value,
                "affected_tenants": affected_tenants,
                "affected_records_count": affected_records_count,
                "data_types_exposed": data_types_exposed,
                "attack_vector": attack_vector,
                "notification_required": notification_required,
                "notification_deadline": notification_deadline.isoformat() if notification_deadline else None
            },
            qms_status="Thank_You"
        )

        self._save_assessment(assessment_id)

        return assessment

    def update_containment(
        self,
        assessment_id: str,
        status: str,
        updated_by: str
    ) -> bool:
        """REM: Update the containment status of a breach assessment."""
        assessment = self._assessments.get(assessment_id)
        if not assessment:
            logger.warning(f"REM: Breach assessment ::{assessment_id}:: not found_Thank_You_But_No")
            return False

        old_status = assessment.containment_status
        assessment.containment_status = status

        logger.info(
            f"REM: Breach ::{assessment_id}:: containment updated "
            f"::{old_status}:: -> ::{status}:: by ::{updated_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Breach containment updated: {old_status} -> {status}",
            actor=updated_by,
            resource=assessment_id,
            details={
                "old_status": old_status,
                "new_status": status,
                "severity": assessment.severity.value
            },
            qms_status="Thank_You"
        )

        self._save_assessment(assessment_id)

        return True

    def determine_notification_requirement(self, data_types: List[str]) -> dict:
        """
        REM: Determine whether breach notification is required based on data types exposed.
        REM: Returns requirement info with reason and deadline.
        """
        # REM: Find the most urgent notification requirement among exposed data types
        required = False
        reason = "No notification-triggering data types exposed"
        deadline_days = 0

        for dtype in data_types:
            rule = NOTIFICATION_RULES.get(dtype)
            if rule and rule["required"]:
                required = True
                # REM: Use the shortest deadline among all matching rules
                if deadline_days == 0 or rule["deadline_days"] < deadline_days:
                    deadline_days = rule["deadline_days"]
                    reason = rule["reason"]

        if not required:
            deadline_days = 0

        return {
            "required": required,
            "reason": reason,
            "deadline_days": deadline_days
        }

    def create_notification(
        self,
        assessment_id: str,
        recipient_type: str,
        recipient: str,
        method: str
    ) -> NotificationRecord:
        """REM: Create a notification record for a breach assessment."""
        notification_id = f"notif_{uuid.uuid4().hex[:12]}"

        notification = NotificationRecord(
            notification_id=notification_id,
            assessment_id=assessment_id,
            recipient_type=recipient_type,
            recipient=recipient,
            method=method,
            status="pending"
        )

        self._notifications[notification_id] = notification

        logger.info(
            f"REM: Notification created - ::{notification_id}:: "
            f"to ::{recipient_type}:: ::{recipient}:: via ::{method}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Breach notification created for {recipient_type}",
            actor="system",
            resource=notification_id,
            details={
                "assessment_id": assessment_id,
                "recipient_type": recipient_type,
                "recipient": recipient,
                "method": method
            },
            qms_status="Thank_You"
        )

        self._save_notification(notification_id)

        return notification

    def mark_notification_sent(self, notification_id: str) -> bool:
        """REM: Mark a notification as sent."""
        notification = self._notifications.get(notification_id)
        if not notification:
            logger.warning(f"REM: Notification ::{notification_id}:: not found_Thank_You_But_No")
            return False

        now = datetime.now(timezone.utc)
        notification.sent_at = now
        notification.status = "sent"

        logger.info(
            f"REM: Notification ::{notification_id}:: marked as sent_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Breach notification sent: {notification_id}",
            actor="system",
            resource=notification_id,
            details={
                "assessment_id": notification.assessment_id,
                "recipient_type": notification.recipient_type,
                "recipient": notification.recipient,
                "sent_at": now.isoformat()
            },
            qms_status="Thank_You"
        )

        self._save_notification(notification_id)

        return True

    def get_overdue_notifications(self) -> List[BreachAssessment]:
        """
        REM: Find assessments past their notification deadline that still have
        REM: pending notifications. For compliance deadline monitoring.
        """
        now = datetime.now(timezone.utc)
        overdue = []

        for assessment in self._assessments.values():
            if not assessment.notification_required:
                continue
            if assessment.status == "closed":
                continue
            if assessment.notification_deadline and now > assessment.notification_deadline:
                # REM: Check if there are still pending notifications for this assessment
                pending = [
                    n for n in self._notifications.values()
                    if n.assessment_id == assessment.assessment_id
                    and n.status == "pending"
                ]
                if pending:
                    overdue.append(assessment)

        return overdue

    def get_assessment(self, assessment_id: str) -> Optional[BreachAssessment]:
        """REM: Get a breach assessment by ID."""
        return self._assessments.get(assessment_id)

    def list_assessments(self, status: Optional[str] = None) -> List[BreachAssessment]:
        """REM: List breach assessments, optionally filtered by status."""
        results = list(self._assessments.values())
        if status is not None:
            results = [a for a in results if a.status == status]
        return results

    def close_assessment(self, assessment_id: str, closed_by: str) -> bool:
        """REM: Close a breach assessment after all notifications are complete."""
        assessment = self._assessments.get(assessment_id)
        if not assessment:
            logger.warning(f"REM: Breach assessment ::{assessment_id}:: not found_Thank_You_But_No")
            return False

        assessment.status = "closed"

        logger.info(
            f"REM: Breach assessment ::{assessment_id}:: closed "
            f"by ::{closed_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Breach assessment closed: {assessment_id}",
            actor=closed_by,
            resource=assessment_id,
            details={
                "severity": assessment.severity.value,
                "affected_records_count": assessment.affected_records_count,
                "containment_status": assessment.containment_status,
                "notification_required": assessment.notification_required
            },
            qms_status="Thank_You"
        )

        self._save_assessment(assessment_id)

        return True

    def _load_from_redis(self):
        """REM: Load breach assessments and notifications from Redis on startup."""
        try:
            from core.persistence import compliance_store
            # REM: Load assessments
            all_assessments = compliance_store.list_records("breaches")
            for record_id, record_data in all_assessments.items():
                self._assessments[record_id] = BreachAssessment(
                    assessment_id=record_data["assessment_id"],
                    detected_at=datetime.fromisoformat(record_data["detected_at"]),
                    assessed_by=record_data["assessed_by"],
                    severity=BreachSeverity(record_data["severity"]),
                    description=record_data["description"],
                    affected_tenants=record_data["affected_tenants"],
                    affected_records_count=record_data["affected_records_count"],
                    data_types_exposed=record_data["data_types_exposed"],
                    attack_vector=record_data["attack_vector"],
                    containment_status=record_data["containment_status"],
                    notification_required=record_data["notification_required"],
                    notification_deadline=datetime.fromisoformat(record_data["notification_deadline"]) if record_data.get("notification_deadline") else None,
                    status=record_data["status"]
                )
            if self._assessments:
                logger.info(f"REM: Loaded {len(self._assessments)} breach assessments from Redis_Thank_You")

            # REM: Load notifications
            all_notifications = compliance_store.list_records("notifications")
            for record_id, record_data in all_notifications.items():
                self._notifications[record_id] = NotificationRecord(
                    notification_id=record_data["notification_id"],
                    assessment_id=record_data["assessment_id"],
                    recipient_type=record_data["recipient_type"],
                    recipient=record_data["recipient"],
                    sent_at=datetime.fromisoformat(record_data["sent_at"]) if record_data.get("sent_at") else None,
                    method=record_data.get("method", "email"),
                    status=record_data.get("status", "pending")
                )
            if self._notifications:
                logger.info(f"REM: Loaded {len(self._notifications)} breach notifications from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Could not load breach data from Redis: {e}_Excuse_Me")

    def _save_assessment(self, record_id: str):
        """REM: Persist a single breach assessment to Redis."""
        try:
            from core.persistence import compliance_store
            record = self._assessments.get(record_id)
            if record:
                data = record.to_dict()
                compliance_store.store_record("breaches", record_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save breach assessment to Redis: {e}_Excuse_Me")

    def _save_notification(self, record_id: str):
        """REM: Persist a single notification record to Redis."""
        try:
            from core.persistence import compliance_store
            record = self._notifications.get(record_id)
            if record:
                data = record.to_dict()
                compliance_store.store_record("notifications", record_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save notification to Redis: {e}_Excuse_Me")
