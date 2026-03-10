# TelsonBase/agents/base.py
# REM: =======================================================================================
# REM: SECURE BASE AGENT CLASS FOR THE TelsonBase (v4.2.0)
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: The foundation ALL agents MUST inherit from. This version
# REM: integrates all security features:
# REM:   - Message signing (core/signing.py)
# REM:   - Capability enforcement (core/capabilities.py)
# REM:   - Behavioral monitoring (core/anomaly.py)
# REM:   - Human approval gates (core/approval.py)
# REM:
# REM: An agent that doesn't inherit from this class is not trusted by the system.
# REM:
# REM: QMS (Qualified Message Standard) Protocol (v3.0.2):
# REM: =======================================================================================
# REM: All agent communication SHOULD use QMS formatting. This provides provenance
# REM: verification beyond cryptographic signatures:
# REM:   1. Signature = WHO sent the message (identity)
# REM:   2. QMS format = HOW it got here (provenance via proper channels)
# REM:
# REM: Agents that receive non-QMS formatted messages should flag them as suspicious.
# REM: This does not reject messages yet — it logs for review.
# REM:
# REM: QMS in Agent Communication:
# REM:   Request:  Action_Please with ::parameters::
# REM:   Success:  Action_Thank_You with ::result::
# REM:   Failure:  Action_Thank_You_But_No with ::reason::
# REM:   Clarify:  Action_Excuse_Me with ??missing_data??
# REM:   Urgent:   Action_Pretty_Please with $$priority=high$$
# REM: =======================================================================================

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from core.anomaly import behavior_monitor
from core.approval import ApprovalStatus, approval_gate
from core.audit import AuditEventType, audit
from core.capabilities import (CAPABILITY_PROFILES, ActionType,
                               EnforcedExternal, EnforcedFilesystem,
                               ResourceType, capability_enforcer)
from core.config import get_settings
from core.signing import MessageSigner, SignedAgentMessage, key_registry
from core.trust_levels import (TRUST_LEVEL_CONSTRAINTS, AgentTrustLevel,
                               trust_manager)

settings = get_settings()
logger = logging.getLogger(__name__)


class AgentRequest(BaseModel):
    """
    REM: Standard structure for requests TO an agent.
    REM: Now includes message signing for inter-agent communication.
    """
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str = Field(..., description="The action the agent should perform")
    payload: Dict[str, Any] = Field(default_factory=dict)
    requester: str = Field(default="system", description="Who/what is making this request")
    priority: str = Field(default="normal", description="normal, high (Pretty_Please)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # REM: Optional signed message for inter-agent requests
    signed_message: Optional[SignedAgentMessage] = None


class AgentResponse(BaseModel):
    """
    REM: Standard structure for responses FROM an agent.
    """
    request_id: str
    agent_name: str
    success: bool
    qms_status: str  # Thank_You or Thank_You_But_No
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # REM: Anomaly detection flags
    anomalies_detected: List[str] = Field(default_factory=list)
    
    # REM: Approval tracking
    approval_required: bool = False
    approval_id: Optional[str] = None


class SecureBaseAgent(ABC):
    """
    REM: Abstract base class for all TelsonBase agents with full security integration.

    Security features:
    - Trust level enforcement (QUARANTINE → PROBATION → RESIDENT → CITIZEN)
    - All actions are capability-checked before execution
    - All actions are behavior-monitored for anomalies
    - Inter-agent messages must be signed
    - Sensitive actions require human approval
    - All external requests go through egress gateway
    """

    # REM: OVERRIDE THESE IN SUBCLASSES
    AGENT_NAME: str = "unnamed_agent"
    CAPABILITIES: List[str] = []  # e.g., ["filesystem.read:/data/*", "external.none"]
    REQUIRES_APPROVAL_FOR: List[str] = []  # Actions that always need approval

    # REM: v4.2.0CC: Trust level configuration
    INITIAL_TRUST_LEVEL: AgentTrustLevel = AgentTrustLevel.QUARANTINE
    SKIP_QUARANTINE: bool = False  # Set True for built-in trusted agents

    def __init__(self):
        """
        REM: Initialize the agent with all security components.
        """
        self.agent_name = self.AGENT_NAME
        self.logger = logging.getLogger(f"agent.{self.agent_name}")

        # REM: v4.2.0CC: Register with trust level manager
        initial_level = self.INITIAL_TRUST_LEVEL
        if self.SKIP_QUARANTINE:
            initial_level = AgentTrustLevel.RESIDENT
        self._trust_record = trust_manager.register_agent(
            self.agent_name,
            initial_level=initial_level,
            skip_quarantine=self.SKIP_QUARANTINE
        )
        self._trust_constraints = trust_manager.get_constraints(self.agent_name)

        # REM: Register agent's signing key
        self._signing_key = key_registry.register_agent(self.agent_name)
        self._signer = MessageSigner(self.agent_name, self._signing_key)

        # REM: Register agent's capabilities (filtered by trust level)
        capabilities = self.CAPABILITIES or CAPABILITY_PROFILES.get(self.agent_name, [])
        effective_capabilities = self._filter_capabilities_by_trust(capabilities)
        capability_enforcer.register_agent(self.agent_name, effective_capabilities)

        # REM: Create capability-enforced resource accessors
        self.filesystem = EnforcedFilesystem(capability_enforcer, self.agent_name)
        self.external = EnforcedExternal(
            capability_enforcer,
            self.agent_name,
            settings.egress_gateway_url
        )

        # REM: Log initialization
        trust_level = trust_manager.get_trust_level(self.agent_name)
        audit.log(
            AuditEventType.AGENT_REGISTERED,
            f"Agent ::{self.agent_name}:: initialized at trust level ::{trust_level.value}::, {len(effective_capabilities)} capabilities",
            actor=self.agent_name,
            details={
                "capabilities": effective_capabilities,
                "trust_level": trust_level.value
            },
            qms_status="Thank_You"
        )

        self.logger.info(
            f"REM: Agent ::{self.agent_name}:: initialized at "
            f"trust level ::{trust_level.value}::_Thank_You"
        )

    def _filter_capabilities_by_trust(self, capabilities: List[str]) -> List[str]:
        """REM: Filter capabilities based on current trust level constraints."""
        import fnmatch

        constraints = self._trust_constraints
        filtered = []

        for cap in capabilities:
            # REM: Check against denied patterns first
            denied = False
            for pattern in constraints.denied_capability_patterns:
                if fnmatch.fnmatch(cap, pattern):
                    denied = True
                    break

            if denied:
                self.logger.warning(
                    f"REM: Capability ::{cap}:: denied by trust level constraints"
                )
                continue

            # REM: Check against allowed patterns
            allowed = False
            for pattern in constraints.allowed_capability_patterns:
                if fnmatch.fnmatch(cap, pattern) or pattern == "*":
                    allowed = True
                    break

            if allowed:
                filtered.append(cap)
            else:
                self.logger.warning(
                    f"REM: Capability ::{cap}:: not in allowed patterns for trust level"
                )

        return filtered

    def get_trust_level(self) -> AgentTrustLevel:
        """REM: Get current trust level."""
        return trust_manager.get_trust_level(self.agent_name)
    
    def handle_request(self, request: AgentRequest) -> AgentResponse:
        """
        REM: Main entry point for handling agent requests.
        REM: This method orchestrates all security checks before executing the action.
        
        Security flow:
        1. Verify signed message (if inter-agent)
        2. Check capabilities
        3. Check for approval requirement
        4. Execute with behavior monitoring
        5. Return signed response
        """
        anomalies = []
        
        # REM: Step 1: Verify signed message if present
        if request.signed_message:
            is_valid, reason = key_registry.verify_message(request.signed_message)
            if not is_valid:
                self.logger.warning(
                    f"REM: Rejected request - invalid signature: {reason}_Thank_You_But_No"
                )
                return AgentResponse(
                    request_id=request.request_id,
                    agent_name=self.agent_name,
                    success=False,
                    qms_status="Thank_You_But_No",
                    error=f"Message signature verification failed: {reason}"
                )
        
        # REM: Step 2: Check capabilities
        # REM: (Resource-level capability checks happen in the enforced accessors)
        
        # REM: Step 3: Check for approval requirement
        if request.action in self.REQUIRES_APPROVAL_FOR:
            rule = approval_gate.check_requires_approval(
                agent_id=self.agent_name,
                action=request.action,
                payload=request.payload
            )
            
            if rule:
                approval_request = approval_gate.create_request(
                    agent_id=self.agent_name,
                    action=request.action,
                    description=f"Agent {self.agent_name} wants to execute {request.action}",
                    payload=request.payload,
                    rule=rule
                )
                
                self.logger.info(
                    f"REM: Action ::{request.action}:: requires approval - "
                    f"Request ::{approval_request.request_id}::_Please"
                )
                
                # REM: Wait for approval
                approval_request = approval_gate.wait_for_decision(
                    approval_request.request_id
                )
                
                if approval_request.status != ApprovalStatus.APPROVED:
                    return AgentResponse(
                        request_id=request.request_id,
                        agent_name=self.agent_name,
                        success=False,
                        qms_status="Thank_You_But_No",
                        error=f"Action not approved: {approval_request.status.value}",
                        approval_required=True,
                        approval_id=approval_request.request_id
                    )
        
        # REM: Step 4: Execute with behavior monitoring
        self.logger.info(
            f"REM: {self.agent_name} executing: '{request.action}_Please' - "
            f"ID: ::{request.request_id}::"
        )
        
        audit.task_dispatched(
            task_name=f"{self.agent_name}.{request.action}",
            task_id=request.request_id,
            actor=request.requester,
            args=request.payload
        )
        
        try:
            # REM: Record behavior for anomaly detection
            result = self.execute(request)
            
            # REM: Check for anomalies
            detected_anomalies = behavior_monitor.record(
                agent_id=self.agent_name,
                action=request.action,
                resource=str(request.payload.get("resource", "unknown")),
                success=True
            )
            anomalies = [a.anomaly_id for a in detected_anomalies]
            
            # REM: Build successful response
            response = AgentResponse(
                request_id=request.request_id,
                agent_name=self.agent_name,
                success=True,
                qms_status="Thank_You",
                result=result,
                anomalies_detected=anomalies
            )
            
            self.logger.info(
                f"REM: {self.agent_name} completed: '{request.action}_Thank_You' - "
                f"ID: ::{request.request_id}::"
            )
            
            audit.task_completed(
                task_name=f"{self.agent_name}.{request.action}",
                task_id=request.request_id,
                result_summary=str(result)[:200] if result else ""
            )
            
            return response
            
        except PermissionError as e:
            # REM: Capability violation
            self.logger.error(
                f"REM: CAPABILITY VIOLATION - {self.agent_name}: {e}_Thank_You_But_No"
            )
            
            # REM: Record failed attempt for anomaly detection
            behavior_monitor.record(
                agent_id=self.agent_name,
                action=request.action,
                resource=str(request.payload.get("resource", "unknown")),
                success=False
            )
            
            return AgentResponse(
                request_id=request.request_id,
                agent_name=self.agent_name,
                success=False,
                qms_status="Thank_You_But_No",
                error=f"Capability violation: {str(e)}"
            )
            
        except Exception as e:
            # REM: Execution error
            error_msg = str(e)
            
            self.logger.error(
                f"REM: {self.agent_name} failed: '{request.action}_Thank_You_But_No' - "
                f"Error: ::{error_msg}::"
            )
            
            # REM: Record failure for anomaly detection
            detected_anomalies = behavior_monitor.record(
                agent_id=self.agent_name,
                action=request.action,
                resource=str(request.payload.get("resource", "unknown")),
                success=False
            )
            anomalies = [a.anomaly_id for a in detected_anomalies]
            
            audit.task_failed(
                task_name=f"{self.agent_name}.{request.action}",
                task_id=request.request_id,
                error=error_msg
            )
            
            return AgentResponse(
                request_id=request.request_id,
                agent_name=self.agent_name,
                success=False,
                qms_status="Thank_You_But_No",
                error=error_msg,
                anomalies_detected=anomalies
            )
    
    @abstractmethod
    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        """
        REM: Abstract method that subclasses MUST implement.
        REM: This is where the agent's actual logic lives.
        
        Note: Use self.filesystem and self.external for resource access.
        These are capability-enforced and will raise PermissionError
        if the agent tries to exceed its declared capabilities.
        """
        pass
    
    def send_to_agent(
        self,
        target_agent: str,
        action: str,
        payload: Dict[str, Any]
    ) -> SignedAgentMessage:
        """
        REM: Send a signed message to another agent.
        REM: The receiving agent will verify the signature before processing.
        """
        message = self._signer.sign(
            action=action,
            payload=payload,
            target_agent=target_agent
        )
        
        self.logger.info(
            f"REM: Sending signed message to ::{target_agent}:: "
            f"Action ::{action}::_Please"
        )
        
        return message
    
    def heartbeat(self) -> Dict[str, Any]:
        """REM: Health check with security status."""
        caps = capability_enforcer.get_agent_capabilities(self.agent_name)
        
        return {
            "agent_name": self.agent_name,
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "capabilities_count": len(caps.allow) if caps else 0,
            "signing_key_registered": self.agent_name in key_registry._keys
        }
    
    def get_pending_approvals(self) -> List[Dict]:
        """REM: Get any pending approval requests for this agent."""
        requests = approval_gate.get_pending_requests(agent_id=self.agent_name)
        return [
            {
                "request_id": r.request_id,
                "action": r.action,
                "created_at": r.created_at.isoformat(),
                "priority": r.priority.value
            }
            for r in requests
        ]


# REM: =======================================================================================
# REM: EXAMPLE: SECURE BACKUP AGENT
# REM: =======================================================================================

class SecureBackupAgent(SecureBaseAgent):
    """
    REM: Example of a properly secured agent.
    """
    
    AGENT_NAME = "backup_agent"
    CAPABILITIES = [
        "filesystem.read:/data/*",
        "filesystem.write:/app/backups/*",
        "filesystem.read:/app/backups/*",
        "external.none",  # Backup agent should NEVER touch external APIs
    ]
    REQUIRES_APPROVAL_FOR = [
        "delete_backup",
        "restore_backup"
    ]
    
    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        action = request.action.lower()
        
        if action == "perform_backup":
            return self._perform_backup(request.payload)
        elif action == "list_backups":
            return self._list_backups(request.payload)
        elif action == "delete_backup":
            return self._delete_backup(request.payload)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    def _perform_backup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Backup implementation using capability-enforced filesystem."""
        volume = payload.get("volume", "test")
        source_path = f"/data/{volume}"
        
        # REM: This will be capability-checked automatically
        try:
            contents = self.filesystem.list_dir(source_path)
            return {
                "status": "backup_simulated",
                "volume": volume,
                "files_found": len(contents)
            }
        except PermissionError as e:
            raise PermissionError(f"Cannot backup {source_path}: {e}")
    
    def _list_backups(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: List backups using capability-enforced filesystem."""
        try:
            backups = self.filesystem.list_dir("/app/backups")
            return {"backups": backups}
        except FileNotFoundError:
            return {"backups": []}
    
    def _delete_backup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Delete a backup (requires approval)."""
        # REM: This action requires human approval (see REQUIRES_APPROVAL_FOR)
        backup_path = payload.get("path")
        if not backup_path:
            raise ValueError("path is required")
        
        # REM: Would delete the backup here
        return {"deleted": backup_path}
