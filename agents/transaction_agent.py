# TelsonBase/agents/transaction_agent.py
# REM: =======================================================================================
# REM: TRANSACTION COORDINATOR AGENT — REAL ESTATE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: A production-ready real estate transaction coordinator agent.
# REM: Manages the full lifecycle of a real estate closing: parties, documents, deadlines,
# REM: checklists, and status tracking. Designed to demonstrate TelsonBase's security model
# REM: with a real-world use case that brokerages and title companies immediately understand.
#
# REM: This is a Third Floor agent — the first specialized industry agent on the platform.
#
# REM: Capabilities:
# REM:   - Create and manage transactions (purchase, sale, lease, refinance)
# REM:   - Track closing checklists with per-item status
# REM:   - Manage transaction parties (buyer, seller, agents, lender, title, attorney)
# REM:   - Track document status per transaction (received, pending, approved, rejected)
# REM:   - Monitor deadlines and flag overdue items
# REM:   - Generate transaction summary reports
#
# REM: QMS Protocol:
# REM:   Transaction_Create_Please → Transaction_Create_Thank_You
# REM:   Transaction_Update_Please → Transaction_Update_Thank_You
# REM:   Transaction_Checklist_Please → Transaction_Checklist_Thank_You
# REM:   Transaction_Close_Please (requires approval) → Transaction_Close_Thank_You
# REM:   Transaction_Cancel_Please (requires approval) → Transaction_Cancel_Thank_You
# REM: =======================================================================================

import logging
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from agents.base import SecureBaseAgent, AgentRequest
from core.audit import audit, AuditEventType
from core.qms import format_qms, QMSStatus

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: DOMAIN MODELS
# REM: =======================================================================================

class TransactionType(str, Enum):
    PURCHASE = "purchase"
    SALE = "sale"
    LEASE = "lease"
    REFINANCE = "refinance"
    COMMERCIAL = "commercial"


class TransactionStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PENDING_CLOSING = "pending_closing"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class PartyRole(str, Enum):
    BUYER = "buyer"
    SELLER = "seller"
    LISTING_AGENT = "listing_agent"
    BUYERS_AGENT = "buyers_agent"
    LENDER = "lender"
    TITLE_COMPANY = "title_company"
    ATTORNEY = "attorney"
    INSPECTOR = "inspector"
    APPRAISER = "appraiser"
    ESCROW_OFFICER = "escrow_officer"


class ChecklistItemStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAIVED = "waived"
    OVERDUE = "overdue"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# REM: =======================================================================================
# REM: STANDARD CLOSING CHECKLISTS
# REM: =======================================================================================

PURCHASE_CHECKLIST = [
    {"id": "CHK-001", "item": "Purchase agreement executed", "category": "contract", "days_from_start": 0},
    {"id": "CHK-002", "item": "Earnest money deposited", "category": "financial", "days_from_start": 3},
    {"id": "CHK-003", "item": "Home inspection scheduled", "category": "inspection", "days_from_start": 5},
    {"id": "CHK-004", "item": "Home inspection completed", "category": "inspection", "days_from_start": 10},
    {"id": "CHK-005", "item": "Inspection response submitted", "category": "inspection", "days_from_start": 12},
    {"id": "CHK-006", "item": "Appraisal ordered", "category": "financial", "days_from_start": 7},
    {"id": "CHK-007", "item": "Appraisal completed", "category": "financial", "days_from_start": 21},
    {"id": "CHK-008", "item": "Loan application submitted", "category": "financial", "days_from_start": 5},
    {"id": "CHK-009", "item": "Title search completed", "category": "title", "days_from_start": 14},
    {"id": "CHK-010", "item": "Title insurance commitment issued", "category": "title", "days_from_start": 21},
    {"id": "CHK-011", "item": "Survey completed", "category": "title", "days_from_start": 21},
    {"id": "CHK-012", "item": "HOA documents received", "category": "compliance", "days_from_start": 10},
    {"id": "CHK-013", "item": "Loan approval received", "category": "financial", "days_from_start": 28},
    {"id": "CHK-014", "item": "Closing disclosure issued", "category": "financial", "days_from_start": 32},
    {"id": "CHK-015", "item": "Final walkthrough completed", "category": "inspection", "days_from_start": 34},
    {"id": "CHK-016", "item": "Closing documents signed", "category": "closing", "days_from_start": 35},
    {"id": "CHK-017", "item": "Funds disbursed", "category": "closing", "days_from_start": 35},
    {"id": "CHK-018", "item": "Deed recorded", "category": "closing", "days_from_start": 36},
    {"id": "CHK-019", "item": "Keys delivered", "category": "closing", "days_from_start": 36},
]

LEASE_CHECKLIST = [
    {"id": "LCK-001", "item": "Lease application received", "category": "application", "days_from_start": 0},
    {"id": "LCK-002", "item": "Credit check completed", "category": "screening", "days_from_start": 2},
    {"id": "LCK-003", "item": "Background check completed", "category": "screening", "days_from_start": 3},
    {"id": "LCK-004", "item": "Income verification completed", "category": "screening", "days_from_start": 3},
    {"id": "LCK-005", "item": "References checked", "category": "screening", "days_from_start": 5},
    {"id": "LCK-006", "item": "Application approved", "category": "application", "days_from_start": 5},
    {"id": "LCK-007", "item": "Lease agreement drafted", "category": "contract", "days_from_start": 6},
    {"id": "LCK-008", "item": "Lease agreement signed", "category": "contract", "days_from_start": 8},
    {"id": "LCK-009", "item": "Security deposit received", "category": "financial", "days_from_start": 8},
    {"id": "LCK-010", "item": "Move-in inspection completed", "category": "inspection", "days_from_start": 10},
    {"id": "LCK-011", "item": "Keys delivered", "category": "closing", "days_from_start": 10},
]

CHECKLIST_TEMPLATES = {
    TransactionType.PURCHASE: PURCHASE_CHECKLIST,
    TransactionType.SALE: PURCHASE_CHECKLIST,  # Same checklist, different perspective
    TransactionType.LEASE: LEASE_CHECKLIST,
    TransactionType.REFINANCE: PURCHASE_CHECKLIST[:14],  # Subset — no walkthrough/keys
    TransactionType.COMMERCIAL: PURCHASE_CHECKLIST,  # Base, extend per deal
}


# REM: =======================================================================================
# REM: REQUIRED DOCUMENTS BY TRANSACTION TYPE
# REM: =======================================================================================

REQUIRED_DOCUMENTS = {
    TransactionType.PURCHASE: [
        {"id": "DOC-001", "name": "Purchase Agreement", "required": True},
        {"id": "DOC-002", "name": "Seller Disclosure Statement", "required": True},
        {"id": "DOC-003", "name": "Lead-Based Paint Disclosure", "required": True},
        {"id": "DOC-004", "name": "Home Inspection Report", "required": False},
        {"id": "DOC-005", "name": "Appraisal Report", "required": True},
        {"id": "DOC-006", "name": "Title Commitment", "required": True},
        {"id": "DOC-007", "name": "Survey", "required": False},
        {"id": "DOC-008", "name": "HOA Documents", "required": False},
        {"id": "DOC-009", "name": "Loan Estimate", "required": True},
        {"id": "DOC-010", "name": "Closing Disclosure", "required": True},
        {"id": "DOC-011", "name": "Proof of Insurance", "required": True},
        {"id": "DOC-012", "name": "Pre-Approval Letter", "required": True},
        {"id": "DOC-013", "name": "Earnest Money Receipt", "required": True},
        {"id": "DOC-014", "name": "Deed", "required": True},
    ],
    TransactionType.LEASE: [
        {"id": "DOC-L01", "name": "Lease Application", "required": True},
        {"id": "DOC-L02", "name": "Credit Report Authorization", "required": True},
        {"id": "DOC-L03", "name": "Proof of Income", "required": True},
        {"id": "DOC-L04", "name": "Photo ID", "required": True},
        {"id": "DOC-L05", "name": "Lease Agreement", "required": True},
        {"id": "DOC-L06", "name": "Move-In Condition Report", "required": True},
        {"id": "DOC-L07", "name": "Lead-Based Paint Disclosure", "required": True},
        {"id": "DOC-L08", "name": "Pet Addendum", "required": False},
    ],
}
REQUIRED_DOCUMENTS[TransactionType.SALE] = REQUIRED_DOCUMENTS[TransactionType.PURCHASE]
REQUIRED_DOCUMENTS[TransactionType.REFINANCE] = [
    d for d in REQUIRED_DOCUMENTS[TransactionType.PURCHASE]
    if d["id"] not in ("DOC-002", "DOC-004", "DOC-008", "DOC-014")
]
REQUIRED_DOCUMENTS[TransactionType.COMMERCIAL] = REQUIRED_DOCUMENTS[TransactionType.PURCHASE]


# REM: =======================================================================================
# REM: TRANSACTION COORDINATOR AGENT
# REM: =======================================================================================

class TransactionCoordinatorAgent(SecureBaseAgent):
    """
    REM: Real estate transaction coordinator agent.
    REM: Manages the full lifecycle of real estate closings with audit trails,
    REM: capability enforcement, and approval gates on critical actions.
    """

    AGENT_NAME = "transaction_agent"

    CAPABILITIES = [
        "filesystem.read:/data/transactions/*",
        "filesystem.write:/data/transactions/*",
        "filesystem.read:/data/documents/*",
        "external.none",  # No external network access — all data stays local
    ]

    # REM: Critical actions require human approval
    REQUIRES_APPROVAL_FOR = [
        "close_transaction",
        "cancel_transaction",
        "remove_party",
        "override_deadline",
    ]

    SUPPORTED_ACTIONS = [
        "create_transaction",
        "get_transaction",
        "list_transactions",
        "update_transaction",
        "close_transaction",
        "cancel_transaction",
        "add_party",
        "remove_party",
        "list_parties",
        "update_checklist",
        "get_checklist",
        "check_deadlines",
        "update_document_status",
        "get_documents",
        "override_deadline",
        "transaction_summary",
    ]

    # REM: Skip quarantine — built-in trusted agent
    SKIP_QUARANTINE = True

    def __init__(self):
        super().__init__()
        # REM: In-memory store — production would use Redis/PostgreSQL via persistence layer
        self._transactions: Dict[str, Dict[str, Any]] = {}
        self._seed_demo_transactions()

    def _seed_demo_transactions(self):
        """REM: Pre-populate with realistic demo transactions for dashboard display."""
        now = datetime.now(timezone.utc)

        # REM: Active purchase — mid-closing
        tx1_id = "TXN-2026-001"
        tx1_start = now - timedelta(days=18)
        self._transactions[tx1_id] = {
            "transaction_id": tx1_id,
            "type": TransactionType.PURCHASE.value,
            "status": TransactionStatus.ACTIVE.value,
            "property_address": "742 Evergreen Terrace, Springfield, OH 45501",
            "purchase_price": 285000,
            "created_at": tx1_start.isoformat(),
            "target_close_date": (tx1_start + timedelta(days=35)).isoformat(),
            "tenant_id": "tenant_remax_north",
            "matter_id": "matter_742_evergreen",
            "parties": [
                {"name": "Sarah & Michael Johnson", "role": PartyRole.BUYER.value, "email": "sjohnson@example.com", "phone": "555-0101"},
                {"name": "Robert Williams", "role": PartyRole.SELLER.value, "email": "rwilliams@example.com", "phone": "555-0102"},
                {"name": "Lisa Chen", "role": PartyRole.LISTING_AGENT.value, "email": "lchen@remax.example.com", "phone": "555-0103", "license": "OH-2024-18834"},
                {"name": "David Park", "role": PartyRole.BUYERS_AGENT.value, "email": "dpark@kw.example.com", "phone": "555-0104", "license": "OH-2023-16221"},
                {"name": "First Federal Savings", "role": PartyRole.LENDER.value, "email": "loans@firstfed.example.com", "phone": "555-0200"},
                {"name": "Buckeye Title Company", "role": PartyRole.TITLE_COMPANY.value, "email": "closings@buckeyetitle.example.com", "phone": "555-0300"},
            ],
            "checklist": self._build_checklist(TransactionType.PURCHASE, tx1_start),
            "documents": self._build_document_tracker(TransactionType.PURCHASE),
        }
        # REM: Mark first 8 checklist items complete, 9th in progress
        for i, item in enumerate(self._transactions[tx1_id]["checklist"]):
            if i < 8:
                item["status"] = ChecklistItemStatus.COMPLETED.value
                item["completed_at"] = (tx1_start + timedelta(days=item["days_from_start"])).isoformat()
            elif i == 8:
                item["status"] = ChecklistItemStatus.IN_PROGRESS.value
        # REM: Mark first 6 documents received/approved
        for i, doc in enumerate(self._transactions[tx1_id]["documents"]):
            if i < 4:
                doc["status"] = DocumentStatus.APPROVED.value
            elif i < 6:
                doc["status"] = DocumentStatus.RECEIVED.value

        # REM: Pending lease
        tx2_id = "TXN-2026-002"
        tx2_start = now - timedelta(days=3)
        self._transactions[tx2_id] = {
            "transaction_id": tx2_id,
            "type": TransactionType.LEASE.value,
            "status": TransactionStatus.ACTIVE.value,
            "property_address": "1200 Oak Street #4B, Bellevue, OH 44811",
            "monthly_rent": 1250,
            "created_at": tx2_start.isoformat(),
            "target_close_date": (tx2_start + timedelta(days=10)).isoformat(),
            "tenant_id": "tenant_remax_north",
            "matter_id": "matter_1200_oak_4b",
            "parties": [
                {"name": "Jennifer Martinez", "role": PartyRole.BUYER.value, "email": "jmartinez@example.com", "phone": "555-0401"},
                {"name": "Heartland Property Management", "role": PartyRole.SELLER.value, "email": "leasing@heartlandpm.example.com", "phone": "555-0500"},
                {"name": "Lisa Chen", "role": PartyRole.LISTING_AGENT.value, "email": "lchen@remax.example.com", "phone": "555-0103", "license": "OH-2024-18834"},
            ],
            "checklist": self._build_checklist(TransactionType.LEASE, tx2_start),
            "documents": self._build_document_tracker(TransactionType.LEASE),
        }
        # REM: First 3 checklist items done
        for i, item in enumerate(self._transactions[tx2_id]["checklist"]):
            if i < 3:
                item["status"] = ChecklistItemStatus.COMPLETED.value
                item["completed_at"] = (tx2_start + timedelta(days=item["days_from_start"])).isoformat()

        # REM: Recently closed transaction
        tx3_id = "TXN-2026-003"
        tx3_start = now - timedelta(days=42)
        self._transactions[tx3_id] = {
            "transaction_id": tx3_id,
            "type": TransactionType.PURCHASE.value,
            "status": TransactionStatus.CLOSED.value,
            "property_address": "5500 State Route 18, Norwalk, OH 44857",
            "purchase_price": 192000,
            "created_at": tx3_start.isoformat(),
            "closed_at": (tx3_start + timedelta(days=38)).isoformat(),
            "target_close_date": (tx3_start + timedelta(days=35)).isoformat(),
            "tenant_id": "tenant_remax_north",
            "matter_id": "matter_5500_sr18",
            "parties": [
                {"name": "Thomas & Amy Baker", "role": PartyRole.BUYER.value, "email": "tbaker@example.com", "phone": "555-0601"},
                {"name": "Estate of Harold Foster", "role": PartyRole.SELLER.value, "email": "foster.estate@lawfirm.example.com", "phone": "555-0700"},
            ],
            "checklist": self._build_checklist(TransactionType.PURCHASE, tx3_start),
            "documents": self._build_document_tracker(TransactionType.PURCHASE),
        }
        # REM: All items complete
        for item in self._transactions[tx3_id]["checklist"]:
            item["status"] = ChecklistItemStatus.COMPLETED.value
            item["completed_at"] = (tx3_start + timedelta(days=item["days_from_start"])).isoformat()
        for doc in self._transactions[tx3_id]["documents"]:
            doc["status"] = DocumentStatus.APPROVED.value

        logger.info(
            f"REM: Transaction agent seeded with ::{len(self._transactions)}:: demo transactions_Thank_You"
        )

    def _build_checklist(self, tx_type: TransactionType, start_date: datetime) -> List[Dict[str, Any]]:
        """REM: Build a checklist from template with calculated deadlines."""
        template = CHECKLIST_TEMPLATES.get(tx_type, PURCHASE_CHECKLIST)
        checklist = []
        for item in template:
            checklist.append({
                "id": item["id"],
                "item": item["item"],
                "category": item["category"],
                "status": ChecklistItemStatus.NOT_STARTED.value,
                "deadline": (start_date + timedelta(days=item["days_from_start"])).isoformat(),
                "days_from_start": item["days_from_start"],
                "completed_at": None,
                "notes": "",
            })
        return checklist

    def _build_document_tracker(self, tx_type: TransactionType) -> List[Dict[str, Any]]:
        """REM: Build document tracker from required documents template."""
        docs = REQUIRED_DOCUMENTS.get(tx_type, [])
        tracker = []
        for doc in docs:
            tracker.append({
                "id": doc["id"],
                "name": doc["name"],
                "required": doc["required"],
                "status": DocumentStatus.PENDING.value,
                "received_at": None,
                "reviewed_by": None,
                "notes": "",
            })
        return tracker

    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        """
        REM: Execute transaction coordination action.
        REM: Called by SecureBaseAgent.handle_request() after security checks pass.
        """
        action = request.action.lower()
        payload = request.payload

        handlers = {
            "create_transaction": self._create_transaction,
            "get_transaction": self._get_transaction,
            "list_transactions": self._list_transactions,
            "update_transaction": self._update_transaction,
            "close_transaction": self._close_transaction,
            "cancel_transaction": self._cancel_transaction,
            "add_party": self._add_party,
            "remove_party": self._remove_party,
            "list_parties": self._list_parties,
            "update_checklist": self._update_checklist,
            "get_checklist": self._get_checklist,
            "check_deadlines": self._check_deadlines,
            "update_document_status": self._update_document_status,
            "get_documents": self._get_documents,
            "override_deadline": self._override_deadline,
            "transaction_summary": self._transaction_summary,
        }

        handler = handlers.get(action)
        if not handler:
            raise ValueError(
                f"Unknown action: {action}. Supported: {list(handlers.keys())}"
            )

        result = handler(payload)

        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms(f"Transaction_{action.title()}", QMSStatus.THANK_YOU,
                       request_id=request.request_id),
            actor=self.AGENT_NAME,
            details={"action": action, "transaction_id": payload.get("transaction_id", "N/A")}
        )

        return result

    # REM: =======================================================================================
    # REM: TRANSACTION CRUD
    # REM: =======================================================================================

    def _create_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Create a new transaction with auto-generated checklist and document tracker."""
        tx_type_str = payload.get("type", "purchase")
        try:
            tx_type = TransactionType(tx_type_str)
        except ValueError:
            raise ValueError(f"Invalid transaction type: {tx_type_str}. Valid: {[t.value for t in TransactionType]}")

        tx_id = f"TXN-{datetime.now(timezone.utc).strftime('%Y')}-{str(uuid.uuid4())[:8].upper()}"
        now = datetime.now(timezone.utc)

        transaction = {
            "transaction_id": tx_id,
            "type": tx_type.value,
            "status": TransactionStatus.DRAFT.value,
            "property_address": payload.get("property_address", ""),
            "purchase_price": payload.get("purchase_price", 0),
            "monthly_rent": payload.get("monthly_rent", 0),
            "created_at": now.isoformat(),
            "target_close_date": payload.get("target_close_date", (now + timedelta(days=35)).isoformat()),
            "tenant_id": payload.get("tenant_id", "default"),
            "matter_id": payload.get("matter_id", f"matter_{tx_id.lower()}"),
            "parties": [],
            "checklist": self._build_checklist(tx_type, now),
            "documents": self._build_document_tracker(tx_type),
        }

        self._transactions[tx_id] = transaction

        return {
            "transaction_id": tx_id,
            "status": "created",
            "type": tx_type.value,
            "checklist_items": len(transaction["checklist"]),
            "required_documents": len(transaction["documents"]),
        }

    def _get_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Get full transaction details."""
        tx_id = payload.get("transaction_id")
        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")
        return self._transactions[tx_id]

    def _list_transactions(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: List transactions with optional filtering."""
        status_filter = payload.get("status")
        type_filter = payload.get("type")
        tenant_filter = payload.get("tenant_id")

        results = []
        for tx in self._transactions.values():
            if status_filter and tx["status"] != status_filter:
                continue
            if type_filter and tx["type"] != type_filter:
                continue
            if tenant_filter and tx.get("tenant_id") != tenant_filter:
                continue
            results.append({
                "transaction_id": tx["transaction_id"],
                "type": tx["type"],
                "status": tx["status"],
                "property_address": tx["property_address"],
                "created_at": tx["created_at"],
                "target_close_date": tx.get("target_close_date"),
            })

        return {"transactions": results, "count": len(results)}

    def _update_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Update transaction fields (status, price, dates, etc.)."""
        tx_id = payload.get("transaction_id")
        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        tx = self._transactions[tx_id]
        updatable = ["status", "property_address", "purchase_price", "monthly_rent",
                      "target_close_date", "notes"]

        updated_fields = []
        for field in updatable:
            if field in payload and field != "transaction_id":
                tx[field] = payload[field]
                updated_fields.append(field)

        tx["updated_at"] = datetime.now(timezone.utc).isoformat()

        return {"transaction_id": tx_id, "updated_fields": updated_fields}

    def _close_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Close a transaction. REQUIRES APPROVAL."""
        tx_id = payload.get("transaction_id")
        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        tx = self._transactions[tx_id]

        # REM: Validate — check for incomplete required items
        incomplete_required_docs = [
            d for d in tx["documents"]
            if d["required"] and d["status"] != DocumentStatus.APPROVED.value
        ]
        incomplete_checklist = [
            c for c in tx["checklist"]
            if c["status"] not in (ChecklistItemStatus.COMPLETED.value, ChecklistItemStatus.WAIVED.value)
        ]

        warnings = []
        if incomplete_required_docs:
            warnings.append(f"{len(incomplete_required_docs)} required documents not approved")
        if incomplete_checklist:
            warnings.append(f"{len(incomplete_checklist)} checklist items incomplete")

        tx["status"] = TransactionStatus.CLOSED.value
        tx["closed_at"] = datetime.now(timezone.utc).isoformat()

        return {
            "transaction_id": tx_id,
            "status": "closed",
            "closed_at": tx["closed_at"],
            "warnings": warnings,
        }

    def _cancel_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Cancel a transaction. REQUIRES APPROVAL."""
        tx_id = payload.get("transaction_id")
        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        tx = self._transactions[tx_id]
        reason = payload.get("reason", "No reason provided")

        tx["status"] = TransactionStatus.CANCELLED.value
        tx["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        tx["cancellation_reason"] = reason

        return {
            "transaction_id": tx_id,
            "status": "cancelled",
            "reason": reason,
        }

    # REM: =======================================================================================
    # REM: PARTY MANAGEMENT
    # REM: =======================================================================================

    def _add_party(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Add a party to a transaction."""
        tx_id = payload.get("transaction_id")
        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        party = {
            "name": payload.get("name", ""),
            "role": payload.get("role", ""),
            "email": payload.get("email", ""),
            "phone": payload.get("phone", ""),
            "license": payload.get("license", ""),
            "added_at": datetime.now(timezone.utc).isoformat(),
        }

        self._transactions[tx_id]["parties"].append(party)

        return {"transaction_id": tx_id, "party_added": party["name"], "role": party["role"]}

    def _remove_party(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Remove a party from a transaction. REQUIRES APPROVAL."""
        tx_id = payload.get("transaction_id")
        party_name = payload.get("name")
        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        parties = self._transactions[tx_id]["parties"]
        original_count = len(parties)
        self._transactions[tx_id]["parties"] = [p for p in parties if p["name"] != party_name]
        removed = original_count - len(self._transactions[tx_id]["parties"])

        return {"transaction_id": tx_id, "party_removed": party_name, "removed_count": removed}

    def _list_parties(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: List all parties on a transaction."""
        tx_id = payload.get("transaction_id")
        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        return {
            "transaction_id": tx_id,
            "parties": self._transactions[tx_id]["parties"],
            "count": len(self._transactions[tx_id]["parties"]),
        }

    # REM: =======================================================================================
    # REM: CHECKLIST MANAGEMENT
    # REM: =======================================================================================

    def _update_checklist(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Update a checklist item status."""
        tx_id = payload.get("transaction_id")
        item_id = payload.get("item_id")
        new_status = payload.get("status")

        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        try:
            status = ChecklistItemStatus(new_status)
        except ValueError:
            raise ValueError(f"Invalid status: {new_status}. Valid: {[s.value for s in ChecklistItemStatus]}")

        checklist = self._transactions[tx_id]["checklist"]
        for item in checklist:
            if item["id"] == item_id:
                item["status"] = status.value
                if status == ChecklistItemStatus.COMPLETED:
                    item["completed_at"] = datetime.now(timezone.utc).isoformat()
                if "notes" in payload:
                    item["notes"] = payload["notes"]
                return {"transaction_id": tx_id, "item_id": item_id, "new_status": status.value}

        raise ValueError(f"Checklist item not found: {item_id}")

    def _get_checklist(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Get checklist with completion stats."""
        tx_id = payload.get("transaction_id")
        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        checklist = self._transactions[tx_id]["checklist"]
        total = len(checklist)
        completed = sum(1 for c in checklist if c["status"] in (ChecklistItemStatus.COMPLETED.value, ChecklistItemStatus.WAIVED.value))
        in_progress = sum(1 for c in checklist if c["status"] == ChecklistItemStatus.IN_PROGRESS.value)
        overdue = sum(1 for c in checklist if c["status"] == ChecklistItemStatus.OVERDUE.value)

        return {
            "transaction_id": tx_id,
            "checklist": checklist,
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "overdue": overdue,
            "completion_pct": round((completed / total) * 100, 1) if total > 0 else 0,
        }

    # REM: =======================================================================================
    # REM: DEADLINE MONITORING
    # REM: =======================================================================================

    def _check_deadlines(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Check all transactions for overdue or upcoming deadline items."""
        now = datetime.now(timezone.utc)
        lookahead_days = payload.get("lookahead_days", 7)
        lookahead = now + timedelta(days=lookahead_days)

        overdue_items = []
        upcoming_items = []

        tx_filter = payload.get("transaction_id")
        transactions = {tx_filter: self._transactions[tx_filter]} if tx_filter and tx_filter in self._transactions else self._transactions

        for tx_id, tx in transactions.items():
            if tx["status"] in (TransactionStatus.CLOSED.value, TransactionStatus.CANCELLED.value):
                continue

            for item in tx["checklist"]:
                if item["status"] in (ChecklistItemStatus.COMPLETED.value, ChecklistItemStatus.WAIVED.value):
                    continue

                deadline = datetime.fromisoformat(item["deadline"])
                if deadline < now:
                    item["status"] = ChecklistItemStatus.OVERDUE.value
                    overdue_items.append({
                        "transaction_id": tx_id,
                        "property": tx["property_address"],
                        "item_id": item["id"],
                        "item": item["item"],
                        "deadline": item["deadline"],
                        "days_overdue": (now - deadline).days,
                    })
                elif deadline <= lookahead:
                    upcoming_items.append({
                        "transaction_id": tx_id,
                        "property": tx["property_address"],
                        "item_id": item["id"],
                        "item": item["item"],
                        "deadline": item["deadline"],
                        "days_until_due": (deadline - now).days,
                    })

        return {
            "checked_at": now.isoformat(),
            "lookahead_days": lookahead_days,
            "overdue": overdue_items,
            "overdue_count": len(overdue_items),
            "upcoming": upcoming_items,
            "upcoming_count": len(upcoming_items),
        }

    def _override_deadline(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Override a deadline. REQUIRES APPROVAL."""
        tx_id = payload.get("transaction_id")
        item_id = payload.get("item_id")
        new_deadline = payload.get("new_deadline")
        reason = payload.get("reason", "No reason provided")

        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        checklist = self._transactions[tx_id]["checklist"]
        for item in checklist:
            if item["id"] == item_id:
                old_deadline = item["deadline"]
                item["deadline"] = new_deadline
                item["override_reason"] = reason
                item["override_at"] = datetime.now(timezone.utc).isoformat()
                if item["status"] == ChecklistItemStatus.OVERDUE.value:
                    item["status"] = ChecklistItemStatus.IN_PROGRESS.value
                return {
                    "transaction_id": tx_id,
                    "item_id": item_id,
                    "old_deadline": old_deadline,
                    "new_deadline": new_deadline,
                    "reason": reason,
                }

        raise ValueError(f"Checklist item not found: {item_id}")

    # REM: =======================================================================================
    # REM: DOCUMENT TRACKING
    # REM: =======================================================================================

    def _update_document_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Update a document's status in the tracker."""
        tx_id = payload.get("transaction_id")
        doc_id = payload.get("document_id")
        new_status = payload.get("status")

        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        try:
            status = DocumentStatus(new_status)
        except ValueError:
            raise ValueError(f"Invalid status: {new_status}. Valid: {[s.value for s in DocumentStatus]}")

        documents = self._transactions[tx_id]["documents"]
        for doc in documents:
            if doc["id"] == doc_id:
                doc["status"] = status.value
                if status == DocumentStatus.RECEIVED:
                    doc["received_at"] = datetime.now(timezone.utc).isoformat()
                if "reviewed_by" in payload:
                    doc["reviewed_by"] = payload["reviewed_by"]
                if "notes" in payload:
                    doc["notes"] = payload["notes"]
                return {"transaction_id": tx_id, "document_id": doc_id, "new_status": status.value}

        raise ValueError(f"Document not found: {doc_id}")

    def _get_documents(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Get document tracker with completion stats."""
        tx_id = payload.get("transaction_id")
        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        documents = self._transactions[tx_id]["documents"]
        total = len(documents)
        required = sum(1 for d in documents if d["required"])
        approved = sum(1 for d in documents if d["status"] == DocumentStatus.APPROVED.value)
        pending = sum(1 for d in documents if d["status"] == DocumentStatus.PENDING.value)

        return {
            "transaction_id": tx_id,
            "documents": documents,
            "total": total,
            "required": required,
            "approved": approved,
            "pending": pending,
            "required_approved": sum(
                1 for d in documents
                if d["required"] and d["status"] == DocumentStatus.APPROVED.value
            ),
        }

    # REM: =======================================================================================
    # REM: REPORTING
    # REM: =======================================================================================

    def _transaction_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Generate a comprehensive summary of a transaction."""
        tx_id = payload.get("transaction_id")
        if not tx_id or tx_id not in self._transactions:
            raise ValueError(f"Transaction not found: {tx_id}")

        tx = self._transactions[tx_id]
        checklist = tx["checklist"]
        documents = tx["documents"]

        total_checklist = len(checklist)
        completed_checklist = sum(
            1 for c in checklist
            if c["status"] in (ChecklistItemStatus.COMPLETED.value, ChecklistItemStatus.WAIVED.value)
        )
        overdue_checklist = sum(1 for c in checklist if c["status"] == ChecklistItemStatus.OVERDUE.value)

        total_docs = len(documents)
        approved_docs = sum(1 for d in documents if d["status"] == DocumentStatus.APPROVED.value)
        required_docs = sum(1 for d in documents if d["required"])
        required_approved = sum(
            1 for d in documents
            if d["required"] and d["status"] == DocumentStatus.APPROVED.value
        )

        # REM: Calculate days to close
        now = datetime.now(timezone.utc)
        target = datetime.fromisoformat(tx.get("target_close_date", now.isoformat()))
        days_to_close = (target - now).days

        return {
            "transaction_id": tx_id,
            "type": tx["type"],
            "status": tx["status"],
            "property_address": tx["property_address"],
            "price": tx.get("purchase_price") or tx.get("monthly_rent", 0),
            "parties_count": len(tx["parties"]),
            "days_to_close": max(days_to_close, 0),
            "target_close_date": tx.get("target_close_date"),
            "checklist_progress": {
                "total": total_checklist,
                "completed": completed_checklist,
                "overdue": overdue_checklist,
                "completion_pct": round((completed_checklist / total_checklist) * 100, 1) if total_checklist > 0 else 0,
            },
            "document_progress": {
                "total": total_docs,
                "approved": approved_docs,
                "required": required_docs,
                "required_approved": required_approved,
                "completion_pct": round((required_approved / required_docs) * 100, 1) if required_docs > 0 else 0,
            },
        }


# REM: =======================================================================================
# REM: CELERY TASKS — Async wrappers for n8n / task dispatch
# REM: =======================================================================================

from celery import shared_task

_agent_instance = None


def _get_agent():
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = TransactionCoordinatorAgent()
    return _agent_instance


@shared_task(name="transaction_agent.execute")
def execute_action(action: str, payload: dict = None):
    """REM: Generic Celery task for transaction agent actions."""
    agent = _get_agent()
    request = AgentRequest(action=action, payload=payload or {}, requester="celery")
    response = agent.handle_request(request)
    return {"success": response.success, "result": response.result, "error": response.error}


@shared_task(name="transaction_agent.check_deadlines")
def check_deadlines(lookahead_days: int = 7):
    """REM: Scheduled task — check all transaction deadlines."""
    agent = _get_agent()
    request = AgentRequest(
        action="check_deadlines",
        payload={"lookahead_days": lookahead_days},
        requester="celery:beat"
    )
    response = agent.handle_request(request)
    return response.result


@shared_task(name="transaction_agent.health")
def health():
    """REM: Health check for the transaction agent."""
    agent = _get_agent()
    return agent.heartbeat()


# REM: =======================================================================================
# REM: EXPORTS
# REM: =======================================================================================

__all__ = ["TransactionCoordinatorAgent"]
