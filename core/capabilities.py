# TelsonBase/core/capabilities.py
# REM: =======================================================================================
# REM: CAPABILITY-BASED PERMISSION SYSTEM FOR AGENTS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Agents declare their capabilities. The orchestrator ENFORCES them.
# REM: An agent CANNOT exceed its declared permissions, even if compromised. This is
# REM: defense-in-depth: even if an attacker gains control of an agent, they can only
# REM: do what that agent was permitted to do.
# REM:
# REM: Capability Format: "resource.action:scope"
# REM:   - resource: filesystem, external, mqtt, ollama, redis
# REM:   - action: read, write, execute, none
# REM:   - scope: path pattern, domain, topic, etc.
# REM:
# REM: Examples:
# REM:   - "filesystem.read:/data/*" - Can read anything under /data/
# REM:   - "filesystem.write:/app/backups/*" - Can write to backups only
# REM:   - "external.read:api.anthropic.com" - Can GET from Anthropic API
# REM:   - "external.none" - Cannot make any external requests
# REM:   - "ollama.execute:*" - Can run any Ollama model
# REM: =======================================================================================

import re
import fnmatch
import asyncio
from enum import Enum
from typing import List, Set, Dict, Optional, Any
from pydantic import BaseModel, Field
import logging

from core.audit import audit, AuditEventType

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    """REM: Types of resources agents can access."""
    FILESYSTEM = "filesystem"
    EXTERNAL = "external"
    MQTT = "mqtt"
    OLLAMA = "ollama"
    REDIS = "redis"
    AGENT = "agent"  # Inter-agent communication


class ActionType(str, Enum):
    """REM: Types of actions agents can perform."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    PUBLISH = "publish"
    SUBSCRIBE = "subscribe"
    MANAGE = "manage"  # Model/resource management (pull, delete, configure)
    NONE = "none"  # Explicitly denied


class Capability(BaseModel):
    """
    REM: A single capability grant.
    """
    resource: ResourceType
    action: ActionType
    scope: str = Field(default="*", description="Scope pattern (glob or exact)")
    
    def matches(self, resource: ResourceType, action: ActionType, target: str) -> bool:
        """
        REM: Check if this capability grants access to the requested resource/action/target.
        """
        # REM: Check resource type
        if self.resource != resource:
            return False
        
        # REM: "none" action explicitly denies
        if self.action == ActionType.NONE:
            return False
        
        # REM: Check action matches
        if self.action != action:
            return False
        
        # REM: Check scope pattern
        if self.scope == "*":
            return True
        
        # REM: Glob pattern matching for paths
        if fnmatch.fnmatch(target, self.scope):
            return True
        
        # REM: Exact match
        return target == self.scope
    
    def __str__(self) -> str:
        return f"{self.resource.value}.{self.action.value}:{self.scope}"
    
    @classmethod
    def from_string(cls, cap_str: str) -> "Capability":
        """
        REM: Parse a capability string like "filesystem.read:/data/*"
        """
        # REM: Handle "resource.none" format (no scope)
        if cap_str.endswith(".none"):
            resource_str = cap_str.replace(".none", "")
            return cls(
                resource=ResourceType(resource_str),
                action=ActionType.NONE,
                scope="*"
            )
        
        # REM: Parse "resource.action:scope" format
        match = re.match(r"^(\w+)\.(\w+):(.+)$", cap_str)
        if not match:
            raise ValueError(f"Invalid capability format: {cap_str}")
        
        resource_str, action_str, scope = match.groups()
        return cls(
            resource=ResourceType(resource_str),
            action=ActionType(action_str),
            scope=scope
        )


class CapabilitySet(BaseModel):
    """
    REM: A set of capabilities for an agent.
    REM: Supports both allow and deny rules. Deny takes precedence.
    """
    allow: List[Capability] = Field(default_factory=list)
    deny: List[Capability] = Field(default_factory=list)
    
    def permits(self, resource: ResourceType, action: ActionType, target: str) -> bool:
        """
        REM: Check if this capability set permits the requested access.
        REM: Deny rules are checked first and take precedence.
        """
        # REM: Check deny rules first
        # REM: v5.3.0CC fix: use cap.matches() to check action too, not just resource+scope
        for cap in self.deny:
            if cap.resource == resource and cap.action == action and fnmatch.fnmatch(target, cap.scope):
                return False
        
        # REM: Check allow rules
        for cap in self.allow:
            if cap.matches(resource, action, target):
                return True
        
        # REM: Default deny
        return False
    
    @classmethod
    def from_strings(cls, capabilities: List[str]) -> "CapabilitySet":
        """
        REM: Parse a list of capability strings.
        REM: Strings starting with "!" are deny rules.
        """
        allow = []
        deny = []
        
        for cap_str in capabilities:
            if cap_str.startswith("!"):
                deny.append(Capability.from_string(cap_str[1:]))
            else:
                allow.append(Capability.from_string(cap_str))
        
        return cls(allow=allow, deny=deny)


class CapabilityEnforcer:
    """
    REM: Enforces capabilities at runtime.
    REM: Wraps resource access and checks permissions before allowing operations.
    """
    
    def __init__(self):
        self._agent_capabilities: Dict[str, CapabilitySet] = {}
    
    def register_agent(self, agent_id: str, capabilities: List[str]):
        """
        REM: Register an agent with its declared capabilities.
        """
        cap_set = CapabilitySet.from_strings(capabilities)
        self._agent_capabilities[agent_id] = cap_set
        
        logger.info(
            f"REM: Registered capabilities for agent ::{agent_id}:: - "
            f"Allow: {[str(c) for c in cap_set.allow]} "
            f"Deny: {[str(c) for c in cap_set.deny]}::_Thank_You"
        )
    
    def check_permission(
        self,
        agent_id: str,
        resource: ResourceType,
        action: ActionType,
        target: str
    ) -> bool:
        """
        REM: Check if an agent has permission for a specific operation.
        REM: Logs all access attempts for audit trail.
        """
        cap_set = self._agent_capabilities.get(agent_id)
        
        if cap_set is None:
            logger.error(f"REM: Unknown agent ::{agent_id}:: attempted access_Thank_You_But_No")
            audit.log(
                AuditEventType.AGENT_ERROR,
                f"Unknown agent ::{agent_id}:: attempted {resource.value}.{action.value}:{target}",
                actor=agent_id,
                resource=target,
                qms_status="Thank_You_But_No"
            )
            return False
        
        permitted = cap_set.permits(resource, action, target)
        
        if permitted:
            logger.debug(
                f"REM: PERMITTED - Agent ::{agent_id}:: "
                f"{resource.value}.{action.value}:{target}_Thank_You"
            )
        else:
            logger.warning(
                f"REM: DENIED - Agent ::{agent_id}:: attempted "
                f"{resource.value}.{action.value}:{target}_Thank_You_But_No"
            )
            audit.log(
                AuditEventType.AGENT_ERROR,
                f"Capability violation: agent ::{agent_id}:: denied {resource.value}.{action.value}:{target}",
                actor=agent_id,
                resource=target,
                details={"resource": resource.value, "action": action.value, "target": target},
                qms_status="Thank_You_But_No"
            )
        
        return permitted
    
    def get_agent_capabilities(self, agent_id: str) -> Optional[CapabilitySet]:
        """REM: Get an agent's registered capabilities."""
        return self._agent_capabilities.get(agent_id)
    
    def list_agents(self) -> List[str]:
        """REM: List all registered agents."""
        return list(self._agent_capabilities.keys())


# REM: =======================================================================================
# REM: CAPABILITY-ENFORCED RESOURCE WRAPPERS
# REM: =======================================================================================
# REM: These wrappers replace direct resource access. Agents use these instead of
# REM: accessing resources directly, ensuring all access goes through capability checks.

class EnforcedFilesystem:
    """
    REM: Capability-enforced filesystem access.
    """
    
    def __init__(self, enforcer: CapabilityEnforcer, agent_id: str):
        self.enforcer = enforcer
        self.agent_id = agent_id
    
    def read(self, path: str) -> Optional[bytes]:
        """REM: Read a file if permitted."""
        if not self.enforcer.check_permission(
            self.agent_id,
            ResourceType.FILESYSTEM,
            ActionType.READ,
            path
        ):
            raise PermissionError(f"Agent ::{self.agent_id}:: denied filesystem.read:{path}")
        
        with open(path, 'rb') as f:
            return f.read()
    
    def write(self, path: str, data: bytes):
        """REM: Write to a file if permitted."""
        if not self.enforcer.check_permission(
            self.agent_id,
            ResourceType.FILESYSTEM,
            ActionType.WRITE,
            path
        ):
            raise PermissionError(f"Agent ::{self.agent_id}:: denied filesystem.write:{path}")
        
        with open(path, 'wb') as f:
            f.write(data)
    
    def list_dir(self, path: str) -> List[str]:
        """REM: List directory contents if permitted."""
        if not self.enforcer.check_permission(
            self.agent_id,
            ResourceType.FILESYSTEM,
            ActionType.READ,
            path
        ):
            raise PermissionError(f"Agent ::{self.agent_id}:: denied filesystem.read:{path}")

        import os
        return os.listdir(path)

    # REM: =======================================================================================
    # REM: ASYNC METHODS (v5.3.0CC) — Non-blocking for use in async FastAPI endpoints
    # REM: Delegates blocking I/O to a thread pool via asyncio.to_thread().
    # REM: =======================================================================================

    async def aread(self, path: str) -> Optional[bytes]:
        """REM: v5.3.0CC — Async read. Runs blocking I/O in thread pool."""
        if not self.enforcer.check_permission(
            self.agent_id,
            ResourceType.FILESYSTEM,
            ActionType.READ,
            path
        ):
            raise PermissionError(f"Agent ::{self.agent_id}:: denied filesystem.read:{path}")

        return await asyncio.to_thread(self._read_file, path)

    async def awrite(self, path: str, data: bytes):
        """REM: v5.3.0CC — Async write. Runs blocking I/O in thread pool."""
        if not self.enforcer.check_permission(
            self.agent_id,
            ResourceType.FILESYSTEM,
            ActionType.WRITE,
            path
        ):
            raise PermissionError(f"Agent ::{self.agent_id}:: denied filesystem.write:{path}")

        await asyncio.to_thread(self._write_file, path, data)

    async def alist_dir(self, path: str) -> List[str]:
        """REM: v5.3.0CC — Async list_dir. Runs blocking I/O in thread pool."""
        if not self.enforcer.check_permission(
            self.agent_id,
            ResourceType.FILESYSTEM,
            ActionType.READ,
            path
        ):
            raise PermissionError(f"Agent ::{self.agent_id}:: denied filesystem.read:{path}")

        import os
        return await asyncio.to_thread(os.listdir, path)

    @staticmethod
    def _read_file(path: str) -> bytes:
        with open(path, 'rb') as f:
            return f.read()

    @staticmethod
    def _write_file(path: str, data: bytes):
        with open(path, 'wb') as f:
            f.write(data)


class EnforcedExternal:
    """
    REM: Capability-enforced external API access.
    REM: All requests go through the egress gateway, but this adds another layer.
    """
    
    def __init__(self, enforcer: CapabilityEnforcer, agent_id: str, gateway_url: str):
        self.enforcer = enforcer
        self.agent_id = agent_id
        self.gateway_url = gateway_url
    
    def _extract_domain(self, url: str) -> str:
        """REM: Extract domain from URL for capability checking."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower()
    
    def get(self, url: str, **kwargs) -> Any:
        """REM: Make a GET request if permitted."""
        domain = self._extract_domain(url)
        
        if not self.enforcer.check_permission(
            self.agent_id,
            ResourceType.EXTERNAL,
            ActionType.READ,
            domain
        ):
            raise PermissionError(f"Agent ::{self.agent_id}:: denied external.read:{domain}")
        
        import httpx
        with httpx.Client(base_url=self.gateway_url) as client:
            return client.get("/proxy", params={"target_url": url}, **kwargs)
    
    def post(self, url: str, **kwargs) -> Any:
        """REM: Make a POST request if permitted."""
        domain = self._extract_domain(url)
        
        if not self.enforcer.check_permission(
            self.agent_id,
            ResourceType.EXTERNAL,
            ActionType.WRITE,
            domain
        ):
            raise PermissionError(f"Agent ::{self.agent_id}:: denied external.write:{domain}")
        
        import httpx
        with httpx.Client(base_url=self.gateway_url) as client:
            return client.post("/proxy", params={"target_url": url}, **kwargs)


# REM: Global enforcer instance
capability_enforcer = CapabilityEnforcer()


# REM: =======================================================================================
# REM: PREDEFINED CAPABILITY PROFILES
# REM: =======================================================================================
# REM: Common capability sets for different agent types.

CAPABILITY_PROFILES = {
    "backup_agent": [
        "filesystem.read:/data/*",
        "filesystem.write:/app/backups/*",
        "filesystem.read:/app/backups/*",
        "external.none",  # Backup agent should NEVER touch external APIs
    ],
    "research_agent": [
        "external.read:api.anthropic.com",
        "external.read:api.perplexity.ai",
        "external.write:api.anthropic.com",  # For sending prompts
        "filesystem.write:/app/outputs/*",
        "filesystem.read:/app/inputs/*",
        "!filesystem.read:/data/*",  # Explicitly deny access to sensitive data
    ],
    "ollama_agent": [
        "ollama.execute:*",
        "filesystem.read:/app/prompts/*",
        "filesystem.write:/app/responses/*",
        "external.none",
    ],
    "orchestrator": [
        "agent.execute:*",  # Can dispatch to any agent
        "mqtt.publish:*",
        "mqtt.subscribe:*",
        "redis.read:*",
        "redis.write:*",
    ],
    "foreman_agent": [
        "filesystem.read:/app/toolroom/*",
        "filesystem.write:/app/toolroom/tools/*",
        "filesystem.read:/data/*",
        "external.read:github.com",              # GitHub ONLY — no other external access
        "external.read:api.github.com",           # GitHub API for release checks
        "external.read:raw.githubusercontent.com", # GitHub raw content
        "agent.execute:*",                        # Supervisor — can interact with all agents
        "redis.read:toolroom:*",
        "redis.write:toolroom:*",
    ],
}
