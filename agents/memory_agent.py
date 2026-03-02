# TelsonBase/agents/memory_agent.py
# REM: =======================================================================================
# REM: CONVERSATION MEMORY AGENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v4.2.0CC: New agent - Conversation memory and context management
#
# REM: Mission Statement: Maintain conversation context and memory for agents, enabling
# REM: coherent multi-turn interactions while respecting privacy and security boundaries.
#
# REM: Features:
# REM:   - Short-term working memory (conversation context)
# REM:   - Long-term memory (persistent facts and preferences)
# REM:   - Semantic search over memories
# REM:   - Privacy-aware memory isolation per agent/user
# REM:   - Memory expiration and cleanup
# REM: =======================================================================================

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from celery import shared_task

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: AGENT CONFIGURATION
# REM: =======================================================================================

AGENT_ID = "memory_agent"

CAPABILITIES = [
    "memory.read:*",
    "memory.write:*",
    "memory.delete:own",
    "internal.none",
]

REQUIRES_APPROVAL_FOR = [
    "clear_all_memories",
    "export_memories",
]


class MemoryType(str, Enum):
    """REM: Types of memories."""
    FACT = "fact"           # Factual information
    PREFERENCE = "preference"  # User/agent preferences
    CONTEXT = "context"     # Conversation context
    INSTRUCTION = "instruction"  # Standing instructions
    ENTITY = "entity"       # Named entities


class MemoryScope(str, Enum):
    """REM: Scope of memory visibility."""
    PRIVATE = "private"     # Only the owner can access
    SHARED = "shared"       # Shared with specific agents
    GLOBAL = "global"       # System-wide (admin only)


@dataclass
class Memory:
    """REM: A single memory entry."""
    memory_id: str
    owner_id: str           # Agent or user who owns this memory
    memory_type: MemoryType
    scope: MemoryScope
    content: str
    metadata: Dict[str, Any]
    created_at: datetime
    expires_at: Optional[datetime]
    last_accessed: datetime
    access_count: int = 0
    importance: float = 0.5  # 0.0 to 1.0
    embedding: Optional[List[float]] = None  # For semantic search
    shared_with: List[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "owner_id": self.owner_id,
            "memory_type": self.memory_type.value,
            "scope": self.scope.value,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "importance": self.importance
        }


@dataclass
class ConversationContext:
    """REM: Short-term conversation context."""
    context_id: str
    agent_id: str
    user_id: Optional[str]
    messages: List[Dict[str, Any]]
    created_at: datetime
    last_updated: datetime
    summary: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    max_messages: int = 20

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        })
        self.last_updated = datetime.now(timezone.utc)

        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]


class MemoryStore:
    """REM: In-memory storage for memories and contexts."""

    def __init__(self):
        self._memories: Dict[str, Memory] = {}
        self._by_owner: Dict[str, set] = defaultdict(set)
        self._contexts: Dict[str, ConversationContext] = {}
        self._context_by_agent: Dict[str, str] = {}

    def store_memory(self, memory: Memory) -> str:
        self._memories[memory.memory_id] = memory
        self._by_owner[memory.owner_id].add(memory.memory_id)
        return memory.memory_id

    def get_memory(self, memory_id: str, accessor_id: str) -> Optional[Memory]:
        memory = self._memories.get(memory_id)
        if not memory:
            return None
        if memory.is_expired():
            return None
        if not self._can_access(memory, accessor_id):
            return None
        memory.access_count += 1
        memory.last_accessed = datetime.now(timezone.utc)
        return memory

    def _can_access(self, memory: Memory, accessor_id: str) -> bool:
        if memory.owner_id == accessor_id:
            return True
        if memory.scope == MemoryScope.GLOBAL:
            return True
        if memory.scope == MemoryScope.SHARED and accessor_id in memory.shared_with:
            return True
        return False

    def search_memories(
        self,
        owner_id: str,
        query: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10
    ) -> List[Memory]:
        results = []

        for memory_id in self._by_owner.get(owner_id, set()):
            memory = self._memories.get(memory_id)
            if not memory or memory.is_expired():
                continue
            if memory_type and memory.memory_type != memory_type:
                continue
            if query and query.lower() not in memory.content.lower():
                continue
            results.append(memory)

        results.sort(key=lambda m: (m.importance, m.last_accessed), reverse=True)
        return results[:limit]

    def delete_memory(self, memory_id: str, deleter_id: str) -> bool:
        memory = self._memories.get(memory_id)
        if not memory:
            return False
        if memory.owner_id != deleter_id:
            return False
        del self._memories[memory_id]
        self._by_owner[memory.owner_id].discard(memory_id)
        return True

    def get_or_create_context(self, agent_id: str, user_id: Optional[str] = None) -> ConversationContext:
        context_key = f"{agent_id}:{user_id or 'system'}"

        if context_key in self._context_by_agent:
            context_id = self._context_by_agent[context_key]
            if context_id in self._contexts:
                return self._contexts[context_id]

        context_id = f"ctx_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        context = ConversationContext(
            context_id=context_id,
            agent_id=agent_id,
            user_id=user_id,
            messages=[],
            created_at=now,
            last_updated=now
        )
        self._contexts[context_id] = context
        self._context_by_agent[context_key] = context_id
        return context

    def clear_context(self, agent_id: str, user_id: Optional[str] = None) -> bool:
        context_key = f"{agent_id}:{user_id or 'system'}"
        if context_key in self._context_by_agent:
            context_id = self._context_by_agent.pop(context_key)
            if context_id in self._contexts:
                del self._contexts[context_id]
                return True
        return False

    def cleanup_expired(self) -> int:
        expired = []
        for memory_id, memory in self._memories.items():
            if memory.is_expired():
                expired.append(memory_id)

        for memory_id in expired:
            memory = self._memories.pop(memory_id)
            self._by_owner[memory.owner_id].discard(memory_id)

        return len(expired)


# REM: Global memory store
_memory_store = MemoryStore()


# REM: =======================================================================================
# REM: CELERY TASKS
# REM: =======================================================================================

@shared_task(name="memory_agent.store_memory")
def store_memory(
    owner_id: str,
    content: str,
    memory_type: str = "fact",
    scope: str = "private",
    importance: float = 0.5,
    expires_hours: Optional[float] = None,
    metadata: Optional[Dict] = None,
    shared_with: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    REM: Store a new memory.
    """
    logger.info(f"REM: {AGENT_ID} received: 'store_memory_Please' for ::{owner_id}::")

    now = datetime.now(timezone.utc)
    memory_id = f"mem_{uuid.uuid4().hex[:12]}"

    try:
        mem_type = MemoryType(memory_type)
    except ValueError:
        mem_type = MemoryType.FACT

    try:
        mem_scope = MemoryScope(scope)
    except ValueError:
        mem_scope = MemoryScope.PRIVATE

    memory = Memory(
        memory_id=memory_id,
        owner_id=owner_id,
        memory_type=mem_type,
        scope=mem_scope,
        content=content,
        metadata=metadata or {},
        created_at=now,
        expires_at=now + timedelta(hours=expires_hours) if expires_hours else None,
        last_accessed=now,
        importance=max(0.0, min(1.0, importance)),
        shared_with=shared_with or []
    )

    _memory_store.store_memory(memory)

    logger.info(f"REM: {AGENT_ID} completed: 'store_memory_Thank_You' - ID: ::{memory_id}::")

    return {
        "status": "success",
        "memory_id": memory_id,
        "memory": memory.to_dict(),
        "qms_status": "Thank_You"
    }


@shared_task(name="memory_agent.recall_memories")
def recall_memories(
    owner_id: str,
    query: Optional[str] = None,
    memory_type: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    REM: Recall memories for an owner.
    """
    logger.info(f"REM: {AGENT_ID} received: 'recall_memories_Please' for ::{owner_id}::")

    mem_type = None
    if memory_type:
        try:
            mem_type = MemoryType(memory_type)
        except ValueError:
            pass

    memories = _memory_store.search_memories(
        owner_id=owner_id,
        query=query,
        memory_type=mem_type,
        limit=limit
    )

    logger.info(
        f"REM: {AGENT_ID} completed: 'recall_memories_Thank_You' - "
        f"Found {len(memories)} memories"
    )

    return {
        "status": "success",
        "memories": [m.to_dict() for m in memories],
        "count": len(memories),
        "qms_status": "Thank_You"
    }


@shared_task(name="memory_agent.forget_memory")
def forget_memory(owner_id: str, memory_id: str) -> Dict[str, Any]:
    """
    REM: Delete a specific memory.
    """
    logger.info(f"REM: {AGENT_ID} received: 'forget_memory_Please' - ID: ::{memory_id}::")

    success = _memory_store.delete_memory(memory_id, owner_id)

    if success:
        logger.info(f"REM: {AGENT_ID} completed: 'forget_memory_Thank_You'")
        return {
            "status": "success",
            "deleted": memory_id,
            "qms_status": "Thank_You"
        }
    else:
        logger.warning(f"REM: {AGENT_ID} error: 'forget_memory_Thank_You_But_No'")
        return {
            "status": "error",
            "error": "Memory not found or access denied",
            "qms_status": "Thank_You_But_No"
        }


@shared_task(name="memory_agent.add_to_context")
def add_to_context(
    agent_id: str,
    role: str,
    content: str,
    user_id: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    REM: Add a message to conversation context.
    """
    context = _memory_store.get_or_create_context(agent_id, user_id)
    context.add_message(role, content, metadata)

    logger.debug(
        f"REM: {AGENT_ID} context updated for ::{agent_id}:: "
        f"({len(context.messages)} messages)_Thank_You"
    )

    return {
        "status": "success",
        "context_id": context.context_id,
        "message_count": len(context.messages),
        "qms_status": "Thank_You"
    }


@shared_task(name="memory_agent.get_context")
def get_context(
    agent_id: str,
    user_id: Optional[str] = None,
    last_n: Optional[int] = None
) -> Dict[str, Any]:
    """
    REM: Get conversation context for an agent.
    """
    context = _memory_store.get_or_create_context(agent_id, user_id)
    messages = context.messages

    if last_n:
        messages = messages[-last_n:]

    return {
        "status": "success",
        "context_id": context.context_id,
        "agent_id": agent_id,
        "user_id": user_id,
        "messages": messages,
        "message_count": len(context.messages),
        "entities": context.entities,
        "created_at": context.created_at.isoformat(),
        "last_updated": context.last_updated.isoformat(),
        "qms_status": "Thank_You"
    }


@shared_task(name="memory_agent.clear_context")
def clear_context(
    agent_id: str,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    REM: Clear conversation context.
    """
    success = _memory_store.clear_context(agent_id, user_id)

    logger.info(
        f"REM: {AGENT_ID} context cleared for ::{agent_id}::_Thank_You"
    )

    return {
        "status": "success",
        "cleared": success,
        "qms_status": "Thank_You"
    }


@shared_task(name="memory_agent.update_entity")
def update_entity(
    agent_id: str,
    entity_name: str,
    entity_value: Any,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    REM: Update an entity in conversation context.
    """
    context = _memory_store.get_or_create_context(agent_id, user_id)
    context.entities[entity_name] = {
        "value": entity_value,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    context.last_updated = datetime.now(timezone.utc)

    logger.debug(
        f"REM: {AGENT_ID} entity ::{entity_name}:: updated for ::{agent_id}::_Thank_You"
    )

    return {
        "status": "success",
        "entity": entity_name,
        "context_id": context.context_id,
        "qms_status": "Thank_You"
    }


@shared_task(name="memory_agent.cleanup")
def cleanup() -> Dict[str, Any]:
    """
    REM: Clean up expired memories.
    """
    expired_count = _memory_store.cleanup_expired()

    logger.info(f"REM: {AGENT_ID} cleanup: {expired_count} expired memories removed_Thank_You")

    return {
        "status": "success",
        "expired_removed": expired_count,
        "qms_status": "Thank_You"
    }


@shared_task(name="memory_agent.get_status")
def get_status() -> Dict[str, Any]:
    """
    REM: Get agent status.
    """
    return {
        "agent_id": AGENT_ID,
        "status": "healthy",
        "capabilities": CAPABILITIES,
        "requires_approval_for": REQUIRES_APPROVAL_FOR,
        "stats": {
            "total_memories": len(_memory_store._memories),
            "total_contexts": len(_memory_store._contexts),
            "unique_owners": len(_memory_store._by_owner)
        },
        "qms_status": "Thank_You"
    }
