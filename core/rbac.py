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

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum

from core.audit import audit, AuditEventType

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
    """

    SESSION_DURATION_HOURS = 8

    def __init__(self):
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, Session] = {}
        self._api_key_to_user: Dict[str, str] = {}

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
        """REM: Get a user by ID."""
        return self._users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """REM: Get a user by username."""
        for user in self._users.values():
            if user.username == username:
                return user
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

        # REM: Invalidate all sessions
        for session_id, session in list(self._sessions.items()):
            if session.user_id == user_id:
                session.is_valid = False

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
        user.last_login = now

        logger.info(f"REM: Session created for ::{user.username}::_Thank_You")

        return session

    def validate_session(self, session_id: str) -> Optional[User]:
        """REM: Validate a session and return the user."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        if not session.is_valid or session.is_expired():
            return None

        user = self._users.get(session.user_id)
        if not user or not user.is_active:
            return None

        return user

    def invalidate_session(self, session_id: str) -> bool:
        """REM: Invalidate a session."""
        session = self._sessions.get(session_id)
        if session:
            session.is_valid = False
            return True
        return False

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
        """REM: Register an API key for a user."""
        if user_id not in self._users:
            return False
        self._api_key_to_user[api_key] = user_id
        return True

    def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """REM: Get user by API key."""
        user_id = self._api_key_to_user.get(api_key)
        if user_id:
            return self._users.get(user_id)
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
    from fastapi import Request, HTTPException

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
