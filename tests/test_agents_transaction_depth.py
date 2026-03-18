# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_agents_transaction_depth.py
# REM: Depth coverage for agents/transaction_agent.py
# REM: Enums, checklists, and TransactionCoordinatorAgent methods.

import sys
from unittest.mock import MagicMock

if "celery" not in sys.modules:
    celery_mock = MagicMock()
    celery_mock.shared_task = lambda *args, **kwargs: (lambda f: f)
    sys.modules["celery"] = celery_mock

import pytest
from datetime import datetime, timezone

from agents.base import AgentRequest
from agents.transaction_agent import (
    CHECKLIST_TEMPLATES,
    LEASE_CHECKLIST,
    PURCHASE_CHECKLIST,
    REQUIRED_DOCUMENTS,
    ChecklistItemStatus,
    DocumentStatus,
    PartyRole,
    TransactionCoordinatorAgent,
    TransactionStatus,
    TransactionType,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Enum tests — pure Python, no external deps
# ═══════════════════════════════════════════════════════════════════════════════

class TestTransactionTypeEnum:
    def test_purchase(self):
        assert TransactionType.PURCHASE == "purchase"

    def test_sale(self):
        assert TransactionType.SALE == "sale"

    def test_lease(self):
        assert TransactionType.LEASE == "lease"

    def test_refinance(self):
        assert TransactionType.REFINANCE == "refinance"

    def test_commercial(self):
        assert TransactionType.COMMERCIAL == "commercial"

    def test_all_unique(self):
        values = [t.value for t in TransactionType]
        assert len(values) == len(set(values))


class TestTransactionStatusEnum:
    def test_draft(self):
        assert TransactionStatus.DRAFT == "draft"

    def test_active(self):
        assert TransactionStatus.ACTIVE == "active"

    def test_pending_closing(self):
        assert TransactionStatus.PENDING_CLOSING == "pending_closing"

    def test_closed(self):
        assert TransactionStatus.CLOSED == "closed"

    def test_cancelled(self):
        assert TransactionStatus.CANCELLED == "cancelled"

    def test_on_hold(self):
        assert TransactionStatus.ON_HOLD == "on_hold"


class TestPartyRoleEnum:
    def test_buyer(self):
        assert PartyRole.BUYER == "buyer"

    def test_seller(self):
        assert PartyRole.SELLER == "seller"

    def test_listing_agent(self):
        assert PartyRole.LISTING_AGENT == "listing_agent"

    def test_buyers_agent(self):
        assert PartyRole.BUYERS_AGENT == "buyers_agent"

    def test_lender(self):
        assert PartyRole.LENDER == "lender"

    def test_title_company(self):
        assert PartyRole.TITLE_COMPANY == "title_company"

    def test_attorney(self):
        assert PartyRole.ATTORNEY == "attorney"

    def test_inspector(self):
        assert PartyRole.INSPECTOR == "inspector"


class TestChecklistItemStatusEnum:
    def test_not_started(self):
        assert ChecklistItemStatus.NOT_STARTED == "not_started"

    def test_in_progress(self):
        assert ChecklistItemStatus.IN_PROGRESS == "in_progress"

    def test_completed(self):
        assert ChecklistItemStatus.COMPLETED == "completed"

    def test_waived(self):
        assert ChecklistItemStatus.WAIVED == "waived"

    def test_overdue(self):
        assert ChecklistItemStatus.OVERDUE == "overdue"


class TestDocumentStatusEnum:
    def test_pending(self):
        assert DocumentStatus.PENDING == "pending"

    def test_received(self):
        assert DocumentStatus.RECEIVED == "received"

    def test_under_review(self):
        assert DocumentStatus.UNDER_REVIEW == "under_review"

    def test_approved(self):
        assert DocumentStatus.APPROVED == "approved"

    def test_rejected(self):
        assert DocumentStatus.REJECTED == "rejected"

    def test_expired(self):
        assert DocumentStatus.EXPIRED == "expired"


# ═══════════════════════════════════════════════════════════════════════════════
# Checklist data structures
# ═══════════════════════════════════════════════════════════════════════════════

class TestPurchaseChecklist:
    def test_is_list(self):
        assert isinstance(PURCHASE_CHECKLIST, list)

    def test_has_items(self):
        assert len(PURCHASE_CHECKLIST) > 0

    def test_each_item_has_id(self):
        for item in PURCHASE_CHECKLIST:
            assert "id" in item

    def test_each_item_has_item_text(self):
        for item in PURCHASE_CHECKLIST:
            assert "item" in item

    def test_each_item_has_category(self):
        for item in PURCHASE_CHECKLIST:
            assert "category" in item

    def test_each_item_has_days_from_start(self):
        for item in PURCHASE_CHECKLIST:
            assert "days_from_start" in item

    def test_first_item_is_zero_days(self):
        assert PURCHASE_CHECKLIST[0]["days_from_start"] == 0

    def test_categories_are_strings(self):
        for item in PURCHASE_CHECKLIST:
            assert isinstance(item["category"], str)


class TestLeaseChecklist:
    def test_is_list(self):
        assert isinstance(LEASE_CHECKLIST, list)

    def test_has_items(self):
        assert len(LEASE_CHECKLIST) > 0

    def test_shorter_than_purchase(self):
        assert len(LEASE_CHECKLIST) < len(PURCHASE_CHECKLIST)

    def test_ids_start_with_lck(self):
        assert all(item["id"].startswith("LCK-") for item in LEASE_CHECKLIST)


class TestChecklistTemplates:
    def test_purchase_template_exists(self):
        assert TransactionType.PURCHASE in CHECKLIST_TEMPLATES

    def test_sale_template_exists(self):
        assert TransactionType.SALE in CHECKLIST_TEMPLATES

    def test_lease_template_exists(self):
        assert TransactionType.LEASE in CHECKLIST_TEMPLATES

    def test_refinance_template_exists(self):
        assert TransactionType.REFINANCE in CHECKLIST_TEMPLATES

    def test_commercial_template_exists(self):
        assert TransactionType.COMMERCIAL in CHECKLIST_TEMPLATES

    def test_refinance_is_subset_of_purchase(self):
        refinance = CHECKLIST_TEMPLATES[TransactionType.REFINANCE]
        assert len(refinance) < len(PURCHASE_CHECKLIST)


class TestRequiredDocuments:
    def test_purchase_docs_exist(self):
        assert TransactionType.PURCHASE in REQUIRED_DOCUMENTS

    def test_lease_docs_exist(self):
        assert TransactionType.LEASE in REQUIRED_DOCUMENTS

    def test_purchase_has_many_docs(self):
        assert len(REQUIRED_DOCUMENTS[TransactionType.PURCHASE]) >= 10

    def test_lease_has_docs(self):
        assert len(REQUIRED_DOCUMENTS[TransactionType.LEASE]) >= 5

    def test_each_doc_has_id(self):
        for doc in REQUIRED_DOCUMENTS[TransactionType.PURCHASE]:
            assert "id" in doc

    def test_each_doc_has_name(self):
        for doc in REQUIRED_DOCUMENTS[TransactionType.PURCHASE]:
            assert "name" in doc

    def test_each_doc_has_required_flag(self):
        for doc in REQUIRED_DOCUMENTS[TransactionType.PURCHASE]:
            assert "required" in doc
            assert isinstance(doc["required"], bool)

    def test_sale_same_as_purchase(self):
        assert REQUIRED_DOCUMENTS[TransactionType.SALE] is REQUIRED_DOCUMENTS[TransactionType.PURCHASE]


# ═══════════════════════════════════════════════════════════════════════════════
# TransactionCoordinatorAgent — full agent tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def agent():
    """Fresh TransactionCoordinatorAgent for the test module."""
    return TransactionCoordinatorAgent()


def _req(action, payload=None):
    return AgentRequest(action=action, payload=payload or {}, requester="test")


class TestAgentInit:
    def test_agent_creates(self, agent):
        assert agent is not None

    def test_agent_name(self, agent):
        assert agent.AGENT_NAME == "transaction_agent"

    def test_has_demo_transactions(self, agent):
        assert len(agent._transactions) >= 3

    def test_seeded_txn_001_exists(self, agent):
        assert "TXN-2026-001" in agent._transactions

    def test_seeded_txn_002_exists(self, agent):
        assert "TXN-2026-002" in agent._transactions

    def test_seeded_txn_003_closed(self, agent):
        assert agent._transactions["TXN-2026-003"]["status"] == "closed"


class TestBuildChecklist:
    def test_build_purchase_checklist(self, agent):
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        result = agent._build_checklist(TransactionType.PURCHASE, now)
        assert len(result) == len(PURCHASE_CHECKLIST)

    def test_checklist_item_has_status_not_started(self, agent):
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        result = agent._build_checklist(TransactionType.PURCHASE, now)
        for item in result:
            assert item["status"] == ChecklistItemStatus.NOT_STARTED.value

    def test_checklist_item_has_deadline(self, agent):
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        result = agent._build_checklist(TransactionType.PURCHASE, now)
        for item in result:
            assert "deadline" in item

    def test_build_lease_checklist(self, agent):
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        result = agent._build_checklist(TransactionType.LEASE, now)
        assert len(result) == len(LEASE_CHECKLIST)


class TestBuildDocumentTracker:
    def test_build_purchase_docs(self, agent):
        result = agent._build_document_tracker(TransactionType.PURCHASE)
        assert len(result) == len(REQUIRED_DOCUMENTS[TransactionType.PURCHASE])

    def test_doc_has_pending_status(self, agent):
        result = agent._build_document_tracker(TransactionType.PURCHASE)
        for doc in result:
            assert doc["status"] == DocumentStatus.PENDING.value

    def test_doc_has_received_at_none(self, agent):
        result = agent._build_document_tracker(TransactionType.PURCHASE)
        for doc in result:
            assert doc["received_at"] is None

    def test_build_lease_docs(self, agent):
        result = agent._build_document_tracker(TransactionType.LEASE)
        assert len(result) == len(REQUIRED_DOCUMENTS[TransactionType.LEASE])


class TestCreateTransaction:
    def test_create_purchase_transaction(self, agent):
        result = agent._create_transaction({
            "type": "purchase",
            "property_address": "123 Test St",
            "purchase_price": 300000,
        })
        assert "transaction_id" in result
        assert result["status"] == "created"
        assert result["type"] == "purchase"

    def test_create_generates_checklist(self, agent):
        result = agent._create_transaction({"type": "purchase"})
        assert result["checklist_items"] == len(PURCHASE_CHECKLIST)

    def test_create_generates_documents(self, agent):
        result = agent._create_transaction({"type": "purchase"})
        assert result["required_documents"] > 0

    def test_create_lease_transaction(self, agent):
        result = agent._create_transaction({"type": "lease"})
        assert result["type"] == "lease"
        assert result["checklist_items"] == len(LEASE_CHECKLIST)

    def test_create_invalid_type_raises(self, agent):
        with pytest.raises(ValueError, match="Invalid transaction type"):
            agent._create_transaction({"type": "invalid_type_xyz"})

    def test_created_transaction_is_stored(self, agent):
        result = agent._create_transaction({"type": "purchase"})
        tx_id = result["transaction_id"]
        assert tx_id in agent._transactions

    def test_new_transaction_is_draft(self, agent):
        result = agent._create_transaction({"type": "purchase"})
        tx = agent._transactions[result["transaction_id"]]
        assert tx["status"] == "draft"


class TestGetTransaction:
    def test_get_existing_transaction(self, agent):
        result = agent._get_transaction({"transaction_id": "TXN-2026-001"})
        assert result["transaction_id"] == "TXN-2026-001"

    def test_get_nonexistent_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            agent._get_transaction({"transaction_id": "TXN-DOES-NOT-EXIST"})

    def test_get_with_no_id_raises(self, agent):
        with pytest.raises(ValueError):
            agent._get_transaction({})


class TestListTransactions:
    def test_list_all_returns_all(self, agent):
        result = agent._list_transactions({})
        assert result["count"] == len(agent._transactions)

    def test_list_by_status_filter(self, agent):
        result = agent._list_transactions({"status": "closed"})
        assert all(t["status"] == "closed" for t in result["transactions"])

    def test_list_by_type_filter(self, agent):
        result = agent._list_transactions({"type": "lease"})
        assert all(t["type"] == "lease" for t in result["transactions"])

    def test_list_by_tenant_filter(self, agent):
        result = agent._list_transactions({"tenant_id": "tenant_remax_north"})
        assert result["count"] >= 1

    def test_list_returns_count(self, agent):
        result = agent._list_transactions({})
        assert result["count"] == len(result["transactions"])

    def test_list_item_has_required_fields(self, agent):
        result = agent._list_transactions({})
        for tx in result["transactions"]:
            assert "transaction_id" in tx
            assert "type" in tx
            assert "status" in tx


class TestUpdateTransaction:
    def test_update_purchase_price(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        result = agent._update_transaction({
            "transaction_id": tx_id,
            "purchase_price": 400000,
        })
        assert "purchase_price" in result["updated_fields"]
        assert agent._transactions[tx_id]["purchase_price"] == 400000

    def test_update_nonexistent_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            agent._update_transaction({"transaction_id": "TXN-NO-EXIST", "status": "active"})

    def test_update_sets_updated_at(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        agent._update_transaction({"transaction_id": tx_id, "status": "active"})
        assert "updated_at" in agent._transactions[tx_id]


class TestCloseTransaction:
    def test_close_transaction(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        result = agent._close_transaction({"transaction_id": tx_id})
        assert result["status"] == "closed"
        assert agent._transactions[tx_id]["status"] == "closed"

    def test_close_nonexistent_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            agent._close_transaction({"transaction_id": "TXN-NO-EXIST"})

    def test_close_has_warnings_for_incomplete(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        result = agent._close_transaction({"transaction_id": tx_id})
        # New transaction has no docs approved and incomplete checklist
        assert len(result["warnings"]) > 0

    def test_close_sets_closed_at(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        agent._close_transaction({"transaction_id": tx_id})
        assert "closed_at" in agent._transactions[tx_id]


class TestCancelTransaction:
    def test_cancel_transaction(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        result = agent._cancel_transaction({"transaction_id": tx_id, "reason": "Client withdrew"})
        assert result["status"] == "cancelled"
        assert agent._transactions[tx_id]["status"] == "cancelled"

    def test_cancel_records_reason(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        agent._cancel_transaction({"transaction_id": tx_id, "reason": "Test reason"})
        assert agent._transactions[tx_id]["cancellation_reason"] == "Test reason"

    def test_cancel_nonexistent_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            agent._cancel_transaction({"transaction_id": "TXN-NO-EXIST"})


class TestPartyManagement:
    def test_add_party(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        result = agent._add_party({
            "transaction_id": tx_id,
            "name": "Jane Doe",
            "role": "buyer",
            "email": "jane@example.com",
            "phone": "555-0001",
        })
        assert result["party_added"] == "Jane Doe"
        assert len(agent._transactions[tx_id]["parties"]) == 1

    def test_add_party_nonexistent_tx_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            agent._add_party({"transaction_id": "TXN-NO-EXIST", "name": "X"})

    def test_remove_party(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        agent._add_party({"transaction_id": tx_id, "name": "To Remove", "role": "buyer"})
        result = agent._remove_party({"transaction_id": tx_id, "name": "To Remove"})
        assert result["removed_count"] == 1
        assert len(agent._transactions[tx_id]["parties"]) == 0

    def test_remove_nonexistent_party(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        result = agent._remove_party({"transaction_id": tx_id, "name": "Ghost"})
        assert result["removed_count"] == 0

    def test_list_parties(self, agent):
        result = agent._list_parties({"transaction_id": "TXN-2026-001"})
        assert "parties" in result
        assert result["count"] >= 2

    def test_list_parties_nonexistent_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            agent._list_parties({"transaction_id": "TXN-NO-EXIST"})


class TestChecklistManagement:
    def test_update_checklist_item(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        first_id = agent._transactions[tx_id]["checklist"][0]["id"]
        result = agent._update_checklist({
            "transaction_id": tx_id,
            "item_id": first_id,
            "status": "completed",
        })
        assert result["new_status"] == "completed"

    def test_update_checklist_completed_sets_timestamp(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        first_id = agent._transactions[tx_id]["checklist"][0]["id"]
        agent._update_checklist({
            "transaction_id": tx_id,
            "item_id": first_id,
            "status": "completed",
        })
        assert agent._transactions[tx_id]["checklist"][0]["completed_at"] is not None

    def test_update_checklist_invalid_status_raises(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        first_id = agent._transactions[tx_id]["checklist"][0]["id"]
        with pytest.raises(ValueError, match="Invalid status"):
            agent._update_checklist({
                "transaction_id": tx_id,
                "item_id": first_id,
                "status": "bad_status_xyz",
            })

    def test_update_checklist_nonexistent_item_raises(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        with pytest.raises(ValueError, match="not found"):
            agent._update_checklist({
                "transaction_id": tx_id,
                "item_id": "CHK-NONEXISTENT",
                "status": "completed",
            })

    def test_get_checklist_stats(self, agent):
        result = agent._get_checklist({"transaction_id": "TXN-2026-001"})
        assert "total" in result
        assert "completed" in result
        assert "in_progress" in result
        assert "overdue" in result
        assert "completion_pct" in result

    def test_get_checklist_completion_pct_range(self, agent):
        result = agent._get_checklist({"transaction_id": "TXN-2026-001"})
        assert 0.0 <= result["completion_pct"] <= 100.0

    def test_get_checklist_nonexistent_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            agent._get_checklist({"transaction_id": "TXN-NO-EXIST"})

    def test_update_checklist_with_notes(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        first_id = agent._transactions[tx_id]["checklist"][0]["id"]
        agent._update_checklist({
            "transaction_id": tx_id,
            "item_id": first_id,
            "status": "in_progress",
            "notes": "Inspector called",
        })
        assert agent._transactions[tx_id]["checklist"][0]["notes"] == "Inspector called"


class TestDeadlineChecking:
    def test_check_deadlines_returns_result(self, agent):
        result = agent._check_deadlines({})
        assert "overdue" in result
        assert "upcoming" in result
        assert "checked_at" in result

    def test_check_deadlines_overdue_is_list(self, agent):
        result = agent._check_deadlines({})
        assert isinstance(result["overdue"], list)

    def test_check_deadlines_upcoming_is_list(self, agent):
        result = agent._check_deadlines({})
        assert isinstance(result["upcoming"], list)

    def test_check_deadlines_skips_closed(self, agent):
        result = agent._check_deadlines({"transaction_id": "TXN-2026-003"})
        # TXN-2026-003 is closed, so no overdue/upcoming items
        assert result["overdue_count"] == 0
        assert result["upcoming_count"] == 0

    def test_check_deadlines_specific_tx(self, agent):
        result = agent._check_deadlines({"transaction_id": "TXN-2026-001"})
        assert isinstance(result["overdue"], list)

    def test_check_deadlines_custom_lookahead(self, agent):
        result = agent._check_deadlines({"lookahead_days": 3})
        assert result["lookahead_days"] == 3


class TestOverrideDeadline:
    def test_override_deadline(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        first_id = agent._transactions[tx_id]["checklist"][0]["id"]
        new_deadline = "2026-12-31T00:00:00+00:00"
        result = agent._override_deadline({
            "transaction_id": tx_id,
            "item_id": first_id,
            "new_deadline": new_deadline,
            "reason": "Client requested extension",
        })
        assert result["new_deadline"] == new_deadline
        assert result["reason"] == "Client requested extension"

    def test_override_nonexistent_item_raises(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        with pytest.raises(ValueError, match="not found"):
            agent._override_deadline({
                "transaction_id": tx_id,
                "item_id": "CHK-NONEXIST",
                "new_deadline": "2026-12-31T00:00:00+00:00",
            })


class TestDocumentTracking:
    def test_update_document_status(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        first_doc_id = agent._transactions[tx_id]["documents"][0]["id"]
        result = agent._update_document_status({
            "transaction_id": tx_id,
            "document_id": first_doc_id,
            "status": "received",
        })
        assert result["new_status"] == "received"

    def test_update_document_received_sets_timestamp(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        first_doc_id = agent._transactions[tx_id]["documents"][0]["id"]
        agent._update_document_status({
            "transaction_id": tx_id,
            "document_id": first_doc_id,
            "status": "received",
        })
        assert agent._transactions[tx_id]["documents"][0]["received_at"] is not None

    def test_update_document_invalid_status_raises(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        first_doc_id = agent._transactions[tx_id]["documents"][0]["id"]
        with pytest.raises(ValueError, match="Invalid status"):
            agent._update_document_status({
                "transaction_id": tx_id,
                "document_id": first_doc_id,
                "status": "bad_status_xyz",
            })

    def test_update_document_nonexistent_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            agent._update_document_status({
                "transaction_id": "TXN-2026-001",
                "document_id": "DOC-NONEXIST",
                "status": "received",
            })

    def test_get_documents_stats(self, agent):
        result = agent._get_documents({"transaction_id": "TXN-2026-001"})
        assert "total" in result
        assert "required" in result
        assert "approved" in result
        assert "pending" in result
        assert "documents" in result

    def test_get_documents_nonexistent_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            agent._get_documents({"transaction_id": "TXN-NO-EXIST"})

    def test_update_document_with_reviewer(self, agent):
        tx_result = agent._create_transaction({"type": "purchase"})
        tx_id = tx_result["transaction_id"]
        first_doc_id = agent._transactions[tx_id]["documents"][0]["id"]
        agent._update_document_status({
            "transaction_id": tx_id,
            "document_id": first_doc_id,
            "status": "approved",
            "reviewed_by": "John Smith",
        })
        assert agent._transactions[tx_id]["documents"][0]["reviewed_by"] == "John Smith"


class TestTransactionSummary:
    def test_summary_returns_all_fields(self, agent):
        result = agent._transaction_summary({"transaction_id": "TXN-2026-001"})
        assert "transaction_id" in result
        assert "type" in result
        assert "status" in result
        assert "checklist_progress" in result
        assert "document_progress" in result

    def test_summary_completion_pct_in_range(self, agent):
        result = agent._transaction_summary({"transaction_id": "TXN-2026-001"})
        assert 0 <= result["checklist_progress"]["completion_pct"] <= 100
        assert 0 <= result["document_progress"]["completion_pct"] <= 100

    def test_summary_nonexistent_raises(self, agent):
        with pytest.raises(ValueError, match="not found"):
            agent._transaction_summary({"transaction_id": "TXN-NO-EXIST"})

    def test_summary_days_to_close_non_negative(self, agent):
        result = agent._transaction_summary({"transaction_id": "TXN-2026-001"})
        assert result["days_to_close"] >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# handle_request — non-approval actions
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleRequest:
    def test_handle_create_transaction(self, agent):
        req = _req("create_transaction", {"type": "purchase", "property_address": "456 Oak Ave"})
        response = agent.handle_request(req)
        assert response.success is True
        assert response.result is not None

    def test_handle_list_transactions(self, agent):
        req = _req("list_transactions", {})
        response = agent.handle_request(req)
        assert response.success is True

    def test_handle_unknown_action_returns_failure(self, agent):
        req = _req("unknown_action_xyz", {})
        response = agent.handle_request(req)
        assert response.success is False

    def test_handle_get_transaction(self, agent):
        req = _req("get_transaction", {"transaction_id": "TXN-2026-001"})
        response = agent.handle_request(req)
        assert response.success is True

    def test_handle_get_checklist(self, agent):
        req = _req("get_checklist", {"transaction_id": "TXN-2026-001"})
        response = agent.handle_request(req)
        assert response.success is True

    def test_handle_get_documents(self, agent):
        req = _req("get_documents", {"transaction_id": "TXN-2026-001"})
        response = agent.handle_request(req)
        assert response.success is True

    def test_handle_transaction_summary(self, agent):
        req = _req("transaction_summary", {"transaction_id": "TXN-2026-001"})
        response = agent.handle_request(req)
        assert response.success is True

    def test_handle_check_deadlines(self, agent):
        req = _req("check_deadlines", {"lookahead_days": 5})
        response = agent.handle_request(req)
        assert response.success is True

    def test_response_has_agent_name(self, agent):
        req = _req("list_transactions", {})
        response = agent.handle_request(req)
        assert response.agent_name == "transaction_agent"

    def test_response_has_qms_status(self, agent):
        req = _req("list_transactions", {})
        response = agent.handle_request(req)
        assert response.qms_status in ("Thank_You", "Thank_You_But_No")
