# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_persistence_depth.py
# REM: Coverage depth tests for core/persistence.py
# REM: Pure-method tests run everywhere.
# REM: Redis-backed tests run in integration env (Redis available) and skip gracefully otherwise.

import json
import pytest
from datetime import datetime, timezone

from core.persistence import (
    RedisStore, SigningKeyStore, CapabilityStore, AnomalyStore,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def redis_available():
    """Returns True if Redis is reachable; skips the test if not."""
    store = RedisStore("ping_check")
    if not store.ping():
        pytest.skip("Redis not available in this environment")
    return True


@pytest.fixture
def signing_store():
    return SigningKeyStore()


@pytest.fixture
def cap_store():
    return CapabilityStore()


@pytest.fixture
def anomaly_store():
    return AnomalyStore()


# ═══════════════════════════════════════════════════════════════════════════════
# RedisStore — pure helper methods (no Redis connection needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRedisStoreKey:
    def test_key_single_part(self):
        store = RedisStore("myprefix")
        assert store._key("foo") == "myprefix:foo"

    def test_key_multiple_parts(self):
        store = RedisStore("myprefix")
        assert store._key("a", "b", "c") == "myprefix:a:b:c"

    def test_key_prefix_stored(self):
        store = RedisStore("test_prefix")
        assert store.prefix == "test_prefix"


class TestRedisStoreSerialize:
    def test_serialize_dict(self):
        store = RedisStore("test")
        result = store._serialize({"key": "value", "num": 42})
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["num"] == 42

    def test_serialize_list(self):
        store = RedisStore("test")
        result = store._serialize([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_serialize_set_becomes_list(self):
        store = RedisStore("test")
        result = store._serialize({"a", "b", "c"})
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert set(parsed) == {"a", "b", "c"}

    def test_serialize_bytes_becomes_base64(self):
        store = RedisStore("test")
        data = b"hello bytes"
        result = store._serialize(data)
        import base64
        decoded = base64.b64decode(result.encode())
        assert decoded == data

    def test_serialize_datetime(self):
        store = RedisStore("test")
        now = datetime.now(timezone.utc)
        result = store._serialize(now)
        assert "T" in result  # ISO format

    def test_serialize_string(self):
        store = RedisStore("test")
        result = store._serialize("hello")
        assert json.loads(result) == "hello"

    def test_serialize_integer(self):
        store = RedisStore("test")
        result = store._serialize(42)
        assert json.loads(result) == 42

    def test_serialize_none(self):
        store = RedisStore("test")
        result = store._serialize(None)
        assert json.loads(result) is None


class TestRedisStoreDeserialize:
    def test_deserialize_dict(self):
        store = RedisStore("test")
        data = json.dumps({"key": "val"})
        result = store._deserialize(data)
        assert result == {"key": "val"}

    def test_deserialize_none_returns_none(self):
        store = RedisStore("test")
        assert store._deserialize(None) is None

    def test_deserialize_list(self):
        store = RedisStore("test")
        data = json.dumps([1, 2, 3])
        result = store._deserialize(data)
        assert result == [1, 2, 3]

    def test_deserialize_string(self):
        store = RedisStore("test")
        data = json.dumps("hello")
        result = store._deserialize(data)
        assert result == "hello"

    def test_deserialize_integer(self):
        store = RedisStore("test")
        data = json.dumps(99)
        result = store._deserialize(data)
        assert result == 99


# ═══════════════════════════════════════════════════════════════════════════════
# RedisStore.ping — tests connectivity (Redis-dependent)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRedisStorePing:
    def test_ping_returns_bool(self, redis_available):
        store = RedisStore("test")
        result = store.ping()
        assert isinstance(result, bool)
        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# SigningKeyStore (Redis-backed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSigningKeyStore:
    def test_store_and_get_key(self, redis_available, signing_store):
        key_bytes = b"test_signing_key_abc123"
        agent_id = "test-agent-signing-001"
        stored = signing_store.store_key(agent_id, key_bytes)
        assert stored is True
        retrieved = signing_store.get_key(agent_id)
        assert retrieved == key_bytes

    def test_get_nonexistent_key_returns_none(self, redis_available, signing_store):
        result = signing_store.get_key("agent-definitely-not-registered-xyz")
        assert result is None

    def test_delete_key(self, redis_available, signing_store):
        agent_id = "test-agent-to-delete-001"
        signing_store.store_key(agent_id, b"some_key")
        deleted = signing_store.delete_key(agent_id)
        assert deleted is True
        assert signing_store.get_key(agent_id) is None

    def test_list_agents_returns_list(self, redis_available, signing_store):
        result = signing_store.list_agents()
        assert isinstance(result, list)

    def test_list_agents_includes_stored(self, redis_available, signing_store):
        agent_id = "test-agent-list-001"
        signing_store.store_key(agent_id, b"key_data")
        agents = signing_store.list_agents()
        assert agent_id in agents

    def test_record_and_check_message_id(self, redis_available, signing_store):
        msg_id = "msg-test-replay-001"
        recorded = signing_store.record_message_id(msg_id, ttl_seconds=60)
        assert recorded is True
        assert signing_store.is_message_seen(msg_id) is True

    def test_unseen_message_returns_false(self, redis_available, signing_store):
        assert signing_store.is_message_seen("msg-never-recorded-xyz") is False


# ═══════════════════════════════════════════════════════════════════════════════
# CapabilityStore (Redis-backed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCapabilityStore:
    def test_store_and_get_capabilities(self, redis_available, cap_store):
        agent_id = "test-agent-cap-001"
        caps = ["filesystem.read", "network.http.get", "memory.read"]
        stored = cap_store.store_capabilities(agent_id, caps)
        assert stored is True
        retrieved = cap_store.get_capabilities(agent_id)
        assert retrieved == caps

    def test_get_capabilities_nonexistent(self, redis_available, cap_store):
        result = cap_store.get_capabilities("agent-no-caps-xyz")
        assert result is None

    def test_list_agents_returns_list(self, redis_available, cap_store):
        result = cap_store.list_agents()
        assert isinstance(result, list)

    def test_list_agents_includes_stored(self, redis_available, cap_store):
        agent_id = "test-agent-cap-list-001"
        cap_store.store_capabilities(agent_id, ["read"])
        agents = cap_store.list_agents()
        assert agent_id in agents

    def test_store_empty_capabilities(self, redis_available, cap_store):
        agent_id = "test-agent-no-caps-001"
        stored = cap_store.store_capabilities(agent_id, [])
        assert stored is True
        retrieved = cap_store.get_capabilities(agent_id)
        assert retrieved == []


# ═══════════════════════════════════════════════════════════════════════════════
# AnomalyStore (Redis-backed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnomalyStore:
    def _make_anomaly(self, anomaly_id=None, agent_id=None, resolved=False):
        return {
            "anomaly_id": anomaly_id or f"anomaly-test-{id(self)}",
            "agent_id": agent_id or "agent-anomaly-test-001",
            "type": "resource_overuse",
            "severity": "medium",
            "resolved": resolved,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def test_store_and_get_baseline(self, redis_available, anomaly_store):
        agent_id = "test-agent-baseline-001"
        baseline = {
            "known_actions": ["read", "write"],
            "request_rate": 5.0,
        }
        stored = anomaly_store.store_baseline(agent_id, baseline)
        assert stored is True
        retrieved = anomaly_store.get_baseline(agent_id)
        assert retrieved is not None
        assert retrieved["request_rate"] == 5.0

    def test_store_baseline_with_set(self, redis_available, anomaly_store):
        agent_id = "test-agent-baseline-set-001"
        baseline = {
            "known_resources": {"path/a", "path/b"},
            "known_actions": {"read", "write"},
        }
        stored = anomaly_store.store_baseline(agent_id, baseline)
        assert stored is True
        retrieved = anomaly_store.get_baseline(agent_id)
        assert isinstance(retrieved["known_resources"], set)
        assert isinstance(retrieved["known_actions"], set)

    def test_store_baseline_with_datetime(self, redis_available, anomaly_store):
        agent_id = "test-agent-baseline-dt-001"
        baseline = {"created_at": datetime.now(timezone.utc)}
        stored = anomaly_store.store_baseline(agent_id, baseline)
        assert stored is True

    def test_get_baseline_nonexistent(self, redis_available, anomaly_store):
        result = anomaly_store.get_baseline("agent-no-baseline-xyz")
        assert result is None

    def test_store_and_get_anomaly(self, redis_available, anomaly_store):
        anomaly = self._make_anomaly("anomaly-store-get-001")
        stored = anomaly_store.store_anomaly(anomaly)
        assert stored is True
        retrieved = anomaly_store.get_anomaly("anomaly-store-get-001")
        assert retrieved is not None
        assert retrieved["anomaly_id"] == "anomaly-store-get-001"

    def test_get_nonexistent_anomaly(self, redis_available, anomaly_store):
        result = anomaly_store.get_anomaly("anomaly-does-not-exist-xyz")
        assert result is None

    def test_get_unresolved_anomalies(self, redis_available, anomaly_store):
        anomaly = self._make_anomaly("anomaly-unresolved-001")
        anomaly_store.store_anomaly(anomaly)
        unresolved = anomaly_store.get_unresolved_anomalies()
        assert isinstance(unresolved, list)

    def test_resolve_anomaly(self, redis_available, anomaly_store):
        anomaly = self._make_anomaly("anomaly-resolve-001")
        anomaly_store.store_anomaly(anomaly)
        resolved = anomaly_store.resolve_anomaly("anomaly-resolve-001", "Manually resolved")
        assert resolved is True
        retrieved = anomaly_store.get_anomaly("anomaly-resolve-001")
        assert retrieved["resolved"] is True
        assert retrieved["resolution_notes"] == "Manually resolved"

    def test_resolve_nonexistent_anomaly(self, redis_available, anomaly_store):
        result = anomaly_store.resolve_anomaly("anomaly-no-such-xyz", "irrelevant")
        assert result is False

    def test_get_agent_anomalies(self, redis_available, anomaly_store):
        agent_id = "agent-anomaly-list-001"
        anomaly = self._make_anomaly("anomaly-agent-list-001", agent_id=agent_id)
        anomaly_store.store_anomaly(anomaly)
        result = anomaly_store.get_agent_anomalies(agent_id)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_get_agent_anomalies_empty(self, redis_available, anomaly_store):
        result = anomaly_store.get_agent_anomalies("agent-with-no-anomalies-xyz")
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# ApprovalStore (Redis-backed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestApprovalStore:
    def _make_request(self, request_id, agent_id="test-agent", status="pending", priority="normal"):
        return {
            "request_id": request_id,
            "agent_id": agent_id,
            "action": "test_action",
            "status": status,
            "priority": priority,
        }

    def test_store_and_get_request(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        req = self._make_request("appr-depth-001")
        stored = store.store_request(req)
        assert stored is True
        retrieved = store.get_request("appr-depth-001")
        assert retrieved is not None
        assert retrieved["request_id"] == "appr-depth-001"

    def test_get_nonexistent_request_returns_none(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        result = store.get_request("appr-not-here-xyz")
        assert result is None

    def test_store_urgent_priority(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        req = self._make_request("appr-urgent-depth-001", priority="urgent")
        stored = store.store_request(req)
        assert stored is True

    def test_store_high_priority(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        req = self._make_request("appr-high-depth-001", priority="high")
        stored = store.store_request(req)
        assert stored is True

    def test_store_low_priority(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        req = self._make_request("appr-low-depth-001", priority="low")
        stored = store.store_request(req)
        assert stored is True

    def test_get_pending_requests_returns_list(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        result = store.get_pending_requests()
        assert isinstance(result, list)

    def test_get_pending_requests_includes_stored(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        req = self._make_request("appr-pending-depth-001", status="pending")
        store.store_request(req)
        pending = store.get_pending_requests(limit=100)
        assert isinstance(pending, list)

    def test_update_request_status(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        req_id = "appr-update-depth-001"
        store.store_request(self._make_request(req_id))
        updated = store.update_request(req_id, {"status": "approved", "decided_by": "admin"})
        assert updated is True
        retrieved = store.get_request(req_id)
        assert retrieved["status"] == "approved"

    def test_update_removes_from_pending_when_not_pending(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        req_id = "appr-remove-pending-depth-001"
        store.store_request(self._make_request(req_id, status="pending"))
        store.update_request(req_id, {"status": "rejected"})
        retrieved = store.get_request(req_id)
        assert retrieved["status"] == "rejected"

    def test_update_nonexistent_request_returns_false(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        result = store.update_request("appr-not-found-xyz", {"status": "approved"})
        assert result is False

    def test_get_agent_requests(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        agent_id = "agent-appr-list-depth-001"
        store.store_request(self._make_request("appr-agent-depth-001", agent_id=agent_id))
        results = store.get_agent_requests(agent_id)
        assert isinstance(results, list)

    def test_get_agent_requests_filters_by_agent(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        agent_id = "agent-filter-appr-depth-001"
        store.store_request(self._make_request("appr-filter-depth-001", agent_id=agent_id))
        results = store.get_agent_requests(agent_id)
        for r in results:
            assert r["agent_id"] == agent_id

    def test_non_pending_request_not_in_priority_queue(self, redis_available):
        from core.persistence import ApprovalStore
        store = ApprovalStore()
        req = self._make_request("appr-non-pending-depth-001", status="approved")
        stored = store.store_request(req)
        assert stored is True


# ═══════════════════════════════════════════════════════════════════════════════
# FederationStore (Redis-backed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFederationStore:
    def _make_relationship(self, rel_id, remote_instance_id="remote-001", status="active"):
        return {
            "relationship_id": rel_id,
            "status": status,
            "remote_identity": {"instance_id": remote_instance_id},
        }

    def test_store_and_get_identity(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        identity = {
            "instance_id": "fed-depth-001",
            "name": "Test Instance",
            "endpoint": "https://test.example.com",
        }
        stored = store.store_identity(identity)
        assert stored is True
        retrieved = store.get_identity()
        assert retrieved is not None
        assert isinstance(retrieved, dict)

    def test_store_and_get_relationship(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        rel = self._make_relationship("rel-depth-001")
        stored = store.store_relationship(rel)
        assert stored is True
        retrieved = store.get_relationship("rel-depth-001")
        assert retrieved is not None
        assert retrieved["relationship_id"] == "rel-depth-001"

    def test_get_nonexistent_relationship_returns_none(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        result = store.get_relationship("rel-not-here-xyz")
        assert result is None

    def test_get_relationship_by_instance(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        remote_id = "remote-lookup-depth-001"
        rel = self._make_relationship("rel-lookup-depth-001", remote_instance_id=remote_id)
        store.store_relationship(rel)
        result = store.get_relationship_by_instance(remote_id)
        assert result is not None
        assert result["relationship_id"] == "rel-lookup-depth-001"

    def test_get_relationship_by_instance_not_found(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        result = store.get_relationship_by_instance("remote-not-found-xyz")
        assert result is None

    def test_list_relationships_returns_list(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        result = store.list_relationships()
        assert isinstance(result, list)

    def test_list_relationships_by_status(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        rel = self._make_relationship("rel-status-depth-001", remote_instance_id="remote-stat-001", status="pending")
        store.store_relationship(rel)
        pending = store.list_relationships(status="pending")
        for r in pending:
            assert r["status"] == "pending"

    def test_list_relationships_no_status_filter_returns_all(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        # Store two relationships with different statuses
        store.store_relationship(self._make_relationship("rel-all-depth-001", remote_instance_id="remote-all-001", status="active"))
        store.store_relationship(self._make_relationship("rel-all-depth-002", remote_instance_id="remote-all-002", status="pending"))
        result = store.list_relationships()
        assert isinstance(result, list)

    def test_update_relationship(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        rel_id = "rel-update-depth-001"
        store.store_relationship(self._make_relationship(rel_id, remote_instance_id="remote-upd-001", status="pending"))
        updated = store.update_relationship(rel_id, {"status": "active"})
        assert updated is True
        retrieved = store.get_relationship(rel_id)
        assert retrieved["status"] == "active"

    def test_update_nonexistent_relationship_returns_false(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        result = store.update_relationship("rel-not-found-xyz", {"status": "active"})
        assert result is False

    def test_store_relationship_without_remote_instance_id(self, redis_available):
        from core.persistence import FederationStore
        store = FederationStore()
        rel = {
            "relationship_id": "rel-no-remote-depth-001",
            "status": "active",
            "remote_identity": {},  # No instance_id
        }
        stored = store.store_relationship(rel)
        assert stored is True
        retrieved = store.get_relationship("rel-no-remote-depth-001")
        assert retrieved is not None
