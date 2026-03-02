# TelsonBase/core/delegation.py
# REM: =======================================================================================
# REM: AGENT-TO-AGENT CAPABILITY DELEGATION
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.2.0CC: New feature - Secure capability delegation between agents
#
# REM: Mission Statement: Enable agents to delegate specific capabilities to other agents
# REM: with proper constraints. Delegations are time-limited, revocable, and audited.
#
# REM: Security Properties:
# REM:   - Cannot delegate more than you have (attenuation only)
# REM:   - Time-bounded delegations with auto-expiry
# REM:   - Delegation chain depth limits
# REM:   - Revocation propagates down the chain
# REM:   - Full audit trail
# REM: =======================================================================================

import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


class DelegationStatus(str, Enum):
    """REM: Status of a delegation."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


@dataclass
class CapabilityDelegation:
    """REM: A capability delegation from one agent to another."""
    delegation_id: str
    grantor_id: str           # Agent granting the capability
    grantee_id: str           # Agent receiving the capability
    capability: str           # The capability being delegated
    constraints: Dict[str, Any]  # Additional constraints
    created_at: datetime
    expires_at: datetime
    status: DelegationStatus = DelegationStatus.ACTIVE
    parent_delegation_id: Optional[str] = None  # If this is a sub-delegation
    delegation_depth: int = 0  # How deep in the chain
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    revocation_reason: Optional[str] = None

    def is_valid(self) -> bool:
        """REM: Check if delegation is currently valid."""
        if self.status != DelegationStatus.ACTIVE:
            return False
        now = datetime.now(timezone.utc)
        return self.created_at <= now < self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """REM: Convert to dictionary for serialization."""
        return {
            "delegation_id": self.delegation_id,
            "grantor_id": self.grantor_id,
            "grantee_id": self.grantee_id,
            "capability": self.capability,
            "constraints": self.constraints,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "status": self.status.value,
            "parent_delegation_id": self.parent_delegation_id,
            "delegation_depth": self.delegation_depth,
            "is_valid": self.is_valid()
        }


class DelegationManager:
    """
    REM: Manages capability delegations between agents.
    REM: v5.3.0CC — Redis-backed persistence. Delegations survive container restarts.
    REM: In-memory indexes (_by_grantor, _by_grantee) are rebuilt from Redis on load.
    """

    MAX_DELEGATION_DEPTH = 3  # Maximum chain depth
    MAX_DELEGATION_DURATION_HOURS = 24  # Maximum delegation duration
    MAX_DELEGATIONS_PER_AGENT = 50  # Maximum active delegations per agent
    _REDIS_PREFIX = "delegation:"

    def __init__(self):
        self._delegations: Dict[str, CapabilityDelegation] = {}
        self._by_grantor: Dict[str, Set[str]] = {}  # grantor_id -> delegation_ids
        self._by_grantee: Dict[str, Set[str]] = {}  # grantee_id -> delegation_ids
        self._redis = None

    def _get_redis(self):
        """REM: v5.3.0CC — Lazy Redis client."""
        if self._redis is None:
            try:
                import redis as _redis
                from core.config import get_settings
                self._redis = _redis.Redis.from_url(
                    get_settings().redis_url, decode_responses=True
                )
                self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    def _persist_delegation(self, delegation: CapabilityDelegation):
        """REM: v5.3.0CC — Write a single delegation to Redis with TTL."""
        client = self._get_redis()
        if not client:
            return
        try:
            data = json.dumps(delegation.to_dict(), default=str)
            # REM: TTL = time until expiry + 1 hour buffer for audit
            now = datetime.now(timezone.utc)
            ttl = max(int((delegation.expires_at - now).total_seconds()) + 3600, 3600)
            client.setex(
                f"{self._REDIS_PREFIX}{delegation.delegation_id}",
                ttl,
                data
            )
        except Exception as e:
            logger.warning(f"REM: Delegation persist failed: {e}_Thank_You_But_No")

    def _delete_from_redis(self, delegation_id: str):
        """REM: v5.3.0CC — Remove a delegation from Redis."""
        client = self._get_redis()
        if client:
            try:
                client.delete(f"{self._REDIS_PREFIX}{delegation_id}")
            except Exception:
                pass

    def load_from_redis(self) -> int:
        """
        REM: v5.3.0CC — Restore delegations from Redis on startup.
        REM: Rebuilds in-memory indexes from persisted data.
        Returns count of delegations loaded.
        """
        client = self._get_redis()
        if not client:
            logger.info("REM: Redis unavailable — delegation persistence disabled_Thank_You")
            return 0

        count = 0
        try:
            for key in client.scan_iter(match=f"{self._REDIS_PREFIX}*", count=100):
                data = client.get(key)
                if not data:
                    continue
                try:
                    d = json.loads(data)
                    delegation = CapabilityDelegation(
                        delegation_id=d["delegation_id"],
                        grantor_id=d["grantor_id"],
                        grantee_id=d["grantee_id"],
                        capability=d["capability"],
                        constraints=d.get("constraints", {}),
                        created_at=datetime.fromisoformat(d["created_at"]),
                        expires_at=datetime.fromisoformat(d["expires_at"]),
                        status=DelegationStatus(d.get("status", "active")),
                        parent_delegation_id=d.get("parent_delegation_id"),
                        delegation_depth=d.get("delegation_depth", 0),
                    )
                    self._delegations[delegation.delegation_id] = delegation
                    # REM: Rebuild indexes
                    self._by_grantor.setdefault(delegation.grantor_id, set()).add(delegation.delegation_id)
                    self._by_grantee.setdefault(delegation.grantee_id, set()).add(delegation.delegation_id)
                    count += 1
                except (KeyError, ValueError) as e:
                    logger.warning(f"REM: Skipping corrupt delegation record: {e}")
        except Exception as e:
            logger.error(f"REM: Delegation restore failed: {e}_Thank_You_But_No")

        if count > 0:
            logger.info(f"REM: Restored {count} delegations from Redis_Thank_You")
        return count

    def delegate(
        self,
        grantor_id: str,
        grantee_id: str,
        capability: str,
        grantor_capabilities: List[str],
        duration_hours: float = 1.0,
        constraints: Optional[Dict[str, Any]] = None,
        parent_delegation_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        REM: Create a capability delegation from grantor to grantee.

        Args:
            grantor_id: Agent granting the capability
            grantee_id: Agent receiving the capability
            capability: The capability to delegate
            grantor_capabilities: Current capabilities of the grantor
            duration_hours: How long the delegation lasts
            constraints: Additional constraints on the delegation
            parent_delegation_id: If this is a sub-delegation

        Returns:
            Tuple of (success, message, delegation_id)
        """
        now = datetime.now(timezone.utc)
        constraints = constraints or {}

        # REM: Self-delegation check
        if grantor_id == grantee_id:
            return False, "Cannot delegate to self", None

        # REM: Check grantor has the capability to delegate
        if not self._grantor_has_capability(grantor_id, capability, grantor_capabilities):
            logger.warning(
                f"REM: Delegation denied - ::{grantor_id}:: lacks ::{capability}::_Thank_You_But_No"
            )
            return False, f"Grantor does not have capability: {capability}", None

        # REM: Check delegation depth
        depth = 0
        if parent_delegation_id:
            parent = self._delegations.get(parent_delegation_id)
            if not parent:
                return False, "Parent delegation not found", None
            if not parent.is_valid():
                return False, "Parent delegation is no longer valid", None
            depth = parent.delegation_depth + 1
            if depth > self.MAX_DELEGATION_DEPTH:
                logger.warning(
                    f"REM: Delegation denied - chain too deep ({depth})_Thank_You_But_No"
                )
                return False, f"Delegation chain too deep (max {self.MAX_DELEGATION_DEPTH})", None

        # REM: Check duration limit
        if duration_hours > self.MAX_DELEGATION_DURATION_HOURS:
            duration_hours = self.MAX_DELEGATION_DURATION_HOURS

        # REM: Check delegation count limit
        active_count = len([
            d for d in self._by_grantor.get(grantor_id, set())
            if self._delegations.get(d, CapabilityDelegation(
                "", "", "", "", {}, now, now, DelegationStatus.REVOKED
            )).is_valid()
        ])
        if active_count >= self.MAX_DELEGATIONS_PER_AGENT:
            return False, f"Maximum delegations reached ({self.MAX_DELEGATIONS_PER_AGENT})", None

        # REM: Create delegation
        delegation_id = f"del_{uuid.uuid4().hex[:12]}"
        delegation = CapabilityDelegation(
            delegation_id=delegation_id,
            grantor_id=grantor_id,
            grantee_id=grantee_id,
            capability=capability,
            constraints=constraints,
            created_at=now,
            expires_at=now + timedelta(hours=duration_hours),
            parent_delegation_id=parent_delegation_id,
            delegation_depth=depth
        )

        self._delegations[delegation_id] = delegation

        # REM: Index by grantor and grantee
        if grantor_id not in self._by_grantor:
            self._by_grantor[grantor_id] = set()
        self._by_grantor[grantor_id].add(delegation_id)

        if grantee_id not in self._by_grantee:
            self._by_grantee[grantee_id] = set()
        self._by_grantee[grantee_id].add(delegation_id)

        # REM: v5.3.0CC — Persist to Redis
        self._persist_delegation(delegation)

        logger.info(
            f"REM: Capability delegated - ::{grantor_id}:: -> ::{grantee_id}:: "
            f"capability: ::{capability}:: expires: {delegation.expires_at}_Thank_You"
        )

        audit.log(
            AuditEventType.CAPABILITY_CHECK,
            f"Capability delegated: {capability}",
            actor=grantor_id,
            resource=grantee_id,
            details={
                "delegation_id": delegation_id,
                "capability": capability,
                "duration_hours": duration_hours,
                "depth": depth
            },
            qms_status="Thank_You"
        )

        return True, "Delegation created", delegation_id

    def _grantor_has_capability(
        self,
        grantor_id: str,
        capability: str,
        grantor_capabilities: List[str]
    ) -> bool:
        """REM: Check if grantor has the capability to delegate."""
        # REM: Check direct capabilities
        for cap in grantor_capabilities:
            if self._capability_matches(cap, capability):
                return True

        # REM: Check delegated capabilities
        for delegation_id in self._by_grantee.get(grantor_id, set()):
            delegation = self._delegations.get(delegation_id)
            if delegation and delegation.is_valid():
                if self._capability_matches(delegation.capability, capability):
                    return True

        return False

    def _capability_matches(self, held: str, needed: str) -> bool:
        """REM: Check if held capability satisfies needed capability."""
        # REM: Exact match
        if held == needed:
            return True

        # REM: Wildcard matching
        held_parts = held.split(".")
        needed_parts = needed.split(".")

        if len(held_parts) != len(needed_parts):
            return False

        for h, n in zip(held_parts, needed_parts):
            if h == "*":
                continue
            h_base, h_resource = h.split(":") if ":" in h else (h, "")
            n_base, n_resource = n.split(":") if ":" in n else (n, "")

            if h_base != n_base:
                return False

            if h_resource and n_resource:
                if h_resource.endswith("*"):
                    if not n_resource.startswith(h_resource[:-1]):
                        return False
                elif h_resource != n_resource:
                    return False

        return True

    def revoke(
        self,
        delegation_id: str,
        revoked_by: str,
        reason: str = "Manual revocation"
    ) -> Tuple[bool, str]:
        """
        REM: Revoke a delegation and all sub-delegations.

        Args:
            delegation_id: The delegation to revoke
            revoked_by: Who is revoking
            reason: Reason for revocation

        Returns:
            Tuple of (success, message)
        """
        if delegation_id not in self._delegations:
            return False, "Delegation not found"

        delegation = self._delegations[delegation_id]
        if delegation.status == DelegationStatus.REVOKED:
            return False, "Already revoked"

        now = datetime.now(timezone.utc)
        revoked_count = self._revoke_chain(delegation_id, revoked_by, reason, now)

        logger.warning(
            f"REM: Delegation revoked - ::{delegation_id}:: by ::{revoked_by}:: "
            f"Reason: ::{reason}:: (chain: {revoked_count})_Thank_You"
        )

        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Delegation revoked: {delegation_id}",
            actor=revoked_by,
            details={
                "delegation_id": delegation_id,
                "reason": reason,
                "chain_revoked": revoked_count
            },
            qms_status="Thank_You"
        )

        return True, f"Revoked {revoked_count} delegation(s)"

    def _revoke_chain(
        self,
        delegation_id: str,
        revoked_by: str,
        reason: str,
        now: datetime
    ) -> int:
        """REM: Revoke a delegation and all its children."""
        delegation = self._delegations.get(delegation_id)
        if not delegation or delegation.status == DelegationStatus.REVOKED:
            return 0

        delegation.status = DelegationStatus.REVOKED
        delegation.revoked_at = now
        delegation.revoked_by = revoked_by
        delegation.revocation_reason = reason
        # REM: v5.3.0CC — Update Redis with revoked status
        self._persist_delegation(delegation)
        count = 1

        # REM: Find and revoke child delegations
        for did, d in self._delegations.items():
            if d.parent_delegation_id == delegation_id:
                count += self._revoke_chain(did, revoked_by, "Parent revoked", now)

        return count

    def get_delegation_ids_by_grantor(self, agent_id: str) -> Set[str]:
        """REM: v5.3.0CC — Public accessor for delegation IDs where agent is grantor."""
        return set(self._by_grantor.get(agent_id, set()))

    def get_delegation_ids_by_grantee(self, agent_id: str) -> Set[str]:
        """REM: v5.3.0CC — Public accessor for delegation IDs where agent is grantee."""
        return set(self._by_grantee.get(agent_id, set()))

    def get_grantee_capabilities(self, grantee_id: str) -> List[Dict[str, Any]]:
        """REM: Get all active delegated capabilities for a grantee."""
        capabilities = []

        for delegation_id in self._by_grantee.get(grantee_id, set()):
            delegation = self._delegations.get(delegation_id)
            if delegation and delegation.is_valid():
                capabilities.append({
                    "delegation_id": delegation.delegation_id,
                    "capability": delegation.capability,
                    "grantor_id": delegation.grantor_id,
                    "expires_at": delegation.expires_at.isoformat(),
                    "constraints": delegation.constraints
                })

        return capabilities

    def get_grantor_delegations(self, grantor_id: str) -> List[Dict[str, Any]]:
        """REM: Get all delegations made by a grantor."""
        delegations = []

        for delegation_id in self._by_grantor.get(grantor_id, set()):
            delegation = self._delegations.get(delegation_id)
            if delegation:
                delegations.append(delegation.to_dict())

        return delegations

    def check_delegated_permission(
        self,
        agent_id: str,
        capability: str
    ) -> Tuple[bool, Optional[str]]:
        """
        REM: Check if agent has permission via delegation.

        Returns:
            Tuple of (has_permission, delegation_id)
        """
        for delegation_id in self._by_grantee.get(agent_id, set()):
            delegation = self._delegations.get(delegation_id)
            if delegation and delegation.is_valid():
                if self._capability_matches(delegation.capability, capability):
                    return True, delegation_id

        return False, None

    def cleanup_expired(self) -> int:
        """REM: Mark expired delegations and cascade to children (v5.3.0CC)."""
        now = datetime.now(timezone.utc)
        count = 0
        newly_expired = []

        for delegation in self._delegations.values():
            if delegation.status == DelegationStatus.ACTIVE:
                if now >= delegation.expires_at:
                    delegation.status = DelegationStatus.EXPIRED
                    count += 1
                    newly_expired.append(delegation.delegation_id)

        # REM: v5.3.0CC — Cascade: expire children of newly expired parents
        for parent_id in newly_expired:
            count += self._expire_children(parent_id)

        if count > 0:
            logger.info(f"REM: Cleaned up {count} expired delegations_Thank_You")

        return count

    def _expire_children(self, parent_id: str) -> int:
        """REM: v5.3.0CC — Recursively expire child delegations when parent expires."""
        count = 0
        for d in self._delegations.values():
            if d.parent_delegation_id == parent_id and d.status == DelegationStatus.ACTIVE:
                d.status = DelegationStatus.EXPIRED
                count += 1
                count += self._expire_children(d.delegation_id)
        return count

    def get_delegation_stats(self) -> Dict[str, Any]:
        """REM: Get delegation statistics."""
        now = datetime.now(timezone.utc)
        active = 0
        expired = 0
        revoked = 0
        by_depth = {}

        for delegation in self._delegations.values():
            if delegation.status == DelegationStatus.ACTIVE:
                if delegation.is_valid():
                    active += 1
                else:
                    expired += 1
            elif delegation.status == DelegationStatus.EXPIRED:
                expired += 1
            elif delegation.status == DelegationStatus.REVOKED:
                revoked += 1

            depth_key = str(delegation.delegation_depth)
            by_depth[depth_key] = by_depth.get(depth_key, 0) + 1

        return {
            "total_delegations": len(self._delegations),
            "active": active,
            "expired": expired,
            "revoked": revoked,
            "by_depth": by_depth,
            "unique_grantors": len(self._by_grantor),
            "unique_grantees": len(self._by_grantee)
        }


# REM: Global delegation manager instance
delegation_manager = DelegationManager()
