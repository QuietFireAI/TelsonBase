# TelsonBase/core/middleware.py
# REM: =======================================================================================
# REM: PRODUCTION HARDENING MIDDLEWARE FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Security and stability middleware for production deployments.
# REM: Includes:
# REM:   - Rate limiting (prevent abuse)
# REM:   - Request size limits (prevent memory exhaustion)
# REM:   - Circuit breaker (graceful degradation)
# REM:   - Request ID tracking (audit trail)
# REM:   - Slow request logging (performance monitoring)
# REM:
# REM: QMS Protocol:
# REM:   Rate limited: Request_Rate_Limited_Thank_You_But_No with ::ip:: ::limit::
# REM:   Circuit open: Service_Unavailable_Thank_You_But_No with ::service::
# REM: =======================================================================================

import time
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Callable, Any
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import get_settings
from core.audit import audit, AuditEventType
from core.qms import format_qms, QMSStatus

settings = get_settings()
logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: RATE LIMITER
# REM: =======================================================================================

class RateLimiter:
    """
    REM: Token bucket rate limiter.
    REM: Each IP/key gets a bucket that refills over time.
    """
    
    # REM: v5.2.1CC: Maximum tracked clients to prevent unbounded memory growth
    MAX_TRACKED_CLIENTS = 10000

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.tokens_per_second = requests_per_minute / 60.0

        # REM: Track buckets per client
        self._buckets: Dict[str, Dict] = defaultdict(lambda: {
            "tokens": burst_size,
            "last_update": time.time()
        })
        self._last_cleanup = time.time()
    
    def _get_client_key(self, request: Request) -> str:
        """REM: Get unique identifier for rate limiting."""
        # REM: Check for API key first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{api_key[:16]}"
        
        # REM: Fall back to IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        
        return f"ip:{request.client.host if request.client else 'unknown'}"
    
    def _refill_bucket(self, bucket: Dict) -> None:
        """REM: Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - bucket["last_update"]
        bucket["tokens"] = min(
            self.burst_size,
            bucket["tokens"] + elapsed * self.tokens_per_second
        )
        bucket["last_update"] = now
    
    def _cleanup_stale_buckets(self):
        """REM: Remove stale rate limit buckets to prevent unbounded memory growth."""
        now = time.time()
        # REM: Only cleanup every 60 seconds
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now

        # REM: Remove buckets inactive for more than 10 minutes
        stale_cutoff = now - 600
        stale_keys = [
            k for k, v in self._buckets.items()
            if v["last_update"] < stale_cutoff
        ]
        for k in stale_keys:
            del self._buckets[k]

        if stale_keys:
            logger.debug(f"REM: Cleaned up {len(stale_keys)} stale rate limit buckets")

    def is_allowed(self, request: Request) -> tuple[bool, Dict[str, Any]]:
        """
        REM: Check if request should be allowed.
        Returns (allowed, info_dict)
        """
        # REM: Periodic cleanup of stale entries
        self._cleanup_stale_buckets()

        client_key = self._get_client_key(request)
        bucket = self._buckets[client_key]
        
        self._refill_bucket(bucket)
        
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True, {
                "client": client_key,
                "remaining": int(bucket["tokens"]),
                "limit": self.requests_per_minute,
            }
        else:
            return False, {
                "client": client_key,
                "remaining": 0,
                "limit": self.requests_per_minute,
                "retry_after": int((1 - bucket["tokens"]) / self.tokens_per_second) + 1
            }


# REM: Global rate limiter instance
rate_limiter = RateLimiter(
    requests_per_minute=getattr(settings, "rate_limit_per_minute", 120),
    burst_size=getattr(settings, "rate_limit_burst", 20),
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    REM: FastAPI middleware for rate limiting.
    """
    
    def __init__(self, app, limiter: RateLimiter = None):
        super().__init__(app)
        self.limiter = limiter or rate_limiter
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # REM: Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        allowed, info = self.limiter.is_allowed(request)
        
        if not allowed:
            audit.log(
                AuditEventType.SECURITY_ALERT,
                format_qms("Rate_Limit_Exceeded", QMSStatus.THANK_YOU_BUT_NO,
                          client=info["client"], limit=info["limit"]),
                actor=info["client"],
                details=info
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "qms_status": "Thank_You_But_No",
                    "retry_after": info["retry_after"],
                    "limit": f"{info['limit']} requests per minute"
                },
                headers={
                    "Retry-After": str(info["retry_after"]),
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                }
            )
        
        response = await call_next(request)
        
        # REM: Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        
        return response


# REM: =======================================================================================
# REM: REQUEST SIZE LIMITER
# REM: =======================================================================================

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    REM: Limit request body size to prevent memory exhaustion.
    """
    
    def __init__(self, app, max_size_mb: float = 10.0):
        super().__init__(app)
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        
        if content_length and int(content_length) > self.max_size_bytes:
            audit.log(
                AuditEventType.SECURITY_ALERT,
                format_qms("Request_Too_Large", QMSStatus.THANK_YOU_BUT_NO,
                          size=content_length, max=self.max_size_bytes),
                actor=request.client.host if request.client else "unknown",
                details={"content_length": content_length}
            )
            
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request too large",
                    "qms_status": "Thank_You_But_No",
                    "max_size_mb": self.max_size_bytes / (1024 * 1024),
                    "your_size_mb": int(content_length) / (1024 * 1024)
                }
            )
        
        return await call_next(request)


# REM: =======================================================================================
# REM: CIRCUIT BREAKER
# REM: =======================================================================================

class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CircuitBreaker:
    """
    REM: Circuit breaker for external service calls.
    REM: Prevents cascade failures by failing fast when a service is down.
    """
    
    name: str
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: int = 30          # Seconds before trying again
    half_open_requests: int = 3         # Requests to test in half-open
    
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    half_open_successes: int = 0
    
    def _should_attempt(self) -> bool:
        """REM: Check if we should attempt the operation."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # REM: Check if recovery timeout has passed
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_successes = 0
                logger.info(f"Circuit {self.name} transitioning to HALF_OPEN")
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """REM: Record a successful operation."""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.half_open_requests:
                self.state = CircuitState.CLOSED
                logger.info(f"Circuit {self.name} CLOSED (recovered)")
                audit.log(
                    AuditEventType.SYSTEM_STARTUP,
                    format_qms("Circuit_Recovered", QMSStatus.THANK_YOU, circuit=self.name),
                    actor="circuit_breaker"
                )
    
    def record_failure(self):
        """REM: Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # REM: Failure during recovery, go back to open
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name} back to OPEN (recovery failed)")
        
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name} OPEN (threshold reached)")
                audit.log(
                    AuditEventType.SYSTEM_ERROR,
                    format_qms("Circuit_Open", QMSStatus.THANK_YOU_BUT_NO, 
                              circuit=self.name, failures=self.failure_count),
                    actor="circuit_breaker"
                )
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        REM: Execute function with circuit breaker protection.
        """
        if not self._should_attempt():
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        REM: Execute async function with circuit breaker protection.
        """
        if not self._should_attempt():
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """REM: Get circuit status for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure": datetime.fromtimestamp(self.last_failure_time, tz=timezone.utc).isoformat() if self.last_failure_time else None,
        }


class CircuitOpenError(Exception):
    """REM: Raised when circuit is open and request is rejected."""
    pass


# REM: Global circuit breakers for common services
_circuits: Dict[str, CircuitBreaker] = {}


def get_circuit(name: str, **kwargs) -> CircuitBreaker:
    """REM: Get or create a circuit breaker for a service."""
    if name not in _circuits:
        _circuits[name] = CircuitBreaker(name=name, **kwargs)
    return _circuits[name]


def circuit_protected(circuit_name: str):
    """
    REM: Decorator for circuit breaker protection.
    
    Usage:
        @circuit_protected("external_api")
        def call_external_api():
            ...
    """
    def decorator(func: Callable):
        circuit = get_circuit(circuit_name)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return circuit.call(func, *args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await circuit.call_async(func, *args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# REM: =======================================================================================
# REM: REQUEST ID MIDDLEWARE
# REM: =======================================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    REM: Add unique request ID to each request for tracing.
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # REM: Store in request state for access in handlers
        request.state.request_id = request_id
        
        response = await call_next(request)
        
        response.headers["X-Request-ID"] = request_id
        
        return response


# REM: =======================================================================================
# REM: SLOW REQUEST LOGGING
# REM: =======================================================================================

class SlowRequestMiddleware(BaseHTTPMiddleware):
    """
    REM: Log requests that take longer than threshold.
    """
    
    def __init__(self, app, threshold_seconds: float = 5.0):
        super().__init__(app)
        self.threshold = threshold_seconds
    
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        
        if duration > self.threshold:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {duration:.2f}s (threshold: {self.threshold}s)"
            )
            audit.log(
                AuditEventType.SYSTEM_ERROR,
                format_qms("Slow_Request", QMSStatus.THANK_YOU,
                          path=request.url.path, duration=f"{duration:.2f}s"),
                actor="performance_monitor",
                details={"duration_seconds": duration, "threshold": self.threshold}
            )
        
        # REM: Add timing header
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        return response


# REM: =======================================================================================
# REM: SECURITY HEADERS MIDDLEWARE
# REM: =======================================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    REM: Add security headers to all responses.
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # REM: Security headers
        # REM: HSTS (Strict-Transport-Security) enforced at Traefik layer:
        # REM:   stsSeconds=31536000, stsIncludeSubdomains=true, stsPreload=true
        # REM: Application layer provides defense-in-depth fallback headers below.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # REM: Remove server identification
        if "server" in response.headers:
            del response.headers["server"]
        
        return response


# REM: =======================================================================================
# REM: APPLY ALL MIDDLEWARE
# REM: =======================================================================================

def apply_production_middleware(app):
    """
    REM: Apply all production hardening middleware to a FastAPI app.
    
    Usage:
        from core.middleware import apply_production_middleware
        app = FastAPI()
        apply_production_middleware(app)
    """
    # REM: Order matters - outermost middleware runs first
    
    # 1. Request ID (first, so all other middleware can use it)
    app.add_middleware(RequestIDMiddleware)
    
    # 2. Security headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # 3. Rate limiting
    app.add_middleware(RateLimitMiddleware)
    
    # 4. Request size limits
    app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=10.0)
    
    # 5. Slow request logging
    app.add_middleware(SlowRequestMiddleware, threshold_seconds=5.0)
    
    logger.info("Production middleware applied")


# REM: =======================================================================================
# REM: EXPORTS
# REM: =======================================================================================

__all__ = [
    "RateLimiter",
    "RateLimitMiddleware",
    "RequestSizeLimitMiddleware",
    "CircuitBreaker",
    "CircuitOpenError",
    "CircuitState",
    "get_circuit",
    "circuit_protected",
    "RequestIDMiddleware",
    "SlowRequestMiddleware",
    "SecurityHeadersMiddleware",
    "apply_production_middleware",
]
