# TelsonBase/core/audit.py
# REM: =======================================================================================
# REM: AUDIT LOGGING SYSTEM FOR THE TelsonBase
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Immutable audit trail for all system actions. For legal/healthcare
# REM: deployments, you must be able to prove what happened, when, and who authorized it.
# REM: This module provides structured, timestamped logging that can be exported for
# REM: compliance audits.
# REM:
# REM: QMS Integration: Log messages follow QMS conventions for human readability.
# REM:
# REM: v4.3.0CC: Added cryptographic hash chaining for tamper-evident logs
# REM:   - Each log entry includes hash of previous entry
# REM:   - Chain can be verified to detect tampering
# REM:   - Persisted chain state survives restarts
# REM: =======================================================================================

import logging
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field
from pythonjsonlogger import jsonlogger


class _SafeJsonFormatter(jsonlogger.JsonFormatter):
    """
    REM: pythonjsonlogger 2.x workaround.
    REM: The base JsonFormatter raises KeyError on 'levelname' and on custom fmt
    REM: fields (e.g. event_type) when those keys are absent from a log record.
    REM: Setting defaults before super().process_log_record() prevents the error.
    """
    def process_log_record(self, log_record: dict) -> dict:
        log_record.setdefault("levelname", "")
        log_record.setdefault("event_type", "")
        return super().process_log_record(log_record)
from core.config import get_settings

settings = get_settings()


# REM: Genesis hash for the first entry in a new chain
GENESIS_HASH = "0" * 64  # SHA-256 produces 64 hex chars


@dataclass
class AuditChainEntry:
    """
    REM: A single entry in the cryptographic audit chain.
    REM: Each entry contains a hash of its content plus the previous entry's hash.
    """
    sequence: int
    timestamp: str
    event_type: str
    message: str
    actor: str
    resource: Optional[str]
    details: Dict[str, Any]
    previous_hash: str
    actor_type: str = "system"  # v6.3.0CC: HIPAA unique user identification
    entry_hash: str = ""

    def compute_hash(self) -> str:
        """REM: Compute SHA-256 hash of this entry's content + previous hash."""
        content = json.dumps({
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "message": self.message,
            "actor": self.actor,
            "actor_type": self.actor_type,
            "resource": self.resource,
            "details": self.details,
            "previous_hash": self.previous_hash
        }, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "message": self.message,
            "actor": self.actor,
            "actor_type": self.actor_type,
            "resource": self.resource,
            "details": self.details,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash
        }


@dataclass
class ChainState:
    """REM: Current state of the audit chain."""
    last_sequence: int = 0
    last_hash: str = GENESIS_HASH
    chain_id: str = ""
    created_at: str = ""
    entries_count: int = 0


class AuditEventType(str, Enum):
    """
    REM: Categorization of audit events. Each type represents a distinct
    REM: action category for filtering and compliance reporting.
    """
    # Authentication events
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_TOKEN_ISSUED = "auth.token_issued"
    
    # Task/Agent events
    TASK_DISPATCHED = "task.dispatched"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    # External communication events
    EXTERNAL_REQUEST = "external.request"
    EXTERNAL_BLOCKED = "external.blocked"
    EXTERNAL_RESPONSE = "external.response"
    
    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    
    # Data events
    BACKUP_STARTED = "backup.started"
    BACKUP_COMPLETED = "backup.completed"
    BACKUP_FAILED = "backup.failed"
    
    # Agent events
    AGENT_REGISTERED = "agent.registered"
    AGENT_HEARTBEAT = "agent.heartbeat"
    AGENT_ERROR = "agent.error"
    AGENT_ACTION = "agent.action"  # v3.0.2: QMS-logged agent actions
    
    # Security events (v3.0.2)
    SECURITY_ALERT = "security.alert"          # Potential security issue detected
    SECURITY_QMS_BYPASS = "security.qms_bypass"  # Non-QMS message detected
    
    # Capability & approval events (v5.1.0CC fix)
    CAPABILITY_CHECK = "capability.check"        # Capability enforcement check
    APPROVAL_GRANTED = "approval.granted"        # Approval request granted
    ANOMALY_DETECTED = "anomaly.detected"        # Behavioral anomaly detected

    # Toolroom events (v4.4.0CC)
    TOOL_REGISTERED = "tool.registered"        # New tool added to toolroom
    TOOL_CHECKOUT = "tool.checkout"            # Agent checked out a tool
    TOOL_RETURN = "tool.return"               # Agent returned a tool
    TOOL_UPDATE = "tool.update"               # Tool updated from source
    TOOL_QUARANTINED = "tool.quarantined"     # Tool flagged for security review
    TOOL_REQUEST = "tool.request"             # Agent requested a new tool
    TOOL_HITL_GATE = "tool.hitl_gate"         # HITL approval required for tool operation

    # Identity events (v7.3.0CC — Identiclaw MCP-I integration)
    IDENTITY_REGISTERED = "identity.registered"               # New DID agent registered
    IDENTITY_VERIFIED = "identity.verified"                   # DID signature verified
    IDENTITY_VERIFICATION_FAILED = "identity.verification_failed"  # Verification failure
    IDENTITY_REVOKED = "identity.revoked"                     # Agent DID revoked (kill switch)
    IDENTITY_REINSTATED = "identity.reinstated"               # Agent DID reinstated after review
    IDENTITY_CREDENTIAL_UPDATED = "identity.credential_updated"  # VC refreshed/changed

    # OpenClaw governance events (v7.4.0CC)
    OPENCLAW_REGISTERED = "openclaw.registered"                   # New claw instance registered
    OPENCLAW_ACTION_ALLOWED = "openclaw.action_allowed"           # Action passed governance pipeline
    OPENCLAW_ACTION_BLOCKED = "openclaw.action_blocked"           # Action rejected by governance
    OPENCLAW_ACTION_GATED = "openclaw.action_gated"               # Action sent to approval queue
    OPENCLAW_TRUST_PROMOTED = "openclaw.trust_promoted"           # Trust level promoted
    OPENCLAW_TRUST_DEMOTED = "openclaw.trust_demoted"             # Trust level demoted
    OPENCLAW_SUSPENDED = "openclaw.suspended"                     # Kill switch activated
    OPENCLAW_REINSTATED = "openclaw.reinstated"                   # Kill switch cleared


# REM: v6.3.0CC Enhancement — HIPAA 45 CFR 164.312(a)(2)(i) Unique User Identification
class ActorType(str, Enum):
    """REM: Distinguishes human operators from AI agents in audit records."""
    HUMAN = "human"
    AI_AGENT = "ai_agent"
    SYSTEM = "system"
    SERVICE_ACCOUNT = "service_account"
    EMERGENCY = "emergency"  # Break-the-glass access


class AuditLogger:
    """
    REM: Centralized audit logger. All auditable events flow through here.
    REM: Outputs JSON-formatted logs for machine parsing and compliance tools.
    REM: v4.3.0CC: Now includes cryptographic hash chaining for tamper evidence.
    """

    def __init__(self):
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)

        # REM: Hash chain state
        self._chain_state = ChainState(
            chain_id=hashlib.sha256(
                f"telsonbase_{datetime.now(timezone.utc).isoformat()}".encode()
            ).hexdigest()[:16],
            created_at=datetime.now(timezone.utc).isoformat()
        )
        self._chain_entries: List[AuditChainEntry] = []
        self._chain_enabled = True

        # REM: Prevent duplicate handlers if logger already configured
        if not self.logger.handlers:
            # REM: Console handler for container logs
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)

            # REM: JSON formatter for structured logging
            formatter = _SafeJsonFormatter(
                fmt="%(asctime)s %(levelname)s %(event_type)s %(message)s"
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

            # REM: File handler for persistent audit trail
            try:
                file_handler = logging.FileHandler(settings.audit_log_path)
                file_handler.setLevel(logging.INFO)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except (OSError, IOError) as e:
                # REM: Log to console only if file unavailable
                self.logger.warning(f"REM: Audit file logging unavailable: {e}")

        # REM: Try to load chain state from persistence
        self._load_chain_state()
        self._load_chain_entries()

    def _load_chain_state(self):
        """REM: Load chain state from Redis persistence if available."""
        try:
            from core.persistence import get_redis
            redis = get_redis()
            if redis:
                state_json = redis.get("audit:chain:state")
                if state_json:
                    state_data = json.loads(state_json)
                    self._chain_state = ChainState(
                        last_sequence=state_data.get("last_sequence", 0),
                        last_hash=state_data.get("last_hash", GENESIS_HASH),
                        chain_id=state_data.get("chain_id", self._chain_state.chain_id),
                        created_at=state_data.get("created_at", self._chain_state.created_at),
                        entries_count=state_data.get("entries_count", 0)
                    )
                    self.logger.debug(
                        f"REM: Loaded audit chain state - sequence {self._chain_state.last_sequence}_Thank_You"
                    )
        except Exception as e:
            self.logger.warning(f"REM: Could not load chain state from Redis: {e}")

    def _save_chain_state(self):
        """REM: Save chain state to Redis persistence."""
        try:
            from core.persistence import get_redis
            redis = get_redis()
            if redis:
                state_data = {
                    "last_sequence": self._chain_state.last_sequence,
                    "last_hash": self._chain_state.last_hash,
                    "chain_id": self._chain_state.chain_id,
                    "created_at": self._chain_state.created_at,
                    "entries_count": self._chain_state.entries_count
                }
                redis.set("audit:chain:state", json.dumps(state_data))
        except Exception:
            pass  # REM: Non-critical, in-memory state still works

    def _create_chain_entry(
        self,
        event_type: str,
        message: str,
        actor: str,
        resource: Optional[str],
        details: Dict[str, Any],
        actor_type: str = "system"
    ) -> AuditChainEntry:
        """REM: Create a new chain entry with hash linking.
        REM: Uses Redis WATCH/MULTI/EXEC (optimistic locking) for atomic read-compute-write.
        REM:
        REM: Why not a Lua script? SHA-256 must run in Python — Redis Lua has no crypto.
        REM: WATCH/MULTI/EXEC gives the same atomicity guarantee:
        REM:   1. WATCH audit:chain:state — Redis will track any concurrent write
        REM:   2. GET current state (seq + last_hash) in immediate mode
        REM:   3. Python builds the entry and computes SHA-256
        REM:   4. MULTI → SET new state + ZADD entry → EXEC
        REM:      If another process wrote between WATCH and EXEC, EXEC raises WatchError
        REM:      and we retry from step 1 with fresh state. No stale data ever committed.
        REM:
        REM: Redis is the single source of truth. In-memory _chain_state is a read cache
        REM: only — it is NEVER trusted for seq/hash during a write.
        REM: Safe for any number of processes or workers.
        """
        import time

        try:
            from core.persistence import get_redis
            r = get_redis()
        except Exception:
            r = None

        if r:
            max_retries = 20
            for attempt in range(max_retries):
                try:
                    with r.pipeline() as pipe:
                        # REM: WATCH — if audit:chain:state is modified before EXEC,
                        # REM: the transaction is aborted and we retry with fresh state.
                        pipe.watch("audit:chain:state")

                        # REM: Read in immediate-execution mode (after WATCH, before MULTI)
                        state_json = pipe.get("audit:chain:state")
                        if state_json:
                            state_data = json.loads(state_json)
                        else:
                            state_data = {
                                "last_sequence": 0,
                                "last_hash": GENESIS_HASH,
                                "chain_id": self._chain_state.chain_id,
                                "created_at": self._chain_state.created_at,
                                "entries_count": 0,
                            }

                        new_seq = state_data["last_sequence"] + 1
                        prev_hash = state_data.get("last_hash", GENESIS_HASH)

                        # REM: Build entry and compute SHA-256 in Python
                        entry = AuditChainEntry(
                            sequence=new_seq,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            event_type=event_type,
                            message=message,
                            actor=actor,
                            actor_type=actor_type,
                            resource=resource,
                            details=details or {},
                            previous_hash=prev_hash,
                        )
                        entry.entry_hash = entry.compute_hash()

                        new_state = {
                            "last_sequence": new_seq,
                            "last_hash": entry.entry_hash,
                            "chain_id": state_data.get("chain_id", self._chain_state.chain_id),
                            "created_at": state_data.get("created_at", self._chain_state.created_at),
                            "entries_count": state_data.get("entries_count", 0) + 1,
                        }

                        # REM: MULTI starts the transaction buffer.
                        # REM: All commands below are queued — nothing executes until EXEC.
                        pipe.multi()
                        pipe.set("audit:chain:state", json.dumps(new_state))
                        pipe.zadd(
                            "audit:chain:entries",
                            {json.dumps(entry.to_dict(), default=str): new_seq},
                        )
                        # REM: Trim oldest entries to stay within configured max.
                        # REM: ZREMRANGEBYRANK 0 -(max+1) keeps the newest max_entries.
                        pipe.zremrangebyrank(
                            "audit:chain:entries",
                            0,
                            -(settings.audit_max_redis_entries + 1),
                        )
                        # REM: EXEC — atomic commit. WatchError if state changed since WATCH.
                        pipe.execute()

                    # REM: Sync in-memory cache to reflect committed state
                    self._chain_state.last_sequence = new_seq
                    self._chain_state.last_hash = entry.entry_hash
                    self._chain_state.entries_count = new_state["entries_count"]

                    self._chain_entries.append(entry)
                    if len(self._chain_entries) > 1000:
                        self._chain_entries = self._chain_entries[-1000:]

                    return entry

                except Exception as e:
                    # REM: WatchError = concurrent write detected — retry with fresh state
                    if "WatchError" in type(e).__name__:
                        time.sleep(0.001 * (attempt + 1))  # brief backoff before retry
                        continue
                    self.logger.warning(
                        f"REM: Chain write attempt {attempt + 1} failed: {e}"
                    )
                    time.sleep(0.005)

            self.logger.error(
                "REM: All Redis chain write attempts exhausted — falling back to in-memory only"
            )

        # REM: No Redis, or all retries exhausted — in-memory only fallback
        self._chain_state.last_sequence += 1
        self._chain_state.entries_count += 1

        entry = AuditChainEntry(
            sequence=self._chain_state.last_sequence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            message=message,
            actor=actor,
            actor_type=actor_type,
            resource=resource,
            details=details or {},
            previous_hash=self._chain_state.last_hash,
        )
        entry.entry_hash = entry.compute_hash()
        self._chain_state.last_hash = entry.entry_hash

        self._chain_entries.append(entry)
        if len(self._chain_entries) > 1000:
            self._chain_entries = self._chain_entries[-1000:]

        return entry

    def _load_chain_entries(self):
        """REM: Load chain entries from Redis on startup for verification. v6.3.0CC"""
        try:
            from core.persistence import get_redis
            r = get_redis()
            if r and r.exists("audit:chain:entries"):
                entries_raw = r.zrange("audit:chain:entries", 0, -1)
                loaded = []
                for entry_json in entries_raw:
                    entry_data = json.loads(entry_json)
                    entry = AuditChainEntry(
                        sequence=entry_data["sequence"],
                        timestamp=entry_data["timestamp"],
                        event_type=entry_data["event_type"],
                        message=entry_data["message"],
                        actor=entry_data["actor"],
                        actor_type=entry_data.get("actor_type", "system"),
                        resource=entry_data.get("resource"),
                        details=entry_data.get("details", {}),
                        previous_hash=entry_data["previous_hash"],
                        entry_hash=entry_data.get("entry_hash", ""),
                    )
                    loaded.append(entry)
                # REM: v7.4.0CC — Verify loaded entries are consistent with saved chain state.
                # If the chain tip (last_hash) doesn't match the last loaded entry, the
                # entries and state are from different sessions. Discard to prevent
                # chain_break at the session boundary during verify_chain().
                if loaded:
                    last_loaded_hash = loaded[-1].entry_hash
                    if last_loaded_hash != self._chain_state.last_hash:
                        self.logger.warning(
                            "REM: Audit chain entries inconsistent with saved state — "
                            "discarding stale entries to preserve chain continuity_Excuse_Me"
                        )
                        loaded = []
                self._chain_entries.extend(loaded)
                if self._chain_entries:
                    self.logger.info(
                        f"REM: Loaded {len(self._chain_entries)} audit chain entries from Redis_Thank_You"
                    )
        except Exception as e:
            self.logger.warning(f"REM: Could not load chain entries from Redis: {e}_Excuse_Me")

    def log(
        self,
        event_type: AuditEventType,
        message: str,
        actor: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        qms_status: Optional[str] = None,
        actor_type: str = "system"
    ):
        """
        REM: Record an audit event with cryptographic hash chaining.

        Args:
            event_type: Category of the event (from AuditEventType enum)
            message: Human-readable description of the event
            actor: Who/what initiated the action (API key ID, agent name, system)
            resource: What was acted upon (task ID, file path, external URL)
            details: Additional structured data about the event
            qms_status: Optional QMS suffix (_Please, _Thank_You, _Thank_You_But_No)
            actor_type: Type of actor (human, ai_agent, system, service_account, emergency)
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        actor_value = actor or "system"

        # REM: Apply QMS suffix to message if provided
        final_message = f"{message}_{qms_status}" if qms_status else message

        # REM: Create chain entry for tamper evidence
        chain_entry = None
        if self._chain_enabled:
            chain_entry = self._create_chain_entry(
                event_type=event_type.value,
                message=final_message,
                actor=actor_value,
                resource=resource,
                details=details or {},
                actor_type=actor_type
            )

        # REM: Build the audit record with chain info
        record = {
            "timestamp": timestamp,
            "event_type": event_type.value,
            "message": final_message,
            "actor": actor_value,
            "resource": resource,
            "details": details or {},
        }

        # REM: Add chain verification data
        if chain_entry:
            record["chain"] = {
                "sequence": chain_entry.sequence,
                "entry_hash": chain_entry.entry_hash,
                "previous_hash": chain_entry.previous_hash,
                "chain_id": self._chain_state.chain_id
            }

        if qms_status:
            record["qms_status"] = qms_status

        self.logger.info(
            json.dumps(record),
            extra={
                "event_type": event_type.value,
                "actor": actor,
                "resource": resource
            }
        )
    
    # REM: --- Convenience methods for common event types ---
    
    def auth_success(self, actor: str, details: Optional[Dict] = None):
        """REM: Log successful authentication."""
        self.log(
            AuditEventType.AUTH_SUCCESS,
            f"Authentication successful for ::{actor}::",
            actor=actor,
            details=details,
            qms_status="Thank_You"
        )
    
    def auth_failure(self, actor: str, reason: str):
        """REM: Log failed authentication attempt."""
        self.log(
            AuditEventType.AUTH_FAILURE,
            f"Authentication failed for ::{actor}:: - Reason: ::{reason}::",
            actor=actor,
            details={"reason": reason},
            qms_status="Thank_You_But_No"
        )
    
    def task_dispatched(self, task_name: str, task_id: str, actor: str, args: Any = None):
        """REM: Log task dispatch."""
        self.log(
            AuditEventType.TASK_DISPATCHED,
            f"Task ::{task_name}:: dispatched with ID ::{task_id}::",
            actor=actor,
            resource=task_id,
            details={"task_name": task_name, "args": str(args)[:500]},  # Truncate large args
            qms_status="Please"
        )
    
    def task_completed(self, task_name: str, task_id: str, result_summary: str = ""):
        """REM: Log task completion."""
        self.log(
            AuditEventType.TASK_COMPLETED,
            f"Task ::{task_name}:: completed - ID ::{task_id}::",
            resource=task_id,
            details={"task_name": task_name, "result_summary": result_summary[:500]},
            qms_status="Thank_You"
        )
    
    def task_failed(self, task_name: str, task_id: str, error: str):
        """REM: Log task failure."""
        self.log(
            AuditEventType.TASK_FAILED,
            f"Task ::{task_name}:: failed - ID ::{task_id}:: - Error: ::{error}::",
            resource=task_id,
            details={"task_name": task_name, "error": error},
            qms_status="Thank_You_But_No"
        )
    
    def external_request(self, url: str, actor: str, method: str = "GET"):
        """REM: Log outbound external API request."""
        self.log(
            AuditEventType.EXTERNAL_REQUEST,
            f"External request to ::{url}:: via ::{method}::",
            actor=actor,
            resource=url,
            details={"method": method},
            qms_status="Please"
        )
    
    def external_blocked(self, url: str, actor: str, reason: str):
        """REM: Log blocked external request (not on whitelist)."""
        self.log(
            AuditEventType.EXTERNAL_BLOCKED,
            f"External request BLOCKED to ::{url}:: - Reason: ::{reason}::",
            actor=actor,
            resource=url,
            details={"reason": reason},
            qms_status="Thank_You_But_No"
        )

    # REM: --- Chain Verification Methods (v4.3.0CC) ---

    def verify_chain(self, entries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        REM: Verify the integrity of the audit chain.

        Args:
            entries: Optional list of entries to verify. If None, uses in-memory entries.

        Returns:
            Dict with verification result, any breaks found, and chain stats
        """
        if entries is None:
            entries_to_check = [e.to_dict() for e in self._chain_entries]
        else:
            entries_to_check = entries

        if not entries_to_check:
            return {
                "valid": True,
                "message": "No entries to verify",
                "entries_checked": 0
            }

        breaks = []
        for i, entry_data in enumerate(entries_to_check):
            entry = AuditChainEntry(
                sequence=entry_data["sequence"],
                timestamp=entry_data["timestamp"],
                event_type=entry_data["event_type"],
                message=entry_data["message"],
                actor=entry_data["actor"],
                actor_type=entry_data.get("actor_type", "system"),
                resource=entry_data.get("resource"),
                details=entry_data.get("details", {}),
                previous_hash=entry_data["previous_hash"],
                entry_hash=entry_data["entry_hash"]
            )

            # REM: Verify this entry's hash
            computed_hash = entry.compute_hash()
            if computed_hash != entry.entry_hash:
                breaks.append({
                    "sequence": entry.sequence,
                    "issue": "hash_mismatch",
                    "expected": entry.entry_hash,
                    "computed": computed_hash
                })
                continue

            # REM: Verify chain link (except first entry)
            if i > 0:
                prev_entry = entries_to_check[i - 1]
                if entry.previous_hash != prev_entry["entry_hash"]:
                    breaks.append({
                        "sequence": entry.sequence,
                        "issue": "chain_break",
                        "expected_previous": prev_entry["entry_hash"],
                        "actual_previous": entry.previous_hash
                    })

        return {
            "valid": len(breaks) == 0,
            "entries_checked": len(entries_to_check),
            "breaks": breaks,
            "chain_id": self._chain_state.chain_id,
            "first_sequence": entries_to_check[0]["sequence"] if entries_to_check else None,
            "last_sequence": entries_to_check[-1]["sequence"] if entries_to_check else None,
            "message": "Chain verified successfully" if not breaks else f"Found {len(breaks)} break(s)"
        }

    def get_chain_state(self) -> Dict[str, Any]:
        """REM: Get current chain state for monitoring."""
        return {
            "chain_id": self._chain_state.chain_id,
            "last_sequence": self._chain_state.last_sequence,
            "last_hash": self._chain_state.last_hash,
            "created_at": self._chain_state.created_at,
            "entries_count": self._chain_state.entries_count,
            "in_memory_entries": len(self._chain_entries)
        }

    def get_recent_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """REM: Get recent chain entries for verification or export."""
        return [e.to_dict() for e in self._chain_entries[-limit:]]

    def export_chain_for_compliance(self, start_sequence: int = 0, end_sequence: Optional[int] = None) -> Dict[str, Any]:
        """
        REM: Export chain data for compliance audit.

        Returns:
            Dict with chain metadata and entries suitable for compliance reporting
        """
        entries = self._chain_entries
        if start_sequence > 0:
            entries = [e for e in entries if e.sequence >= start_sequence]
        if end_sequence:
            entries = [e for e in entries if e.sequence <= end_sequence]

        verification = self.verify_chain([e.to_dict() for e in entries])

        return {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "chain_id": self._chain_state.chain_id,
            "chain_created_at": self._chain_state.created_at,
            "total_entries": self._chain_state.entries_count,
            "exported_entries": len(entries),
            "verification": verification,
            "entries": [e.to_dict() for e in entries]
        }


# REM: Singleton instance for import throughout the application
audit = AuditLogger()
