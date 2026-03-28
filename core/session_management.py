# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# ClawFilters/core/session_management.py
# REM: =======================================================================================
# REM: HIPAA SESSION MANAGEMENT — AUTOMATIC LOGOFF
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.3.0CC: New feature - HIPAA 45 CFR 164.312(a)(2)(iii) Automatic Logoff
#
# REM: Mission Statement: Enforce automatic session termination after periods of inactivity.
# REM: Healthcare systems must protect ePHI by ensuring unattended workstations do not
# REM: remain logged in. This module provides configurable idle timeouts, maximum session
# REM: durations, and role-based timeout policies.
#
# REM: Features:
# REM:   - Configurable idle timeout (default 15 minutes, 10 for privileged roles)
# REM:   - Maximum session duration (default 8 hours)
# REM:   - Pre-logoff warning window
# REM:   - Role-based idle timeout overrides
# REM:   - Bulk expired session cleanup
# REM:   - Full audit trail of session lifecycle events
# REM: =======================================================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


# REM: Privileged roles that get shorter idle timeouts
PRIVILEGED_ROLES = {"admin", "security_officer", "super_admin"}
PRIVILEGED_IDLE_MINUTES = 10

# REM: All valid roles — role claims outside this set are rejected (H5 fix)
VALID_ROLES = {"viewer", "operator", "admin", "security_officer", "super_admin"}


@dataclass
class SessionConfig:
    """
    REM: Configuration for session management policies.
    REM: Defaults align with HIPAA automatic logoff requirements.
    """
    max_idle_minutes: int = 15
    max_session_hours: int = 8
    warning_before_logoff_seconds: int = 60
    require_reauth_for_phi: bool = True


@dataclass
class UserSession:
    """
    REM: Represents an active user session with tracking metadata.
    REM: Each session is uniquely identified and tracks activity timestamps.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    role: str = "operator"
    mfa_verified: bool = False

    def to_dict(self) -> dict:
        """REM: v7.2.0CC: Convert to dictionary for JSON serialization in routes."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_active": self.is_active,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "role": self.role,
            "mfa_verified": self.mfa_verified,
        }


class SessionManager:
    """
    REM: Manages user sessions with HIPAA-compliant automatic logoff.
    REM: Enforces idle timeouts, maximum session durations, and role-based
    REM: timeout policies. All session lifecycle events are audit-logged.
    """

    def __init__(self, config: Optional[SessionConfig] = None):
        self._config = config or SessionConfig()
        self._sessions: Dict[str, UserSession] = {}
        self._load_from_redis()
        logger.info("REM: SessionManager initialized with idle=%d min, max=%d hrs_Thank_You",
                     self._config.max_idle_minutes, self._config.max_session_hours)

    def _get_session_from_redis(self, session_id: str) -> Optional["UserSession"]:
        """REM: Load a single session directly from Redis (cross-worker lookup)."""
        try:
            from core.persistence import security_store
            data = security_store.get_record("sessions", session_id)
            if not data:
                return None
            return UserSession(
                session_id=data["session_id"],
                user_id=data["user_id"],
                created_at=datetime.fromisoformat(data["created_at"]),
                last_activity=datetime.fromisoformat(data["last_activity"]),
                expires_at=datetime.fromisoformat(data["expires_at"]),
                is_active=data.get("is_active", True),
                ip_address=data.get("ip_address"),
                user_agent=data.get("user_agent"),
                role=data.get("role", "operator"),
                mfa_verified=data.get("mfa_verified", False),
            )
        except Exception as e:
            logger.warning(
                f"REM: Failed to load session ::{session_id}:: from Redis: {e}_Thank_You_But_No"
            )
            return None

    def _get_user_session_ids_from_redis(self, user_id: str) -> set:
        """REM: Return all session IDs for a user from the Redis index (all workers)."""
        try:
            from core.persistence import security_store
            return security_store.get_set_members(f"user_sessions:{user_id}")
        except Exception as e:
            logger.warning(
                f"REM: Failed to get user session index from Redis: {e}_Thank_You_But_No"
            )
            return set()

    def _load_from_redis(self) -> None:
        """REM: Load session records from Redis on startup. In-memory dict is a local cache."""
        try:
            from core.persistence import security_store
            all_records = security_store.list_records("sessions")
            for session_id, record_data in all_records.items():
                try:
                    session = UserSession(
                        session_id=record_data["session_id"],
                        user_id=record_data["user_id"],
                        created_at=datetime.fromisoformat(record_data["created_at"]),
                        last_activity=datetime.fromisoformat(record_data["last_activity"]),
                        expires_at=datetime.fromisoformat(record_data["expires_at"]),
                        is_active=record_data.get("is_active", True),
                        ip_address=record_data.get("ip_address"),
                        user_agent=record_data.get("user_agent"),
                        role=record_data.get("role", "operator"),
                    )
                    self._sessions[session_id] = session
                except Exception as e:
                    logger.warning(
                        f"REM: Failed to load session ::{session_id}:: from Redis: {e}_Thank_You_But_No"
                    )
            if all_records:
                logger.info(f"REM: Loaded {len(self._sessions)} sessions from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Redis unavailable for session load: {e}_Thank_You_But_No")

    def _save_record(self, session_id: str) -> None:
        """REM: Write-through save of a single session record to Redis."""
        try:
            from core.persistence import security_store
            session = self._sessions.get(session_id)
            if not session:
                return
            data = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "is_active": session.is_active,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "role": session.role,
                "mfa_verified": session.mfa_verified,
            }
            security_store.store_record("sessions", session_id, data)
            # REM: Maintain user session index
            security_store.add_to_set(f"user_sessions:{session.user_id}", session_id)
        except Exception as e:
            logger.warning(f"REM: Failed to save session to Redis for ::{session_id}::: {e}_Thank_You_But_No")

    def _delete_record(self, session_id: str, user_id: str) -> None:
        """REM: Delete a session record from Redis and remove from user index."""
        try:
            from core.persistence import security_store
            security_store.delete_record("sessions", session_id)
            security_store.remove_from_set(f"user_sessions:{user_id}", session_id)
        except Exception as e:
            logger.warning(f"REM: Failed to delete session from Redis for ::{session_id}::: {e}_Thank_You_But_No")

    def _get_idle_timeout(self, role: str) -> timedelta:
        """REM: Return idle timeout based on role. Privileged roles get shorter timeouts."""
        if role.lower() in PRIVILEGED_ROLES:
            return timedelta(minutes=PRIVILEGED_IDLE_MINUTES)
        return timedelta(minutes=self._config.max_idle_minutes)

    def create_session(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        role: str = "operator"
    ) -> UserSession:
        """
        REM: Create a new authenticated session for a user.

        Args:
            user_id: Unique identifier of the authenticated user
            ip_address: Optional originating IP address
            user_agent: Optional browser/client user agent string
            role: User role for idle timeout policy

        Returns:
            UserSession with generated session_id and expiry
        """
        # REM: Validate role against known valid values — reject untrusted caller-supplied roles (H5 fix)
        if role not in VALID_ROLES:
            logger.warning(
                f"REM: Invalid role ::{role}:: rejected in create_session for ::{user_id}::, "
                f"defaulting to 'operator'_Thank_You_But_No"
            )
            role = "operator"

        now = datetime.now(timezone.utc)
        session = UserSession(
            user_id=user_id,
            created_at=now,
            last_activity=now,
            expires_at=now + timedelta(hours=self._config.max_session_hours),
            is_active=True,
            ip_address=ip_address,
            user_agent=user_agent,
            role=role
        )
        self._sessions[session.session_id] = session

        audit.log(
            AuditEventType.AUTH_SUCCESS,
            f"Session created for ::{user_id}:: - ID ::{session.session_id}::",
            actor=user_id,
            resource=session.session_id,
            details={"ip_address": ip_address, "user_agent": user_agent, "role": role},
            qms_status="Thank_You"
        )
        logger.info("REM: Session ::%s:: created for user ::%s::_Thank_You",
                     session.session_id, user_id)
        self._save_record(session.session_id)
        return session

    def touch_session(self, session_id: str) -> bool:
        """
        REM: Update last_activity timestamp to prevent idle timeout.

        Args:
            session_id: Session to refresh

        Returns:
            True if session was active and updated, False otherwise
        """
        session = self._sessions.get(session_id)
        if session is None:
            # REM: Session may exist on another worker — check Redis
            session = self._get_session_from_redis(session_id)
            if session:
                self._sessions[session_id] = session
        if not session or not session.is_active:
            return False

        session.last_activity = datetime.now(timezone.utc)
        self._save_record(session_id)
        return True

    def check_session(self, session_id: str) -> bool:
        """
        REM: Validate that a session is still active, not expired, and not idle.
        REM: Automatically terminates sessions that have exceeded their limits.
        REM: Falls back to Redis on cache miss — handles sessions created on other workers.

        Args:
            session_id: Session to validate

        Returns:
            True if session is valid, False if expired/idle/terminated
        """
        session = self._sessions.get(session_id)
        if session is None:
            # REM: Not in local cache — another worker may have created this session
            session = self._get_session_from_redis(session_id)
            if session:
                self._sessions[session_id] = session
        if not session or not session.is_active:
            return False

        now = datetime.now(timezone.utc)

        # REM: Check absolute session expiry
        if now >= session.expires_at:
            self.terminate_session(session_id, reason="max_duration_exceeded")
            return False

        # REM: Check idle timeout (role-based)
        idle_timeout = self._get_idle_timeout(session.role)
        idle_since = now - session.last_activity
        if idle_since >= idle_timeout:
            self.terminate_session(session_id, reason="idle_timeout")
            return False

        return True

    def set_mfa_verified(self, session_id: str) -> bool:
        """REM: Mark a session as MFA-verified and persist to Redis.
        REM: L11 fix: previously mfa_verified was set in-memory only and never saved."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.mfa_verified = True
        self._save_record(session_id)
        return True

    def terminate_session(self, session_id: str, reason: str = "manual") -> bool:
        """
        REM: Terminate a specific session.

        Args:
            session_id: Session to terminate
            reason: Reason for termination (manual, idle_timeout, max_duration_exceeded)

        Returns:
            True if session was found and terminated, False if not found
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        was_active = session.is_active
        session.is_active = False

        if was_active:
            audit.log(
                AuditEventType.AUTH_SESSION_TERMINATED,
                f"Session terminated for ::{session.user_id}:: - Reason: ::{reason}::",
                actor=session.user_id,
                resource=session_id,
                details={"reason": reason, "session_duration_seconds": (
                    datetime.now(timezone.utc) - session.created_at
                ).total_seconds()},
                qms_status="Thank_You" if reason == "manual" else "Thank_You_But_No"
            )
            logger.info("REM: Session ::%s:: terminated - reason: ::%s::_Thank_You",
                         session_id, reason)

        self._save_record(session_id)
        self._delete_record(session_id, session.user_id)
        # REM: Remove from local cache — prevents memory leak and ensures cross-worker
        # REM: consistency (a session terminated here is gone, not just marked inactive)
        self._sessions.pop(session_id, None)

        return was_active

    def terminate_all_user_sessions(self, user_id: str, reason: str = "manual") -> int:
        """
        REM: Terminate all active sessions for a specific user across all workers.
        REM: Combines local cache and Redis index so sessions on other workers are caught.

        Args:
            user_id: User whose sessions should be terminated
            reason: Reason for bulk termination

        Returns:
            Number of sessions terminated
        """
        # REM: Collect from local cache
        local_ids = {
            sid for sid, s in self._sessions.items()
            if s.user_id == user_id and s.is_active
        }
        # REM: Collect from Redis index — covers sessions created on other workers
        redis_ids = self._get_user_session_ids_from_redis(user_id)
        all_ids = local_ids | redis_ids

        count = 0
        for sid in all_ids:
            if self.terminate_session(sid, reason=reason):
                count += 1

        if count > 0:
            logger.info("REM: Terminated %d sessions for user ::%s:: - reason: ::%s::_Thank_You",
                         count, user_id, reason)
        return count

    def get_session(self, session_id: str) -> Optional[UserSession]:
        """
        REM: v7.2.0CC: Retrieve a specific session by ID.
        REM: Falls back to Redis on cache miss for cross-worker consistency.
        """
        session = self._sessions.get(session_id)
        if session is None:
            session = self._get_session_from_redis(session_id)
            if session:
                self._sessions[session_id] = session
        return session

    def get_active_sessions(self, user_id: Optional[str] = None) -> List[UserSession]:
        """
        REM: List active sessions, optionally filtered by user.

        Args:
            user_id: Optional filter by user ID

        Returns:
            List of active UserSession objects
        """
        sessions = [s for s in self._sessions.values() if s.is_active]
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        return sessions

    def cleanup_expired(self) -> int:
        """
        REM: Bulk cleanup of all expired and idle sessions.
        REM: Intended to be called periodically by a background task.

        Returns:
            Number of sessions cleaned up
        """
        count = 0
        now = datetime.now(timezone.utc)

        for sid, session in list(self._sessions.items()):
            if not session.is_active:
                continue

            idle_timeout = self._get_idle_timeout(session.role)
            idle_since = now - session.last_activity
            expired = now >= session.expires_at
            idle = idle_since >= idle_timeout

            if expired:
                self.terminate_session(sid, reason="max_duration_exceeded")
                count += 1
            elif idle:
                self.terminate_session(sid, reason="idle_timeout")
                count += 1

        if count > 0:
            logger.info("REM: Cleanup removed %d expired/idle sessions_Thank_You", count)
        return count


# REM: Global session manager instance
session_manager = SessionManager()
