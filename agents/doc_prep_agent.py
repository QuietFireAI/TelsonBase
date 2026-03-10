# TelsonBase/agents/doc_prep_agent.py
# REM: =======================================================================================
# REM: DOCUMENT PREPARATION AGENT — REAL ESTATE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: Mission Statement: Real estate document preparation agent. Generates standard
# REM: real estate forms and documents from transaction data — purchase agreements,
# REM: disclosure forms, listing documents, closing checklists, and addenda. Uses
# REM: templates that get populated with matter-specific data.
#
# REM: Third Floor agent — specialized industry document generation.
#
# REM: Capabilities:
# REM:   - Generate purchase agreement from transaction data
# REM:   - Generate seller disclosure form
# REM:   - Generate agency disclosure
# REM:   - Generate closing checklist document
# REM:   - Generate comparative market analysis (CMA) shell
# REM:   - List available templates
# REM:   - Preview document before finalization
#
# REM: QMS Protocol:
# REM:   DocPrep_Generate_Please → DocPrep_Generate_Thank_You
# REM:   DocPrep_Preview_Please → DocPrep_Preview_Thank_You
# REM:   DocPrep_Finalize_Please (requires approval) → DocPrep_Finalize_Thank_You
# REM: =======================================================================================

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.base import AgentRequest, SecureBaseAgent
from core.audit import AuditEventType, audit
from core.qms import QMSStatus, format_qms
from version import __version__ as APP_VERSION

logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: DOCUMENT TEMPLATES
# REM: =======================================================================================

TEMPLATES = {
    "purchase_agreement": {
        "id": "TPL-PA-001",
        "name": "Residential Purchase Agreement",
        "description": "Standard Ohio residential purchase agreement",
        "category": "contract",
        "fields": [
            "buyer_name", "seller_name", "property_address", "legal_description",
            "purchase_price", "earnest_money", "financing_type", "loan_amount",
            "closing_date", "possession_date", "inspection_period_days",
            "listing_agent", "buyers_agent", "title_company",
        ],
        "sections": [
            "parties", "property_description", "purchase_price_and_terms",
            "earnest_money", "financing_contingency", "inspection_contingency",
            "appraisal_contingency", "title_and_survey", "closing_and_possession",
            "disclosures", "default_and_remedies", "additional_terms", "signatures",
        ],
    },
    "seller_disclosure": {
        "id": "TPL-SD-001",
        "name": "Ohio Residential Property Disclosure Form",
        "description": "Required under ORC 5302.30",
        "category": "disclosure",
        "fields": [
            "seller_name", "property_address", "year_built",
            "roof_age", "hvac_type", "hvac_age", "water_source",
            "sewer_type", "known_defects", "prior_flooding",
            "environmental_hazards", "hoa_name", "hoa_dues",
        ],
        "sections": [
            "property_information", "structural", "mechanical_systems",
            "water_and_sewer", "environmental", "legal_and_zoning",
            "hoa_and_community", "seller_certification",
        ],
    },
    "agency_disclosure": {
        "id": "TPL-AD-001",
        "name": "Agency Disclosure Statement",
        "description": "Required under ORC 4735.56 — discloses agent-client relationship",
        "category": "disclosure",
        "fields": [
            "client_name", "agent_name", "agent_license", "brokerage_name",
            "relationship_type", "property_address",
        ],
        "sections": [
            "agent_identification", "relationship_type", "duties_owed",
            "compensation_disclosure", "dual_agency_notice", "acknowledgment",
        ],
    },
    "closing_checklist": {
        "id": "TPL-CC-001",
        "name": "Closing Checklist",
        "description": "Comprehensive closing task tracker for all parties",
        "category": "checklist",
        "fields": [
            "property_address", "closing_date", "buyer_name", "seller_name",
            "listing_agent", "buyers_agent", "lender", "title_company",
        ],
        "sections": [
            "pre_closing_buyer", "pre_closing_seller", "pre_closing_lender",
            "pre_closing_title", "closing_day", "post_closing",
        ],
    },
    "listing_agreement": {
        "id": "TPL-LA-001",
        "name": "Exclusive Right to Sell Listing Agreement",
        "description": "Standard exclusive listing agreement",
        "category": "contract",
        "fields": [
            "seller_name", "property_address", "list_price", "listing_period_days",
            "commission_rate", "agent_name", "agent_license", "brokerage_name",
            "lockbox_authorized", "sign_authorized",
        ],
        "sections": [
            "parties", "property", "listing_price_and_terms", "commission",
            "marketing_authorization", "seller_obligations", "agent_obligations",
            "termination", "signatures",
        ],
    },
    "cma_report": {
        "id": "TPL-CMA-001",
        "name": "Comparative Market Analysis",
        "description": "CMA shell for property valuation",
        "category": "analysis",
        "fields": [
            "subject_address", "subject_beds", "subject_baths", "subject_sqft",
            "subject_year_built", "subject_lot_size",
            "comp_1_address", "comp_1_price", "comp_1_sqft", "comp_1_sold_date",
            "comp_2_address", "comp_2_price", "comp_2_sqft", "comp_2_sold_date",
            "comp_3_address", "comp_3_price", "comp_3_sqft", "comp_3_sold_date",
        ],
        "sections": [
            "subject_property", "comparable_sales", "adjustments",
            "price_recommendation", "market_conditions", "agent_notes",
        ],
    },
    "lead_paint_disclosure": {
        "id": "TPL-LP-001",
        "name": "Lead-Based Paint Disclosure",
        "description": "Required for pre-1978 properties per 42 USC 4852d",
        "category": "disclosure",
        "fields": [
            "property_address", "seller_name", "buyer_name",
            "known_lead_paint", "lead_paint_location", "lead_reports_available",
        ],
        "sections": [
            "seller_disclosure", "buyer_acknowledgment", "agent_acknowledgment",
            "epa_pamphlet_receipt", "signatures",
        ],
    },
}


# REM: =======================================================================================
# REM: DOCUMENT PREPARATION AGENT
# REM: =======================================================================================

class DocPrepAgent(SecureBaseAgent):
    """
    REM: Real estate document preparation agent.
    REM: Generates standard forms from templates and transaction data.
    REM: All generated documents are audit-logged with SHA-256 hashes.
    """

    AGENT_NAME = "doc_prep_agent"

    CAPABILITIES = [
        "filesystem.read:/data/documents/*",
        "filesystem.write:/data/documents/generated/*",
        "filesystem.read:/data/transactions/*",
        "filesystem.read:/data/templates/*",
        "external.none",
    ]

    REQUIRES_APPROVAL_FOR = [
        "finalize_document",
        "delete_document",
    ]

    SUPPORTED_ACTIONS = [
        "list_templates",
        "get_template",
        "generate_document",
        "preview_document",
        "finalize_document",
        "list_generated",
        "get_document",
        "delete_document",
        "validate_fields",
    ]

    SKIP_QUARANTINE = True

    def __init__(self):
        super().__init__()
        self._generated_documents: Dict[str, Dict[str, Any]] = {}
        self._seed_demo_documents()

    def _seed_demo_documents(self):
        """REM: Pre-populate with demo generated documents."""
        now = datetime.now(timezone.utc)

        # REM: A completed purchase agreement for the Evergreen Terrace transaction
        pa_content = self._render_template("purchase_agreement", {
            "buyer_name": "Sarah & Michael Johnson",
            "seller_name": "Robert Williams",
            "property_address": "742 Evergreen Terrace, Springfield, OH 45501",
            "legal_description": "Lot 42, Block 7, Springfield Heights Subdivision, Clark County, OH",
            "purchase_price": "$285,000.00",
            "earnest_money": "$5,000.00",
            "financing_type": "Conventional",
            "loan_amount": "$228,000.00",
            "closing_date": "March 15, 2026",
            "possession_date": "March 15, 2026 at 5:00 PM",
            "inspection_period_days": "10",
            "listing_agent": "Lisa Chen (OH-2024-18834)",
            "buyers_agent": "David Park (OH-2023-16221)",
            "title_company": "Buckeye Title Company",
        })

        pa_hash = hashlib.sha256(pa_content.encode()).hexdigest()
        self._generated_documents["GEN-PA-001"] = {
            "document_id": "GEN-PA-001",
            "template_id": "TPL-PA-001",
            "template_name": "Residential Purchase Agreement",
            "transaction_id": "TXN-2026-001",
            "status": "finalized",
            "content": pa_content,
            "sha256": pa_hash,
            "generated_at": (now - timedelta(days=18)).isoformat(),
            "finalized_at": (now - timedelta(days=17)).isoformat(),
            "generated_by": self.AGENT_NAME,
        }

        # REM: A draft seller disclosure
        sd_content = self._render_template("seller_disclosure", {
            "seller_name": "Robert Williams",
            "property_address": "742 Evergreen Terrace, Springfield, OH 45501",
            "year_built": "1998",
            "roof_age": "8 years (replaced 2018)",
            "hvac_type": "Forced air gas furnace / Central AC",
            "hvac_age": "12 years",
            "water_source": "Municipal",
            "sewer_type": "Municipal sewer",
            "known_defects": "Minor basement seepage during heavy rain (east wall). Treated with waterproof sealant 2022.",
            "prior_flooding": "No",
            "environmental_hazards": "None known",
            "hoa_name": "Springfield Heights HOA",
            "hoa_dues": "$75/month",
        })

        sd_hash = hashlib.sha256(sd_content.encode()).hexdigest()
        self._generated_documents["GEN-SD-001"] = {
            "document_id": "GEN-SD-001",
            "template_id": "TPL-SD-001",
            "template_name": "Ohio Residential Property Disclosure Form",
            "transaction_id": "TXN-2026-001",
            "status": "draft",
            "content": sd_content,
            "sha256": sd_hash,
            "generated_at": (now - timedelta(days=16)).isoformat(),
            "finalized_at": None,
            "generated_by": self.AGENT_NAME,
        }

        # REM: A lease-related agency disclosure
        ad_content = self._render_template("agency_disclosure", {
            "client_name": "Jennifer Martinez",
            "agent_name": "Lisa Chen",
            "agent_license": "OH-2024-18834",
            "brokerage_name": "RE/MAX North",
            "relationship_type": "Exclusive Buyer/Tenant Agent",
            "property_address": "1200 Oak Street #4B, Bellevue, OH 44811",
        })

        ad_hash = hashlib.sha256(ad_content.encode()).hexdigest()
        self._generated_documents["GEN-AD-001"] = {
            "document_id": "GEN-AD-001",
            "template_id": "TPL-AD-001",
            "template_name": "Agency Disclosure Statement",
            "transaction_id": "TXN-2026-002",
            "status": "finalized",
            "content": ad_content,
            "sha256": ad_hash,
            "generated_at": (now - timedelta(days=3)).isoformat(),
            "finalized_at": (now - timedelta(days=3)).isoformat(),
            "generated_by": self.AGENT_NAME,
        }

        logger.info(
            f"REM: Doc prep agent seeded with ::{len(self._generated_documents)}:: demo documents_Thank_You"
        )

    def _render_template(self, template_key: str, data: Dict[str, str]) -> str:
        """
        REM: Render a document template with provided data.
        REM: Returns structured text — production would return formatted PDF/DOCX.
        """
        template = TEMPLATES.get(template_key)
        if not template:
            raise ValueError(f"Template not found: {template_key}")

        lines = []
        lines.append("=" * 72)
        lines.append(f"  {template['name'].upper()}")
        lines.append(f"  Generated by TelsonBase — {datetime.now(timezone.utc).strftime('%B %d, %Y')}")
        lines.append("=" * 72)
        lines.append("")

        for section in template["sections"]:
            section_title = section.replace("_", " ").title()
            lines.append(f"--- {section_title} ---")
            lines.append("")

            # REM: Populate fields relevant to this section
            for field in template["fields"]:
                if field in data:
                    field_label = field.replace("_", " ").title()
                    lines.append(f"  {field_label}: {data[field]}")

            lines.append("")

        lines.append("=" * 72)
        lines.append(f"  Document Hash (SHA-256): [computed on finalization]")
        lines.append(f"  Template: {template['id']} — {template['name']}")
        lines.append(f"  Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"  Platform: TelsonBase {APP_VERSION}")
        lines.append("=" * 72)

        return "\n".join(lines)

    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        """REM: Execute document preparation action."""
        action = request.action.lower()
        payload = request.payload

        handlers = {
            "list_templates": self._list_templates,
            "get_template": self._get_template,
            "generate_document": self._generate_document,
            "preview_document": self._preview_document,
            "finalize_document": self._finalize_document,
            "list_generated": self._list_generated,
            "get_document": self._get_document,
            "delete_document": self._delete_document,
            "validate_fields": self._validate_fields,
        }

        handler = handlers.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}. Supported: {list(handlers.keys())}")

        result = handler(payload)

        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms(f"DocPrep_{action.title()}", QMSStatus.THANK_YOU,
                       request_id=request.request_id),
            actor=self.AGENT_NAME,
            details={"action": action}
        )

        return result

    # REM: =======================================================================================
    # REM: TEMPLATE MANAGEMENT
    # REM: =======================================================================================

    def _list_templates(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: List all available document templates."""
        category_filter = payload.get("category")

        templates = []
        for key, tmpl in TEMPLATES.items():
            if category_filter and tmpl["category"] != category_filter:
                continue
            templates.append({
                "key": key,
                "id": tmpl["id"],
                "name": tmpl["name"],
                "description": tmpl["description"],
                "category": tmpl["category"],
                "field_count": len(tmpl["fields"]),
                "section_count": len(tmpl["sections"]),
            })

        return {"templates": templates, "count": len(templates)}

    def _get_template(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Get full template details including required fields."""
        template_key = payload.get("template_key") or payload.get("template")
        if not template_key or template_key not in TEMPLATES:
            raise ValueError(f"Template not found: {template_key}. Available: {list(TEMPLATES.keys())}")

        tmpl = TEMPLATES[template_key]
        return {
            "key": template_key,
            "id": tmpl["id"],
            "name": tmpl["name"],
            "description": tmpl["description"],
            "category": tmpl["category"],
            "fields": tmpl["fields"],
            "sections": tmpl["sections"],
        }

    # REM: =======================================================================================
    # REM: DOCUMENT GENERATION
    # REM: =======================================================================================

    def _generate_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Generate a document from a template with provided data."""
        template_key = payload.get("template_key") or payload.get("template")
        data = payload.get("data", {})
        transaction_id = payload.get("transaction_id", "N/A")

        if not template_key or template_key not in TEMPLATES:
            raise ValueError(f"Template not found: {template_key}")

        content = self._render_template(template_key, data)
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        doc_id = f"GEN-{template_key[:2].upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        document = {
            "document_id": doc_id,
            "template_id": TEMPLATES[template_key]["id"],
            "template_name": TEMPLATES[template_key]["name"],
            "transaction_id": transaction_id,
            "status": "draft",
            "content": content,
            "sha256": content_hash,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "finalized_at": None,
            "generated_by": self.AGENT_NAME,
            "field_data": data,
        }

        self._generated_documents[doc_id] = document

        return {
            "document_id": doc_id,
            "template": template_key,
            "status": "draft",
            "sha256": content_hash,
            "content_length": len(content),
        }

    def _preview_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Preview a generated document without finalizing."""
        doc_id = payload.get("document_id")
        if not doc_id or doc_id not in self._generated_documents:
            raise ValueError(f"Document not found: {doc_id}")

        doc = self._generated_documents[doc_id]
        # REM: Return first 2000 chars for preview
        preview_length = payload.get("preview_length", 2000)

        return {
            "document_id": doc_id,
            "template_name": doc["template_name"],
            "status": doc["status"],
            "preview": doc["content"][:preview_length],
            "total_length": len(doc["content"]),
            "truncated": len(doc["content"]) > preview_length,
        }

    def _finalize_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Finalize a document — locks it and computes final hash. REQUIRES APPROVAL."""
        doc_id = payload.get("document_id")
        if not doc_id or doc_id not in self._generated_documents:
            raise ValueError(f"Document not found: {doc_id}")

        doc = self._generated_documents[doc_id]
        if doc["status"] == "finalized":
            raise ValueError(f"Document {doc_id} is already finalized")

        # REM: Compute final hash
        final_hash = hashlib.sha256(doc["content"].encode()).hexdigest()
        doc["sha256"] = final_hash
        doc["status"] = "finalized"
        doc["finalized_at"] = datetime.now(timezone.utc).isoformat()

        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms("DocPrep_Finalize", QMSStatus.THANK_YOU,
                       document=doc_id, hash=final_hash[:16]),
            actor=self.AGENT_NAME,
            details={
                "document_id": doc_id,
                "sha256": final_hash,
                "template": doc["template_name"],
                "transaction_id": doc["transaction_id"],
            }
        )

        return {
            "document_id": doc_id,
            "status": "finalized",
            "sha256": final_hash,
            "finalized_at": doc["finalized_at"],
        }

    # REM: =======================================================================================
    # REM: DOCUMENT RETRIEVAL
    # REM: =======================================================================================

    def _list_generated(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: List all generated documents with optional filters."""
        status_filter = payload.get("status")
        tx_filter = payload.get("transaction_id")

        results = []
        for doc in self._generated_documents.values():
            if status_filter and doc["status"] != status_filter:
                continue
            if tx_filter and doc["transaction_id"] != tx_filter:
                continue
            results.append({
                "document_id": doc["document_id"],
                "template_name": doc["template_name"],
                "transaction_id": doc["transaction_id"],
                "status": doc["status"],
                "sha256": doc["sha256"][:16] + "...",
                "generated_at": doc["generated_at"],
                "finalized_at": doc["finalized_at"],
            })

        return {"documents": results, "count": len(results)}

    def _get_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Get full document content."""
        doc_id = payload.get("document_id")
        if not doc_id or doc_id not in self._generated_documents:
            raise ValueError(f"Document not found: {doc_id}")

        doc = self._generated_documents[doc_id]
        return {
            "document_id": doc["document_id"],
            "template_name": doc["template_name"],
            "transaction_id": doc["transaction_id"],
            "status": doc["status"],
            "content": doc["content"],
            "sha256": doc["sha256"],
            "generated_at": doc["generated_at"],
            "finalized_at": doc["finalized_at"],
        }

    def _delete_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Delete a generated document. REQUIRES APPROVAL."""
        doc_id = payload.get("document_id")
        if not doc_id or doc_id not in self._generated_documents:
            raise ValueError(f"Document not found: {doc_id}")

        doc = self._generated_documents.pop(doc_id)
        return {
            "document_id": doc_id,
            "deleted": True,
            "was_finalized": doc["status"] == "finalized",
        }

    # REM: =======================================================================================
    # REM: VALIDATION
    # REM: =======================================================================================

    def _validate_fields(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Validate that all required template fields are provided."""
        template_key = payload.get("template_key") or payload.get("template")
        data = payload.get("data", {})

        if not template_key or template_key not in TEMPLATES:
            raise ValueError(f"Template not found: {template_key}")

        tmpl = TEMPLATES[template_key]
        provided = set(data.keys())
        required = set(tmpl["fields"])
        missing = required - provided
        extra = provided - required

        return {
            "template": template_key,
            "valid": len(missing) == 0,
            "required_fields": len(required),
            "provided_fields": len(provided),
            "missing_fields": sorted(list(missing)),
            "extra_fields": sorted(list(extra)),
        }


# REM: =======================================================================================
# REM: CELERY TASKS
# REM: =======================================================================================

from datetime import timedelta

from celery import shared_task

_agent_instance = None


def _get_agent():
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DocPrepAgent()
    return _agent_instance


@shared_task(name="doc_prep_agent.execute")
def execute_action(action: str, payload: dict = None):
    """REM: Generic Celery task for doc prep actions."""
    agent = _get_agent()
    request = AgentRequest(action=action, payload=payload or {}, requester="celery")
    response = agent.handle_request(request)
    return {"success": response.success, "result": response.result, "error": response.error}


@shared_task(name="doc_prep_agent.health")
def health():
    """REM: Health check."""
    agent = _get_agent()
    return agent.heartbeat()


# REM: =======================================================================================
# REM: EXPORTS
# REM: =======================================================================================

__all__ = ["DocPrepAgent"]
