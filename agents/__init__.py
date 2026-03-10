# TelsonBase/agents/__init__.py
# REM: =======================================================================================
# REM: AGENT REGISTRY AND DISCOVERY FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Central registry for all TelsonBase agents. Provides discovery
# REM: functions for Goose/MCP integration and API introspection.
# REM: =======================================================================================

import logging
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

# REM: Import base classes
from agents.base import AgentRequest, AgentResponse, SecureBaseAgent
from agents.compliance_check_agent import ComplianceCheckAgent
from agents.doc_prep_agent import DocPrepAgent
# REM: Import concrete class-based agents
# REM: Note: backup_agent and demo_agent are functional modules, not class-based.
# REM: They're registered via metadata only — no class import needed.
from agents.document_agent import DocumentAgent
from agents.ollama_agent import OllamaAgent
from agents.transaction_agent import TransactionCoordinatorAgent

# REM: =======================================================================================
# REM: AGENT REGISTRY
# REM: =======================================================================================

# REM: Registry maps agent names to their classes (class-based agents only)
_AGENT_REGISTRY: Dict[str, Type[SecureBaseAgent]] = {
    "document_agent": DocumentAgent,
    "ollama_agent": OllamaAgent,
    "transaction_agent": TransactionCoordinatorAgent,
    "compliance_check_agent": ComplianceCheckAgent,
    "doc_prep_agent": DocPrepAgent,
}

# REM: Agent metadata for discovery
_AGENT_METADATA: Dict[str, Dict[str, Any]] = {
    "backup_agent": {
        "name": "backup_agent",
        "description": "Performs automated backups of TelsonBase data volumes",
        "actions": ["full_backup", "incremental_backup", "restore", "list_backups"],
        "requires_approval": ["restore"],
        "capabilities": ["filesystem.write:/app/backups/*", "filesystem.read:/data/*"],
    },
    "demo_agent": {
        "name": "demo_agent",
        "description": "Demonstration agent for testing TelsonBase security features",
        "actions": ["echo", "compute", "external_call", "sensitive_action"],
        "requires_approval": ["sensitive_action"],
        "capabilities": ["external.https://api.example.com/*"],
    },
    "document_agent": {
        "name": "document_agent",
        "description": "Document processing agent for extraction, summarization, search, and redaction",
        "actions": ["extract_text", "summarize", "search", "redact", "get_metadata", "list_documents"],
        "requires_approval": ["redact", "delete"],
        "capabilities": ["filesystem.read:/data/documents/*", "filesystem.write:/data/documents/processed/*"],
    },
    "ollama_agent": {
        "name": "ollama_agent",
        "description": "Sovereign AI engine agent. All LLM interactions — generate, chat, model management — flow through here, monitored and audited.",
        "actions": ["generate", "chat", "list_models", "model_info", "pull_model", "delete_model", "health_check", "recommended", "set_default"],
        "requires_approval": ["pull_model", "delete_model"],
        "capabilities": ["ollama.execute:*", "ollama.manage:*"],
    },
    "transaction_agent": {
        "name": "transaction_agent",
        "description": "Real estate transaction coordinator. Manages closings, checklists, parties, documents, and deadlines.",
        "actions": [
            "create_transaction", "get_transaction", "list_transactions", "update_transaction",
            "close_transaction", "cancel_transaction", "add_party", "remove_party", "list_parties",
            "update_checklist", "get_checklist", "check_deadlines", "update_document_status",
            "get_documents", "override_deadline", "transaction_summary",
        ],
        "requires_approval": ["close_transaction", "cancel_transaction", "remove_party", "override_deadline"],
        "capabilities": ["filesystem.read:/data/transactions/*", "filesystem.write:/data/transactions/*", "filesystem.read:/data/documents/*"],
    },
    "compliance_check_agent": {
        "name": "compliance_check_agent",
        "description": "Real estate compliance monitor. Tracks licenses, fair housing, disclosures, and continuing education.",
        "actions": [
            "check_license", "list_licenses", "add_license", "update_license",
            "check_disclosures", "verify_fair_housing", "check_ce_status", "update_ce_credits",
            "compliance_report", "override_violation", "waive_disclosure", "check_all",
        ],
        "requires_approval": ["override_violation", "waive_disclosure", "suspend_license"],
        "capabilities": ["filesystem.read:/data/compliance/*", "filesystem.write:/data/compliance/*"],
    },
    "doc_prep_agent": {
        "name": "doc_prep_agent",
        "description": "Real estate document preparation. Generates purchase agreements, disclosures, and closing documents from templates.",
        "actions": [
            "list_templates", "get_template", "generate_document", "preview_document",
            "finalize_document", "list_generated", "get_document", "delete_document", "validate_fields",
        ],
        "requires_approval": ["finalize_document", "delete_document"],
        "capabilities": ["filesystem.read:/data/documents/*", "filesystem.write:/data/documents/generated/*"],
    },
    "foreman_agent": {
        "name": "foreman_agent",
        "description": "Supervisor-level Toolroom manager. Controls tool inventory, checkout, updates, and HITL gates for API access.",
        "actions": [
            "daily_update_check", "checkout_tool", "return_tool",
            "register_uploaded_tool", "request_new_tool", "toolroom_status",
        ],
        "requires_approval": [
            "install_tool_from_github", "update_tool_from_github",
            "enable_api_access_for_tool", "quarantine_tool", "delete_tool",
        ],
        "capabilities": [
            "filesystem.read:/app/toolroom/*", "filesystem.write:/app/toolroom/tools/*",
            "external.read:github.com", "external.read:api.github.com",
            "agent.execute:*", "redis.read:toolroom:*", "redis.write:toolroom:*",
        ],
        "level": "supervisor",
        "module": "toolroom.foreman",
    },
    "goose_operator": {
        "name": "goose_operator",
        "description": (
            "Goose AI operator (by Block) connected via MCP. Accesses all 13 TelsonBase MCP tools natively: "
            "governance, audit, tenancy, and HITL approval gates. Configured via goose.yaml at project root. "
            "Goose uses its own LLM for reasoning; TelsonBase uses local Ollama internally — no cloud dependencies "
            "required on either side. n8n REMOVED Feb 24, 2026 — Goose/MCP is the native operator integration."
        ),
        "actions": [
            "system_status", "get_health", "list_agents", "get_agent", "register_as_agent",
            "list_tenants", "create_tenant", "list_matters", "get_audit_chain_status",
            "verify_audit_chain", "get_recent_audit_entries", "list_pending_approvals", "approve_tool_request",
        ],
        "requires_approval": ["approve_tool_request"],
        "capabilities": ["mcp.tools:*"],
        "integration": "mcp",
        "config_file": "goose.yaml",
    },
}


def register_agent(name: str, agent_class: Type[SecureBaseAgent], metadata: Dict[str, Any] = None):
    """
    REM: Register a new agent with the registry.
    REM: QMS: Agent_Register_Please with ::name:: → Agent_Register_Thank_You
    """
    _AGENT_REGISTRY[name] = agent_class
    if metadata:
        _AGENT_METADATA[name] = metadata
    else:
        # REM: Auto-generate metadata from class attributes
        _AGENT_METADATA[name] = {
            "name": name,
            "description": agent_class.__doc__ or "No description",
            "actions": getattr(agent_class, "SUPPORTED_ACTIONS", []),
            "requires_approval": getattr(agent_class, "REQUIRES_APPROVAL_FOR", []),
            "capabilities": getattr(agent_class, "CAPABILITIES", []),
        }
    logger.info(f"Registered agent: {name}")


def get_agent_by_name(name: str) -> Optional[Type[SecureBaseAgent]]:
    """
    REM: Get an agent class by name.
    REM: Returns None if agent not found.
    """
    return _AGENT_REGISTRY.get(name)


def list_available_agents() -> List[str]:
    """REM: Get list of registered agent names."""
    return list(_AGENT_REGISTRY.keys())


def get_agent_info(name: str) -> Optional[Dict[str, Any]]:
    """REM: Get metadata for a specific agent."""
    return _AGENT_METADATA.get(name)


def get_all_agent_info() -> List[Dict[str, Any]]:
    """REM: Get metadata for all registered agents."""
    return list(_AGENT_METADATA.values())


# REM: =======================================================================================
# REM: EXPORTS
# REM: =======================================================================================

__all__ = [
    # Base classes
    "SecureBaseAgent",
    "AgentRequest", 
    "AgentResponse",
    # Concrete agents
    "DocumentAgent",
    "OllamaAgent",
    "TransactionCoordinatorAgent",
    "ComplianceCheckAgent",
    "DocPrepAgent",
    # Registry functions
    "register_agent",
    "get_agent_by_name",
    "list_available_agents",
    "get_agent_info",
    "get_all_agent_info",
]
