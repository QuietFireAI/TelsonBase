# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_rate_limiting_depth.py
# REM: Depth tests for core/rate_limiting.py — pure in-memory, no external deps

import time
import pytest

from core.rate_limiting import (
    ACTION_COST_MULTIPLIERS,
    AgentRateState,
    DEFAULT_TIER_CONFIGS,
    RateLimitConfig,
    RateLimiter,
    RateLimitTier,
    RateLimitWindow,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    monkeypatch.setattr("core.persistence.get_redis", lambda: None)


@pytest.fixture
def limiter():
    return RateLimiter()


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimitTier enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimitTier:
    def test_minimal(self):
        assert RateLimitTier.MINIMAL.value == "minimal"

    def test_restricted(self):
        assert RateLimitTier.RESTRICTED.value == "restricted"

    def test_standard(self):
        assert RateLimitTier.STANDARD.value == "standard"

    def test_elevated(self):
        assert RateLimitTier.ELEVATED.value == "elevated"

    def test_unlimited(self):
        assert RateLimitTier.UNLIMITED.value == "unlimited"

    def test_five_tiers(self):
        assert len(RateLimitTier) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT_TIER_CONFIGS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDefaultTierConfigs:
    def test_all_tiers_present(self):
        for tier in RateLimitTier:
            assert tier in DEFAULT_TIER_CONFIGS

    def test_minimal_rpm(self):
        assert DEFAULT_TIER_CONFIGS[RateLimitTier.MINIMAL].requests_per_minute == 5

    def test_restricted_rpm(self):
        assert DEFAULT_TIER_CONFIGS[RateLimitTier.RESTRICTED].requests_per_minute == 20

    def test_standard_rpm(self):
        assert DEFAULT_TIER_CONFIGS[RateLimitTier.STANDARD].requests_per_minute == 60

    def test_elevated_rpm(self):
        assert DEFAULT_TIER_CONFIGS[RateLimitTier.ELEVATED].requests_per_minute == 120

    def test_unlimited_rpm_very_high(self):
        assert DEFAULT_TIER_CONFIGS[RateLimitTier.UNLIMITED].requests_per_minute == 999999

    def test_minimal_cooldown_60s(self):
        assert DEFAULT_TIER_CONFIGS[RateLimitTier.MINIMAL].cooldown_seconds == 60

    def test_unlimited_cooldown_zero(self):
        assert DEFAULT_TIER_CONFIGS[RateLimitTier.UNLIMITED].cooldown_seconds == 0


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION_COST_MULTIPLIERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestActionCostMultipliers:
    def test_read_cheap(self):
        assert ACTION_COST_MULTIPLIERS["read"] < 1.0

    def test_write_standard(self):
        assert ACTION_COST_MULTIPLIERS["write"] == 1.0

    def test_delete_expensive(self):
        assert ACTION_COST_MULTIPLIERS["delete"] > 1.0

    def test_external_most_expensive(self):
        assert ACTION_COST_MULTIPLIERS["external"] >= 3.0

    def test_approve_very_cheap(self):
        assert ACTION_COST_MULTIPLIERS["approve"] <= 0.1

    def test_execute_moderate(self):
        assert 1.0 < ACTION_COST_MULTIPLIERS["execute"] < 2.0


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimiter init
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimiterInit:
    def test_no_agents_initially(self, limiter):
        assert len(limiter._agent_states) == 0

    def test_has_tier_configs(self, limiter):
        assert len(limiter._tier_configs) == len(RateLimitTier)

    def test_trust_to_tier_mapping(self, limiter):
        assert "quarantine" in limiter._trust_to_tier
        assert "probation" in limiter._trust_to_tier
        assert "resident" in limiter._trust_to_tier
        assert "citizen" in limiter._trust_to_tier


# ═══════════════════════════════════════════════════════════════════════════════
# get_tier_for_trust_level
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetTierForTrustLevel:
    def test_quarantine_to_minimal(self, limiter):
        assert limiter.get_tier_for_trust_level("quarantine") == RateLimitTier.MINIMAL

    def test_probation_to_restricted(self, limiter):
        assert limiter.get_tier_for_trust_level("probation") == RateLimitTier.RESTRICTED

    def test_resident_to_standard(self, limiter):
        assert limiter.get_tier_for_trust_level("resident") == RateLimitTier.STANDARD

    def test_citizen_to_elevated(self, limiter):
        assert limiter.get_tier_for_trust_level("citizen") == RateLimitTier.ELEVATED

    def test_unknown_defaults_to_minimal(self, limiter):
        assert limiter.get_tier_for_trust_level("unknown") == RateLimitTier.MINIMAL

    def test_agent_maps_to_unlimited(self, limiter):
        # apex tier "agent" now maps to UNLIMITED (NM14 fix)
        assert limiter.get_tier_for_trust_level("agent") == RateLimitTier.UNLIMITED


# ═══════════════════════════════════════════════════════════════════════════════
# _get_or_create_state
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetOrCreateState:
    def test_creates_new_state(self, limiter):
        state = limiter._get_or_create_state("agent-1", RateLimitTier.STANDARD)
        assert isinstance(state, AgentRateState)

    def test_agent_id_stored(self, limiter):
        state = limiter._get_or_create_state("agent-42", RateLimitTier.STANDARD)
        assert state.agent_id == "agent-42"

    def test_tier_set(self, limiter):
        state = limiter._get_or_create_state("agent-1", RateLimitTier.ELEVATED)
        assert state.tier == RateLimitTier.ELEVATED

    def test_reuses_existing_state(self, limiter):
        s1 = limiter._get_or_create_state("agent-1", RateLimitTier.STANDARD)
        s2 = limiter._get_or_create_state("agent-1", RateLimitTier.STANDARD)
        assert s1 is s2

    def test_updates_tier_on_existing(self, limiter):
        limiter._get_or_create_state("agent-1", RateLimitTier.STANDARD)
        state = limiter._get_or_create_state("agent-1", RateLimitTier.ELEVATED)
        assert state.tier == RateLimitTier.ELEVATED


# ═══════════════════════════════════════════════════════════════════════════════
# check_rate_limit — basic allowed
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckRateLimitAllowed:
    def test_first_request_allowed(self, limiter):
        allowed, info = limiter.check_rate_limit("agent-1", "resident", "read")
        assert allowed is True

    def test_allowed_info_has_tier(self, limiter):
        allowed, info = limiter.check_rate_limit("agent-1", "resident", "read")
        assert "tier" in info

    def test_allowed_info_tier_value(self, limiter):
        allowed, info = limiter.check_rate_limit("agent-1", "resident", "read")
        assert info["tier"] == "standard"

    def test_allowed_info_has_allowed(self, limiter):
        allowed, info = limiter.check_rate_limit("agent-1", "resident", "execute")
        assert info["allowed"] is True

    def test_counter_incremented_after_allowed(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        state = limiter._agent_states["agent-1"]
        assert state.total_requests == 1

    def test_multiple_requests_increment_counter(self, limiter):
        for _ in range(5):
            limiter.check_rate_limit("agent-1", "resident", "read")
        state = limiter._agent_states["agent-1"]
        assert state.total_requests == 5


# ═══════════════════════════════════════════════════════════════════════════════
# check_rate_limit — cooldown
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckRateLimitCooldown:
    def test_denied_in_cooldown(self, limiter):
        state = limiter._get_or_create_state("agent-1", RateLimitTier.MINIMAL)
        state.cooldown_until = time.time() + 3600  # 1 hour cooldown
        allowed, info = limiter.check_rate_limit("agent-1", "quarantine", "write")
        assert allowed is False

    def test_cooldown_reason(self, limiter):
        state = limiter._get_or_create_state("agent-1", RateLimitTier.MINIMAL)
        state.cooldown_until = time.time() + 3600
        allowed, info = limiter.check_rate_limit("agent-1", "quarantine", "write")
        assert info["reason"] == "cooldown"

    def test_cooldown_has_retry_after(self, limiter):
        state = limiter._get_or_create_state("agent-1", RateLimitTier.MINIMAL)
        state.cooldown_until = time.time() + 100
        allowed, info = limiter.check_rate_limit("agent-1", "quarantine", "write")
        assert info["retry_after"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# check_rate_limit — minute limit exceeded
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckRateLimitMinuteExceeded:
    def _exhaust_minute(self, limiter, agent_id="agent-1"):
        """REM: Pre-fill the minute window counter past the limit."""
        config = DEFAULT_TIER_CONFIGS[RateLimitTier.MINIMAL]
        state = limiter._get_or_create_state(agent_id, RateLimitTier.MINIMAL)
        # Set count above minute_limit = rpm + burst_size = 5 + 2 = 7
        state.minute_window.request_count = 8
        state.hour_window.request_count = 0
        state.day_window.request_count = 0

    def test_minute_limit_denied(self, limiter):
        self._exhaust_minute(limiter)
        allowed, info = limiter.check_rate_limit("agent-1", "quarantine", "write")
        assert allowed is False

    def test_minute_limit_reason(self, limiter):
        self._exhaust_minute(limiter)
        allowed, info = limiter.check_rate_limit("agent-1", "quarantine", "write")
        assert info["reason"] == "minute_limit"

    def test_minute_limit_increments_total_limited(self, limiter):
        self._exhaust_minute(limiter)
        limiter.check_rate_limit("agent-1", "quarantine", "write")
        state = limiter._agent_states["agent-1"]
        assert state.total_limited == 1


# ═══════════════════════════════════════════════════════════════════════════════
# check_rate_limit — cost override
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckRateLimitCostOverride:
    def test_cost_override_applied(self, limiter):
        allowed, info = limiter.check_rate_limit("agent-1", "resident", "read",
                                                   cost_override=2.5)
        assert info["action_cost"] == 2.5

    def test_default_action_cost_for_unknown_action(self, limiter):
        allowed, info = limiter.check_rate_limit("agent-1", "resident", "unknown_action")
        assert info["action_cost"] == 1.0  # Default fallback


# ═══════════════════════════════════════════════════════════════════════════════
# get_agent_rate_info
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetAgentRateInfo:
    def test_returns_none_for_unknown(self, limiter):
        assert limiter.get_agent_rate_info("unknown-agent") is None

    def test_returns_dict_after_request(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        info = limiter.get_agent_rate_info("agent-1")
        assert isinstance(info, dict)

    def test_info_has_agent_id(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        info = limiter.get_agent_rate_info("agent-1")
        assert info["agent_id"] == "agent-1"

    def test_info_has_tier(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        info = limiter.get_agent_rate_info("agent-1")
        assert info["tier"] == "standard"

    def test_info_has_total_requests(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        info = limiter.get_agent_rate_info("agent-1")
        assert info["total_requests"] == 1

    def test_info_has_minute_window(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        info = limiter.get_agent_rate_info("agent-1")
        assert "minute" in info
        assert "used" in info["minute"]
        assert "limit" in info["minute"]

    def test_not_in_cooldown_initially(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        info = limiter.get_agent_rate_info("agent-1")
        assert info["in_cooldown"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# reset_agent_limits
# ═══════════════════════════════════════════════════════════════════════════════

class TestResetAgentLimits:
    def test_returns_true_for_known_agent(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        assert limiter.reset_agent_limits("agent-1") is True

    def test_returns_false_for_unknown(self, limiter):
        assert limiter.reset_agent_limits("unknown-agent") is False

    def test_state_deleted_after_reset(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        limiter.reset_agent_limits("agent-1")
        assert "agent-1" not in limiter._agent_states

    def test_next_request_succeeds_after_reset(self, limiter):
        # Exhaust limits
        state = limiter._get_or_create_state("agent-1", RateLimitTier.MINIMAL)
        state.cooldown_until = time.time() + 3600
        limiter.reset_agent_limits("agent-1")
        allowed, info = limiter.check_rate_limit("agent-1", "quarantine", "read")
        assert allowed is True


# ═══════════════════════════════════════════════════════════════════════════════
# update_tier_config
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateTierConfig:
    def test_config_updated(self, limiter):
        new_config = RateLimitConfig(
            requests_per_minute=999,
            requests_per_hour=9999,
            requests_per_day=99999,
            burst_size=100,
            cooldown_seconds=1
        )
        limiter.update_tier_config(RateLimitTier.MINIMAL, new_config)
        assert limiter._tier_configs[RateLimitTier.MINIMAL].requests_per_minute == 999


# ═══════════════════════════════════════════════════════════════════════════════
# get_all_rate_stats
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetAllRateStats:
    def test_zero_agents_initially(self, limiter):
        stats = limiter.get_all_rate_stats()
        assert stats["total_agents_tracked"] == 0

    def test_after_requests(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        limiter.check_rate_limit("agent-2", "citizen", "write")
        stats = limiter.get_all_rate_stats()
        assert stats["total_agents_tracked"] == 2

    def test_total_requests_counted(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        limiter.check_rate_limit("agent-1", "resident", "read")
        stats = limiter.get_all_rate_stats()
        assert stats["total_requests"] == 2

    def test_has_by_tier(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        stats = limiter.get_all_rate_stats()
        assert "by_tier" in stats

    def test_by_tier_counts_agents(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        limiter.check_rate_limit("agent-2", "resident", "read")
        stats = limiter.get_all_rate_stats()
        assert stats["by_tier"].get("standard", 0) == 2

    def test_has_top_requesters(self, limiter):
        limiter.check_rate_limit("agent-1", "resident", "read")
        stats = limiter.get_all_rate_stats()
        assert "top_requesters" in stats

    def test_top_requesters_sorted(self, limiter):
        for _ in range(5):
            limiter.check_rate_limit("agent-1", "resident", "read")
        limiter.check_rate_limit("agent-2", "resident", "read")
        stats = limiter.get_all_rate_stats()
        requesters = stats["top_requesters"]
        assert requesters[0]["agent_id"] == "agent-1"

    def test_agents_in_cooldown_count(self, limiter):
        state = limiter._get_or_create_state("agent-1", RateLimitTier.MINIMAL)
        state.cooldown_until = time.time() + 3600
        stats = limiter.get_all_rate_stats()
        assert stats["agents_in_cooldown"] == 1
