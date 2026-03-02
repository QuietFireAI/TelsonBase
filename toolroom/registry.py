# TelsonBase/toolroom/registry.py
# REM: =======================================================================================
# REM: TOOL REGISTRY - INVENTORY AND CHECKOUT SYSTEM
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: The Tool Registry is the master inventory of every tool available
# REM: to agents on base. It tracks what exists, who's using it, usage history, and
# REM: pending requests. Think of it as the tool crib at a machine shop — nothing leaves
# REM: without being signed out, nothing returns without being inspected.
# REM:
# REM: All state is persisted to Redis for durability across restarts.
# REM:
# REM: QMS Protocol:
# REM:   Tool_Checkout_Please ::agent_id:: ::tool_id::
# REM:   Tool_Checkout_Thank_You ::checkout_id::
# REM:   Tool_Checkout_Thank_You_But_No ::reason::
# REM:   Tool_Return_Please ::checkout_id::
# REM:   Tool_Request_New_Please ::tool_description:: ::requesting_agent::
# REM: =======================================================================================

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from dataclasses import dataclass, field, asdict
import json

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)

# REM: Import persistence store (lazy to avoid circular imports at module load)
_tool_store = None


def _get_store():
    """REM: Lazy-load the ToolroomStore to avoid circular imports."""
    global _tool_store
    if _tool_store is None:
        try:
            from core.persistence import toolroom_store
            _tool_store = toolroom_store
            if _tool_store.ping():
                logger.info("REM: Toolroom using Redis persistence (ToolroomStore)")
            else:
                logger.warning("REM: ToolroomStore instantiated but Redis not reachable")
                _tool_store = False
        except Exception as e:
            logger.warning(f"REM: Redis persistence unavailable for toolroom, using in-memory: {e}")
            _tool_store = False
    return _tool_store if _tool_store else None


# REM: =======================================================================================
# REM: DATA STRUCTURES
# REM: =======================================================================================

class ToolStatus(str, Enum):
    """REM: Lifecycle states for tools in the registry."""
    AVAILABLE = "available"           # Ready for checkout
    CHECKED_OUT = "checked_out"       # Currently in use by an agent
    UPDATING = "updating"             # Foreman is pulling updates
    DEPRECATED = "deprecated"         # Scheduled for removal
    QUARANTINED = "quarantined"       # Flagged — security review needed
    PENDING_UPLOAD = "pending_upload"  # Requested but not yet provided


class ToolCategory(str, Enum):
    """REM: Classification of tools by function."""
    DATABASE = "database"         # SQL, query tools
    PARSING = "parsing"           # Document parsers, extractors
    NETWORK = "network"           # HTTP clients, protocol handlers
    CRYPTO = "crypto"             # Encryption, hashing, signing
    FILESYSTEM = "filesystem"     # File manipulation tools
    ANALYTICS = "analytics"       # Data analysis, statistics
    INTEGRATION = "integration"   # External service connectors
    UTILITY = "utility"           # General-purpose helpers


@dataclass
class ToolMetadata:
    """
    REM: Complete metadata record for a tool in the registry.
    REM: This is the "inventory card" for every tool on the shelf.
    """
    tool_id: str
    name: str
    description: str
    category: str                            # ToolCategory value
    version: str
    source: str                              # "github:<org>/<repo>" or "upload:<filename>"
    status: str = ToolStatus.AVAILABLE       # ToolStatus value
    
    # REM: Access control
    requires_api_access: bool = False        # If True, HITL gate before checkout
    allowed_agents: List[str] = field(default_factory=list)  # Empty = all agents
    min_trust_level: str = "resident"        # Minimum AgentTrustLevel (lowercase to match enum)
    
    # REM: Provenance
    installed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    update_source: str = ""                  # Last GitHub repo or upload path
    sha256_hash: str = ""                    # Integrity hash of tool package
    
    # REM: Usage tracking
    total_checkouts: int = 0
    active_checkouts: int = 0
    last_checkout_at: str = ""
    last_checkout_by: str = ""

    # REM: v5.4.0CC: Concurrent checkout control
    # REM: 0 = unlimited (default for function tools — stateless, no disk state)
    # REM: 1 = exclusive (default for subprocess tools — share tool directory on disk)
    # REM: N = allow up to N simultaneous checkouts
    max_concurrent_checkouts: int = 1

    # REM: v4.6.0CC: Tool manifest — defines execution contract
    # REM: Stored as dict (serialized from tool_manifest.json)
    # REM: None means no manifest — tool exists but cannot be executed
    manifest_data: Optional[Dict[str, Any]] = None
    execution_type: str = "unknown"  # "subprocess", "function", "none"

    # REM: v5.4.0CC: Version history for rollback support
    # REM: Each entry: {version, sha256_hash, installed_at, source}
    # REM: Capped at 10 entries (oldest trimmed on update)
    version_history: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolMetadata":
        # REM: v5.5.0CC — Filter to known fields only. Prevents crashes when
        # REM: Redis contains records with fields from older/newer schema versions.
        known = set(cls.__dataclass_fields__.keys())
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class ToolCheckout:
    """
    REM: Record of an agent checking out a tool. Every checkout is logged.
    REM: Like a library card — we know who has what and when it's due back.
    REM: ID format: CHKOUT-{short_uuid} for QMS parseability in logs.
    """
    checkout_id: str = field(default_factory=lambda: f"CHKOUT-{uuid.uuid4().hex[:12]}")
    tool_id: str = ""
    agent_id: str = ""
    checked_out_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    returned_at: Optional[str] = None
    purpose: str = ""                        # Why the agent needs the tool
    approved_by: str = "system"              # Who authorized the checkout
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCheckout":
        # REM: v5.5.0CC — Filter to known fields (same pattern as ToolMetadata)
        known = set(cls.__dataclass_fields__.keys())
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class ToolRequest:
    """
    REM: An agent's request for a new tool that doesn't exist yet.
    REM: QMS: New_Tool_Request_Please ::description:: from @@agent_id@@
    REM: ID format: TOOLREQ-{short_uuid} for QMS parseability in logs.
    """
    request_id: str = field(default_factory=lambda: f"TOOLREQ-{uuid.uuid4().hex[:12]}")
    requesting_agent: str = ""
    tool_description: str = ""
    suggested_source: str = ""               # e.g., "github:dbcli/pgcli"
    justification: str = ""
    requested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "pending"                  # pending, approved, rejected, fulfilled
    reviewed_by: str = ""
    reviewed_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolRequest":
        return cls(**data)


# REM: =======================================================================================
# REM: TOOL REGISTRY — THE MASTER INVENTORY
# REM: =======================================================================================

class ToolRegistry:
    """
    REM: The single source of truth for all tools on base.
    REM: All agents access tools through this registry via the Foreman.
    REM: No direct tool access is permitted.
    """
    
    def __init__(self):
        # REM: In-memory state (warm cache, backed by Redis)
        self._tools: Dict[str, ToolMetadata] = {}
        self._active_checkouts: Dict[str, ToolCheckout] = {}
        self._checkout_history: List[ToolCheckout] = []
        self._tool_requests: Dict[str, ToolRequest] = {}
        self._usage_log: List[Dict[str, Any]] = []
        
        # REM: Load from Redis if available
        self._load_from_persistence()
        
        logger.info(
            f"REM: ToolRegistry initialized with {len(self._tools)} tools, "
            f"{len(self._active_checkouts)} active checkouts"
        )
    
    # REM: -----------------------------------------------------------------------------------
    # REM: TOOL MANAGEMENT
    # REM: -----------------------------------------------------------------------------------
    
    def register_tool(self, metadata: ToolMetadata) -> ToolMetadata:
        """
        REM: Add a new tool to the registry.
        REM: QMS: Tool_Register_Please ::tool_id:: → Tool_Register_Thank_You
        """
        if metadata.tool_id in self._tools:
            # REM: v5.4.0CC: Snapshot current version into history before overwriting
            existing = self._tools[metadata.tool_id]
            history_entry = {
                "version": existing.version,
                "sha256_hash": existing.sha256_hash,
                "installed_at": existing.installed_at,
                "source": existing.source,
                "updated_at": existing.last_updated,
            }
            # REM: Carry forward existing history + new snapshot
            if not hasattr(metadata, 'version_history') or not metadata.version_history:
                metadata.version_history = list(existing.version_history) if existing.version_history else []
            metadata.version_history.append(history_entry)
            # REM: Cap at 10 entries (trim oldest)
            if len(metadata.version_history) > 10:
                metadata.version_history = metadata.version_history[-10:]
            logger.warning(
                f"REM: Tool ::{metadata.tool_id}:: already registered, updating metadata. "
                f"Previous v{existing.version} saved to version_history "
                f"({len(metadata.version_history)} entries)"
            )

        self._tools[metadata.tool_id] = metadata
        self._persist_tools()
        
        audit.log(
            AuditEventType.TOOL_REGISTERED,
            f"Tool registered in toolroom: ::{metadata.name}:: v{metadata.version}",
            actor="foreman_agent",
            details={
                "tool_id": metadata.tool_id,
                "category": metadata.category,
                "source": metadata.source,
                "requires_api": metadata.requires_api_access,
            }
        )
        
        logger.info(
            f"REM: Tool_Register_Thank_You ::{metadata.tool_id}:: "
            f"({metadata.category}) from {metadata.source}"
        )
        return metadata
    
    def get_tool(self, tool_id: str) -> Optional[ToolMetadata]:
        """REM: Look up a tool by ID."""
        return self._tools.get(tool_id)
    
    def list_tools(
        self, 
        category: Optional[str] = None,
        status: Optional[str] = None,
        available_only: bool = False,
    ) -> List[ToolMetadata]:
        """
        REM: List tools with optional filters.
        REM: QMS: List_Tools_Please → List_Tools_Thank_You with ::count::
        """
        tools = list(self._tools.values())
        
        if category:
            tools = [t for t in tools if t.category == category]
        if status:
            tools = [t for t in tools if t.status == status]
        if available_only:
            tools = [t for t in tools if t.status == ToolStatus.AVAILABLE]
        
        return tools
    
    def update_tool_status(self, tool_id: str, new_status: str, reason: str = "") -> bool:
        """REM: Update a tool's status. Only the Foreman should call this."""
        tool = self._tools.get(tool_id)
        if not tool:
            return False
        
        old_status = tool.status
        tool.status = new_status
        tool.last_updated = datetime.now(timezone.utc).isoformat()
        self._persist_tools()
        
        # REM: Use appropriate TOOL_* audit event based on new status
        event_type = AuditEventType.TOOL_UPDATE
        if new_status == "quarantined":
            event_type = AuditEventType.TOOL_QUARANTINED
        
        audit.log(
            event_type,
            f"Tool status changed: ::{tool_id}:: {old_status} → {new_status}",
            actor="foreman_agent",
            details={"reason": reason, "tool_id": tool_id}
        )
        return True
    
    # REM: -----------------------------------------------------------------------------------
    # REM: VERSION HISTORY & ROLLBACK (v5.4.0CC)
    # REM: -----------------------------------------------------------------------------------

    def get_version_history(self, tool_id: str) -> Optional[List[Dict[str, str]]]:
        """
        REM: v5.4.0CC — Get a tool's version history.
        REM: Returns list of previous version snapshots, newest last.
        """
        tool = self._tools.get(tool_id)
        if not tool:
            return None
        return list(tool.version_history) if tool.version_history else []

    def rollback_tool(self, tool_id: str, target_version: str) -> Optional[Dict[str, Any]]:
        """
        REM: v5.4.0CC — Roll back a tool to a previous version from its history.
        REM: This updates the metadata only (version, sha256, source).
        REM: The caller (Foreman) is responsible for HITL approval and re-cloning
        REM: the correct version from GitHub if needed.
        REM:
        REM: Returns the rollback details dict on success, None on failure.
        """
        tool = self._tools.get(tool_id)
        if not tool:
            logger.warning(f"REM: Rollback failed — tool ::{tool_id}:: not found")
            return None

        if not tool.version_history:
            logger.warning(f"REM: Rollback failed — tool ::{tool_id}:: has no version history")
            return None

        # REM: Find the target version in history
        target_entry = None
        target_idx = None
        for idx, entry in enumerate(tool.version_history):
            if entry.get("version") == target_version:
                target_entry = entry
                target_idx = idx
                break

        if not target_entry:
            logger.warning(
                f"REM: Rollback failed — version '{target_version}' not found in "
                f"history for ::{tool_id}::"
            )
            return None

        # REM: Snapshot current version into history before rolling back
        current_snapshot = {
            "version": tool.version,
            "sha256_hash": tool.sha256_hash,
            "installed_at": tool.installed_at,
            "source": tool.source,
            "updated_at": tool.last_updated,
        }

        # REM: Apply the rollback
        old_version = tool.version
        tool.version = target_entry["version"]
        tool.sha256_hash = target_entry.get("sha256_hash", "")
        tool.source = target_entry.get("source", tool.source)
        tool.last_updated = datetime.now(timezone.utc).isoformat()

        # REM: Update history: remove the rolled-back-to entry, add current as snapshot
        tool.version_history.pop(target_idx)
        tool.version_history.append(current_snapshot)
        if len(tool.version_history) > 10:
            tool.version_history = tool.version_history[-10:]

        self._persist_tools()

        rollback_details = {
            "tool_id": tool_id,
            "rolled_back_from": old_version,
            "rolled_back_to": target_version,
            "sha256_hash": tool.sha256_hash,
        }

        audit.log(
            AuditEventType.TOOL_UPDATE,
            f"Tool rolled back: ::{tool_id}:: {old_version} → {target_version}",
            actor="foreman_agent",
            details=rollback_details,
        )

        logger.info(
            f"REM: Tool_Rollback_Thank_You ::{tool_id}:: "
            f"{old_version} → {target_version}"
        )
        return rollback_details

    # REM: -----------------------------------------------------------------------------------
    # REM: CHECKOUT SYSTEM
    # REM: -----------------------------------------------------------------------------------
    
    def checkout_tool(
        self,
        tool_id: str,
        agent_id: str,
        purpose: str = "",
        approved_by: str = "system",
    ) -> Optional[ToolCheckout]:
        """
        REM: Agent checks out a tool for use.
        REM: QMS: Tool_Checkout_Please ::agent_id:: ::tool_id::
        REM:      → Tool_Checkout_Thank_You ::checkout_id::
        REM:      → Tool_Checkout_Thank_You_But_No ::reason::
        """
        tool = self._tools.get(tool_id)
        if not tool:
            logger.warning(f"REM: Tool_Checkout_Thank_You_But_No ::tool_not_found:: ::{tool_id}::")
            return None
        
        if tool.status != ToolStatus.AVAILABLE and tool.status != ToolStatus.CHECKED_OUT:
            logger.warning(
                f"REM: Tool_Checkout_Thank_You_But_No "
                f"::tool_unavailable:: ::{tool_id}:: status={tool.status}"
            )
            return None
        
        # REM: v5.4.0CC: Exclusive checkout enforcement
        # REM: 0 = unlimited, N = max N concurrent checkouts
        if tool.max_concurrent_checkouts > 0 and tool.active_checkouts >= tool.max_concurrent_checkouts:
            # REM: Find who has it checked out for the response
            current_holders = [
                c for c in self._active_checkouts.values()
                if c.tool_id == tool_id
            ]
            holder_info = [
                {"agent_id": c.agent_id, "checkout_id": c.checkout_id, "since": c.checked_out_at}
                for c in current_holders
            ]
            logger.warning(
                f"REM: Tool_Checkout_Thank_You_But_No "
                f"::tool_busy:: ::{tool_id}:: "
                f"({tool.active_checkouts}/{tool.max_concurrent_checkouts} checkouts active)"
            )
            audit.log(
                AuditEventType.TOOL_CHECKOUT,
                f"Tool checkout denied (busy): ::{tool_id}:: requested by ::{agent_id}::, "
                f"held by {[h['agent_id'] for h in holder_info]}",
                actor=agent_id,
                details={"tool_id": tool_id, "holders": holder_info},
                qms_status="Thank_You_But_No"
            )
            return None

        # REM: Check agent authorization
        if tool.allowed_agents and agent_id not in tool.allowed_agents:
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Unauthorized tool checkout attempt: ::{agent_id}:: → ::{tool_id}::",
                actor=agent_id,
                details={"tool_id": tool_id, "allowed": tool.allowed_agents}
            )
            logger.warning(
                f"REM: Tool_Checkout_Thank_You_But_No "
                f"::agent_not_authorized:: ::{agent_id}:: for ::{tool_id}::"
            )
            return None
        
        # REM: Create checkout record
        checkout = ToolCheckout(
            tool_id=tool_id,
            agent_id=agent_id,
            purpose=purpose,
            approved_by=approved_by,
        )
        
        # REM: Update tool state
        tool.total_checkouts += 1
        tool.active_checkouts += 1
        tool.last_checkout_at = checkout.checked_out_at
        tool.last_checkout_by = agent_id
        
        self._active_checkouts[checkout.checkout_id] = checkout
        self._persist_tools()
        self._persist_checkouts()
        
        # REM: Log usage
        self._log_usage(tool_id, agent_id, "checkout", checkout.checkout_id)
        
        audit.log(
            AuditEventType.TOOL_CHECKOUT,
            f"Tool checked out: ::{tool_id}:: → ::{agent_id}:: (checkout ::{checkout.checkout_id}::)",
            actor="foreman_agent",
            details={
                "checkout_id": checkout.checkout_id,
                "tool_id": tool_id,
                "agent_id": agent_id,
                "purpose": purpose,
            }
        )
        
        logger.info(
            f"REM: Tool_Checkout_Thank_You ::{checkout.checkout_id}:: "
            f"::{tool_id}:: → ::{agent_id}::"
        )
        return checkout
    
    def return_tool(self, checkout_id: str) -> bool:
        """
        REM: Agent returns a tool after use.
        REM: QMS: Tool_Return_Please ::checkout_id:: → Tool_Return_Thank_You
        """
        checkout = self._active_checkouts.get(checkout_id)
        if not checkout:
            logger.warning(f"REM: Tool_Return_Thank_You_But_No ::checkout_not_found:: ::{checkout_id}::")
            return False
        
        checkout.returned_at = datetime.now(timezone.utc).isoformat()
        
        # REM: Update tool state
        tool = self._tools.get(checkout.tool_id)
        if tool:
            tool.active_checkouts = max(0, tool.active_checkouts - 1)
        
        # REM: Move to history
        self._checkout_history.append(checkout)
        del self._active_checkouts[checkout_id]
        self._persist_tools()
        self._persist_checkouts()
        self._persist_checkout_history_entry(checkout)
        
        # REM: Log usage
        self._log_usage(checkout.tool_id, checkout.agent_id, "return", checkout_id)
        
        logger.info(f"REM: Tool_Return_Thank_You ::{checkout_id}:: ::{checkout.tool_id}::")
        return True
    
    def cleanup_stale_checkouts(self, max_age_hours: int = 24) -> List[str]:
        """
        REM: v5.5.0CC — Remove checkouts older than max_age_hours.
        REM: Prevents permanently locked tools when a worker crashes mid-checkout.
        REM: Returns list of cleaned checkout IDs.
        """
        now = datetime.now(timezone.utc)
        stale = []
        for cid, checkout in list(self._active_checkouts.items()):
            try:
                checked_out = datetime.fromisoformat(checkout.checked_out_at)
                if (now - checked_out).total_seconds() > max_age_hours * 3600:
                    stale.append(cid)
            except (ValueError, TypeError):
                # REM: Unparseable timestamp — treat as stale
                stale.append(cid)

        for cid in stale:
            checkout = self._active_checkouts.pop(cid, None)
            if checkout:
                tool = self._tools.get(checkout.tool_id)
                if tool:
                    tool.active_checkouts = max(0, tool.active_checkouts - 1)
                logger.warning(
                    f"REM: Stale checkout cleaned: ::{cid}:: ::{checkout.tool_id}:: "
                    f"by ::{checkout.agent_id}:: (checked out {checkout.checked_out_at})"
                )

        if stale:
            self._persist()
        return stale

    def get_active_checkouts(self, agent_id: Optional[str] = None) -> List[ToolCheckout]:
        """REM: Get active checkouts, optionally filtered by agent."""
        checkouts = list(self._active_checkouts.values())
        if agent_id:
            checkouts = [c for c in checkouts if c.agent_id == agent_id]
        return checkouts
    
    # REM: -----------------------------------------------------------------------------------
    # REM: TOOL REQUESTS (agents requesting new tools)
    # REM: -----------------------------------------------------------------------------------
    
    def submit_tool_request(
        self,
        agent_id: str,
        description: str,
        suggested_source: str = "",
        justification: str = "",
    ) -> ToolRequest:
        """
        REM: Agent requests a tool that doesn't exist yet.
        REM: QMS: New_Tool_Request_Please ::description:: from @@agent_id@@
        """
        request = ToolRequest(
            requesting_agent=agent_id,
            tool_description=description,
            suggested_source=suggested_source,
            justification=justification,
        )
        
        self._tool_requests[request.request_id] = request
        self._persist_requests()
        
        audit.log(
            AuditEventType.TOOL_REQUEST,
            f"New tool requested by ::{agent_id}::: ::{description}::",
            actor=agent_id,
            details={
                "request_id": request.request_id,
                "suggested_source": suggested_source,
            }
        )
        
        logger.info(
            f"REM: New_Tool_Request_Please from @@{agent_id}@@ - "
            f"::{description}:: (source: {suggested_source})"
        )
        return request
    
    def get_pending_requests(self) -> List[ToolRequest]:
        """REM: Get all pending tool requests for Foreman review."""
        return [r for r in self._tool_requests.values() if r.status == "pending"]
    
    def resolve_request(
        self, request_id: str, status: str, reviewer: str = "foreman_agent"
    ) -> bool:
        """REM: Foreman resolves a tool request (approve/reject/fulfill)."""
        request = self._tool_requests.get(request_id)
        if not request:
            return False
        
        request.status = status
        request.reviewed_by = reviewer
        request.reviewed_at = datetime.now(timezone.utc).isoformat()
        self._persist_requests()
        
        logger.info(
            f"REM: Tool request ::{request_id}:: resolved as ::{status}:: by {reviewer}"
        )
        return True
    
    # REM: -----------------------------------------------------------------------------------
    # REM: USAGE TRACKING
    # REM: -----------------------------------------------------------------------------------
    
    def _log_usage(self, tool_id: str, agent_id: str, action: str, reference_id: str = ""):
        """REM: Internal usage logging for analytics and compliance."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_id": tool_id,
            "agent_id": agent_id,
            "action": action,
            "reference_id": reference_id,
        }
        self._usage_log.append(entry)
        
        # REM: Trim in-memory log (keep last 1000 entries, Redis has full history)
        if len(self._usage_log) > 1000:
            self._usage_log = self._usage_log[-1000:]
        
        store = _get_store()
        if store:
            try:
                store.append_to_list("usage_log", json.dumps(entry))
            except Exception as e:
                logger.warning(f"REM: Failed to persist usage log entry: {e}")
    
    def get_usage_report(
        self,
        tool_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """REM: Generate usage report with optional filters."""
        entries = self._usage_log
        if tool_id:
            entries = [e for e in entries if e["tool_id"] == tool_id]
        if agent_id:
            entries = [e for e in entries if e["agent_id"] == agent_id]
        return entries[-limit:]
    
    # REM: -----------------------------------------------------------------------------------
    # REM: PERSISTENCE (Redis-backed via ToolroomStore)
    # REM: -----------------------------------------------------------------------------------
    
    def _persist_tools(self):
        """REM: Save tool inventory to Redis."""
        store = _get_store()
        if store:
            try:
                data = {tid: t.to_dict() for tid, t in self._tools.items()}
                store.set("tools", json.dumps(data))
            except Exception as e:
                logger.warning(f"REM: Failed to persist tool registry: {e}")
    
    def _persist_checkouts(self):
        """REM: Save active checkouts to Redis."""
        store = _get_store()
        if store:
            try:
                data = {cid: c.to_dict() for cid, c in self._active_checkouts.items()}
                store.set("active_checkouts", json.dumps(data))
            except Exception as e:
                logger.warning(f"REM: Failed to persist checkouts: {e}")
    
    def _persist_checkout_history_entry(self, checkout: ToolCheckout):
        """
        REM: Append a completed checkout to the persistent history list.
        REM: Uses Redis list with automatic trimming (keeps last 10,000 entries).
        REM: In-memory list is warm cache only — Redis is the source of truth.
        """
        store = _get_store()
        if store:
            try:
                store.append_to_list(
                    "checkout_history",
                    json.dumps(checkout.to_dict()),
                    max_length=10000
                )
            except Exception as e:
                logger.warning(f"REM: Failed to persist checkout history entry: {e}")
    
    def _persist_requests(self):
        """REM: Save tool requests to Redis."""
        store = _get_store()
        if store:
            try:
                data = {rid: r.to_dict() for rid, r in self._tool_requests.items()}
                store.set("tool_requests", json.dumps(data))
            except Exception as e:
                logger.warning(f"REM: Failed to persist tool requests: {e}")
    
    def _load_from_persistence(self):
        """REM: Restore state from Redis on startup."""
        store = _get_store()
        if not store:
            logger.info("REM: No Redis store available — toolroom starting with empty state")
            return
        
        loaded_counts = {"tools": 0, "checkouts": 0, "requests": 0, "history": 0}
        
        try:
            # Load tools
            tools_raw = store.get("tools")
            if tools_raw:
                data = json.loads(tools_raw)
                self._tools = {
                    tid: ToolMetadata.from_dict(tdata) 
                    for tid, tdata in data.items()
                }
                loaded_counts["tools"] = len(self._tools)
            
            # Load active checkouts
            checkouts_raw = store.get("active_checkouts")
            if checkouts_raw:
                data = json.loads(checkouts_raw)
                self._active_checkouts = {
                    cid: ToolCheckout.from_dict(cdata) 
                    for cid, cdata in data.items()
                }
                loaded_counts["checkouts"] = len(self._active_checkouts)
            
            # Load tool requests
            requests_raw = store.get("tool_requests")
            if requests_raw:
                data = json.loads(requests_raw)
                self._tool_requests = {
                    rid: ToolRequest.from_dict(rdata) 
                    for rid, rdata in data.items()
                }
                loaded_counts["requests"] = len(self._tool_requests)
            
            # REM: Load recent checkout history into warm cache (last 100 entries)
            history_raw = store.get_list("checkout_history", -100, -1)
            if history_raw:
                self._checkout_history = [
                    ToolCheckout.from_dict(json.loads(entry))
                    for entry in history_raw
                ]
                loaded_counts["history"] = len(self._checkout_history)
            
            logger.info(
                f"REM: Toolroom state restored from Redis — "
                f"{loaded_counts['tools']} tools, "
                f"{loaded_counts['checkouts']} active checkouts, "
                f"{loaded_counts['requests']} requests, "
                f"{loaded_counts['history']} history entries"
            )
        except Exception as e:
            logger.warning(f"REM: Failed to restore toolroom state: {e}")
    
    def get_full_checkout_history(self, limit: int = 500) -> List[ToolCheckout]:
        """
        REM: Retrieve checkout history from Redis (not just in-memory cache).
        REM: Returns up to `limit` most recent completed checkouts.
        """
        store = _get_store()
        if store:
            try:
                raw_entries = store.get_list("checkout_history", -limit, -1)
                return [
                    ToolCheckout.from_dict(json.loads(entry))
                    for entry in raw_entries
                ]
            except Exception as e:
                logger.warning(f"REM: Failed to load checkout history from Redis: {e}")
        # REM: Fall back to in-memory cache
        return self._checkout_history[-limit:]


# REM: =======================================================================================
# REM: SINGLETON INSTANCE
# REM: =======================================================================================

tool_registry = ToolRegistry()
