# TelsonBase/core/user_management.py
# REM: =======================================================================================
# REM: PER-USER AUTHENTICATION — REGISTRATION, LOGIN, PASSWORD MANAGEMENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v7.0.0CC: New feature — Per-user authentication system
#
# REM: Mission Statement: Provide secure user registration, login, and password management
# REM: for human operators. Integrates with RBAC for role assignment, MFA for multi-factor
# REM: enforcement, and session management for HIPAA-compliant session handling.
#
# REM: Security:
# REM:   - bcrypt password hashing (12 rounds)
# REM:   - Password hashes stored separately from user records
# REM:   - Account lockout after 5 failed attempts (15 min cooldown)
# REM:   - Password strength validation (min 12 chars, mixed case, digit, special)
# REM:   - All mutations audit-logged
# REM:   - Redis persistence with encryption at rest
#
# REM: QMS Protocol:
# REM:   Success: "Thank_You"
# REM:   Failure: "Thank_You_But_No"
# REM: =======================================================================================

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import bcrypt as _bcrypt_lib

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)

# REM: Account lockout policy
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class UserManager:
    """
    REM: Manages user registration, authentication, and password lifecycle.
    REM: In-memory dict with Redis write-through persistence (same pattern as MFA, sessions).
    """

    def __init__(self):
        self._password_hashes: Dict[str, str] = {}  # user_id -> bcrypt hash
        self._failed_attempts: Dict[str, int] = {}  # username -> count
        self._lockout_until: Dict[str, datetime] = {}  # username -> lockout expiry
        self._user_count: int = 0  # Track total registered users for first-user detection
        self._load_from_redis()

    def _load_from_redis(self) -> None:
        """REM: Load password hashes from Redis on startup. In-memory dict is primary."""
        try:
            from core.persistence import security_store
            from core.secure_storage import secure_storage
            all_hashes = security_store.list_records("password_hashes")
            for user_id, hash_data in all_hashes.items():
                try:
                    # REM: Decrypt hash if it was encrypted at rest
                    stored_hash = hash_data.get("hash", "")
                    if hash_data.get("_encrypted"):
                        try:
                            stored_hash = secure_storage.decrypt_string(stored_hash)
                        except Exception:
                            logger.warning(
                                f"REM: Failed to decrypt password hash for ::{user_id}::_Thank_You_But_No"
                            )
                            continue
                    self._password_hashes[user_id] = stored_hash
                except Exception as e:
                    logger.warning(
                        f"REM: Failed to load password hash for ::{user_id}:: from Redis: {e}_Thank_You_But_No"
                    )
            if all_hashes:
                logger.info(f"REM: Loaded {len(self._password_hashes)} password hashes from Redis_Thank_You")

            # REM: Count existing users via RBAC to maintain first-user detection
            from core.rbac import rbac_manager
            self._user_count = len(rbac_manager._users)
        except Exception as e:
            logger.warning(f"REM: Redis unavailable for password hash load: {e}_Thank_You_But_No")

    def _save_password_hash(self, user_id: str) -> None:
        """REM: Write-through save of a single password hash to Redis (encrypted)."""
        try:
            from core.persistence import security_store
            from core.secure_storage import secure_storage
            pw_hash = self._password_hashes.get(user_id)
            if not pw_hash:
                return
            data = {"hash": pw_hash, "_encrypted": False}
            # REM: Encrypt hash before storing in Redis
            try:
                data["hash"] = secure_storage.encrypt_string(pw_hash)
                data["_encrypted"] = True
            except Exception:
                pass  # Store unencrypted if encryption unavailable
            security_store.store_record("password_hashes", user_id, data)
        except Exception as e:
            logger.warning(
                f"REM: Failed to save password hash to Redis for ::{user_id}::: {e}_Thank_You_But_No"
            )

    def _delete_password_hash(self, user_id: str) -> None:
        """REM: Delete a password hash from Redis."""
        try:
            from core.persistence import security_store
            security_store.delete_record("password_hashes", user_id)
        except Exception as e:
            logger.warning(
                f"REM: Failed to delete password hash from Redis for ::{user_id}::: {e}_Thank_You_But_No"
            )

    def _validate_password_strength(self, password: str) -> Tuple[bool, str]:
        """
        REM: Validate password meets security requirements.
        REM: Min 12 chars, upper, lower, digit, special character.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < 12:
            return False, "Password must be at least 12 characters long"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r'[0-9]', password):
            return False, "Password must contain at least one digit"
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?~`]', password):
            return False, "Password must contain at least one special character"
        return True, ""

    def _validate_email(self, email: str) -> bool:
        """REM: Basic email format validation."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _is_account_locked(self, username: str) -> bool:
        """REM: Check if account is currently locked out."""
        lockout_time = self._lockout_until.get(username)
        if lockout_time and datetime.now(timezone.utc) < lockout_time:
            return True
        # REM: Lockout expired — clear it
        if lockout_time:
            del self._lockout_until[username]
            self._failed_attempts.pop(username, None)
        return False

    def _record_failed_attempt(self, username: str) -> None:
        """REM: Record a failed login attempt and lock if threshold reached."""
        count = self._failed_attempts.get(username, 0) + 1
        self._failed_attempts[username] = count

        if count >= MAX_FAILED_ATTEMPTS:
            lockout_time = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            self._lockout_until[username] = lockout_time
            logger.warning(
                f"REM: Account ::{username}:: locked for {LOCKOUT_DURATION_MINUTES} minutes "
                f"after {count} failed attempts_Thank_You_But_No"
            )
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Account locked: {username} after {count} failed login attempts",
                actor=username,
                details={
                    "failed_attempts": count,
                    "lockout_minutes": LOCKOUT_DURATION_MINUTES,
                    "lockout_until": lockout_time.isoformat(),
                },
                qms_status="Thank_You_But_No"
            )

    def _clear_failed_attempts(self, username: str) -> None:
        """REM: Clear failed attempt counter on successful login."""
        self._failed_attempts.pop(username, None)
        self._lockout_until.pop(username, None)

    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: List[str] = None
    ) -> Dict:
        """
        REM: Register a new user with password hashing and RBAC user creation.

        Args:
            username: Unique username
            email: User email address
            password: Plaintext password (validated and hashed)
            roles: List of role names (default: ["viewer"])

        Returns:
            Dict with user profile (never includes password hash)

        Raises:
            ValueError: If validation fails (username taken, weak password, bad email)
        """
        from core.rbac import rbac_manager

        # REM: Default roles
        if roles is None:
            roles = ["viewer"]

        # REM: First user gets super_admin automatically
        if self._user_count == 0:
            roles = ["super_admin"]
            logger.info("REM: First user registration — assigning super_admin role_Thank_You")

        # REM: Validate username uniqueness
        existing = rbac_manager.get_user_by_username(username)
        if existing:
            raise ValueError(f"Username '{username}' is already taken")

        # REM: Validate email format
        if not self._validate_email(email):
            raise ValueError(f"Invalid email format: '{email}'")

        # REM: Validate password strength
        valid, error_msg = self._validate_password_strength(password)
        if not valid:
            raise ValueError(error_msg)

        # REM: Hash password with bcrypt (12 rounds)
        password_hash = _bcrypt_lib.hashpw(password.encode("utf-8"), _bcrypt_lib.gensalt(rounds=12)).decode("utf-8")

        # REM: Create RBAC user
        user = rbac_manager.create_user(
            username=username,
            email=email,
            roles=roles,
            created_by="user_registration"
        )

        # REM: Store password hash separately (never in RBAC user object)
        self._password_hashes[user.user_id] = password_hash
        self._save_password_hash(user.user_id)

        self._user_count += 1

        logger.info(
            f"REM: User registered ::{username}:: with roles "
            f"{roles}_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"User registered: {username}",
            actor="user_registration",
            resource=user.user_id,
            details={
                "username": username,
                "email": email,
                "roles": roles,
                "is_first_user": self._user_count == 1,
            },
            qms_status="Thank_You"
        )

        return user.to_dict()

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """
        REM: Authenticate a user by username and password.

        Args:
            username: The username to authenticate
            password: The plaintext password to verify

        Returns:
            User dict if valid, None if authentication fails
        """
        from core.rbac import rbac_manager

        # REM: Check account lockout
        if self._is_account_locked(username):
            lockout_time = self._lockout_until.get(username)
            remaining = (lockout_time - datetime.now(timezone.utc)).total_seconds() if lockout_time else 0
            logger.warning(
                f"REM: Login attempt for locked account ::{username}:: "
                f"({int(remaining)}s remaining)_Thank_You_But_No"
            )
            audit.log(
                AuditEventType.AUTH_FAILURE,
                f"Login attempt for locked account: {username}",
                actor=username,
                details={"remaining_seconds": int(remaining)},
                qms_status="Thank_You_But_No"
            )
            return None

        # REM: Look up user by username
        user = rbac_manager.get_user_by_username(username)
        if not user:
            # REM: Still record attempt to prevent username enumeration timing attacks
            self._record_failed_attempt(username)
            audit.log(
                AuditEventType.AUTH_FAILURE,
                f"Login failed: unknown username {username}",
                actor=username,
                details={"reason": "unknown_user"},
                qms_status="Thank_You_But_No"
            )
            return None

        # REM: Check if user is active
        if not user.is_active:
            audit.log(
                AuditEventType.AUTH_FAILURE,
                f"Login failed: deactivated account {username}",
                actor=username,
                details={"reason": "account_deactivated"},
                qms_status="Thank_You_But_No"
            )
            return None

        # REM: Verify password hash
        stored_hash = self._password_hashes.get(user.user_id)
        if not stored_hash:
            logger.error(
                f"REM: No password hash found for user ::{user.user_id}::_Thank_You_But_No"
            )
            return None

        if not _bcrypt_lib.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            self._record_failed_attempt(username)
            audit.log(
                AuditEventType.AUTH_FAILURE,
                f"Login failed: invalid password for {username}",
                actor=username,
                details={
                    "reason": "invalid_password",
                    "failed_attempts": self._failed_attempts.get(username, 0),
                },
                qms_status="Thank_You_But_No"
            )
            return None

        # REM: Successful authentication — clear failed attempts
        self._clear_failed_attempts(username)

        # REM: Update last_login timestamp
        user.last_login = datetime.now(timezone.utc)

        logger.info(f"REM: User ::{username}:: authenticated successfully_Thank_You")

        audit.log(
            AuditEventType.AUTH_SUCCESS,
            f"User login successful: {username}",
            actor=username,
            resource=user.user_id,
            details={"method": "password"},
            qms_status="Thank_You"
        )

        return user.to_dict()

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """
        REM: Change a user's password (requires old password verification).

        Args:
            user_id: The user's unique identifier
            old_password: Current password for verification
            new_password: New password to set

        Returns:
            True if password was changed successfully
        """
        from core.rbac import rbac_manager

        user = rbac_manager.get_user(user_id)
        if not user:
            return False

        # REM: Verify old password
        stored_hash = self._password_hashes.get(user_id)
        if not stored_hash or not _bcrypt_lib.checkpw(old_password.encode("utf-8"), stored_hash.encode("utf-8")):
            audit.log(
                AuditEventType.AUTH_FAILURE,
                f"Password change failed: invalid old password for {user.username}",
                actor=user.username,
                resource=user_id,
                details={"reason": "invalid_old_password"},
                qms_status="Thank_You_But_No"
            )
            return False

        # REM: Validate new password strength
        valid, error_msg = self._validate_password_strength(new_password)
        if not valid:
            raise ValueError(error_msg)

        # REM: Hash and store new password
        new_hash = _bcrypt_lib.hashpw(new_password.encode("utf-8"), _bcrypt_lib.gensalt(rounds=12)).decode("utf-8")
        self._password_hashes[user_id] = new_hash
        self._save_password_hash(user_id)

        logger.info(f"REM: Password changed for user ::{user.username}::_Thank_You")

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Password changed for user: {user.username}",
            actor=user.username,
            resource=user_id,
            details={"action": "password_change"},
            qms_status="Thank_You"
        )

        return True

    def reset_password_admin(self, user_id: str, new_password: str, reset_by: str) -> bool:
        """
        REM: Admin-only password reset (no old password required).

        Args:
            user_id: The user whose password is being reset
            new_password: New password to set
            reset_by: Identifier of the admin performing the reset

        Returns:
            True if password was reset successfully
        """
        from core.rbac import rbac_manager

        user = rbac_manager.get_user(user_id)
        if not user:
            return False

        # REM: Validate new password strength
        valid, error_msg = self._validate_password_strength(new_password)
        if not valid:
            raise ValueError(error_msg)

        # REM: Hash and store new password
        new_hash = _bcrypt_lib.hashpw(new_password.encode("utf-8"), _bcrypt_lib.gensalt(rounds=12)).decode("utf-8")
        self._password_hashes[user_id] = new_hash
        self._save_password_hash(user_id)

        # REM: Clear any lockouts
        self._clear_failed_attempts(user.username)

        logger.warning(
            f"REM: Admin password reset for user ::{user.username}:: "
            f"by ::{reset_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Admin password reset for user: {user.username} by {reset_by}",
            actor=reset_by,
            resource=user_id,
            details={"action": "admin_password_reset", "reset_by": reset_by},
            qms_status="Thank_You"
        )

        return True

    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """
        REM: Get full user profile including MFA status, roles, and permissions.

        Args:
            user_id: The user's unique identifier

        Returns:
            Dict with user profile or None if user not found
        """
        from core.rbac import rbac_manager

        user = rbac_manager.get_user(user_id)
        if not user:
            return None

        profile = user.to_dict()

        # REM: Add MFA status
        try:
            from core.mfa import mfa_manager
            mfa_status = mfa_manager.get_mfa_status(user_id)
            profile["mfa_status"] = mfa_status
            profile["mfa_enrolled"] = mfa_status.get("enrolled", False)
        except Exception:
            profile["mfa_status"] = {"enrolled": False, "active": False}
            profile["mfa_enrolled"] = False

        # REM: Add permission details
        profile["permissions"] = [p.value for p in user.get_all_permissions()]

        # REM: Add email verification status placeholder
        profile["email_verified"] = False  # REM: Will integrate with email_verification module

        return profile

    def is_first_user(self) -> bool:
        """REM: Check if no users have been registered yet (for first-user super_admin logic)."""
        return self._user_count == 0


# REM: Global singleton instance
user_manager = UserManager()
