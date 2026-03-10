# TelsonBase/core/training.py
# REM: =======================================================================================
# REM: HIPAA SECURITY AWARENESS TRAINING TRACKING
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.3.0CC: HIPAA 45 CFR 164.308(a)(5) — Security Awareness and Training
#
# REM: Mission Statement: Workforce training compliance for HIPAA. The Security Rule
# REM: requires covered entities to implement a security awareness and training program
# REM: for all workforce members. This module tracks training completion, expiration,
# REM: compliance status, and generates compliance reports with full audit trail.
#
# REM: Features:
# REM:   - Training type classification (privacy, security, incident response, etc.)
# REM:   - Configurable training requirements per role with renewal periods
# REM:   - Compliance checking against role-based requirements
# REM:   - Overdue training detection
# REM:   - Compliance reporting with statistics
# REM:   - QMS-formatted logging throughout
# REM: =======================================================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.audit import AuditEventType, audit
from core.rbac import Role

logger = logging.getLogger(__name__)


class TrainingType(str, Enum):
    """REM: Categories of required HIPAA security awareness training."""
    HIPAA_PRIVACY = "hipaa_privacy"
    HIPAA_SECURITY = "hipaa_security"
    INCIDENT_RESPONSE = "incident_response"
    PHISHING_AWARENESS = "phishing_awareness"
    DATA_HANDLING = "data_handling"
    ANNUAL_REFRESHER = "annual_refresher"


@dataclass
class TrainingRecord:
    """REM: A single completed training session for a workforce member."""
    record_id: str
    user_id: str
    training_type: TrainingType
    completed_at: datetime
    expires_at: datetime
    score: Optional[float] = None
    passed: bool = False
    certificate_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "training_type": self.training_type.value,
            "completed_at": self.completed_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "score": self.score,
            "passed": self.passed,
            "certificate_id": self.certificate_id
        }


@dataclass
class TrainingRequirement:
    """REM: A training requirement definition with role applicability and renewal rules."""
    training_type: TrainingType
    required_for_roles: Set[Role]
    renewal_period_days: int
    minimum_score: float

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "training_type": self.training_type.value,
            "required_for_roles": [r.value for r in self.required_for_roles],
            "renewal_period_days": self.renewal_period_days,
            "minimum_score": self.minimum_score
        }


# REM: Default set of all roles for universal training requirements
_ALL_ROLES: Set[Role] = {Role.VIEWER, Role.OPERATOR, Role.ADMIN, Role.SECURITY_OFFICER, Role.SUPER_ADMIN}


class TrainingManager:
    """
    REM: Manages workforce training compliance for HIPAA 45 CFR 164.308(a)(5).
    REM: All completions and compliance checks are audit-logged.
    """

    def __init__(self):
        # REM: In-memory storage for training records and requirements
        self._records: List[TrainingRecord] = []
        self._requirements: Dict[TrainingType, TrainingRequirement] = {}

        # REM: Register default requirements for all training types
        self._register_defaults()

        # REM: Load persisted records from Redis
        self._load_from_redis()

        logger.info("REM: TrainingManager initialized with default requirements_Thank_You")

    def _register_defaults(self):
        """REM: Pre-register default training requirements for all training types."""
        defaults = [
            (TrainingType.HIPAA_PRIVACY, _ALL_ROLES, 365, 80.0),
            (TrainingType.HIPAA_SECURITY, _ALL_ROLES, 365, 80.0),
            (TrainingType.INCIDENT_RESPONSE, {Role.OPERATOR, Role.ADMIN, Role.SECURITY_OFFICER, Role.SUPER_ADMIN}, 365, 75.0),
            (TrainingType.PHISHING_AWARENESS, _ALL_ROLES, 180, 70.0),
            (TrainingType.DATA_HANDLING, _ALL_ROLES, 365, 80.0),
            (TrainingType.ANNUAL_REFRESHER, _ALL_ROLES, 365, 70.0),
        ]
        for ttype, roles, days, score in defaults:
            self._requirements[ttype] = TrainingRequirement(
                training_type=ttype,
                required_for_roles=roles,
                renewal_period_days=days,
                minimum_score=score
            )

    def add_requirement(
        self,
        training_type: TrainingType,
        roles: Set[Role],
        renewal_days: int,
        min_score: float
    ) -> None:
        """REM: Add or update a training requirement."""
        self._requirements[training_type] = TrainingRequirement(
            training_type=training_type,
            required_for_roles=roles,
            renewal_period_days=renewal_days,
            minimum_score=min_score
        )

        logger.info(
            f"REM: Training requirement set - ::{training_type.value}:: "
            f"renewal ::{renewal_days}:: days min_score ::{min_score}::_Thank_You"
        )

        self._save_requirement(training_type.value)

    def record_completion(
        self,
        user_id: str,
        training_type,
        score: Optional[float],
        passed: bool
    ) -> TrainingRecord:
        """REM: Record a training completion for a workforce member."""
        # REM: v7.2.0CC: Accept both TrainingType enum and raw string
        if isinstance(training_type, str) and not isinstance(training_type, TrainingType):
            training_type = TrainingType(training_type)
        record_id = f"train_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # REM: Calculate expiration from the requirement renewal period
        requirement = self._requirements.get(training_type)
        renewal_days = requirement.renewal_period_days if requirement else 365
        expires_at = now + timedelta(days=renewal_days)

        certificate_id = f"cert_{uuid.uuid4().hex[:8]}" if passed else None

        record = TrainingRecord(
            record_id=record_id,
            user_id=user_id,
            training_type=training_type,
            completed_at=now,
            expires_at=expires_at,
            score=score,
            passed=passed,
            certificate_id=certificate_id
        )

        self._records.append(record)

        logger.info(
            f"REM: Training completed - ::{record_id}:: "
            f"user ::{user_id}:: type ::{training_type.value}:: "
            f"passed ::{passed}:: score ::{score}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Training completed: {training_type.value} by {user_id}",
            actor=user_id,
            resource=record_id,
            details={
                "training_type": training_type.value,
                "score": score,
                "passed": passed,
                "expires_at": expires_at.isoformat(),
                "certificate_id": certificate_id
            },
            qms_status="Thank_You" if passed else "Thank_You_But_No"
        )

        self._save_completion(record_id)

        return record

    def is_compliant(self, user_id: str, user_roles: Set[Role]) -> bool:
        """REM: Check if a user has completed all required trainings that are still current."""
        overdue = self.get_overdue_trainings(user_id, user_roles)
        compliant = len(overdue) == 0

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Training compliance check: {user_id} compliant={compliant}",
            actor="system",
            resource=user_id,
            details={
                "user_roles": [r.value for r in user_roles],
                "compliant": compliant,
                "overdue_count": len(overdue),
                "overdue_types": [t.value for t in overdue]
            },
            qms_status="Thank_You" if compliant else "Thank_You_But_No"
        )

        return compliant

    def get_overdue_trainings(self, user_id: str, user_roles: Set[Role]) -> List[TrainingType]:
        """REM: Get list of training types that are overdue or never completed for a user."""
        now = datetime.now(timezone.utc)
        overdue: List[TrainingType] = []

        for ttype, requirement in self._requirements.items():
            # REM: Only check requirements applicable to the user's roles
            if not requirement.required_for_roles.intersection(user_roles):
                continue

            # REM: Find the most recent passing record for this training type
            user_records = [
                r for r in self._records
                if r.user_id == user_id
                and r.training_type == ttype
                and r.passed
            ]

            if not user_records:
                # REM: Never completed this required training
                overdue.append(ttype)
                continue

            # REM: Check if the most recent passing record has expired
            latest = max(user_records, key=lambda r: r.completed_at)
            if now > latest.expires_at:
                overdue.append(ttype)

        return overdue

    def get_compliance_status(self, user_id: str) -> Dict[str, Any]:
        """REM: v7.2.0CC: Get compliance status for a specific user. Returns dict for route unpacking."""
        now = datetime.now(timezone.utc)
        user_records = [r for r in self._records if r.user_id == user_id]
        passed = [r for r in user_records if r.passed]
        current = [r for r in passed if now <= r.expires_at]
        expired = [r for r in passed if now > r.expires_at]
        return {
            "user_id": user_id,
            "total_completions": len(user_records),
            "passed": len(passed),
            "current_valid": len(current),
            "expired": len(expired),
            "records": [r.to_dict() for r in user_records]
        }

    def get_overdue_training(self, user_id: str, user_roles=None) -> List[str]:
        """REM: v7.2.0CC: Alias for get_overdue_trainings — routes use singular form."""
        if user_roles is None:
            user_roles = _ALL_ROLES
        overdue = self.get_overdue_trainings(user_id, user_roles)
        return [t.value for t in overdue]

    def get_compliance_report(self) -> Dict[str, Any]:
        """REM: Generate a compliance report with aggregate statistics."""
        now = datetime.now(timezone.utc)
        total_records = len(self._records)
        passed_records = sum(1 for r in self._records if r.passed)
        expired_records = sum(1 for r in self._records if r.passed and now > r.expires_at)
        current_records = sum(1 for r in self._records if r.passed and now <= r.expires_at)

        # REM: Unique users who have any training
        unique_users = set(r.user_id for r in self._records)

        return {
            "generated_at": now.isoformat(),
            "total_completions": total_records,
            "passed": passed_records,
            "failed": total_records - passed_records,
            "current_valid": current_records,
            "expired": expired_records,
            "unique_users_trained": len(unique_users),
            "requirements_count": len(self._requirements),
            "requirements": {t.value: req.to_dict() for t, req in self._requirements.items()}
        }

    def _load_from_redis(self):
        """REM: Load training records and requirements from Redis on startup."""
        try:
            from core.persistence import compliance_store

            # REM: Load training completion records
            all_records = compliance_store.list_records("training_records")
            loaded_ids = set()
            for record_id, record_data in all_records.items():
                rec = TrainingRecord(
                    record_id=record_data["record_id"],
                    user_id=record_data["user_id"],
                    training_type=TrainingType(record_data["training_type"]),
                    completed_at=datetime.fromisoformat(record_data["completed_at"]),
                    expires_at=datetime.fromisoformat(record_data["expires_at"]),
                    score=record_data.get("score"),
                    passed=record_data.get("passed", False),
                    certificate_id=record_data.get("certificate_id")
                )
                # REM: Avoid duplicates if already present
                if rec.record_id not in loaded_ids:
                    self._records.append(rec)
                    loaded_ids.add(rec.record_id)
            if loaded_ids:
                logger.info(f"REM: Loaded {len(loaded_ids)} training records from Redis_Thank_You")

            # REM: Load custom training requirements (overrides defaults)
            all_reqs = compliance_store.list_records("training_requirements")
            for record_id, record_data in all_reqs.items():
                ttype = TrainingType(record_data["training_type"])
                self._requirements[ttype] = TrainingRequirement(
                    training_type=ttype,
                    required_for_roles={Role(r) for r in record_data["required_for_roles"]},
                    renewal_period_days=record_data["renewal_period_days"],
                    minimum_score=record_data["minimum_score"]
                )
            if all_reqs:
                logger.info(f"REM: Loaded {len(all_reqs)} training requirements from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Could not load training data from Redis: {e}_Excuse_Me")

    def _save_completion(self, record_id: str):
        """REM: Persist a single training completion record to Redis."""
        try:
            from core.persistence import compliance_store
            record = next((r for r in self._records if r.record_id == record_id), None)
            if record:
                data = record.to_dict()
                compliance_store.store_record("training_records", record_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save training record to Redis: {e}_Excuse_Me")

    def _save_requirement(self, training_type_value: str):
        """REM: Persist a single training requirement to Redis."""
        try:
            from core.persistence import compliance_store
            ttype = TrainingType(training_type_value)
            requirement = self._requirements.get(ttype)
            if requirement:
                data = requirement.to_dict()
                compliance_store.store_record("training_requirements", training_type_value, data)
        except Exception as e:
            logger.warning(f"REM: Could not save training requirement to Redis: {e}_Excuse_Me")


# REM: Module-level singleton for import convenience
training_manager = TrainingManager()
