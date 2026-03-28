# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# ClawFilters/core/openclaw.py
# REM: =======================================================================================
# REM: OPENCLAW GOVERNANCE ENGINE — "CONTROL YOUR CLAW"
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v7.4.0CC: OpenClaw governance integration — trust-level action enforcement
#
# REM: Mission Statement: OpenClaw is the autonomous AI agent with 180K+ GitHub stars
# REM: and zero mandatory HITL. ClawFilters is the leash. This module intercepts every
# REM: action OpenClaw wants to take and evaluates it against the governance pipeline:
# REM:
# REM:   1. Is this claw registered? (reject if not)
# REM:   2. Is this claw suspended? (kill switch — reject immediately)
# REM:   3. What trust level? (QUARANTINE → PROBATION → RESIDENT → CITIZEN)
# REM:   4. Does the trust level permit this action autonomously?
# REM:   5. Manners compliance check (auto-demote if score < threshold)
# REM:   6. Anomaly detection check (flag deviations)
# REM:   7. Egress whitelist check (block unauthorized external calls)
# REM:   8. If approval required → pause and wait for human
# REM:   9. Audit every decision to cryptographic chain
# REM:
# REM: Architecture: ClawFilters acts as a governed MCP proxy. OpenClaw itself is NEVER
# REM: modified — ClawFilters wraps it. The claw doesn't know it's on a leash.
# REM:
# REM: Integration guide: docs/Operation Documents/OPENCLAW_INTEGRATION_GUIDE.md
# REM: Full start-to-finish walkthrough: install, register, govern, trust journey (45 min).
# REM:
# REM: The Trust Level Model (the "secret sauce"):
# REM:   QUARANTINE — ALL actions require approval, read-only only
# REM:   PROBATION  — External actions require approval, internal tools allowed
# REM:   RESIDENT   — High-risk actions require approval
# REM:   CITIZEN    — Autonomous, anomaly-flagged actions still gate
# REM: =======================================================================================

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from core.audit import AuditEventType, audit
from core.config import get_settings

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: TRUST LEVELS — THE SECRET SAUCE
# REM: =======================================================================================

class TrustLevel(str, Enum):
    """
    REM: The five trust levels for governed OpenClaw instances.
    REM: Every claw starts at QUARANTINE. Trust is earned, not given.
    REM: AGENT is the final earned tier — full delegation, anomaly-advisory only.
    """
    QUARANTINE = "quarantine"   # Full HITL — all actions require approval
    PROBATION = "probation"     # External gated, internal read allowed
    RESIDENT = "resident"       # High-risk gated, most actions autonomous
    CITIZEN = "citizen"         # Autonomous — only anomaly-flagged actions gate
    AGENT = "agent"             # Full earned autonomy — anomalies advisory only, pre-authorized profile

# REM: Valid trust level transitions (prevent jumps — one step at a time)
VALID_PROMOTIONS = {
    TrustLevel.QUARANTINE: [TrustLevel.PROBATION],
    TrustLevel.PROBATION: [TrustLevel.RESIDENT],
    TrustLevel.RESIDENT: [TrustLevel.CITIZEN],
    TrustLevel.CITIZEN: [TrustLevel.AGENT],
    TrustLevel.AGENT: [],
}
# REM: Demotions can go to any lower level (instant consequences)
VALID_DEMOTIONS = {
    TrustLevel.AGENT: [TrustLevel.CITIZEN, TrustLevel.RESIDENT, TrustLevel.PROBATION, TrustLevel.QUARANTINE],
    TrustLevel.CITIZEN: [TrustLevel.RESIDENT, TrustLevel.PROBATION, TrustLevel.QUARANTINE],
    TrustLevel.RESIDENT: [TrustLevel.PROBATION, TrustLevel.QUARANTINE],
    TrustLevel.PROBATION: [TrustLevel.QUARANTINE],
    TrustLevel.QUARANTINE: [],
}


# REM: =======================================================================================
# REM: ACTION CLASSIFICATION
# REM: =======================================================================================

class ActionCategory(str, Enum):
    """REM: How we classify incoming OpenClaw actions for governance decisions."""
    READ_INTERNAL = "read_internal"           # Read local data
    WRITE_INTERNAL = "write_internal"         # Write local data
    DELETE = "delete"                         # Destructive action
    EXTERNAL_REQUEST = "external_request"     # Outbound network call
    FINANCIAL = "financial"                   # Money or value transfer
    SYSTEM_CONFIG = "system_config"           # System configuration change
    # REM: M17 fix — communication channels (Slack/WhatsApp/Discord/SMS/Teams) have higher
    # REM: data-sensitivity than generic outbound requests: they reach real humans, can
    # REM: spread misinformation at scale, and are irreversible. Kept gated at all tiers.
    COMMUNICATION = "communication"           # Outbound message to humans via comms channel

# REM: Map tool names to action categories
TOOL_CATEGORY_MAP: Dict[str, ActionCategory] = {
    # Read operations (canonical + common aliases)
    "file_read": ActionCategory.READ_INTERNAL,
    "read_file": ActionCategory.READ_INTERNAL,
    "read_files": ActionCategory.READ_INTERNAL,
    "database_query": ActionCategory.READ_INTERNAL,
    "list_files": ActionCategory.READ_INTERNAL,
    "list_directory": ActionCategory.READ_INTERNAL,
    "search": ActionCategory.READ_INTERNAL,
    "search_files": ActionCategory.READ_INTERNAL,
    "calendar_read": ActionCategory.READ_INTERNAL,
    "email_read": ActionCategory.READ_INTERNAL,
    # Write operations (canonical + common aliases)
    "file_write": ActionCategory.WRITE_INTERNAL,
    "write_file": ActionCategory.WRITE_INTERNAL,
    "edit_file": ActionCategory.WRITE_INTERNAL,
    "database_insert": ActionCategory.WRITE_INTERNAL,
    "database_update": ActionCategory.WRITE_INTERNAL,
    "email_send": ActionCategory.EXTERNAL_REQUEST,
    "calendar_create": ActionCategory.WRITE_INTERNAL,
    "calendar_update": ActionCategory.WRITE_INTERNAL,
    # Delete operations
    "file_delete": ActionCategory.DELETE,
    "database_delete": ActionCategory.DELETE,
    "calendar_delete": ActionCategory.DELETE,
    # External operations
    "http_request": ActionCategory.EXTERNAL_REQUEST,
    "api_call": ActionCategory.EXTERNAL_REQUEST,
    "webhook_send": ActionCategory.EXTERNAL_REQUEST,
    # Communication channel tools — elevated governance, gated at ALL trust tiers
    "slack_send": ActionCategory.COMMUNICATION,
    "slack_post": ActionCategory.COMMUNICATION,
    "slack_dm": ActionCategory.COMMUNICATION,
    "slack_channel_post": ActionCategory.COMMUNICATION,
    "whatsapp_send": ActionCategory.COMMUNICATION,
    "whatsapp_dm": ActionCategory.COMMUNICATION,
    "whatsapp_broadcast": ActionCategory.COMMUNICATION,
    "whatsapp_group_send": ActionCategory.COMMUNICATION,
    "discord_send": ActionCategory.COMMUNICATION,
    "discord_post": ActionCategory.COMMUNICATION,
    "teams_send": ActionCategory.COMMUNICATION,
    "teams_post": ActionCategory.COMMUNICATION,
    "sms_send": ActionCategory.COMMUNICATION,
    "twilio_send": ActionCategory.COMMUNICATION,
    # Financial
    "payment_send": ActionCategory.FINANCIAL,
    "invoice_create": ActionCategory.FINANCIAL,
    "transaction_execute": ActionCategory.FINANCIAL,
    # System
    "config_update": ActionCategory.SYSTEM_CONFIG,
    "service_restart": ActionCategory.SYSTEM_CONFIG,
}

# REM: Trust level → which action categories are autonomous / gated / blocked
TRUST_PERMISSION_MATRIX: Dict[TrustLevel, Dict[str, List[ActionCategory]]] = {
    TrustLevel.QUARANTINE: {
        "autonomous": [],
        "gated": [ActionCategory.READ_INTERNAL],
        "blocked": [
            ActionCategory.WRITE_INTERNAL, ActionCategory.DELETE,
            ActionCategory.EXTERNAL_REQUEST, ActionCategory.FINANCIAL,
            ActionCategory.SYSTEM_CONFIG, ActionCategory.COMMUNICATION,
        ],
    },
    TrustLevel.PROBATION: {
        "autonomous": [ActionCategory.READ_INTERNAL],
        "gated": [ActionCategory.WRITE_INTERNAL, ActionCategory.EXTERNAL_REQUEST],
        "blocked": [
            ActionCategory.DELETE, ActionCategory.FINANCIAL,
            ActionCategory.SYSTEM_CONFIG, ActionCategory.COMMUNICATION,
        ],
    },
    TrustLevel.RESIDENT: {
        "autonomous": [
            ActionCategory.READ_INTERNAL, ActionCategory.WRITE_INTERNAL,
        ],
        "gated": [
            ActionCategory.DELETE, ActionCategory.EXTERNAL_REQUEST,
            ActionCategory.FINANCIAL, ActionCategory.SYSTEM_CONFIG,
            ActionCategory.COMMUNICATION,
        ],
        "blocked": [],
    },
    TrustLevel.CITIZEN: {
        "autonomous": [
            ActionCategory.READ_INTERNAL, ActionCategory.WRITE_INTERNAL,
            ActionCategory.DELETE, ActionCategory.EXTERNAL_REQUEST,
            ActionCategory.FINANCIAL, ActionCategory.SYSTEM_CONFIG,
        ],
        # REM: COMMUNICATION stays gated even for CITIZEN — agents must have explicit
        # REM: approval to send messages to real humans on comms channels at any trust tier.
        "gated": [ActionCategory.COMMUNICATION],
        "blocked": [],
    },
    TrustLevel.AGENT: {
        "autonomous": [
            ActionCategory.READ_INTERNAL, ActionCategory.WRITE_INTERNAL,
            ActionCategory.DELETE, ActionCategory.EXTERNAL_REQUEST,
            ActionCategory.FINANCIAL, ActionCategory.SYSTEM_CONFIG,
        ],
        # REM: COMMUNICATION stays gated even at apex — human outreach always requires approval.
        "gated": [ActionCategory.COMMUNICATION],
        "blocked": [],
    },
}


# REM: =======================================================================================
# REM: DATA MODELS
# REM: =======================================================================================

class OpenClawInstance(BaseModel):
    """
    REM: A registered OpenClaw instance under ClawFilters governance.
    REM: Starts at QUARANTINE. Trust must be earned.
    """
    instance_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    trust_level: str = TrustLevel.QUARANTINE.value
    api_key_hash: str = ""                              # SHA-256 of the claw's API key
    allowed_tools: List[str] = Field(default_factory=list)   # Explicit tool whitelist (empty = all registered)
    blocked_tools: List[str] = Field(default_factory=list)   # Explicit tool blacklist
    manners_score: float = 1.0                             # Manners compliance score (0.0-1.0)
    action_count: int = 0                               # Total actions evaluated
    actions_allowed: int = 0                             # Actions that were allowed
    actions_blocked: int = 0                             # Actions that were blocked
    actions_gated: int = 0                               # Actions sent to approval queue
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_action_at: Optional[datetime] = None
    suspended: bool = False                             # Kill switch
    suspended_by: Optional[str] = None
    suspended_at: Optional[datetime] = None
    suspended_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class OpenClawActionRequest(BaseModel):
    """REM: An action request from an OpenClaw instance to be evaluated."""
    instance_id: str
    tool_name: str
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    nonce: str = Field(default_factory=lambda: uuid.uuid4().hex)


class OpenClawActionResult(BaseModel):
    """REM: The governance decision for an OpenClaw action."""
    allowed: bool = False
    reason: str = ""
    action_category: str = ""
    trust_level_at_decision: str = ""
    approval_required: bool = False
    approval_id: Optional[str] = None
    audit_entry_id: Optional[str] = None
    manners_score_at_decision: float = 1.0
    anomaly_flagged: bool = False


class TrustChangeRecord(BaseModel):
    """REM: A record of a trust level change for audit trail."""
    instance_id: str
    old_level: str
    new_level: str
    changed_by: str
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    change_type: str = ""  # "promotion", "demotion", "auto_demotion"

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# REM: =======================================================================================
# REM: OPENCLAW MANAGER (SINGLETON)
# REM: =======================================================================================

class OpenClawManager:
    """
    REM: v7.4.0CC — Singleton manager for OpenClaw governance.
    REM: Follows the singleton pattern from core/identiclaw.py.
    REM:
    REM: Responsibilities:
    REM:   1. Instance registration and lifecycle management
    REM:   2. Action governance pipeline (trust → Manners → anomaly → egress → approve)
    REM:   3. Trust level promotion/demotion
    REM:   4. Kill switch (suspend/reinstate)
    REM:   5. Redis-backed state persistence
    REM:   6. Action logging for anomaly detection
    """

    def __init__(self):
        self._instances: Dict[str, OpenClawInstance] = {}
        self._suspended_ids: Set[str] = set()
        self._trust_history: Dict[str, List[TrustChangeRecord]] = {}
        self._initialized = False

    # REM: ==========================================
    # REM: INITIALIZATION
    # REM: ==========================================

    def startup_check(self):
        """REM: Called during app lifespan when OPENCLAW_ENABLED=true."""
        self._load_from_persistence()
        self._initialized = True
        logger.info(
            f"REM: OpenClaw governance engine initialized — "
            f"{len(self._instances)} instances cached, "
            f"{len(self._suspended_ids)} suspended_Thank_You"
        )

    def _get_redis(self):
        """REM: Lazy Redis client to avoid circular imports."""
        try:
            import redis
            settings = get_settings()
            return redis.Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            return None

    def _load_from_persistence(self):
        """REM: Load cached instances and suspensions from Redis on startup."""
        client = self._get_redis()
        if not client:
            return

        try:
            # REM: Load suspended instance IDs
            suspended_keys = client.keys("openclaw:suspended:*")
            for key in suspended_keys:
                instance_id = key.replace("openclaw:suspended:", "")
                self._suspended_ids.add(instance_id)

            # REM: Load instance records
            instance_keys = client.keys("openclaw:instance:*")
            for key in instance_keys:
                data = client.get(key)
                if data:
                    try:
                        instance = OpenClawInstance.model_validate_json(data)
                        self._instances[instance.instance_id] = instance
                    except Exception as e:
                        logger.warning(f"REM: Failed to load OpenClaw instance from {key}: {e}")

            # REM: Load trust history
            history_keys = client.keys("openclaw:trust_history:*")
            for key in history_keys:
                instance_id = key.replace("openclaw:trust_history:", "")
                data = client.get(key)
                if data:
                    try:
                        records = json.loads(data)
                        self._trust_history[instance_id] = [
                            TrustChangeRecord.model_validate(r) for r in records
                        ]
                    except Exception as e:
                        logger.warning(f"REM: Failed to load trust history from {key}: {e}")

            logger.info(
                f"REM: Loaded from Redis — {len(self._instances)} instances, "
                f"{len(self._suspended_ids)} suspended_Thank_You"
            )
        except Exception as e:
            logger.warning(f"REM: Failed to load OpenClaw state from Redis: {e}_Excuse_Me")

    # REM: ==========================================
    # REM: INSTANCE REGISTRATION
    # REM: ==========================================

    def register_instance(
        self,
        name: str,
        api_key: str,
        allowed_tools: List[str] = None,
        blocked_tools: List[str] = None,
        registered_by: str = "system",
        metadata: Dict[str, Any] = None,
    ) -> Optional[OpenClawInstance]:
        """
        REM: Register a new OpenClaw instance under ClawFilters governance.
        REM: Always starts at QUARANTINE. Trust must be earned.
        """
        settings = get_settings()

        # REM: Enforce max instances
        active_count = sum(1 for i in self._instances.values() if not i.suspended)
        if active_count >= settings.openclaw_max_instances:
            logger.warning(
                f"REM: Max OpenClaw instances reached ({settings.openclaw_max_instances})"
                f"_Thank_You_But_No"
            )
            return None

        # REM: Hash the API key (never store plaintext)
        api_key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

        # REM: Check for duplicate registration (same API key hash)
        for existing in self._instances.values():
            if existing.api_key_hash == api_key_hash and not existing.suspended:
                logger.info(f"REM: OpenClaw instance already registered with this API key_Thank_You")
                return existing

        instance = OpenClawInstance(
            name=name,
            trust_level=settings.openclaw_default_trust_level,
            api_key_hash=api_key_hash,
            allowed_tools=allowed_tools or [],
            blocked_tools=blocked_tools or [],
            metadata=metadata or {},
        )

        self._instances[instance.instance_id] = instance
        self._persist_instance(instance)

        # REM: Initialize trust history
        self._trust_history[instance.instance_id] = [
            TrustChangeRecord(
                instance_id=instance.instance_id,
                old_level="unregistered",
                new_level=settings.openclaw_default_trust_level,
                changed_by=registered_by,
                reason="Initial registration",
                change_type="registration",
            )
        ]
        self._persist_trust_history(instance.instance_id)

        # REM: Audit trail
        audit.log(
            AuditEventType.OPENCLAW_REGISTERED,
            f"OpenClaw instance registered: ::{name}:: ({instance.instance_id})",
            actor=registered_by,
            details={
                "instance_id": instance.instance_id,
                "name": name,
                "trust_level": settings.openclaw_default_trust_level,
                "allowed_tools": allowed_tools or [],
                "blocked_tools": blocked_tools or [],
            },
            qms_status="Thank_You"
        )

        logger.info(
            f"REM: OpenClaw instance registered ::{name}:: "
            f"at {settings.openclaw_default_trust_level}_Thank_You"
        )
        return instance

    def _persist_instance(self, instance: OpenClawInstance):
        """REM: Persist instance record to Redis and local cache.
        REM: Local cache write is always performed — Redis write is best-effort.
        REM: This ensures mutations (promote, demote, suspend, reinstate) survive
        REM: the pop-then-read cycle in test environments where Redis is unavailable.
        REM: In production (Redis healthy), Redis is the cross-worker authority;
        REM: local cache is evicted at the start of each governance evaluation.
        """
        # REM: Always update local cache so the instance survives in no-Redis environments.
        self._instances[instance.instance_id] = instance
        client = self._get_redis()
        if not client:
            return
        try:
            client.set(
                f"openclaw:instance:{instance.instance_id}",
                instance.model_dump_json()
            )
        except Exception as e:
            logger.warning(f"REM: Failed to persist OpenClaw instance: {e}")

    def _persist_trust_history(self, instance_id: str):
        """REM: Persist trust change history to Redis."""
        client = self._get_redis()
        if not client:
            return
        try:
            history = self._trust_history.get(instance_id, [])
            data = json.dumps([r.model_dump(mode="json") for r in history])
            client.set(f"openclaw:trust_history:{instance_id}", data)
        except Exception as e:
            logger.warning(f"REM: Failed to persist trust history: {e}")

    # REM: ==========================================
    # REM: THE GOVERNANCE PIPELINE
    # REM: ==========================================

    def evaluate_action(
        self,
        instance_id: str,
        tool_name: str,
        tool_args: Dict[str, Any] = None,
        nonce: str = None,
    ) -> OpenClawActionResult:
        """
        REM: The core governance pipeline. Every OpenClaw action passes through here.
        REM:
        REM: Steps:
        REM:   1. Instance exists? → reject if unregistered
        REM:   2. Kill switch? → reject if suspended
        REM:   3. Nonce replay? → reject if seen before
        REM:   4. Tool blocked? → reject if on blocklist
        REM:   5. Classify action category
        REM:   6. Manners compliance check → auto-demote if below threshold
        REM:   7. Check trust level permissions
        REM:   8. Anomaly detection check
        REM:   9. Log and return decision
        """
        tool_args = tool_args or {}
        nonce = nonce or uuid.uuid4().hex

        # REM: Step 1 — Instance exists? Force Redis refresh before governance evaluation.
        # REM: Trust level, suspension status, or blocklist may have changed on another Gunicorn
        # REM: worker since this worker last cached the instance. Governance decisions (allow/gate/block)
        # REM: MUST be authoritative — evict stale in-memory copy so get_instance() re-reads Redis.
        # REM: v9.0.0B — multi-worker fix: same pattern applied to get_tenant() in TenantManager.
        # REM: v9.5.0B — local_fallback preserves in-memory instance when Redis is unavailable
        # REM: (test environments, Redis outage). Redis-authoritative path is unchanged when Redis is up.
        local_fallback = self._instances.pop(instance_id, None)
        instance = self.get_instance(instance_id)
        # REM: If Redis is unavailable (test env, outage), get_instance returns None even though
        # REM: the instance exists in local cache. Restore from local_fallback.
        # REM: In production with Redis healthy, get_instance always finds the instance in Redis
        # REM: after the pop — local_fallback never activates there.
        if instance is None and local_fallback is not None:
            instance = local_fallback
            # REM: Redis unavailable — restore to _instances immediately.
            # REM: Early-exit paths (kill switch, nonce replay) return without calling _persist_instance,
            # REM: which would otherwise be the write-back. Without this, the instance is lost after
            # REM: any early-exit and subsequent operations (reinstate, etc.) cannot find it.
            # REM: In production (Redis healthy), get_instance() already restored _instances above;
            # REM: this line only activates in the no-Redis path.
            self._instances[instance_id] = instance
        if not instance:
            audit.log(
                AuditEventType.OPENCLAW_ACTION_BLOCKED,
                f"Unregistered OpenClaw instance: {instance_id}",
                actor=f"openclaw:{instance_id}",
                details={"tool": tool_name, "reason": "unregistered"},
                qms_status="Thank_You_But_No"
            )
            return OpenClawActionResult(
                allowed=False,
                reason="Instance not registered",
                trust_level_at_decision="unregistered",
            )

        # REM: Step 2 — Kill switch (FIRST — fast rejection, Redis-backed via is_suspended)
        if instance.suspended or self.is_suspended(instance_id):
            audit.log(
                AuditEventType.OPENCLAW_ACTION_BLOCKED,
                f"Suspended OpenClaw action blocked: ::{instance.name}:: → {tool_name}",
                actor=f"openclaw:{instance_id}",
                details={
                    "tool": tool_name, "reason": "suspended",
                    "suspended_reason": instance.suspended_reason,
                },
                qms_status="Thank_You_But_No"
            )
            return OpenClawActionResult(
                allowed=False,
                reason=f"Instance suspended: {instance.suspended_reason or 'kill switch active'}",
                trust_level_at_decision=instance.trust_level,
            )

        # REM: Step 3 — Nonce replay protection
        if not self._check_nonce(nonce):
            return OpenClawActionResult(
                allowed=False,
                reason="Nonce replay detected",
                trust_level_at_decision=instance.trust_level,
            )

        # REM: Step 4 — Tool blocklist check
        if tool_name in instance.blocked_tools:
            audit.log(
                AuditEventType.OPENCLAW_ACTION_BLOCKED,
                f"Blocklisted tool: ::{instance.name}:: → {tool_name}",
                actor=f"openclaw:{instance_id}",
                details={"tool": tool_name, "reason": "tool_blocked"},
                qms_status="Thank_You_But_No"
            )
            instance.action_count += 1
            instance.actions_blocked += 1
            instance.last_action_at = datetime.now(timezone.utc)
            self._persist_instance(instance)
            try:
                from core.manners import ViolationType, manners_engine
                manners_engine.record_violation(
                    agent_name=instance.name,
                    violation_type=ViolationType.CAPABILITY_VIOLATION,
                    details=f"Blocked tool: '{tool_name}' is on the blocklist",
                    action=tool_name,
                )
                new_score = manners_engine.evaluate(instance.name).overall_score
                self.update_manners_score(instance_id, new_score)
            except Exception as e:
                logger.warning(f"REM: Manners wire-up error (blocklist): {e}")
            return OpenClawActionResult(
                allowed=False,
                reason=f"Tool '{tool_name}' is blocked for this instance",
                trust_level_at_decision=instance.trust_level,
                manners_score_at_decision=instance.manners_score,
            )

        # REM: Tool allowlist check (if non-empty, only allowed tools pass)
        if instance.allowed_tools and tool_name not in instance.allowed_tools:
            audit.log(
                AuditEventType.OPENCLAW_ACTION_BLOCKED,
                f"Tool not on allowlist: ::{instance.name}:: → {tool_name}",
                actor=f"openclaw:{instance_id}",
                details={"tool": tool_name, "reason": "tool_not_allowed"},
                qms_status="Thank_You_But_No"
            )
            instance.action_count += 1
            instance.actions_blocked += 1
            instance.last_action_at = datetime.now(timezone.utc)
            self._persist_instance(instance)
            return OpenClawActionResult(
                allowed=False,
                reason=f"Tool '{tool_name}' not on allowlist",
                trust_level_at_decision=instance.trust_level,
            )

        # REM: Step 5 — Classify the action.
        # REM: Unknown tools default to DELETE (most restrictive gated category) so that
        # REM: tools not explicitly mapped always require approval rather than running autonomously.
        category = TOOL_CATEGORY_MAP.get(tool_name, ActionCategory.DELETE)
        trust_level = TrustLevel(instance.trust_level)

        # REM: Step 6 — Manners compliance auto-demotion check
        settings = get_settings()
        if instance.manners_score < settings.openclaw_auto_demote_manners_threshold:
            if trust_level != TrustLevel.QUARANTINE:
                old_level = instance.trust_level
                instance.trust_level = TrustLevel.QUARANTINE.value
                trust_level = TrustLevel.QUARANTINE

                # REM: Record the auto-demotion
                change = TrustChangeRecord(
                    instance_id=instance_id,
                    old_level=old_level,
                    new_level=TrustLevel.QUARANTINE.value,
                    changed_by="manners_engine",
                    reason=f"Manners score ({instance.manners_score:.2f}) below threshold ({settings.openclaw_auto_demote_manners_threshold})",
                    change_type="auto_demotion",
                )
                self._trust_history.setdefault(instance_id, []).append(change)
                self._persist_trust_history(instance_id)
                self._persist_instance(instance)

                audit.log(
                    AuditEventType.OPENCLAW_TRUST_DEMOTED,
                    f"Auto-demotion: ::{instance.name}:: {old_level} → quarantine (Manners score {instance.manners_score:.2f})",
                    actor="manners_engine",
                    details={
                        "instance_id": instance_id,
                        "old_level": old_level,
                        "new_level": "quarantine",
                        "manners_score": instance.manners_score,
                        "threshold": settings.openclaw_auto_demote_manners_threshold,
                    },
                    qms_status="Thank_You"
                )

                # REM: Set demotion review flag on auto-demotion — Manners breach is a behavioral signal
                # REM: requiring cross-infection analysis before the agent can be re-promoted.
                self._set_review_required(
                    instance_id, "manners_engine",
                    f"Auto-demoted: Manners score {instance.manners_score:.2f} below threshold {settings.openclaw_auto_demote_manners_threshold}",
                    instance.action_count,
                )

                logger.warning(
                    f"REM: Manners auto-demotion: ::{instance.name}:: → quarantine "
                    f"(score: {instance.manners_score:.2f})_Thank_You"
                )

        # REM: Step 7 — Trust level permission check
        permissions = TRUST_PERMISSION_MATRIX[trust_level]

        # REM: Check if action category is blocked at this trust level
        if category in permissions["blocked"]:
            audit.log(
                AuditEventType.OPENCLAW_ACTION_BLOCKED,
                f"Trust level block: ::{instance.name}:: ({trust_level.value}) → {tool_name} ({category.value})",
                actor=f"openclaw:{instance_id}",
                details={
                    "tool": tool_name, "category": category.value,
                    "trust_level": trust_level.value, "reason": "trust_level_block",
                },
                qms_status="Thank_You_But_No"
            )
            instance.action_count += 1
            instance.actions_blocked += 1
            instance.last_action_at = datetime.now(timezone.utc)
            self._persist_instance(instance)
            self._log_action(instance_id, tool_name, "blocked")
            try:
                from core.manners import ViolationType, manners_engine
                manners_engine.record_violation(
                    agent_name=instance.name,
                    violation_type=ViolationType.OUT_OF_ROLE_ACTION,
                    details=(
                        f"Trust level block: '{trust_level.value}' tier prohibits "
                        f"'{category.value}' action (tool='{tool_name}')"
                    ),
                    action=tool_name,
                )
                new_score = manners_engine.evaluate(instance.name).overall_score
                self.update_manners_score(instance_id, new_score)
            except Exception as e:
                logger.warning(f"REM: Manners wire-up error (trust block): {e}")
            return OpenClawActionResult(
                allowed=False,
                reason=(
                    f"BLOCKED: '{trust_level.value}' tier prohibits '{category.value}' actions — "
                    f"tool='{tool_name}', category='{category.value}', trust='{trust_level.value}' — "
                    f"promote instance to enable this action category"
                ),
                action_category=category.value,
                trust_level_at_decision=trust_level.value,
                manners_score_at_decision=instance.manners_score,
            )

        # REM: Check if action requires approval (gated)
        approval_required = category in permissions["gated"]

        # REM: Step 8 — Anomaly detection check (flag even autonomous actions)
        anomaly_flagged = self._check_anomaly(instance_id, tool_name, tool_args)
        # REM: AGENT tier — anomalies are advisory only. Log loudly, do not gate.
        if anomaly_flagged and trust_level == TrustLevel.AGENT:
            audit.log(
                AuditEventType.OPENCLAW_ANOMALY_DETECTED,
                f"Advisory anomaly (AGENT tier — not gated): ::{instance.name}:: → {tool_name}",
                actor=f"openclaw:{instance_id}",
                details={"tool": tool_name, "trust_level": "agent", "advisory_only": True},
                qms_status="Thank_You"
            )
            logger.warning(
                f"REM: AGENT-tier advisory anomaly: ::{instance.name}:: → {tool_name} "
                f"(not gated — AGENT has earned full trust)_Thank_You"
            )
        if anomaly_flagged and trust_level == TrustLevel.CITIZEN:
            # REM: Even Citizens get gated on anomaly-flagged actions
            approval_required = True

        # REM: Mark nonce as used
        self._mark_nonce_used(nonce)

        # REM: Update instance counters
        instance.action_count += 1
        instance.last_action_at = datetime.now(timezone.utc)

        if approval_required:
            # REM: Create approval request in the approval system (visible in dashboard)
            try:
                from core.approval import approval_gate

                # REM: Select rule based on trust level and action category
                if trust_level == TrustLevel.QUARANTINE:
                    rule_id = "rule-openclaw-quarantine-action"
                elif category == ActionCategory.EXTERNAL_REQUEST:
                    rule_id = "rule-openclaw-external-action"
                elif category == ActionCategory.DELETE:
                    rule_id = "rule-openclaw-destructive-action"
                else:
                    rule_id = "rule-openclaw-quarantine-action"
                rule = approval_gate._rules.get(rule_id)
                if rule:
                    appr = approval_gate.create_request(
                        agent_id=f"openclaw:{instance_id}",
                        action=tool_name,
                        description=f"OpenClaw {instance.name} ({trust_level.value}) wants to: {tool_name}",
                        payload={"tool_name": tool_name, "tool_args": tool_args, "instance_id": instance_id},
                        rule=rule,
                        risk_factors=["openclaw_governed_action"] + (["anomaly_flagged"] if anomaly_flagged else []),
                    )
                    approval_id = appr.request_id
                else:
                    approval_id = uuid.uuid4().hex[:16]
            except Exception:
                approval_id = uuid.uuid4().hex[:16]

            instance.actions_gated += 1
            self._persist_instance(instance)
            self._log_action(instance_id, tool_name, "gated")

            audit.log(
                AuditEventType.OPENCLAW_ACTION_GATED,
                f"Approval required: ::{instance.name}:: ({trust_level.value}) → {tool_name}",
                actor=f"openclaw:{instance_id}",
                details={
                    "tool": tool_name, "category": category.value,
                    "trust_level": trust_level.value,
                    "approval_id": approval_id,
                    "anomaly_flagged": anomaly_flagged,
                },
                qms_status="Excuse_Me"
            )

            return OpenClawActionResult(
                allowed=False,
                reason=(
                    f"HITL gate: '{trust_level.value}' tier requires human approval for "
                    f"'{category.value}' — tool='{tool_name}', approval_id={approval_id}"
                ),
                action_category=category.value,
                trust_level_at_decision=trust_level.value,
                approval_required=True,
                approval_id=approval_id,
                manners_score_at_decision=instance.manners_score,
                anomaly_flagged=anomaly_flagged,
            )

        # REM: Action is autonomous — allow it
        instance.actions_allowed += 1
        self._persist_instance(instance)
        self._log_action(instance_id, tool_name, "allowed")

        audit.log(
            AuditEventType.OPENCLAW_ACTION_ALLOWED,
            f"Action allowed: ::{instance.name}:: ({trust_level.value}) → {tool_name}",
            actor=f"openclaw:{instance_id}",
            details={
                "tool": tool_name, "category": category.value,
                "trust_level": trust_level.value,
                "anomaly_flagged": anomaly_flagged,
            },
            qms_status="Thank_You"
        )

        return OpenClawActionResult(
            allowed=True,
            reason=(
                f"Autonomous: '{trust_level.value}' tier permits '{category.value}' — "
                f"tool='{tool_name}' allowed without HITL"
            ),
            action_category=category.value,
            trust_level_at_decision=trust_level.value,
            manners_score_at_decision=instance.manners_score,
            anomaly_flagged=anomaly_flagged,
        )

    def _check_anomaly(self, instance_id: str, tool_name: str, tool_args: Dict) -> bool:
        """
        REM: Check if this action is anomalous for this instance.
        REM: Delegates to core/anomaly.py if available.
        """
        try:
            from core.anomaly import BehaviorMonitor
            detector = BehaviorMonitor()
            # REM: Record action and check for anomalies
            anomalies = detector.record(
                agent_id=f"openclaw:{instance_id}",
                action=tool_name,
                resource=json.dumps(tool_args, default=str)[:200],
            )
            return len(anomalies) > 0
        except Exception:
            # REM: Anomaly detection unavailable — proceed without flagging
            return False

    def _log_action(self, instance_id: str, tool_name: str, decision: str):
        """REM: Log action to Redis sorted set for anomaly detection baseline."""
        client = self._get_redis()
        if not client:
            return
        try:
            settings = get_settings()
            ttl_seconds = settings.openclaw_action_log_ttl_hours * 3600
            key = f"openclaw:actions:{instance_id}"
            score = time.time()
            value = json.dumps({
                "tool": tool_name,
                "decision": decision,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            client.zadd(key, {value: score})
            client.expire(key, ttl_seconds)
            # REM: Trim to keep only recent entries (max 1000)
            client.zremrangebyrank(key, 0, -1001)
        except Exception as e:
            logger.debug(f"REM: Failed to log action to Redis: {e}")

    def _check_nonce(self, nonce: str) -> bool:
        """REM: Check if nonce has been used (replay protection). Returns True if nonce is fresh."""
        client = self._get_redis()
        if client:
            try:
                if client.exists(f"openclaw:nonce:{nonce}"):
                    return False
                return True
            except Exception:
                pass
        return True

    def _mark_nonce_used(self, nonce: str):
        """REM: Mark a nonce as used with 5-minute TTL."""
        client = self._get_redis()
        if client:
            try:
                client.setex(f"openclaw:nonce:{nonce}", 300, "used")
            except Exception:
                pass

    # REM: ==========================================
    # REM: DEMOTION REVIEW FRAMEWORK
    # REM: ==========================================

    def _set_review_required(
        self, instance_id: str, demoted_by: str, reason: str, action_count: int
    ):
        """
        REM: Set demotion review flag in Redis.
        REM: Human admin should review last N actions for cross-infection before re-promoting.
        REM: Cleared via clear_review(). Surfaced via get_review_status() and GET /status.
        """
        client = self._get_redis()
        if not client:
            return
        try:
            data = json.dumps({
                "demoted_by": demoted_by,
                "reason": reason,
                "action_count_at_demotion": action_count,
                "actions_to_review": min(action_count, 500),
                "review_required_at": datetime.now(timezone.utc).isoformat(),
                "review_note": (
                    f"Review last {min(action_count, 500)} actions for cross-infection "
                    f"before re-promoting. Use GET /v1/openclaw/{{id}}/actions to export."
                ),
            })
            client.set(f"openclaw:review_required:{instance_id}", data)
        except Exception as e:
            logger.warning(f"REM: Failed to set demotion review flag: {e}")

    def _is_review_required(self, instance_id: str) -> bool:
        """REM: Check if a demotion review is pending. Redis-backed (multi-worker safe)."""
        client = self._get_redis()
        if not client:
            return False
        try:
            return bool(client.exists(f"openclaw:review_required:{instance_id}"))
        except Exception:
            return False

    def get_review_status(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """REM: Get demotion review details. Returns None if no review pending."""
        client = self._get_redis()
        if not client:
            return None
        try:
            data = client.get(f"openclaw:review_required:{instance_id}")
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    def clear_review(self, instance_id: str, cleared_by: str, notes: str = "") -> bool:
        """
        REM: Clear the demotion review flag after human sign-off.
        REM: Admin acknowledges they have reviewed last-N-actions for cross-infection.
        REM: Re-promotion advisory is lifted once this is called.
        """
        instance = self.get_instance(instance_id)
        if not instance:
            return False

        review_data = self.get_review_status(instance_id)

        client = self._get_redis()
        if client:
            try:
                client.delete(f"openclaw:review_required:{instance_id}")
            except Exception as e:
                logger.warning(f"REM: Failed to clear review flag: {e}")

        audit.log(
            AuditEventType.OPENCLAW_TRUST_PROMOTED,
            f"Demotion review cleared: ::{instance.name}:: — re-promotion advisory lifted",
            actor=cleared_by,
            details={
                "instance_id": instance_id,
                "cleared_by": cleared_by,
                "notes": notes,
                "reviewed_actions": (review_data or {}).get("actions_to_review", 0),
                "original_demotion": review_data,
            },
            qms_status="Thank_You"
        )
        logger.info(
            f"REM: Demotion review cleared: ::{instance.name}:: by {cleared_by}_Thank_You"
        )
        return True

    # REM: ==========================================
    # REM: TRUST LEVEL MANAGEMENT
    # REM: ==========================================

    def promote_trust(self, instance_id: str, new_level: str, promoted_by: str, reason: str = "") -> bool:
        """
        REM: Promote an instance to a higher trust level.
        REM: Must follow valid promotion path: QUARANTINE → PROBATION → RESIDENT → CITIZEN
        REM: A pending demotion review is flagged in audit — see clear_review() for sign-off.
        """
        # REM: No destructive pop for mutations — get_instance reads local cache then Redis.
        # REM: _persist_instance writes to both _instances and Redis after a successful mutation.
        # REM: Only evaluate_action needs forced Redis eviction (governance decision must be authoritative).
        instance = self.get_instance(instance_id)
        if not instance:
            return False

        try:
            current = TrustLevel(instance.trust_level)
            target = TrustLevel(new_level)
        except ValueError:
            logger.warning(f"REM: Invalid trust level: {new_level}_Thank_You_But_No")
            return False

        # REM: Validate promotion path
        if target not in VALID_PROMOTIONS.get(current, []):
            logger.warning(
                f"REM: Invalid promotion: {current.value} → {target.value} "
                f"(valid: {[v.value for v in VALID_PROMOTIONS.get(current, [])]})_Thank_You_But_No"
            )
            return False

        # REM: Demotion review check — flag in audit if human sign-off is still pending.
        # REM: Advisory in beta; human admin should call clear_review() before re-promoting.
        # REM: Surface: GET /v1/openclaw/{id}/status returns review_required:true.
        if self._is_review_required(instance_id):
            logger.warning(
                f"REM: ADVISORY — demotion review pending for ::{instance.name}::. "
                f"Acknowledge via POST /v1/openclaw/{instance_id}/clear-review before promoting_Thank_You"
            )
            audit.log(
                AuditEventType.OPENCLAW_ACTION_BLOCKED,
                f"Promotion advisory: ::{instance.name}:: — demotion review pending (proceeding with override)",
                actor=promoted_by,
                details={
                    "instance_id": instance_id,
                    "attempted_promotion": new_level,
                    "advisory": "demotion_review_pending — call /clear-review to acknowledge",
                },
                qms_status="Excuse_Me"
            )

        old_level = instance.trust_level
        instance.trust_level = target.value
        self._persist_instance(instance)

        # REM: Record the change
        change = TrustChangeRecord(
            instance_id=instance_id,
            old_level=old_level,
            new_level=target.value,
            changed_by=promoted_by,
            reason=reason,
            change_type="promotion",
        )
        self._trust_history.setdefault(instance_id, []).append(change)
        self._persist_trust_history(instance_id)

        audit.log(
            AuditEventType.OPENCLAW_TRUST_PROMOTED,
            f"Trust promoted: ::{instance.name}:: {old_level} → {target.value}",
            actor=promoted_by,
            details={
                "instance_id": instance_id,
                "old_level": old_level,
                "new_level": target.value,
                "reason": reason,
            },
            qms_status="Thank_You"
        )

        logger.info(
            f"REM: Trust promoted: ::{instance.name}:: {old_level} → {target.value} "
            f"by {promoted_by}_Thank_You"
        )
        return True

    def demote_trust(self, instance_id: str, new_level: str, demoted_by: str, reason: str = "") -> bool:
        """
        REM: Demote an instance to a lower trust level.
        REM: Demotions can skip levels (instant consequences).
        REM: Sets demotion review flag — human admin should call clear_review() before re-promotion.
        """
        # REM: No destructive pop for mutations — get_instance reads local cache then Redis.
        # REM: _persist_instance writes to both _instances and Redis after a successful mutation.
        # REM: Only evaluate_action needs forced Redis eviction (governance decision must be authoritative).
        instance = self.get_instance(instance_id)
        if not instance:
            return False

        try:
            current = TrustLevel(instance.trust_level)
            target = TrustLevel(new_level)
        except ValueError:
            logger.warning(f"REM: Invalid trust level: {new_level}_Thank_You_But_No")
            return False

        # REM: Validate demotion path
        if target not in VALID_DEMOTIONS.get(current, []):
            logger.warning(
                f"REM: Invalid demotion: {current.value} → {target.value}_Thank_You_But_No"
            )
            return False

        old_level = instance.trust_level
        instance.trust_level = target.value
        self._persist_instance(instance)

        change = TrustChangeRecord(
            instance_id=instance_id,
            old_level=old_level,
            new_level=target.value,
            changed_by=demoted_by,
            reason=reason,
            change_type="demotion",
        )
        self._trust_history.setdefault(instance_id, []).append(change)
        self._persist_trust_history(instance_id)

        # REM: Set demotion review flag — human admin should review last N actions for
        # REM: cross-infection before re-promoting. Surface via GET /status or /clear-review.
        self._set_review_required(instance_id, demoted_by, reason, instance.action_count)

        audit.log(
            AuditEventType.OPENCLAW_TRUST_DEMOTED,
            f"Trust demoted: ::{instance.name}:: {old_level} → {target.value}",
            actor=demoted_by,
            details={
                "instance_id": instance_id,
                "old_level": old_level,
                "new_level": target.value,
                "reason": reason,
                "review_required": True,
                "review_note": f"Review last {min(instance.action_count, 500)} actions for cross-infection",
            },
            qms_status="Thank_You"
        )

        logger.warning(
            f"REM: Trust demoted: ::{instance.name}:: {old_level} → {target.value} "
            f"by {demoted_by}_Thank_You"
        )
        return True

    # REM: ==========================================
    # REM: KILL SWITCH
    # REM: ==========================================

    def suspend_instance(self, instance_id: str, suspended_by: str, reason: str = "") -> bool:
        """
        REM: Immediately suspend an OpenClaw instance. The kill switch.
        REM: All subsequent actions are rejected until reinstatement.
        """
        # REM: No destructive pop for mutations — get_instance reads local cache then Redis.
        # REM: _persist_instance writes to both _instances and Redis after a successful mutation.
        instance = self.get_instance(instance_id)
        if not instance:
            return False

        instance.suspended = True
        instance.suspended_by = suspended_by
        instance.suspended_at = datetime.now(timezone.utc)
        instance.suspended_reason = reason
        self._suspended_ids.add(instance_id)
        self._persist_instance(instance)

        # REM: Persist suspension to Redis (survives restarts)
        client = self._get_redis()
        if client:
            try:
                client.set(f"openclaw:suspended:{instance_id}", "suspended")
            except Exception:
                pass

        audit.log(
            AuditEventType.OPENCLAW_SUSPENDED,
            f"OpenClaw SUSPENDED (kill switch): ::{instance.name}:: ({instance_id})",
            actor=suspended_by,
            details={
                "instance_id": instance_id,
                "name": instance.name,
                "reason": reason,
                "action_count": instance.action_count,
                "trust_level": instance.trust_level,
            },
            qms_status="Thank_You"
        )

        logger.warning(
            f"REM: KILL SWITCH — OpenClaw suspended: ::{instance.name}:: "
            f"by {suspended_by} — {reason}_Thank_You"
        )
        return True

    def reinstate_instance(self, instance_id: str, reinstated_by: str, reason: str = "") -> bool:
        """REM: Clear suspension after human review. Instance returns to its previous trust level."""
        # REM: Multi-worker fix: evict stale in-memory copy before reading authoritative Redis state.
        # REM: No destructive pop for mutations — get_instance reads local cache then Redis.
        # REM: _persist_instance writes to both _instances and Redis after a successful mutation.
        instance = self.get_instance(instance_id)
        if not instance:
            return False

        if not instance.suspended and instance_id not in self._suspended_ids:
            return False

        instance.suspended = False
        instance.suspended_by = None
        instance.suspended_at = None
        instance.suspended_reason = None
        self._suspended_ids.discard(instance_id)
        self._persist_instance(instance)

        # REM: Remove suspension from Redis
        client = self._get_redis()
        if client:
            try:
                client.delete(f"openclaw:suspended:{instance_id}")
            except Exception:
                pass

        audit.log(
            AuditEventType.OPENCLAW_REINSTATED,
            f"OpenClaw REINSTATED: ::{instance.name}:: ({instance_id})",
            actor=reinstated_by,
            details={
                "instance_id": instance_id,
                "name": instance.name,
                "reason": reason,
                "trust_level": instance.trust_level,
            },
            qms_status="Thank_You"
        )

        logger.info(
            f"REM: OpenClaw reinstated: ::{instance.name}:: "
            f"by {reinstated_by}_Thank_You"
        )
        return True

    def deregister_instance(self, instance_id: str, deregistered_by: str, reason: str = "") -> bool:
        """
        REM: Permanently remove an OpenClaw instance from governance.
        REM: Deletes all Redis state (instance record, suspension flag, trust history,
        REM: demotion review). Irreversible — agent must re-register to re-enter governance.
        """
        instance = self.get_instance(instance_id)
        if not instance:
            return False

        # REM: Capture name before removal for audit record
        name = instance.name
        trust_level = instance.trust_level
        action_count = instance.action_count

        # REM: Remove from local caches
        self._instances.pop(instance_id, None)
        self._suspended_ids.discard(instance_id)
        self._trust_history.pop(instance_id, None)

        # REM: Remove all Redis keys for this instance
        client = self._get_redis()
        if client:
            try:
                client.delete(f"openclaw:instance:{instance_id}")
                client.delete(f"openclaw:suspended:{instance_id}")
                client.delete(f"openclaw:trust_history:{instance_id}")
                client.delete(f"openclaw:review_required:{instance_id}")
            except Exception as e:
                logger.warning(f"REM: Failed to delete OpenClaw instance from Redis: {e}")

        audit.log(
            AuditEventType.OPENCLAW_DEREGISTERED,
            f"OpenClaw instance DEREGISTERED: ::{name}:: ({instance_id})",
            actor=deregistered_by,
            details={
                "instance_id": instance_id,
                "name": name,
                "reason": reason,
                "trust_level": trust_level,
                "action_count": action_count,
            },
            qms_status="Thank_You"
        )

        logger.info(
            f"REM: OpenClaw instance deregistered: ::{name}:: "
            f"by {deregistered_by}_Thank_You"
        )
        return True

    def is_suspended(self, instance_id: str) -> bool:
        """REM: Check if an instance is suspended. Always checked first in governance pipeline."""
        if instance_id in self._suspended_ids:
            return True
        # REM: Fallback to Redis (may have been suspended by another worker)
        client = self._get_redis()
        if client:
            try:
                if client.exists(f"openclaw:suspended:{instance_id}"):
                    self._suspended_ids.add(instance_id)
                    return True
            except Exception:
                pass
        return False

    # REM: ==========================================
    # REM: QUERY METHODS
    # REM: ==========================================

    def get_instance(self, instance_id: str) -> Optional[OpenClawInstance]:
        """REM: Get an OpenClaw instance by ID."""
        instance = self._instances.get(instance_id)
        if instance:
            return instance
        # REM: Try Redis
        client = self._get_redis()
        if client:
            try:
                data = client.get(f"openclaw:instance:{instance_id}")
                if data:
                    instance = OpenClawInstance.model_validate_json(data)
                    self._instances[instance_id] = instance
                    return instance
            except Exception:
                pass
        return None

    def list_instances(self) -> List[OpenClawInstance]:
        """REM: List all registered OpenClaw instances. Scans Redis to pick up cross-worker registrations."""
        client = self._get_redis()
        if client:
            try:
                keys = client.keys("openclaw:instance:*")
                for key in keys:
                    instance_id = key.replace("openclaw:instance:", "")
                    if instance_id not in self._instances:
                        data = client.get(key)
                        if data:
                            try:
                                instance = OpenClawInstance.model_validate_json(data)
                                self._instances[instance_id] = instance
                            except Exception:
                                pass
            except Exception:
                pass
        return list(self._instances.values())

    def get_trust_report(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """REM: Get a trust report for an instance: history, action summary, current status."""
        instance = self.get_instance(instance_id)
        if not instance:
            return None

        history = self._trust_history.get(instance_id, [])

        return {
            "instance_id": instance_id,
            "name": instance.name,
            "current_trust_level": instance.trust_level,
            "manners_score": instance.manners_score,
            "suspended": instance.suspended,
            "action_summary": {
                "total": instance.action_count,
                "allowed": instance.actions_allowed,
                "blocked": instance.actions_blocked,
                "gated": instance.actions_gated,
            },
            "trust_history": [r.model_dump(mode="json") for r in history],
            "registered_at": instance.registered_at.isoformat(),
            "last_action_at": instance.last_action_at.isoformat() if instance.last_action_at else None,
        }

    def get_recent_actions(self, instance_id: str, limit: int = 50) -> List[Dict]:
        """REM: Get recent actions from Redis sorted set."""
        client = self._get_redis()
        if not client:
            return []
        try:
            key = f"openclaw:actions:{instance_id}"
            raw_entries = client.zrevrange(key, 0, limit - 1, withscores=True)
            actions = []
            for value, score in raw_entries:
                try:
                    entry = json.loads(value)
                    entry["score"] = score
                    actions.append(entry)
                except json.JSONDecodeError:
                    pass
            return actions
        except Exception:
            return []

    def update_manners_score(self, instance_id: str, new_score: float):
        """REM: Update an instance's Manners compliance score (called by Manners engine)."""
        instance = self._instances.get(instance_id)
        if instance:
            instance.manners_score = max(0.0, min(1.0, new_score))
            self._persist_instance(instance)

    def authenticate_instance(self, api_key: str) -> Optional[OpenClawInstance]:
        """
        REM: Authenticate an OpenClaw instance by its API key.
        REM: Returns the instance if the key hash matches.
        """
        api_key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        for instance in self._instances.values():
            if instance.api_key_hash == api_key_hash and not instance.suspended:
                return instance
        return None


# REM: =======================================================================================
# REM: GLOBAL SINGLETON
# REM: =======================================================================================
openclaw_manager = OpenClawManager()
