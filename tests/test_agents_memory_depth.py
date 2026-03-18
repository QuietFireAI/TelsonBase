# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_agents_memory_depth.py
# REM: Depth coverage for agents/memory_agent.py
# REM: Pure Python classes (MemoryStore, Memory, ConversationContext) + Celery task direct calls

import sys
from unittest.mock import MagicMock

if "celery" not in sys.modules:
    celery_mock = MagicMock()
    celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = celery_mock

import pytest
from datetime import datetime, timedelta, timezone

from agents.memory_agent import (
    AGENT_ID,
    CAPABILITIES,
    REQUIRES_APPROVAL_FOR,
    ConversationContext,
    Memory,
    MemoryScope,
    MemoryStore,
    MemoryType,
    add_to_context,
    cleanup,
    clear_context,
    forget_memory,
    get_context,
    get_status,
    recall_memories,
    store_memory,
    update_entity,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryAgentConstants:
    def test_agent_id(self):
        assert AGENT_ID == "memory_agent"

    def test_capabilities_is_list(self):
        assert isinstance(CAPABILITIES, list)
        assert len(CAPABILITIES) > 0

    def test_requires_approval_for(self):
        assert isinstance(REQUIRES_APPROVAL_FOR, list)
        assert "clear_all_memories" in REQUIRES_APPROVAL_FOR
        assert "export_memories" in REQUIRES_APPROVAL_FOR


# ═══════════════════════════════════════════════════════════════════════════════
# MemoryType enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryTypeEnum:
    def test_fact(self):
        assert MemoryType.FACT == "fact"

    def test_preference(self):
        assert MemoryType.PREFERENCE == "preference"

    def test_context(self):
        assert MemoryType.CONTEXT == "context"

    def test_instruction(self):
        assert MemoryType.INSTRUCTION == "instruction"

    def test_entity(self):
        assert MemoryType.ENTITY == "entity"

    def test_all_values_unique(self):
        values = [m.value for m in MemoryType]
        assert len(values) == len(set(values))


# ═══════════════════════════════════════════════════════════════════════════════
# MemoryScope enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryScopeEnum:
    def test_private(self):
        assert MemoryScope.PRIVATE == "private"

    def test_shared(self):
        assert MemoryScope.SHARED == "shared"

    def test_global(self):
        assert MemoryScope.GLOBAL == "global"


# ═══════════════════════════════════════════════════════════════════════════════
# Memory dataclass
# ═══════════════════════════════════════════════════════════════════════════════

def _make_memory(memory_id="mem-001", owner_id="agent-A", expires_at=None, importance=0.5):
    now = datetime.now(timezone.utc)
    return Memory(
        memory_id=memory_id,
        owner_id=owner_id,
        memory_type=MemoryType.FACT,
        scope=MemoryScope.PRIVATE,
        content="Test content",
        metadata={"source": "test"},
        created_at=now,
        expires_at=expires_at,
        last_accessed=now,
        importance=importance,
    )


class TestMemoryIsExpired:
    def test_no_expiry_never_expires(self):
        m = _make_memory()
        assert m.is_expired() is False

    def test_future_expiry_not_expired(self):
        m = _make_memory(expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        assert m.is_expired() is False

    def test_past_expiry_is_expired(self):
        m = _make_memory(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        assert m.is_expired() is True


class TestMemoryToDict:
    def test_to_dict_has_required_keys(self):
        m = _make_memory()
        d = m.to_dict()
        for key in ["memory_id", "owner_id", "memory_type", "scope", "content",
                    "metadata", "created_at", "expires_at", "last_accessed",
                    "access_count", "importance"]:
            assert key in d

    def test_to_dict_memory_id(self):
        m = _make_memory(memory_id="mem-xyz")
        assert m.to_dict()["memory_id"] == "mem-xyz"

    def test_to_dict_expires_at_none(self):
        m = _make_memory()
        assert m.to_dict()["expires_at"] is None

    def test_to_dict_expires_at_isoformat(self):
        exp = datetime.now(timezone.utc) + timedelta(hours=2)
        m = _make_memory(expires_at=exp)
        assert m.to_dict()["expires_at"] == exp.isoformat()

    def test_to_dict_memory_type_is_string(self):
        m = _make_memory()
        assert m.to_dict()["memory_type"] == "fact"

    def test_to_dict_scope_is_string(self):
        m = _make_memory()
        assert m.to_dict()["scope"] == "private"

    def test_to_dict_importance(self):
        m = _make_memory(importance=0.9)
        assert m.to_dict()["importance"] == 0.9


# ═══════════════════════════════════════════════════════════════════════════════
# ConversationContext
# ═══════════════════════════════════════════════════════════════════════════════

class TestConversationContext:
    def _make_ctx(self, max_messages=20):
        now = datetime.now(timezone.utc)
        return ConversationContext(
            context_id="ctx-001",
            agent_id="agent-A",
            user_id="user-001",
            messages=[],
            created_at=now,
            last_updated=now,
            max_messages=max_messages,
        )

    def test_add_message_appends(self):
        ctx = self._make_ctx()
        ctx.add_message("user", "hello")
        assert len(ctx.messages) == 1

    def test_add_message_role_content(self):
        ctx = self._make_ctx()
        ctx.add_message("assistant", "world")
        assert ctx.messages[0]["role"] == "assistant"
        assert ctx.messages[0]["content"] == "world"

    def test_add_message_has_timestamp(self):
        ctx = self._make_ctx()
        ctx.add_message("user", "hi")
        assert "timestamp" in ctx.messages[0]

    def test_add_message_metadata_default_empty(self):
        ctx = self._make_ctx()
        ctx.add_message("user", "hi")
        assert ctx.messages[0]["metadata"] == {}

    def test_add_message_metadata_passed(self):
        ctx = self._make_ctx()
        ctx.add_message("user", "hi", metadata={"token_count": 5})
        assert ctx.messages[0]["metadata"]["token_count"] == 5

    def test_add_message_updates_last_updated(self):
        ctx = self._make_ctx()
        old_ts = ctx.last_updated
        ctx.add_message("user", "hi")
        assert ctx.last_updated >= old_ts

    def test_message_cap_trims_oldest(self):
        ctx = self._make_ctx(max_messages=3)
        for i in range(5):
            ctx.add_message("user", f"msg-{i}")
        assert len(ctx.messages) == 3
        # Only last 3 remain
        assert ctx.messages[0]["content"] == "msg-2"
        assert ctx.messages[2]["content"] == "msg-4"

    def test_message_cap_exactly_at_limit_no_trim(self):
        ctx = self._make_ctx(max_messages=3)
        for i in range(3):
            ctx.add_message("user", f"msg-{i}")
        assert len(ctx.messages) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# MemoryStore
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def ms():
    return MemoryStore()


class TestMemoryStoreStoreAndGet:
    def test_store_returns_memory_id(self, ms):
        m = _make_memory("mem-store-001")
        result = ms.store_memory(m)
        assert result == "mem-store-001"

    def test_get_memory_returns_memory(self, ms):
        m = _make_memory("mem-get-001", owner_id="owner-A")
        ms.store_memory(m)
        retrieved = ms.get_memory("mem-get-001", "owner-A")
        assert retrieved is not None
        assert retrieved.memory_id == "mem-get-001"

    def test_get_memory_increments_access_count(self, ms):
        m = _make_memory("mem-acc-001", owner_id="owner-A")
        ms.store_memory(m)
        ms.get_memory("mem-acc-001", "owner-A")
        ms.get_memory("mem-acc-001", "owner-A")
        # After 2 accesses, access_count should be 2
        assert ms._memories["mem-acc-001"].access_count == 2

    def test_get_nonexistent_returns_none(self, ms):
        assert ms.get_memory("no-such-id", "owner") is None

    def test_get_expired_returns_none(self, ms):
        m = _make_memory("mem-exp-001", owner_id="owner-A",
                         expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        ms.store_memory(m)
        assert ms.get_memory("mem-exp-001", "owner-A") is None

    def test_get_by_non_owner_private_returns_none(self, ms):
        m = _make_memory("mem-priv-001", owner_id="owner-A")
        ms.store_memory(m)
        assert ms.get_memory("mem-priv-001", "other-owner") is None

    def test_get_global_scope_accessible_by_anyone(self, ms):
        now = datetime.now(timezone.utc)
        m = Memory(
            memory_id="mem-global-001",
            owner_id="owner-A",
            memory_type=MemoryType.FACT,
            scope=MemoryScope.GLOBAL,
            content="global fact",
            metadata={},
            created_at=now,
            expires_at=None,
            last_accessed=now,
        )
        ms.store_memory(m)
        retrieved = ms.get_memory("mem-global-001", "completely-different-agent")
        assert retrieved is not None

    def test_get_shared_accessible_by_shared_with(self, ms):
        now = datetime.now(timezone.utc)
        m = Memory(
            memory_id="mem-shared-001",
            owner_id="owner-A",
            memory_type=MemoryType.FACT,
            scope=MemoryScope.SHARED,
            content="shared info",
            metadata={},
            created_at=now,
            expires_at=None,
            last_accessed=now,
            shared_with=["agent-B"],
        )
        ms.store_memory(m)
        assert ms.get_memory("mem-shared-001", "agent-B") is not None
        assert ms.get_memory("mem-shared-001", "agent-C") is None


class TestMemoryStoreSearch:
    def test_search_returns_owner_memories(self, ms):
        m = _make_memory("mem-srch-001", owner_id="owner-search")
        ms.store_memory(m)
        results = ms.search_memories("owner-search")
        assert any(r.memory_id == "mem-srch-001" for r in results)

    def test_search_excludes_other_owners(self, ms):
        m = _make_memory("mem-srch-other-001", owner_id="other-owner-X")
        ms.store_memory(m)
        results = ms.search_memories("owner-A")
        assert not any(r.memory_id == "mem-srch-other-001" for r in results)

    def test_search_by_query_match(self, ms):
        now = datetime.now(timezone.utc)
        m = Memory(
            memory_id="mem-query-001",
            owner_id="owner-Q",
            memory_type=MemoryType.FACT,
            scope=MemoryScope.PRIVATE,
            content="The sky is blue",
            metadata={},
            created_at=now,
            expires_at=None,
            last_accessed=now,
        )
        ms.store_memory(m)
        results = ms.search_memories("owner-Q", query="blue")
        assert any(r.memory_id == "mem-query-001" for r in results)

    def test_search_by_query_no_match(self, ms):
        now = datetime.now(timezone.utc)
        m = Memory(
            memory_id="mem-query-002",
            owner_id="owner-Q2",
            memory_type=MemoryType.FACT,
            scope=MemoryScope.PRIVATE,
            content="The sky is blue",
            metadata={},
            created_at=now,
            expires_at=None,
            last_accessed=now,
        )
        ms.store_memory(m)
        results = ms.search_memories("owner-Q2", query="purple")
        assert not any(r.memory_id == "mem-query-002" for r in results)

    def test_search_by_memory_type_filter(self, ms):
        now = datetime.now(timezone.utc)
        m_fact = Memory(
            memory_id="mem-fact-001",
            owner_id="owner-T",
            memory_type=MemoryType.FACT,
            scope=MemoryScope.PRIVATE,
            content="a fact",
            metadata={},
            created_at=now,
            expires_at=None,
            last_accessed=now,
        )
        m_pref = Memory(
            memory_id="mem-pref-001",
            owner_id="owner-T",
            memory_type=MemoryType.PREFERENCE,
            scope=MemoryScope.PRIVATE,
            content="a preference",
            metadata={},
            created_at=now,
            expires_at=None,
            last_accessed=now,
        )
        ms.store_memory(m_fact)
        ms.store_memory(m_pref)
        results = ms.search_memories("owner-T", memory_type=MemoryType.PREFERENCE)
        ids = [r.memory_id for r in results]
        assert "mem-pref-001" in ids
        assert "mem-fact-001" not in ids

    def test_search_limit_respected(self, ms):
        now = datetime.now(timezone.utc)
        for i in range(5):
            m = Memory(
                memory_id=f"mem-limit-{i:03d}",
                owner_id="owner-lim",
                memory_type=MemoryType.FACT,
                scope=MemoryScope.PRIVATE,
                content=f"content {i}",
                metadata={},
                created_at=now,
                expires_at=None,
                last_accessed=now,
            )
            ms.store_memory(m)
        results = ms.search_memories("owner-lim", limit=3)
        assert len(results) <= 3

    def test_search_excludes_expired(self, ms):
        now = datetime.now(timezone.utc)
        m = Memory(
            memory_id="mem-exp-srch-001",
            owner_id="owner-exp",
            memory_type=MemoryType.FACT,
            scope=MemoryScope.PRIVATE,
            content="expired",
            metadata={},
            created_at=now,
            expires_at=now - timedelta(seconds=1),
            last_accessed=now,
        )
        ms.store_memory(m)
        results = ms.search_memories("owner-exp")
        assert not any(r.memory_id == "mem-exp-srch-001" for r in results)


class TestMemoryStoreDelete:
    def test_delete_by_owner_succeeds(self, ms):
        m = _make_memory("mem-del-001", owner_id="owner-del")
        ms.store_memory(m)
        result = ms.delete_memory("mem-del-001", "owner-del")
        assert result is True
        assert ms.get_memory("mem-del-001", "owner-del") is None

    def test_delete_nonexistent_returns_false(self, ms):
        assert ms.delete_memory("no-such-id", "owner") is False

    def test_delete_by_non_owner_returns_false(self, ms):
        m = _make_memory("mem-del-nonowner-001", owner_id="owner-A")
        ms.store_memory(m)
        result = ms.delete_memory("mem-del-nonowner-001", "owner-B")
        assert result is False
        # Memory still exists
        assert ms.get_memory("mem-del-nonowner-001", "owner-A") is not None


class TestMemoryStoreContext:
    def test_get_or_create_creates_context(self, ms):
        ctx = ms.get_or_create_context("agent-ctx-001")
        assert ctx is not None
        assert ctx.agent_id == "agent-ctx-001"

    def test_get_or_create_returns_same_context(self, ms):
        ctx1 = ms.get_or_create_context("agent-ctx-same")
        ctx2 = ms.get_or_create_context("agent-ctx-same")
        assert ctx1.context_id == ctx2.context_id

    def test_get_or_create_with_user_id(self, ms):
        ctx = ms.get_or_create_context("agent-ctx-user", user_id="user-001")
        assert ctx.user_id == "user-001"

    def test_different_users_get_different_contexts(self, ms):
        ctx1 = ms.get_or_create_context("agent-ctx-diff", user_id="user-A")
        ctx2 = ms.get_or_create_context("agent-ctx-diff", user_id="user-B")
        assert ctx1.context_id != ctx2.context_id

    def test_clear_context_returns_true_if_existed(self, ms):
        ms.get_or_create_context("agent-ctx-clear-001")
        result = ms.clear_context("agent-ctx-clear-001")
        assert result is True

    def test_clear_context_returns_false_if_not_found(self, ms):
        result = ms.clear_context("agent-ctx-no-exist-xyz")
        assert result is False

    def test_clear_context_removes_context(self, ms):
        ms.get_or_create_context("agent-ctx-gone")
        ms.clear_context("agent-ctx-gone")
        # Re-creating should give a fresh context
        ctx_new = ms.get_or_create_context("agent-ctx-gone")
        assert len(ctx_new.messages) == 0


class TestMemoryStoreCleanup:
    def test_cleanup_removes_expired(self, ms):
        now = datetime.now(timezone.utc)
        m = Memory(
            memory_id="mem-cleanup-exp-001",
            owner_id="owner-cleanup",
            memory_type=MemoryType.FACT,
            scope=MemoryScope.PRIVATE,
            content="expired",
            metadata={},
            created_at=now,
            expires_at=now - timedelta(seconds=1),
            last_accessed=now,
        )
        ms.store_memory(m)
        count = ms.cleanup_expired()
        assert count >= 1
        assert "mem-cleanup-exp-001" not in ms._memories

    def test_cleanup_preserves_valid(self, ms):
        m = _make_memory("mem-cleanup-valid-001", owner_id="owner-valid")
        ms.store_memory(m)
        ms.cleanup_expired()
        assert "mem-cleanup-valid-001" in ms._memories

    def test_cleanup_returns_count(self, ms):
        count = ms.cleanup_expired()
        assert isinstance(count, int)
        assert count >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# Celery task functions — called directly (no Celery broker needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStoreMemoryTask:
    def test_store_memory_returns_success(self):
        result = store_memory("owner-task-001", "test content")
        assert result["status"] == "success"
        assert "memory_id" in result
        assert result["memory_id"].startswith("mem_")

    def test_store_memory_default_type_fact(self):
        result = store_memory("owner-task-002", "content", memory_type="fact")
        assert result["memory"]["memory_type"] == "fact"

    def test_store_memory_invalid_type_defaults_to_fact(self):
        result = store_memory("owner-task-003", "content", memory_type="invalid_type")
        assert result["memory"]["memory_type"] == "fact"

    def test_store_memory_invalid_scope_defaults_to_private(self):
        result = store_memory("owner-task-004", "content", scope="invalid_scope")
        assert result["memory"]["scope"] == "private"

    def test_store_memory_with_expiry(self):
        result = store_memory("owner-task-005", "expires soon", expires_hours=1.0)
        assert result["memory"]["expires_at"] is not None

    def test_store_memory_no_expiry(self):
        result = store_memory("owner-task-006", "no expiry")
        assert result["memory"]["expires_at"] is None

    def test_store_memory_importance_clamped(self):
        result = store_memory("owner-task-007", "content", importance=2.0)
        assert result["memory"]["importance"] == 1.0

    def test_store_memory_importance_clamped_low(self):
        result = store_memory("owner-task-008", "content", importance=-1.0)
        assert result["memory"]["importance"] == 0.0

    def test_store_memory_with_metadata(self):
        result = store_memory("owner-task-009", "content", metadata={"key": "val"})
        assert result["status"] == "success"

    def test_store_memory_with_shared_with(self):
        result = store_memory("owner-task-010", "shared content",
                              scope="shared", shared_with=["agent-X"])
        assert result["status"] == "success"

    def test_store_memory_qms_status(self):
        result = store_memory("owner-task-011", "content")
        assert result["qms_status"] == "Thank_You"


class TestRecallMemoriesTask:
    def test_recall_returns_list(self):
        result = recall_memories("owner-recall-001")
        assert "memories" in result
        assert isinstance(result["memories"], list)

    def test_recall_includes_stored(self):
        store_memory("owner-recall-002", "specific content for recall test")
        result = recall_memories("owner-recall-002")
        assert result["count"] >= 1

    def test_recall_with_query(self):
        store_memory("owner-recall-003", "unique recall phrase xyz123")
        result = recall_memories("owner-recall-003", query="unique recall phrase xyz123")
        assert result["count"] >= 1

    def test_recall_invalid_type_returns_all(self):
        result = recall_memories("owner-recall-004", memory_type="bad_type")
        assert "memories" in result

    def test_recall_valid_type_filter(self):
        store_memory("owner-recall-005", "pref content", memory_type="preference")
        result = recall_memories("owner-recall-005", memory_type="preference")
        assert result["status"] == "success"

    def test_recall_qms_status(self):
        result = recall_memories("owner-recall-006")
        assert result["qms_status"] == "Thank_You"


class TestForgetMemoryTask:
    def test_forget_existing_memory(self):
        stored = store_memory("owner-forget-001", "to be forgotten")
        mem_id = stored["memory_id"]
        result = forget_memory("owner-forget-001", mem_id)
        assert result["status"] == "success"
        assert result["deleted"] == mem_id

    def test_forget_nonexistent_memory(self):
        result = forget_memory("owner-forget-002", "mem_nonexistent_xyz")
        assert result["status"] == "error"
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()

    def test_forget_wrong_owner(self):
        stored = store_memory("owner-forget-003", "to be forgotten")
        mem_id = stored["memory_id"]
        result = forget_memory("other-owner", mem_id)
        assert result["status"] == "error"


class TestAddToContextTask:
    def test_add_to_context_success(self):
        result = add_to_context("agent-add-ctx-001", "user", "Hello")
        assert result["status"] == "success"
        assert "context_id" in result

    def test_add_to_context_increments_count(self):
        add_to_context("agent-add-ctx-002", "user", "msg1")
        result = add_to_context("agent-add-ctx-002", "assistant", "reply")
        assert result["message_count"] >= 2

    def test_add_to_context_with_user_id(self):
        result = add_to_context("agent-add-ctx-003", "user", "hi", user_id="user-001")
        assert result["status"] == "success"

    def test_add_to_context_qms_status(self):
        result = add_to_context("agent-add-ctx-004", "user", "test")
        assert result["qms_status"] == "Thank_You"


class TestGetContextTask:
    def test_get_context_returns_messages(self):
        add_to_context("agent-get-ctx-001", "user", "hello")
        result = get_context("agent-get-ctx-001")
        assert result["status"] == "success"
        assert isinstance(result["messages"], list)

    def test_get_context_with_last_n(self):
        for i in range(5):
            add_to_context("agent-get-ctx-002", "user", f"msg {i}")
        result = get_context("agent-get-ctx-002", last_n=2)
        assert len(result["messages"]) == 2

    def test_get_context_has_entities(self):
        result = get_context("agent-get-ctx-003")
        assert "entities" in result

    def test_get_context_qms_status(self):
        result = get_context("agent-get-ctx-004")
        assert result["qms_status"] == "Thank_You"


class TestClearContextTask:
    def test_clear_existing_context(self):
        add_to_context("agent-clear-ctx-001", "user", "msg")
        result = clear_context("agent-clear-ctx-001")
        assert result["status"] == "success"

    def test_clear_nonexistent_context(self):
        result = clear_context("agent-clear-ctx-nonexist-xyz")
        assert result["status"] == "success"
        assert result["cleared"] is False

    def test_clear_context_qms_status(self):
        result = clear_context("agent-clear-ctx-002")
        assert result["qms_status"] == "Thank_You"


class TestUpdateEntityTask:
    def test_update_entity_success(self):
        result = update_entity("agent-ent-001", "user_name", "Alice")
        assert result["status"] == "success"
        assert result["entity"] == "user_name"

    def test_update_entity_persists(self):
        update_entity("agent-ent-002", "city", "Springfield")
        ctx_result = get_context("agent-ent-002")
        assert "city" in ctx_result["entities"]

    def test_update_entity_with_user_id(self):
        result = update_entity("agent-ent-003", "pref", "dark_mode", user_id="u-001")
        assert result["status"] == "success"

    def test_update_entity_qms_status(self):
        result = update_entity("agent-ent-004", "key", "value")
        assert result["qms_status"] == "Thank_You"


class TestCleanupTask:
    def test_cleanup_returns_success(self):
        result = cleanup()
        assert result["status"] == "success"
        assert isinstance(result["expired_removed"], int)

    def test_cleanup_qms_status(self):
        result = cleanup()
        assert result["qms_status"] == "Thank_You"


class TestGetStatusTask:
    def test_get_status_returns_agent_id(self):
        result = get_status()
        assert result["agent_id"] == "memory_agent"

    def test_get_status_healthy(self):
        result = get_status()
        assert result["status"] == "healthy"

    def test_get_status_has_stats(self):
        result = get_status()
        assert "stats" in result
        stats = result["stats"]
        assert "total_memories" in stats
        assert "total_contexts" in stats

    def test_get_status_capabilities_list(self):
        result = get_status()
        assert isinstance(result["capabilities"], list)

    def test_get_status_qms_status(self):
        result = get_status()
        assert result["qms_status"] == "Thank_You"
