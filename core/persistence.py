# TelsonBase/core/persistence.py
# REM: =======================================================================================
# REM: REDIS PERSISTENCE LAYER FOR SECURITY INFRASTRUCTURE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: In-memory data structures are fine for development but won't
# REM: survive container restarts. This module provides Redis-backed persistence for:
# REM:   - Agent signing keys
# REM:   - Capability registrations
# REM:   - Behavioral baselines
# REM:   - Anomaly records
# REM:   - Approval requests
# REM:   - Federation trust relationships
# REM:
# REM: All data is JSON-serialized and stored with appropriate TTLs where relevant.
# REM: =======================================================================================

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import redis
from pydantic import BaseModel

from core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class RedisStore:
    """
    REM: Base class for Redis-backed storage.
    REM: Handles connection management and common operations.
    """
    
    def __init__(self, prefix: str):
        """
        REM: Initialize with a key prefix to namespace this store.
        """
        self.prefix = prefix
        self._client: Optional[redis.Redis] = None
    
    @property
    def client(self) -> redis.Redis:
        """REM: Lazy-initialized Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
        return self._client
    
    def _key(self, *parts: str) -> str:
        """REM: Build a namespaced key."""
        return f"{self.prefix}:{':'.join(parts)}"
    
    def _serialize(self, obj: Any) -> str:
        """REM: Serialize object to JSON string."""
        if isinstance(obj, BaseModel):
            return obj.model_dump_json()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, set):
            return json.dumps(list(obj))
        elif isinstance(obj, bytes):
            import base64
            return base64.b64encode(obj).decode()
        else:
            return json.dumps(obj, default=str)
    
    def _deserialize(self, data: str, as_type: type = None) -> Any:
        """REM: Deserialize JSON string to object."""
        if data is None:
            return None
        
        parsed = json.loads(data)
        
        if as_type and issubclass(as_type, BaseModel):
            return as_type.model_validate(parsed)
        
        return parsed
    
    def ping(self) -> bool:
        """REM: Check Redis connectivity."""
        try:
            return self.client.ping()
        except redis.RedisError:
            return False


class SigningKeyStore(RedisStore):
    """
    REM: Redis-backed storage for agent signing keys.
    """
    
    def __init__(self):
        super().__init__("signing")
    
    def store_key(self, agent_id: str, key: bytes) -> bool:
        """REM: Store an agent's signing key."""
        import base64
        try:
            self.client.set(
                self._key("keys", agent_id),
                base64.b64encode(key).decode()
            )
            logger.info(f"REM: Stored signing key for agent ::{agent_id}::_Thank_You")
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to store signing key: {e}_Thank_You_But_No")
            return False
    
    def get_key(self, agent_id: str) -> Optional[bytes]:
        """REM: Retrieve an agent's signing key."""
        import base64
        try:
            data = self.client.get(self._key("keys", agent_id))
            if data:
                return base64.b64decode(data)
            return None
        except redis.RedisError as e:
            logger.error(f"REM: Failed to get signing key: {e}_Thank_You_But_No")
            return None
    
    def delete_key(self, agent_id: str) -> bool:
        """REM: Delete (revoke) an agent's signing key."""
        try:
            self.client.delete(self._key("keys", agent_id))
            logger.warning(f"REM: Deleted signing key for agent ::{agent_id}::_Thank_You_But_No")
            return True
        except redis.RedisError:
            return False
    
    def list_agents(self) -> List[str]:
        """REM: List all agents with registered keys. Uses SCAN to avoid blocking."""
        try:
            agents = []
            for key in self.client.scan_iter(match=self._key("keys", "*"), count=100):
                agents.append(key.split(":")[-1])
            return agents
        except redis.RedisError:
            return []
    
    def record_message_id(self, message_id: str, ttl_seconds: int = 600) -> bool:
        """REM: Record a message ID for replay protection."""
        try:
            self.client.setex(
                self._key("seen", message_id),
                ttl_seconds,
                "1"
            )
            return True
        except redis.RedisError:
            return False
    
    def is_message_seen(self, message_id: str) -> bool:
        """REM: Check if a message ID has been seen (replay attack check)."""
        try:
            return self.client.exists(self._key("seen", message_id)) > 0
        except redis.RedisError:
            return False


class CapabilityStore(RedisStore):
    """
    REM: Redis-backed storage for agent capabilities.
    """
    
    def __init__(self):
        super().__init__("capabilities")
    
    def store_capabilities(self, agent_id: str, capabilities: List[str]) -> bool:
        """REM: Store an agent's capability set."""
        try:
            self.client.set(
                self._key("agents", agent_id),
                json.dumps(capabilities)
            )
            logger.info(f"REM: Stored {len(capabilities)} capabilities for ::{agent_id}::_Thank_You")
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to store capabilities: {e}_Thank_You_But_No")
            return False
    
    def get_capabilities(self, agent_id: str) -> Optional[List[str]]:
        """REM: Retrieve an agent's capabilities."""
        try:
            data = self.client.get(self._key("agents", agent_id))
            if data:
                return json.loads(data)
            return None
        except redis.RedisError:
            return None
    
    def list_agents(self) -> List[str]:
        """REM: List all agents with registered capabilities. Uses SCAN to avoid blocking."""
        try:
            agents = []
            for key in self.client.scan_iter(match=self._key("agents", "*"), count=100):
                agents.append(key.split(":")[-1])
            return agents
        except redis.RedisError:
            return []


class AnomalyStore(RedisStore):
    """
    REM: Redis-backed storage for behavioral baselines and anomalies.
    """
    
    def __init__(self):
        super().__init__("anomaly")
    
    def store_baseline(self, agent_id: str, baseline: Dict[str, Any]) -> bool:
        """REM: Store an agent's behavioral baseline."""
        try:
            # REM: Convert sets to lists for JSON serialization
            serializable = {}
            for k, v in baseline.items():
                if isinstance(v, set):
                    serializable[k] = list(v)
                elif isinstance(v, datetime):
                    serializable[k] = v.isoformat()
                else:
                    serializable[k] = v
            
            self.client.set(
                self._key("baseline", agent_id),
                json.dumps(serializable)
            )
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to store baseline: {e}_Thank_You_But_No")
            return False
    
    def get_baseline(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """REM: Retrieve an agent's behavioral baseline."""
        try:
            data = self.client.get(self._key("baseline", agent_id))
            if data:
                baseline = json.loads(data)
                # REM: Convert lists back to sets where appropriate
                if "known_resources" in baseline:
                    baseline["known_resources"] = set(baseline["known_resources"])
                if "known_actions" in baseline:
                    baseline["known_actions"] = set(baseline["known_actions"])
                return baseline
            return None
        except redis.RedisError:
            return None
    
    def store_anomaly(self, anomaly: Dict[str, Any]) -> bool:
        """REM: Store a detected anomaly."""
        try:
            anomaly_id = anomaly.get("anomaly_id")
            agent_id = anomaly.get("agent_id")
            
            # REM: Store in anomaly hash
            self.client.hset(
                self._key("anomalies"),
                anomaly_id,
                json.dumps(anomaly, default=str)
            )
            
            # REM: Add to agent's anomaly list
            self.client.rpush(
                self._key("agent_anomalies", agent_id),
                anomaly_id
            )
            
            # REM: Add to unresolved set if not resolved
            if not anomaly.get("resolved", False):
                self.client.sadd(self._key("unresolved"), anomaly_id)
            
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to store anomaly: {e}_Thank_You_But_No")
            return False
    
    def get_anomaly(self, anomaly_id: str) -> Optional[Dict[str, Any]]:
        """REM: Retrieve a specific anomaly."""
        try:
            data = self.client.hget(self._key("anomalies"), anomaly_id)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError:
            return None
    
    def get_unresolved_anomalies(self, limit: int = 100) -> List[Dict[str, Any]]:
        """REM: Get all unresolved anomalies."""
        try:
            anomaly_ids = self.client.smembers(self._key("unresolved"))
            anomalies = []
            for aid in list(anomaly_ids)[:limit]:
                anomaly = self.get_anomaly(aid)
                if anomaly:
                    anomalies.append(anomaly)
            return anomalies
        except redis.RedisError:
            return []
    
    def resolve_anomaly(self, anomaly_id: str, resolution_notes: str) -> bool:
        """REM: Mark an anomaly as resolved."""
        try:
            anomaly = self.get_anomaly(anomaly_id)
            if anomaly:
                anomaly["resolved"] = True
                anomaly["resolution_notes"] = resolution_notes
                anomaly["resolved_at"] = datetime.now(timezone.utc).isoformat()
                
                self.client.hset(
                    self._key("anomalies"),
                    anomaly_id,
                    json.dumps(anomaly, default=str)
                )
                self.client.srem(self._key("unresolved"), anomaly_id)
                return True
            return False
        except redis.RedisError:
            return False
    
    def get_agent_anomalies(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """REM: Get anomalies for a specific agent."""
        try:
            anomaly_ids = self.client.lrange(
                self._key("agent_anomalies", agent_id),
                -limit,
                -1
            )
            anomalies = []
            for aid in anomaly_ids:
                anomaly = self.get_anomaly(aid)
                if anomaly:
                    anomalies.append(anomaly)
            return anomalies
        except redis.RedisError:
            return []


class ApprovalStore(RedisStore):
    """
    REM: Redis-backed storage for approval requests.
    """
    
    def __init__(self):
        super().__init__("approval")
    
    def store_request(self, request: Dict[str, Any]) -> bool:
        """REM: Store an approval request."""
        try:
            request_id = request.get("request_id")
            
            self.client.hset(
                self._key("requests"),
                request_id,
                json.dumps(request, default=str)
            )
            
            # REM: Add to pending set
            if request.get("status") == "pending":
                self.client.sadd(self._key("pending"), request_id)
                
                # REM: Also add to priority queue
                priority_score = {
                    "urgent": 0, "high": 1, "normal": 2, "low": 3
                }.get(request.get("priority", "normal"), 2)
                
                self.client.zadd(
                    self._key("pending_queue"),
                    {request_id: priority_score}
                )
            
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to store approval request: {e}_Thank_You_But_No")
            return False
    
    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """REM: Retrieve a specific approval request."""
        try:
            data = self.client.hget(self._key("requests"), request_id)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError:
            return None
    
    def update_request(self, request_id: str, updates: Dict[str, Any]) -> bool:
        """REM: Update an approval request."""
        try:
            request = self.get_request(request_id)
            if request:
                request.update(updates)
                self.client.hset(
                    self._key("requests"),
                    request_id,
                    json.dumps(request, default=str)
                )
                
                # REM: Remove from pending if no longer pending
                if updates.get("status") and updates["status"] != "pending":
                    self.client.srem(self._key("pending"), request_id)
                    self.client.zrem(self._key("pending_queue"), request_id)
                
                return True
            return False
        except redis.RedisError:
            return False
    
    def get_pending_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """REM: Get pending approval requests, ordered by priority."""
        try:
            # REM: Get from priority queue (lower score = higher priority)
            request_ids = self.client.zrange(
                self._key("pending_queue"),
                0,
                limit - 1
            )
            
            requests = []
            for rid in request_ids:
                request = self.get_request(rid)
                if request:
                    requests.append(request)
            return requests
        except redis.RedisError:
            return []
    
    def get_agent_requests(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """REM: Get approval requests for a specific agent."""
        try:
            all_requests = self.client.hgetall(self._key("requests"))
            agent_requests = []
            
            for rid, data in all_requests.items():
                request = json.loads(data)
                if request.get("agent_id") == agent_id:
                    agent_requests.append(request)
                    if len(agent_requests) >= limit:
                        break
            
            return agent_requests
        except redis.RedisError:
            return []


class FederationStore(RedisStore):
    """
    REM: Redis-backed storage for federation trust relationships.
    """
    
    def __init__(self):
        super().__init__("federation")
    
    def store_identity(self, identity: Dict[str, Any]) -> bool:
        """REM: Store our instance identity."""
        try:
            self.client.set(
                self._key("identity"),
                json.dumps(identity, default=str)
            )
            return True
        except redis.RedisError:
            return False
    
    def get_identity(self) -> Optional[Dict[str, Any]]:
        """REM: Retrieve our instance identity."""
        try:
            data = self.client.get(self._key("identity"))
            if data:
                return json.loads(data)
            return None
        except redis.RedisError:
            return None
    
    def store_relationship(self, relationship: Dict[str, Any]) -> bool:
        """REM: Store a trust relationship."""
        try:
            rel_id = relationship.get("relationship_id")
            remote_instance_id = relationship.get("remote_identity", {}).get("instance_id")
            
            self.client.hset(
                self._key("relationships"),
                rel_id,
                json.dumps(relationship, default=str)
            )
            
            # REM: Index by remote instance for lookup
            if remote_instance_id:
                self.client.set(
                    self._key("by_instance", remote_instance_id),
                    rel_id
                )
            
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to store relationship: {e}_Thank_You_But_No")
            return False
    
    def get_relationship(self, relationship_id: str) -> Optional[Dict[str, Any]]:
        """REM: Retrieve a trust relationship."""
        try:
            data = self.client.hget(self._key("relationships"), relationship_id)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError:
            return None
    
    def get_relationship_by_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """REM: Get relationship by remote instance ID."""
        try:
            rel_id = self.client.get(self._key("by_instance", instance_id))
            if rel_id:
                return self.get_relationship(rel_id)
            return None
        except redis.RedisError:
            return None
    
    def list_relationships(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """REM: List all trust relationships."""
        try:
            all_rels = self.client.hgetall(self._key("relationships"))
            relationships = []
            
            for rid, data in all_rels.items():
                rel = json.loads(data)
                if status is None or rel.get("status") == status:
                    relationships.append(rel)
            
            return relationships
        except redis.RedisError:
            return []
    
    def update_relationship(self, relationship_id: str, updates: Dict[str, Any]) -> bool:
        """REM: Update a trust relationship."""
        try:
            rel = self.get_relationship(relationship_id)
            if rel:
                rel.update(updates)
                return self.store_relationship(rel)
            return False
        except redis.RedisError:
            return False


class ToolroomStore(RedisStore):
    """
    REM: Redis-backed storage for the Toolroom.
    REM: Persists tool inventory, active checkouts, checkout history,
    REM: tool requests, and usage logs across container restarts.
    REM:
    REM: v4.4.0CC: Created to support the Foreman agent and Tool Registry.
    """
    
    def __init__(self):
        super().__init__("toolroom")
    
    # REM: -----------------------------------------------------------------------------------
    # REM: GENERIC KEY-VALUE (for tool inventory, active checkouts, requests)
    # REM: -----------------------------------------------------------------------------------
    
    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """REM: Store a JSON string by key."""
        try:
            if ttl:
                self.client.setex(self._key(key), ttl, value)
            else:
                self.client.set(self._key(key), value)
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Toolroom store set failed for key '{key}': {e}")
            return False
    
    def get(self, key: str) -> Optional[str]:
        """REM: Retrieve a JSON string by key."""
        try:
            return self.client.get(self._key(key))
        except redis.RedisError as e:
            logger.error(f"REM: Toolroom store get failed for key '{key}': {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """REM: Delete a key."""
        try:
            self.client.delete(self._key(key))
            return True
        except redis.RedisError:
            return False
    
    # REM: -----------------------------------------------------------------------------------
    # REM: LIST OPERATIONS (for usage log, checkout history)
    # REM: -----------------------------------------------------------------------------------
    
    def append_to_list(self, key: str, value: str, max_length: int = 10000) -> bool:
        """
        REM: Append to a Redis list with automatic trimming.
        REM: Keeps the most recent max_length entries.
        """
        try:
            full_key = self._key(key)
            self.client.rpush(full_key, value)
            # REM: Trim to prevent unbounded growth
            self.client.ltrim(full_key, -max_length, -1)
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Toolroom store append_to_list failed for key '{key}': {e}")
            return False
    
    def get_list(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """REM: Retrieve items from a Redis list."""
        try:
            return self.client.lrange(self._key(key), start, end)
        except redis.RedisError as e:
            logger.error(f"REM: Toolroom store get_list failed for key '{key}': {e}")
            return []
    
    def get_list_length(self, key: str) -> int:
        """REM: Get the length of a Redis list."""
        try:
            return self.client.llen(self._key(key))
        except redis.RedisError:
            return 0
    
    # REM: -----------------------------------------------------------------------------------
    # REM: HASH OPERATIONS (for indexed lookups)
    # REM: -----------------------------------------------------------------------------------
    
    def hset(self, hash_key: str, field: str, value: str) -> bool:
        """REM: Store a field in a Redis hash."""
        try:
            self.client.hset(self._key(hash_key), field, value)
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Toolroom store hset failed: {e}")
            return False
    
    def hget(self, hash_key: str, field: str) -> Optional[str]:
        """REM: Get a field from a Redis hash."""
        try:
            return self.client.hget(self._key(hash_key), field)
        except redis.RedisError:
            return None
    
    def hgetall(self, hash_key: str) -> Dict[str, str]:
        """REM: Get all fields from a Redis hash."""
        try:
            return self.client.hgetall(self._key(hash_key))
        except redis.RedisError:
            return {}
    
    def hdel(self, hash_key: str, field: str) -> bool:
        """REM: Delete a field from a Redis hash."""
        try:
            self.client.hdel(self._key(hash_key), field)
            return True
        except redis.RedisError:
            return False


class ComplianceStore(RedisStore):
    """REM: Redis-backed storage for compliance and regulatory data. v6.3.0CC"""

    def __init__(self):
        super().__init__("compliance")

    def store_record(self, record_type: str, record_id: str, data: Dict) -> bool:
        """REM: Store a compliance record in a hash keyed by record_type."""
        try:
            self.client.hset(
                self._key(record_type),
                record_id,
                json.dumps(data, default=str)
            )
            logger.info(f"REM: Stored compliance record ::{record_type}::{record_id}::_Thank_You")
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to store compliance record: {e}_Thank_You_But_No")
            return False

    def get_record(self, record_type: str, record_id: str) -> Optional[Dict]:
        """REM: Retrieve a compliance record from hash."""
        try:
            data = self.client.hget(self._key(record_type), record_id)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError as e:
            logger.error(f"REM: Failed to get compliance record: {e}_Thank_You_But_No")
            return None

    def delete_record(self, record_type: str, record_id: str) -> bool:
        """REM: Delete a compliance record from hash."""
        try:
            self.client.hdel(self._key(record_type), record_id)
            logger.warning(f"REM: Deleted compliance record ::{record_type}::{record_id}::_Thank_You_But_No")
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to delete compliance record: {e}_Thank_You_But_No")
            return False

    def list_records(self, record_type: str) -> Dict[str, Dict]:
        """REM: Return all records of a given type via hgetall."""
        try:
            all_data = self.client.hgetall(self._key(record_type))
            results = {}
            for rid, data in all_data.items():
                results[rid] = json.loads(data)
            return results
        except redis.RedisError as e:
            logger.error(f"REM: Failed to list compliance records: {e}_Thank_You_But_No")
            return {}

    def list_records_filtered(self, record_type: str, filter_key: str, filter_value: str) -> List[Dict]:
        """REM: Filter records of a type by a field value."""
        try:
            all_data = self.client.hgetall(self._key(record_type))
            filtered = []
            for rid, data in all_data.items():
                record = json.loads(data)
                if record.get(filter_key) == filter_value:
                    filtered.append(record)
            return filtered
        except redis.RedisError as e:
            logger.error(f"REM: Failed to filter compliance records: {e}_Thank_You_But_No")
            return []


class SecurityStore(RedisStore):
    """REM: Redis-backed storage for security modules (MFA, sessions, CAPTCHA, passwords). v7.0.0CC"""

    def __init__(self):
        super().__init__("security")

    def store_record(self, record_type: str, record_id: str, data: Dict, ttl: Optional[int] = None) -> bool:
        """REM: Store a security record. Uses setex with TTL key if ttl provided, otherwise hash."""
        try:
            serialized = json.dumps(data, default=str)
            if ttl is not None:
                self.client.setex(
                    self._key(record_type, record_id),
                    ttl,
                    serialized
                )
            else:
                self.client.hset(
                    self._key(record_type),
                    record_id,
                    serialized
                )
            logger.info(f"REM: Stored security record ::{record_type}::{record_id}::_Thank_You")
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to store security record: {e}_Thank_You_But_No")
            return False

    def get_record(self, record_type: str, record_id: str, use_ttl_key: bool = False) -> Optional[Dict]:
        """REM: Retrieve a security record. Reads TTL key or hash depending on use_ttl_key."""
        try:
            if use_ttl_key:
                data = self.client.get(self._key(record_type, record_id))
            else:
                data = self.client.hget(self._key(record_type), record_id)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError as e:
            logger.error(f"REM: Failed to get security record: {e}_Thank_You_But_No")
            return None

    def delete_record(self, record_type: str, record_id: str, use_ttl_key: bool = False) -> bool:
        """REM: Delete a security record from TTL key or hash."""
        try:
            if use_ttl_key:
                self.client.delete(self._key(record_type, record_id))
            else:
                self.client.hdel(self._key(record_type), record_id)
            logger.warning(f"REM: Deleted security record ::{record_type}::{record_id}::_Thank_You_But_No")
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to delete security record: {e}_Thank_You_But_No")
            return False

    def list_records(self, record_type: str) -> Dict[str, Dict]:
        """REM: Return all records of a given type via hgetall."""
        try:
            all_data = self.client.hgetall(self._key(record_type))
            results = {}
            for rid, data in all_data.items():
                results[rid] = json.loads(data)
            return results
        except redis.RedisError as e:
            logger.error(f"REM: Failed to list security records: {e}_Thank_You_But_No")
            return {}

    def add_to_set(self, set_name: str, value: str) -> bool:
        """REM: Add a value to a Redis set."""
        try:
            self.client.sadd(self._key(set_name), value)
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to add to security set: {e}_Thank_You_But_No")
            return False

    def remove_from_set(self, set_name: str, value: str) -> bool:
        """REM: Remove a value from a Redis set."""
        try:
            self.client.srem(self._key(set_name), value)
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to remove from security set: {e}_Thank_You_But_No")
            return False

    def get_set_members(self, set_name: str) -> Set[str]:
        """REM: Get all members of a Redis set."""
        try:
            return self.client.smembers(self._key(set_name))
        except redis.RedisError as e:
            logger.error(f"REM: Failed to get security set members: {e}_Thank_You_But_No")
            return set()

    # REM: =======================================================================================
    # REM: PASSWORD HASH STORAGE (v7.0.0CC)
    # REM: =======================================================================================
    # REM: Dedicated methods for user password hash persistence. Hashes are encrypted
    # REM: via secure_storage before storage in Redis hash "security:password_hashes".
    # REM: =======================================================================================

    def store_password_hash(self, user_id: str, hash_data: Dict) -> bool:
        """
        REM: Store an encrypted password hash for a user.
        REM: Delegates to store_record with record_type="password_hashes".
        """
        return self.store_record("password_hashes", user_id, hash_data)

    def get_password_hash(self, user_id: str) -> Optional[Dict]:
        """
        REM: Retrieve an encrypted password hash for a user.
        REM: Delegates to get_record with record_type="password_hashes".
        """
        return self.get_record("password_hashes", user_id)

    def delete_password_hash(self, user_id: str) -> bool:
        """
        REM: Remove a password hash from storage.
        REM: Delegates to delete_record with record_type="password_hashes".
        """
        return self.delete_record("password_hashes", user_id)

    def list_password_hashes(self) -> Dict[str, Dict]:
        """
        REM: List all stored password hashes (for loading on startup).
        REM: Delegates to list_records with record_type="password_hashes".
        """
        return self.list_records("password_hashes")


class TenancyStore(RedisStore):
    """REM: Redis-backed storage for multi-tenancy data. v6.3.0CC"""

    def __init__(self):
        super().__init__("tenancy")

    def store_tenant(self, tenant_id: str, data: Dict) -> bool:
        """REM: Store a tenant record in the tenants hash."""
        try:
            self.client.hset(
                self._key("tenants"),
                tenant_id,
                json.dumps(data, default=str)
            )
            logger.info(f"REM: Stored tenant ::{tenant_id}::_Thank_You")
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to store tenant: {e}_Thank_You_But_No")
            return False

    def get_tenant(self, tenant_id: str) -> Optional[Dict]:
        """REM: Retrieve a tenant record from the tenants hash."""
        try:
            data = self.client.hget(self._key("tenants"), tenant_id)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError as e:
            logger.error(f"REM: Failed to get tenant: {e}_Thank_You_But_No")
            return None

    def delete_tenant(self, tenant_id: str) -> bool:
        """REM: Delete a tenant record from the tenants hash."""
        try:
            self.client.hdel(self._key("tenants"), tenant_id)
            logger.warning(f"REM: Deleted tenant ::{tenant_id}::_Thank_You_But_No")
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to delete tenant: {e}_Thank_You_But_No")
            return False

    def list_tenants(self) -> Dict[str, Dict]:
        """REM: List all tenants via hgetall."""
        try:
            all_data = self.client.hgetall(self._key("tenants"))
            results = {}
            for tid, data in all_data.items():
                results[tid] = json.loads(data)
            return results
        except redis.RedisError as e:
            logger.error(f"REM: Failed to list tenants: {e}_Thank_You_But_No")
            return {}

    def store_matter(self, matter_id: str, data: Dict) -> bool:
        """REM: Store a matter record and index it under its tenant."""
        try:
            tenant_id = data.get("tenant_id")

            self.client.hset(
                self._key("matters"),
                matter_id,
                json.dumps(data, default=str)
            )

            # REM: Add to tenant's matter set for indexed lookup
            if tenant_id:
                self.client.sadd(self._key("tenant_matters", tenant_id), matter_id)

            logger.info(f"REM: Stored matter ::{matter_id}:: for tenant ::{tenant_id}::_Thank_You")
            return True
        except redis.RedisError as e:
            logger.error(f"REM: Failed to store matter: {e}_Thank_You_But_No")
            return False

    def get_matter(self, matter_id: str) -> Optional[Dict]:
        """REM: Retrieve a matter record from the matters hash."""
        try:
            data = self.client.hget(self._key("matters"), matter_id)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError as e:
            logger.error(f"REM: Failed to get matter: {e}_Thank_You_But_No")
            return None

    def list_tenant_matters(self, tenant_id: str) -> List[Dict]:
        """REM: Get all matters for a specific tenant via set members lookup."""
        try:
            matter_ids = self.client.smembers(self._key("tenant_matters", tenant_id))
            matters = []
            for mid in matter_ids:
                matter = self.get_matter(mid)
                if matter:
                    matters.append(matter)
            return matters
        except redis.RedisError as e:
            logger.error(f"REM: Failed to list tenant matters: {e}_Thank_You_But_No")
            return []


# REM: =======================================================================================
# REM: GLOBAL STORE INSTANCES
# REM: =======================================================================================

signing_store = SigningKeyStore()
# REM: ---------------------------------------------------------------------------------------
# REM: CONVENIENCE FUNCTION — DIRECT REDIS ACCESS
# REM: ---------------------------------------------------------------------------------------
# REM: Used by core/audit.py for chain state persistence. Returns a Redis client
# REM: or None if connection fails. This keeps audit.py decoupled from RedisStore
# REM: class hierarchy while providing the same connection logic.

def get_redis() -> Optional[redis.Redis]:
    """
    REM: Returns a Redis client connection, or None if unavailable.
    REM: Used by modules that need direct Redis access without a RedisStore subclass.
    """
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


# REM: ---------------------------------------------------------------------------------------
# REM: SINGLETON STORE INSTANCES
# REM: ---------------------------------------------------------------------------------------

capability_store = CapabilityStore()
anomaly_store = AnomalyStore()
approval_store = ApprovalStore()
federation_store = FederationStore()
toolroom_store = ToolroomStore()
compliance_store = ComplianceStore()
security_store = SecurityStore()
tenancy_store = TenancyStore()
