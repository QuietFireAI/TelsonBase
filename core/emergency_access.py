# TelsonBase/core/emergency_access.py
# REM: =======================================================================================
# REM: HIPAA BREAK-THE-GLASS EMERGENCY ACCESS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: HIPAA 45 CFR 164.312(a)(2)(i) requires covered entities to
# REM: establish emergency access procedures for obtaining necessary ePHI during an
# REM: emergency. "Break-the-glass" allows temporary elevated access when normal
# REM: authorization channels are unavailable or too slow for patient safety.
# REM: Every emergency access event MUST be audit-logged for post-incident review.
#
# REM: Features:
# REM:   - Emergency access request and approval workflow
# REM:   - Time-limited elevated permissions with auto-expiry
# REM:   - Full Permission set granted during emergency
# REM:   - Mandatory audit trail for all emergency access events
# REM:   - Revocation capability for security officers
# REM:   - Active emergency monitoring
# REM:   - QMS-formatted logging throughout
#
# REM: v6.3.0CC: Initial implementation for HIPAA healthcare compliance infrastructure
# REM: =======================================================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from core.audit import AuditEventType, audit
from core.rbac import Permission

logger = logging.getLogger(__name__)


@dataclass
class EmergencyAccessRequest:
    """
    REM: A break-the-glass emergency access request per 45 CFR 164.312(a)(2)(i).
    REM: Grants temporary elevated permissions when normal access is insufficient
    REM: for patient safety or operational continuity.
    """
    request_id: str
    user_id: str
    reason: str
    timestamp: datetime
    approved_by: Optional[str] = None
    expires_at: Optional[datetime] = None
    permissions_granted: Set[str] = field(default_factory=set)
    is_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "approved_by": self.approved_by,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "permissions_granted": sorted(list(self.permissions_granted)),
            "is_active": self.is_active
        }


class EmergencyAccessManager:
    """
    REM: Manages break-the-glass emergency access requests per HIPAA.
    REM: All emergency access events are audit-logged with SECURITY_ALERT.
    REM: Emergency access grants all Permission values from the RBAC module
    REM: for the duration of the emergency window.
    """

    def __init__(self):
        # REM: In-memory storage of emergency access requests
        self._requests: Dict[str, EmergencyAccessRequest] = {}
        # REM: Index of active emergencies by user_id for fast lookup
        self._active_by_user: Dict[str, str] = {}
        self._load_from_redis()

        logger.info("REM: EmergencyAccessManager initialized_Thank_You")

    def _load_from_redis(self) -> None:
        """REM: Load emergency access records from Redis on startup."""
        try:
            from core.persistence import security_store
            all_records = security_store.list_records("emergency")
            for request_id, record_data in all_records.items():
                try:
                    req = EmergencyAccessRequest(
                        request_id=record_data["request_id"],
                        user_id=record_data["user_id"],
                        reason=record_data["reason"],
                        timestamp=datetime.fromisoformat(record_data["timestamp"]),
                        approved_by=record_data.get("approved_by"),
                        expires_at=(
                            datetime.fromisoformat(record_data["expires_at"])
                            if record_data.get("expires_at") else None
                        ),
                        permissions_granted=set(record_data.get("permissions_granted", [])),
                        is_active=record_data.get("is_active", False),
                    )
                    self._requests[request_id] = req
                    if req.is_active:
                        self._active_by_user[req.user_id] = request_id
                except Exception as e:
                    logger.warning(
                        f"REM: Failed to load emergency record ::{request_id}:: from Redis: {e}_Thank_You_But_No"
                    )
            if all_records:
                logger.info(f"REM: Loaded {len(self._requests)} emergency records from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Redis unavailable for emergency access load: {e}_Thank_You_But_No")

    def _save_record(self, request_id: str) -> None:
        """REM: Write-through save of a single emergency access record to Redis."""
        try:
            from core.persistence import security_store
            request = self._requests.get(request_id)
            if not request:
                return
            data = {
                "request_id": request.request_id,
                "user_id": request.user_id,
                "reason": request.reason,
                "timestamp": request.timestamp.isoformat(),
                "approved_by": request.approved_by,
                "expires_at": request.expires_at.isoformat() if request.expires_at else None,
                "permissions_granted": list(request.permissions_granted),
                "is_active": request.is_active,
            }
            security_store.store_record("emergency", request_id, data)
        except Exception as e:
            logger.warning(f"REM: Failed to save emergency record to Redis for ::{request_id}::: {e}_Thank_You_But_No")

    def _get_all_permissions(self) -> Set[str]:
        """REM: Get all Permission values from the RBAC module for emergency elevation."""
        return {p.value for p in Permission}

    def _check_expiry(self, request: EmergencyAccessRequest) -> bool:
        """
        REM: Check if an emergency access request has expired.
        REM: Auto-deactivates expired requests.
        """
        if not request.is_active:
            return False

        now = datetime.now(timezone.utc)
        if request.expires_at and now > request.expires_at:
            # REM: Auto-expire the request
            request.is_active = False
            if request.user_id in self._active_by_user:
                del self._active_by_user[request.user_id]

            logger.warning(
                f"REM: Emergency access ::{request.request_id}:: for user "
                f"::{request.user_id}:: auto-expired_Thank_You"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Emergency access auto-expired: {request.request_id}",
                actor="system",
                resource=request.request_id,
                details={
                    "user_id": request.user_id,
                    "reason": request.reason,
                    "expired_at": request.expires_at.isoformat() if request.expires_at else None
                },
                qms_status="Thank_You"
            )

            return False  # REM: No longer active

        return True  # REM: Still active

    def request_emergency_access(
        self,
        user_id: str,
        reason: str,
        duration_minutes: int = 60
    ) -> EmergencyAccessRequest:
        """
        REM: Create a new break-the-glass emergency access request.
        REM: The request is created in a pending state (is_active=False)
        REM: and must be approved before permissions are granted.
        """
        request_id = f"emerg_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        request = EmergencyAccessRequest(
            request_id=request_id,
            user_id=user_id,
            reason=reason,
            timestamp=now,
            approved_by=None,
            expires_at=now + timedelta(minutes=duration_minutes),
            permissions_granted=set(),
            is_active=False
        )

        self._requests[request_id] = request
        self._save_record(request_id)

        logger.warning(
            f"REM: Emergency access REQUESTED - ::{request_id}:: "
            f"by user ::{user_id}:: reason ::{reason}:: "
            f"duration {duration_minutes} minutes_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Break-the-glass emergency access requested by {user_id}",
            actor=user_id,
            resource=request_id,
            details={
                "user_id": user_id,
                "reason": reason,
                "duration_minutes": duration_minutes,
                "expires_at": request.expires_at.isoformat() if request.expires_at else None
            },
            qms_status="Thank_You"
        )

        return request

    def approve_emergency_access(
        self,
        request_id: str,
        approved_by: str
    ) -> bool:
        """
        REM: Approve an emergency access request, granting elevated permissions.
        REM: All RBAC permissions are granted for the duration of the emergency.
        """
        request = self._requests.get(request_id)
        if not request:
            logger.warning(
                f"REM: Emergency access request ::{request_id}:: not found_Thank_You_But_No"
            )
            return False

        if request.is_active:
            logger.warning(
                f"REM: Emergency access ::{request_id}:: already active_Thank_You_But_No"
            )
            return False

        # REM: Grant all permissions for the emergency window
        request.approved_by = approved_by
        request.permissions_granted = self._get_all_permissions()
        request.is_active = True

        # REM: Track active emergency by user
        self._active_by_user[request.user_id] = request_id
        self._save_record(request_id)

        logger.warning(
            f"REM: Emergency access APPROVED - ::{request_id}:: "
            f"for user ::{request.user_id}:: approved by ::{approved_by}:: "
            f"— ALL permissions granted_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Break-the-glass emergency access APPROVED for {request.user_id}",
            actor=approved_by,
            resource=request_id,
            details={
                "user_id": request.user_id,
                "approved_by": approved_by,
                "reason": request.reason,
                "permissions_granted": sorted(list(request.permissions_granted)),
                "expires_at": request.expires_at.isoformat() if request.expires_at else None
            },
            qms_status="Thank_You"
        )

        return True

    def revoke_emergency_access(
        self,
        request_id: str,
        revoked_by: str
    ) -> bool:
        """
        REM: Revoke an active emergency access request immediately.
        REM: Security officers can revoke emergency access at any time.
        """
        request = self._requests.get(request_id)
        if not request:
            logger.warning(
                f"REM: Emergency access request ::{request_id}:: not found_Thank_You_But_No"
            )
            return False

        if not request.is_active:
            logger.warning(
                f"REM: Emergency access ::{request_id}:: is not active_Thank_You_But_No"
            )
            return False

        # REM: Deactivate and remove from active index
        request.is_active = False
        request.permissions_granted = set()
        if request.user_id in self._active_by_user:
            del self._active_by_user[request.user_id]
        self._save_record(request_id)

        logger.warning(
            f"REM: Emergency access REVOKED - ::{request_id}:: "
            f"for user ::{request.user_id}:: revoked by ::{revoked_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Break-the-glass emergency access REVOKED for {request.user_id}",
            actor=revoked_by,
            resource=request_id,
            details={
                "user_id": request.user_id,
                "revoked_by": revoked_by,
                "reason": request.reason,
                "original_approved_by": request.approved_by
            },
            qms_status="Thank_You"
        )

        return True

    def is_emergency_active(self, user_id: str) -> bool:
        """
        REM: Check if a user currently has active emergency access.
        REM: Performs auto-expiry check before returning status.
        """
        request_id = self._active_by_user.get(user_id)
        if not request_id:
            return False

        request = self._requests.get(request_id)
        if not request:
            return False

        # REM: Check expiry — may auto-deactivate
        return self._check_expiry(request)

    def get_active_emergencies(self) -> List[EmergencyAccessRequest]:
        """
        REM: Get all currently active emergency access requests.
        REM: Performs expiry check on each request before including it.
        """
        active = []
        for request_id in list(self._active_by_user.values()):
            request = self._requests.get(request_id)
            if request and self._check_expiry(request):
                active.append(request)
        return active

    def get_request(self, request_id: str) -> Optional[EmergencyAccessRequest]:
        """REM: Get an emergency access request by ID."""
        return self._requests.get(request_id)

    def list_all_requests(self) -> List[Dict[str, Any]]:
        """REM: List all emergency access requests for audit review."""
        return [r.to_dict() for r in self._requests.values()]


# REM: Global instance for import throughout the application
emergency_access_manager = EmergencyAccessManager()
