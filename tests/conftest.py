# TelsonBase/tests/conftest.py
# REM: =======================================================================================
# REM: PYTEST FIXTURES AND CONFIGURATION
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM: =======================================================================================

import os
import re
import hashlib
import pytest
from datetime import datetime, timezone
from typing import Generator

# REM: Set test environment before importing app modules
os.environ["MCP_API_KEY"] = "test_api_key_12345"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only"

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
    try:
        import redis as redis_lib
        r = redis_lib.from_url(os.environ["REDIS_URL"], decode_responses=True)
        r.delete("audit:chain:state", "audit:chain:entries")
    except Exception:
        pass
    try:
        from core.audit import audit, ChainState, GENESIS_HASH
        audit._chain_entries.clear()
        audit._chain_state = ChainState(
            chain_id=hashlib.sha256(
                f"telsonbase_{datetime.now(timezone.utc).isoformat()}".encode()
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
