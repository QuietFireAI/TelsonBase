# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# ClawFilters/core/signing.py
# REM: =======================================================================================
# REM: CRYPTOGRAPHIC MESSAGE SIGNING FOR AGENT COMMUNICATIONS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Every message between agents MUST be signed. An unsigned or
# REM: invalidly signed message is rejected. Period. This prevents:
# REM:   - Agent impersonation (Agent A pretending to be Agent B)
# REM:   - Message tampering (modifying payload in transit)
# REM:   - Replay attacks (re-sending old valid messages)
# REM:
# REM: Security Model: Each agent has a unique signing key. The orchestrator maintains
# REM: a registry of trusted agent keys. Messages are HMAC-SHA256 signed.
# REM:
# REM: v4.1.0CC: Added Redis persistence and key revocation with audit trail
# REM: =======================================================================================

import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# REM: Import persistence store (lazy to avoid circular imports)
_signing_store = None

def _get_store():
    """REM: Lazy-load the signing store to avoid circular imports.
    REM: M3 fix: failure is not cached — caller retries on every invocation so the store
    REM: self-heals once Redis becomes available (prevents permanent in-memory-only mode)."""
    global _signing_store
    if _signing_store is None:
        try:
            from core.persistence import signing_store
            _signing_store = signing_store
        except Exception as e:
            # REM: Do NOT cache failure — return None so the next call retries
            logger.warning(
                f"REM: Signing store (Redis) unavailable — replay protection degraded to "
                f"in-memory only (single-worker, non-persistent): {e}_Thank_You_But_No"
            )
            return None
    return _signing_store

# REM: Message replay window - reject messages older than this
REPLAY_WINDOW_SECONDS = 300  # 5 minutes


class SignedAgentMessage(BaseModel):
    """
    REM: A cryptographically signed message between agents.
    REM: Every inter-agent communication MUST use this format.
    """
    # REM: Message metadata
    message_id: str = Field(..., description="Unique message identifier (UUID)")
    agent_id: str = Field(..., description="ID of the sending agent")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # REM: Message content
    action: str = Field(..., description="The action being requested")
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    # REM: Cryptographic signature
    signature: str = Field(..., description="HMAC-SHA256 signature of the message")
    
    # REM: Optional routing
    target_agent: Optional[str] = Field(default=None, description="Intended recipient agent")
    reply_to: Optional[str] = Field(default=None, description="Message ID this is replying to")
    
    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v
    
    def get_signing_payload(self) -> str:
        """
        REM: Generate the canonical payload string for signing.
        REM: Order matters - must be deterministic.
        """
        canonical = {
            "message_id": self.message_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "payload": self.payload,
            "target_agent": self.target_agent,
            "reply_to": self.reply_to,
        }
        # REM: Sort keys for deterministic serialization
        return json.dumps(canonical, sort_keys=True, separators=(',', ':'))
    
    def verify(self, secret_key: bytes) -> bool:
        """
        REM: Verify this message's signature against a known secret key.
        
        Returns:
            True if signature is valid, False otherwise
        """
        expected_signature = hmac.new(
            secret_key,
            self.get_signing_payload().encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # REM: Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(self.signature, expected_signature)
    
    def is_expired(self, window_seconds: int = REPLAY_WINDOW_SECONDS) -> bool:
        """
        REM: Check if this message is outside the replay window.
        """
        now = datetime.now(timezone.utc)
        age = (now - self.timestamp).total_seconds()
        return abs(age) > window_seconds


class AgentKeyRegistry:
    """
    REM: Registry of agent signing keys.
    REM: The orchestrator uses this to verify message authenticity.
    REM: v4.1.0CC: Now persists to Redis and tracks revoked keys.
    """

    def __init__(self):
        self._keys: Dict[str, bytes] = {}
        self._seen_message_ids: Set[str] = set()
        self._message_timestamps: Dict[str, datetime] = {}
        self._revoked_agents: Set[str] = set()  # Track revoked agents
        self._load_from_persistence()

    def _load_from_persistence(self):
        """REM: Load keys and revocations from Redis on startup."""
        store = _get_store()
        if store:
            try:
                for agent_id in store.list_agents():
                    key = store.get_key(agent_id)
                    if key:
                        self._keys[agent_id] = key
                logger.info(f"REM: Loaded {len(self._keys)} signing keys from persistence_Thank_You")
            except Exception as e:
                logger.warning(f"REM: Failed to load keys from persistence: {e}")
        # REM: Load persisted revocations — prevents revoked agents from re-authenticating
        # REM: after restart (H2 fix: _revoked_agents was previously in-memory only).
        try:
            from core.persistence import security_store
            revoked = security_store.get_set_members("signing:revoked_agents")
            if revoked:
                self._revoked_agents = set(revoked)
                logger.info(
                    f"REM: Loaded {len(self._revoked_agents)} revoked agents from Redis_Thank_You"
                )
        except Exception as e:
            logger.warning(f"REM: Failed to load revoked agents from Redis: {e}_Thank_You_But_No")

    def _persist_key(self, agent_id: str, key: bytes):
        """REM: Persist a key to Redis."""
        store = _get_store()
        if store:
            try:
                store.store_key(agent_id, key)
            except Exception as e:
                logger.warning(f"REM: Failed to persist key for {agent_id}: {e}")

    def _delete_persisted_key(self, agent_id: str):
        """REM: Delete a key from Redis."""
        store = _get_store()
        if store:
            try:
                store.delete_key(agent_id)
            except Exception as e:
                logger.warning(f"REM: Failed to delete persisted key for {agent_id}: {e}")

    def register_agent(self, agent_id: str, secret_key: Optional[bytes] = None) -> bytes:
        """
        REM: Register an agent and assign or store its signing key.

        Args:
            agent_id: Unique agent identifier
            secret_key: Optional pre-existing key (generates new if None)

        Returns:
            The agent's signing key
        """
        # REM: Check if agent was previously revoked
        if agent_id in self._revoked_agents:
            logger.warning(f"REM: Attempt to re-register revoked agent ::{agent_id}::_Thank_You_But_No")
            raise PermissionError(f"Agent {agent_id} was revoked and cannot be re-registered")

        if secret_key is None:
            secret_key = secrets.token_bytes(32)

        self._keys[agent_id] = secret_key
        self._persist_key(agent_id, secret_key)  # Persist to Redis
        logger.info(f"REM: Registered signing key for agent ::{agent_id}::_Thank_You")
        return secret_key
    
    def get_key(self, agent_id: str) -> Optional[bytes]:
        """REM: Retrieve an agent's signing key."""
        return self._keys.get(agent_id)
    
    def revoke_agent(self, agent_id: str, reason: str = "No reason provided", revoked_by: str = "system") -> bool:
        """
        REM: Revoke an agent's signing key with full audit trail.
        REM: All future messages from this agent will be rejected.
        REM: The agent cannot be re-registered without explicit clearing.

        Args:
            agent_id: The agent to revoke
            reason: Why the key is being revoked
            revoked_by: Who/what is revoking the key

        Returns:
            True if revoked, False if agent not found
        """
        if agent_id in self._keys:
            del self._keys[agent_id]
            self._revoked_agents.add(agent_id)
            self._delete_persisted_key(agent_id)
            # REM: Persist revocation to Redis — survives restarts (H2 fix)
            try:
                from core.persistence import security_store
                security_store.add_to_set("signing:revoked_agents", agent_id)
            except Exception as e:
                logger.warning(
                    f"REM: Failed to persist revocation for ::{agent_id}::: {e}_Thank_You_But_No"
                )

            logger.warning(
                f"REM: REVOKED signing key for agent ::{agent_id}:: "
                f"Reason: ::{reason}:: By: ::{revoked_by}::_Thank_You_But_No"
            )

            # REM: Audit the revocation
            try:
                from core.audit import AuditEventType, audit
                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    f"Agent signing key REVOKED: ::{agent_id}::",
                    actor=revoked_by,
                    resource=agent_id,
                    details={
                        "reason": reason,
                        "revoked_by": revoked_by,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    qms_status="Thank_You_But_No"
                )
            except Exception as e:
                logger.error(f"REM: Failed to audit key revocation: {e}")

            return True
        return False

    def clear_revocation(self, agent_id: str, cleared_by: str = "system") -> bool:
        """
        REM: Clear a revocation, allowing an agent to be re-registered.
        REM: This should only be used after security review.
        """
        if agent_id in self._revoked_agents:
            self._revoked_agents.discard(agent_id)
            # REM: Remove from Redis revocation set
            try:
                from core.persistence import security_store
                security_store.remove_from_set("signing:revoked_agents", agent_id)
            except Exception as e:
                logger.warning(
                    f"REM: Failed to clear Redis revocation for ::{agent_id}::: {e}_Thank_You_But_No"
                )
            logger.warning(
                f"REM: Revocation cleared for agent ::{agent_id}:: "
                f"By: ::{cleared_by}::_Thank_You"
            )
            try:
                from core.audit import AuditEventType, audit
                audit.log(
                    AuditEventType.SECURITY_ALERT,
                    f"Signing key revocation cleared for agent ::{agent_id}::",
                    actor=cleared_by,
                    resource=agent_id,
                    details={
                        "action": "clear_revocation",
                        "cleared_by": cleared_by,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    qms_status="Thank_You"
                )
            except Exception as e:
                logger.error(f"REM: Failed to audit revocation clear: {e}")
            return True
        return False

    def is_revoked(self, agent_id: str) -> bool:
        """REM: Check if an agent has been revoked."""
        return agent_id in self._revoked_agents
    
    def verify_message(self, message: SignedAgentMessage) -> tuple[bool, str]:
        """
        REM: Comprehensive message verification.

        Checks:
        0. Agent is not revoked
        1. Agent is registered
        2. Signature is valid
        3. Message is not expired (replay protection)
        4. Message ID has not been seen before (replay protection)

        Returns:
            Tuple of (is_valid, reason)
        """
        # REM: Check 0: Agent is not revoked
        if message.agent_id in self._revoked_agents:
            logger.warning(
                f"REM: REVOKED AGENT attempted message ::{message.agent_id}:: "
                f"message ::{message.message_id}::_Thank_You_But_No"
            )
            return False, f"Agent has been revoked: ::{message.agent_id}::"

        # REM: Check 1: Agent is registered
        secret_key = self._keys.get(message.agent_id)
        if secret_key is None:
            return False, f"Unknown agent: ::{message.agent_id}::"
        
        # REM: Check 2: Signature is valid
        if not message.verify(secret_key):
            logger.warning(
                f"REM: INVALID SIGNATURE from agent ::{message.agent_id}:: "
                f"message ::{message.message_id}::_Thank_You_But_No"
            )
            return False, "Invalid signature"
        
        # REM: Check 3: Message is not expired
        if message.is_expired():
            logger.warning(
                f"REM: EXPIRED MESSAGE from agent ::{message.agent_id}:: "
                f"message ::{message.message_id}:: age exceeded replay window_Thank_You_But_No"
            )
            return False, "Message expired (outside replay window)"
        
        # REM: Check 4: Message ID not seen before (replay attack prevention)
        # REM: Check both in-memory and Redis for distributed deployments
        store = _get_store()
        seen_in_redis = store.is_message_seen(message.message_id) if store else False

        if message.message_id in self._seen_message_ids or seen_in_redis:
            logger.warning(
                f"REM: REPLAY ATTACK DETECTED from agent ::{message.agent_id}:: "
                f"duplicate message_id ::{message.message_id}::_Thank_You_But_No"
            )
            return False, "Duplicate message ID (possible replay attack)"

        # REM: Record this message ID (both in-memory and Redis)
        self._seen_message_ids.add(message.message_id)
        self._message_timestamps[message.message_id] = datetime.now(timezone.utc)
        if store:
            store.record_message_id(message.message_id, ttl_seconds=REPLAY_WINDOW_SECONDS * 2)
        
        # REM: Cleanup old message IDs periodically (prevent unbounded growth)
        self._cleanup_old_messages()
        
        logger.info(
            f"REM: Message verified from agent ::{message.agent_id}:: "
            f"action ::{message.action}::_Thank_You"
        )
        return True, "Valid"
    
    def _cleanup_old_messages(self):
        """REM: Remove message IDs older than 2x the replay window."""
        # REM: Run cleanup every 100 messages to prevent unbounded growth
        if len(self._seen_message_ids) < 100:
            return

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=REPLAY_WINDOW_SECONDS * 2)
        old_ids = [
            msg_id for msg_id, ts in self._message_timestamps.items()
            if ts < cutoff
        ]
        for msg_id in old_ids:
            self._seen_message_ids.discard(msg_id)
            del self._message_timestamps[msg_id]

        if old_ids:
            logger.debug(f"REM: Cleaned up {len(old_ids)} expired message IDs")


class MessageSigner:
    """
    REM: Helper class for agents to sign their outgoing messages.
    """
    
    def __init__(self, agent_id: str, secret_key: bytes):
        self.agent_id = agent_id
        self.secret_key = secret_key
    
    def sign(
        self,
        action: str,
        payload: Dict[str, Any],
        target_agent: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> SignedAgentMessage:
        """
        REM: Create and sign a new message.
        """
        import uuid
        
        message = SignedAgentMessage(
            message_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            timestamp=datetime.now(timezone.utc),
            action=action,
            payload=payload,
            target_agent=target_agent,
            reply_to=reply_to,
            signature=""  # Placeholder, will be replaced
        )
        
        # REM: Generate signature
        signature = hmac.new(
            self.secret_key,
            message.get_signing_payload().encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # REM: Return new message with valid signature
        return SignedAgentMessage(
            message_id=message.message_id,
            agent_id=message.agent_id,
            timestamp=message.timestamp,
            action=action,
            payload=payload,
            target_agent=target_agent,
            reply_to=reply_to,
            signature=signature
        )


# REM: Global registry instance
key_registry = AgentKeyRegistry()
