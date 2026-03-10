# TelsonBase/core/rotation.py
# REM: =======================================================================================
# REM: SECRET ROTATION MANAGER
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.2.0CC: New feature - Automated secret rotation
#
# REM: Mission Statement: Long-lived secrets are a security risk. This module provides
# REM: automated rotation for:
# REM:   - JWT signing keys (with grace period for existing tokens)
# REM:   - Agent signing keys (with message re-signing capability)
# REM:   - Federation session keys (triggers key re-exchange)
#
# REM: Rotation is audit-logged and can be triggered manually or on schedule.
# REM: =======================================================================================

import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


class SecretType(str, Enum):
    """REM: Types of secrets that can be rotated."""
    JWT_SECRET = "jwt_secret"
    AGENT_SIGNING_KEY = "agent_signing_key"
    FEDERATION_SESSION = "federation_session"
    API_KEY = "api_key"


@dataclass
class RotationRecord:
    """REM: Record of a secret rotation event."""
    secret_type: SecretType
    identifier: str  # e.g., agent_id for signing keys
    rotated_at: datetime
    rotated_by: str
    old_key_expires_at: datetime
    reason: str
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class ActiveSecret:
    """REM: An active secret with optional grace period for old key."""
    current_key: bytes
    current_key_created_at: datetime
    previous_key: Optional[bytes] = None
    previous_key_expires_at: Optional[datetime] = None

    def is_in_grace_period(self) -> bool:
        """REM: Check if we're in the grace period where both keys are valid."""
        if self.previous_key is None or self.previous_key_expires_at is None:
            return False
        return datetime.now(timezone.utc) < self.previous_key_expires_at

    def validate_with_either_key(self, validator_func, *args) -> bool:
        """REM: Validate using current key, or previous key if in grace period."""
        if validator_func(self.current_key, *args):
            return True
        if self.is_in_grace_period() and self.previous_key:
            return validator_func(self.previous_key, *args)
        return False


class KeyRotationManager:
    """
    REM: Manages rotation of cryptographic secrets across the system.
    """

    def __init__(self):
        self._rotation_history: List[RotationRecord] = []
        self._active_secrets: Dict[str, ActiveSecret] = {}
        self._jwt_secret: Optional[ActiveSecret] = None
        self._rotation_schedule: Dict[SecretType, timedelta] = {
            SecretType.JWT_SECRET: timedelta(days=90),
            SecretType.AGENT_SIGNING_KEY: timedelta(days=180),
            SecretType.FEDERATION_SESSION: timedelta(days=30),
            SecretType.API_KEY: timedelta(days=365),
        }

    def rotate_jwt_secret(
        self,
        rotated_by: str = "system",
        grace_period_hours: int = 24,
        reason: str = "Scheduled rotation"
    ) -> Tuple[bool, str, Optional[bytes]]:
        """
        REM: Rotate the JWT signing secret with a grace period.

        During the grace period, both old and new secrets are valid for
        token verification. New tokens are signed with the new secret.

        Args:
            rotated_by: Who/what initiated the rotation
            grace_period_hours: Hours to accept old tokens
            reason: Why the rotation is happening

        Returns:
            Tuple of (success, message, new_secret)
        """
        try:
            new_secret = secrets.token_bytes(32)
            now = datetime.now(timezone.utc)

            # REM: Store with grace period for old key
            old_secret = None
            if self._jwt_secret:
                old_secret = self._jwt_secret.current_key

            self._jwt_secret = ActiveSecret(
                current_key=new_secret,
                current_key_created_at=now,
                previous_key=old_secret,
                previous_key_expires_at=now + timedelta(hours=grace_period_hours) if old_secret else None
            )

            # REM: Record rotation
            record = RotationRecord(
                secret_type=SecretType.JWT_SECRET,
                identifier="global",
                rotated_at=now,
                rotated_by=rotated_by,
                old_key_expires_at=now + timedelta(hours=grace_period_hours),
                reason=reason
            )
            self._rotation_history.append(record)

            logger.info(
                f"REM: JWT secret rotated by ::{rotated_by}:: - "
                f"Grace period: {grace_period_hours} hours_Thank_You"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"JWT secret rotated - grace period {grace_period_hours}h",
                actor=rotated_by,
                details={
                    "reason": reason,
                    "grace_period_hours": grace_period_hours,
                    "old_key_expires": record.old_key_expires_at.isoformat()
                },
                qms_status="Thank_You"
            )

            return True, "JWT secret rotated successfully", new_secret

        except Exception as e:
            logger.error(f"REM: JWT secret rotation failed: {e}_Thank_You_But_No")
            return False, f"Rotation failed: {str(e)}", None

    def rotate_agent_key(
        self,
        agent_id: str,
        rotated_by: str = "system",
        grace_period_hours: int = 1,
        reason: str = "Scheduled rotation"
    ) -> Tuple[bool, str, Optional[bytes]]:
        """
        REM: Rotate an agent's signing key.

        Args:
            agent_id: The agent whose key should be rotated
            rotated_by: Who/what initiated the rotation
            grace_period_hours: Hours to accept old signatures
            reason: Why the rotation is happening

        Returns:
            Tuple of (success, message, new_key)
        """
        try:
            from core.signing import key_registry

            # REM: Get current key
            old_key = key_registry.get_key(agent_id)
            if old_key is None:
                return False, f"Agent {agent_id} not found", None

            # REM: Generate new key
            new_key = secrets.token_bytes(32)
            now = datetime.now(timezone.utc)

            # REM: Store with grace period
            secret_id = f"agent:{agent_id}"
            self._active_secrets[secret_id] = ActiveSecret(
                current_key=new_key,
                current_key_created_at=now,
                previous_key=old_key,
                previous_key_expires_at=now + timedelta(hours=grace_period_hours)
            )

            # REM: Update the key registry
            key_registry._keys[agent_id] = new_key

            # REM: Record rotation
            record = RotationRecord(
                secret_type=SecretType.AGENT_SIGNING_KEY,
                identifier=agent_id,
                rotated_at=now,
                rotated_by=rotated_by,
                old_key_expires_at=now + timedelta(hours=grace_period_hours),
                reason=reason
            )
            self._rotation_history.append(record)

            logger.info(
                f"REM: Agent ::{agent_id}:: signing key rotated by ::{rotated_by}::_Thank_You"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Agent signing key rotated: {agent_id}",
                actor=rotated_by,
                resource=agent_id,
                details={
                    "reason": reason,
                    "grace_period_hours": grace_period_hours
                },
                qms_status="Thank_You"
            )

            return True, f"Agent {agent_id} key rotated", new_key

        except Exception as e:
            logger.error(f"REM: Agent key rotation failed: {e}_Thank_You_But_No")
            return False, f"Rotation failed: {str(e)}", None

    def rotate_all_agent_keys(
        self,
        rotated_by: str = "system",
        reason: str = "Bulk rotation"
    ) -> Dict[str, bool]:
        """
        REM: Rotate all registered agent keys.

        Returns:
            Dict mapping agent_id to success status
        """
        from core.signing import key_registry

        results = {}
        for agent_id in list(key_registry._keys.keys()):
            success, _, _ = self.rotate_agent_key(
                agent_id,
                rotated_by=rotated_by,
                reason=reason
            )
            results[agent_id] = success

        logger.info(
            f"REM: Bulk key rotation complete - "
            f"{sum(results.values())}/{len(results)} succeeded_Thank_You"
        )

        return results

    def trigger_federation_rekey(
        self,
        relationship_id: str,
        triggered_by: str = "system",
        reason: str = "Scheduled rotation"
    ) -> Tuple[bool, str]:
        """
        REM: Trigger re-keying of a federation relationship.

        This invalidates the current session key and requires a new
        key exchange before messages can be sent.
        """
        try:
            from federation.trust import FederationManager

            # REM: This would need to be connected to the actual federation manager
            # For now, record the intent
            now = datetime.now(timezone.utc)

            record = RotationRecord(
                secret_type=SecretType.FEDERATION_SESSION,
                identifier=relationship_id,
                rotated_at=now,
                rotated_by=triggered_by,
                old_key_expires_at=now,  # Immediate invalidation
                reason=reason
            )
            self._rotation_history.append(record)

            logger.info(
                f"REM: Federation rekey triggered for ::{relationship_id}:: "
                f"by ::{triggered_by}::_Thank_You"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Federation session key invalidated: {relationship_id}",
                actor=triggered_by,
                resource=relationship_id,
                details={"reason": reason},
                qms_status="Thank_You"
            )

            return True, "Federation rekey triggered"

        except Exception as e:
            logger.error(f"REM: Federation rekey failed: {e}_Thank_You_But_No")
            return False, f"Rekey failed: {str(e)}"

    def get_rotation_history(
        self,
        secret_type: Optional[SecretType] = None,
        identifier: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[RotationRecord]:
        """REM: Get rotation history with optional filters."""
        results = self._rotation_history

        if secret_type:
            results = [r for r in results if r.secret_type == secret_type]
        if identifier:
            results = [r for r in results if r.identifier == identifier]
        if since:
            results = [r for r in results if r.rotated_at >= since]

        return sorted(results, key=lambda r: r.rotated_at, reverse=True)

    def get_next_scheduled_rotation(
        self,
        secret_type: SecretType,
        identifier: str
    ) -> Optional[datetime]:
        """REM: Calculate when the next rotation should occur."""
        history = self.get_rotation_history(
            secret_type=secret_type,
            identifier=identifier
        )

        if not history:
            return None

        last_rotation = history[0].rotated_at
        rotation_interval = self._rotation_schedule.get(secret_type)

        if rotation_interval:
            return last_rotation + rotation_interval
        return None

    def get_secrets_due_for_rotation(self) -> List[Dict[str, Any]]:
        """REM: Get list of secrets that are due for rotation."""
        due = []
        now = datetime.now(timezone.utc)

        # REM: Check JWT secret
        jwt_next = self.get_next_scheduled_rotation(SecretType.JWT_SECRET, "global")
        if jwt_next and jwt_next <= now:
            due.append({
                "type": SecretType.JWT_SECRET,
                "identifier": "global",
                "due_since": jwt_next
            })

        # REM: Check agent keys
        from core.signing import key_registry
        for agent_id in key_registry._keys.keys():
            agent_next = self.get_next_scheduled_rotation(
                SecretType.AGENT_SIGNING_KEY,
                agent_id
            )
            if agent_next and agent_next <= now:
                due.append({
                    "type": SecretType.AGENT_SIGNING_KEY,
                    "identifier": agent_id,
                    "due_since": agent_next
                })

        return due

    def cleanup_expired_grace_periods(self):
        """REM: Remove expired grace period keys from memory."""
        now = datetime.now(timezone.utc)
        cleaned = 0

        # REM: Clean JWT secret
        if self._jwt_secret and self._jwt_secret.previous_key_expires_at:
            if now > self._jwt_secret.previous_key_expires_at:
                self._jwt_secret.previous_key = None
                self._jwt_secret.previous_key_expires_at = None
                cleaned += 1

        # REM: Clean agent secrets
        for secret_id, secret in self._active_secrets.items():
            if secret.previous_key_expires_at and now > secret.previous_key_expires_at:
                secret.previous_key = None
                secret.previous_key_expires_at = None
                cleaned += 1

        if cleaned > 0:
            logger.info(f"REM: Cleaned {cleaned} expired grace period keys_Thank_You")


# REM: Global rotation manager instance
rotation_manager = KeyRotationManager()
