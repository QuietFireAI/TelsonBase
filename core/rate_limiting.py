# TelsonBase/core/rate_limiting.py
# REM: =======================================================================================
# REM: PER-AGENT RATE LIMITING
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.2.0CC: New feature - Per-agent rate limiting with trust-based tiers
#
# REM: Mission Statement: Prevent resource exhaustion and abuse by applying rate limits
# REM: based on agent identity, trust level, and action type. Higher trust = more leeway.
#
# REM: Features:
# REM:   - Sliding window rate limiting
# REM:   - Trust-level based rate tiers
# REM:   - Per-action rate limits
# REM:   - Burst allowance for trusted agents
# REM:   - Rate limit headers for API responses
# REM: =======================================================================================

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from fastapi import Header, HTTPException, Request

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


class RateLimitTier(str, Enum):
    """REM: Rate limit tiers based on trust level."""
    MINIMAL = "minimal"       # Quarantine agents
    RESTRICTED = "restricted" # Probation agents
    STANDARD = "standard"     # Resident agents
    ELEVATED = "elevated"     # Citizen agents
    UNLIMITED = "unlimited"   # System agents


@dataclass
class RateLimitConfig:
    """REM: Rate limit configuration for a tier."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_size: int  # Allowed burst above normal rate
    cooldown_seconds: int  # Cooldown after hitting limit


# REM: Default rate limits per tier
DEFAULT_TIER_CONFIGS: Dict[RateLimitTier, RateLimitConfig] = {
    RateLimitTier.MINIMAL: RateLimitConfig(
        requests_per_minute=5,
        requests_per_hour=50,
        requests_per_day=200,
        burst_size=2,
        cooldown_seconds=60
    ),
    RateLimitTier.RESTRICTED: RateLimitConfig(
        requests_per_minute=20,
        requests_per_hour=200,
        requests_per_day=1000,
        burst_size=5,
        cooldown_seconds=30
    ),
    RateLimitTier.STANDARD: RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        requests_per_day=10000,
        burst_size=20,
        cooldown_seconds=10
    ),
    RateLimitTier.ELEVATED: RateLimitConfig(
        requests_per_minute=120,
        requests_per_hour=3000,
        requests_per_day=50000,
        burst_size=50,
        cooldown_seconds=5
    ),
    RateLimitTier.UNLIMITED: RateLimitConfig(
        requests_per_minute=999999,
        requests_per_hour=999999,
        requests_per_day=999999,
        burst_size=999999,
        cooldown_seconds=0
    ),
}

# REM: Action-specific multipliers (some actions are more expensive)
ACTION_COST_MULTIPLIERS: Dict[str, float] = {
    "read": 0.5,           # Reads are cheap
    "write": 1.0,          # Standard cost
    "delete": 2.0,         # Deletes cost more
    "execute": 1.5,        # Execution is moderately expensive
    "external": 3.0,       # External calls are expensive
    "approve": 0.1,        # Approvals should always be allowed
}


@dataclass
class RateLimitWindow:
    """REM: Sliding window for tracking request counts."""
    window_start: float
    request_count: int = 0
    last_request: float = 0.0


@dataclass
class AgentRateState:
    """REM: Rate limiting state for an agent."""
    agent_id: str
    tier: RateLimitTier
    minute_window: RateLimitWindow = field(default_factory=lambda: RateLimitWindow(time.time()))
    hour_window: RateLimitWindow = field(default_factory=lambda: RateLimitWindow(time.time()))
    day_window: RateLimitWindow = field(default_factory=lambda: RateLimitWindow(time.time()))
    cooldown_until: float = 0.0
    total_requests: int = 0
    total_limited: int = 0


class RateLimiter:
    """
    REM: Per-agent rate limiter with trust-based tiers.
    """

    def __init__(self):
        self._agent_states: Dict[str, AgentRateState] = {}
        self._tier_configs = DEFAULT_TIER_CONFIGS.copy()
        self._trust_to_tier: Dict[str, RateLimitTier] = {
            "quarantine": RateLimitTier.MINIMAL,
            "probation": RateLimitTier.RESTRICTED,
            "resident": RateLimitTier.STANDARD,
            "citizen": RateLimitTier.ELEVATED,
        }

    def _get_or_create_state(self, agent_id: str, tier: RateLimitTier) -> AgentRateState:
        """REM: Get or create rate limit state for an agent."""
        if agent_id not in self._agent_states:
            self._agent_states[agent_id] = AgentRateState(
                agent_id=agent_id,
                tier=tier
            )
        else:
            # REM: Update tier if it changed (promotion/demotion)
            self._agent_states[agent_id].tier = tier
        return self._agent_states[agent_id]

    def _slide_window(self, window: RateLimitWindow, window_seconds: float) -> None:
        """REM: Slide the window and reset count if needed."""
        now = time.time()
        if now - window.window_start >= window_seconds:
            window.window_start = now
            window.request_count = 0

    def get_tier_for_trust_level(self, trust_level: str) -> RateLimitTier:
        """REM: Map trust level to rate limit tier."""
        return self._trust_to_tier.get(trust_level, RateLimitTier.MINIMAL)

    def check_rate_limit(
        self,
        agent_id: str,
        trust_level: str = "quarantine",
        action: str = "execute",
        cost_override: Optional[float] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        REM: Check if an agent is within rate limits.

        Args:
            agent_id: The agent making the request
            trust_level: Agent's current trust level
            action: The type of action being performed
            cost_override: Optional override for action cost

        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        tier = self.get_tier_for_trust_level(trust_level)
        config = self._tier_configs[tier]
        state = self._get_or_create_state(agent_id, tier)
        now = time.time()

        # REM: Check cooldown
        if now < state.cooldown_until:
            remaining = int(state.cooldown_until - now)
            logger.warning(
                f"REM: Rate limit: ::{agent_id}:: in cooldown for {remaining}s_Thank_You_But_No"
            )
            return False, {
                "allowed": False,
                "reason": "cooldown",
                "retry_after": remaining,
                "tier": tier.value
            }

        # REM: Calculate action cost
        cost = cost_override if cost_override is not None else ACTION_COST_MULTIPLIERS.get(action, 1.0)

        # REM: Slide windows
        self._slide_window(state.minute_window, 60)
        self._slide_window(state.hour_window, 3600)
        self._slide_window(state.day_window, 86400)

        # REM: Check limits (with burst allowance)
        minute_limit = config.requests_per_minute + config.burst_size
        hour_limit = config.requests_per_hour + (config.burst_size * 10)
        day_limit = config.requests_per_day + (config.burst_size * 100)

        effective_minute = state.minute_window.request_count * cost
        effective_hour = state.hour_window.request_count * cost
        effective_day = state.day_window.request_count * cost

        rate_info = {
            "tier": tier.value,
            "minute": {"used": int(effective_minute), "limit": minute_limit},
            "hour": {"used": int(effective_hour), "limit": hour_limit},
            "day": {"used": int(effective_day), "limit": day_limit},
            "action_cost": cost
        }

        # REM: Check each window
        if effective_minute >= minute_limit:
            state.cooldown_until = now + config.cooldown_seconds
            state.total_limited += 1
            self._log_rate_limit_hit(agent_id, "minute", rate_info)
            return False, {
                "allowed": False,
                "reason": "minute_limit",
                "retry_after": config.cooldown_seconds,
                **rate_info
            }

        if effective_hour >= hour_limit:
            state.cooldown_until = now + config.cooldown_seconds * 2
            state.total_limited += 1
            self._log_rate_limit_hit(agent_id, "hour", rate_info)
            return False, {
                "allowed": False,
                "reason": "hour_limit",
                "retry_after": config.cooldown_seconds * 2,
                **rate_info
            }

        if effective_day >= day_limit:
            state.cooldown_until = now + config.cooldown_seconds * 10
            state.total_limited += 1
            self._log_rate_limit_hit(agent_id, "day", rate_info)
            return False, {
                "allowed": False,
                "reason": "day_limit",
                "retry_after": config.cooldown_seconds * 10,
                **rate_info
            }

        # REM: Request allowed - update counters
        state.minute_window.request_count += 1
        state.minute_window.last_request = now
        state.hour_window.request_count += 1
        state.hour_window.last_request = now
        state.day_window.request_count += 1
        state.day_window.last_request = now
        state.total_requests += 1

        return True, {
            "allowed": True,
            **rate_info
        }

    def _log_rate_limit_hit(self, agent_id: str, window: str, info: Dict) -> None:
        """REM: Log and audit rate limit hit."""
        logger.warning(
            f"REM: Rate limit hit: ::{agent_id}:: exceeded {window} limit_Thank_You_But_No"
        )
        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Rate limit exceeded for agent: {agent_id}",
            actor=agent_id,
            details={
                "window": window,
                "tier": info["tier"],
                "used": info[window]["used"],
                "limit": info[window]["limit"]
            },
            qms_status="Thank_You_But_No"
        )

    def get_agent_rate_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """REM: Get current rate limit info for an agent."""
        if agent_id not in self._agent_states:
            return None

        state = self._agent_states[agent_id]
        config = self._tier_configs[state.tier]
        now = time.time()

        return {
            "agent_id": agent_id,
            "tier": state.tier.value,
            "in_cooldown": now < state.cooldown_until,
            "cooldown_remaining": max(0, int(state.cooldown_until - now)),
            "minute": {
                "used": state.minute_window.request_count,
                "limit": config.requests_per_minute,
                "resets_in": max(0, int(60 - (now - state.minute_window.window_start)))
            },
            "hour": {
                "used": state.hour_window.request_count,
                "limit": config.requests_per_hour,
                "resets_in": max(0, int(3600 - (now - state.hour_window.window_start)))
            },
            "day": {
                "used": state.day_window.request_count,
                "limit": config.requests_per_day,
                "resets_in": max(0, int(86400 - (now - state.day_window.window_start)))
            },
            "total_requests": state.total_requests,
            "total_limited": state.total_limited
        }

    def reset_agent_limits(self, agent_id: str, reset_by: str = "system") -> bool:
        """REM: Reset rate limits for an agent (emergency override)."""
        if agent_id in self._agent_states:
            del self._agent_states[agent_id]

            logger.warning(
                f"REM: Rate limits reset for ::{agent_id}:: by ::{reset_by}::_Thank_You"
            )
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Rate limits manually reset for agent: {agent_id}",
                actor=reset_by,
                resource=agent_id,
                qms_status="Thank_You"
            )
            return True
        return False

    def update_tier_config(
        self,
        tier: RateLimitTier,
        config: RateLimitConfig,
        updated_by: str = "system"
    ) -> None:
        """REM: Update rate limit configuration for a tier."""
        self._tier_configs[tier] = config

        logger.info(
            f"REM: Rate limit config updated for tier ::{tier.value}:: "
            f"by ::{updated_by}::_Thank_You"
        )
        audit.log(
            AuditEventType.SECURITY_ALERT,
            f"Rate limit configuration updated for tier: {tier.value}",
            actor=updated_by,
            details={
                "requests_per_minute": config.requests_per_minute,
                "requests_per_hour": config.requests_per_hour,
                "requests_per_day": config.requests_per_day
            },
            qms_status="Thank_You"
        )

    def get_all_rate_stats(self) -> Dict[str, Any]:
        """REM: Get rate limiting statistics for all agents."""
        stats = {
            "total_agents_tracked": len(self._agent_states),
            "agents_in_cooldown": 0,
            "total_requests": 0,
            "total_limited": 0,
            "by_tier": defaultdict(int),
            "top_requesters": []
        }

        now = time.time()
        agent_stats = []

        for agent_id, state in self._agent_states.items():
            stats["total_requests"] += state.total_requests
            stats["total_limited"] += state.total_limited
            stats["by_tier"][state.tier.value] += 1

            if now < state.cooldown_until:
                stats["agents_in_cooldown"] += 1

            agent_stats.append({
                "agent_id": agent_id,
                "total_requests": state.total_requests,
                "tier": state.tier.value
            })

        # REM: Top 5 requesters
        agent_stats.sort(key=lambda x: x["total_requests"], reverse=True)
        stats["top_requesters"] = agent_stats[:5]
        stats["by_tier"] = dict(stats["by_tier"])

        return stats


# REM: Global rate limiter instance
rate_limiter = RateLimiter()


# REM: =======================================================================================
# REM: FASTAPI DEPENDENCY — PER-AGENT RATE LIMIT GATE
# REM: =======================================================================================
# REM: Apply to any endpoint that agents call directly (task dispatch, tool execute,
# REM: federated message, LLM generate/chat). Human-facing endpoints skip this check.
# REM:
# REM: Agents SHOULD include these headers on every request:
# REM:   X-Agent-ID:    agent's canonical identifier (e.g. "backup_agent_prod")
# REM:   X-Agent-Trust: agent's current trust level (quarantine/probation/resident/citizen)
# REM:
# REM: If X-Agent-ID is absent the dependency is a no-op (human user, handled by the
# REM: IP-based token-bucket in core/middleware.py).
# REM: =======================================================================================

async def agent_rate_limit(
    x_agent_id: Optional[str] = Header(None, alias="X-Agent-ID"),
    x_agent_trust: Optional[str] = Header(None, alias="X-Agent-Trust"),
    x_agent_action: Optional[str] = Header(None, alias="X-Agent-Action"),
) -> None:
    """
    REM: FastAPI dependency — enforce per-agent rate limits.

    Raises HTTP 429 if the agent has exceeded its tier's sliding-window quota.
    No-op when X-Agent-ID header is absent (human/API-key request).
    """
    if not x_agent_id:
        return  # Not an agent call — skip

    trust_level = x_agent_trust or "quarantine"
    action = x_agent_action or "execute"

    allowed, info = rate_limiter.check_rate_limit(
        agent_id=x_agent_id,
        trust_level=trust_level,
        action=action,
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Agent rate limit exceeded",
                "qms_status": "Thank_You_But_No",
                "agent_id": x_agent_id,
                "tier": info.get("tier"),
                "retry_after": info.get("retry_after"),
                "reason": info.get("reason"),
            },
            headers={"Retry-After": str(info.get("retry_after", 60))},
        )
