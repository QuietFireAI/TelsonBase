# TelsonBase/core/email_verification.py
# REM: =======================================================================================
# REM: EMAIL VERIFICATION MODULE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.3.0CC: Email verification for new user registration
#
# REM: Mission Statement: Ensure every registered email address is verified before granting
# REM: access. Uses cryptographically secure tokens with expiry and rate-limited resend.
# REM: Constant-time comparison prevents timing-based token enumeration attacks.
#
# REM: Features:
# REM:   - Secure token generation via secrets.token_urlsafe
# REM:   - 24-hour token expiry with configurable lifetime
# REM:   - Constant-time token comparison (hmac.compare_digest)
# REM:   - Max 3 verification attempts per token
# REM:   - Rate-limited resend (max 3 per hour per user)
# REM:   - Full audit trail for all verification events
# REM: =======================================================================================

import hmac
import secrets
import uuid
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


class VerificationStatus(Enum):
    """REM: Status states for an email verification token."""
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class VerificationToken:
    """REM: Stores email verification state for a single user."""
    token_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    email: str = ""
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24)
    )
    status: VerificationStatus = VerificationStatus.PENDING
    attempts: int = 0


class EmailVerificationManager:
    """
    REM: Manages email verification for new user registrations.
    REM: In-memory storage with rate-limited resend and secure token comparison.
    """

    # REM: Maximum verification attempts per token before marking as FAILED
    MAX_ATTEMPTS = 3

    # REM: Maximum resend requests per user per hour
    MAX_RESENDS_PER_HOUR = 3

    # REM: Token expiry lifetime
    TOKEN_LIFETIME = timedelta(hours=24)

    def __init__(self):
        self._tokens: Dict[str, VerificationToken] = {}
        self._verified_emails: Dict[str, str] = {}
        self._resend_tracking: Dict[str, List[datetime]] = {}
        self._load_from_redis()

    def _load_from_redis(self) -> None:
        """REM: Load email verification records from Redis on startup."""
        try:
            from core.persistence import security_store
            # REM: Load verified emails (stored in hash, not TTL keys)
            verified_records = security_store.list_records("verified_emails")
            for user_id, record_data in verified_records.items():
                try:
                    self._verified_emails[user_id] = record_data["email"]
                except Exception as e:
                    logger.warning(
                        f"REM: Failed to load verified email for ::{user_id}:: from Redis: {e}_Thank_You_But_No"
                    )
            # REM: Note: email_tokens use TTL keys and cannot be enumerated via hgetall.
            # REM: They will expire naturally. Active tokens are transient by design.
            if verified_records:
                logger.info(f"REM: Loaded {len(self._verified_emails)} verified emails from Redis_Thank_You")
        except Exception as e:
            logger.warning(f"REM: Redis unavailable for email verification load: {e}_Thank_You_But_No")

    def _save_record(self, user_id: str) -> None:
        """REM: Write-through save of a single email token record to Redis with TTL."""
        try:
            from core.persistence import security_store
            token_rec = self._tokens.get(user_id)
            if not token_rec:
                return
            data = {
                "token_id": token_rec.token_id,
                "user_id": token_rec.user_id,
                "email": token_rec.email,
                "token": token_rec.token,
                "created_at": token_rec.created_at.isoformat(),
                "expires_at": token_rec.expires_at.isoformat(),
                "status": token_rec.status.value,
                "attempts": token_rec.attempts,
            }
            security_store.store_record("email_tokens", user_id, data, ttl=86400)
        except Exception as e:
            logger.warning(f"REM: Failed to save email token to Redis for ::{user_id}::: {e}_Thank_You_But_No")

    def _save_verified_email(self, user_id: str, email: str) -> None:
        """REM: Persist verified email status to Redis."""
        try:
            from core.persistence import security_store
            security_store.store_record("verified_emails", user_id, {"email": email})
        except Exception as e:
            logger.warning(f"REM: Failed to save verified email to Redis for ::{user_id}::: {e}_Thank_You_But_No")

    def create_verification(self, user_id: str, email: str) -> VerificationToken:
        """
        REM: Create a new email verification token for a user.
        REM: Generates a cryptographically secure URL-safe token.

        Args:
            user_id: The user's unique identifier
            email: The email address to verify

        Returns:
            VerificationToken with the generated token details
        """
        now = datetime.now(timezone.utc)

        token = VerificationToken(
            user_id=user_id,
            email=email,
            created_at=now,
            expires_at=now + self.TOKEN_LIFETIME,
            status=VerificationStatus.PENDING,
            attempts=0
        )

        self._tokens[user_id] = token
        self._save_record(user_id)

        logger.info(
            f"REM: Email verification created for user ::{user_id}:: "
            f"email ::{email}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Email verification token created for user: {user_id}",
            actor=user_id,
            resource=email,
            details={"action": "email_verification_created", "email": email},
            qms_status="Thank_You"
        )

        # REM: Fire-and-forget email delivery — does not block token creation
        try:
            import asyncio
            from core.email_sender import send_verification_email
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    send_verification_email(email, user_id, token.token, user_id)
                )
            else:
                loop.run_until_complete(
                    send_verification_email(email, user_id, token.token, user_id)
                )
        except Exception as _e:
            logger.warning(
                f"REM: Could not dispatch verification email for ::{user_id}::: {_e}_Thank_You_But_No"
            )

        return token

    def verify_email(self, user_id: str, token: str) -> bool:
        """
        REM: Verify an email using the provided token.
        REM: Uses constant-time comparison. Checks expiry and max attempts.

        Args:
            user_id: The user's unique identifier
            token: The verification token to validate

        Returns:
            True if the token is valid and email is now verified
        """
        record = self._tokens.get(user_id)
        if not record:
            logger.warning(
                f"REM: Verification attempt for unknown user "
                f"::{user_id}::_Thank_You_But_No"
            )
            return False

        # REM: Check if already verified
        if record.status == VerificationStatus.VERIFIED:
            logger.info(
                f"REM: Email already verified for user ::{user_id}::_Thank_You"
            )
            return True

        # REM: Check max attempts
        if record.attempts >= self.MAX_ATTEMPTS:
            record.status = VerificationStatus.FAILED
            logger.warning(
                f"REM: Max verification attempts exceeded for user "
                f"::{user_id}::_Thank_You_But_No"
            )
            audit.log(
                AuditEventType.AUTH_FAILURE,
                f"Email verification max attempts exceeded for user: {user_id}",
                actor=user_id,
                resource=record.email,
                details={"action": "email_verification_max_attempts", "attempts": record.attempts},
                qms_status="Thank_You_But_No"
            )
            return False

        # REM: Check token expiry
        now = datetime.now(timezone.utc)
        if now > record.expires_at:
            record.status = VerificationStatus.EXPIRED
            logger.warning(
                f"REM: Verification token expired for user "
                f"::{user_id}::_Thank_You_But_No"
            )
            audit.log(
                AuditEventType.AUTH_FAILURE,
                f"Email verification token expired for user: {user_id}",
                actor=user_id,
                resource=record.email,
                details={"action": "email_verification_expired"},
                qms_status="Thank_You_But_No"
            )
            return False

        # REM: Increment attempt counter
        record.attempts += 1

        # REM: Constant-time token comparison to prevent timing attacks
        is_valid = hmac.compare_digest(token, record.token)

        if is_valid:
            record.status = VerificationStatus.VERIFIED
            self._verified_emails[user_id] = record.email

            logger.info(
                f"REM: Email verified successfully for user ::{user_id}:: "
                f"email ::{record.email}::_Thank_You"
            )

            audit.log(
                AuditEventType.AUTH_SUCCESS,
                f"Email verified for user: {user_id}",
                actor=user_id,
                resource=record.email,
                details={"action": "email_verified", "email": record.email},
                qms_status="Thank_You"
            )

            self._save_record(user_id)
            self._save_verified_email(user_id, record.email)
        else:
            logger.warning(
                f"REM: Invalid verification token for user ::{user_id}:: "
                f"(attempt {record.attempts}/{self.MAX_ATTEMPTS})_Thank_You_But_No"
            )

            audit.log(
                AuditEventType.AUTH_FAILURE,
                f"Invalid email verification token for user: {user_id}",
                actor=user_id,
                resource=record.email,
                details={
                    "action": "email_verification_failed",
                    "attempt": record.attempts,
                    "max_attempts": self.MAX_ATTEMPTS
                },
                qms_status="Thank_You_But_No"
            )

        return is_valid

    def is_verified(self, user_id: str) -> bool:
        """
        REM: Check if a user's email has been verified.

        Args:
            user_id: The user's unique identifier

        Returns:
            True if the user has a verified email on record
        """
        return user_id in self._verified_emails

    def resend_verification(self, user_id: str) -> Optional[VerificationToken]:
        """
        REM: Resend a verification token for a user.
        REM: Rate limited to MAX_RESENDS_PER_HOUR per user.

        Args:
            user_id: The user's unique identifier

        Returns:
            New VerificationToken if within rate limit, None otherwise
        """
        record = self._tokens.get(user_id)
        if not record:
            logger.warning(
                f"REM: Resend attempt for unknown user "
                f"::{user_id}::_Thank_You_But_No"
            )
            return None

        # REM: Check rate limit before generating a new token
        if not self._check_rate_limit(user_id):
            logger.warning(
                f"REM: Resend rate limit exceeded for user "
                f"::{user_id}::_Thank_You_But_No"
            )
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Email verification resend rate limit exceeded for user: {user_id}",
                actor=user_id,
                resource=record.email,
                details={"action": "email_resend_rate_limited"},
                qms_status="Thank_You_But_No"
            )
            return None

        # REM: Track this resend request
        now = datetime.now(timezone.utc)
        if user_id not in self._resend_tracking:
            self._resend_tracking[user_id] = []
        self._resend_tracking[user_id].append(now)

        # REM: Generate a fresh token for the same email
        new_token = self.create_verification(user_id, record.email)

        logger.info(
            f"REM: Verification token resent for user ::{user_id}::_Thank_You"
        )

        return new_token

    def get_verification_status(self, user_id: str) -> Dict[str, Any]:
        """
        REM: Get the current verification status for a user.

        Args:
            user_id: The user's unique identifier

        Returns:
            Dict with verification status details
        """
        record = self._tokens.get(user_id)
        if not record:
            return {
                "user_id": user_id,
                "verified": self.is_verified(user_id),
                "status": None,
                "email": self._verified_emails.get(user_id)
            }

        return {
            "user_id": user_id,
            "verified": self.is_verified(user_id),
            "status": record.status.value,
            "email": record.email,
            "created_at": record.created_at.isoformat(),
            "expires_at": record.expires_at.isoformat(),
            "attempts": record.attempts,
            "max_attempts": self.MAX_ATTEMPTS
        }

    def cleanup_expired(self) -> int:
        """
        REM: Remove all expired verification tokens from storage.

        Returns:
            Number of expired tokens removed
        """
        now = datetime.now(timezone.utc)
        expired_users = [
            uid for uid, tok in self._tokens.items()
            if now > tok.expires_at and tok.status != VerificationStatus.VERIFIED
        ]

        for uid in expired_users:
            del self._tokens[uid]

        if expired_users:
            logger.info(
                f"REM: Cleaned up {len(expired_users)} expired verification tokens_Thank_You"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Expired email verification tokens cleaned up: {len(expired_users)}",
                actor="system",
                details={"action": "email_verification_cleanup", "removed": len(expired_users)},
                qms_status="Thank_You"
            )

        return len(expired_users)

    def _check_rate_limit(self, user_id: str) -> bool:
        """
        REM: Check if a user is within the resend rate limit.
        REM: Allows MAX_RESENDS_PER_HOUR resend requests per hour.

        Args:
            user_id: The user's unique identifier

        Returns:
            True if the user is within the rate limit
        """
        if user_id not in self._resend_tracking:
            return True

        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)

        # REM: Filter to only recent resend timestamps within the last hour
        recent = [ts for ts in self._resend_tracking[user_id] if ts > one_hour_ago]
        self._resend_tracking[user_id] = recent

        return len(recent) < self.MAX_RESENDS_PER_HOUR


# REM: Global email verification manager instance
email_verification = EmailVerificationManager()
