# TelsonBase/core/tenant_rate_limiting.py
# REM: =======================================================================================
# REM: TENANT-SCOPED RATE LIMITING
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.4.0CC: New feature - Tenant-scoped rate limiting with Redis sliding window
#
# REM: Mission Statement: Enforce per-tenant and per-user request quotas using a Redis
# REM: sliding window algorithm. Premium tenants receive higher limits. Quota changes
# REM: are audit-logged. Falls back to in-memory tracking when Redis is unavailable.
#
# REM: Features:
# REM:   - Per-tenant and per-user sliding window rate limits
# REM:   - Redis-backed sorted sets with automatic TTL cleanup
# REM:   - Configurable per-tenant quota overrides (admin action)
# REM:   - Premium tenant multiplier (2x default)
# REM:   - Burst allowance (1.5x base rate)
# REM:   - In-memory fallback when Redis is unavailable
# REM:   - Usage reporting with quota utilization percentages
# REM:   - FastAPI dependency for endpoint enforcement
#
# REM: QMS Protocol:
# REM:   Rate limited: Tenant_Rate_Limited_Thank_You_But_No with ::tenant_id:: ::user_id::
# REM:   Quota changed: Tenant_Quota_Updated_Thank_You with ::tenant_id:: ::set_by::
# REM: =======================================================================================

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict

from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse

from core.audit import audit, AuditEventType
from core.auth import AuthResult, authenticate_request

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: DEFAULT CONFIGURATION
# REM: =======================================================================================

DEFAULT_TENANT_REQUESTS_PER_MINUTE = 600
DEFAULT_USER_REQUESTS_PER_MINUTE = 120
BURST_MULTIPLIER = 1.5
PREMIUM_TENANT_MULTIPLIER = 2.0
REDIS_KEY_TTL_SECONDS = 120


# REM: =======================================================================================
# REM: IN-MEMORY FALLBACK STATE
# REM: =======================================================================================

@dataclass
class _InMemoryBucket:
    """REM: Fallback sliding window bucket when Redis is unavailable."""
    timestamps: list = field(default_factory=list)

    def add_and_count(self, now: float, window_seconds: float = 60.0) -> int:
        """REM: Add current timestamp and return count within window."""
        cutoff = now - window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        self.timestamps.append(now)
        return len(self.timestamps)

    def count(self, now: float, window_seconds: float = 60.0) -> int:
        """REM: Return count within window without adding."""
        cutoff = now - window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        return len(self.timestamps)


# REM: =======================================================================================
# REM: REDIS HELPERS — Lazy import
# REM: =======================================================================================

def _get_redis_client():
    """REM: Lazy import Redis client to avoid circular imports."""
    try:
        from core.config import get_settings
        _settings = get_settings()
        import redis
        return redis.Redis.from_url(_settings.redis_url, decode_responses=True)
    except Exception:
        return None


# REM: =======================================================================================
# REM: TENANT RATE LIMITER
# REM: =======================================================================================

class TenantRateLimiter:
    """
    REM: Redis-backed, tenant-aware rate limiter.
    REM: Enforces per-tenant and per-user quotas using sorted-set sliding windows.
    REM: Falls back to in-memory tracking when Redis is unavailable.
    """

    def __init__(self):
        self._fallback_tenant_buckets: Dict[str, _InMemoryBucket] = defaultdict(_InMemoryBucket)
        self._fallback_user_buckets: Dict[str, _InMemoryBucket] = defaultdict(_InMemoryBucket)
        self._redis_warned: bool = False

    # REM: ---------------------------------------------------------------------------------
    # REM: REDIS KEY BUILDERS
    # REM: ---------------------------------------------------------------------------------

    @staticmethod
    def _tenant_key(tenant_id: str, minute_bucket: int) -> str:
        return f"ratelimit:tenant:{tenant_id}:{minute_bucket}"

    @staticmethod
    def _user_key(user_id: str, minute_bucket: int) -> str:
        return f"ratelimit:user:{user_id}:{minute_bucket}"

    @staticmethod
    def _quota_key(tenant_id: str) -> str:
        return f"ratelimit:quota:{tenant_id}"

    @staticmethod
    def _minute_bucket(now: float) -> int:
        """REM: Current minute bucket for Redis key partitioning."""
        return int(now // 60)

    # REM: ---------------------------------------------------------------------------------
    # REM: QUOTA MANAGEMENT
    # REM: ---------------------------------------------------------------------------------

    def get_tenant_quota(self, tenant_id: str) -> Dict[str, Any]:
        """
        REM: Return current quota settings for a tenant.
        REM: Checks Redis for per-tenant overrides; falls back to defaults.
        """
        defaults = {
            "tenant_id": tenant_id,
            "requests_per_minute": DEFAULT_TENANT_REQUESTS_PER_MINUTE,
            "user_requests_per_minute": DEFAULT_USER_REQUESTS_PER_MINUTE,
            "burst_multiplier": BURST_MULTIPLIER,
            "premium_multiplier": 1.0,
            "is_custom": False,
        }

        client = _get_redis_client()
        if client:
            try:
                data = client.hgetall(self._quota_key(tenant_id))
                if data:
                    defaults["requests_per_minute"] = int(data.get(
                        "requests_per_minute", DEFAULT_TENANT_REQUESTS_PER_MINUTE
                    ))
                    defaults["user_requests_per_minute"] = int(data.get(
                        "user_requests_per_minute", DEFAULT_USER_REQUESTS_PER_MINUTE
                    ))
                    defaults["burst_multiplier"] = float(data.get(
                        "burst_multiplier", BURST_MULTIPLIER
                    ))
                    defaults["premium_multiplier"] = float(data.get(
                        "premium_multiplier", 1.0
                    ))
                    defaults["is_custom"] = True
            except Exception as e:
                logger.warning(
                    f"REM: Redis quota lookup failed for ::{tenant_id}::, "
                    f"using defaults: {e}_Thank_You_But_No"
                )

        # REM: Apply premium multiplier to effective limits
        effective_rpm = int(
            defaults["requests_per_minute"] * defaults["premium_multiplier"]
        )
        effective_user_rpm = int(
            defaults["user_requests_per_minute"] * defaults["premium_multiplier"]
        )
        defaults["effective_requests_per_minute"] = effective_rpm
        defaults["effective_user_requests_per_minute"] = effective_user_rpm

        return defaults

    def set_tenant_quota(
        self,
        tenant_id: str,
        requests_per_minute: int,
        set_by: str,
        user_requests_per_minute: Optional[int] = None,
        premium_multiplier: Optional[float] = None,
    ) -> bool:
        """
        REM: Set custom quota for a tenant (admin action).
        REM: Persists to Redis and audit-logs the change.
        """
        client = _get_redis_client()
        if not client:
            logger.error(
                f"REM: Cannot set tenant quota — Redis unavailable_Thank_You_But_No"
            )
            return False

        try:
            quota_data = {
                "requests_per_minute": str(requests_per_minute),
                "user_requests_per_minute": str(
                    user_requests_per_minute or DEFAULT_USER_REQUESTS_PER_MINUTE
                ),
                "burst_multiplier": str(BURST_MULTIPLIER),
                "premium_multiplier": str(
                    premium_multiplier if premium_multiplier is not None else 1.0
                ),
                "set_by": set_by,
                "set_at": datetime.now(timezone.utc).isoformat(),
            }
            client.hset(self._quota_key(tenant_id), mapping=quota_data)

            logger.info(
                f"REM: Tenant quota updated for ::{tenant_id}:: "
                f"rpm={requests_per_minute} by ::{set_by}::_Thank_You"
            )
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Tenant rate limit quota updated: {tenant_id}",
                actor=set_by,
                resource=tenant_id,
                details={
                    "requests_per_minute": requests_per_minute,
                    "user_requests_per_minute": (
                        user_requests_per_minute or DEFAULT_USER_REQUESTS_PER_MINUTE
                    ),
                    "premium_multiplier": (
                        premium_multiplier if premium_multiplier is not None else 1.0
                    ),
                },
                qms_status="Thank_You"
            )
            return True
        except Exception as e:
            logger.error(
                f"REM: Failed to set tenant quota for ::{tenant_id}::: "
                f"{e}_Thank_You_But_No"
            )
            return False

    # REM: ---------------------------------------------------------------------------------
    # REM: RATE LIMIT CHECK
    # REM: ---------------------------------------------------------------------------------

    def check_rate_limit(
        self, tenant_id: str, user_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        REM: Check both tenant-level and user-level rate limits.
        REM: Uses Redis sliding window (sorted set with timestamp scores).
        REM: Falls back to in-memory tracking if Redis is unavailable.

        Returns:
            (allowed: bool, info: dict with remaining, limit, reset_at)
        """
        now = time.time()
        minute_bucket = self._minute_bucket(now)
        quota = self.get_tenant_quota(tenant_id)

        tenant_limit = int(quota["effective_requests_per_minute"] * BURST_MULTIPLIER)
        user_limit = int(quota["effective_user_requests_per_minute"] * BURST_MULTIPLIER)
        reset_at = (minute_bucket + 1) * 60

        client = _get_redis_client()

        if client:
            try:
                return self._check_redis(
                    client, tenant_id, user_id, now, minute_bucket,
                    tenant_limit, user_limit, quota, reset_at
                )
            except Exception as e:
                logger.warning(
                    f"REM: Redis rate limit check failed, falling back to "
                    f"in-memory: {e}_Thank_You_But_No"
                )

        # REM: In-memory fallback
        return self._check_in_memory(
            tenant_id, user_id, now, tenant_limit, user_limit, quota, reset_at
        )

    def _check_redis(
        self, client, tenant_id: str, user_id: str, now: float,
        minute_bucket: int, tenant_limit: int, user_limit: int,
        quota: Dict, reset_at: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """REM: Redis sliding-window rate limit check using sorted sets."""
        window_start = now - 60.0
        tenant_rkey = self._tenant_key(tenant_id, minute_bucket)
        user_rkey = self._user_key(user_id, minute_bucket)

        pipe = client.pipeline(transaction=True)

        # REM: Clean old entries and count current window for tenant
        pipe.zremrangebyscore(tenant_rkey, "-inf", window_start)
        pipe.zcard(tenant_rkey)

        # REM: Clean old entries and count current window for user
        pipe.zremrangebyscore(user_rkey, "-inf", window_start)
        pipe.zcard(user_rkey)

        results = pipe.execute()
        tenant_count = results[1]
        user_count = results[3]

        # REM: Check tenant limit
        if tenant_count >= tenant_limit:
            return False, self._build_info(
                allowed=False,
                reason="tenant_limit",
                tenant_id=tenant_id,
                user_id=user_id,
                tenant_count=tenant_count,
                user_count=user_count,
                tenant_limit=tenant_limit,
                user_limit=user_limit,
                reset_at=reset_at,
                quota=quota,
            )

        # REM: Check user limit
        if user_count >= user_limit:
            return False, self._build_info(
                allowed=False,
                reason="user_limit",
                tenant_id=tenant_id,
                user_id=user_id,
                tenant_count=tenant_count,
                user_count=user_count,
                tenant_limit=tenant_limit,
                user_limit=user_limit,
                reset_at=reset_at,
                quota=quota,
            )

        # REM: Allowed — record the request
        member = f"{now}"
        pipe2 = client.pipeline(transaction=True)
        pipe2.zadd(tenant_rkey, {member: now})
        pipe2.expire(tenant_rkey, REDIS_KEY_TTL_SECONDS)
        pipe2.zadd(user_rkey, {member: now})
        pipe2.expire(user_rkey, REDIS_KEY_TTL_SECONDS)
        pipe2.execute()

        return True, self._build_info(
            allowed=True,
            reason=None,
            tenant_id=tenant_id,
            user_id=user_id,
            tenant_count=tenant_count + 1,
            user_count=user_count + 1,
            tenant_limit=tenant_limit,
            user_limit=user_limit,
            reset_at=reset_at,
            quota=quota,
        )

    def _check_in_memory(
        self, tenant_id: str, user_id: str, now: float,
        tenant_limit: int, user_limit: int, quota: Dict, reset_at: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """REM: In-memory fallback rate limit check."""
        if not self._redis_warned:
            logger.warning(
                "REM: Tenant rate limiting using in-memory fallback — "
                "Redis unavailable_Thank_You_But_No"
            )
            self._redis_warned = True

        t_bucket = self._fallback_tenant_buckets[tenant_id]
        u_bucket = self._fallback_user_buckets[user_id]

        tenant_count = t_bucket.count(now)
        user_count = u_bucket.count(now)

        # REM: Check tenant limit
        if tenant_count >= tenant_limit:
            return False, self._build_info(
                allowed=False, reason="tenant_limit",
                tenant_id=tenant_id, user_id=user_id,
                tenant_count=tenant_count, user_count=user_count,
                tenant_limit=tenant_limit, user_limit=user_limit,
                reset_at=reset_at, quota=quota,
            )

        # REM: Check user limit
        if user_count >= user_limit:
            return False, self._build_info(
                allowed=False, reason="user_limit",
                tenant_id=tenant_id, user_id=user_id,
                tenant_count=tenant_count, user_count=user_count,
                tenant_limit=tenant_limit, user_limit=user_limit,
                reset_at=reset_at, quota=quota,
            )

        # REM: Allowed — record
        t_bucket.add_and_count(now)
        u_bucket.add_and_count(now)

        return True, self._build_info(
            allowed=True, reason=None,
            tenant_id=tenant_id, user_id=user_id,
            tenant_count=tenant_count + 1, user_count=user_count + 1,
            tenant_limit=tenant_limit, user_limit=user_limit,
            reset_at=reset_at, quota=quota,
        )

    @staticmethod
    def _build_info(
        allowed: bool, reason: Optional[str],
        tenant_id: str, user_id: str,
        tenant_count: int, user_count: int,
        tenant_limit: int, user_limit: int,
        reset_at: float, quota: Dict,
    ) -> Dict[str, Any]:
        """REM: Build standardized rate limit info response."""
        return {
            "allowed": allowed,
            "reason": reason,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "tenant": {
                "used": tenant_count,
                "limit": tenant_limit,
                "remaining": max(0, tenant_limit - tenant_count),
            },
            "user": {
                "used": user_count,
                "limit": user_limit,
                "remaining": max(0, user_limit - user_count),
            },
            "reset_at": int(reset_at),
            "retry_after": max(1, int(reset_at - time.time())) if not allowed else 0,
            "quota": quota,
        }

    # REM: ---------------------------------------------------------------------------------
    # REM: USAGE REPORTING
    # REM: ---------------------------------------------------------------------------------

    def get_usage_report(self, tenant_id: str) -> Dict[str, Any]:
        """
        REM: Return usage report for a tenant.
        REM: Includes current minute usage, daily usage trend, and quota utilization.
        """
        now = time.time()
        minute_bucket = self._minute_bucket(now)
        quota = self.get_tenant_quota(tenant_id)
        effective_limit = quota["effective_requests_per_minute"]

        current_minute_count = 0
        daily_buckets: Dict[int, int] = {}

        client = _get_redis_client()
        if client:
            try:
                # REM: Current minute usage
                tenant_rkey = self._tenant_key(tenant_id, minute_bucket)
                window_start = now - 60.0
                client.zremrangebyscore(tenant_rkey, "-inf", window_start)
                current_minute_count = client.zcard(tenant_rkey)

                # REM: Scan last 1440 minutes (24 hours) for daily trend
                for offset in range(0, 1440, 10):
                    bucket = minute_bucket - offset
                    rkey = self._tenant_key(tenant_id, bucket)
                    count = client.zcard(rkey)
                    if count > 0:
                        hour_offset = offset // 60
                        daily_buckets[hour_offset] = (
                            daily_buckets.get(hour_offset, 0) + count
                        )
            except Exception as e:
                logger.warning(
                    f"REM: Usage report Redis error for ::{tenant_id}::: "
                    f"{e}_Thank_You_But_No"
                )
        else:
            # REM: In-memory fallback
            t_bucket = self._fallback_tenant_buckets.get(tenant_id)
            if t_bucket:
                current_minute_count = t_bucket.count(now)

        utilization_pct = (
            (current_minute_count / effective_limit * 100.0)
            if effective_limit > 0 else 0.0
        )

        return {
            "tenant_id": tenant_id,
            "current_minute": {
                "used": current_minute_count,
                "limit": effective_limit,
                "utilization_pct": round(utilization_pct, 2),
            },
            "daily_trend_by_hour": daily_buckets,
            "quota": quota,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# REM: =======================================================================================
# REM: FASTAPI DEPENDENCY
# REM: =======================================================================================

async def enforce_tenant_rate_limit(
    request: Request,
    auth: AuthResult = Depends(authenticate_request),
) -> AuthResult:
    """
    REM: FastAPI dependency that enforces tenant-scoped rate limits.
    REM: Extract tenant_id from X-Tenant-ID header or auth context.
    REM: If denied, raises HTTP 429 with Retry-After header.
    REM: Sets X-RateLimit-Remaining and X-RateLimit-Limit headers on response.
    """
    # REM: Extract tenant_id from header or auth actor
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        # REM: Fall back to extracting from auth actor (e.g. "owner:label")
        tenant_id = f"default_{auth.actor.split(':')[0]}"

    user_id = auth.actor

    allowed, info = tenant_rate_limiter.check_rate_limit(tenant_id, user_id)

    if not allowed:
        logger.warning(
            f"REM: Tenant rate limited ::{tenant_id}:: user=::{user_id}:: "
            f"reason={info['reason']}_Thank_You_But_No"
        )
        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Tenant rate limit exceeded: {tenant_id} user={user_id}",
            actor=user_id,
            resource=tenant_id,
            details={
                "reason": info["reason"],
                "tenant_used": info["tenant"]["used"],
                "tenant_limit": info["tenant"]["limit"],
                "user_used": info["user"]["used"],
                "user_limit": info["user"]["limit"],
            },
            qms_status="Thank_You_But_No"
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "qms_status": "Thank_You_But_No",
                "reason": info["reason"],
                "retry_after": info["retry_after"],
                "tenant_limit": info["tenant"]["limit"],
                "tenant_remaining": info["tenant"]["remaining"],
                "user_limit": info["user"]["limit"],
                "user_remaining": info["user"]["remaining"],
            },
            headers={
                "Retry-After": str(info["retry_after"]),
                "X-RateLimit-Limit": str(info["tenant"]["limit"]),
                "X-RateLimit-Remaining": str(info["tenant"]["remaining"]),
                "X-RateLimit-User-Limit": str(info["user"]["limit"]),
                "X-RateLimit-User-Remaining": str(info["user"]["remaining"]),
            },
        )

    # REM: Store rate limit info in request state for response header injection
    request.state.rate_limit_info = info

    return auth


# REM: =======================================================================================
# REM: API ROUTER — Admin endpoints for rate limit management
# REM: =======================================================================================

from fastapi import APIRouter
from core.auth import require_permission

tenant_rate_limit_router = APIRouter(
    prefix="/v1/system/rate-limits",
    tags=["rate-limits"],
)


@tenant_rate_limit_router.get("/{tenant_id}")
async def get_tenant_rate_limit_status(
    tenant_id: str,
    auth: AuthResult = Depends(require_permission("admin")),
):
    """
    REM: Get a tenant's current rate limit status and usage report.
    REM: Requires admin permission.
    """
    quota = tenant_rate_limiter.get_tenant_quota(tenant_id)
    usage = tenant_rate_limiter.get_usage_report(tenant_id)

    return {
        "qms_status": "Thank_You",
        "tenant_id": tenant_id,
        "quota": quota,
        "usage": usage,
    }


@tenant_rate_limit_router.put("/{tenant_id}")
async def set_tenant_rate_limit_quota(
    tenant_id: str,
    requests_per_minute: int,
    user_requests_per_minute: Optional[int] = None,
    premium_multiplier: Optional[float] = None,
    auth: AuthResult = Depends(require_permission("admin")),
):
    """
    REM: Set custom rate limit quota for a tenant.
    REM: Requires admin permission. Changes are audit-logged.
    """
    success = tenant_rate_limiter.set_tenant_quota(
        tenant_id=tenant_id,
        requests_per_minute=requests_per_minute,
        set_by=auth.actor,
        user_requests_per_minute=user_requests_per_minute,
        premium_multiplier=premium_multiplier,
    )

    if not success:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Failed to set tenant quota — Redis unavailable",
                "qms_status": "Thank_You_But_No",
            },
        )

    return {
        "qms_status": "Thank_You",
        "tenant_id": tenant_id,
        "requests_per_minute": requests_per_minute,
        "user_requests_per_minute": (
            user_requests_per_minute or DEFAULT_USER_REQUESTS_PER_MINUTE
        ),
        "premium_multiplier": premium_multiplier if premium_multiplier is not None else 1.0,
        "set_by": auth.actor,
    }


# REM: =======================================================================================
# REM: GLOBAL SINGLETON
# REM: =======================================================================================

tenant_rate_limiter = TenantRateLimiter()


# REM: =======================================================================================
# REM: EXPORTS
# REM: =======================================================================================

__all__ = [
    "TenantRateLimiter",
    "tenant_rate_limiter",
    "enforce_tenant_rate_limit",
    "tenant_rate_limit_router",
    "DEFAULT_TENANT_REQUESTS_PER_MINUTE",
    "DEFAULT_USER_REQUESTS_PER_MINUTE",
    "BURST_MULTIPLIER",
    "PREMIUM_TENANT_MULTIPLIER",
]
