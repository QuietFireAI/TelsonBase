# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# TelsonBase/tests/conftest.py
# REM: =======================================================================================
# REM: PYTEST FIXTURES AND CONFIGURATION
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM: =======================================================================================

import os
import re
import sys
import types
import hashlib
import pytest
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import MagicMock

# REM: Install celery stub before any test file is imported.
# REM: Agent depth tests also install stubs but run after conftest; this
# REM: ensures the stub is a real types.ModuleType (not MagicMock) so that
# REM: Python's submodule import machinery works (celery.__path__ required).
if "celery" not in sys.modules:
    _celery = types.ModuleType("celery")
    _celery.__path__ = []
    _celery.__package__ = "celery"
    _celery.shared_task = lambda *args, **kwargs: (lambda f: f)
    _celery.Celery = MagicMock()
    sys.modules["celery"] = _celery
    _celery_sched = types.ModuleType("celery.schedules")
    _celery_sched.crontab = MagicMock()
    sys.modules["celery.schedules"] = _celery_sched
    _celery_utils = types.ModuleType("celery.utils")
    sys.modules["celery.utils"] = _celery_utils
    _celery_utils_log = types.ModuleType("celery.utils.log")
    _celery_utils_log.get_task_logger = MagicMock(return_value=MagicMock())
    sys.modules["celery.utils.log"] = _celery_utils_log
    sys.modules["celery.signals"] = types.ModuleType("celery.signals")

# REM: Set test environment before importing app modules
os.environ["MCP_API_KEY"] = "test_api_key_12345"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only"
# REM: H4 fix: secure_storage now raises at startup if key is not set.
# REM: Provide a deterministic test key so tests don't use ephemeral keys.
os.environ.setdefault("CLAWCOAT_ENCRYPTION_KEY", "test_encryption_key_32bytes_____x")

# REM: Use DB 15 for test isolation, but preserve the real Redis hostname so tests
# REM: work both on the dev machine (localhost:6379) and inside Docker (redis:6379).
_real_redis = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
os.environ["REDIS_URL"] = re.sub(r'/\d+$', '/15', _real_redis)

os.environ["LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def api_key() -> str:
    """REM: Test API key."""
    return "test_api_key_12345"


@pytest.fixture(scope="session")
def auth_headers(api_key: str) -> dict:
    """REM: Authentication headers for API requests."""
    return {"X-API-Key": api_key}


@pytest.fixture(scope="function")
def client() -> Generator:
    """REM: FastAPI test client."""
    # REM: Reset rate limiter between tests to prevent 429s in full suite
    try:
        from core.middleware import rate_limiter
        rate_limiter._buckets.clear()
    except (ImportError, AttributeError):
        pass

    # REM: v7.4.0CC — Flush audit chain state from Redis DB 15 and reset the
    # in-memory singleton to prevent chain_break across test runs. Without this,
    # leftover entries from a prior session cause verify_chain to fail because
    # the first new-session entry's previous_hash doesn't match the last old entry.
    # REM: v11.0.2 — Also flush RBAC Redis state so first-user detection works
    # correctly in tests that register users. RBAC write-through persistence means
    # users from prior tests accumulate in Redis and contaminate first-user logic.
    try:
        import redis as redis_lib
        r = redis_lib.from_url(os.environ["REDIS_URL"], decode_responses=True)
        r.delete("audit:chain:state", "audit:chain:entries")
        r.delete("security:rbac_users", "security:rbac_api_keys", "security:rbac_username_idx")
        # REM: Flush Redis-backed rate limit bucket so tests don't 429 each other.
        # The in-memory _buckets.clear() above only covers the fallback path; when
        # Redis is available the Lua token-bucket key persists across tests.
        for k in r.keys("ratelimit:*"):
            r.delete(k)
    except Exception:
        pass
    # REM: Reset in-memory RBAC state to match flushed Redis state
    try:
        from core.rbac import rbac_manager
        rbac_manager._users.clear()
        rbac_manager._sessions.clear()
        rbac_manager._api_key_to_user.clear()
    except (ImportError, AttributeError):
        pass
    try:
        from core.audit import audit, ChainState, GENESIS_HASH
        audit._chain_entries.clear()
        audit._chain_state = ChainState(
            chain_id=hashlib.sha256(
                f"clawcoat_{datetime.now(timezone.utc).isoformat()}".encode()
            ).hexdigest()[:16],
            created_at=datetime.now(timezone.utc).isoformat()
        )
    except (ImportError, AttributeError):
        pass

    from main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def mock_redis(mocker):
    """REM: Mock Redis for unit tests that don't need real Redis."""
    mock = mocker.MagicMock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
    mock.keys.return_value = []
    mock.hget.return_value = None
    mock.hset.return_value = True
    mock.hgetall.return_value = {}
    mock.sadd.return_value = 1
    mock.smembers.return_value = set()
    mock.srem.return_value = 1
    mock.zadd.return_value = 1
    mock.zrange.return_value = []
    mock.exists.return_value = 0
    mock.setex.return_value = True
    mock.rpush.return_value = 1
    mock.lrange.return_value = []
    return mock


@pytest.fixture
def sample_agent_request() -> dict:
    """REM: Sample agent request for testing."""
    return {
        "request_id": "test-req-001",
        "action": "test_action",
        "payload": {"key": "value"},
        "requester": "test_user",
        "priority": "normal",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def sample_capability_set() -> list:
    """REM: Sample capability set for testing."""
    return [
        "filesystem.read:/data/*",
        "filesystem.write:/app/backups/*",
        "external.none"
    ]


@pytest.fixture
def sample_anomaly() -> dict:
    """REM: Sample anomaly record for testing."""
    return {
        "anomaly_id": "ANOM-000001",
        "agent_id": "test_agent",
        "anomaly_type": "rate_spike",
        "severity": "medium",
        "description": "Test anomaly for unit testing",
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "evidence": {"test": "data"},
        "requires_human_review": False,
        "resolved": False
    }


@pytest.fixture
def sample_approval_request() -> dict:
    """REM: Sample approval request for testing."""
    return {
        "request_id": "APPR-TEST001",
        "agent_id": "test_agent",
        "action": "delete_data",
        "description": "Test deletion request",
        "payload": {"file": "/data/test.txt"},
        "priority": "high",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
