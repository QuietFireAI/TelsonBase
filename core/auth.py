# TelsonBase/core/auth.py
# REM: =======================================================================================
# REM: AUTHENTICATION & AUTHORIZATION FOR THE TelsonBase
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Zero-trust API security. Every request must be authenticated.
# REM: No exceptions. This module provides API key validation and JWT token handling.
# REM: =======================================================================================

import hmac
import uuid
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from core.config import get_settings
from core.audit import audit, AuditEventType  # FIXED v3.0.1: Import AuditEventType directly

settings = get_settings()
logger = logging.getLogger(__name__)

# REM: =======================================================================================
# REM: API KEY AUTH AUDIT RATE LIMITER
# REM: =======================================================================================
# REM: Machine-to-machine API key polls (dashboard, agents) authenticate on every request.
# REM: Logging auth.success for each poll floods the cryptographic audit chain with noise,
# REM: obscuring meaningful governance events and inflating sequence numbers.
# REM: Solution: only log API key auth.success once per APIKEY_AUDIT_INTERVAL per actor.
# REM: JWT (human login) and DID (agent identity) auth events are ALWAYS logged.
# REM: =======================================================================================
_apikey_last_logged: Dict[str, datetime] = {}
APIKEY_AUDIT_INTERVAL = timedelta(minutes=5)


def _should_log_apikey_auth(actor: str) -> bool:
    """REM: Return True only if this actor hasn't had a successful API key auth logged recently."""
    now = datetime.now(timezone.utc)
    last = _apikey_last_logged.get(actor)
    if last is None or (now - last) >= APIKEY_AUDIT_INTERVAL:
        _apikey_last_logged[actor] = now
        return True
    return False

# REM: Security schemes for FastAPI's automatic docs
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)
# REM: v7.3.0CC — Identiclaw DID authentication header
# REM: Format: <did>|<base64-signature>|<nonce>|<timestamp>
did_auth_header = APIKeyHeader(name="X-DID-Auth", auto_error=False)

# REM: =======================================================================================
# REM: JWT REVOCATION LIST (v5.3.0CC)
# REM: =======================================================================================
# REM: Redis-backed set of revoked JWT `jti` claims. Each entry has a TTL matching
# REM: the token's remaining lifetime so Redis auto-cleans expired revocations.
# REM: Fallback: in-memory set if Redis is unavailable (cleared on restart).
# REM: =======================================================================================

_REVOCATION_PREFIX = "jwt:revoked:"
_revoked_tokens_fallback: set = set()  # In-memory fallback


def _get_redis_client():
    """REM: Lazy import Redis client to avoid circular imports."""
    try:
        import redis
        return redis.Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None


def revoke_token(jti: str, expires_at: datetime, revoked_by: str = "system") -> bool:
    """
    REM: Revoke a JWT by its jti claim. Stores in Redis with TTL.
    """
    now = datetime.now(timezone.utc)
    ttl_seconds = max(int((expires_at - now).total_seconds()), 1)

    client = _get_redis_client()
    if client:
        try:
            client.setex(f"{_REVOCATION_PREFIX}{jti}", ttl_seconds, "revoked")
        except Exception as e:
            logger.warning(f"REM: Redis revocation failed, using fallback: {e}")
            _revoked_tokens_fallback.add(jti)
    else:
        _revoked_tokens_fallback.add(jti)

    audit.log(
        AuditEventType.SECURITY_ALERT,
        f"JWT token revoked: {jti}",
        actor=revoked_by,
        details={"jti": jti, "ttl_seconds": ttl_seconds},
        qms_status="Thank_You"
    )
    logger.info(f"REM: JWT revoked ::{jti}:: by ::{revoked_by}::_Thank_You")
    return True


def is_token_revoked(jti: str) -> bool:
    """REM: Check if a JWT jti has been revoked."""
    if jti in _revoked_tokens_fallback:
        return True
    client = _get_redis_client()
    if client:
        try:
            return client.exists(f"{_REVOCATION_PREFIX}{jti}") > 0
        except Exception:
            pass
    return False


class TokenData(BaseModel):
    """REM: Data extracted from a validated JWT token."""
    sub: str  # Subject (API key identifier or user ID)
    exp: datetime
    jti: str = ""  # Unique token ID for revocation (v5.3.0CC)
    permissions: list[str] = []


class AuthResult(BaseModel):
    """REM: Result of authentication check."""
    authenticated: bool
    actor: str  # Who is making the request
    method: str  # How they authenticated (api_key, jwt)
    permissions: list[str] = []


# REM: =======================================================================================
# REM: API KEY REGISTRY (v5.3.0CC)
# REM: =======================================================================================
# REM: Supports multiple API keys with per-key scoped permissions, labels, and
# REM: zero-downtime rotation. Keys are stored in Redis; the master key from config
# REM: is always accepted as a fallback (backward compatible).
# REM:
# REM: Key record stored in Redis hash "apikeys:<key_hash>":
# REM:   { label, owner, permissions (JSON list), created_at, active }
# REM:
# REM: Keys are hashed with SHA-256 before storage — the raw key is never stored.
# REM: =======================================================================================

import hashlib

_APIKEY_PREFIX = "apikeys:"


def _hash_key(api_key: str) -> str:
    """REM: One-way hash of API key for storage lookup (SHA-256)."""
    return hashlib.sha256(api_key.encode()).hexdigest()


class APIKeyRecord(BaseModel):
    """REM: Metadata for a registered API key."""
    label: str
    owner: str
    permissions: list[str] = ["*"]
    created_at: str = ""
    active: bool = True


class APIKeyRegistry:
    """
    REM: v5.3.0CC — Redis-backed multi-key registry with scoped permissions.
    REM: The master key from config is always valid (backward compat).
    REM: Additional keys can be created, rotated, and revoked at runtime.
    """

    def validate(self, api_key: str) -> Optional[APIKeyRecord]:
        """
        REM: Validate an API key. Checks registered keys first, then master key.
        Returns APIKeyRecord if valid, None if invalid.
        """
        if not api_key:
            return None

        # REM: Check Redis registry first (per-user scoped keys)
        record = self._lookup_registered(api_key)
        if record:
            return record

        # REM: Fallback: master key from config (backward compatible)
        if hmac.compare_digest(api_key, settings.mcp_api_key):
            return APIKeyRecord(
                label="master",
                owner="system",
                permissions=["*"],
                created_at="config",
                active=True
            )

        return None

    def _lookup_registered(self, api_key: str) -> Optional[APIKeyRecord]:
        """REM: Look up a key in the Redis registry."""
        client = _get_redis_client()
        if not client:
            return None
        try:
            key_hash = _hash_key(api_key)
            data = client.get(f"{_APIKEY_PREFIX}{key_hash}")
            if data:
                record = APIKeyRecord.model_validate_json(data)
                if record.active:
                    return record
        except Exception as e:
            logger.warning(f"REM: API key registry lookup failed: {e}")
        return None

    def register_key(
        self,
        api_key: str,
        label: str,
        owner: str,
        permissions: List[str],
        registered_by: str = "system"
    ) -> bool:
        """REM: Register a new API key with scoped permissions."""
        client = _get_redis_client()
        if not client:
            logger.error("REM: Cannot register API key — Redis unavailable_Thank_You_But_No")
            return False
        try:
            key_hash = _hash_key(api_key)
            record = APIKeyRecord(
                label=label,
                owner=owner,
                permissions=permissions,
                created_at=datetime.now(timezone.utc).isoformat(),
                active=True
            )
            client.set(f"{_APIKEY_PREFIX}{key_hash}", record.model_dump_json())
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"API key registered: {label} for {owner}",
                actor=registered_by,
                details={"label": label, "owner": owner, "permissions": permissions},
                qms_status="Thank_You"
            )
            logger.info(f"REM: API key registered ::{label}:: for ::{owner}::_Thank_You")
            return True
        except Exception as e:
            logger.error(f"REM: API key registration failed: {e}_Thank_You_But_No")
            return False

    def revoke_key(self, api_key: str, revoked_by: str = "system") -> bool:
        """REM: Revoke an API key (zero-downtime rotation)."""
        client = _get_redis_client()
        if not client:
            return False
        try:
            key_hash = _hash_key(api_key)
            data = client.get(f"{_APIKEY_PREFIX}{key_hash}")
            if data:
                record = APIKeyRecord.model_validate_json(data)
                record.active = False
                client.set(f"{_APIKEY_PREFIX}{key_hash}", record.model_dump_json())
                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    f"API key revoked: {record.label}",
                    actor=revoked_by,
                    details={"label": record.label, "owner": record.owner},
                    qms_status="Thank_You"
                )
                logger.warning(f"REM: API key revoked ::{record.label}::_Thank_You")
                return True
        except Exception as e:
            logger.error(f"REM: API key revocation failed: {e}_Thank_You_But_No")
        return False


# REM: Global API key registry
api_key_registry = APIKeyRegistry()


def validate_api_key(api_key: str) -> bool:
    """
    REM: Validate the provided API key.
    REM: v5.3.0CC: Now checks Redis registry first, then falls back to master key.
    REM: Kept for backward compatibility — new code should use api_key_registry.validate().
    """
    return api_key_registry.validate(api_key) is not None


def create_access_token(subject: str, permissions: list[str] = None, expires_delta: Optional[timedelta] = None) -> str:
    """
    REM: Create a JWT access token.
    
    Args:
        subject: The identifier for the token holder (API key ID, user ID)
        permissions: List of permission strings
        expires_delta: Custom expiration time (defaults to config value)
    
    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiration_hours)
    
    token_id = f"jti_{uuid.uuid4().hex[:16]}"
    to_encode = {
        "sub": subject,
        "exp": expire,
        "jti": token_id,
        "permissions": permissions or [],
        "iat": datetime.now(timezone.utc),
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    
    audit.log(
        AuditEventType.AUTH_TOKEN_ISSUED,  # FIXED v3.0.1: Use imported enum, not audit.AuditEventType
        f"JWT token issued for ::{subject}::",
        actor=subject,
        details={"expires": expire.isoformat()}
    )
    
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """
    REM: Decode and validate a JWT token.
    
    Returns:
        TokenData if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        jti = payload.get("jti", "")
        # REM: v5.3.0CC — Check revocation list before accepting token
        if jti and is_token_revoked(jti):
            logger.warning(f"REM: Revoked JWT presented ::{jti}::_Thank_You_But_No")
            return None
        return TokenData(
            sub=payload.get("sub"),
            exp=datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc),
            jti=jti,
            permissions=payload.get("permissions", [])
        )
    except JWTError:
        return None


async def authenticate_request(
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    did_auth: Optional[str] = Security(did_auth_header),
) -> AuthResult:
    """
    REM: FastAPI dependency that authenticates incoming requests.
    REM: Supports API key (X-API-Key), Bearer token, and DID (X-DID-Auth) authentication.
    REM: v7.3.0CC: Added DID authentication via Identiclaw MCP-I.

    Usage in endpoints:
        @app.get("/protected")
        async def protected_route(auth: AuthResult = Depends(authenticate_request)):
            ...
    """
    # REM: Try API key first
    # REM: v5.3.0CC — Uses registry for per-key scoped permissions
    if api_key:
        key_record = api_key_registry.validate(api_key)
        if key_record:
            actor = f"{key_record.owner}:{key_record.label}"
            # REM: Rate-limit API key auth logging — only write to chain once per 5 min per actor
            # REM: Suppresses dashboard polling noise (57k+ events → ~12/hr per key)
            if _should_log_apikey_auth(actor):
                audit.auth_success(actor=actor, details={"method": "api_key", "label": key_record.label})
            return AuthResult(
                authenticated=True,
                actor=actor,
                method="api_key",
                permissions=key_record.permissions
            )
        else:
            audit.auth_failure(actor="unknown", reason="Invalid API key")
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "API key"}
            )

    # REM: Try Bearer token
    if bearer:
        token_data = decode_token(bearer.credentials)
        if token_data:
            audit.auth_success(actor=token_data.sub, details={"method": "jwt"})
            return AuthResult(
                authenticated=True,
                actor=token_data.sub,
                method="jwt",
                permissions=token_data.permissions
            )
        else:
            audit.auth_failure(actor="unknown", reason="Invalid or expired JWT token")
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )

    # REM: v7.3.0CC — Try DID authentication (Identiclaw MCP-I)
    # REM: Only active when IDENTICLAW_ENABLED=true. Silently skipped otherwise.
    if did_auth:
        if settings.identiclaw_enabled:
            try:
                from core.identiclaw import identiclaw_manager
                from fastapi import Request

                # REM: Extract request path and method from the scope
                # REM: The IdenticlawManager handles all verification locally
                did_result = identiclaw_manager.authenticate_from_header(
                    did_auth, "/", "GET"  # Path/method populated by middleware if needed
                )
                if did_result:
                    actor = f"did:{did_result.did}"
                    audit.auth_success(actor=actor, details={"method": "did", "did": did_result.did})
                    return AuthResult(
                        authenticated=True,
                        actor=actor,
                        method="did",
                        permissions=did_result.telsonbase_permissions
                    )
                else:
                    audit.auth_failure(actor="unknown_did", reason="DID authentication failed")
                    raise HTTPException(
                        status_code=401,
                        detail="DID authentication failed",
                        headers={"WWW-Authenticate": "DID"}
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"REM: DID auth error: {e}_Thank_You_But_No")
                audit.auth_failure(actor="unknown_did", reason=f"DID auth error: {e}")
                raise HTTPException(
                    status_code=401,
                    detail="DID authentication error",
                    headers={"WWW-Authenticate": "DID"}
                )
        else:
            # REM: Identiclaw disabled — ignore the DID header silently
            logger.debug("REM: X-DID-Auth header present but IDENTICLAW_ENABLED=false, ignoring")

    # REM: No credentials provided
    audit.auth_failure(actor="anonymous", reason="No credentials provided")
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide X-API-Key header, Bearer token, or X-DID-Auth header.",
        headers={"WWW-Authenticate": "API key, Bearer, DID"}
    )


async def optional_auth(
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    did_auth: Optional[str] = Security(did_auth_header),
) -> Optional[AuthResult]:
    """
    REM: Optional authentication - returns None if no credentials provided.
    REM: Use for endpoints that can work both authenticated and anonymously.
    REM: v7.3.0CC: Added DID authentication support.
    """
    if not api_key and not bearer and not did_auth:
        return None

    return await authenticate_request(api_key, bearer, did_auth)


def require_permission(required_permission: str):
    """
    REM: Dependency factory for permission-based access control.
    
    Usage:
        @app.post("/admin/action")
        async def admin_action(auth: AuthResult = Depends(require_permission("admin"))):
            ...
    """
    async def permission_checker(auth: AuthResult = Depends(authenticate_request)) -> AuthResult:
        if "*" in auth.permissions or required_permission in auth.permissions:
            return auth
        
        audit.log(
            AuditEventType.AUTH_FAILURE,  # FIXED v3.0.1: Use imported enum, not audit.AuditEventType
            f"Permission denied: ::{required_permission}:: required",
            actor=auth.actor,
            details={"required": required_permission, "had": auth.permissions}
        )
        raise HTTPException(
            status_code=403,
            detail=f"Permission '{required_permission}' required"
        )
    
    return permission_checker
