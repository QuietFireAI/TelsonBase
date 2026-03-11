# TelsonBase/main.py
# REM: =======================================================================================
# REM: MAIN API SERVER FOR THE TelsonBase v9.0.0B
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Complete API for the zero-trust agent platform. Includes:
# REM:   - Authentication (API key + JWT)
# REM:   - Agent task dispatch
# REM:   - Approval management UI endpoints
# REM:   - Anomaly monitoring dashboard
# REM:   - Federation trust management
# REM:   - System health and status
# REM:
# REM: QMS (Qualified Message Standard) Protocol (v3.0.2):
# REM: =======================================================================================
# REM: All internal messages SHOULD carry QMS formatting. This provides a second layer of
# REM: verification beyond cryptographic signatures:
# REM:   1. Signature = WHO sent the message (identity)
# REM:   2. QMS format = HOW it got here (provenance)
# REM:
# REM: Messages without QMS formatting are logged as potential security anomalies.
# REM: This does not block traffic yet — it flags for review.
# REM:
# REM: QMS Suffixes:
# REM:   ..._Please          = Request / Action Initiation
# REM:   ..._Thank_You       = Successful Completion
# REM:   ..._Thank_You_But_No = Unsuccessful / Graceful Refusal  
# REM:   ..._Excuse_Me       = Need Clarification
# REM:   ..._Pretty_Please   = High Priority Request
# REM:
# REM: QMS Field Markers:
# REM:   ::value::    = Critical field / key data
# REM:   $$value$$    = Priority or financial value
# REM:   ##value##    = Policy or rule ID
# REM:   @@value@@    = Agent target or entity reference
# REM:   ??value??    = Point of uncertainty / question
# REM: =======================================================================================

import asyncio
import html as html_module
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from version import __version__ as APP_VERSION

from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, Field
import redis

from starlette.requests import Request
from starlette.responses import JSONResponse

from core.config import get_settings, validate_production_secrets
from core.auth import authenticate_request, create_access_token, AuthResult, require_permission
from core.audit import audit, AuditEventType
from core.persistence import (
    signing_store, capability_store, anomaly_store, 
    approval_store, federation_store, toolroom_store
)
from core.middleware import apply_production_middleware
from core.rate_limiting import agent_rate_limit
from core.metrics import MetricsMiddleware, metrics_response, set_system_info, record_qms_message
from core.ollama_service import get_ollama_service, OllamaServiceError, OllamaConnectionError, OllamaModelError

# REM: Import API routers
# REM: n8n replaced by Goose/MCP native integration (see api/mcp_gateway.py and /mcp endpoint).
# from api.n8n_integration import router as n8n_router

settings = get_settings()

# REM: Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: PYDANTIC MODELS
# REM: =======================================================================================

# --- Auth Models ---
class TokenRequest(BaseModel):
    api_key: str
    expiration_hours: Optional[int] = 24

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int

# --- Task Models ---
class TaskDispatchRequest(BaseModel):
    task_name: str
    args: list = []
    kwargs: dict = {}
    priority: str = "normal"

class TaskDispatchResponse(BaseModel):
    task_id: str
    task_name: str
    status: str
    message: str
    qms_status: str

# --- Approval Models ---
class ApprovalDecision(BaseModel):
    decided_by: str = Field(..., description="Identifier of person making decision")
    notes: Optional[str] = None

class MoreInfoRequest(BaseModel):
    decided_by: str
    questions: List[str]

# --- Anomaly Models ---
class AnomalyResolution(BaseModel):
    resolution_notes: str

# --- Federation Models ---
class TrustInvitationRequest(BaseModel):
    trust_level: str = "standard"
    allowed_agents: List[str] = ["*"]
    allowed_actions: List[str] = ["message", "query"]
    expires_in_hours: int = 72

class TrustAcceptRequest(BaseModel):
    decided_by: str

class TrustRevokeRequest(BaseModel):
    reason: str
    revoked_by: str

class FederatedMessageRequest(BaseModel):
    source_agent_id: str
    action: str
    payload: Dict[str, Any]
    target_agent_id: Optional[str] = None

# --- System Models ---
class SystemStatus(BaseModel):
    status: str
    version: str
    timestamp: str
    services: Dict[str, str]
    security_status: Dict[str, Any]

# --- LLM Models ---
class LLMGenerateRequest(BaseModel):
    prompt: str = Field(..., description="The prompt to send to the model", min_length=1, max_length=100_000)
    model: Optional[str] = Field(None, description="Model name. Uses system default if not specified.")
    system: Optional[str] = Field(None, description="System prompt to set model behavior", max_length=10_000)
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Creativity control. 0=deterministic, 2=wild")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")

class LLMChatRequest(BaseModel):
    messages: List[Dict[str, str]] = Field(..., description="Chat messages: [{role: user/assistant, content: ...}]", min_length=1, max_length=100)
    model: Optional[str] = Field(None, description="Model name. Uses system default if not specified.")
    system: Optional[str] = Field(None, description="System prompt", max_length=10_000)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = None

class LLMPullRequest(BaseModel):
    model: str = Field(..., description="Model to download, e.g. 'gemma2:9b'")


# REM: =======================================================================================
# REM: APPLICATION LIFECYCLE
# REM: =======================================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """REM: Application lifecycle handler."""
    logger.info(f"REM: TelsonBase API Server v{APP_VERSION} starting_Please")
    
    # REM: =====================================================================
    # REM: SECRETS VALIDATION — Must happen FIRST, before any other init
    # REM: =====================================================================
    secret_errors = validate_production_secrets(settings)
    if settings.telsonbase_env == "production" and secret_errors:
        for err in secret_errors:
            logger.error(f"REM: FATAL Secret Error — {err}_Thank_You_But_No")
        raise RuntimeError(
            f"FATAL: {len(secret_errors)} secret(s) failed production validation. "
            f"Run scripts/generate_secrets.sh and set TELSONBASE_ENV=production. "
            f"Errors: {'; '.join(secret_errors)}"
        )
    elif secret_errors:
        for err in secret_errors:
            logger.warning(f"REM: Secret Warning — {err} (OK in development)_Excuse_Me")
    else:
        logger.info("REM: Secrets_Validation_Thank_You — All secrets validated")
    
    set_system_info(version=settings.traefik_domain or "local", instance_id="telsonbase-primary")
    
    # REM: Initialize MQTT bus for agent-to-agent communication
    from core.mqtt_bus import init_mqtt_bus, shutdown_mqtt_bus
    mqtt_connected = init_mqtt_bus()
    if mqtt_connected:
        logger.info("REM: MQTT agent communication bus online_Thank_You")
    else:
        logger.warning("REM: MQTT bus unavailable — agent-to-agent messaging disabled_Excuse_Me")
    
    # REM: v7.3.0CC — Initialize W3C DID identity engine if enabled
    if settings.identiclaw_enabled:
        from core.identiclaw import identiclaw_manager
        identiclaw_manager.startup_check()
        logger.info("REM: W3C DID identity engine enabled_Thank_You")
    else:
        logger.info("REM: W3C DID identity disabled (set IDENTICLAW_ENABLED=true to enable)")

    # REM: v7.4.0CC — Initialize OpenClaw governance engine if enabled
    if settings.openclaw_enabled:
        from core.openclaw import openclaw_manager
        openclaw_manager.startup_check()
        logger.info("REM: OpenClaw governance engine enabled — Control Your Claw_Thank_You")
    else:
        logger.info("REM: OpenClaw governance disabled (set OPENCLAW_ENABLED=true to enable)")

    audit.log(
        AuditEventType.SYSTEM_STARTUP,
        f"TelsonBase API Server v{APP_VERSION} started",
        actor="system",
        qms_status="Thank_You"
    )
    # REM: Reset session manager before each lifespan entry so it can be re-entered
    # REM: cleanly. StreamableHTTPSessionManager.run() can only be called once per
    # REM: instance. Tests spin up multiple TestClient(app) contexts in the same process,
    # REM: hitting this lifespan repeatedly. Resetting _session_manager and recreating the
    # REM: ASGI inner app gives each lifespan a fresh instance.
    global _mcp_asgi_inner
    _mcp_server._session_manager = None
    _mcp_asgi_inner = _mcp_server.streamable_http_app()
    async with _mcp_server.session_manager.run():
        yield
    logger.info("REM: TelsonBase API Server shutting down")
    shutdown_mqtt_bus()
    audit.log(
        AuditEventType.SYSTEM_SHUTDOWN,
        "TelsonBase API Server stopped",
        actor="system"
    )


# REM: v7.3.0CC: Standard error responses for OpenAPI spec — documents all common error codes
# REM: This eliminates ~234 "undocumented status code" findings from schemathesis
_standard_responses = {
    400: {"description": "Bad request. The HTTP request was malformed or contained invalid characters."},
    401: {"description": "Authentication required. Provide X-API-Key header or Bearer token."},
    403: {"description": "Forbidden. Insufficient permissions for this operation."},
    404: {"description": "Resource not found."},
    422: {"description": "Validation error. Check request body, query parameters, or path parameters."},
    429: {"description": "Rate limit exceeded. Retry after the indicated delay.", "content": {"application/json": {"example": {"error": "Rate limit exceeded", "qms_status": "Thank_You_But_No", "retry_after": 1, "limit": "300 requests per minute"}}}},
    500: {"description": "Internal server error. Check server logs."},
    503: {"description": "Service unavailable. A required dependency (Ollama, DID identity, Celery) is not enabled or reachable."},
}

app = FastAPI(
    title="TelsonBase by Quietfire AI",
    description=f"""
## Zero-Trust AI Agent Platform (v{APP_VERSION})

A decentralized, self-hosted operating system for sovereign AI agents with comprehensive security:

- **Message Signing**: Cryptographic verification of all inter-agent communication
- **Capability Enforcement**: Declarative permissions that agents cannot exceed
- **Behavioral Monitoring**: Anomaly detection with baseline tracking
- **Human Approval Gates**: Sensitive actions require human authorization
- **Federated Trust**: Secure cross-instance agent collaboration
- **QMS Protocol**: Qualified Message Standard for internal message verification
- **MCP Gateway**: Native Goose / Claude Desktop integration at /mcp (13 tools, HITL-gated)
- **Alien Quarantine**: Secure isolation for external agent frameworks

All endpoints except `/health` require authentication via `X-API-Key` header or Bearer token.
Authorization header (Bearer token) is optional — X-API-Key is the primary authentication method.
    """,
    version=APP_VERSION,
    lifespan=lifespan,
    responses=_standard_responses,
)

# REM: v7.3.0CC: Customize OpenAPI schema to make Authorization header optional
# REM: X-API-Key is the primary auth method; Bearer token is a secondary option.
# REM: This fixes ~77 schemathesis "schema-violating request" failures (Bucket 3).
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # REM: Remove Authorization (Bearer) from required security on all operations.
    # REM: Keep X-API-Key as required, Bearer as optional.
    if "paths" in openapi_schema:
        for path_data in openapi_schema["paths"].values():
            for operation in path_data.values():
                if isinstance(operation, dict) and "security" in operation:
                    # REM: Keep only APIKeyHeader, remove HTTPBearer requirement
                    new_security = []
                    for sec in operation["security"]:
                        if "HTTPBearer" not in sec:
                            new_security.append(sec)
                        else:
                            # REM: Add Bearer as optional (empty requirements = optional)
                            new_security.append({"HTTPBearer": []})
                    operation["security"] = new_security
    app.openapi_schema = openapi_schema
    return openapi_schema

app.openapi = custom_openapi

# REM: Apply production hardening middleware (rate limiting, circuit breaker, etc.)
apply_production_middleware(app)

# REM: Prometheus metrics middleware — tracks every request automatically
app.add_middleware(MetricsMiddleware)

# REM: v6.2.0CC: CORS hardened — credentials only allowed with explicit origins, never with wildcard
_cors_allow_credentials = "*" not in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
)

# REM: =======================================================================================
# REM: SECURITY RESPONSE HEADERS MIDDLEWARE (v6.3.0CC)
# REM: =======================================================================================
# REM: Adds security headers to every response. Defense-in-depth alongside Traefik HSTS.
# REM: Uses pure ASGI middleware (not BaseHTTPMiddleware) for test compatibility.
# REM: =======================================================================================

class SecurityHeadersMiddleware:
    """REM: Pure ASGI middleware that adds security headers to all responses."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                extra_headers = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"cache-control", b"no-store"),
                ]
                existing = list(message.get("headers", []))
                existing.extend(extra_headers)
                message["headers"] = existing
            await send(message)

        await self.app(scope, receive, send_with_headers)

app.add_middleware(SecurityHeadersMiddleware)


# REM: =======================================================================================
# REM: GLOBAL EXCEPTION HANDLER — ERROR SANITIZATION (v6.3.0CC)
# REM: =======================================================================================
# REM: Catches ALL unhandled exceptions and returns a sanitized JSON response.
# REM: Internal error details are logged server-side but NEVER sent to the client.
# REM: This prevents information leakage (stack traces, file paths, library versions).
# REM: =======================================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """REM: Catch-all for unhandled exceptions — sanitize before returning to client."""
    # REM: Log the real error server-side for debugging
    logger.error(
        f"REM: Unhandled exception on {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {exc}_Thank_You_But_No",
        exc_info=True
    )
    audit.log(
        AuditEventType.SECURITY_ALERT,
        f"Unhandled exception on {request.url.path}",
        actor="system",
        details={"method": request.method, "error_type": type(exc).__name__},
        qms_status="Thank_You_But_No"
    )
    # REM: Return sanitized response — no internal details
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again or contact support.",
            "qms_status": "Thank_You_But_No"
        }
    )


# REM: Include API routers
# REM: n8n router removed — replaced by native MCP/Goose integration at /mcp
# app.include_router(n8n_router)

from api.auth_routes import router as auth_router
from api.security_routes import router as security_router
from api.compliance_routes import router as compliance_router
from api.tenancy_routes import router as tenancy_router
from core.tenant_rate_limiting import tenant_rate_limit_router
app.include_router(auth_router)
app.include_router(security_router)
app.include_router(compliance_router)
app.include_router(tenancy_router)
app.include_router(tenant_rate_limit_router)

# REM: v7.3.0CC — W3C DID identity management routes
from api.identiclaw_routes import router as identiclaw_router
app.include_router(identiclaw_router)

# REM: v7.4.0CC — OpenClaw governance routes ("Control Your Claw")
from api.openclaw_routes import router as openclaw_router
app.include_router(openclaw_router)

# REM: =======================================================================================
# REM: DASHBOARD - SERVED FROM /dashboard
# REM: =======================================================================================

FRONTEND_DIR = Path(__file__).parent / "frontend"

# REM: Serve vendored JS libraries (React, ReactDOM, Babel) from local files.
# REM: Eliminates hard-refresh failures caused by slow or unavailable CDN (unpkg.com).
# REM: Files live at frontend/vendor/ — update them by re-running scripts/update_vendor.sh.
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# REM: =======================================================================================
# REM: MCP GATEWAY — Goose / Claude Desktop / any MCP-compatible agent connects here
# REM: =======================================================================================
# REM: Exposes all TelsonBase tools (agents, tenants, audit, approvals) as MCP tools at /mcp.
# REM: Transport: Streamable HTTP (SSE).  Auth: Bearer <TelsonBase API key>.
# REM: Goose config: see goose.yaml at the project root.
# REM:
# REM: MCP Session Gate: When OPENCLAW_ENABLED=true, tool calls are gated on the trust level
# REM: of the registered OpenClaw instance matching the Bearer token.
# REM:   ALWAYS: get_health, system_status, register_as_agent
# REM:   QUARANTINE+: list_agents, get_agent, audit chain tools
# REM:   PROBATION+: list_tenants, create_tenant, list_matters, approvals
# REM:
# REM: The ASGI wrapper below extracts the Bearer token and sets the ContextVar used
# REM: by _check_mcp_session() in mcp_gateway.py. The ContextVar persists across the
# REM: async call chain within the same asyncio task.
import hashlib as _hashlib
from api.mcp_gateway import mcp as _mcp_server, _mcp_api_key_hash as _mcp_key_ctx

# REM: FastMCP streamable_http_app() defaults to path=/mcp internally.
# REM: FastAPI app.mount("/mcp", ...) strips the /mcp prefix before passing to the
# REM: inner ASGI app, so the inner app must listen at / not /mcp.
# REM: Setting streamable_http_path="/" aligns the inner route with the stripped path.
_mcp_server.settings.streamable_http_path = "/"
_mcp_asgi_inner = _mcp_server.streamable_http_app()


async def _mcp_session_gate_wrapper(scope, receive, send):
    """
    REM: Thin ASGI wrapper — extracts Bearer token, sets ContextVar, delegates to FastMCP.
    REM: ContextVar is visible to all mcp_gateway tool handlers within the same async task.
    """
    if scope.get("type") == "http":
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth = headers.get(b"authorization", b"").decode("utf-8", errors="ignore")
        if auth.startswith("Bearer "):
            key = auth[7:].strip()
            key_hash = _hashlib.sha256(key.encode("utf-8")).hexdigest()
            token = _mcp_key_ctx.set(key_hash)
            try:
                await _mcp_asgi_inner(scope, receive, send)
            finally:
                _mcp_key_ctx.reset(token)
            return
    await _mcp_asgi_inner(scope, receive, send)


app.mount("/mcp", _mcp_session_gate_wrapper)
logger.info("REM: MCP gateway mounted at /mcp — session gate active, Goose integration ready_Thank_You")

@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard():
    """REM: Serve the TelsonBase Dashboard UI."""
    index_path = FRONTEND_DIR / "user-console.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(), status_code=200)
    else:
        return HTMLResponse(
            content="<h1>Dashboard not found</h1><p>Frontend files missing from /frontend directory</p>",
            status_code=404
        )


@app.get("/console", response_class=HTMLResponse, tags=["Dashboard"])
async def user_console():
    """REM: Serve the TelsonBase User Console UI (Layer B — simplified operator interface)."""
    console_path = FRONTEND_DIR / "user-console.html"
    if console_path.exists():
        return HTMLResponse(content=console_path.read_text(), status_code=200)
    else:
        return HTMLResponse(
            content="<h1>User Console not found</h1><p>user-console.html missing from /frontend directory</p>",
            status_code=404
        )


@app.get("/login", response_class=HTMLResponse, tags=["Dashboard"])
async def login_ui():
    """REM: Serve the TelsonBase login/MFA UI — entry point for human operators."""
    login_path = FRONTEND_DIR / "login.html"
    if login_path.exists():
        return HTMLResponse(content=login_path.read_text(), status_code=200)
    else:
        return HTMLResponse(
            content="<h1>Login UI not found</h1><p>login.html missing from /frontend directory</p>",
            status_code=404
        )


_DOC_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TelsonBase — {title}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'DM Mono','Fira Code','Cascadia Code',monospace;background:#080f1e;color:#cbd5e1;padding:32px 48px;max-width:900px;margin:0 auto;line-height:1.75;font-size:13px}}
  .hdr{{border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:14px;margin-bottom:28px;display:flex;align-items:center;justify-content:space-between}}
  .hdr-left{{display:flex;align-items:center;gap:10px}}
  .badge{{background:rgba(34,211,238,0.1);color:#22d3ee;border:1px solid rgba(34,211,238,0.2);padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.05em}}
  a{{color:#22d3ee;text-decoration:none}}
  a:hover{{text-decoration:underline}}
  pre{{white-space:pre-wrap;word-wrap:break-word;color:#e2e8f0;font-size:13px;line-height:1.75}}
</style>
</head>
<body>
<div class="hdr">
  <div class="hdr-left">
    <span style="color:#64748b;font-size:12px">TelsonBase by Quietfire AI</span>
    <span class="badge">DOCS</span>
  </div>
  <a href="/dashboard" style="font-size:11px;color:#475569">← Back to Dashboard</a>
</div>
<pre>{content}</pre>
</body>
</html>"""


def _serve_doc(path: Path, title: str) -> HTMLResponse:
    """REM: Serve a markdown file as a readable HTML page (no external dependencies)."""
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{title} not found at {path}")
    content = html_module.escape(path.read_text())
    return HTMLResponse(content=_DOC_TEMPLATE.format(title=title, content=content))


@app.get("/docs/qms", response_class=HTMLResponse, tags=["Documentation"])
async def view_qms_spec():
    """REM: Serve QMS_SPECIFICATION.md — the Qualified Message Standard protocol reference."""
    return _serve_doc(
        Path(__file__).parent / "docs" / "QMS Documents" / "QMS_SPECIFICATION.md",
        "QMS Specification"
    )


@app.get("/docs/manners", response_class=HTMLResponse, tags=["Documentation"])
async def view_manners():
    """REM: Serve MANNERS.md — TelsonBase agent operating principles and compliance framework."""
    return _serve_doc(
        Path(__file__).parent / "MANNERS.md",
        "MANNERS — Agent Operating Principles"
    )


# REM: =======================================================================================
# REM: PUBLIC ENDPOINTS
# REM: =======================================================================================

@app.get("/", tags=["Public"])
async def root():
    """REM: Welcome endpoint with API overview."""
    return {
        "message": "Welcome to TelsonBase by Quietfire AI",
        "version": APP_VERSION,
        "dashboard": "/dashboard",
        "console": "/console",
        "documentation": "/docs",
        "endpoints": {
            "health": "/health",
            "dashboard": "/dashboard",
            "console": "/console",
            "auth": "/v1/auth/token",
            "tasks": "/v1/tasks/",
            "approvals": "/v1/approvals/",
            "anomalies": "/v1/anomalies/",
            "federation": "/v1/federation/",
            "agents": "/v1/agents/"
        }
    }


@app.get("/health", tags=["Public"])
async def health_check():
    """REM: Health check for load balancers and monitoring."""
    # REM: v6.2.0CC: Health endpoint no longer leaks internal error details
    redis_status = "unknown"
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    # REM: Check MQTT bus status
    mqtt_status = "unknown"
    try:
        from core.mqtt_bus import get_mqtt_bus
        bus = get_mqtt_bus()
        mqtt_status = "connected" if bus.is_connected else "disconnected"
    except Exception:
        mqtt_status = "not_initialized"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "redis": redis_status,
        "mqtt": mqtt_status
    }


@app.get("/metrics", tags=["Public"], responses={200: {"content": {"text/plain": {"schema": {"type": "string"}}}, "description": "Prometheus metrics in text/plain format"}})
async def prometheus_metrics():
    """
    REM: Prometheus metrics endpoint. Scraped every 10-15 seconds by Prometheus.
    REM: No authentication required — Prometheus scrapes this from the monitoring network.
    REM: The endpoint is only reachable from the internal Docker network, not externally.
    """
    return metrics_response()


# REM: =======================================================================================
# REM: AUTHENTICATION ENDPOINTS
# REM: =======================================================================================

@app.post("/v1/auth/token", response_model=TokenResponse, tags=["Authentication"])
async def get_token(request: TokenRequest):
    """
    REM: Exchange API key for a JWT token.
    """
    if request.api_key != settings.mcp_api_key:
        audit.auth_failure(actor="token_request", reason="Invalid API key")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    token = create_access_token(
        subject="api_key_holder",
        permissions=["*"]
    )
    
    return TokenResponse(
        access_token=token,
        expires_in_hours=settings.jwt_expiration_hours
    )


# REM: =======================================================================================
# REM: SYSTEM STATUS ENDPOINTS
# REM: =======================================================================================

@app.get("/v1/system/status", response_model=SystemStatus, tags=["System"])
async def system_status(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("admin:config")),
):
    """REM: Comprehensive system status including security infrastructure."""
    
    services = {}
    
    # REM: Check Redis
    try:
        signing_store.ping()
        services["redis"] = "healthy"
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        services["redis"] = "unhealthy"
    
    # REM: Check Ollama engine
    try:
        ollama = get_ollama_service()
        health = ollama.health_check()
        services["ollama"] = health.get("status", "unknown")
        if health.get("status") == "healthy":
            services["ollama_latency_ms"] = str(health.get("latency_ms", "?"))
            services["ollama_default_model"] = ollama.default_model
    except Exception as e:
        logger.warning(f"Ollama health check failed: {e}")
        services["ollama"] = "unhealthy"
    
    # REM: Get security statistics
    pending_approvals = len(approval_store.get_pending_requests())
    unresolved_anomalies = len(anomaly_store.get_unresolved_anomalies())
    active_relationships = len(federation_store.list_relationships(status="established"))
    registered_agents = len(signing_store.list_agents())
    
    return SystemStatus(
        status="healthy",
        version=APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services=services,
        security_status={
            "registered_agents": registered_agents,
            "pending_approvals": pending_approvals,
            "unresolved_anomalies": unresolved_anomalies,
            "active_federation_relationships": active_relationships
        }
    )


@app.post("/v1/system/analyze", tags=["System"])
async def run_system_analysis(
    auto_remediate: bool = Query(default=False, description="Auto-fix issues where possible"),
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("admin:config")),
):
    """
    REM: Trigger comprehensive system-wide security analysis.

    Analyzes:
    - Agent health and trust levels
    - Re-verification status
    - Federation relationships
    - Anomaly patterns
    - Rate limiting status
    - Capability delegations

    Returns detailed findings and security posture score.
    """
    from core.system_analysis import system_analyzer

    try:
        report = system_analyzer.run_full_analysis(
            triggered_by=auth.actor or "api_user",
            auto_remediate=auto_remediate
        )

        return {
            **report.to_dict(),
            "qms_status": "Thank_You"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"REM: System analysis failed: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail={
            "qms_status": "Thank_You_But_No",
            "error": f"System analysis failed: {str(e)}"
        })


@app.get("/v1/system/analysis/last", tags=["System"])
async def get_last_analysis(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("admin:config")),
):
    """REM: Get the last system analysis report."""
    from core.system_analysis import system_analyzer

    report = system_analyzer.get_last_report()
    if not report:
        return {
            "message": "No analysis has been run yet",
            "qms_status": "Thank_You"
        }

    return {
        **report,
        "qms_status": "Thank_You"
    }


@app.post("/v1/system/reverification", tags=["System"])
async def run_system_reverification(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("admin:config")),
):
    """REM: Run re-verification for all agents that need it."""
    from core.trust_levels import trust_manager

    result = trust_manager.run_system_reverification()

    return {
        **result,
        "qms_status": "Thank_You"
    }


@app.get("/v1/system/reverification/status", tags=["System"])
async def get_reverification_status(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("admin:config")),
):
    """REM: Get re-verification status for all agents."""
    from core.trust_levels import trust_manager

    status = trust_manager.get_reverification_status()

    return {
        **status,
        "qms_status": "Thank_You"
    }


# REM: =======================================================================================
# REM: AUDIT CHAIN ENDPOINTS (v4.3.2CC)
# REM: =======================================================================================

@app.get("/v1/audit/chain/status", tags=["Audit"])
async def get_audit_chain_status(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:audit")),
):
    """REM: Get current audit chain state for monitoring."""
    return {
        **audit.get_chain_state(),
        "qms_status": "Thank_You"
    }


@app.get("/v1/audit/chain/verify", tags=["Audit"])
async def verify_audit_chain(
    limit: int = Query(default=100, le=1000, description="Number of recent entries to verify"),
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:audit")),
):
    """
    REM: Verify integrity of the audit chain.
    REM: Returns verification result with any breaks found.
    """
    entries = audit.get_recent_entries(limit)
    result = audit.verify_chain(entries)

    return {
        **result,
        "qms_status": "Thank_You" if result["valid"] else "Thank_You_But_No"
    }


@app.get("/v1/audit/chain/export", tags=["Audit"])
async def export_audit_chain(
    start_sequence: int = Query(default=0, description="Start sequence number"),
    end_sequence: Optional[int] = Query(default=None, description="End sequence number"),
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:audit")),
):
    """
    REM: Export audit chain for compliance.
    REM: Returns chain entries with verification status.
    """
    export = audit.export_chain_for_compliance(start_sequence, end_sequence)

    return {
        **export,
        "qms_status": "Thank_You"
    }


@app.get("/v1/audit/chain/entries", tags=["Audit"])
async def get_audit_entries(
    limit: int = Query(default=50, le=500, description="Number of entries to return"),
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:audit")),
):
    """REM: Get recent audit chain entries."""
    entries = audit.get_recent_entries(limit)

    return {
        "entries": entries,
        "count": len(entries),
        "chain_id": audit.get_chain_state()["chain_id"],
        "qms_status": "Thank_You"
    }


@app.get("/v1/audit/stream", tags=["Audit"])
async def stream_audit_entries(
    api_key: Optional[str] = Query(default=None, description="API key — required for SSE (EventSource cannot send headers)"),
    last_sequence: int = Query(default=0, description="Stream entries with sequence number greater than this value"),
):
    """
    REM: Stream new audit chain entries as Server-Sent Events.
    REM: Accepts api_key as a query parameter because browser EventSource cannot set custom headers.
    REM: Pushes new entries within ~2 seconds of being written to the chain.
    REM: Send a last_sequence to resume from where you left off without re-receiving old entries.
    """
    settings = get_settings()
    if not api_key or api_key != settings.mcp_api_key:
        raise HTTPException(status_code=401, detail="Authentication required. Pass your API key as ?api_key=...")

    async def event_generator():
        seen_sequence = last_sequence
        try:
            while True:
                entries = audit.get_recent_entries(limit=200)
                new_entries = [e for e in entries if e.get("sequence", 0) > seen_sequence]
                if new_entries:
                    for entry in sorted(new_entries, key=lambda x: x.get("sequence", 0)):
                        yield f"data: {json.dumps(entry)}\n\n"
                        seen_sequence = max(seen_sequence, entry.get("sequence", 0))
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# REM: =======================================================================================
# REM: AGENT MANAGEMENT ENDPOINTS
# REM: =======================================================================================

@app.get("/v1/agents", tags=["Agents"])
async def list_agents(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:agents")),
):
    """REM: List all registered agents with their capabilities."""
    agents = signing_store.list_agents()
    
    result = []
    for agent_id in agents:
        caps = capability_store.get_capabilities(agent_id)
        result.append({
            "agent_id": agent_id,
            "capabilities": caps or [],
            "signing_key_registered": True
        })
    
    return {
        "agents": result,
        "count": len(result),
        "qms_status": "Thank_You"
    }


@app.get("/v1/agents/{agent_id}", tags=["Agents"])
async def get_agent_details(
    agent_id: str,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:agents")),
):
    """REM: Get detailed information about a specific agent."""
    caps = capability_store.get_capabilities(agent_id)
    baseline = anomaly_store.get_baseline(agent_id)
    anomalies = anomaly_store.get_agent_anomalies(agent_id, limit=10)
    approvals = approval_store.get_agent_requests(agent_id, limit=10)
    
    return {
        "agent_id": agent_id,
        "capabilities": caps or [],
        "baseline": baseline,
        "recent_anomalies": anomalies,
        "recent_approvals": approvals,
        "qms_status": "Thank_You"
    }


# REM: =======================================================================================
# REM: Manners COMPLIANCE ENDPOINTS
# REM: =======================================================================================

@app.get("/v1/manners/status", tags=["Manners"])
async def manners_compliance_summary(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:agents")),
):
    """REM: Get Manners compliance summary across all agents."""
    from core.manners import manners_engine
    return manners_engine.get_compliance_summary()


@app.get("/v1/manners/agent/{agent_name}", tags=["Manners"])
async def manners_agent_report(
    agent_name: str,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:agents")),
):
    """REM: Get Manners compliance report for a specific agent."""
    from core.manners import manners_engine
    report = manners_engine.evaluate(agent_name)
    return report.to_dict()


@app.get("/v1/manners/violations/{agent_name}", tags=["Manners"])
async def manners_agent_violations(
    agent_name: str,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:agents")),
):
    """REM: Get Manners violations for a specific agent."""
    from core.manners import manners_engine
    violations = manners_engine.get_violations(agent_name)
    return {
        "agent_name": agent_name,
        "violations": [v.to_dict() for v in violations],
        "count": len(violations),
    }


# REM: =======================================================================================
# REM: TASK DISPATCH ENDPOINTS
# REM: =======================================================================================

@app.post("/v1/tasks/dispatch", response_model=TaskDispatchResponse, tags=["Tasks"])
async def dispatch_task(
    request: TaskDispatchRequest,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("action:approve")),
    _rl=Depends(agent_rate_limit),
):
    """
    REM: Dispatch a task to a Celery worker.
    
    REM: QMS Protocol - This endpoint initiates task requests.
    REM: Incoming: Task_Dispatch_Please with ::task_name:: and ::args::
    REM: Outgoing: Task_Dispatch_Thank_You or Task_Dispatch_Thank_You_But_No
    REM: SECURITY: All dispatched tasks should be tracked for QMS compliance.
    """
    try:
        from celery_app.worker import app as celery_app
        
        if request.task_name not in celery_app.tasks:
            raise HTTPException(
                status_code=404,
                detail=f"Task '{request.task_name}' not found"
            )
        
        result = celery_app.send_task(
            request.task_name,
            args=request.args,
            kwargs=request.kwargs
        )
        
        audit.task_dispatched(
            task_name=request.task_name,
            task_id=result.id,
            actor=auth.actor,
            args={"args": request.args, "kwargs": request.kwargs}
        )
        
        return TaskDispatchResponse(
            task_id=result.id,
            task_name=request.task_name,
            status="dispatched",
            message=f"Task '{request.task_name}' dispatched successfully",
            qms_status="Please"
        )
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery not available"
        )


@app.get("/v1/tasks/{task_id}", tags=["Tasks"])
async def get_task_status(
    task_id: str,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:dashboard")),
):
    """REM: Get status and result of a dispatched task."""
    try:
        from celery_app.worker import app as celery_app
        result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
        }
        
        if result.ready():
            if result.successful():
                response["result"] = result.result
                response["qms_status"] = "Thank_You"
            else:
                # REM: v6.2.0CC: Sanitize error — don't leak internal exception details
                response["error"] = "Task failed. Check server logs for details."
                response["qms_status"] = "Thank_You_But_No"
        else:
            response["qms_status"] = "Please"
        
        return response
        
    except ImportError:
        raise HTTPException(status_code=503, detail="Celery not available")


# REM: =======================================================================================
# REM: APPROVAL MANAGEMENT ENDPOINTS
# REM: =======================================================================================

@app.get("/v1/approvals/", tags=["Approvals"])
async def list_pending_approvals(
    limit: int = Query(50, ge=1, le=200),
    agent_id: Optional[str] = None,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:approvals")),
):
    """
    REM: List pending approval requests.
    REM: Returns requests ordered by priority (urgent first).
    """
    if agent_id:
        requests = approval_store.get_agent_requests(agent_id, limit=limit)
        requests = [r for r in requests if r.get("status") == "pending"]
    else:
        requests = approval_store.get_pending_requests(limit=limit)
    
    return {
        "pending_requests": requests,
        "count": len(requests),
        "qms_status": "Thank_You"
    }


@app.get("/v1/approvals/{request_id}", tags=["Approvals"])
async def get_approval_request(
    request_id: str,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:approvals")),
):
    """REM: Get details of a specific approval request."""
    request = approval_store.get_request(request_id)
    
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    return {
        "request": request,
        "qms_status": "Thank_You"
    }


@app.post("/v1/approvals/{request_id}/approve", tags=["Approvals"])
async def approve_request(
    request_id: str,
    decision: ApprovalDecision,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("action:approve")),
):
    """
    REM: Approve a pending request.
    REM: The waiting task will be unblocked and proceed with execution.
    """
    request = approval_store.get_request(request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if request.get("status") != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Request is not pending (status: {request.get('status')})"
        )

    approval_store.update_request(request_id, {
        "status": "approved",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "decided_by": decision.decided_by,
        "decision_notes": decision.notes
    })

    audit.log(
        AuditEventType.TASK_COMPLETED,
        f"Approval request ::{request_id}:: approved by ::{decision.decided_by}::",
        actor=decision.decided_by,
        resource=request_id,
        qms_status="Thank_You"
    )

    logger.info(f"REM: Approval ::{request_id}:: APPROVED by ::{decision.decided_by}::_Thank_You")

    # REM: Trigger n8n webhook callback if registered
    try:
        from api.n8n_integration import on_approval_decided
        await on_approval_decided(request_id, "approved", decision.decided_by)
    except Exception as e:
        logger.warning(f"Failed to send approval webhook: {e}")

    return {
        "request_id": request_id,
        "status": "approved",
        "decided_by": decision.decided_by,
        "qms_status": "Thank_You"
    }


@app.post("/v1/approvals/{request_id}/reject", tags=["Approvals"])
async def reject_request(
    request_id: str,
    decision: ApprovalDecision,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("action:approve")),
):
    """
    REM: Reject a pending request.
    REM: The waiting task will be unblocked and fail with rejection reason.
    """
    request = approval_store.get_request(request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if request.get("status") != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Request is not pending (status: {request.get('status')})"
        )

    approval_store.update_request(request_id, {
        "status": "rejected",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "decided_by": decision.decided_by,
        "decision_notes": decision.notes
    })

    audit.log(
        AuditEventType.TASK_FAILED,
        f"Approval request ::{request_id}:: rejected by ::{decision.decided_by}::",
        actor=decision.decided_by,
        resource=request_id,
        qms_status="Thank_You_But_No"
    )

    logger.info(f"REM: Approval ::{request_id}:: REJECTED by ::{decision.decided_by}::_Thank_You_But_No")

    # REM: Trigger n8n webhook callback if registered
    try:
        from api.n8n_integration import on_approval_decided
        await on_approval_decided(request_id, "rejected", decision.decided_by)
    except Exception as e:
        logger.warning(f"Failed to send rejection webhook: {e}")

    return {
        "request_id": request_id,
        "status": "rejected",
        "decided_by": decision.decided_by,
        "qms_status": "Thank_You_But_No"
    }


@app.post("/v1/approvals/{request_id}/request-info", tags=["Approvals"])
async def request_more_info(
    request_id: str,
    info_request: MoreInfoRequest,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("action:approve")),
):
    """REM: Request more information before making a decision."""
    request = approval_store.get_request(request_id)
    
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    approval_store.update_request(request_id, {
        "status": "more_info_requested",
        "decision_notes": f"Questions: {'; '.join(info_request.questions)}"
    })
    
    logger.info(f"REM: More info requested for ::{request_id}::_Excuse_Me")
    
    return {
        "request_id": request_id,
        "status": "more_info_requested",
        "questions": info_request.questions,
        "qms_status": "Excuse_Me"
    }


# REM: =======================================================================================
# REM: ANOMALY MONITORING ENDPOINTS
# REM: =======================================================================================

@app.get("/v1/anomalies/", tags=["Anomalies"])
async def list_anomalies(
    unresolved_only: bool = Query(True),
    agent_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:anomalies")),
):
    """
    REM: List detected anomalies.
    REM: By default shows only unresolved anomalies.
    """
    if agent_id:
        anomalies = anomaly_store.get_agent_anomalies(agent_id, limit=limit)
        if unresolved_only:
            anomalies = [a for a in anomalies if not a.get("resolved", False)]
    elif unresolved_only:
        anomalies = anomaly_store.get_unresolved_anomalies(limit=limit)
    else:
        # REM: Would need a get_all method for this
        anomalies = anomaly_store.get_unresolved_anomalies(limit=limit)
    
    if severity:
        anomalies = [a for a in anomalies if a.get("severity") == severity]
    
    # REM: Sort by severity (critical first) then timestamp
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    anomalies.sort(key=lambda a: (
        severity_order.get(a.get("severity", "low"), 4),
        a.get("detected_at", "")
    ))
    
    return {
        "anomalies": anomalies,
        "count": len(anomalies),
        "qms_status": "Thank_You"
    }


@app.get("/v1/anomalies/{anomaly_id}", tags=["Anomalies"])
async def get_anomaly(
    anomaly_id: str,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:anomalies")),
):
    """REM: Get details of a specific anomaly."""
    anomaly = anomaly_store.get_anomaly(anomaly_id)
    
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    
    return {
        "anomaly": anomaly,
        "qms_status": "Thank_You"
    }


@app.post("/v1/anomalies/{anomaly_id}/resolve", tags=["Anomalies"])
async def resolve_anomaly(
    anomaly_id: str,
    resolution: AnomalyResolution,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("action:resolve_anomaly")),
):
    """
    REM: Mark an anomaly as resolved.
    REM: Provide notes explaining the resolution (false positive, addressed, etc.)
    """
    success = anomaly_store.resolve_anomaly(anomaly_id, resolution.resolution_notes)
    
    if not success:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    
    audit.log(
        AuditEventType.TASK_COMPLETED,
        f"Anomaly ::{anomaly_id}:: resolved",
        actor=auth.actor,
        resource=anomaly_id,
        details={"notes": resolution.resolution_notes},
        qms_status="Thank_You"
    )
    
    logger.info(f"REM: Anomaly ::{anomaly_id}:: resolved_Thank_You")
    
    return {
        "anomaly_id": anomaly_id,
        "status": "resolved",
        "resolution_notes": resolution.resolution_notes,
        "qms_status": "Thank_You"
    }


@app.get("/v1/anomalies/dashboard/summary", tags=["Anomalies"])
async def anomaly_dashboard_summary(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:anomalies")),
):
    """
    REM: Get a summary for the anomaly monitoring dashboard.
    REM: Provides counts by severity and type.
    """
    unresolved = anomaly_store.get_unresolved_anomalies(limit=500)
    
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_type = {}
    by_agent = {}
    requires_review = 0
    
    for anomaly in unresolved:
        # Count by severity
        sev = anomaly.get("severity", "low")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        
        # Count by type
        atype = anomaly.get("anomaly_type", "unknown")
        by_type[atype] = by_type.get(atype, 0) + 1
        
        # Count by agent
        agent = anomaly.get("agent_id", "unknown")
        by_agent[agent] = by_agent.get(agent, 0) + 1
        
        # Count requiring review
        if anomaly.get("requires_human_review"):
            requires_review += 1
    
    return {
        "total_unresolved": len(unresolved),
        "requires_human_review": requires_review,
        "by_severity": by_severity,
        "by_type": by_type,
        "by_agent": by_agent,
        "qms_status": "Thank_You"
    }


# REM: =======================================================================================
# REM: FEDERATION MANAGEMENT ENDPOINTS
# REM: =======================================================================================

@app.get("/v1/federation/identity", tags=["Federation"])
async def get_federation_identity(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:federation")),
):
    """REM: Get this instance's federation identity."""
    identity = federation_store.get_identity()

    if not identity:
        # REM: Generate identity if not exists
        from federation.trust import get_federation_manager

        fm = get_federation_manager()
        identity = fm.identity.to_dict()
        federation_store.store_identity(identity)
    
    return {
        "identity": identity,
        "qms_status": "Thank_You"
    }


@app.post("/v1/federation/invitations", tags=["Federation"])
async def create_trust_invitation(
    request: TrustInvitationRequest,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:federation")),
):
    """
    REM: Create a trust invitation to send to another TelsonBase instance.
    REM: Share the returned invitation through a secure channel.
    """
    from federation.trust import get_federation_manager, TrustLevel

    # REM: Validate trust_level enum value
    try:
        trust_level = TrustLevel(request.trust_level)
    except ValueError:
        valid_levels = [level.value for level in TrustLevel]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trust_level '{request.trust_level}'. Valid values: {valid_levels}"
        )

    # REM: Validate expires_in_hours
    if request.expires_in_hours <= 0:
        raise HTTPException(
            status_code=400,
            detail="expires_in_hours must be positive"
        )

    fm = get_federation_manager()

    invitation = fm.create_trust_invitation(
        trust_level=trust_level,
        allowed_agents=request.allowed_agents,
        allowed_actions=request.allowed_actions,
        expires_in_hours=request.expires_in_hours
    )
    
    return {
        "invitation": invitation,
        "instructions": "Share this invitation with the target instance through a secure channel",
        "qms_status": "Please"
    }


@app.post("/v1/federation/invitations/process", tags=["Federation"])
async def process_trust_invitation(
    invitation: Dict[str, Any] = Body(...),
    auto_accept: bool = Query(False),
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:federation")),
):
    """
    REM: Process an incoming trust invitation from another instance.
    REM: Set auto_accept=true to immediately establish trust (use with caution).
    """
    from federation.trust import get_federation_manager

    fm = get_federation_manager()

    success, message, relationship = fm.process_trust_invitation(invitation, auto_accept)
    
    if relationship:
        # REM: Persist the relationship
        federation_store.store_relationship({
            "relationship_id": relationship.relationship_id,
            "remote_identity": relationship.remote_identity.to_dict(),
            "trust_level": relationship.trust_level.value,
            "status": relationship.status.value,
            "allowed_agents": relationship.allowed_agents,
            "allowed_actions": relationship.allowed_actions,
            "created_at": relationship.created_at.isoformat()
        })
    
    return {
        "success": success,
        "message": message,
        "relationship_id": relationship.relationship_id if relationship else None,
        "qms_status": "Thank_You" if success else "Thank_You_But_No"
    }


@app.get("/v1/federation/relationships", tags=["Federation"])
async def list_federation_relationships(
    status: Optional[str] = None,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:federation")),
):
    """REM: List all federation trust relationships."""
    relationships = federation_store.list_relationships(status=status)
    
    return {
        "relationships": relationships,
        "count": len(relationships),
        "qms_status": "Thank_You"
    }


@app.get("/v1/federation/relationships/{relationship_id}", tags=["Federation"])
async def get_federation_relationship(
    relationship_id: str,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:federation")),
):
    """REM: Get details of a specific trust relationship."""
    relationship = federation_store.get_relationship(relationship_id)
    
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    
    return {
        "relationship": relationship,
        "qms_status": "Thank_You"
    }


@app.post("/v1/federation/relationships/{relationship_id}/accept", tags=["Federation"])
async def accept_trust_relationship(
    relationship_id: str,
    request: TrustAcceptRequest,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:federation")),
):
    """REM: Accept a pending trust invitation."""
    relationship = federation_store.get_relationship(relationship_id)
    
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    
    if relationship.get("status") != "pending_inbound":
        raise HTTPException(
            status_code=400,
            detail=f"Relationship not pending (status: {relationship.get('status')})"
        )
    
    federation_store.update_relationship(relationship_id, {
        "status": "established",
        "established_at": datetime.now(timezone.utc).isoformat()
    })
    
    audit.log(
        AuditEventType.EXTERNAL_RESPONSE,
        f"Trust relationship ::{relationship_id}:: established",
        actor=request.decided_by,
        resource=relationship_id,
        qms_status="Thank_You"
    )
    
    return {
        "relationship_id": relationship_id,
        "status": "established",
        "qms_status": "Thank_You"
    }


@app.post("/v1/federation/relationships/{relationship_id}/revoke", tags=["Federation"])
async def revoke_trust_relationship(
    relationship_id: str,
    request: TrustRevokeRequest,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:federation")),
):
    """
    REM: Immediately revoke a trust relationship.
    REM: All future messages from the remote instance will be rejected.
    """
    relationship = federation_store.get_relationship(relationship_id)
    
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    
    federation_store.update_relationship(relationship_id, {
        "status": "revoked",
        "revoked_at": datetime.now(timezone.utc).isoformat(),
        "revocation_reason": request.reason
    })
    
    audit.log(
        AuditEventType.EXTERNAL_BLOCKED,
        f"Trust relationship ::{relationship_id}:: revoked - Reason: ::{request.reason}::",
        actor=request.revoked_by,
        resource=relationship_id,
        qms_status="Thank_You_But_No"
    )
    
    logger.warning(
        f"REM: Trust ::{relationship_id}:: REVOKED by ::{request.revoked_by}:: - "
        f"Reason: ::{request.reason}::_Thank_You_But_No"
    )
    
    return {
        "relationship_id": relationship_id,
        "status": "revoked",
        "reason": request.reason,
        "qms_status": "Thank_You_But_No"
    }


@app.post("/v1/federation/relationships/{relationship_id}/message", tags=["Federation"])
async def send_federated_message(
    relationship_id: str,
    message: FederatedMessageRequest,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:federation")),
    _rl=Depends(agent_rate_limit),
):
    """
    REM: Send an encrypted message to a federated instance.
    REM: Returns the wire-format message to be transmitted.
    """
    relationship = federation_store.get_relationship(relationship_id)
    
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    
    if relationship.get("status") != "established":
        raise HTTPException(
            status_code=400,
            detail=f"Trust not established (status: {relationship.get('status')})"
        )
    
    # REM: In production, this would actually send the message
    # REM: For now, we return what would be sent
    
    return {
        "status": "message_prepared",
        "relationship_id": relationship_id,
        "action": message.action,
        "note": "Message prepared for transmission. In production, this would be sent to the remote instance.",
        "qms_status": "Please"
    }


# REM: =======================================================================================
# REM: TOOLROOM API — TOOL INVENTORY & MANAGEMENT
# REM: =======================================================================================

@app.get("/v1/toolroom/status", tags=["Toolroom"])
async def get_toolroom_status(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:dashboard")),
):
    """
    REM: Full Toolroom status report.
    REM: QMS: Toolroom_Status_Please → Toolroom_Status_Thank_You
    """
    from toolroom.registry import tool_registry
    
    tools = tool_registry.list_tools()
    active_checkouts = tool_registry.get_active_checkouts()
    pending_requests = tool_registry.get_pending_requests()
    
    return {
        "status": "operational",
        "qms_status": "Thank_You",
        "summary": {
            "total_tools": len(tools),
            "available_tools": len([t for t in tools if t.status == "available"]),
            "checked_out_tools": len([t for t in tools if t.active_checkouts > 0]),
            "quarantined_tools": len([t for t in tools if t.status == "quarantined"]),
            "active_checkouts": len(active_checkouts),
            "pending_requests": len(pending_requests),
        },
        "redis_connected": toolroom_store.ping(),
    }


@app.get("/v1/toolroom/tools", tags=["Toolroom"])
async def list_toolroom_tools(
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    available_only: bool = Query(False, description="Only show available tools"),
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:dashboard")),
):
    """
    REM: List all tools in the Toolroom.
    REM: QMS: List_Tools_Please → List_Tools_Thank_You
    """
    from toolroom.registry import tool_registry
    
    tools = tool_registry.list_tools(
        category=category,
        status=status,
        available_only=available_only,
    )
    
    return {
        "status": "success",
        "qms_status": "Thank_You",
        "count": len(tools),
        "tools": [t.to_dict() for t in tools],
    }


@app.get("/v1/toolroom/tools/{tool_id}", tags=["Toolroom"])
async def get_toolroom_tool(
    tool_id: str,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:dashboard")),
):
    """REM: Get detailed information about a specific tool."""
    from toolroom.registry import tool_registry
    
    tool = tool_registry.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    
    return {
        "status": "success",
        "tool": tool.to_dict(),
    }


@app.get("/v1/toolroom/checkouts", tags=["Toolroom"])
async def list_active_checkouts(
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:dashboard")),
):
    """
    REM: List active tool checkouts.
    REM: QMS: List_Checkouts_Please → List_Checkouts_Thank_You
    """
    from toolroom.registry import tool_registry
    
    checkouts = tool_registry.get_active_checkouts(agent_id=agent_id)
    
    return {
        "status": "success",
        "qms_status": "Thank_You",
        "count": len(checkouts),
        "checkouts": [c.to_dict() for c in checkouts],
    }


@app.get("/v1/toolroom/checkouts/history", tags=["Toolroom"])
async def get_checkout_history(
    limit: int = Query(100, ge=1, le=500, description="Max entries to return"),
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:dashboard")),
):
    """
    REM: Get checkout history from Redis (not just in-memory cache).
    """
    from toolroom.registry import tool_registry
    
    history = tool_registry.get_full_checkout_history(limit=limit)
    
    return {
        "status": "success",
        "count": len(history),
        "history": [c.to_dict() for c in history],
    }


@app.get("/v1/toolroom/requests", tags=["Toolroom"])
async def list_tool_requests(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:dashboard")),
):
    """
    REM: List pending tool requests from agents.
    REM: QMS: List_Requests_Please → List_Requests_Thank_You
    """
    from toolroom.registry import tool_registry
    
    pending = tool_registry.get_pending_requests()
    
    return {
        "status": "success",
        "qms_status": "Thank_You",
        "count": len(pending),
        "requests": [r.to_dict() for r in pending],
    }


@app.get("/v1/toolroom/usage", tags=["Toolroom"])
async def get_tool_usage_report(
    tool_id: Optional[str] = Query(None, description="Filter by tool"),
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    limit: int = Query(100, ge=1, le=1000),
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:dashboard")),
):
    """
    REM: Usage report for tool checkout/return activity.
    """
    from toolroom.registry import tool_registry
    
    entries = tool_registry.get_usage_report(
        tool_id=tool_id,
        agent_id=agent_id,
        limit=limit,
    )
    
    return {
        "status": "success",
        "count": len(entries),
        "usage": entries,
    }


# REM: -----------------------------------------------------------------------------------
# REM: TOOLROOM — POST OPERATIONS (WRITE)
# REM: -----------------------------------------------------------------------------------
# REM: These endpoints let agents and operators actually USE the toolroom:
# REM: checkout tools, return them, propose installs, and request new tools.

class ToolCheckoutRequest(BaseModel):
    """REM: Request to check out a tool from the toolroom."""
    agent_id: str
    tool_id: str
    purpose: str = ""
    agent_trust_level: str = "resident"

class ToolReturnRequest(BaseModel):
    """REM: Request to return a checked-out tool."""
    checkout_id: str

class ToolInstallProposal(BaseModel):
    """REM: Propose installing a tool from an approved GitHub repo."""
    github_repo: str = Field(..., min_length=3, max_length=200)
    tool_name: str = Field(..., min_length=1, max_length=100)
    description: str
    category: str
    requires_api: bool = False

class ToolInstallExecution(BaseModel):
    """REM: Execute a tool install after HITL approval."""
    github_repo: str = Field(..., min_length=3, max_length=200)
    tool_name: str = Field(..., min_length=1, max_length=100)
    description: str
    category: str
    approval_request_id: str
    version: str = "latest"
    requires_api: bool = False
    allow_no_manifest: bool = False

class ApprovedSourceRequest(BaseModel):
    """REM: v6.0.0CC — Add/remove an approved GitHub source."""
    repo: str = Field(..., min_length=3, max_length=200)

class ToolRollbackRequest(BaseModel):
    """REM: v6.0.0CC — Roll back a tool to a previous version."""
    target_version: str

class NewToolRequestModel(BaseModel):
    """REM: Agent requesting a new tool that doesn't exist yet."""
    agent_id: str
    description: str
    suggested_source: str = ""
    justification: str = ""

class ApiCheckoutCompletion(BaseModel):
    """REM: Complete checkout of an API-access tool after HITL approval."""
    agent_id: str
    tool_id: str
    purpose: str
    approval_request_id: str


@app.post("/v1/toolroom/checkout", tags=["Toolroom"])
async def checkout_tool_endpoint(
    request: ToolCheckoutRequest,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:agents")),
    _rl=Depends(agent_rate_limit),
):
    """
    REM: Agent checks out a tool through the Foreman.
    REM: QMS: Foreman_Checkout_Tool_Please ::agent_id:: ::tool_id::
    REM: Returns checkout_id on success, or pending_approval if HITL gate triggered.
    """
    from toolroom.foreman import ForemanAgent
    
    foreman = ForemanAgent()
    result = foreman.handle_checkout_request(
        agent_id=request.agent_id,
        tool_id=request.tool_id,
        purpose=request.purpose,
        agent_trust_level=request.agent_trust_level,
    )
    
    if result["status"] == "error":
        raise HTTPException(status_code=403, detail=result)
    
    return result


@app.post("/v1/toolroom/return", tags=["Toolroom"])
async def return_tool_endpoint(
    request: ToolReturnRequest,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:agents")),
):
    """
    REM: Agent returns a tool after use.
    REM: QMS: Tool_Return_Please ::checkout_id::
    """
    from toolroom.foreman import ForemanAgent
    
    foreman = ForemanAgent()
    result = foreman.handle_return(request.checkout_id)
    
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result)
    
    return result


@app.post("/v1/toolroom/install/propose", tags=["Toolroom"])
async def propose_tool_install_endpoint(
    request: ToolInstallProposal,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:agents")),
):
    """
    REM: Propose a tool installation from an approved GitHub source.
    REM: Creates HITL approval request — does NOT auto-install.
    REM: QMS: Foreman_Install_Tool_Please ::github_repo::
    """
    from toolroom.foreman import ForemanAgent
    
    foreman = ForemanAgent()
    result = foreman.propose_tool_install(
        github_repo=request.github_repo,
        tool_name=request.tool_name,
        description=request.description,
        category=request.category,
        requires_api=request.requires_api,
    )
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result)
    
    return result


@app.post("/v1/toolroom/install/execute", tags=["Toolroom"])
async def execute_tool_install_endpoint(
    request: ToolInstallExecution,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:agents")),
):
    """
    REM: Execute a tool installation AFTER HITL approval.
    REM: Verifies approval exists and is approved before proceeding.
    REM: QMS: Foreman_Install_Execute_Thank_You (post-approval)
    """
    from toolroom.foreman import ForemanAgent
    
    foreman = ForemanAgent()
    result = foreman.execute_tool_install(
        github_repo=request.github_repo,
        tool_name=request.tool_name,
        description=request.description,
        category=request.category,
        version=request.version,
        requires_api=request.requires_api,
        approval_request_id=request.approval_request_id,
        allow_no_manifest=request.allow_no_manifest,
    )
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result)
    
    return result


@app.post("/v1/toolroom/request", tags=["Toolroom"])
async def request_new_tool_endpoint(
    request: NewToolRequestModel,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:agents")),
):
    """
    REM: Agent requests a tool that doesn't exist in the toolroom.
    REM: Foreman logs the request for HITL review.
    REM: QMS: New_Tool_Request_Please ::description:: from @@agent_id@@
    """
    from toolroom.foreman import ForemanAgent
    
    foreman = ForemanAgent()
    result = foreman.handle_new_tool_request(
        agent_id=request.agent_id,
        description=request.description,
        suggested_source=request.suggested_source,
        justification=request.justification,
    )
    
    return result


@app.post("/v1/toolroom/checkout/complete-api", tags=["Toolroom"])
async def complete_api_checkout_endpoint(
    request: ApiCheckoutCompletion,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:agents")),
):
    """
    REM: Complete checkout of an API-access tool AFTER HITL approval.
    REM: This is the second step in the two-step checkout for API tools:
    REM:   1. Agent calls /checkout → gets pending_approval + approval_request_id
    REM:   2. Human approves via /approvals/{id}/approve
    REM:   3. Agent/system calls this endpoint with the approval_request_id
    REM: QMS: Foreman_API_Checkout_Complete_Thank_You
    """
    from toolroom.foreman import ForemanAgent
    from core.approval import approval_gate, ApprovalStatus
    
    # REM: v4.6.0CC: Use get_approval_status() — checks Redis as fallback
    approval_info = approval_gate.get_approval_status(request.approval_request_id)
    
    if not approval_info:
        raise HTTPException(status_code=404, detail=
            f"Approval request '{request.approval_request_id}' not found"
        )
    
    if approval_info["status"] != ApprovalStatus.APPROVED.value:
        raise HTTPException(status_code=403, detail=
            f"Approval not approved (status: {approval_info['status']})"
        )
    
    foreman = ForemanAgent()
    checkout = foreman.registry.checkout_tool(
        tool_id=request.tool_id,
        agent_id=request.agent_id,
        purpose=request.purpose,
        approved_by=approval_info.get("decided_by") or "operator",
    )
    
    if not checkout:
        raise HTTPException(status_code=400, detail=
            "Checkout failed — tool may be unavailable"
        )
    
    return {
        "status": "success",
        "qms": f"API_Checkout_Complete_Thank_You ::{checkout.checkout_id}::",
        "checkout_id": checkout.checkout_id,
        "tool_id": request.tool_id,
        "agent_id": request.agent_id,
        "approval_request_id": request.approval_request_id,
        "message": f"API-access tool '{request.tool_id}' checked out to '{request.agent_id}'",
    }


# REM: --- v4.6.0CC: TOOL EXECUTION ENDPOINT ---

class ToolExecutionRequest(BaseModel):
    """REM: Request to execute a checked-out tool."""
    tool_id: str
    agent_id: str
    checkout_id: str
    inputs: Dict[str, Any] = {}


@app.post("/v1/toolroom/execute", tags=["Toolroom"])
async def execute_tool_endpoint(
    request: ToolExecutionRequest,
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:agents")),
    _rl=Depends(agent_rate_limit),
):
    """
    REM: Execute a tool that an agent has checked out.
    REM: Routes to subprocess or function execution based on tool type.
    REM: Requires active checkout — no execution without checkout.
    REM:
    REM: QMS: Tool_Execute_Please ::tool_id:: → Tool_Execute_Thank_You / Thank_You_But_No
    """
    from toolroom.foreman import ForemanAgent
    
    foreman = ForemanAgent()
    result = foreman.execute_tool(
        tool_id=request.tool_id,
        agent_id=request.agent_id,
        checkout_id=request.checkout_id,
        inputs=request.inputs,
    )
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


# REM: -----------------------------------------------------------------------------------
# REM: TOOLROOM v6.0.0CC — SOURCES, VERSION HISTORY, ROLLBACK
# REM: -----------------------------------------------------------------------------------

@app.get("/v1/toolroom/sources", tags=["Toolroom"])
async def list_approved_sources(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("manage:agents")),
):
    """
    REM: v6.0.0CC — List all approved GitHub sources for the toolroom.
    REM: QMS: Foreman_Sources_Thank_You
    """
    from toolroom.foreman import ForemanAgent
    foreman = ForemanAgent()
    return foreman.list_approved_sources()


@app.post("/v1/toolroom/sources", tags=["Toolroom"])
async def add_approved_source(
    request: ApprovedSourceRequest,
    auth: AuthResult = Depends(require_permission("manage:agents")),
):
    """
    REM: v6.0.0CC — Propose adding a GitHub repo to approved sources.
    REM: Creates HITL approval request — source is only added after approval.
    REM: QMS: Foreman_Add_Source_Please ::repo::
    """
    from toolroom.foreman import ForemanAgent
    foreman = ForemanAgent()
    result = foreman.add_approved_source(repo=request.repo, added_by=auth.actor)
    return result


@app.post("/v1/toolroom/sources/execute-add", tags=["Toolroom"])
async def execute_add_approved_source(
    request: ApprovedSourceRequest,
    auth: AuthResult = Depends(require_permission("manage:agents")),
):
    """
    REM: v6.0.0CC — Actually add a source after HITL approval.
    REM: Called by operator or approval callback.
    """
    from toolroom.foreman import ForemanAgent
    foreman = ForemanAgent()
    result = foreman.execute_add_approved_source(repo=request.repo, added_by=auth.actor)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.delete("/v1/toolroom/sources/{repo_owner}/{repo_name}", tags=["Toolroom"])
async def remove_approved_source(
    repo_owner: str,
    repo_name: str,
    auth: AuthResult = Depends(require_permission("manage:agents")),
):
    """
    REM: v6.0.0CC — Remove a GitHub repo from approved sources.
    REM: Tightening access — no HITL needed (restriction is always safe).
    """
    from toolroom.foreman import ForemanAgent
    repo = f"{repo_owner}/{repo_name}"
    foreman = ForemanAgent()
    result = foreman.execute_remove_approved_source(repo=repo, removed_by=auth.actor)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.get("/v1/toolroom/tools/{tool_id}/versions", tags=["Toolroom"])
async def get_tool_version_history(
    tool_id: str,
    auth: AuthResult = Depends(require_permission("view:dashboard")),
):
    """
    REM: v6.0.0CC — Get a tool's version history for rollback decisions.
    """
    from toolroom.registry import tool_registry
    history = tool_registry.get_version_history(tool_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    return {
        "tool_id": tool_id,
        "version_history": history,
        "count": len(history),
    }


@app.post("/v1/toolroom/tools/{tool_id}/rollback", tags=["Toolroom"])
async def rollback_tool_endpoint(
    tool_id: str,
    request: ToolRollbackRequest,
    auth: AuthResult = Depends(require_permission("manage:agents")),
):
    """
    REM: v6.0.0CC — Roll back a tool to a previous version.
    REM: Updates registry metadata. Operator may need to re-clone correct version.
    """
    from toolroom.registry import tool_registry
    result = tool_registry.rollback_tool(tool_id, request.target_version)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail=f"Rollback failed for '{tool_id}' to version '{request.target_version}'. "
                   f"Tool not found or version not in history."
        )
    return {
        "status": "success",
        "qms": f"Tool_Rollback_Thank_You ::{tool_id}::",
        **result,
    }


# REM: -----------------------------------------------------------------------------------
# REM: TOOLROOM CAGE — COMPLIANCE ARCHIVE (v6.0.0CC)
# REM: -----------------------------------------------------------------------------------

@app.get("/v1/toolroom/cage", tags=["Toolroom"])
async def get_cage_inventory(
    tool_id: Optional[str] = None,
    auth: AuthResult = Depends(require_permission("view:dashboard")),
):
    """
    REM: v6.0.0CC — List all cage archives (provenance records).
    REM: Optional filter by tool_id.
    REM: QMS: Cage_Inventory_Please
    """
    from toolroom.cage import cage
    inventory = cage.get_inventory(tool_id=tool_id)
    return {
        "status": "success",
        "qms": f"Cage_Inventory_Thank_You ::{len(inventory)} entries::",
        "count": len(inventory),
        "entries": inventory,
    }


@app.get("/v1/toolroom/cage/{receipt_id}", tags=["Toolroom"])
async def get_cage_receipt(
    receipt_id: str,
    auth: AuthResult = Depends(require_permission("view:dashboard")),
):
    """
    REM: v6.0.0CC — Get a specific cage receipt by ID.
    """
    from toolroom.cage import cage
    receipt = cage.get_receipt(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail=f"Cage receipt '{receipt_id}' not found")
    return receipt.to_dict()


@app.post("/v1/toolroom/cage/verify/{tool_id}", tags=["Toolroom"])
async def verify_tool_integrity(
    tool_id: str,
    auth: AuthResult = Depends(require_permission("security:audit")),
):
    """
    REM: v6.0.0CC — Verify a live tool's integrity against its cage archive.
    REM: Compares current SHA-256 hash with archived snapshot.
    REM: QMS: Cage_Verify_Please ::tool_id::
    """
    from toolroom.cage import cage
    from toolroom.executor import TOOLROOM_TOOLS_PATH
    live_path = TOOLROOM_TOOLS_PATH / tool_id
    result = cage.verify_tool(tool_id, live_path)
    return result


# REM: =======================================================================================
# REM: LLM ENGINE ENDPOINTS — Sovereign AI Brain
# REM: =======================================================================================
# REM: Direct REST API to the local Ollama engine. No cloud dependency.
# REM: All inference runs on your hardware, in your Docker network, under your control.
# REM: =======================================================================================

@app.get("/v1/llm/health", tags=["LLM Engine"])
async def llm_health(auth: AuthResult = Depends(require_permission("view:dashboard"))):
    """
    REM: Check Ollama engine health, latency, and available models.
    REM: QMS: Ollama_Health_Check_Please → Ollama_Health_Check_Thank_You
    """
    ollama = get_ollama_service()
    health = await ollama.ahealth_check()

    # REM: Enrich with model list if healthy
    if health.get("status") == "healthy":
        try:
            models = await ollama.alist_models()
            health["models_available"] = len(models)
            health["model_names"] = [m["name"] for m in models]
        except Exception:
            health["models_available"] = -1

    return health


@app.get("/v1/llm/models", tags=["LLM Engine"])
async def list_llm_models(auth: AuthResult = Depends(require_permission("view:dashboard"))):
    """
    REM: List all locally downloaded models with metadata.
    REM: Shows which models are recommended, which is default, size, and tier.
    """
    ollama = get_ollama_service()
    try:
        models = await ollama.alist_models()
        return {
            "models": models,
            "count": len(models),
            "default_model": ollama.default_model,
            "qms_status": "Ollama_List_Models_Thank_You",
        }
    except OllamaConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Ollama engine unreachable. Is the container running?"
        )


@app.get("/v1/llm/models/recommended", tags=["LLM Engine"])
async def recommended_models(auth: AuthResult = Depends(require_permission("view:dashboard"))):
    """
    REM: Curated model recommendations for consumer hardware.
    REM: Shows download status, RAM requirements, and best-use descriptions.
    REM: Dashboard uses this to populate the model selector.
    """
    ollama = get_ollama_service()
    models = await ollama.aget_recommended_models()
    return {
        "recommended": models,
        "count": len(models),
        "default_model": ollama.default_model,
    }


@app.get("/v1/llm/models/{model_name:path}", tags=["LLM Engine"])
async def model_info(
    model_name: str,
    auth: AuthResult = Depends(require_permission("view:dashboard")),
):
    """
    REM: Detailed info about a specific model — family, parameters, quantization.
    """
    ollama = get_ollama_service()
    try:
        info = await ollama.amodel_info(model_name)
        return info
    except OllamaModelError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OllamaConnectionError:
        raise HTTPException(status_code=503, detail="Ollama engine unreachable")
    except Exception:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found or unavailable.")


@app.post("/v1/llm/models/pull", tags=["LLM Engine"])
async def pull_model(
    request: LLMPullRequest,
    auth: AuthResult = Depends(require_permission("manage:agents")),
):
    """
    REM: Download a model from the Ollama registry.
    REM: QMS: Ollama_Pull_Model_Please ::model_name::
    REM:
    REM: WARNING: This is a blocking call. Large models (5GB+) will take minutes.
    REM: For production, dispatch as a background task via /v1/tasks/dispatch.
    """
    if not request.model or not request.model.strip():
        raise HTTPException(status_code=422, detail="Model name cannot be empty.")

    ollama = get_ollama_service()

    audit.log(
        AuditEventType.AGENT_ACTION,
        f"Ollama_Pull_Model_Please ::{request.model}::",
        actor=auth.actor,
        details={"model": request.model},
        qms_status="Please"
    )

    try:
        result = await ollama.apull_model(request.model)

        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Ollama_Pull_Model_Thank_You ::{request.model}::",
            actor=auth.actor,
            details=result,
            qms_status="Thank_You"
        )

        return result
    except OllamaConnectionError:
        raise HTTPException(status_code=503, detail="Ollama engine unreachable")
    except OllamaServiceError as e:
        logger.error(f"REM: Ollama service error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail="LLM engine error. Check server logs.")
    except Exception as e:
        logger.error(f"REM: Unexpected error pulling model: {e}_Thank_You_But_No")
        raise HTTPException(status_code=422, detail=f"Failed to pull model '{request.model}': {e}")


@app.delete("/v1/llm/models/{model_name:path}", tags=["LLM Engine"])
async def delete_model(
    model_name: str,
    auth: AuthResult = Depends(require_permission("manage:agents")),
):
    """
    REM: Delete a model from local storage.
    REM: QMS: Ollama_Delete_Model_Please ::model_name::
    """
    ollama = get_ollama_service()
    
    audit.log(
        AuditEventType.AGENT_ACTION,
        f"Ollama_Delete_Model_Please ::{model_name}::",
        actor=auth.actor,
        details={"model": model_name},
        qms_status="Please"
    )
    
    try:
        result = await ollama.adelete_model(model_name)
        return result
    except OllamaModelError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OllamaConnectionError:
        raise HTTPException(status_code=503, detail="Ollama engine unreachable")
    except Exception:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found or unavailable.")


@app.post("/v1/llm/generate", tags=["LLM Engine"])
async def llm_generate(
    request: LLMGenerateRequest,
    auth: AuthResult = Depends(require_permission("manage:agents")),
    _rl=Depends(agent_rate_limit),
):
    """
    REM: Single prompt → single response. Non-streaming.
    REM: QMS: Ollama_Generate_Please → Ollama_Generate_Thank_You
    REM:
    REM: Use this for one-shot tasks: summarize, classify, extract, translate.
    REM: For conversation, use /v1/llm/chat.
    """
    ollama = get_ollama_service()
    
    try:
        result = await ollama.agenerate(
            prompt=request.prompt,
            model=request.model,
            system=request.system,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        
        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Ollama_Generate_Thank_You ::{result['model']}:: {result.get('eval_count', 0)} tokens",
            actor=auth.actor,
            details={
                "model": result["model"],
                "prompt_length": len(request.prompt),
                "tokens_per_second": result.get("tokens_per_second", 0),
            },
            qms_status="Thank_You"
        )
        
        return result
        
    except OllamaModelError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OllamaConnectionError:
        raise HTTPException(status_code=503, detail="Ollama engine unreachable")
    except OllamaServiceError as e:
        logger.error(f"REM: Ollama service error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail="LLM engine error. Check server logs.")


@app.post("/v1/llm/chat", tags=["LLM Engine"])
async def llm_chat(
    request: LLMChatRequest,
    auth: AuthResult = Depends(require_permission("manage:agents")),
    _rl=Depends(agent_rate_limit),
):
    """
    REM: Multi-turn conversation. Non-streaming.
    REM: QMS: Ollama_Chat_Please → Ollama_Chat_Thank_You
    REM:
    REM: Messages format:
    REM:   [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
    REM:
    REM: The user chooses their model from the dashboard. If no model specified,
    REM: the system default is used (configurable via /v1/llm/default).
    """
    ollama = get_ollama_service()
    
    # REM: Validate message format
    for msg in request.messages:
        if "role" not in msg or "content" not in msg:
            raise HTTPException(
                status_code=422,
                detail="Each message must have 'role' and 'content' fields"
            )
        if msg["role"] not in ("user", "assistant", "system"):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid role: {msg['role']}. Use user/assistant/system"
            )
    
    try:
        result = await ollama.achat(
            messages=request.messages,
            model=request.model,
            system=request.system,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        
        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Ollama_Chat_Thank_You ::{result['model']}:: {len(request.messages)} messages",
            actor=auth.actor,
            details={
                "model": result["model"],
                "message_count": len(request.messages),
                "tokens_per_second": result.get("tokens_per_second", 0),
            },
            qms_status="Thank_You"
        )
        
        return result
        
    except OllamaModelError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OllamaConnectionError:
        raise HTTPException(status_code=503, detail="Ollama engine unreachable")
    except OllamaServiceError as e:
        logger.error(f"REM: Ollama service error: {e}_Thank_You_But_No")
        raise HTTPException(status_code=500, detail="LLM engine error. Check server logs.")


@app.put("/v1/llm/default", tags=["LLM Engine"])
async def set_default_model(
    model: str = Body(..., embed=True, description="Model name to set as default", min_length=1, max_length=200),
    auth: AuthResult = Depends(require_permission("admin:config")),
):
    """
    REM: Change the default model used when no model is specified.
    REM: QMS: Ollama_Set_Default_Please ::model_name::
    """
    ollama = get_ollama_service()
    old_default = ollama.default_model
    ollama.default_model = model
    
    audit.log(
        AuditEventType.AGENT_ACTION,
        f"Ollama_Set_Default_Thank_You ::{model}:: (was ::{old_default}::)",
        actor=auth.actor,
        details={"old_default": old_default, "new_default": model},
        qms_status="Thank_You"
    )
    
    return {
        "old_default": old_default,
        "new_default": model,
        "qms_status": "Ollama_Set_Default_Thank_You",
    }


# REM: =======================================================================================
# REM: MAIN ENTRY POINT
# REM: =======================================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
