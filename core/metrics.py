# TelsonBase/core/metrics.py
# REM: =======================================================================================
# REM: PROMETHEUS METRICS INSTRUMENTATION FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Observable systems are controllable systems. This module exposes
# REM: Prometheus-compatible metrics for every critical operation in TelsonBase:
# REM:   - HTTP request rates and latencies
# REM:   - Authentication success/failure counts
# REM:   - QMS message counts by status
# REM:   - Agent action tracking
# REM:   - Anomaly detection counts
# REM:   - Rate limiting events
# REM:   - Sovereign Score components
# REM:
# REM: Metrics are scraped by Prometheus every 10-15 seconds and visualized in Grafana.
# REM: This is NOT optional for production — you cannot manage what you cannot measure.
# REM: =======================================================================================

import logging
import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import Response as FastAPIResponse
from prometheus_client import (CONTENT_TYPE_LATEST, REGISTRY,
                               CollectorRegistry, Counter, Gauge, Histogram,
                               Info, generate_latest)
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: METRIC DEFINITIONS
# REM: =======================================================================================
# REM: Naming convention: telsonbase_{subsystem}_{metric_name}_{unit}
# REM: This follows Prometheus best practices for metric naming.

# --- HTTP Metrics ---
HTTP_REQUESTS_TOTAL = Counter(
    'telsonbase_http_requests_total',
    'Total HTTP requests received',
    ['method', 'endpoint', 'status_code']
)

HTTP_REQUEST_DURATION = Histogram(
    'telsonbase_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    'telsonbase_http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    ['method']
)

# --- Authentication Metrics ---
AUTH_TOTAL = Counter(
    'telsonbase_auth_total',
    'Authentication attempts',
    ['method', 'result']  # method: api_key/jwt, result: success/failure
)

# --- QMS Protocol Metrics ---
QMS_MESSAGES_TOTAL = Counter(
    'telsonbase_qms_messages_total',
    'QMS messages processed',
    ['status']  # Please, Thank_You, Thank_You_But_No, Excuse_Me, Pretty_Please
)

# --- Agent Activity Metrics ---
AGENT_ACTIONS_TOTAL = Counter(
    'telsonbase_agent_actions_total',
    'Agent actions executed',
    ['agent', 'action']
)

# --- Anomaly Metrics ---
ANOMALIES_TOTAL = Counter(
    'telsonbase_anomalies_total',
    'Anomalies detected',
    ['severity']  # low, medium, high, critical
)

# --- Rate Limiting Metrics ---
RATE_LIMITED_TOTAL = Counter(
    'telsonbase_rate_limited_total',
    'Requests rejected by rate limiter',
    ['endpoint']
)

# --- Approval Metrics ---
APPROVALS_PENDING = Gauge(
    'telsonbase_approvals_pending',
    'Number of actions awaiting human approval'
)

APPROVALS_TOTAL = Counter(
    'telsonbase_approvals_total',
    'Approval decisions made',
    ['decision']  # approved, denied
)

# --- Federation Metrics ---
FEDERATION_MESSAGES_TOTAL = Counter(
    'telsonbase_federation_messages_total',
    'Federated messages sent/received',
    ['direction']  # inbound, outbound
)

FEDERATION_ACTIVE_RELATIONSHIPS = Gauge(
    'telsonbase_federation_active_relationships',
    'Number of active federation trust relationships'
)

# --- Sovereign Score ---
SOVEREIGN_SCORE = Gauge(
    'telsonbase_sovereign_score',
    'Overall data sovereignty score (0-100)'
)

SOVEREIGN_FACTOR = Gauge(
    'telsonbase_sovereign_factor',
    'Individual sovereignty factor score',
    ['factor']  # llm_locality, data_residency, network_exposure, backup_sovereignty, auth_posture
)

# --- System Info ---
SYSTEM_INFO = Info(
    'telsonbase',
    'TelsonBase system information'
)


# REM: =======================================================================================
# REM: METRICS MIDDLEWARE
# REM: =======================================================================================

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    REM: Automatically tracks HTTP request count, duration, and in-progress
    REM: for every request that passes through the API.
    REM:
    REM: Excludes /metrics and /health from being tracked to avoid noise.
    """

    EXCLUDED_PATHS = {'/metrics', '/health', '/favicon.ico'}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # REM: Skip metrics for the metrics endpoint itself (avoid recursion/noise)
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        method = request.method
        # REM: Normalize path to avoid cardinality explosion
        # REM: e.g., /v1/agents/signing/keys/abc123 → /v1/agents/signing/keys/{id}
        endpoint = self._normalize_path(request.url.path)

        HTTP_REQUESTS_IN_PROGRESS.labels(method=method).inc()
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.time() - start_time
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code)
            ).inc()
            HTTP_REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method).dec()

        return response

    @staticmethod
    def _normalize_path(path: str) -> str:
        """
        REM: Collapse variable path segments to prevent label cardinality explosion.
        REM: /v1/agents/signing/keys/abc123 → /v1/agents/signing/keys/{id}
        REM: /v1/federation/relationships/xyz → /v1/federation/relationships/{id}
        """
        parts = path.strip('/').split('/')
        normalized = []
        for i, part in enumerate(parts):
            # REM: If the part looks like an ID (hex, uuid, or long alphanumeric), normalize it
            if len(part) > 8 and any(c.isdigit() for c in part):
                normalized.append('{id}')
            else:
                normalized.append(part)
        return '/' + '/'.join(normalized)


# REM: =======================================================================================
# REM: HELPER FUNCTIONS FOR RECORDING METRICS
# REM: =======================================================================================
# REM: These are called from throughout the codebase to record business events.

def record_auth(method: str, success: bool):
    """REM: Record an authentication attempt."""
    AUTH_TOTAL.labels(
        method=method,
        result="success" if success else "failure"
    ).inc()


def record_qms_message(status: str):
    """REM: Record a QMS message by its status suffix."""
    QMS_MESSAGES_TOTAL.labels(status=status).inc()


def record_agent_action(agent: str, action: str):
    """REM: Record an agent performing an action."""
    AGENT_ACTIONS_TOTAL.labels(agent=agent, action=action).inc()


def record_anomaly(severity: str):
    """REM: Record an anomaly detection event."""
    ANOMALIES_TOTAL.labels(severity=severity).inc()


def record_rate_limit(endpoint: str):
    """REM: Record a rate limiting event."""
    RATE_LIMITED_TOTAL.labels(endpoint=endpoint).inc()


def record_approval(decision: str):
    """REM: Record an approval decision (approved/denied)."""
    APPROVALS_TOTAL.labels(decision=decision).inc()


def set_pending_approvals(count: int):
    """REM: Set the current number of pending approvals."""
    APPROVALS_PENDING.set(count)


def record_federation_message(direction: str):
    """REM: Record a federation message (inbound/outbound)."""
    FEDERATION_MESSAGES_TOTAL.labels(direction=direction).inc()


def set_federation_relationships(count: int):
    """REM: Set the current number of active federation relationships."""
    FEDERATION_ACTIVE_RELATIONSHIPS.set(count)


def set_sovereign_score(score: float, factors: dict = None):
    """REM: Update the sovereign score and individual factors."""
    SOVEREIGN_SCORE.set(score)
    if factors:
        for factor_name, factor_score in factors.items():
            SOVEREIGN_FACTOR.labels(factor=factor_name).set(factor_score)


def set_system_info(version: str, instance_id: str = ""):
    """REM: Set static system information labels."""
    SYSTEM_INFO.info({
        'version': version,
        'instance_id': instance_id,
        'platform': 'telsonbase',
        'architect': 'quietfire'
    })


# REM: =======================================================================================
# REM: METRICS ENDPOINT
# REM: =======================================================================================

def metrics_response() -> FastAPIResponse:
    """
    REM: Generate the Prometheus metrics response.
    REM: This is called by the /metrics endpoint in main.py.
    """
    return FastAPIResponse(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )
