# TelsonBase/core/__init__.py
# REM: Core module exports - all security infrastructure

from core.config import get_settings, Settings
from core.auth import authenticate_request, require_permission, AuthResult
from core.audit import audit, AuditEventType, AuditLogger
from core.signing import (
    SignedAgentMessage,
    AgentKeyRegistry,
    MessageSigner,
    key_registry
)
from core.capabilities import (
    Capability,
    CapabilitySet,
    CapabilityEnforcer,
    capability_enforcer,
    ResourceType,
    ActionType,
    EnforcedFilesystem,
    EnforcedExternal,
    CAPABILITY_PROFILES
)
from core.anomaly import (
    BehaviorMonitor,
    behavior_monitor,
    AnomalyType,
    AnomalySeverity,
    Anomaly
)
from core.approval import (
    ApprovalGate,
    approval_gate,
    ApprovalStatus,
    ApprovalPriority,
    ApprovalRequest,
    requires_approval
)
from core.persistence import (
    signing_store,
    capability_store,
    anomaly_store,
    approval_store,
    federation_store
)

# v3.0.2: Qualified Message Standard (QMS) - Internal message verification
from core.qms import (
    QMSStatus,
    QMSFieldType,
    QMSMessage,
    is_qms_formatted,
    validate_qms,
    parse_qms,
    format_qms,
    format_qms_response,
    qms_endpoint,
    log_qms_transaction
)
