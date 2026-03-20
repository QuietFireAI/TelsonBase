# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# TelsonBase/api/mcp_gateway.py
# REM: =======================================================================================
# REM: MCP GATEWAY — TELSONBASE AS AN MCP SERVER
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 24, 2026
# REM:
# REM: Mission Statement: Expose TelsonBase management capabilities as MCP (Model Context
# REM: Protocol) tools so that authorised operators using Goose, Claude Desktop, or any
# REM: MCP-compatible AI agent can drive TelsonBase workflows through natural language —
# REM: no n8n, no REST wrappers, no glue code.
# REM:
# REM: ⚠  SECURITY BOUNDARY — THIS IS NOT AN OPEN DOOR
# REM: -----------------------------------------------
# REM: The MCP gateway is an OPERATOR interface, not a public API. Access requires a
# REM: valid Bearer token (TelsonBase API key or JWT). All tool calls are logged to the
# REM: immutable audit chain just like any other API request.
# REM:
# REM: More importantly: TelsonBase operates on a ZERO external-data-egress policy.
# REM: No data leaves the sovereign perimeter without passing through a Human-in-the-Loop
# REM: (HITL) approval gate. When an agent — whether Goose or an internal OpenClaw
# REM: instance — must reach beyond the TelsonBase boundary to call an external service,
# REM: write to an external system, or exfiltrate any payload, that call is:
# REM:
# REM:   1. QUEUED in the toolroom as a pending approval request.
# REM:   2. HELD until a human operator reviews and explicitly approves it
# REM:      (via the portal Approvals tab or the approve_tool_request MCP tool).
# REM:   3. LOGGED with the approver's identity, timestamp, and reason before execution.
# REM:
# REM: The MCP tools in this file give operators VISIBILITY and CONTROL over that queue —
# REM: they do not bypass it. Saying "TelsonBase exposes an MCP endpoint" does not mean
# REM: the front door is open; it means authorised operators get a richer interface to the
# REM: same zero-trust, HITL-gated system they already operate.
# REM:
# REM: How it works:
# REM:   1. Operator runs Goose Desktop / CLI on their own machine (no Docker container).
# REM:   2. Goose is pointed at http://<host>:8000/mcp via goose.yaml.
# REM:   3. Goose discovers the tools below via MCP tool discovery (tools/list).
# REM:   4. Operator uses natural language: "Show me pending approvals", "List all agents",
# REM:      "Verify the audit chain", etc. Goose calls the appropriate MCP tool.
# REM:   5. If an agent action would cross the external boundary, Goose sees it appear in
# REM:      list_pending_approvals and the operator decides: approve or reject.
# REM:   6. First-time Goose sessions can self-register via register_as_agent, which places
# REM:      the session in OpenClaw quarantine until a human promotes its trust level.
# REM:
# REM: Transport: Streamable HTTP (SSE) — mounted at /mcp on the main FastAPI app.
# REM:
# REM: Auth: Bearer token (same TelsonBase API key / JWT used everywhere).
# REM:       Pass as:  Authorization: Bearer <token>
# REM:       Or set TELSONBASE_API_KEY in the Goose environment / goose.yaml.
# REM:
# REM: QMS Protocol:
# REM:   Success: "Thank_You"
# REM:   Failure: "Thank_You_But_No"
# REM: =======================================================================================

import contextvars
import hashlib
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# REM: =======================================================================================
# REM: MCP SESSION GATE
# REM: =======================================================================================
# REM: When OPENCLAW_ENABLED=true, MCP tool calls are gated on the trust level of the
# REM: registered OpenClaw instance whose API key matches the Bearer token.
# REM:
# REM: Gate levels:
# REM:   ALWAYS available:  get_health, system_status, register_as_agent
# REM:   QUARANTINE+:       list_agents, get_agent, audit tools, list_pending_approvals
# REM:   PROBATION+:        list_tenants, create_tenant, list_matters, approve_tool_request
# REM:
# REM: Goose connects → calls register_as_agent → session at QUARANTINE
# REM: → admin promotes in dashboard → full tool access at PROBATION+
# REM:
# REM: Non-registered sessions get a graceful "register first" message, not an error.
# REM: This is set via ASGI wrapper in main.py (see app.mount("/mcp", ...)).
# REM: =======================================================================================

# REM: ContextVar set by the ASGI wrapper in main.py before tool handlers run.
# REM: Contains the SHA-256 hash of the Bearer token, or None if unauthenticated.
_mcp_api_key_hash: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "mcp_api_key_hash", default=None
)

# REM: Trust level ordering for gate comparisons.
_TRUST_ORDER = {"quarantine": 0, "probation": 1, "resident": 2, "citizen": 3, "agent": 4}


def _check_mcp_session(tool_name: str, required_level: str = "probation") -> Optional[dict]:
    """
    REM: Gate check for MCP tool calls.
    REM: Returns None if the session is approved at the required level.
    REM: Returns a gate response dict (Goose displays this) if not.
    REM: Gate is bypassed when OPENCLAW_ENABLED=false.
    """
    try:
        from core.config import get_settings
        settings = get_settings()
        if not settings.openclaw_enabled:
            return None  # REM: Gate only active when OpenClaw governance is enabled

        key_hash = _mcp_api_key_hash.get()
        if not key_hash:
            return {
                "qms_status": "Excuse_Me",
                "status": "session_unrecognized",
                "message": (
                    "MCP session context unavailable. "
                    "Ensure Authorization: Bearer <api_key> header is set."
                ),
            }

        from core.openclaw import openclaw_manager
        instance = None
        for inst in openclaw_manager.list_instances():
            if inst.api_key_hash == key_hash:
                instance = inst
                break

        if instance is None:
            return {
                "qms_status": "Excuse_Me",
                "status": "session_not_registered",
                "message": (
                    "MCP session not registered under TelsonBase governance. "
                    "Call register_as_agent first — your session starts at QUARANTINE "
                    "and the administrator promotes trust when satisfied."
                ),
                "action": "register_as_agent(name='<your_name>', api_key='<your_api_key>')",
            }

        if instance.suspended:
            return {
                "qms_status": "Thank_You_But_No",
                "status": "session_suspended",
                "message": f"MCP session suspended: {instance.suspended_reason or 'kill switch active'}",
                "instance_id": instance.instance_id,
            }

        current = _TRUST_ORDER.get(instance.trust_level, 0)
        required = _TRUST_ORDER.get(required_level, 1)

        if current < required:
            return {
                "qms_status": "Excuse_Me",
                "status": "session_gated",
                "tool": tool_name,
                "trust_level": instance.trust_level,
                "required_level": required_level,
                "message": (
                    f"Tool '{tool_name}' requires '{required_level}' trust — "
                    f"session is at '{instance.trust_level}'. "
                    f"Administrator: promote this session in the TelsonBase dashboard."
                ),
                "instance_id": instance.instance_id,
                "action": (
                    f"POST /v1/openclaw/{instance.instance_id}/promote "
                    f"with new_level='{required_level}'"
                ),
            }

        return None  # REM: Session approved at required trust level

    except Exception as e:
        logger.warning(f"REM: MCP session gate check failed (permitting): {e}")
        return None  # REM: Fail open — gate error should not block legitimate operators


# REM: Create the FastMCP server instance. The name and instructions appear in
# REM: tool discovery responses so Goose knows what it's connected to.
mcp = FastMCP(
    name="TelsonBase",
    instructions=(
        "You are connected to TelsonBase by Quietfire AI — a sovereign AI agent "
        "management platform. Use these tools to inspect and manage AI agents "
        "(OpenClaw instances), tenants and client-matters, the audit chain, "
        "pending approvals, system health, and background tasks. "
        "Always check system_status first if something seems wrong. "
        "Call register_as_agent first to place your session under governance — "
        "this is required before operational tools are available."
    ),
)


# REM: =======================================================================================
# REM: SYSTEM TOOLS
# REM: =======================================================================================

@mcp.tool()
async def system_status() -> dict:
    """
    Get the full TelsonBase system status: service health, agent counts,
    audit chain integrity, and resource usage. Start here when diagnosing issues.
    """
    try:
        import redis as redis_lib

        from core.audit import audit
        from core.config import get_settings
        from core.openclaw import openclaw_manager

        r = redis_lib.from_url(get_settings().redis_url, decode_responses=True)
        redis_ok = r.ping()

        chain_state = audit.get_chain_state()
        instances = openclaw_manager.list_instances()
        active = sum(1 for i in instances if i.trust_level not in ("suspended",))
        suspended = sum(1 for i in instances if i.trust_level == "suspended")

        return {
            "qms_status": "Thank_You",
            "redis": "healthy" if redis_ok else "unreachable",
            "agents": {"total": len(instances), "active": active, "suspended": suspended},
            "audit_chain": {
                "entry_count": chain_state.get("entries_count", 0),
                "last_sequence": chain_state.get("last_sequence"),
            },
        }
    except Exception as e:
        logger.error(f"MCP system_status error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


@mcp.tool()
async def get_health() -> dict:
    """
    Quick liveness check. Returns healthy/degraded/unhealthy for each
    subsystem (Redis, Postgres, MQTT). Use system_status for full detail.
    """
    try:
        import redis as redis_lib

        from core.config import get_settings

        r = redis_lib.from_url(get_settings().redis_url, decode_responses=True)
        redis_ok = r.ping()
        return {
            "qms_status": "Thank_You",
            "redis": "healthy" if redis_ok else "degraded",
            "api": "healthy",
        }
    except Exception as e:
        return {"qms_status": "Thank_You_But_No", "redis": "unreachable", "error": str(e)}


# REM: =======================================================================================
# REM: AGENT TOOLS (OpenClaw)
# REM: =======================================================================================

@mcp.tool()
async def list_agents(include_suspended: bool = False) -> dict:
    """
    List all registered OpenClaw AI agents.

    Args:
        include_suspended: If True, include suspended/quarantined agents.
                           Default False returns only active agents.
    """
    gate = _check_mcp_session("list_agents", required_level="quarantine")
    if gate:
        return gate
    try:
        from core.openclaw import openclaw_manager

        instances = openclaw_manager.list_instances()
        if not include_suspended:
            instances = [i for i in instances if i.trust_level != "suspended"]

        return {
            "qms_status": "Thank_You",
            "count": len(instances),
            "agents": [
                {
                    "instance_id": i.instance_id,
                    "name": i.name,
                    "trust_level": i.trust_level,
                    "allowed_tools": i.allowed_tools,
                    "last_seen": str(i.last_seen) if hasattr(i, "last_seen") else None,
                }
                for i in instances
            ],
        }
    except Exception as e:
        logger.error(f"MCP list_agents error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


@mcp.tool()
async def get_agent(instance_id: str) -> dict:
    """
    Get full details for a specific OpenClaw agent by its instance ID.

    Args:
        instance_id: The agent's instance_id (from list_agents).
    """
    gate = _check_mcp_session("get_agent", required_level="quarantine")
    if gate:
        return gate
    try:
        from core.openclaw import openclaw_manager

        instance = openclaw_manager.get_instance(instance_id)
        if not instance:
            return {
                "qms_status": "Thank_You_But_No",
                "error": f"Agent '{instance_id}' not found",
            }
        return {"qms_status": "Thank_You", "agent": instance.to_dict()}
    except Exception as e:
        logger.error(f"MCP get_agent error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


@mcp.tool()
async def register_as_agent(
    name: str,
    api_key: str,
    initial_trust_level: str = "quarantine",
    override_reason: Optional[str] = None,
) -> dict:
    """
    Register this Goose session (or any external agent) as an OpenClaw instance
    in TelsonBase. After registration the agent appears on the portal's Agents tab.

    Args:
        name:                 A human-readable name for this agent session.
        api_key:              The agent's API key for future authentication.
        initial_trust_level:  One of: quarantine (default), probation, resident, citizen.
                              Anything above quarantine requires override_reason.
        override_reason:      Justification for starting above quarantine (min 10 chars).
    """
    try:
        _TRUST_LADDER = ["quarantine", "probation", "resident", "citizen"]
        level = (initial_trust_level or "quarantine").lower().strip()
        if level not in _TRUST_LADDER:
            return {
                "qms_status": "Thank_You_But_No",
                "error": f"Invalid trust level '{level}'. Valid: {_TRUST_LADDER}",
            }
        if level != "quarantine":
            if not override_reason or len(override_reason.strip()) < 10:
                return {
                    "qms_status": "Thank_You_But_No",
                    "error": "override_reason (min 10 chars) required when starting above quarantine",
                }

        from core.openclaw import openclaw_manager

        instance = openclaw_manager.register_instance(
            name=name,
            api_key=api_key,
            allowed_tools=[],
            blocked_tools=[],
            metadata={"source": "goose_mcp", "registered_via": "mcp_gateway"},
        )

        # REM: Ladder-walk to the requested trust level
        if level != "quarantine":
            target_idx = _TRUST_LADDER.index(level)
            for step in _TRUST_LADDER[1 : target_idx + 1]:
                openclaw_manager.promote_trust(
                    instance_id=instance.instance_id,
                    new_level=step,
                    promoted_by="mcp_gateway",
                    reason=override_reason,
                )

        logger.info(f"REM: Goose agent registered via MCP: {name} ({instance.instance_id})_Thank_You")
        return {
            "qms_status": "Thank_You",
            "instance_id": instance.instance_id,
            "name": name,
            "trust_level": level,
            "message": "Agent registered. It now appears in the TelsonBase portal under Registered Agents.",
        }
    except Exception as e:
        logger.error(f"MCP register_as_agent error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


# REM: =======================================================================================
# REM: TENANT & MATTER TOOLS
# REM: =======================================================================================

@mcp.tool()
async def list_tenants(active_only: bool = True) -> dict:
    """
    List all tenant organizations in TelsonBase.

    Args:
        active_only: If True (default), return only active tenants.
    """
    gate = _check_mcp_session("list_tenants", required_level="probation")
    if gate:
        return gate
    try:
        from core.tenancy import tenant_manager

        tenants = tenant_manager.list_tenants()
        if active_only:
            tenants = [t for t in tenants if t.is_active]

        return {
            "qms_status": "Thank_You",
            "count": len(tenants),
            "tenants": [
                {
                    "tenant_id": t.tenant_id,
                    "name": t.name,
                    "tenant_type": t.tenant_type if hasattr(t, "tenant_type") else None,
                    "is_active": t.is_active,
                }
                for t in tenants
            ],
        }
    except Exception as e:
        logger.error(f"MCP list_tenants error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


@mcp.tool()
async def create_tenant(name: str, tenant_type: str) -> dict:
    """
    Create a new tenant organization.

    Args:
        name:        Organization name.
        tenant_type: One of: law_firm, insurance, real_estate, healthcare,
                     small_business, personal, general.
    """
    gate = _check_mcp_session("create_tenant", required_level="probation")
    if gate:
        return gate
    _VALID_TYPES = [
        "law_firm", "insurance", "real_estate", "healthcare",
        "small_business", "personal", "general",
    ]
    if tenant_type not in _VALID_TYPES:
        return {
            "qms_status": "Thank_You_But_No",
            "error": f"Invalid tenant_type '{tenant_type}'. Valid: {_VALID_TYPES}",
        }
    try:
        from core.tenancy import tenant_manager

        tenant = tenant_manager.create_tenant(
            name=name,
            tenant_type=tenant_type,
            created_by="mcp_gateway",
        )
        return {"qms_status": "Thank_You", "tenant": tenant.to_dict()}
    except Exception as e:
        logger.error(f"MCP create_tenant error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


@mcp.tool()
async def list_matters(tenant_id: str, status_filter: Optional[str] = None) -> dict:
    """
    List all client-matters under a tenant.

    Args:
        tenant_id:     The tenant's ID (from list_tenants).
        status_filter: Optional — one of: active, closed, hold.
    """
    gate = _check_mcp_session("list_matters", required_level="probation")
    if gate:
        return gate
    try:
        from core.tenancy import tenant_manager

        tenant = tenant_manager.get_tenant(tenant_id=tenant_id)
        if not tenant:
            return {
                "qms_status": "Thank_You_But_No",
                "error": f"Tenant '{tenant_id}' not found",
            }

        matters = tenant_manager.list_matters(
            tenant_id=tenant_id,
            status_filter=status_filter,
        )
        return {
            "qms_status": "Thank_You",
            "tenant_name": tenant.name,
            "count": len(matters),
            "matters": [m.to_dict() for m in matters],
        }
    except Exception as e:
        logger.error(f"MCP list_matters error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


# REM: =======================================================================================
# REM: AUDIT CHAIN TOOLS
# REM: =======================================================================================

@mcp.tool()
async def get_audit_chain_status() -> dict:
    """
    Get the current audit chain state: entry count, last sequence number,
    and last hash. Use verify_audit_chain to check integrity end-to-end.
    """
    gate = _check_mcp_session("get_audit_chain_status", required_level="quarantine")
    if gate:
        return gate
    try:
        from core.audit import audit

        state = audit.get_chain_state()
        return {"qms_status": "Thank_You", "chain": state}
    except Exception as e:
        logger.error(f"MCP get_audit_chain_status error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


@mcp.tool()
async def verify_audit_chain(limit: int = 100) -> dict:
    """
    Cryptographically verify the audit chain integrity. Checks that each
    entry's hash correctly chains to the next. Returns any breaks found.

    Args:
        limit: Number of recent entries to verify (default 100, max 1000).
    """
    gate = _check_mcp_session("verify_audit_chain", required_level="quarantine")
    if gate:
        return gate
    try:
        from core.audit import audit

        limit = min(max(limit, 1), 1000)
        result = audit.verify_chain(limit=limit)
        return {
            "qms_status": "Thank_You",
            "valid": result.get("valid", False),
            "entries_checked": result.get("entries_checked", 0),
            "breaks": result.get("breaks", []),
            "message": result.get("message", ""),
        }
    except Exception as e:
        logger.error(f"MCP verify_audit_chain error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


@mcp.tool()
async def get_recent_audit_entries(limit: int = 20, event_type: Optional[str] = None) -> dict:
    """
    Retrieve recent audit chain entries.

    Args:
        limit:      Number of entries to return (default 20, max 200).
        event_type: Optional filter by event type (e.g. 'auth.success', 'agent.registered').
    """
    gate = _check_mcp_session("get_recent_audit_entries", required_level="quarantine")
    if gate:
        return gate
    try:
        from core.audit import audit

        limit = min(max(limit, 1), 200)
        entries = audit.get_entries(limit=limit, event_type=event_type)
        return {
            "qms_status": "Thank_You",
            "count": len(entries),
            "entries": entries,
        }
    except Exception as e:
        logger.error(f"MCP get_recent_audit_entries error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


# REM: =======================================================================================
# REM: APPROVALS TOOLS
# REM: =======================================================================================

@mcp.tool()
async def list_pending_approvals(limit: int = 20) -> dict:
    """
    List all pending approval requests in the TelsonBase toolroom queue.
    These are tool calls from agents that require human operator sign-off.

    Args:
        limit: Max number of approvals to return (default 20).
    """
    gate = _check_mcp_session("list_pending_approvals", required_level="probation")
    if gate:
        return gate
    try:
        from core.toolroom import toolroom_manager

        pending = toolroom_manager.get_pending_approvals(limit=limit)
        return {
            "qms_status": "Thank_You",
            "count": len(pending),
            "approvals": pending,
        }
    except Exception as e:
        logger.error(f"MCP list_pending_approvals error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}


@mcp.tool()
async def approve_tool_request(request_id: str, approved_by: str, notes: Optional[str] = None) -> dict:
    """
    Approve a pending tool request in the toolroom queue.

    Args:
        request_id:  The approval request ID (from list_pending_approvals).
        approved_by: Identity of the approving operator.
        notes:       Optional approval notes for the audit log.
    """
    gate = _check_mcp_session("approve_tool_request", required_level="probation")
    if gate:
        return gate
    try:
        from core.toolroom import toolroom_manager

        result = toolroom_manager.approve_request(
            request_id=request_id,
            approved_by=approved_by,
            notes=notes or "",
        )
        if result:
            return {"qms_status": "Thank_You", "approved": True, "request_id": request_id}
        return {
            "qms_status": "Thank_You_But_No",
            "error": f"Approval request '{request_id}' not found or already resolved",
        }
    except Exception as e:
        logger.error(f"MCP approve_tool_request error: {e}")
        return {"qms_status": "Thank_You_But_No", "error": str(e)}
