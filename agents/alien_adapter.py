# TelsonBase/agents/alien_adapter.py
# REM: =======================================================================================
# REM: ALIEN ADAPTER — QUARANTINE ZONE FOR EXTERNAL AGENT FRAMEWORKS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: This module provides a bridge between external agent frameworks
# REM: (LangChain, CrewAI, AutoGen, etc.) and TelsonBase's secure execution environment.
# REM:
# REM: SECURITY MODEL:
# REM:   - External agents ("aliens") execute in a QUARANTINE context
# REM:   - Aliens have NO direct access to TelsonBase internals
# REM:   - All alien requests go through QMS validation
# REM:   - Aliens must be explicitly granted capabilities
# REM:   - All alien actions are logged and can be monitored
# REM:
# REM: CITIZENSHIP PATH:
# REM:   1. Alien registers with TelsonBase (quarantine status)
# REM:   2. Alien operates under restricted capabilities
# REM:   3. Human reviews alien behavior via dashboard
# REM:   4. Human grants citizenship (full TelsonBase access)
# REM:
# REM: QMS Protocol:
# REM:   Incoming: Alien_Request_Please with ::framework:: ::action::
# REM:   Success:  Alien_Request_Thank_You with ::result::
# REM:   Blocked:  Alien_Request_Thank_You_But_No with ::reason::
# REM: =======================================================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from core.audit import AuditEventType, audit
from core.capabilities import ActionType, ResourceType, capability_enforcer
from core.config import get_settings
from core.qms import QMSStatus, format_qms, validate_qms
from core.signing import MessageSigner, key_registry

settings = get_settings()
logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: ALIEN STATUS LEVELS
# REM: =======================================================================================

class AlienStatus(str, Enum):
    """
    REM: Trust levels for external agents.
    """
    QUARANTINE = "quarantine"       # New alien, heavily restricted
    PROBATION = "probation"         # Passed initial vetting, limited access
    RESIDENT = "resident"           # Trusted, expanded capabilities  
    CITIZEN = "citizen"             # Full TelsonBase access


# REM: Default capabilities by status
ALIEN_CAPABILITIES = {
    AlienStatus.QUARANTINE: [
        # Can only read from designated sandbox
        "filesystem.read:/sandbox/alien/*",
        # No external network access
        "external.none",
    ],
    AlienStatus.PROBATION: [
        "filesystem.read:/sandbox/alien/*",
        "filesystem.write:/sandbox/alien/*",
        # Limited external access
        "external.https://api.openai.com/*",
    ],
    AlienStatus.RESIDENT: [
        "filesystem.read:/data/*",
        "filesystem.write:/sandbox/*",
        "external.https://*/*",
    ],
    AlienStatus.CITIZEN: [
        # Full access - same as native agents
        "filesystem.*",
        "external.*",
    ],
}


# REM: =======================================================================================
# REM: ALIEN REGISTRATION
# REM: =======================================================================================

@dataclass
class AlienAgent:
    """
    REM: Registration record for an external agent.
    """
    alien_id: str
    framework: str  # "langchain", "crewai", "autogen", etc.
    name: str
    description: str
    status: AlienStatus = AlienStatus.QUARANTINE
    capabilities: List[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: Optional[datetime] = None
    request_count: int = 0
    blocked_count: int = 0
    vetted_by: Optional[str] = None
    vetted_at: Optional[datetime] = None
    notes: str = ""


# REM: In-memory registry - use Redis in production
_ALIEN_REGISTRY: Dict[str, AlienAgent] = {}


def register_alien(
    framework: str,
    name: str,
    description: str = "",
) -> AlienAgent:
    """
    REM: Register a new external agent in quarantine.
    REM: QMS: Alien_Register_Please with ::framework:: ::name::
    """
    alien_id = f"alien_{framework}_{uuid.uuid4().hex[:8]}"
    
    alien = AlienAgent(
        alien_id=alien_id,
        framework=framework,
        name=name,
        description=description,
        status=AlienStatus.QUARANTINE,
        capabilities=ALIEN_CAPABILITIES[AlienStatus.QUARANTINE].copy(),
    )
    
    _ALIEN_REGISTRY[alien_id] = alien
    
    # REM: Register with capability enforcer
    capability_enforcer.register_agent(alien_id, alien.capabilities)
    
    # REM: Generate signing key for the alien
    key_registry.register_agent(alien_id)
    
    audit.log(
        AuditEventType.AGENT_REGISTERED,
        format_qms("Alien_Register", QMSStatus.THANK_YOU,
                  alien_id=alien_id, framework=framework, status="quarantine"),
        actor="alien_adapter",
        details={"framework": framework, "name": name}
    )
    
    logger.info(f"Registered alien agent: {alien_id} ({framework}/{name}) in QUARANTINE")
    
    return alien


def get_alien(alien_id: str) -> Optional[AlienAgent]:
    """REM: Get alien registration by ID."""
    return _ALIEN_REGISTRY.get(alien_id)


def list_aliens(status: Optional[AlienStatus] = None) -> List[AlienAgent]:
    """REM: List registered aliens, optionally filtered by status."""
    aliens = list(_ALIEN_REGISTRY.values())
    if status:
        aliens = [a for a in aliens if a.status == status]
    return aliens


def promote_alien(
    alien_id: str,
    new_status: AlienStatus,
    vetted_by: str,
    notes: str = ""
) -> bool:
    """
    REM: Promote an alien to a higher trust level.
    REM: QMS: Alien_Promote_Please with ::alien_id:: ::new_status::
    """
    alien = get_alien(alien_id)
    if not alien:
        return False
    
    old_status = alien.status
    alien.status = new_status
    alien.capabilities = ALIEN_CAPABILITIES[new_status].copy()
    alien.vetted_by = vetted_by
    alien.vetted_at = datetime.now(timezone.utc)
    alien.notes = notes
    
    # REM: Update capabilities in enforcer
    capability_enforcer.register_agent(alien_id, alien.capabilities)
    
    audit.log(
        AuditEventType.SECURITY_ALERT,
        format_qms("Alien_Promote", QMSStatus.THANK_YOU,
                  alien_id=alien_id, old_status=old_status.value, new_status=new_status.value),
        actor=vetted_by,
        details={"notes": notes}
    )
    
    logger.info(f"Promoted alien {alien_id}: {old_status.value} → {new_status.value}")
    
    return True


def revoke_alien(alien_id: str, revoked_by: str, reason: str) -> bool:
    """
    REM: Revoke an alien's access (back to quarantine or removal).
    REM: QMS: Alien_Revoke_Please with ::alien_id:: ::reason::
    """
    alien = get_alien(alien_id)
    if not alien:
        return False
    
    old_status = alien.status
    alien.status = AlienStatus.QUARANTINE
    alien.capabilities = ALIEN_CAPABILITIES[AlienStatus.QUARANTINE].copy()
    alien.notes = f"REVOKED: {reason}"
    
    capability_enforcer.register_agent(alien_id, alien.capabilities)
    
    audit.log(
        AuditEventType.SECURITY_ALERT,
        format_qms("Alien_Revoke", QMSStatus.THANK_YOU,
                  alien_id=alien_id, old_status=old_status.value, reason=reason),
        actor=revoked_by,
        details={"reason": reason}
    )
    
    logger.warning(f"Revoked alien {alien_id}: {reason}")
    
    return True


# REM: =======================================================================================
# REM: ALIEN EXECUTION CONTEXT
# REM: =======================================================================================

class AlienExecutionContext:
    """
    REM: Secure execution context for alien agents.
    REM: All alien operations go through this context for enforcement.
    """
    
    def __init__(self, alien: AlienAgent):
        self.alien = alien
        self.alien_id = alien.alien_id
        self._signer = MessageSigner(alien.alien_id, key_registry.get_key(alien.alien_id))
    
    def _check_capability(self, resource_type: ResourceType, action: ActionType, resource: str) -> bool:
        """REM: Check if alien has capability for the requested operation."""
        return capability_enforcer.check_capability(
            self.alien_id, resource_type, action, resource
        )
    
    def _log_request(self, action: str, payload: Dict, success: bool, error: str = None):
        """REM: Log alien request for monitoring."""
        self.alien.request_count += 1
        self.alien.last_activity = datetime.now(timezone.utc)
        
        if not success:
            self.alien.blocked_count += 1
        
        status = QMSStatus.THANK_YOU if success else QMSStatus.THANK_YOU_BUT_NO
        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms(f"Alien_{action}", status, alien_id=self.alien_id),
            actor=self.alien_id,
            details={"payload": payload, "success": success, "error": error}
        )
    
    def invoke_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        REM: Invoke a tool through the quarantine layer.
        REM: QMS: Alien_Tool_Invoke_Please with ::tool_name::
        
        This is the main entry point for LangChain tools.
        """
        # REM: Validate the request has QMS characteristics
        # For aliens, we're lenient but we log non-compliance
        validate_qms(f"{tool_name}_Please", source=self.alien_id)
        
        # REM: Map common tool names to internal actions
        tool_actions = {
            "read_file": (ResourceType.FILESYSTEM, ActionType.READ),
            "write_file": (ResourceType.FILESYSTEM, ActionType.WRITE),
            "http_request": (ResourceType.EXTERNAL, ActionType.EXECUTE),
            "run_code": (ResourceType.CODE, ActionType.EXECUTE),
        }
        
        if tool_name not in tool_actions:
            self._log_request(tool_name, kwargs, False, "Unknown tool")
            return {"error": f"Tool '{tool_name}' not available in quarantine"}
        
        resource_type, action_type = tool_actions[tool_name]
        resource = kwargs.get("path") or kwargs.get("url") or "*"
        
        # REM: Check capability
        if not self._check_capability(resource_type, action_type, resource):
            self._log_request(tool_name, kwargs, False, "Capability denied")
            return {
                "error": f"Alien '{self.alien_id}' lacks capability for {tool_name} on {resource}",
                "status": self.alien.status.value,
                "hint": "Request promotion to gain additional capabilities"
            }
        
        # REM: Execute the tool
        try:
            result = self._execute_tool(tool_name, kwargs)
            self._log_request(tool_name, kwargs, True)
            return result
        except Exception as e:
            self._log_request(tool_name, kwargs, False, str(e))
            return {"error": str(e)}
    
    def _execute_tool(self, tool_name: str, kwargs: Dict) -> Dict[str, Any]:
        """REM: Actually execute a tool. Override in subclasses for framework-specific behavior."""
        
        if tool_name == "read_file":
            path = kwargs.get("path")
            try:
                with open(path, "r") as f:
                    return {"content": f.read(), "path": path}
            except Exception as e:
                return {"error": str(e)}
        
        elif tool_name == "write_file":
            path = kwargs.get("path")
            content = kwargs.get("content", "")
            try:
                with open(path, "w") as f:
                    f.write(content)
                return {"success": True, "path": path, "bytes_written": len(content)}
            except Exception as e:
                return {"error": str(e)}
        
        elif tool_name == "http_request":
            # REM: HTTP requests must go through egress gateway
            import httpx
            url = kwargs.get("url")
            method = kwargs.get("method", "GET").upper()
            
            try:
                with httpx.Client(base_url=settings.egress_gateway_url) as client:
                    response = client.request(
                        method=method,
                        url="/proxy",
                        params={"target_url": url},
                        timeout=30.0
                    )
                    return {
                        "status_code": response.status_code,
                        "body": response.text[:10000],  # Limit response size
                        "url": url
                    }
            except Exception as e:
                return {"error": str(e)}
        
        return {"error": f"Tool '{tool_name}' not implemented"}


# REM: =======================================================================================
# REM: LANGCHAIN ADAPTER
# REM: =======================================================================================

class LangChainAdapter:
    """
    REM: Adapter for LangChain agents to operate within TelsonBase.
    
    Usage:
        adapter = LangChainAdapter("my_langchain_agent", "Research assistant")
        
        # Create LangChain tools that go through TelsonBase
        tools = adapter.create_tools()
        
        # Use in LangChain agent
        agent = create_react_agent(llm, tools)
    """
    
    def __init__(self, name: str, description: str = ""):
        """
        REM: Create a new LangChain adapter.
        REM: Registers the agent in QUARANTINE status.
        """
        self.alien = register_alien(
            framework="langchain",
            name=name,
            description=description
        )
        self.context = AlienExecutionContext(self.alien)
        self.alien_id = self.alien.alien_id
    
    @property
    def status(self) -> AlienStatus:
        """REM: Get current alien status."""
        return self.alien.status
    
    def create_tools(self) -> List[Any]:
        """
        REM: Create LangChain-compatible tools that route through TelsonBase.
        
        Returns tools that can be passed to create_react_agent or similar.
        """
        try:
            from langchain.tools import Tool
        except ImportError:
            logger.error("LangChain not installed. Install with: pip install langchain")
            return []
        
        tools = []
        
        # REM: File read tool
        if self._has_file_read_capability():
            tools.append(Tool(
                name="read_file",
                description="Read contents of a file. Input should be file path.",
                func=lambda path: self.context.invoke_tool("read_file", path=path)
            ))
        
        # REM: File write tool
        if self._has_file_write_capability():
            tools.append(Tool(
                name="write_file",
                description="Write content to a file. Input should be JSON with 'path' and 'content' keys.",
                func=lambda input_str: self._parse_and_write(input_str)
            ))
        
        # REM: HTTP request tool
        if self._has_http_capability():
            tools.append(Tool(
                name="http_request",
                description="Make HTTP request. Input should be URL.",
                func=lambda url: self.context.invoke_tool("http_request", url=url, method="GET")
            ))
        
        return tools
    
    def _has_file_read_capability(self) -> bool:
        return any("filesystem.read" in c or "filesystem.*" in c for c in self.alien.capabilities)
    
    def _has_file_write_capability(self) -> bool:
        return any("filesystem.write" in c or "filesystem.*" in c for c in self.alien.capabilities)
    
    def _has_http_capability(self) -> bool:
        return any("external.http" in c or "external.*" in c for c in self.alien.capabilities)
    
    def _parse_and_write(self, input_str: str) -> Dict[str, Any]:
        """REM: Parse LangChain input and write file."""
        import json
        try:
            data = json.loads(input_str)
            return self.context.invoke_tool("write_file", **data)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON input. Expected {'path': '...', 'content': '...'}"}
    
    def invoke(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        REM: Direct invocation for custom actions.
        REM: QMS: Alien_Invoke_Please with ::action::
        """
        return self.context.invoke_tool(action, **kwargs)
    
    def get_stats(self) -> Dict[str, Any]:
        """REM: Get usage statistics for this alien."""
        return {
            "alien_id": self.alien_id,
            "status": self.alien.status.value,
            "request_count": self.alien.request_count,
            "blocked_count": self.alien.blocked_count,
            "last_activity": self.alien.last_activity.isoformat() if self.alien.last_activity else None,
            "capabilities": self.alien.capabilities,
        }


# REM: =======================================================================================
# REM: DECORATOR FOR QUARANTINED FUNCTIONS
# REM: =======================================================================================

def quarantine(alien_id: str):
    """
    REM: Decorator to run a function in alien quarantine context.
    
    Usage:
        @quarantine("alien_langchain_abc123")
        def my_tool_function(arg1, arg2):
            # This runs with alien's restricted capabilities
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            alien = get_alien(alien_id)
            if not alien:
                raise ValueError(f"Unknown alien: {alien_id}")
            
            context = AlienExecutionContext(alien)
            
            # REM: Inject context as first argument if function accepts it
            import inspect
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            
            if params and params[0] == "context":
                return func(context, *args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


# REM: =======================================================================================
# REM: EXPORTS
# REM: =======================================================================================

__all__ = [
    "AlienStatus",
    "AlienAgent",
    "register_alien",
    "get_alien",
    "list_aliens",
    "promote_alien",
    "revoke_alien",
    "AlienExecutionContext",
    "LangChainAdapter",
    "quarantine",
]
