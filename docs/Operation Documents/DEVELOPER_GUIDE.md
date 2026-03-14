# ClawCoat - Developer Guide

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

This guide explains how to build AI agents that run within the TelsonBase zero-trust architecture using the **embedded Python integration path** - agents written in Python that inherit from `SecureBaseAgent` and run inside TelsonBase.

> **External agents (Goose, Claude Desktop, any HTTP client)** use a different path - the OpenClaw REST API. See [OPENCLAW_INTEGRATION_GUIDE.md](OPENCLAW_INTEGRATION_GUIDE.md) for that approach.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Agent Architecture](#agent-architecture)
3. [Trust Levels and Your Agent](#trust-levels-and-your-agent)
4. [Declaring Capabilities](#declaring-capabilities)
5. [Using Enforced Resources](#using-enforced-resources)
6. [Inter-Agent Communication](#inter-agent-communication)
7. [Requiring Human Approval](#requiring-human-approval)
8. [QMS Logging Conventions](#qms-logging-conventions)
9. [Testing Your Agent](#testing-your-agent)
10. [Common Patterns](#common-patterns)
11. [Local Development Without Docker](#local-development-without-docker)

---

## Quick Start

Here's the minimal code for a secure agent:

```python
from agents.base import SecureBaseAgent, AgentRequest
from typing import Dict, Any, Optional

class MyAgent(SecureBaseAgent):
    """A simple example agent."""

    # Required: unique name used in audit logs and routing
    AGENT_NAME = "my_agent"

    # Required: declare exactly what this agent is allowed to do
    CAPABILITIES = [
        "filesystem.read:/app/inputs/*",
        "filesystem.write:/app/outputs/*",
        "external.none",  # cannot make external API calls
    ]

    # Optional: actions that pause and wait for human approval
    REQUIRES_APPROVAL_FOR = [
        "delete_file",
        "send_notification",
    ]

    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        """Route incoming actions to handler methods."""
        action = request.action.lower()

        if action == "process_file":
            return self._process_file(request.payload)
        elif action == "delete_file":
            return self._delete_file(request.payload)
        else:
            raise ValueError(f"Unknown action: {action}")

    def _process_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Use self.filesystem - capability-enforced, not raw Python file I/O
        file_path = payload.get("path")
        content = self.filesystem.read(file_path)

        processed = content.upper()

        output_path = file_path.replace("/inputs/", "/outputs/")
        self.filesystem.write(output_path, processed)

        return {"processed": output_path}

    def _delete_file(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Only reached after a human approves the request (REQUIRES_APPROVAL_FOR)
        file_path = payload.get("path")
        # ... deletion logic ...
        return {"deleted": file_path}
```

---

## Agent Architecture

Every agent inherits from `SecureBaseAgent`, which wraps your logic with six enforcement layers:

```
┌─────────────────────────────────────────────────────────────┐
│                     SecureBaseAgent                          │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ Message Signing│  │   Capability   │  │   Anomaly     │  │
│  │                │  │   Enforcement  │  │   Monitoring  │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ Approval Gates │  │ Audit Logging  │  │   Enforced    │  │
│  │                │  │                │  │   Resources   │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  │
│                                                              │
│                    ┌────────────────┐                        │
│                    │  YOUR AGENT    │                        │
│                    │    LOGIC       │                        │
│                    └────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

**What happens when a request arrives (embedded Python path):**

1. **Signature Verification** - If the request came from another agent, its HMAC-SHA256 signature is verified against the sender's registered key. Unsigned inter-agent messages are rejected. *(proof: tb-proof-064)*
2. **Capability Check** - The declared `CAPABILITIES` list is checked against the requested action and target. No match means an immediate `PermissionError`, logged to the audit chain. *(proof: tb-proof-063)*
3. **Approval Check** - If the action is in `REQUIRES_APPROVAL_FOR`, the request pauses and creates a visible approval item. Execution does not continue until a human approves. *(proof: TB-PROOF-019)*
4. **Execution** - Your `execute()` method runs.
5. **Behavior Recording** - The action is recorded for anomaly baseline tracking. Deviations from baseline trigger anomaly events. *(proof: tb-proof-059)*
6. **Audit Logging** - Every request and outcome is written to the hash-chained audit trail. *(proof: TB-PROOF-009)*

> **Note:** External agents connecting via the REST API go through the full 8-step OpenClaw governance pipeline (which adds kill switch, nonce replay, and Manners compliance checks). See `docs/FAQ.md` Q21 for the full pipeline breakdown.

---

## Trust Levels and Your Agent

**New embedded agents start at QUARANTINE.** This is intentional and important.

| Trust Level | What it means for your agent |
|---|---|
| QUARANTINE | Severely restricted. Most capabilities blocked. Requires manual review to proceed. |
| PROBATION | Limited capabilities. Closely monitored. Standard starting point for most deployments. |
| RESIDENT | Standard capabilities. Periodic re-verification. |
| CITIZEN | Full capabilities. 95%+ success rate required. |
| AGENT | Apex tier. 99.9% success rate, zero anomaly tolerance, re-verification every 3 days. |

**Before your agent can do useful work**, an operator must promote it from QUARANTINE via the dashboard or API:

```bash
# Promote via API
curl -X POST http://localhost:8000/v1/openclaw/{instance_id}/promote \
  -H "X-API-Key: $API_KEY" \
  -d '{"reason": "Initial deployment - reviewed and approved"}'
```

**Manners compliance score:** Every agent receives a score from 0.0 to 1.0, updated in real time. Five states:

| Score | Status | Operational impact |
|---|---|---|
| 0.90-1.00 | EXEMPLARY | Full autonomous operation |
| 0.75-0.89 | COMPLIANT | Normal operation |
| 0.50-0.74 | DEGRADED | Increased monitoring, weekly review triggered |
| 0.25-0.49 | NON_COMPLIANT | Read-only access only |
| 0.00-0.24 | SUSPENDED | Quarantined, human review required |

**Two triggers for automatic quarantine** (no human delay required):
1. Score drops below 0.25 (SUSPENDED range)
2. Three or more violations within any 24-hour window - regardless of overall score

Build agents that behave predictably. *(proof: TB-PROOF-038)*

---

## Declaring Capabilities

Capabilities follow the format: `resource.action:scope`

### Resource Types

| Resource | Description |
|---|---|
| `filesystem` | Local file system access |
| `external` | External API calls (through egress gateway) |
| `mqtt` | MQTT pub/sub messaging |
| `ollama` | Local LLM inference |
| `redis` | Redis cache/store access |
| `agent` | Inter-agent communication |

### Action Types

| Action | Description |
|---|---|
| `read` | Read/GET operations |
| `write` | Write/POST/PUT operations |
| `execute` | Run/invoke operations |
| `publish` | MQTT publish |
| `subscribe` | MQTT subscribe |
| `none` | Explicitly deny all access to this resource |

### Scope Patterns

Scopes support glob patterns:

```python
CAPABILITIES = [
    "filesystem.read:/data/*",            # all files under /data/
    "filesystem.read:/data/users/*.json", # only JSON files in users/
    "filesystem.write:/app/backups/*",    # write only to backups/
    "external.read:api.anthropic.com",    # only Anthropic API
    "external.none",                       # no external access at all
    "ollama.execute:*",                    # any Ollama model
]
```

### Deny Rules

Prefix with `!` to explicitly deny a specific path within a broader allow:

```python
CAPABILITIES = [
    "filesystem.read:/data/*",           # allow all of /data/
    "!filesystem.read:/data/secrets/*",  # but deny /data/secrets/
]
```

Deny rules take precedence over allow rules. *(proof: tb-proof-063)*

---

## Using Enforced Resources

Do not use raw Python file operations (`open()`) or HTTP clients (`requests`, `httpx`) directly. Use the enforced wrappers provided by the base class. Bypassing these wrappers bypasses capability enforcement and audit logging.

### Filesystem Access

```python
def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
    # All of these are capability-checked against CAPABILITIES
    content = self.filesystem.read("/data/input.txt")
    self.filesystem.write("/app/outputs/result.txt", b"processed data")
    files = self.filesystem.list_dir("/data/")

    return {"files_found": len(files)}
```

If your agent tries to access a path outside its declared capabilities, a `PermissionError` is raised and logged to the audit chain. The request does not silently fail - it fails loudly and on record.

### External API Access

```python
# Declare the capability first
CAPABILITIES = [
    "external.read:api.anthropic.com",
    "external.write:api.anthropic.com",
]

def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
    # All external requests go through the egress gateway
    # The gateway enforces the ALLOWED_EXTERNAL_DOMAINS system whitelist
    # as a second check after capability enforcement
    response = self.external.post(
        "https://api.anthropic.com/v1/messages",
        json={"model": "claude-sonnet-4-6", "messages": [...]}
    )

    return {"response": response.json()}
```

Two enforcement layers apply: your agent's `CAPABILITIES` list, and the system-level `ALLOWED_EXTERNAL_DOMAINS` whitelist. A request blocked at either layer is logged.

---

## Inter-Agent Communication

Agents communicate by sending signed messages to each other via the MQTT bus. Every message carries an HMAC-SHA256 signature computed from the sender's registered key.

```python
def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
    # Send a signed message to another agent
    message = self.send_to_agent(
        target_agent="backup_agent",
        action="perform_backup",
        payload={"volume": "user_data"}
    )

    # The receiving agent verifies the signature before processing.
    # If verification fails, the message is rejected and an anomaly is logged.

    return {"message_sent": message.message_id}
```

You do not need to sign messages manually. `send_to_agent()` handles signing. You do need to ensure your agent has the `agent.execute:backup_agent` capability (or `agent.execute:*`) in its `CAPABILITIES` list. *(proof: tb-proof-064)*

---

## Requiring Human Approval

Add destructive or sensitive actions to `REQUIRES_APPROVAL_FOR`. The framework handles the pause/resume automatically - your `execute()` method only runs after a human approves.

```python
class SensitiveAgent(SecureBaseAgent):
    AGENT_NAME = "sensitive_agent"

    CAPABILITIES = [
        "filesystem.read:/data/*",
        "filesystem.write:/data/*",
    ]

    # These actions pause and wait for a human decision
    REQUIRES_APPROVAL_FOR = [
        "delete_user_data",
        "export_to_external",
        "modify_configuration",
    ]

    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        if request.action == "delete_user_data":
            # Only reached after a human approved this specific request
            return self._delete_user_data(request.payload)
```

**The full approval flow:**

1. Request arrives for `delete_user_data`
2. Framework creates an approval record - visible in the dashboard and via `GET /v1/approvals`
3. Task pauses (`threading.Event.wait()`)
4. Human reviews the payload and clicks Approve or Reject
5. If approved: execution resumes, your method runs
6. If rejected or expired: `PermissionError` is raised, logged to audit chain, task fails cleanly

The approval record includes the full payload so the reviewer knows exactly what they are approving. *(proof: TB-PROOF-019)*

---

## QMS Logging Conventions

TelsonBase uses the Qualified Message Standard (QMS™) in logs for human readability. Your agent's base class appends these suffixes automatically. Understanding them helps when reading audit logs.

| Suffix | Meaning | Example |
|---|---|---|
| `_Please` | Request initiated | `Backup_Started_Please` |
| `_Thank_You` | Success | `Backup_Completed_Thank_You` |
| `_Thank_You_But_No` | Failure or rejection | `Permission_Denied_Thank_You_But_No` |
| `_Excuse_Me` | More information needed | `Missing_Parameter_Excuse_Me` |
| `::value::` | Critical inline data | `File ::/data/users.db:: backed up` |

Chains use `-` as a separator and always end with `::`. Example from a live audit entry:

```
::backup_agent.perform_backup::-::volume:user_data::-::Thank_You::
```

You do not write QMS manually. The base class and audit logger handle formatting. What you write in your log messages appears inside the `::` blocks. *(proof: tb-proof-053, docs/QMS Documents/QMS_SPECIFICATION.md)*

---

## Testing Your Agent

### Unit Testing

```python
# tests/test_my_agent.py

import pytest
from unittest.mock import MagicMock, patch
from agents.my_agent import MyAgent
from agents.base import AgentRequest

class TestMyAgent:

    @pytest.fixture
    def agent(self):
        return MyAgent()

    def test_process_file_action(self, agent):
        # Mock the filesystem wrapper to avoid needing real files
        agent.filesystem = MagicMock()
        agent.filesystem.read.return_value = b"hello world"

        request = AgentRequest(
            request_id="test-001",
            action="process_file",
            payload={"path": "/app/inputs/test.txt"},
            requester="test"
        )

        result = agent._process_file(request.payload)
        assert result["processed"] == "/app/outputs/test.txt"
        agent.filesystem.write.assert_called_once()

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

Mock `self.filesystem`, `self.external`, and `self.send_to_agent` when unit testing. These wrappers call into the enforcement layer - in unit tests you want to test your logic, not the framework.

### Integration Testing

```bash
# Run all tests inside Docker (full stack available)
docker compose exec mcp_server python -m pytest -v

# Run with coverage
docker compose exec mcp_server python -m pytest --cov=agents --cov-report=html

# Run specific test file
docker compose exec mcp_server python -m pytest tests/test_my_agent.py -v
```

---

## Common Patterns

### Pattern: Research Agent

```python
class ResearchAgent(SecureBaseAgent):
    """Agent that queries external APIs and saves results locally."""

    AGENT_NAME = "research_agent"

    CAPABILITIES = [
        "external.read:api.perplexity.ai",
        "external.write:api.perplexity.ai",
        "filesystem.write:/app/research/*",
        "!filesystem.read:/data/*",  # explicitly cannot read sensitive data
    ]

    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        query = request.payload.get("query")

        response = self.external.post(
            "https://api.perplexity.ai/chat/completions",
            json={"query": query}
        )

        result_path = f"/app/research/{request.request_id}.json"
        self.filesystem.write(result_path, response.content)

        return {"saved_to": result_path}
```

### Pattern: Orchestrator Agent

```python
class OrchestratorAgent(SecureBaseAgent):
    """Agent that coordinates other agents."""

    AGENT_NAME = "orchestrator"

    CAPABILITIES = [
        "agent.execute:*",  # can dispatch to any registered agent
    ]

    REQUIRES_APPROVAL_FOR = [
        "complex_workflow",  # multi-agent workflows need human sign-off
    ]

    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        if request.action == "data_pipeline":
            # Step 1: tell research agent to gather data
            self.send_to_agent(
                "research_agent",
                "gather_data",
                {"topic": request.payload["topic"]}
            )

            # Step 2: tell analysis agent to process
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
    """Agent that manages backups. Creates freely, deletes/restores with approval."""

    AGENT_NAME = "backup_agent"

    CAPABILITIES = [
        "filesystem.read:/data/*",
        "filesystem.write:/app/backups/*",
        "filesystem.read:/app/backups/*",
        "external.none",
    ]

    REQUIRES_APPROVAL_FOR = [
        "delete_backup",   # destructive
        "restore_backup",  # could overwrite live data
    ]

    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        if request.action == "create_backup":
            return self._create_backup(request.payload)
        elif request.action == "delete_backup":
            # Only reached after human approval
            return self._delete_backup(request.payload)
        elif request.action == "restore_backup":
            # Only reached after human approval
            return self._restore_backup(request.payload)
```

---

## Local Development Without Docker

For quick iteration on agent code or running unit tests, you can run without the full Docker stack.

### Prerequisites

```bash
# Python 3.11+ required
python --version

# Redis is required for state persistence
# Run a dev Redis in Docker while developing locally:
docker run -d -p 6379:6379 --name redis-dev redis:7-alpine
```

### Setup

```bash
git clone https://github.com/QuietFireAI/ClawCoat.git
cd TelsonBase

python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/macOS)
source venv/bin/activate

pip install -r requirements.txt
```

### Environment Configuration

```bash
cp .env.example .env

# Minimum required for local development:
MCP_API_KEY=dev_key_for_testing
JWT_SECRET_KEY=dev_secret_minimum_32_characters_long
ALLOWED_EXTERNAL_DOMAINS=api.anthropic.com
LOG_LEVEL=DEBUG
```

### Running the API Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests Only

```bash
pip install pytest pytest-asyncio pytest-cov httpx

pytest -v tests/
pytest -v tests/test_api.py
pytest --cov=core --cov=agents --cov-report=html tests/
```

### What Requires Docker

| Feature | Local | Needs Docker |
|---|---|---|
| Unit tests | Yes | - |
| API endpoint tests | Yes (needs Redis) | - |
| Agent code development | Yes | - |
| Federation testing | - | Yes |
| Egress gateway testing | - | Yes |
| Full integration tests | - | Yes |
| Production deployment | - | Yes |

---

## Next Steps

1. Review the example agents in `/agents/`
2. Run the full test suite: `docker compose exec mcp_server python -m pytest -v`
3. Check live API docs at `http://localhost:8000/docs` when the server is running
4. Read [OPENCLAW_INTEGRATION_GUIDE.md](OPENCLAW_INTEGRATION_GUIDE.md) if you need external agents (Goose, Claude Desktop, HTTP clients)
5. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues

For questions: support@clawcoat.com

---

> **On AI collaboration:** TelsonBase was built with Claude Code (Anthropic) as engineering co-author. 80+ commits carry a `Co-Authored-By: Claude Sonnet 4.6` trailer. That is an accurate record of how this was built, not a liability disclaimer. The README contains a full verification note from Claude Code covering what was checked against the live codebase before launch. If you have questions about methodology, `support@clawcoat.com` reaches the human.

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
