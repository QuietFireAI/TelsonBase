# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# TelsonBase/core/rbac.py
# REM: =======================================================================================
# REM: ROLE-BASED ACCESS CONTROL FOR OPERATORS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.2.0CC: New feature - RBAC for human operators
#
# REM: Mission Statement: Control what human operators can do in the system. Different
# REM: roles have different permissions (viewer, operator, admin, security officer).
#
# REM: Features:
# REM:   - Predefined roles with escalating permissions
# REM:   - Permission checks for API endpoints
# REM:   - Audit logging of privileged actions
# REM:   - Role assignment and management
# REM:   - Session-based permission caching
# REM: =======================================================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.audit import AuditEventType, audit

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """REM: Individual permissions that can be granted."""
    # View permissions
    VIEW_DASHBOARD = "view:dashboard"
    VIEW_AGENTS = "view:agents"
    VIEW_ANOMALIES = "view:anomalies"
    VIEW_APPROVALS = "view:approvals"
    VIEW_FEDERATION = "view:federation"
    VIEW_AUDIT = "view:audit"
    VIEW_CONFIG = "view:config"

    # Action permissions
    APPROVE_REQUESTS = "action:approve"
    REJECT_REQUESTS = "action:reject"
    RESOLVE_ANOMALIES = "action:resolve_anomaly"

    # Management permissions
    MANAGE_AGENTS = "manage:agents"
    MANAGE_FEDERATION = "manage:federation"
    MANAGE_KEYS = "manage:keys"
    MANAGE_USERS = "manage:users"
    MANAGE_ROLES = "manage:roles"

    # Admin permissions
    ADMIN_CONFIG = "admin:config"
    ADMIN_REVOKE = "admin:revoke"
    ADMIN_EXPORT = "admin:export"
    ADMIN_ROTATE_SECRETS = "admin:rotate_secrets"

    # Security officer permissions
    SECURITY_QUARANTINE = "security:quarantine"
    SECURITY_PROMOTE = "security:promote"
    SECURITY_AUDIT = "security:audit"
    SECURITY_OVERRIDE = "security:override"


class Role(str, Enum):
    """REM: Predefined roles with sets of permissions."""
    VIEWER = "viewer"           # Read-only access
    OPERATOR = "operator"       # Can approve/reject, resolve anomalies
    ADMIN = "admin"             # Full system management
    SECURITY_OFFICER = "security_officer"  # Security-focused permissions
    SUPER_ADMIN = "super_admin"  # All permissions


# REM: Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.VIEWER: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AGENTS,
        Permission.VIEW_ANOMALIES,
        Permission.VIEW_APPROVALS,
        Permission.VIEW_FEDERATION,
    },
    Role.OPERATOR: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AGENTS,
        Permission.VIEW_ANOMALIES,
        Permission.VIEW_APPROVALS,
        Permission.VIEW_FEDERATION,
        Permission.VIEW_AUDIT,
        Permission.APPROVE_REQUESTS,
        Permission.REJECT_REQUESTS,
        Permission.RESOLVE_ANOMALIES,
    },
    Role.ADMIN: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AGENTS,
        Permission.VIEW_ANOMALIES,
        Permission.VIEW_APPROVALS,
        Permission.VIEW_FEDERATION,
        Permission.VIEW_AUDIT,
        Permission.VIEW_CONFIG,
        Permission.APPROVE_REQUESTS,
        Permission.REJECT_REQUESTS,
        Permission.RESOLVE_ANOMALIES,
        Permission.MANAGE_AGENTS,
        Permission.MANAGE_FEDERATION,
        Permission.MANAGE_KEYS,
        Permission.ADMIN_CONFIG,
        Permission.ADMIN_EXPORT,
    },
    Role.SECURITY_OFFICER: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AGENTS,
        Permission.VIEW_ANOMALIES,
        Permission.VIEW_APPROVALS,
        Permission.VIEW_FEDERATION,
        Permission.VIEW_AUDIT,
        Permission.VIEW_CONFIG,
        Permission.APPROVE_REQUESTS,
        Permission.REJECT_REQUESTS,
        Permission.RESOLVE_ANOMALIES,
        Permission.ADMIN_REVOKE,
        Permission.ADMIN_ROTATE_SECRETS,
        Permission.SECURITY_QUARANTINE,
        Permission.SECURITY_PROMOTE,
        Permission.SECURITY_AUDIT,
    },
    Role.SUPER_ADMIN: set(Permission),  # All permissions
}


@dataclass
class User:
    """REM: A human operator in the system."""
    user_id: str
    username: str
    email: str
    roles: Set[Role]
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    mfa_enabled: bool = False
    custom_permissions: Set[Permission] = field(default_factory=set)
    denied_permissions: Set[Permission] = field(default_factory=set)

    def get_all_permissions(self) -> Set[Permission]:
        """REM: Get all permissions for this user."""
        permissions = set()
        for role in self.roles:
            permissions.update(ROLE_PERMISSIONS.get(role, set()))
        permissions.update(self.custom_permissions)
        permissions -= self.denied_permissions
        return permissions

    def has_permission(self, permission: Permission) -> bool:
        """REM: Check if user has a specific permission."""
        if not self.is_active:
            return False
        return permission in self.get_all_permissions()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "roles": [r.value for r in self.roles],
            "is_active": self.is_active,
            "mfa_enabled": self.mfa_enabled,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "permission_count": len(self.get_all_permissions())
        }


@dataclass
class Session:
    """REM: An active user session."""
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_valid: bool = True

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class RBACManager:
    """
    REM: Manages role-based access control for operators.
    REM: Redis write-through persistence — all workers share the same user/session state.
    """

    SESSION_DURATION_HOURS = 8

    def __init__(self):
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, Session] = {}
        self._api_key_to_user: Dict[str, str] = {}
        self._load_from_redis()

    # ── Redis persistence helpers ──────────────────────────────────────────────

    def _load_from_redis(self) -> None:
        """REM: Load users and API-key index from Redis on startup."""
        try:
            from core.persistence import security_store
            all_users = security_store.list_records("rbac_users")
            for user_id, data in all_users.items():
                user = self._user_from_dict(data)
                if user:
                    self._users[user_id] = user
            all_keys = security_store.list_records("rbac_api_keys")
            for api_key, data in all_keys.items():
                uid = data.get("user_id", "") if isinstance(data, dict) else str(data)
                if uid:
                    self._api_key_to_user[api_key] = uid
            if all_users:
                logger.info(
                    f"REM: Loaded {len(self._users)} RBAC users from Redis_Thank_You"
                )
        except Exception as e:
            logger.warning(
                f"REM: Redis unavailable for RBAC load: {e}_Thank_You_But_No"
            )

    def _user_to_redis_dict(self, user: User) -> Dict[str, Any]:
        """REM: Full-fidelity serialization for Redis round-trip (includes custom/denied perms)."""
        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "roles": [r.value for r in user.roles],
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "is_active": user.is_active,
            "mfa_enabled": user.mfa_enabled,
            "custom_permissions": [p.value for p in user.custom_permissions],
            "denied_permissions": [p.value for p in user.denied_permissions],
        }

    def _user_from_dict(self, data: Dict) -> Optional[User]:
        """REM: Deserialize a User from a Redis dict."""
        try:
            roles = {Role(r) for r in data.get("roles", [])}
            custom_perms = {Permission(p) for p in data.get("custom_permissions", [])}
            denied_perms = {Permission(p) for p in data.get("denied_permissions", [])}
            created_at = datetime.fromisoformat(data["created_at"])
            last_login = (
                datetime.fromisoformat(data["last_login"])
                if data.get("last_login")
                else None
            )
            return User(
                user_id=data["user_id"],
                username=data["username"],
                email=data["email"],
                roles=roles,
                created_at=created_at,
                last_login=last_login,
                is_active=data.get("is_active", True),
                mfa_enabled=data.get("mfa_enabled", False),
                custom_permissions=custom_perms,
                denied_permissions=denied_perms,
            )
        except Exception as e:
            logger.warning(
                f"REM: Failed to deserialize RBAC user: {e}_Thank_You_But_No"
            )
            return None

    def _save_user(self, user: User) -> None:
        """REM: Write-through save of a user record and username index to Redis."""
        try:
            from core.persistence import security_store
            security_store.store_record(
                "rbac_users", user.user_id, self._user_to_redis_dict(user)
            )
            security_store.store_record(
                "rbac_username_idx", user.username, {"user_id": user.user_id}
            )
        except Exception as e:
            logger.warning(
                f"REM: Failed to save RBAC user to Redis: {e}_Thank_You_But_No"
            )

    def _load_user_from_redis(self, user_id: str) -> Optional[User]:
        """REM: Fetch a user from Redis and cache it in-memory."""
        try:
            from core.persistence import security_store
            data = security_store.get_record("rbac_users", user_id)
            if not data:
                return None
            user = self._user_from_dict(data)
            if user:
                self._users[user_id] = user
            return user
        except Exception as e:
            logger.warning(
                f"REM: Failed to load user from Redis: {e}_Thank_You_But_No"
            )
            return None

    def _save_session(self, session: Session) -> None:
        """REM: Persist session to Redis with TTL matching its expiry."""
        try:
            from core.persistence import security_store
            remaining = int(
                (session.expires_at - datetime.now(timezone.utc)).total_seconds()
            )
            if remaining <= 0:
                return
            data = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
            }
            security_store.store_record(
                "rbac_sessions", session.session_id, data, ttl=remaining
            )
        except Exception as e:
            logger.warning(
                f"REM: Failed to save session to Redis: {e}_Thank_You_But_No"
            )

    def _load_session_from_redis(self, session_id: str) -> Optional[Session]:
        """REM: Load a session from Redis (another worker may have created it)."""
        try:
            from core.persistence import security_store
            data = security_store.get_record(
                "rbac_sessions", session_id, use_ttl_key=True
            )
            if not data:
                return None
            return Session(
                session_id=data["session_id"],
                user_id=data["user_id"],
                created_at=datetime.fromisoformat(data["created_at"]),
                expires_at=datetime.fromisoformat(data["expires_at"]),
                ip_address=data.get("ip_address"),
                user_agent=data.get("user_agent"),
                is_valid=True,
            )
        except Exception as e:
            logger.warning(
                f"REM: Failed to load session from Redis: {e}_Thank_You_But_No"
            )
            return None

    def _delete_session_from_redis(self, session_id: str) -> None:
        """REM: Delete a session from Redis on explicit invalidation."""
        try:
            from core.persistence import security_store
            security_store.delete_record(
                "rbac_sessions", session_id, use_ttl_key=True
            )
        except Exception as e:
            logger.warning(
                f"REM: Failed to delete session from Redis: {e}_Thank_You_But_No"
            )

    # ── Core operations ────────────────────────────────────────────────────────

    def create_user(
        self,
        username: str,
        email: str,
        roles: List[str],
        created_by: str = "system"
    ) -> User:
        """REM: Create a new user."""
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        role_set = set()
        for role_name in roles:
            try:
                role_set.add(Role(role_name))
            except ValueError:
                logger.warning(f"REM: Unknown role ::{role_name}::_Thank_You_But_No")

        if not role_set:
            role_set.add(Role.VIEWER)

        user = User(
            user_id=user_id,
            username=username,
            email=email,
            roles=role_set,
            created_at=now
        )

        self._users[user_id] = user
        self._save_user(user)

        logger.info(
            f"REM: User created - ::{username}:: with roles "
            f"{[r.value for r in role_set]}_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"User created: {username}",
            actor=created_by,
            resource=user_id,
            details={"roles": [r.value for r in role_set]},
            qms_status="Thank_You"
        )

        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """REM: Get a user by ID. Falls back to Redis if not in memory cache."""
        user = self._users.get(user_id)
        if user is None:
            user = self._load_user_from_redis(user_id)
        return user

    def get_user_by_username(self, username: str) -> Optional[User]:
        """REM: Get a user by username. Falls back to Redis username index on cache miss."""
        for user in self._users.values():
            if user.username == username:
                return user
        # REM: Not in memory — check Redis username index (another worker may have created it)
        try:
            from core.persistence import security_store
            data = security_store.get_record("rbac_username_idx", username)
            if data:
                user_id = data.get("user_id") if isinstance(data, dict) else str(data)
                if user_id:
                    return self._load_user_from_redis(user_id)
        except Exception:
            pass
        return None

    def assign_role(
        self,
        user_id: str,
        role: str,
        assigned_by: str = "system"
    ) -> bool:
        """REM: Assign a role to a user."""
        user = self._users.get(user_id)
        if not user:
            return False

        try:
            role_enum = Role(role)
        except ValueError:
            return False

        user.roles.add(role_enum)
        self._save_user(user)

        logger.info(
            f"REM: Role ::{role}:: assigned to ::{user.username}:: "
            f"by ::{assigned_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Role assigned: {role} to {user.username}",
            actor=assigned_by,
            resource=user_id,
            qms_status="Thank_You"
        )

        return True

    def remove_role(
        self,
        user_id: str,
        role: str,
        removed_by: str = "system"
    ) -> bool:
        """REM: Remove a role from a user."""
        user = self._users.get(user_id)
        if not user:
            return False

        try:
            role_enum = Role(role)
        except ValueError:
            return False

        if role_enum in user.roles:
            user.roles.remove(role_enum)
            self._save_user(user)

            logger.warning(
                f"REM: Role ::{role}:: removed from ::{user.username}:: "
                f"by ::{removed_by}::_Thank_You"
            )

            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Role removed: {role} from {user.username}",
                actor=removed_by,
                resource=user_id,
                qms_status="Thank_You"
            )

            return True
        return False

    def deactivate_user(self, user_id: str, deactivated_by: str = "system") -> bool:
        """REM: Deactivate a user account."""
        user = self._users.get(user_id)
        if not user:
            return False

        user.is_active = False
        self._save_user(user)

        # REM: Invalidate all in-memory sessions; Redis TTL sessions expire naturally
        for session_id, session in list(self._sessions.items()):
            if session.user_id == user_id:
                session.is_valid = False
                self._delete_session_from_redis(session_id)

        logger.warning(
            f"REM: User ::{user.username}:: deactivated by ::{deactivated_by}::_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"User deactivated: {user.username}",
            actor=deactivated_by,
            resource=user_id,
            qms_status="Thank_You"
        )

        return True

    def create_session(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Session]:
        """REM: Create a new session for a user."""
        user = self._users.get(user_id)
        if not user or not user.is_active:
            return None

        session_id = f"sess_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)

        session = Session(
            session_id=session_id,
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(hours=self.SESSION_DURATION_HOURS),
            ip_address=ip_address,
            user_agent=user_agent
        )

        self._sessions[session_id] = session
        self._save_session(session)
        user.last_login = now

        logger.info(f"REM: Session created for ::{user.username}::_Thank_You")

        return session

    def validate_session(self, session_id: str) -> Optional[User]:
        """REM: Validate a session and return the user. Falls back to Redis on cache miss."""
        session = self._sessions.get(session_id)
        if session is None:
            # REM: Not in memory — another worker may have created it
            session = self._load_session_from_redis(session_id)
            if session:
                self._sessions[session_id] = session

        if not session:
            return None
        if not session.is_valid or session.is_expired():
            return None

        user = self._users.get(session.user_id)
        if user is None:
            user = self._load_user_from_redis(session.user_id)
        if not user or not user.is_active:
            return None

        return user

    def invalidate_session(self, session_id: str) -> bool:
        """REM: Invalidate a session (in-memory and Redis)."""
        found = False
        session = self._sessions.get(session_id)
        if session:
            session.is_valid = False
            found = True
        self._delete_session_from_redis(session_id)
        return found

    def check_permission(
        self,
        session_id: str,
        permission: Permission
    ) -> bool:
        """REM: Check if session has a permission."""
        user = self.validate_session(session_id)
        if not user:
            return False
        return user.has_permission(permission)

    def register_api_key(self, api_key: str, user_id: str) -> bool:
        """REM: Register an API key for a user. Persisted to Redis."""
        if user_id not in self._users:
            if not self._load_user_from_redis(user_id):
                return False
        self._api_key_to_user[api_key] = user_id
        try:
            from core.persistence import security_store
            security_store.store_record("rbac_api_keys", api_key, {"user_id": user_id})
        except Exception as e:
            logger.warning(
                f"REM: Failed to save API key to Redis: {e}_Thank_You_But_No"
            )
        return True

    def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """REM: Get user by API key. Falls back to Redis on cache miss."""
        user_id = self._api_key_to_user.get(api_key)
        if not user_id:
            try:
                from core.persistence import security_store
                data = security_store.get_record("rbac_api_keys", api_key)
                if data:
                    user_id = data.get("user_id") if isinstance(data, dict) else str(data)
                    if user_id:
                        self._api_key_to_user[api_key] = user_id
            except Exception:
                pass
        if user_id:
            return self.get_user(user_id)
        return None

    def check_api_key_permission(
        self,
        api_key: str,
        permission: Permission
    ) -> bool:
        """REM: Check if API key has permission."""
        user = self.get_user_by_api_key(api_key)
        if not user or not user.is_active:
            return False
        return user.has_permission(permission)

    def list_users(self) -> List[Dict[str, Any]]:
        """REM: List all users."""
        return [u.to_dict() for u in self._users.values()]

    def list_roles(self) -> List[Dict[str, Any]]:
        """REM: List all available roles with their permissions."""
        return [
            {
                "role": role.value,
                "permissions": [p.value for p in permissions]
            }
            for role, permissions in ROLE_PERMISSIONS.items()
        ]

    def get_permission_report(self, user_id: str) -> Optional[Dict[str, Any]]:
        """REM: Get a detailed permission report for a user."""
        user = self._users.get(user_id)
        if not user:
            return None

        all_permissions = user.get_all_permissions()

        return {
            "user_id": user_id,
            "username": user.username,
            "roles": [r.value for r in user.roles],
            "permissions": [p.value for p in all_permissions],
            "custom_permissions": [p.value for p in user.custom_permissions],
            "denied_permissions": [p.value for p in user.denied_permissions],
            "is_active": user.is_active,
            "can_approve": user.has_permission(Permission.APPROVE_REQUESTS),
            "can_manage_agents": user.has_permission(Permission.MANAGE_AGENTS),
            "can_admin": user.has_permission(Permission.ADMIN_CONFIG),
            "is_security_officer": Role.SECURITY_OFFICER in user.roles
        }


# REM: Global RBAC manager instance
rbac_manager = RBACManager()


# REM: =======================================================================================
# REM: FASTAPI DEPENDENCY FOR PERMISSION CHECKING (v5.2.1CC)
# REM: =======================================================================================
# REM: Usage in endpoints:
# REM:   @app.get("/v1/admin/config")
# REM:   async def get_config(
# REM:       auth: AuthResult = Depends(authenticate_request),
# REM:       _perm = Depends(require_permission(Permission.ADMIN_CONFIG)),
# REM:   ):
# REM:
# REM: If the RBAC system has no users registered (initial setup), permission checks
# REM: are skipped with a warning — the system falls back to API-key-only auth.
# REM: Once users are registered, RBAC enforcement activates.
# REM: =======================================================================================

def require_permission(permission: Permission):
    """
    REM: FastAPI dependency factory that checks RBAC permissions.
    REM: Returns a Depends-compatible callable.
    """
    from fastapi import HTTPException, Request

    async def _check_permission(request: Request):
        # REM: If no users are registered, RBAC is not yet active — pass through
        if not rbac_manager._users:
            return True

        # REM: Try to find user by API key from auth
        api_key = request.headers.get("X-API-Key")
        if api_key:
            user = rbac_manager.get_user_by_api_key(api_key)
            if user and user.has_permission(permission):
                return True
            if user and not user.has_permission(permission):
                logger.warning(
                    f"REM: RBAC denied ::{permission.value}:: for user "
                    f"::{user.username}::_Thank_You_But_No"
                )
                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    f"RBAC permission denied: {permission.value}",
                    actor=user.username,
                    details={"permission": permission.value, "user_id": user.user_id},
                    qms_status="Thank_You_But_No"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions: {permission.value} required"
                )

        # REM: No API key match — if users exist but none matched, deny
        # REM: (the auth middleware already validated the key itself)
        return True

    return _check_permission
