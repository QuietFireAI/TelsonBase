# TelsonBase Developer Guide

# REM: =======================================================================================
# REM: DEVELOPER GUIDE: BUILDING SECURE AGENTS FOR TELSONBASE v7.3.0CC
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: AI Model Collaborators: ChatGPT 3.5/4.0, Gemini 3, Claude Sonnet 4.5, Claude Opus 4.5
# REM: Date: February 23, 2026
# REM: Updated: 2026-02-04
# REM: =======================================================================================

# Developer Guide: Building Secure Agents

This guide explains how to build AI agents that run within the TelsonBase zero-trust architecture.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Agent Architecture](#agent-architecture)
3. [Declaring Capabilities](#declaring-capabilities)
4. [Using Enforced Resources](#using-enforced-resources)
5. [Inter-Agent Communication](#inter-agent-communication)
6. [Requiring Human Approval](#requiring-human-approval)
7. [Testing Your Agent](#testing-your-agent)
8. [Common Patterns](#common-patterns)

---

## Quick Start

Here's the minimal code for a secure agent:

```python
from agents.base import SecureBaseAgent, AgentRequest
from typing import Dict, Any, Optional

class MyAgent(SecureBaseAgent):
    """
    REM: A simple example agent.
    """
    
    # REM: Required: Give your agent a unique name
    AGENT_NAME = "my_agent"
    
    # REM: Required: Declare what your agent can do
    CAPABILITIES = [
        "filesystem.read:/app/inputs/*",
        "filesystem.write:/app/outputs/*",
        "external.none",  # This agent cannot make external API calls
    ]
    
    # REM: Optional: Actions that require human approval
    REQUIRES_APPROVAL_FOR = [
        "delete_file",
        "send_notification"
    ]
    
    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        """
        REM: Your agent's logic goes here.
        """
        action = request.action.lower()
        
        if action == "process_file":
            return self._process_file(request.payload)
        elif action == "delete_file":
            return self._delete_file(request.payload)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    def _process_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # REM: Use self.filesystem for file operations (capability-enforced)
        file_path = payload.get("path")
        content = self.filesystem.read(file_path)
        
        # Process content...
        processed = content.upper()
        
        output_path = file_path.replace("/inputs/", "/outputs/")
        self.filesystem.write(output_path, processed)
        
        return {"processed": output_path}
    
    def _delete_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # REM: This action requires approval (see REQUIRES_APPROVAL_FOR)
        # REM: The request will pause until a human approves it
        file_path = payload.get("path")
        # ... deletion logic ...
        return {"deleted": file_path}
```

---

## Agent Architecture

Every agent in TelsonBase inherits from `SecureBaseAgent`, which provides:

```
┌─────────────────────────────────────────────────────────────┐
│                     SecureBaseAgent                          │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │ Message Signing│  │   Capability   │  │   Anomaly     │ │
│  │                │  │   Enforcement  │  │   Monitoring  │ │
│  └────────────────┘  └────────────────┘  └───────────────┘ │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │ Approval Gates │  │ Audit Logging  │  │   Enforced    │ │
│  │                │  │                │  │   Resources   │ │
│  └────────────────┘  └────────────────┘  └───────────────┘ │
│                                                              │
│                    ┌────────────────┐                       │
│                    │  YOUR AGENT    │                       │
│                    │    LOGIC       │                       │
│                    └────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

When a request comes in:

1. **Signature Verification** - If the request came from another agent, its cryptographic signature is verified
2. **Capability Check** - The orchestrator verifies the action is within declared capabilities
3. **Approval Check** - If the action requires approval, the request pauses until a human approves
4. **Execution** - Your `execute()` method runs
5. **Behavior Recording** - The action is recorded for anomaly detection
6. **Audit Logging** - Everything is logged for compliance

---

## Declaring Capabilities

Capabilities follow the format: `resource.action:scope`

### Resource Types

| Resource | Description |
|----------|-------------|
| `filesystem` | Local file system access |
| `external` | External API calls (through egress gateway) |
| `mqtt` | MQTT pub/sub messaging |
| `ollama` | Local LLM inference |
| `redis` | Redis cache/store access |
| `agent` | Inter-agent communication |

### Action Types

| Action | Description |
|--------|-------------|
| `read` | Read/GET operations |
| `write` | Write/POST/PUT operations |
| `execute` | Run/invoke operations |
| `publish` | MQTT publish |
| `subscribe` | MQTT subscribe |
| `none` | Explicitly deny all access |

### Scope Patterns

Scopes support glob patterns:

```python
CAPABILITIES = [
    "filesystem.read:/data/*",           # All files under /data/
    "filesystem.read:/data/users/*.json", # Only JSON files in users/
    "filesystem.write:/app/backups/*",    # Write only to backups/
    "external.read:api.anthropic.com",    # Only Anthropic API
    "external.none",                       # No external access at all
    "ollama.execute:*",                    # Any Ollama model
]
```

### Deny Rules

Prefix with `!` to explicitly deny:

```python
CAPABILITIES = [
    "filesystem.read:/data/*",           # Allow all of /data/
    "!filesystem.read:/data/secrets/*",  # But deny /data/secrets/
]
```

---

## Using Enforced Resources

Don't use standard Python file operations or HTTP clients directly. Use the enforced wrappers provided by the base class:

### Filesystem Access

```python
def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
    # REM: Reading a file (capability-checked)
    content = self.filesystem.read("/data/input.txt")
    
    # REM: Writing a file (capability-checked)
    self.filesystem.write("/app/outputs/result.txt", b"processed data")
    
    # REM: Listing a directory (capability-checked)
    files = self.filesystem.list_dir("/data/")
    
    return {"files_found": len(files)}
```

If your agent tries to access a path outside its declared capabilities, a `PermissionError` is raised and logged.

### External API Access

```python
# REM: Declare the capability first
CAPABILITIES = [
    "external.read:api.anthropic.com",
    "external.write:api.anthropic.com",
]

def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
    # REM: All external requests go through the egress gateway
    response = self.external.post(
        "https://api.anthropic.com/v1/messages",
        json={"model": "claude-3", "messages": [...]}
    )
    
    return {"response": response.json()}
```

If you try to call a domain not in your capabilities (or not in the system whitelist), the request is blocked.

---

## Inter-Agent Communication

Agents can send signed messages to each other:

```python
def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
    # REM: Send a signed message to another agent
    message = self.send_to_agent(
        target_agent="backup_agent",
        action="perform_backup",
        payload={"volume": "user_data"}
    )
    
    # REM: The message is cryptographically signed with our key
    # REM: The receiving agent will verify the signature
    
    return {"message_sent": message.message_id}
```

The receiving agent's `handle_request()` will automatically verify the signature before processing.

---

## Requiring Human Approval

For sensitive operations, require human approval:

```python
class SensitiveAgent(SecureBaseAgent):
    AGENT_NAME = "sensitive_agent"
    
    CAPABILITIES = [
        "filesystem.read:/data/*",
        "filesystem.write:/data/*",
    ]
    
    # REM: These actions will pause and wait for human approval
    REQUIRES_APPROVAL_FOR = [
        "delete_user_data",
        "export_to_external",
        "modify_configuration",
    ]
    
    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        action = request.action
        
        # REM: If action is in REQUIRES_APPROVAL_FOR, the framework
        # REM: has already paused and gotten approval before reaching here
        
        if action == "delete_user_data":
            # REM: We only get here if a human approved this
            return self._delete_user_data(request.payload)
```

The approval flow:

1. Request comes in for `delete_user_data`
2. Framework creates approval request (visible in API/dashboard)
3. Task pauses and waits
4. Human reviews and clicks "Approve" or "Reject"
5. If approved, execution continues. If rejected, PermissionError is raised.

---

## Testing Your Agent

### Unit Testing

```python
# tests/test_my_agent.py

import pytest
from agents.my_agent import MyAgent
from agents.base import AgentRequest

class TestMyAgent:
    
    @pytest.fixture
    def agent(self):
        return MyAgent()
    
    def test_process_file_action(self, agent, tmp_path):
        # REM: Create test file
        input_file = tmp_path / "input.txt"
        input_file.write_text("hello world")
        
        request = AgentRequest(
            request_id="test-001",
            action="process_file",
            payload={"path": str(input_file)},
            requester="test"
        )
        
        # REM: This would need mocking of filesystem access
        # response = agent.handle_request(request)
        # assert response.success
    
    def test_unknown_action_fails(self, agent):
        request = AgentRequest(
            request_id="test-002",
            action="nonexistent_action",
            payload={},
            requester="test"
        )
        
        response = agent.handle_request(request)
        assert not response.success
        assert "Unknown action" in response.error
```

### Integration Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=agents --cov-report=html

# Run specific test file
pytest tests/test_my_agent.py -v
```

---

## Common Patterns

### Pattern: Research Agent

```python
class ResearchAgent(SecureBaseAgent):
    """REM: Agent that queries external APIs and saves results."""
    
    AGENT_NAME = "research_agent"
    
    CAPABILITIES = [
        "external.read:api.perplexity.ai",
        "external.write:api.perplexity.ai",
        "filesystem.write:/app/research/*",
        "!filesystem.read:/data/*",  # Cannot read sensitive data
    ]
    
    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        query = request.payload.get("query")
        
        # REM: Query external API (through egress gateway)
        response = self.external.post(
            "https://api.perplexity.ai/chat/completions",
            json={"query": query}
        )
        
        # REM: Save results locally
        result_path = f"/app/research/{request.request_id}.json"
        self.filesystem.write(result_path, response.content)
        
        return {"saved_to": result_path}
```

### Pattern: Orchestrator Agent

```python
class OrchestratorAgent(SecureBaseAgent):
    """REM: Agent that coordinates other agents."""
    
    AGENT_NAME = "orchestrator"
    
    CAPABILITIES = [
        "agent.execute:*",  # Can dispatch to any agent
    ]
    
    REQUIRES_APPROVAL_FOR = [
        "complex_workflow",  # Multi-agent workflows need approval
    ]
    
    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        if request.action == "data_pipeline":
            # REM: Coordinate multiple agents
            
            # Step 1: Tell research agent to gather data
            self.send_to_agent(
                "research_agent",
                "gather_data",
                {"topic": request.payload["topic"]}
            )
            
            # Step 2: Tell analysis agent to process
            self.send_to_agent(
                "analysis_agent",
                "analyze",
                {"input_dir": "/app/research/"}
            )
            
            return {"pipeline": "initiated"}
```

### Pattern: Backup Agent with Approval

```python
class BackupAgent(SecureBaseAgent):
    """REM: Agent that manages backups."""
    
    AGENT_NAME = "backup_agent"
    
    CAPABILITIES = [
        "filesystem.read:/data/*",
        "filesystem.write:/app/backups/*",
        "filesystem.read:/app/backups/*",
        "external.none",
    ]
    
    REQUIRES_APPROVAL_FOR = [
        "delete_backup",   # Destructive
        "restore_backup",  # Could overwrite data
    ]
    
    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        if request.action == "create_backup":
            # REM: No approval needed
            return self._create_backup(request.payload)
        elif request.action == "delete_backup":
            # REM: Approval required - we only get here if approved
            return self._delete_backup(request.payload)
        elif request.action == "restore_backup":
            # REM: Approval required
            return self._restore_backup(request.payload)
```

---

## QMS Logging Conventions

The TelsonBase uses the Qualified Message Standard (QMS) in logs for human readability:

| Suffix | Meaning | Example |
|--------|---------|---------|
| `_Please` | Request initiated | `Backup_Started_Please` |
| `_Thank_You` | Success | `Backup_Completed_Thank_You` |
| `_Thank_You_But_No` | Failure/Rejection | `Permission_Denied_Thank_You_But_No` |
| `_Excuse_Me` | More info needed | `Missing_Parameter_Excuse_Me` |
| `::value::` | Critical data | `File ::/data/users.db:: backed up` |

Your agent logs will automatically follow these conventions through the base class.

---

## Local Development Without Docker

For quick iteration on agent code or running tests, you can run components locally without Docker.

### Prerequisites

```bash
# Python 3.10+
python --version

# Redis (required for state persistence)
# Install via package manager or run Redis in Docker
docker run -d -p 6379:6379 --name redis-dev redis:7-alpine
```

### Setup

```bash
# Clone repository
git clone https://github.com/quietfire/telsonbase.git
cd telsonbase

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Configuration

```bash
# Copy example environment
cp .env.example .env

# Minimum required for local development:
MCP_API_KEY=dev_key_for_testing
JWT_SECRET_KEY=dev_secret_minimum_32_characters_long
ALLOWED_EXTERNAL_DOMAINS=api.anthropic.com
LOG_LEVEL=DEBUG
```

### Running the API Server

```bash
# Start FastAPI with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or with specific log level
LOG_LEVEL=DEBUG uvicorn main:app --reload
```

### Running Tests Only

If you only need to run tests (no server required):

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov httpx

# Run all tests
pytest -v tests/

# Run specific test file
pytest -v tests/test_api.py

# Run with coverage
pytest --cov=core --cov=agents --cov-report=html tests/
```

### Minimal Component Testing

For testing a single agent without the full stack:

```python
# test_my_agent_local.py
import sys
sys.path.insert(0, '.')

from agents.base import AgentRequest
from agents.document_agent import DocumentProcessorAgent

# Create agent instance
agent = DocumentProcessorAgent()

# Test request (mock - won't actually process files without filesystem setup)
request = AgentRequest(
    request_id="test-001",
    action="get_metadata",
    payload={"file_path": "/app/test.txt"},
    requester="test"
)

# Inspect capabilities
print(f"Agent: {agent.AGENT_NAME}")
print(f"Capabilities: {agent.CAPABILITIES}")
print(f"Requires approval for: {agent.REQUIRES_APPROVAL_FOR}")
```

### What Requires Docker

Some features require the full Docker stack:

| Feature | Local | Docker Required |
|---------|-------|-----------------|
| Unit tests | ✅ | - |
| API endpoint tests | ✅ | Redis |
| Agent code development | ✅ | - |
| Federation testing | - | ✅ |
| Egress gateway testing | - | ✅ |
| Full integration tests | - | ✅ |
| Production deployment | - | ✅ |

---

## Next Steps

1. Review the example agents in `/agents/`
2. Run the test suite: `pytest -v`
3. Check the API documentation at `/docs` when the server is running
4. Read the Federation Guide if you need cross-instance communication
5. See [Troubleshooting](TROUBLESHOOTING.md) for common issues

For questions or issues, contact: support@telsonbase.com
