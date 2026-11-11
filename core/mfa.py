# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
# TelsonBase/core/mfa.py
# REM: =======================================================================================
# REM: TOTP MULTI-FACTOR AUTHENTICATION MODULE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v5.3.0CC: New feature - TOTP MFA for operator authentication
#
# REM: Mission Statement: Enforce zero-trust multi-factor authentication for human operators.
# REM: Privileged roles (Admin, Security Officer, Super Admin) MUST complete MFA before
# REM: accessing protected resources. Uses RFC 6238 TOTP with backup recovery codes.
#
# REM: Features:
# REM:   - TOTP enrollment with provisioning URI for QR code scanning
# REM:   - Constant-time token verification (replay-safe)
# REM:   - One-time backup codes for account recovery
# REM:   - Role-based MFA requirement enforcement
# REM:   - Full audit trail for all MFA state changes
# REM: =======================================================================================

import hmac
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pyotp

from core.audit import AuditEventType, audit
from core.rbac import Role, User

logger = logging.getLogger(__name__)


@dataclass
class MFARecord:
    """REM: Stores TOTP enrollment state for a single user."""
    user_id: str
    secret: str
    backup_codes: List[str]
    enrolled_at: datetime
    last_used_token: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    is_active: bool = True


class MFAManager:
    """
    REM: Manages TOTP multi-factor authentication for operators.
    REM: In-memory storage, composable with RBACManager.
    """

    # REM: Roles that require MFA enrollment
    MFA_REQUIRED_ROLES = {Role.ADMIN, Role.SECURITY_OFFICER, Role.SUPER_ADMIN}

    # REM: Number of one-time backup codes generated during enrollment
    BACKUP_CODE_COUNT = 10

    # REM: Backup code length in hex characters (8 hex chars = 4 bytes of entropy)
    BACKUP_CODE_LENGTH = 8

    def __init__(self):
        self._records: Dict[str, MFARecord] = {}
        self._local_failures: Dict[str, tuple] = {}  # user_id -> (count, window end)
        self._load_from_redis()

    @staticmethod
    def _record_from_data(record_data: Dict[str, Any]) -> Optional[MFARecord]:
        """REM: Build an MFARecord from its stored form. None if it cannot be decrypted."""
        from core.secure_storage import secure_storage
        record_data = dict(record_data)
        if record_data.get("_encrypted"):
            try:
                record_data["secret"] = secure_storage.decrypt_string(record_data["secret"])
                record_data["backup_codes"] = json.loads(secure_storage.decrypt_string(record_data["backup_codes"]))
            except Exception:
                return None  # Skip records we can't decrypt
        return MFARecord(
            user_id=record_data["user_id"],
            secret=record_data["secret"],
            backup_codes=record_data.get("backup_codes", []),
            enrolled_at=datetime.fromisoformat(record_data["enrolled_at"]),
            last_used_token=record_data.get("last_used_token"),
            last_verified_at=(
                datetime.fromisoformat(record_data["last_verified_at"])
                if record_data.get("last_verified_at") else None
            ),
            is_active=record_data.get("is_active", True),
        )

    def _load_from_redis(self) -> None:
        """REM: Load MFA records from Redis on startup."""
        try:
            from core.persistence import security_store
            all_records = security_store.list_records("mfa")
            for user_id, record_data in all_records.items():
                try:
                    rec = self._record_from_data(record_data)
                    if rec is not None:
                        self._records[user_id] = rec
                except Exception as e:
                    logger.warning(
                        f"REM: Failed to load MFA record for ::{user_id}:: from Redis: {e}_Thank_You_But_No"
                    )
            if all_records:
                logger.info(f"REM: Loaded {len(self._records)} MFA records from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Redis unavailable for MFA load: {e}_Thank_You_But_No")

    def _get_record(self, user_id: str) -> Optional[MFARecord]:
        """
        REM: 2026-11-11 — Current record for a user, Redis first.
        REM: With more than one worker (the image default is two; docker-compose.yml pins
        REM: one) an enrolment made on one worker was invisible to the others, which kept
        REM: answering from the copy they loaded at start-up. The
        REM: in-memory copy is now only a fallback for when Redis has no record or is down.
        REM: A disabled enrolment is kept in Redis as an inactive record so that the other
        REM: worker learns about the disable as well.
        """
        try:
            from core.persistence import security_store
            data = security_store.get_record("mfa", user_id)
            if data:
                rec = self._record_from_data(data)
                if rec is not None:
                    self._records[user_id] = rec
                    return rec
        except Exception as e:
            logger.warning(f"REM: MFA record refresh failed for ::{user_id}::: {e}_Thank_You_But_No")
        return self._records.get(user_id)

    # REM: ---------------------------------------------------------------------------------
    # REM: Attempt limit for second-factor codes (shared across workers, in-memory fallback)
    # REM: ---------------------------------------------------------------------------------
    MAX_FAILED_CODES = 5
    CODE_LOCKOUT_SECONDS = 15 * 60

    def _fail_key(self, user_id: str) -> str:
        from core.persistence import security_store
        return security_store._key("mfa_failures", user_id)

    def is_locked(self, user_id: str) -> bool:
        """REM: True if too many wrong codes were entered for this user recently."""
        try:
            from core.persistence import security_store
            value = security_store.client.get(self._fail_key(user_id))
            if value is not None:
                return int(value) >= self.MAX_FAILED_CODES
        except Exception:
            pass
        count, until = self._local_failures.get(user_id, (0, None))
        if until and datetime.now(timezone.utc) >= until:
            self._local_failures.pop(user_id, None)
            return False
        return count >= self.MAX_FAILED_CODES

    def _record_failed_code(self, user_id: str) -> None:
        from datetime import timedelta
        count, until = self._local_failures.get(user_id, (0, None))
        now = datetime.now(timezone.utc)
        if until is None or now >= until:
            count, until = 0, now + timedelta(seconds=self.CODE_LOCKOUT_SECONDS)
        self._local_failures[user_id] = (count + 1, until)
        try:
            from core.persistence import security_store
            key = self._fail_key(user_id)
            shared = security_store.client.incr(key)
            if shared == 1 or security_store.client.ttl(key) < 0:
                security_store.client.expire(key, self.CODE_LOCKOUT_SECONDS)
            count = max(count + 1, int(shared))
        except Exception:
            count = count + 1
        if count == self.MAX_FAILED_CODES:
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"MFA code entry locked for user: {user_id}",
                actor=user_id,
                resource=user_id,
                details={"action": "mfa_locked", "failed_codes": count,
                         "lockout_seconds": self.CODE_LOCKOUT_SECONDS},
                qms_status="Thank_You_But_No"
            )

    def _clear_failed_codes(self, user_id: str) -> None:
        self._local_failures.pop(user_id, None)
        try:
            from core.persistence import security_store
            security_store.client.delete(self._fail_key(user_id))
        except Exception:
            pass

    @staticmethod
    def _same(a: str, b: str) -> bool:
        """REM: Constant-time comparison on bytes (compare_digest rejects non-ASCII str)."""
        if not isinstance(a, str) or not isinstance(b, str):
            return False
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

    def _save_record(self, user_id: str) -> None:
        """REM: Write-through save of a single MFA record to Redis."""
        try:
            from core.persistence import security_store
            from core.secure_storage import secure_storage
            record = self._records.get(user_id)
            if not record:
                return
            data = {
                "user_id": record.user_id,
                "secret": record.secret,
                "backup_codes": record.backup_codes,
                "enrolled_at": record.enrolled_at.isoformat(),
                "last_used_token": record.last_used_token,
                "last_verified_at": (
                    record.last_verified_at.isoformat()
                    if record.last_verified_at else None
                ),
                "is_active": record.is_active,
            }
            # REM: Encrypt sensitive fields before storing — fail-hard, never store plaintext
            data["secret"] = secure_storage.encrypt_string(data["secret"])
            data["backup_codes"] = secure_storage.encrypt_string(json.dumps(data["backup_codes"]))
            data["_encrypted"] = True
            security_store.store_record("mfa", user_id, data)
        except Exception as e:
            logger.warning(f"REM: Failed to save MFA record to Redis for ::{user_id}::: {e}_Thank_You_But_No")

    def _delete_record(self, user_id: str) -> None:
        """REM: Delete a single MFA record from Redis."""
        try:
            from core.persistence import security_store
            security_store.delete_record("mfa", user_id)
        except Exception as e:
            logger.warning(f"REM: Failed to delete MFA record from Redis for ::{user_id}::: {e}_Thank_You_But_No")

    def enroll_mfa(self, user_id: str, username: str, replace: bool = False) -> Dict[str, Any]:
        """
        REM: Enroll a user in TOTP MFA.
        REM: Generates a secret, provisioning URI, and backup codes.

        Args:
            user_id: The user's unique identifier
            username: The user's display name (used in provisioning URI)

        Returns:
            Dict with secret, provisioning_uri, and backup_codes
        """
        # REM: An active enrolment is not replaced unless the caller says so explicitly.
        # REM: Replacing it swaps the user's authenticator secret and backup codes; the
        # REM: supported path is disable_mfa (which is audited) followed by a new enrolment.
        if not replace and self.is_enrolled(user_id):
            raise ValueError("MFA is already enrolled for this user. Disable it before enrolling again.")

        # REM: Generate a fresh TOTP secret
        secret = pyotp.random_base32()

        # REM: Build provisioning URI for QR code scanning
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=username,
            issuer_name="TelsonBase"
        )

        # REM: Generate one-time backup codes using cryptographic randomness
        backup_codes = [
            secrets.token_hex(self.BACKUP_CODE_LENGTH // 2)
            for _ in range(self.BACKUP_CODE_COUNT)
        ]

        now = datetime.now(timezone.utc)

        record = MFARecord(
            user_id=user_id,
            secret=secret,
            backup_codes=list(backup_codes),
            enrolled_at=now,
            is_active=True
        )

        self._records[user_id] = record

        logger.info(
            f"REM: MFA enrolled for user ::{user_id}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"MFA enrolled for user: {user_id}",
            actor=user_id,
            resource=user_id,
            details={"action": "mfa_enroll", "backup_codes_generated": len(backup_codes)},
            qms_status="Thank_You"
        )

        self._save_record(user_id)
        self._clear_failed_codes(user_id)

        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "backup_codes": backup_codes
        }

    def verify_mfa(self, user_id: str, token: str) -> bool:
        """
        REM: Verify a 6-digit TOTP token for a user.
        REM: Uses constant-time comparison and replay prevention.

        Args:
            user_id: The user's unique identifier
            token: The 6-digit TOTP token to verify

        Returns:
            True if the token is valid and has not been replayed
        """
        record = self._get_record(user_id)
        if not record or not record.is_active:
            logger.warning(
                f"REM: MFA verify attempt for unknown/inactive user "
                f"::{user_id}::_Thank_You_But_No"
            )
            return False

        if self.is_locked(user_id):
            logger.warning(f"REM: MFA code entry locked for user ::{user_id}::_Thank_You_But_No")
            return False

        # REM: Replay prevention — reject if this token was already used
        if record.last_used_token is not None:
            if self._same(token, record.last_used_token):
                logger.warning(
                    f"REM: MFA replay detected for user ::{user_id}::_Thank_You_But_No"
                )
                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    f"MFA token replay detected for user: {user_id}",
                    actor=user_id,
                    resource=user_id,
                    details={"action": "mfa_replay_blocked"},
                    qms_status="Thank_You_But_No"
                )
                return False

        # REM: Verify the TOTP token (constant-time internally in pyotp)
        totp = pyotp.TOTP(record.secret)
        is_valid = isinstance(token, str) and token.isascii() and totp.verify(token)

        if is_valid:
            self._clear_failed_codes(user_id)
            record.last_used_token = token
            record.last_verified_at = datetime.now(timezone.utc)

            logger.info(
                f"REM: MFA verification successful for user ::{user_id}::_Thank_You"
            )

            audit.log(
                AuditEventType.AUTH_SUCCESS,
                f"MFA verification successful for user: {user_id}",
                actor=user_id,
                resource=user_id,
                details={"action": "mfa_verify"},
                qms_status="Thank_You"
            )

            self._save_record(user_id)
        else:
            logger.warning(
                f"REM: MFA verification failed for user ::{user_id}::_Thank_You_But_No"
            )

            audit.log(
                AuditEventType.AUTH_FAILURE,
                f"MFA verification failed for user: {user_id}",
                actor=user_id,
                resource=user_id,
                details={"action": "mfa_verify_failed"},
                qms_status="Thank_You_But_No"
            )
            self._record_failed_code(user_id)

        return is_valid

    def verify_backup_code(self, user_id: str, code: str) -> bool:
        """
        REM: Verify and consume a one-time backup code.
        REM: Each backup code can only be used once.

        Args:
            user_id: The user's unique identifier
            code: The backup code to verify

        Returns:
            True if the backup code is valid and was consumed
        """
        record = self._get_record(user_id)
        if not record or not record.is_active:
            logger.warning(
                f"REM: Backup code attempt for unknown/inactive user "
                f"::{user_id}::_Thank_You_But_No"
            )
            return False

        if self.is_locked(user_id):
            logger.warning(f"REM: MFA code entry locked for user ::{user_id}::_Thank_You_But_No")
            return False

        # REM: Constant-time search through backup codes
        matched_index = None
        for i, stored_code in enumerate(record.backup_codes):
            if self._same(code, stored_code):
                matched_index = i

        if matched_index is not None:
            self._clear_failed_codes(user_id)
            # REM: Consume the backup code (one-time use)
            record.backup_codes.pop(matched_index)
            record.last_verified_at = datetime.now(timezone.utc)

            remaining = len(record.backup_codes)

            logger.info(
                f"REM: Backup code used for user ::{user_id}:: "
                f"({remaining} remaining)_Thank_You"
            )

            audit.log(
                AuditEventType.AUTH_SUCCESS,
                f"MFA backup code used for user: {user_id}",
                actor=user_id,
                resource=user_id,
                details={
                    "action": "mfa_backup_code_used",
                    "remaining_codes": remaining
                },
                qms_status="Thank_You"
            )

            self._save_record(user_id)

            return True

        logger.warning(
            f"REM: Invalid backup code for user ::{user_id}::_Thank_You_But_No"
        )

        audit.log(
            AuditEventType.AUTH_FAILURE,
            f"Invalid MFA backup code for user: {user_id}",
            actor=user_id,
            resource=user_id,
            details={"action": "mfa_backup_code_failed"},
            qms_status="Thank_You_But_No"
        )
        self._record_failed_code(user_id)

        return False

    def is_mfa_required(self, user: User) -> bool:
        """
        REM: Determine if MFA is required for a given user based on their roles.
        REM: Admin, Security Officer, and Super Admin roles require MFA.

        Args:
            user: The User dataclass instance to check

        Returns:
            True if the user holds any role that mandates MFA
        """
        return bool(user.roles & self.MFA_REQUIRED_ROLES)

    def is_enrolled(self, user_id: str) -> bool:
        """
        REM: Check if a user is currently enrolled in MFA.

        Args:
            user_id: The user's unique identifier

        Returns:
            True if the user has an active MFA enrollment
        """
        record = self._get_record(user_id)
        return record is not None and record.is_active

    def disable_mfa(self, user_id: str, disabled_by: str) -> bool:
        """
        REM: Disable and remove MFA enrollment for a user.
        REM: Requires audit logging of who performed the action.

        Args:
            user_id: The user whose MFA should be disabled
            disabled_by: The user_id or identity of the person disabling MFA

        Returns:
            True if MFA was successfully disabled
        """
        record = self._get_record(user_id)
        if not record or not record.is_active:
            logger.warning(
                f"REM: MFA disable attempt for non-enrolled user "
                f"::{user_id}:: by ::{disabled_by}::_Thank_You_But_No"
            )
            return False

        record.is_active = False
        record.backup_codes.clear()

        logger.warning(
            f"REM: MFA disabled for user ::{user_id}:: "
            f"by ::{disabled_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"MFA disabled for user: {user_id} by {disabled_by}",
            actor=disabled_by,
            resource=user_id,
            details={"action": "mfa_disable", "disabled_by": disabled_by},
            qms_status="Thank_You"
        )

        # REM: Keep an inactive record (secret blanked, no backup codes) in Redis so that
        # REM: other workers see the disable instead of answering from their cached copy.
        record.secret = ""
        record.last_used_token = None
        self._save_record(user_id)
        self._records.pop(user_id, None)
        self._clear_failed_codes(user_id)

        return True

    def get_mfa_status(self, user_id: str) -> Dict[str, Any]:
        """
        REM: Get MFA enrollment status for a user.

        Args:
            user_id: The user's unique identifier

        Returns:
            Dict with enrollment status details
        """
        record = self._get_record(user_id)
        if not record or not record.is_active:
            return {
                "user_id": user_id,
                "enrolled": False,
                "active": False
            }

        return {
            "user_id": user_id,
            "enrolled": True,
            "active": record.is_active,
            "enrolled_at": record.enrolled_at.isoformat(),
            "last_verified_at": (
                record.last_verified_at.isoformat()
                if record.last_verified_at else None
            ),
            "backup_codes_remaining": len(record.backup_codes)
        }


# REM: Global MFA manager instance
mfa_manager = MFAManager()
