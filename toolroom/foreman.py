# TelsonBase/toolroom/foreman.py
# REM: =======================================================================================
# REM: FOREMAN AGENT - SUPERVISOR-LEVEL TOOL MANAGEMENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: The Foreman is the supervisor of the Toolroom. No tool enters
# REM: or leaves without the Foreman's knowledge. The Foreman is the ONLY agent permitted
# REM: to access GitHub repositories for tool updates. Any operation that requires external
# REM: API access triggers a HITL (Human-In-The-Loop) gate — the Foreman notifies the
# REM: human operator and waits for explicit authorization before proceeding.
# REM:
# REM: Responsibilities:
# REM:   1. MAINTAIN all tools for agents (install, update, deprecate, quarantine)
# REM:   2. UPDATE tools daily from approved GitHub repositories ONLY
# REM:   3. CHECK AUTH of agents before granting tool access
# REM:   4. RECORD USAGE of every tool checkout and return
# REM:   5. IDENTIFY new tool requests from agents and route for approval
# REM:   6. NOTIFY HITL when API access is needed — NEVER proceed without human auth
# REM:
# REM: Security Constraints:
# REM:   - GitHub access ONLY (no arbitrary URLs, no pip install from internet)
# REM:   - HITL gate on ALL external operations
# REM:   - Cannot modify its own capabilities
# REM:   - All actions audited with hash-chained logs
# REM:
# REM: QMS Protocol:
# REM:   Foreman_Daily_Update_Please → Foreman_Daily_Update_Thank_You
# REM:   Foreman_Install_Tool_Please ::source:: → (HITL gate) → Install_Thank_You
# REM:   Foreman_Checkout_Tool_Please ::agent:: ::tool:: → Checkout_Thank_You
# REM:   Foreman_API_Access_Required_Pretty_Please ::reason:: → (waits for human)
# REM: =======================================================================================

import os
import hashlib
import shutil
import subprocess
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

from celery import shared_task

from core.audit import audit, AuditEventType
from core.trust_levels import AgentTrustLevel
from core.approval import approval_gate, ApprovalRule, ApprovalPriority, ApprovalStatus

# REM: v4.6.0CC — New imports for execution engine, manifests, versioning
from toolroom.manifest import (
    ToolManifest, load_manifest_from_tool_dir, validate_manifest, MANIFEST_FILENAME,
)
from toolroom.executor import (
    execute_subprocess_tool, execute_function_tool, ExecutionResult, TOOLROOM_TOOLS_PATH,
)
from toolroom.function_tools import function_tool_registry
from toolroom.cage import cage

logger = logging.getLogger(__name__)

# REM: =======================================================================================
# REM: AGENT CONFIGURATION
# REM: =======================================================================================

FOREMAN_AGENT_ID = "foreman_agent"

# REM: Capabilities — tightly scoped. Foreman can read/write the toolroom,
# REM: access GitHub (and ONLY GitHub) for updates, and communicate with agents.
CAPABILITIES = [
    "filesystem.read:/app/toolroom/*",
    "filesystem.write:/app/toolroom/tools/*",
    "filesystem.read:/data/*",                          # Read-only access to data volumes
    "external.read:github.com",                         # GitHub ONLY — no other external access
    "external.read:api.github.com",                     # GitHub API for release checks
    "external.read:raw.githubusercontent.com",           # GitHub raw content
    "agent.execute:*",                                  # Can interact with all agents (supervisor)
    "redis.read:toolroom:*",
    "redis.write:toolroom:*",
]

# REM: Actions that ALWAYS require human approval
REQUIRES_APPROVAL_FOR = [
    "install_tool_from_github",      # Any new tool installation
    "update_tool_from_github",       # Tool updates (daily check proposes, human approves)
    "enable_api_access_for_tool",    # Granting a tool API access
    "quarantine_tool",               # Taking a tool offline
    "delete_tool",                   # Permanent removal
]

# REM: =======================================================================================
# REM: APPROVED GITHUB SOURCES — v5.4.0CC RUNTIME-MANAGED
# REM: =======================================================================================
# REM: Seed defaults — these are loaded into Redis on first startup if no sources exist.
# REM: After that, sources are managed at runtime via API (add/remove with HITL approval).
# REM: The hardcoded list is a fallback ONLY when Redis is unavailable.
# REM: =======================================================================================
DEFAULT_GITHUB_SOURCES: List[str] = [
    "jqlang/jq",       # JSON query tool — lightweight, widely trusted
    "dbcli/pgcli",     # PostgreSQL CLI with auto-completion
    "dbcli/mycli",     # MySQL CLI with auto-completion
]

_SOURCES_REDIS_KEY = "toolroom:approved_sources"

# REM: In-memory cache of approved sources (warm cache backed by Redis)
APPROVED_GITHUB_SOURCES: List[str] = list(DEFAULT_GITHUB_SOURCES)


def _load_approved_sources() -> List[str]:
    """
    REM: v5.4.0CC — Load approved sources from Redis.
    REM: If Redis has no sources yet, seed with DEFAULT_GITHUB_SOURCES.
    REM: Returns the list and updates the module-level cache.
    """
    global APPROVED_GITHUB_SOURCES
    try:
        import redis
        from core.config import get_settings
        client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
        raw = client.get(_SOURCES_REDIS_KEY)
        if raw:
            sources = json.loads(raw)
            APPROVED_GITHUB_SOURCES = sources
            return sources
        else:
            # REM: First startup — seed Redis with defaults
            client.set(_SOURCES_REDIS_KEY, json.dumps(DEFAULT_GITHUB_SOURCES))
            APPROVED_GITHUB_SOURCES = list(DEFAULT_GITHUB_SOURCES)
            logger.info(
                f"REM: Seeded {len(DEFAULT_GITHUB_SOURCES)} default approved GitHub sources to Redis"
            )
            return APPROVED_GITHUB_SOURCES
    except Exception as e:
        logger.warning(f"REM: Could not load approved sources from Redis: {e}")
        APPROVED_GITHUB_SOURCES = list(DEFAULT_GITHUB_SOURCES)
        return APPROVED_GITHUB_SOURCES


def _save_approved_sources(sources: List[str]) -> bool:
    """REM: v5.4.0CC — Persist approved sources to Redis."""
    global APPROVED_GITHUB_SOURCES
    try:
        import redis
        from core.config import get_settings
        client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
        client.set(_SOURCES_REDIS_KEY, json.dumps(sources))
        APPROVED_GITHUB_SOURCES = list(sources)
        return True
    except Exception as e:
        logger.error(f"REM: Failed to save approved sources to Redis: {e}")
        return False

# REM: Path where tools are stored on disk — defaults to /app/toolroom/tools in Docker,
# REM: falls back to env var for local dev and CI (same pattern as CAGE_PATH in cage.py)
TOOLROOM_PATH = Path(os.environ.get("TOOLROOM_PATH", "/app/toolroom/tools"))

# REM: Toolroom-specific approval rule
# REM: All foreman actions in REQUIRES_APPROVAL_FOR trigger this rule.
TOOLROOM_APPROVAL_RULE = ApprovalRule(
    rule_id="rule-toolroom-operations",
    name="Toolroom Operations",
    description=(
        "All tool installations, updates, API access grants, quarantines, "
        "and deletions require human approval. The Foreman NEVER proceeds "
        "without explicit authorization."
    ),
    agent_pattern="foreman_agent",
    action_pattern="toolroom.*",
    priority=ApprovalPriority.HIGH,
    timeout_seconds=86400,      # 24 hours — no rush, human decides
    auto_reject_on_timeout=False,  # Don't auto-reject — hold until human acts
    enabled=True,
)

# REM: Register the rule with the approval gate at module load
try:
    approval_gate.add_rule(TOOLROOM_APPROVAL_RULE)
    logger.info("REM: Toolroom approval rule registered with ApprovalGate_Thank_You")
except Exception as e:
    logger.warning(f"REM: Could not register toolroom approval rule: {e}")


# REM: =======================================================================================
# REM: FOREMAN AGENT CLASS
# REM: =======================================================================================

class ForemanAgent:
    """
    REM: The Foreman — supervisor-level agent managing the Toolroom.
    REM: All tool operations flow through the Foreman.
    """
    
    def __init__(self):
        from toolroom.registry import tool_registry
        self.registry = tool_registry
        self.agent_id = FOREMAN_AGENT_ID

        # REM: Ensure toolroom directory exists
        TOOLROOM_PATH.mkdir(parents=True, exist_ok=True)

        # REM: v5.4.0CC: Load approved sources from Redis (seeds defaults on first startup)
        _load_approved_sources()

        logger.info(
            f"REM: Foreman Agent initialized. "
            f"Tools on shelf: {len(self.registry.list_tools())}. "
            f"Approved GitHub sources: {len(APPROVED_GITHUB_SOURCES)}"
        )
    
    # REM: -----------------------------------------------------------------------------------
    # REM: TOOL CHECKOUT — THE MAIN INTERFACE FOR AGENTS
    # REM: -----------------------------------------------------------------------------------
    
    def handle_checkout_request(
        self,
        agent_id: str,
        tool_id: str,
        purpose: str = "",
        agent_trust_level: str = AgentTrustLevel.RESIDENT,
    ) -> Dict[str, Any]:
        """
        REM: An agent requests to check out a tool.
        REM: QMS: Foreman_Checkout_Tool_Please ::agent_id:: ::tool_id::
        REM:
        REM: The Foreman verifies:
        REM:   1. Tool exists in registry
        REM:   2. Agent is authorized (trust level, allowed list)
        REM:   3. Tool doesn't require API access without HITL approval
        REM:   4. Checkout is recorded and audited
        """
        logger.info(
            f"REM: Foreman received: Checkout_Tool_Please "
            f"from @@{agent_id}@@ for ::{tool_id}::"
        )
        
        # REM: Step 1 — Tool exists?
        tool = self.registry.get_tool(tool_id)
        if not tool:
            logger.warning(
                f"REM: Foreman_Checkout_Thank_You_But_No "
                f"::tool_not_found:: ::{tool_id}::"
            )
            return {
                "status": "error",
                "qms": f"Tool_Checkout_Thank_You_But_No ::tool_not_found:: ::{tool_id}::",
                "message": f"Tool '{tool_id}' not found in toolroom",
            }
        
        # REM: Step 2 — Agent authorized?
        if tool.allowed_agents and agent_id not in tool.allowed_agents:
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Unauthorized checkout attempt: ::{agent_id}:: → ::{tool_id}::",
                actor=agent_id,
                details={"tool_id": tool_id, "agent_trust": agent_trust_level}
            )
            return {
                "status": "error",
                "qms": f"Tool_Checkout_Thank_You_But_No ::not_authorized:: ::{agent_id}::",
                "message": f"Agent '{agent_id}' not authorized for tool '{tool_id}'",
            }
        
        # REM: Step 3 — Trust level check
        # REM: Uses actual AgentTrustLevel enum values (lowercase) for correct comparison
        _trust_hierarchy = [
            AgentTrustLevel.QUARANTINE,   # "quarantine"
            AgentTrustLevel.PROBATION,    # "probation"
            AgentTrustLevel.RESIDENT,     # "resident"
            AgentTrustLevel.CITIZEN,      # "citizen"
        ]
        
        # REM: Normalize to lowercase for comparison — handles both "RESIDENT" and "resident"
        agent_level_norm = agent_trust_level.lower() if isinstance(agent_trust_level, str) else str(agent_trust_level).lower()
        tool_level_norm = tool.min_trust_level.lower() if isinstance(tool.min_trust_level, str) else str(tool.min_trust_level).lower()
        
        hierarchy_values = [lvl.value for lvl in _trust_hierarchy]
        if agent_level_norm in hierarchy_values:
            agent_level_idx = hierarchy_values.index(agent_level_norm)
        else:
            agent_level_idx = 0  # REM: Unknown agent → QUARANTINE (fail-safe)
            logger.warning(
                f"REM: Unknown agent trust level '{agent_trust_level}' for ::{agent_id}::, "
                f"defaulting to QUARANTINE (most restrictive)"
            )

        if tool_level_norm in hierarchy_values:
            required_level_idx = hierarchy_values.index(tool_level_norm)
        else:
            # REM: v5.4.0CC fix: Unknown tool trust → CITIZEN (most restrictive)
            # REM: Previously defaulted to index 2 (RESIDENT) which silently lowered the bar
            required_level_idx = len(hierarchy_values) - 1
            logger.warning(
                f"REM: Unknown tool trust level '{tool.min_trust_level}' for ::{tool_id}::, "
                f"defaulting to CITIZEN (most restrictive)"
            )
        
        if agent_level_idx < required_level_idx:
            logger.warning(
                f"REM: Foreman_Checkout_Thank_You_But_No "
                f"::insufficient_trust:: ::{agent_id}:: needs {tool.min_trust_level}, "
                f"has {agent_trust_level}"
            )
            return {
                "status": "error",
                "qms": f"Tool_Checkout_Thank_You_But_No ::insufficient_trust_level::",
                "message": (
                    f"Agent '{agent_id}' trust level {agent_trust_level} "
                    f"below minimum {tool.min_trust_level}"
                ),
            }
        
        # REM: Step 4 — API access gate
        if tool.requires_api_access:
            # REM: This tool needs external API access.
            # REM: We CANNOT proceed without human authorization.
            # REM: Create a real approval request so it's tracked and visible.
            api_approval = approval_gate.create_request(
                agent_id=agent_id,
                action="toolroom.checkout_api_tool",
                description=(
                    f"Agent '{agent_id}' requesting checkout of API-access tool "
                    f"'{tool_id}' for: {purpose or 'unspecified'}"
                ),
                payload={
                    "tool_id": tool_id,
                    "agent_id": agent_id,
                    "purpose": purpose,
                    "requires_api_access": True,
                },
                rule=TOOLROOM_APPROVAL_RULE,
                risk_factors=["api_access", f"tool:{tool_id}", f"agent:{agent_id}"],
            )
            
            audit.log(
                AuditEventType.TOOL_HITL_GATE,
                f"API-access tool checkout requires HITL: ::{tool_id}:: → ::{agent_id}::",
                actor=self.agent_id,
                details={
                    "tool_id": tool_id,
                    "agent_id": agent_id,
                    "approval_request_id": api_approval.request_id,
                },
            )
            
            logger.info(
                f"REM: Foreman_API_Access_Required_Pretty_Please "
                f"::tool={tool_id}:: ::agent={agent_id}:: "
                f"— Approval ::{api_approval.request_id}:: created"
            )
            return {
                "status": "pending_approval",
                "qms": (
                    f"Foreman_API_Access_Required_Pretty_Please "
                    f"::tool={tool_id}:: ::agent={agent_id}::"
                ),
                "approval_request_id": api_approval.request_id,
                "message": (
                    f"Tool '{tool_id}' requires API access. "
                    f"Approval request {api_approval.request_id} created. "
                    f"Awaiting human authorization."
                ),
                "approval_required": True,
                "tool_id": tool_id,
                "agent_id": agent_id,
            }
        
        # REM: Step 5 — All checks passed, proceed with checkout
        checkout = self.registry.checkout_tool(
            tool_id=tool_id,
            agent_id=agent_id,
            purpose=purpose,
            approved_by=self.agent_id,
        )
        
        if not checkout:
            return {
                "status": "error",
                "qms": f"Tool_Checkout_Thank_You_But_No ::checkout_failed::",
                "message": "Checkout failed — tool may be unavailable",
            }
        
        return {
            "status": "success",
            "qms": f"Tool_Checkout_Thank_You ::{checkout.checkout_id}::",
            "checkout_id": checkout.checkout_id,
            "tool_id": tool_id,
            "agent_id": agent_id,
            "message": f"Tool '{tool_id}' checked out to '{agent_id}'",
        }
    
    def handle_return(self, checkout_id: str) -> Dict[str, Any]:
        """
        REM: Agent returns a tool.
        REM: QMS: Tool_Return_Please ::checkout_id::
        """
        success = self.registry.return_tool(checkout_id)
        if success:
            return {
                "status": "success",
                "qms": f"Tool_Return_Thank_You ::{checkout_id}::",
                "message": f"Tool returned successfully",
            }
        return {
            "status": "error",
            "qms": f"Tool_Return_Thank_You_But_No ::not_found:: ::{checkout_id}::",
            "message": f"Checkout '{checkout_id}' not found",
        }
    
    # REM: -----------------------------------------------------------------------------------
    # REM: APPROVED SOURCES MANAGEMENT (v5.4.0CC)
    # REM: -----------------------------------------------------------------------------------

    def add_approved_source(self, repo: str, added_by: str = "operator") -> Dict[str, Any]:
        """
        REM: v5.4.0CC — Add a GitHub repo to the approved sources list.
        REM: Creates HITL approval request. Source is only added after approval.
        REM: QMS: Foreman_Add_Source_Please ::repo::
        """
        # REM: Normalize repo format (owner/repo)
        repo = repo.strip().lower()
        if "/" not in repo or len(repo.split("/")) != 2:
            return {
                "status": "error",
                "qms": f"Foreman_Add_Source_Thank_You_But_No ::invalid_format:: ::{repo}::",
                "message": f"Invalid repo format '{repo}'. Expected 'owner/repo'.",
            }

        current_sources = list(APPROVED_GITHUB_SOURCES)
        if repo in current_sources:
            return {
                "status": "error",
                "qms": f"Foreman_Add_Source_Thank_You_But_No ::already_approved:: ::{repo}::",
                "message": f"Repository '{repo}' is already in the approved list.",
            }

        # REM: Create HITL approval request
        approval_request = approval_gate.create_request(
            agent_id=self.agent_id,
            action="toolroom.add_approved_source",
            description=f"Add GitHub repository '{repo}' to approved sources whitelist",
            payload={"repo": repo, "added_by": added_by},
            rule=TOOLROOM_APPROVAL_RULE,
            risk_factors=["whitelist_modification", f"repo:{repo}"],
        )

        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Foreman proposing new approved source: ::{repo}::, requested by ::{added_by}::",
            actor=self.agent_id,
            details={"repo": repo, "approval_request_id": approval_request.request_id},
        )

        return {
            "status": "pending_approval",
            "qms": f"Foreman_Add_Source_Please ::{repo}:: — awaiting HITL",
            "approval_request_id": approval_request.request_id,
            "message": f"Source '{repo}' addition requires approval. Request: {approval_request.request_id}",
        }

    def execute_add_approved_source(self, repo: str, added_by: str = "operator") -> Dict[str, Any]:
        """
        REM: v5.4.0CC — Actually add the source after HITL approval.
        REM: Called by the approval callback or direct operator action.
        """
        current_sources = list(APPROVED_GITHUB_SOURCES)
        if repo in current_sources:
            return {"status": "error", "message": f"'{repo}' already approved"}

        current_sources.append(repo)
        if _save_approved_sources(current_sources):
            audit.log(
                AuditEventType.AGENT_ACTION,
                f"Approved source added: ::{repo}:: by ::{added_by}::",
                actor=self.agent_id,
                details={"repo": repo, "total_sources": len(current_sources)},
            )
            logger.info(f"REM: Foreman_Add_Source_Thank_You ::{repo}:: (total: {len(current_sources)})")
            return {
                "status": "success",
                "qms": f"Foreman_Add_Source_Thank_You ::{repo}::",
                "message": f"Source '{repo}' added to approved list",
                "approved_sources": current_sources,
            }
        return {"status": "error", "message": "Failed to persist to Redis"}

    def execute_remove_approved_source(self, repo: str, removed_by: str = "operator") -> Dict[str, Any]:
        """
        REM: v5.4.0CC — Remove a source from the approved list.
        REM: Direct operator action (no HITL needed for restriction — tightening is always safe).
        """
        current_sources = list(APPROVED_GITHUB_SOURCES)
        if repo not in current_sources:
            return {
                "status": "error",
                "qms": f"Foreman_Remove_Source_Thank_You_But_No ::not_found:: ::{repo}::",
                "message": f"Repository '{repo}' not in approved list.",
            }

        current_sources.remove(repo)
        if _save_approved_sources(current_sources):
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Approved source removed: ::{repo}:: by ::{removed_by}::",
                actor=self.agent_id,
                details={"repo": repo, "remaining_sources": len(current_sources)},
            )
            logger.info(f"REM: Foreman_Remove_Source_Thank_You ::{repo}:: (remaining: {len(current_sources)})")
            return {
                "status": "success",
                "qms": f"Foreman_Remove_Source_Thank_You ::{repo}::",
                "message": f"Source '{repo}' removed from approved list",
                "approved_sources": current_sources,
            }
        return {"status": "error", "message": "Failed to persist to Redis"}

    def list_approved_sources(self) -> Dict[str, Any]:
        """REM: v5.4.0CC — List all currently approved GitHub sources."""
        _load_approved_sources()
        return {
            "status": "success",
            "qms": f"Foreman_Sources_Thank_You ::{len(APPROVED_GITHUB_SOURCES)} sources::",
            "approved_sources": list(APPROVED_GITHUB_SOURCES),
            "count": len(APPROVED_GITHUB_SOURCES),
        }

    # REM: -----------------------------------------------------------------------------------
    # REM: TOOL INSTALLATION — HITL GATED
    # REM: -----------------------------------------------------------------------------------
    
    def propose_tool_install(
        self,
        github_repo: str,
        tool_name: str,
        description: str,
        category: str,
        requires_api: bool = False,
    ) -> Dict[str, Any]:
        """
        REM: Propose installing a tool from GitHub.
        REM: This ALWAYS goes through HITL approval. The Foreman prepares the
        REM: proposal and notifies the human operator. Installation only proceeds
        REM: after explicit human authorization.
        REM:
        REM: QMS: Foreman_Install_Tool_Please ::github_repo::
        REM:      → Foreman_API_Access_Required_Pretty_Please (HITL gate)
        """
        # REM: Validate source is from approved GitHub repos
        # REM: v5.5.0CC — Normalize to lowercase for consistent comparison
        github_repo = github_repo.strip().lower()
        if github_repo not in APPROVED_GITHUB_SOURCES:
            logger.warning(
                f"REM: Foreman_Install_Thank_You_But_No "
                f"::unapproved_source:: ::{github_repo}::"
            )
            return {
                "status": "error",
                "qms": (
                    f"Foreman_Install_Thank_You_But_No "
                    f"::unapproved_source:: ::{github_repo}::"
                ),
                "message": (
                    f"Repository '{github_repo}' is not on the approved sources list. "
                    f"Add it to APPROVED_GITHUB_SOURCES and redeploy to enable."
                ),
            }
        
        # REM: Build the proposal payload for HITL review
        proposal_payload = {
            "action": "install_tool_from_github",
            "source": f"github:{github_repo}",
            "tool_name": tool_name,
            "description": description,
            "category": category,
            "requires_api_access": requires_api,
            "proposed_by": self.agent_id,
            "proposed_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # REM: Create a real ApprovalRequest through the approval gate.
        # REM: This persists to Redis and is visible through the approval API.
        approval_request = approval_gate.create_request(
            agent_id=self.agent_id,
            action="toolroom.install_tool_from_github",
            description=(
                f"Install tool '{tool_name}' from github:{github_repo}. "
                f"Category: {category}. Requires API: {requires_api}."
            ),
            payload=proposal_payload,
            rule=TOOLROOM_APPROVAL_RULE,
            risk_factors=[
                "external_network_access",
                "github_clone",
                f"repo:{github_repo}",
            ],
        )
        
        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Foreman proposing tool install: ::{tool_name}:: from github:{github_repo}",
            actor=self.agent_id,
            details={
                **proposal_payload,
                "approval_request_id": approval_request.request_id,
            },
        )
        
        logger.info(
            f"REM: Foreman_Install_Tool_Please ::{github_repo}:: "
            f"— HITL approval request ::{approval_request.request_id}:: created"
        )
        
        return {
            "status": "pending_approval",
            "qms": (
                f"Foreman_API_Access_Required_Pretty_Please "
                f"::install:: ::{github_repo}::"
            ),
            "approval_request_id": approval_request.request_id,
            "proposal": proposal_payload,
            "message": (
                f"Tool install proposed: '{tool_name}' from github:{github_repo}. "
                f"Approval request {approval_request.request_id} created. "
                f"Awaiting human authorization."
            ),
        }
    
    def execute_tool_install(
        self,
        github_repo: str,
        tool_name: str,
        description: str,
        category: str,
        version: str = "latest",
        requires_api: bool = False,
        human_approver: str = "operator",
        approval_request_id: str = "",
        allow_no_manifest: bool = False,
    ) -> Dict[str, Any]:
        """
        REM: Execute a tool installation AFTER human approval.
        REM: Verifies the approval request exists and was approved before proceeding.
        REM:
        REM: QMS: Foreman_Install_Execute_Thank_You (post-approval)
        """
        from toolroom.registry import ToolMetadata, ToolCategory
        
        # REM: VERIFICATION — Confirm approval exists and is approved.
        # REM: v4.6.0CC: Uses get_approval_status() which checks Redis as fallback.
        # REM: This fixes the race condition where worker restart between approval
        # REM: creation and verification loses in-memory state.
        if approval_request_id:
            approval_info = approval_gate.get_approval_status(approval_request_id)
            
            if not approval_info:
                logger.error(
                    f"REM: Foreman_Install_Thank_You_But_No "
                    f"::approval_not_found:: ::{approval_request_id}::"
                )
                return {
                    "status": "error",
                    "qms": "Foreman_Install_Thank_You_But_No ::approval_not_found::",
                    "message": f"Approval request '{approval_request_id}' not found",
                }
            
            if approval_info["status"] != ApprovalStatus.APPROVED.value:
                logger.error(
                    f"REM: Foreman_Install_Thank_You_But_No "
                    f"::not_approved:: status={approval_info['status']}"
                )
                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    f"Attempted tool install without approval: ::{tool_name}:: "
                    f"approval_id={approval_request_id} status={approval_info['status']}",
                    actor=self.agent_id,
                    details={"approval_id": approval_request_id},
                )
                return {
                    "status": "error",
                    "qms": "Foreman_Install_Thank_You_But_No ::not_approved::",
                    "message": (
                        f"Approval request '{approval_request_id}' is not approved "
                        f"(current status: {approval_info['status']})"
                    ),
                }
            human_approver = approval_info.get("decided_by") or human_approver
        else:
            # REM: No approval_request_id provided — log warning but allow
            # REM: for backward compat (direct human CLI invocation).
            logger.warning(
                "REM: execute_tool_install called without approval_request_id. "
                "Proceeding on assumption of direct human invocation."
            )
            audit.log(
                AuditEventType.AGENT_ACTION,
                f"Tool install without formal approval_id — assumed direct CLI: "
                f"::{tool_name}:: from github:{github_repo}",
                actor=self.agent_id,
                details={"human_approver": human_approver},
            )
        
        # REM: v5.5.0CC — Normalize repo for consistent comparison
        github_repo = github_repo.strip().lower()
        tool_id = f"tool_{tool_name.lower().replace(' ', '_').replace('-', '_')}"
        install_path = TOOLROOM_PATH / tool_id
        
        logger.info(
            f"REM: Foreman executing approved install: ::{tool_name}:: "
            f"from github:{github_repo} (approved by ::{human_approver}::)"
        )
        
        try:
            # REM: Clone from GitHub (shallow clone for efficiency)
            # REM: v5.5.0CC fix: Do NOT mkdir before clone — git clone creates the
            # REM: directory itself and fails on non-empty directories. If a stale
            # REM: directory exists from a previous failed install, clean it first.
            if install_path.exists():
                shutil.rmtree(install_path, ignore_errors=True)
            install_path.parent.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                [
                    "git", "clone", "--depth", "1",
                    f"https://github.com/{github_repo}.git",
                    str(install_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            if result.returncode != 0:
                logger.error(f"REM: Git clone failed: {result.stderr}")
                return {
                    "status": "error",
                    "qms": f"Foreman_Install_Thank_You_But_No ::git_clone_failed::",
                    "message": f"Git clone failed: {result.stderr[:200]}",
                }
            
            # REM: Calculate integrity hash of installed files
            sha256 = self._hash_directory(install_path)
            
            # REM: v4.6.0CC: Load and validate tool manifest
            manifest = load_manifest_from_tool_dir(install_path)
            manifest_data = manifest.to_dict() if manifest else None
            execution_type = "subprocess" if manifest else "unknown"
            
            # REM: v5.4.0CC: Manifest is REQUIRED unless explicitly overridden
            if not manifest and not allow_no_manifest:
                # REM: Clean up — don't leave zombie directories
                shutil.rmtree(install_path, ignore_errors=True)
                audit.log(
                    AuditEventType.AGENT_ACTION,
                    f"Tool install rejected (no manifest): ::{tool_name}:: from github:{github_repo}",
                    actor=self.agent_id,
                    details={
                        "tool_name": tool_name,
                        "repo": github_repo,
                        "reason": f"No valid {MANIFEST_FILENAME} found in repository root",
                    },
                )
                logger.error(
                    f"REM: Foreman_Install_Thank_You_But_No ::manifest_required:: "
                    f"::{tool_name}:: — No valid {MANIFEST_FILENAME} in repo root. "
                    f"Installation aborted and directory cleaned up."
                )
                return {
                    "status": "error",
                    "qms": f"Foreman_Install_Thank_You_But_No ::manifest_required:: ::{tool_name}::",
                    "message": (
                        f"Tool '{tool_name}' rejected: no valid {MANIFEST_FILENAME} found. "
                        f"Every tool must provide a manifest defining its execution contract. "
                        f"Use allow_no_manifest=True to override (operator responsibility)."
                    ),
                }

            if not manifest and allow_no_manifest:
                logger.warning(
                    f"REM: Tool ::{tool_name}:: installed WITHOUT manifest (operator override). "
                    f"Tool exists in registry but CANNOT be executed until "
                    f"a {MANIFEST_FILENAME} is provided."
                )
                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    f"Tool installed without manifest (operator override): ::{tool_name}::",
                    actor=self.agent_id,
                    details={"tool_name": tool_name, "repo": github_repo},
                )
            
            # REM: Register in tool registry
            metadata = ToolMetadata(
                tool_id=tool_id,
                name=tool_name,
                description=description,
                category=category,
                version=version,
                source=f"github:{github_repo}",
                requires_api_access=requires_api,
                sha256_hash=sha256,
                update_source=f"github:{github_repo}",
                manifest_data=manifest_data,
                execution_type=execution_type,
            )
            
            self.registry.register_tool(metadata)

            # REM: v5.4.0CC: Archive to the cage for compliance/provenance
            cage_receipt = cage.archive_tool(
                tool_id=tool_id,
                tool_name=tool_name,
                version=version,
                source=f"github:{github_repo}",
                source_path=install_path,
                approved_by=human_approver,
                approval_request_id=approval_request_id,
                archive_type="install",
                notes=f"Installed from github:{github_repo}",
            )

            audit.log(
                AuditEventType.AGENT_ACTION,
                f"Tool installed: ::{tool_name}:: v{version} from github:{github_repo}",
                actor=self.agent_id,
                details={
                    "tool_id": tool_id,
                    "sha256": sha256,
                    "approved_by": human_approver,
                    "cage_receipt_id": cage_receipt.receipt_id if cage_receipt else None,
                }
            )

            return {
                "status": "success",
                "qms": f"Foreman_Install_Thank_You ::{tool_id}::  v{version}",
                "tool_id": tool_id,
                "sha256": sha256,
                "cage_receipt_id": cage_receipt.receipt_id if cage_receipt else None,
                "message": f"Tool '{tool_name}' installed successfully",
            }
            
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "qms": "Foreman_Install_Thank_You_But_No ::timeout::",
                "message": "Git clone timed out after 120 seconds",
            }
        except Exception as e:
            logger.error(f"REM: Tool install error: {e}")
            return {
                "status": "error",
                "qms": f"Foreman_Install_Thank_You_But_No ::error:: ::{e}::",
                "message": f"Installation failed: {str(e)}",
            }
    
    # REM: -----------------------------------------------------------------------------------
    # REM: TOOL UPLOAD — HUMAN-PROVIDED TOOLS
    # REM: -----------------------------------------------------------------------------------
    
    def register_uploaded_tool(
        self,
        tool_name: str,
        description: str,
        category: str,
        upload_path: str,
        version: str = "1.0.0",
        requires_api: bool = False,
    ) -> Dict[str, Any]:
        """
        REM: Register a tool that was manually uploaded by the human operator.
        REM: This is for tools like open-source SQL clients, parsers, etc.
        REM: that Jeff uploads directly to the toolroom.
        REM:
        REM: QMS: Foreman_Register_Upload_Please ::tool_name::
        """
        from toolroom.registry import ToolMetadata
        
        tool_id = f"tool_{tool_name.lower().replace(' ', '_').replace('-', '_')}"
        
        # REM: Verify upload path exists
        if not Path(upload_path).exists():
            return {
                "status": "error",
                "qms": f"Foreman_Register_Thank_You_But_No ::file_not_found:: ::{upload_path}::",
                "message": f"Upload path not found: {upload_path}",
            }
        
        # REM: Calculate integrity hash
        sha256 = self._hash_directory(Path(upload_path)) if Path(upload_path).is_dir() else self._hash_file(Path(upload_path))
        
        metadata = ToolMetadata(
            tool_id=tool_id,
            name=tool_name,
            description=description,
            category=category,
            version=version,
            source=f"upload:{Path(upload_path).name}",
            requires_api_access=requires_api,
            sha256_hash=sha256,
        )
        
        self.registry.register_tool(metadata)

        # REM: v5.4.0CC: Archive to cage
        cage_receipt = cage.archive_tool(
            tool_id=tool_id,
            tool_name=tool_name,
            version=version,
            source=f"upload:{Path(upload_path).name}",
            source_path=Path(upload_path),
            approved_by="operator",
            archive_type="install",
            notes=f"Uploaded by operator from {upload_path}",
        )

        logger.info(
            f"REM: Foreman_Register_Upload_Thank_You ::{tool_id}:: "
            f"v{version} from upload ::{upload_path}::"
        )

        return {
            "status": "success",
            "qms": f"Foreman_Register_Upload_Thank_You ::{tool_id}::",
            "tool_id": tool_id,
            "sha256": sha256,
            "cage_receipt_id": cage_receipt.receipt_id if cage_receipt else None,
            "message": f"Uploaded tool '{tool_name}' registered in toolroom",
        }
    
    # REM: -----------------------------------------------------------------------------------
    # REM: DAILY UPDATE CHECK — SCHEDULED BY CELERY BEAT
    # REM: -----------------------------------------------------------------------------------
    
    def check_for_updates(self) -> Dict[str, Any]:
        """
        REM: Daily check for tool updates from approved GitHub repos.
        REM: The Foreman checks each tool's source repo for new releases.
        REM: If updates are found, the Foreman PROPOSES them — does NOT auto-install.
        REM: Every update requires HITL approval.
        REM:
        REM: QMS: Foreman_Daily_Update_Please → Foreman_Daily_Update_Thank_You
        """
        logger.info("REM: Foreman received: Daily_Update_Check_Please")
        
        tools = self.registry.list_tools()
        github_tools = [t for t in tools if t.source.startswith("github:")]
        
        proposals = []
        errors = []
        
        for tool in github_tools:
            repo = tool.source.replace("github:", "").strip().lower()

            if repo not in APPROVED_GITHUB_SOURCES:
                logger.warning(
                    f"REM: Skipping update check for ::{tool.tool_id}:: "
                    f"— source ::{repo}:: no longer in approved list"
                )
                continue
            
            try:
                # REM: Check GitHub API for latest release
                # REM: NOTE: This is a READ-ONLY operation against GitHub API
                # REM: Actual download/install requires HITL approval
                result = subprocess.run(
                    [
                        "git", "ls-remote", "--tags",
                        f"https://github.com/{repo}.git",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    # REM: Parse latest tag
                    tags = result.stdout.strip().split("\n")
                    latest_tag = tags[-1].split("/")[-1] if tags else "unknown"
                    
                    # REM: v4.6.0CC: Semantic version comparison instead of string equality.
                    # REM: Handles v-prefixes, pre-release tags, etc.
                    # REM: Fixes Issue 5 from architectural review.
                    if latest_tag != "unknown":
                        try:
                            from packaging.version import parse as parse_version, InvalidVersion
                            # REM: Strip common 'v' prefix for comparison
                            clean_latest = latest_tag.lstrip("vV")
                            clean_current = tool.version.lstrip("vV")
                            
                            latest_ver = parse_version(clean_latest)
                            current_ver = parse_version(clean_current)
                            
                            is_newer = latest_ver > current_ver
                        except (InvalidVersion, Exception):
                            # REM: If parsing fails, fall back to string inequality
                            # REM: (better to propose a false update than miss a real one)
                            is_newer = (latest_tag != tool.version)
                            logger.warning(
                                f"REM: Version parse failed for ::{tool.tool_id}:: "
                                f"current={tool.version} latest={latest_tag} "
                                f"— falling back to string comparison"
                            )
                        
                        if is_newer:
                            # REM: v5.4.0CC: Create a real ApprovalRequest for each update
                            # REM: This makes proposals trackable, visible in approval API,
                            # REM: and actionable by the operator.
                            update_payload = {
                                "tool_id": tool.tool_id,
                                "tool_name": tool.name,
                                "current_version": tool.version,
                                "available_version": latest_tag,
                                "source": f"github:{repo}",
                            }
                            try:
                                update_approval = approval_gate.create_request(
                                    agent_id=self.agent_id,
                                    action="toolroom.update_tool_from_github",
                                    description=(
                                        f"Update tool '{tool.name}' from "
                                        f"v{tool.version} to {latest_tag} "
                                        f"(source: github:{repo})"
                                    ),
                                    payload=update_payload,
                                    rule=TOOLROOM_APPROVAL_RULE,
                                    risk_factors=[
                                        "external_network_access",
                                        "github_clone",
                                        f"repo:{repo}",
                                        f"tool:{tool.tool_id}",
                                    ],
                                )
                                update_payload["approval_request_id"] = update_approval.request_id
                                audit.log(
                                    AuditEventType.AGENT_ACTION,
                                    f"Update proposal for ::{tool.tool_id}::: "
                                    f"{tool.version} → {latest_tag} "
                                    f"(approval ::{update_approval.request_id}::)",
                                    actor=self.agent_id,
                                    details=update_payload,
                                )
                            except Exception as e:
                                logger.error(
                                    f"REM: Failed to create ApprovalRequest for "
                                    f"::{tool.tool_id}:: update: {e}"
                                )
                                update_payload["approval_request_id"] = None

                            proposals.append(update_payload)
                            logger.info(
                                f"REM: Update available for ::{tool.tool_id}::: "
                                f"{tool.version} → {latest_tag}"
                            )
                        
            except subprocess.TimeoutExpired:
                errors.append({"tool_id": tool.tool_id, "error": "timeout"})
            except Exception as e:
                errors.append({"tool_id": tool.tool_id, "error": str(e)})
        
        # REM: Log daily check results
        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Foreman daily update check: {len(github_tools)} tools checked, "
            f"{len(proposals)} updates available",
            actor=self.agent_id,
            details={
                "tools_checked": len(github_tools),
                "updates_available": len(proposals),
                "errors": len(errors),
            }
        )
        
        result = {
            "status": "success",
            "qms": f"Foreman_Daily_Update_Thank_You ::{len(proposals)} updates available::",
            "tools_checked": len(github_tools),
            "proposals": proposals,
            "errors": errors,
            "message": (
                f"Daily check complete. {len(proposals)} updates available. "
                f"HITL approval required for each update."
            ),
        }
        
        if proposals:
            logger.info(
                f"REM: Foreman_API_Access_Required_Pretty_Please "
                f"::daily_updates:: ::{len(proposals)} tools need updating:: "
                f"— Awaiting HITL authorization for each"
            )
        
        return result
    
    # REM: -----------------------------------------------------------------------------------
    # REM: NEW TOOL REQUESTS FROM AGENTS
    # REM: -----------------------------------------------------------------------------------
    
    def handle_new_tool_request(
        self,
        agent_id: str,
        description: str,
        suggested_source: str = "",
        justification: str = "",
    ) -> Dict[str, Any]:
        """
        REM: An agent needs a tool that doesn't exist yet.
        REM: Foreman logs the request and notifies HITL.
        REM:
        REM: QMS: New_Tool_Request_Please ::description:: from @@agent_id@@
        """
        request = self.registry.submit_tool_request(
            agent_id=agent_id,
            description=description,
            suggested_source=suggested_source,
            justification=justification,
        )
        
        logger.info(
            f"REM: Foreman received: New_Tool_Request_Please "
            f"from @@{agent_id}@@ — ::{description}:: "
            f"— Forwarding to HITL for review"
        )
        
        return {
            "status": "pending_review",
            "qms": (
                f"New_Tool_Request_Received_Thank_You "
                f"::{request.request_id}:: from @@{agent_id}@@"
            ),
            "request_id": request.request_id,
            "message": (
                f"Tool request recorded. Foreman will notify operator for review. "
                f"Request ID: {request.request_id}"
            ),
        }
    
    # REM: -----------------------------------------------------------------------------------
    # REM: STATUS & REPORTING
    # REM: -----------------------------------------------------------------------------------
    
    def get_toolroom_status(self) -> Dict[str, Any]:
        """
        REM: Full status report of the toolroom.
        REM: QMS: Toolroom_Status_Please → Toolroom_Status_Thank_You
        """
        all_tools = self.registry.list_tools()
        active_checkouts = self.registry.get_active_checkouts()
        pending_requests = self.registry.get_pending_requests()
        
        status_counts = {}
        for tool in all_tools:
            status_counts[tool.status] = status_counts.get(tool.status, 0) + 1
        
        category_counts = {}
        for tool in all_tools:
            category_counts[tool.category] = category_counts.get(tool.category, 0) + 1
        
        return {
            "status": "success",
            "qms": "Toolroom_Status_Thank_You",
            "total_tools": len(all_tools),
            "status_breakdown": status_counts,
            "category_breakdown": category_counts,
            "active_checkouts": len(active_checkouts),
            "pending_tool_requests": len(pending_requests),
            "approved_github_sources": len(APPROVED_GITHUB_SOURCES),
            "tools": [t.to_dict() for t in all_tools],
            "checkouts": [c.to_dict() for c in active_checkouts],
            "pending_requests": [r.to_dict() for r in pending_requests],
        }
    
    # REM: -----------------------------------------------------------------------------------
    # REM: TOOL EXECUTION — HOW AGENTS ACTUALLY USE TOOLS (v4.6.0CC)
    # REM: -----------------------------------------------------------------------------------

    def execute_tool(
        self,
        tool_id: str,
        agent_id: str,
        checkout_id: str,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        REM: Execute a tool that an agent has checked out.
        REM: Routes to subprocess or function execution based on tool type.
        REM:
        REM: Prerequisites:
        REM:   1. Agent must have an active checkout for this tool
        REM:   2. Tool must have a manifest (or be a function tool)
        REM:
        REM: QMS: Tool_Execute_Please ::tool_id:: → Tool_Execute_Thank_You / Thank_You_But_No
        """
        logger.info(
            f"REM: Tool_Execute_Please ::{tool_id}:: "
            f"agent={agent_id} checkout={checkout_id}"
        )

        # REM: Verify active checkout exists
        active = self.registry.get_active_checkouts(agent_id=agent_id)
        checkout_valid = any(
            c.checkout_id == checkout_id and c.tool_id == tool_id
            for c in active
        )

        if not checkout_valid:
            logger.warning(
                f"REM: Tool_Execute_Thank_You_But_No ::no_checkout:: "
                f"agent={agent_id} tool={tool_id} checkout={checkout_id}"
            )
            return {
                "status": "error",
                "qms": f"Tool_Execute_Thank_You_But_No ::no_checkout:: ::{tool_id}::",
                "message": (
                    f"Agent '{agent_id}' does not have an active checkout "
                    f"'{checkout_id}' for tool '{tool_id}'"
                ),
            }

        # REM: Check if it's a function tool first
        func_entry = function_tool_registry.get(tool_id)
        if func_entry:
            result = execute_function_tool(
                tool_id=tool_id,
                func=func_entry.func,
                inputs=inputs,
                agent_id=agent_id,
                checkout_id=checkout_id,
                timeout_seconds=func_entry.manifest.timeout_seconds,
            )
            return self._execution_result_to_response(result)

        # REM: Subprocess tool — needs manifest
        tool = self.registry.get_tool(tool_id)
        if not tool:
            return {
                "status": "error",
                "qms": f"Tool_Execute_Thank_You_But_No ::not_found:: ::{tool_id}::",
                "message": f"Tool '{tool_id}' not found in registry",
            }

        if not tool.manifest_data:
            return {
                "status": "error",
                "qms": f"Tool_Execute_Thank_You_But_No ::no_manifest:: ::{tool_id}::",
                "message": (
                    f"Tool '{tool_id}' has no manifest. Cannot execute without "
                    f"a {MANIFEST_FILENAME}. Upload one or register as function tool."
                ),
            }

        # REM: Reconstruct manifest and execute via subprocess
        manifest = ToolManifest.from_dict(tool.manifest_data)
        tool_dir = TOOLROOM_TOOLS_PATH / tool_id

        if not tool_dir.exists():
            return {
                "status": "error",
                "qms": f"Tool_Execute_Thank_You_But_No ::dir_missing:: ::{tool_id}::",
                "message": f"Tool directory not found: {tool_dir}",
            }

        result = execute_subprocess_tool(
            tool_id=tool_id,
            manifest=manifest,
            tool_dir=tool_dir,
            inputs=inputs,
            agent_id=agent_id,
            checkout_id=checkout_id,
        )
        return self._execution_result_to_response(result)

    def _execution_result_to_response(self, result: ExecutionResult) -> Dict[str, Any]:
        """REM: Convert ExecutionResult to API response dict."""
        if result.success:
            return {
                "status": "success",
                "qms": f"Tool_Execute_Thank_You ::{result.tool_id}::",
                "tool_id": result.tool_id,
                "exit_code": result.exit_code,
                "duration_seconds": result.duration_seconds,
                "output": result.output_data,
                "message": f"Tool '{result.tool_id}' executed successfully",
            }
        else:
            return {
                "status": "error",
                "qms": f"Tool_Execute_Thank_You_But_No ::{result.tool_id}::",
                "tool_id": result.tool_id,
                "exit_code": result.exit_code,
                "duration_seconds": result.duration_seconds,
                "error": result.error_message or result.stderr[:500],
                "message": f"Tool '{result.tool_id}' execution failed",
            }

    # REM: -----------------------------------------------------------------------------------
    # REM: FUNCTION TOOL SYNC — BRIDGE BETWEEN FUNCTION REGISTRY AND MAIN REGISTRY
    # REM: -----------------------------------------------------------------------------------

    def sync_function_tools(self) -> Dict[str, Any]:
        """
        REM: Sync function tools from FunctionToolRegistry into the main ToolRegistry.
        REM: This ensures function tools appear in toolroom status, can be checked out,
        REM: and have usage tracking just like git-cloned tools.
        REM:
        REM: Called at startup and when new function tools are registered.
        REM:
        REM: QMS: Sync_Function_Tools_Please → Sync_Function_Tools_Thank_You
        """
        from toolroom.registry import ToolMetadata

        synced = 0
        for entry in function_tool_registry.list_all():
            # REM: Register/update in main registry
            metadata = ToolMetadata(
                tool_id=entry.tool_id,
                name=entry.name,
                description=entry.description,
                category=entry.category,
                version=entry.version,
                source=f"function:{entry.func.__module__}.{entry.func.__name__}",
                requires_api_access=entry.requires_api_access,
                min_trust_level=entry.min_trust_level,
                manifest_data=entry.manifest.to_dict(),
                execution_type="function",
            )
            self.registry.register_tool(metadata)
            synced += 1

        if synced:
            logger.info(
                f"REM: Sync_Function_Tools_Thank_You — "
                f"{synced} function tools synced to main registry"
            )

        return {
            "status": "success",
            "qms": f"Sync_Function_Tools_Thank_You ::{synced} synced::",
            "synced_count": synced,
        }

    # REM: -----------------------------------------------------------------------------------
    # REM: INTERNAL UTILITIES
    # REM: -----------------------------------------------------------------------------------
    
    def _hash_directory(self, directory: Path) -> str:
        """
        REM: Calculate SHA-256 hash of all files in a directory.
        REM: v5.5.0CC — Delegates to Cage._hash_directory for consistent exclusion
        REM: rules. The Foreman's hash MUST match the Cage's hash for the same
        REM: content, otherwise verify_tool always reports tampering.
        """
        from toolroom.cage import Cage
        return Cage._hash_directory(directory)
    
    def _hash_file(self, filepath: Path) -> str:
        """REM: Calculate SHA-256 hash of a single file."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


# REM: =======================================================================================
# REM: CELERY TASKS — SCHEDULED AND ON-DEMAND
# REM: =======================================================================================

@shared_task(name="foreman_agent.daily_update_check")
def daily_update_check() -> Dict[str, Any]:
    """
    REM: Scheduled daily task — Foreman checks all GitHub-sourced tools for updates.
    REM: Triggered by Celery Beat every 24 hours.
    REM: QMS: Foreman_Daily_Update_Please (from Celery Beat)
    """
    logger.info(f"REM: {FOREMAN_AGENT_ID} received: 'Daily_Update_Check_Please' (scheduled)")
    foreman = ForemanAgent()
    return foreman.check_for_updates()


@shared_task(name="foreman_agent.checkout_tool")
def checkout_tool(
    agent_id: str,
    tool_id: str,
    purpose: str = "",
    agent_trust_level: str = "resident",
) -> Dict[str, Any]:
    """
    REM: Agent requests tool checkout through Celery task.
    REM: QMS: Foreman_Checkout_Tool_Please ::agent_id:: ::tool_id::
    """
    logger.info(
        f"REM: {FOREMAN_AGENT_ID} received: "
        f"'Checkout_Tool_Please' from @@{agent_id}@@ for ::{tool_id}::"
    )
    foreman = ForemanAgent()
    return foreman.handle_checkout_request(agent_id, tool_id, purpose, agent_trust_level)


@shared_task(name="foreman_agent.return_tool")
def return_tool(checkout_id: str) -> Dict[str, Any]:
    """
    REM: Agent returns a tool through Celery task.
    REM: QMS: Tool_Return_Please ::checkout_id::
    """
    logger.info(f"REM: {FOREMAN_AGENT_ID} received: 'Return_Tool_Please' ::{checkout_id}::")
    foreman = ForemanAgent()
    return foreman.handle_return(checkout_id)


@shared_task(name="foreman_agent.register_uploaded_tool")
def register_uploaded_tool(
    tool_name: str,
    description: str,
    category: str,
    upload_path: str,
    version: str = "1.0.0",
    requires_api: bool = False,
) -> Dict[str, Any]:
    """
    REM: Register a tool uploaded by the human operator.
    REM: QMS: Foreman_Register_Upload_Please ::tool_name::
    """
    logger.info(f"REM: {FOREMAN_AGENT_ID} received: 'Register_Upload_Please' ::{tool_name}::")
    foreman = ForemanAgent()
    return foreman.register_uploaded_tool(
        tool_name, description, category, upload_path, version, requires_api
    )


@shared_task(name="foreman_agent.request_new_tool")
def request_new_tool(
    agent_id: str,
    description: str,
    suggested_source: str = "",
    justification: str = "",
) -> Dict[str, Any]:
    """
    REM: Agent requests a tool that doesn't exist yet.
    REM: QMS: New_Tool_Request_Please ::description:: from @@agent_id@@
    """
    logger.info(
        f"REM: {FOREMAN_AGENT_ID} received: "
        f"'New_Tool_Request_Please' from @@{agent_id}@@ — ::{description}::"
    )
    foreman = ForemanAgent()
    return foreman.handle_new_tool_request(agent_id, description, suggested_source, justification)


@shared_task(name="foreman_agent.toolroom_status")
def toolroom_status() -> Dict[str, Any]:
    """
    REM: Get full toolroom status report.
    REM: QMS: Toolroom_Status_Please
    """
    logger.info(f"REM: {FOREMAN_AGENT_ID} received: 'Toolroom_Status_Please'")
    foreman = ForemanAgent()
    return foreman.get_toolroom_status()


@shared_task(name="foreman_agent.propose_tool_install")
def propose_tool_install(
    github_repo: str,
    tool_name: str,
    description: str,
    category: str,
    requires_api: bool = False,
) -> Dict[str, Any]:
    """
    REM: Propose installing a tool from an approved GitHub source.
    REM: Creates HITL approval request — does NOT auto-install.
    REM: QMS: Foreman_Install_Tool_Please ::github_repo::
    """
    logger.info(
        f"REM: {FOREMAN_AGENT_ID} received: "
        f"'Install_Tool_Please' — ::{tool_name}:: from github:{github_repo}"
    )
    foreman = ForemanAgent()
    return foreman.propose_tool_install(github_repo, tool_name, description, category, requires_api)


@shared_task(name="foreman_agent.execute_tool_install")
def execute_tool_install_task(
    github_repo: str,
    tool_name: str,
    description: str,
    category: str,
    version: str = "latest",
    requires_api: bool = False,
    human_approver: str = "operator",
    approval_request_id: str = "",
    allow_no_manifest: bool = False,
) -> Dict[str, Any]:
    """
    REM: Execute a tool installation AFTER human approval.
    REM: Verifies approval status before proceeding.
    REM: QMS: Foreman_Install_Execute_Thank_You (post-approval)
    """
    logger.info(
        f"REM: {FOREMAN_AGENT_ID} received: "
        f"'Execute_Install_Please' — ::{tool_name}:: from github:{github_repo} "
        f"(approval ::{approval_request_id}::)"
    )
    foreman = ForemanAgent()
    return foreman.execute_tool_install(
        github_repo, tool_name, description, category,
        version, requires_api, human_approver, approval_request_id,
        allow_no_manifest,
    )


@shared_task(name="foreman_agent.complete_api_checkout")
def complete_api_checkout(
    agent_id: str,
    tool_id: str,
    purpose: str,
    approval_request_id: str,
) -> Dict[str, Any]:
    """
    REM: Complete checkout of an API-access tool AFTER HITL approval.
    REM: Verifies the approval request was approved before completing checkout.
    REM: QMS: Foreman_API_Checkout_Complete_Thank_You
    """
    logger.info(
        f"REM: {FOREMAN_AGENT_ID} received: "
        f"'Complete_API_Checkout_Please' — ::{tool_id}:: → @@{agent_id}@@ "
        f"(approval ::{approval_request_id}::)"
    )
    
    # REM: Verify approval exists and is approved
    # REM: v4.6.0CC: Uses get_approval_status() — checks Redis as fallback.
    approval_info = approval_gate.get_approval_status(approval_request_id)
    
    if not approval_info:
        return {
            "status": "error",
            "qms": f"API_Checkout_Thank_You_But_No ::approval_not_found:: ::{approval_request_id}::",
            "message": f"Approval request '{approval_request_id}' not found",
        }
    
    if approval_info["status"] != ApprovalStatus.APPROVED.value:
        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"API tool checkout attempted without approval: ::{tool_id}:: → ::{agent_id}::",
            actor=FOREMAN_AGENT_ID,
            details={"approval_id": approval_request_id, "status": approval_info["status"]},
        )
        return {
            "status": "error",
            "qms": f"API_Checkout_Thank_You_But_No ::not_approved::",
            "message": f"Approval request not approved (status: {approval_info['status']})",
        }
    
    # REM: Approval verified — proceed with checkout
    foreman = ForemanAgent()
    checkout = foreman.registry.checkout_tool(
        tool_id=tool_id,
        agent_id=agent_id,
        purpose=purpose,
        approved_by=approval_info.get("decided_by") or "operator",
    )
    
    if not checkout:
        return {
            "status": "error",
            "qms": f"API_Checkout_Thank_You_But_No ::checkout_failed::",
            "message": "Checkout failed — tool may be unavailable",
        }
    
    return {
        "status": "success",
        "qms": f"API_Checkout_Complete_Thank_You ::{checkout.checkout_id}::",
        "checkout_id": checkout.checkout_id,
        "tool_id": tool_id,
        "agent_id": agent_id,
        "approval_request_id": approval_request_id,
        "message": f"API-access tool '{tool_id}' checked out to '{agent_id}' (approved)",
    }


# REM: =======================================================================================
# REM: v4.6.0CC: NEW CELERY TASKS — EXECUTION AND FUNCTION TOOL MANAGEMENT
# REM: =======================================================================================

@shared_task(name="foreman_agent.execute_tool")
def execute_tool_task(
    tool_id: str,
    agent_id: str,
    checkout_id: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    REM: Execute a checked-out tool via Celery.
    REM: Routes to subprocess or function execution based on tool type.
    REM: QMS: Tool_Execute_Please ::tool_id::
    """
    logger.info(
        f"REM: {FOREMAN_AGENT_ID} received: "
        f"'Tool_Execute_Please' — ::{tool_id}:: by @@{agent_id}@@ "
        f"checkout={checkout_id}"
    )
    foreman = ForemanAgent()
    return foreman.execute_tool(
        tool_id=tool_id,
        agent_id=agent_id,
        checkout_id=checkout_id,
        inputs=inputs or {},
    )


@shared_task(name="foreman_agent.sync_function_tools")
def sync_function_tools_task() -> Dict[str, Any]:
    """
    REM: Sync function tools into the main tool registry.
    REM: Called at startup and when new function tools are registered.
    REM: QMS: Sync_Function_Tools_Please
    """
    logger.info(f"REM: {FOREMAN_AGENT_ID} received: 'Sync_Function_Tools_Please'")
    foreman = ForemanAgent()
    return foreman.sync_function_tools()
