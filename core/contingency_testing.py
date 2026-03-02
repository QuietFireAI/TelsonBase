# TelsonBase/core/contingency_testing.py
# REM: =======================================================================================
# REM: HIPAA CONTINGENCY PLAN TESTING
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.3.0CC: HIPAA 45 CFR 164.308(a)(7)(ii)(D) — Testing and Revision Procedures
#
# REM: Mission Statement: Contingency plan testing and documentation for HIPAA compliance.
# REM: The Security Rule requires covered entities to implement procedures for periodic
# REM: testing and revision of contingency plans. This module tracks test scheduling,
# REM: execution, findings, corrective actions, and overdue test detection.
#
# REM: Features:
# REM:   - Contingency test type classification (backup, failover, DR, etc.)
# REM:   - Test scheduling and result recording
# REM:   - Findings and corrective action tracking
# REM:   - Overdue test detection with configurable intervals
# REM:   - Compliance summary generation
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


class TestType(str, Enum):
    """REM: Categories of contingency plan tests required under HIPAA."""
    BACKUP_RESTORE = "backup_restore"
    FAILOVER = "failover"
    DISASTER_RECOVERY = "disaster_recovery"
    DATA_INTEGRITY = "data_integrity"
    EMERGENCY_MODE = "emergency_mode"


@dataclass
class ContingencyTest:
    """REM: A single contingency plan test execution with results."""
    test_id: str
    test_type: TestType
    conducted_by: str
    conducted_at: datetime
    duration_minutes: int
    passed: bool
    findings: List[str]
    corrective_actions: List[str]
    next_scheduled: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "test_id": self.test_id,
            "test_type": self.test_type.value,
            "conducted_by": self.conducted_by,
            "conducted_at": self.conducted_at.isoformat(),
            "duration_minutes": self.duration_minutes,
            "passed": self.passed,
            "findings": self.findings,
            "corrective_actions": self.corrective_actions,
            "next_scheduled": self.next_scheduled.isoformat() if self.next_scheduled else None
        }


@dataclass
class ScheduledTest:
    """REM: A scheduled future contingency test."""
    schedule_id: str
    test_type: TestType
    scheduled_for: datetime
    conducted_by: str
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "schedule_id": self.schedule_id,
            "test_type": self.test_type.value,
            "scheduled_for": self.scheduled_for.isoformat(),
            "conducted_by": self.conducted_by,
            "completed": self.completed
        }


class ContingencyTestManager:
    """
    REM: Manages contingency plan testing for HIPAA 45 CFR 164.308(a)(7)(ii)(D).
    REM: All test results are audit-logged for regulatory evidence.
    """

    def __init__(self):
        # REM: In-memory storage for test results and schedules
        self._tests: Dict[str, ContingencyTest] = {}
        self._schedules: Dict[str, ScheduledTest] = {}

        # REM: Load persisted records from Redis
        self._load_from_redis()

        logger.info("REM: ContingencyTestManager initialized_Thank_You")

    def schedule_test(
        self,
        test_type: TestType,
        scheduled_for: datetime,
        conducted_by: str
    ) -> ScheduledTest:
        """REM: Schedule a future contingency test."""
        schedule_id = f"sched_{uuid.uuid4().hex[:12]}"

        scheduled = ScheduledTest(
            schedule_id=schedule_id,
            test_type=test_type,
            scheduled_for=scheduled_for,
            conducted_by=conducted_by
        )

        self._schedules[schedule_id] = scheduled

        logger.info(
            f"REM: Contingency test scheduled - ::{schedule_id}:: "
            f"type ::{test_type.value}:: for ::{scheduled_for.isoformat()}:: "
            f"by ::{conducted_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Contingency test scheduled: {test_type.value}",
            actor=conducted_by,
            resource=schedule_id,
            details={
                "test_type": test_type.value,
                "scheduled_for": scheduled_for.isoformat(),
                "conducted_by": conducted_by
            },
            qms_status="Thank_You"
        )

        self._save_schedule(schedule_id)

        return scheduled

    def record_test_result(
        self,
        test_type: TestType,
        conducted_by: str,
        duration: int,
        passed: bool,
        findings: List[str],
        corrective_actions: List[str]
    ) -> ContingencyTest:
        """REM: Record the result of a contingency test execution."""
        test_id = f"ctest_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        test = ContingencyTest(
            test_id=test_id,
            test_type=test_type,
            conducted_by=conducted_by,
            conducted_at=now,
            duration_minutes=duration,
            passed=passed,
            findings=findings,
            corrective_actions=corrective_actions
        )

        self._tests[test_id] = test

        logger.info(
            f"REM: Contingency test recorded - ::{test_id}:: "
            f"type ::{test_type.value}:: passed ::{passed}:: "
            f"duration ::{duration}:: min by ::{conducted_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Contingency test result: {test_type.value} passed={passed}",
            actor=conducted_by,
            resource=test_id,
            details={
                "test_type": test_type.value,
                "duration_minutes": duration,
                "passed": passed,
                "findings_count": len(findings),
                "corrective_actions_count": len(corrective_actions),
                "findings": findings,
                "corrective_actions": corrective_actions
            },
            qms_status="Thank_You" if passed else "Thank_You_But_No"
        )

        self._save_test(test_id)

        return test

    def get_test_history(self, test_type: Optional[TestType] = None) -> List[ContingencyTest]:
        """REM: Get test history, optionally filtered by test type."""
        results = list(self._tests.values())
        if test_type is not None:
            results = [t for t in results if t.test_type == test_type]
        # REM: Sort by conducted_at descending (most recent first)
        results.sort(key=lambda t: t.conducted_at, reverse=True)
        return results

    def get_overdue_tests(self, interval_days: int = 90) -> List[TestType]:
        """
        REM: Find test types that have not been conducted within the specified interval.
        REM: Returns list of TestType values that are overdue for testing.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=interval_days)
        overdue: List[TestType] = []

        for ttype in TestType:
            # REM: Find the most recent test of this type
            type_tests = [t for t in self._tests.values() if t.test_type == ttype]
            if not type_tests:
                # REM: Never tested — overdue
                overdue.append(ttype)
                continue

            latest = max(type_tests, key=lambda t: t.conducted_at)
            if latest.conducted_at < cutoff:
                overdue.append(ttype)

        return overdue

    def get_compliance_summary(self) -> Dict[str, Any]:
        """REM: Generate a compliance summary with last test dates and pass/fail status."""
        now = datetime.now(timezone.utc)
        summary: Dict[str, Any] = {
            "generated_at": now.isoformat(),
            "test_types": {}
        }

        for ttype in TestType:
            type_tests = [t for t in self._tests.values() if t.test_type == ttype]

            if not type_tests:
                summary["test_types"][ttype.value] = {
                    "last_tested": None,
                    "last_passed": None,
                    "total_tests": 0,
                    "pass_count": 0,
                    "fail_count": 0
                }
                continue

            latest = max(type_tests, key=lambda t: t.conducted_at)
            pass_count = sum(1 for t in type_tests if t.passed)

            summary["test_types"][ttype.value] = {
                "last_tested": latest.conducted_at.isoformat(),
                "last_passed": latest.passed,
                "total_tests": len(type_tests),
                "pass_count": pass_count,
                "fail_count": len(type_tests) - pass_count
            }

        return summary

    def _load_from_redis(self):
        """REM: Load contingency test records and schedules from Redis on startup."""
        try:
            from core.persistence import compliance_store
            # REM: Load test results
            all_tests = compliance_store.list_records("contingency_tests")
            for record_id, record_data in all_tests.items():
                self._tests[record_id] = ContingencyTest(
                    test_id=record_data["test_id"],
                    test_type=TestType(record_data["test_type"]),
                    conducted_by=record_data["conducted_by"],
                    conducted_at=datetime.fromisoformat(record_data["conducted_at"]),
                    duration_minutes=record_data["duration_minutes"],
                    passed=record_data["passed"],
                    findings=record_data.get("findings", []),
                    corrective_actions=record_data.get("corrective_actions", []),
                    next_scheduled=datetime.fromisoformat(record_data["next_scheduled"]) if record_data.get("next_scheduled") else None
                )
            if self._tests:
                logger.info(f"REM: Loaded {len(self._tests)} contingency tests from Redis_Thank_You")

            # REM: Load scheduled tests
            all_schedules = compliance_store.list_records("contingency_schedules")
            for record_id, record_data in all_schedules.items():
                self._schedules[record_id] = ScheduledTest(
                    schedule_id=record_data["schedule_id"],
                    test_type=TestType(record_data["test_type"]),
                    scheduled_for=datetime.fromisoformat(record_data["scheduled_for"]),
                    conducted_by=record_data["conducted_by"],
                    completed=record_data.get("completed", False)
                )
            if self._schedules:
                logger.info(f"REM: Loaded {len(self._schedules)} contingency schedules from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Could not load contingency data from Redis: {e}_Excuse_Me")

    def _save_test(self, record_id: str):
        """REM: Persist a single contingency test result to Redis."""
        try:
            from core.persistence import compliance_store
            record = self._tests.get(record_id)
            if record:
                data = record.to_dict()
                compliance_store.store_record("contingency_tests", record_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save contingency test to Redis: {e}_Excuse_Me")

    def _save_schedule(self, record_id: str):
        """REM: Persist a single scheduled test to Redis."""
        try:
            from core.persistence import compliance_store
            record = self._schedules.get(record_id)
            if record:
                data = record.to_dict()
                compliance_store.store_record("contingency_schedules", record_id, data)
        except Exception as e:
            logger.warning(f"REM: Could not save contingency schedule to Redis: {e}_Excuse_Me")


# REM: Module-level singleton for import convenience
contingency_manager = ContingencyTestManager()
