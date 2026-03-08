# TelsonBase - API Reference

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

# API Reference

## Overview

The TelsonBase API provides endpoints for:
- Agent management and task dispatch
- Approval workflow management
- Anomaly monitoring and resolution
- Federation trust management
- System health and status

**Base URL:** `https://your-domain.com` or `http://localhost:8000` for development

**Authentication:** All endpoints except `/health` require authentication via:
- `X-API-Key` header, OR
- `Authorization: Bearer <token>` header

---

## Authentication

### Get JWT Token

Exchange your API key for a JWT token.

```
POST /v1/auth/token
```

**Request Body:**
```json
{
  "api_key": "your_api_key",
  "expiration_hours": 24
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in_hours": 24
}
```

---

## System

### Health Check

```
GET /health
```

No authentication required.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-01T12:00:00Z",
  "redis": "healthy"
}
```

### System Status

```
GET /v1/system/status
```

**Response:**
```json
{
  "status": "healthy",
  "version": "3.0.0",
  "timestamp": "2026-02-01T12:00:00Z",
  "services": {
    "redis": "healthy"
  },
  "security_status": {
    "registered_agents": 5,
    "pending_approvals": 2,
    "unresolved_anomalies": 1,
    "active_federation_relationships": 3
  }
}
```

---

## Agents

### List Agents

```
GET /v1/agents/
```

**Response:**
```json
{
  "agents": [
    {
      "agent_id": "backup_agent",
      "capabilities": [
        "filesystem.read:/data/*",
        "filesystem.write:/app/backups/*"
      ],
      "signing_key_registered": true
    }
  ],
  "count": 1,
  "qms_status": "Thank_You"
}
```

### Get Agent Details

```
GET /v1/agents/{agent_id}
```

**Response:**
```json
{
  "agent_id": "backup_agent",
  "capabilities": ["filesystem.read:/data/*"],
  "baseline": {
    "avg_actions_per_minute": 2.5,
    "known_resources": ["/data/users", "/data/config"],
    "total_observations": 1523
  },
  "recent_anomalies": [],
  "recent_approvals": [],
  "qms_status": "Thank_You"
}
```

---

## Tasks

### Dispatch Task

```
POST /v1/tasks/dispatch
```

**Request Body:**
```json
{
  "task_name": "backup_agent.perform_backup",
  "args": ["daily"],
  "kwargs": {"volumes": ["user_data"]},
  "priority": "normal"
}
```

**Response:**
```json
{
  "task_id": "abc123-def456",
  "task_name": "backup_agent.perform_backup",
  "status": "dispatched",
  "message": "Task dispatched successfully",
  "qms_status": "Please"
}
```

### Get Task Status

```
GET /v1/tasks/{task_id}
```

**Response (pending):**
```json
{
  "task_id": "abc123-def456",
  "status": "PENDING",
  "ready": false,
  "qms_status": "Please"
}
```

**Response (completed):**
```json
{
  "task_id": "abc123-def456",
  "status": "SUCCESS",
  "ready": true,
  "result": {
    "backup_type": "daily",
    "volumes": {"user_data": {"status": "success"}}
  },
  "qms_status": "Thank_You"
}
```

---

## Approvals

### List Pending Approvals

```
GET /v1/approvals/
```

**Query Parameters:**
- `limit` (int, default 50): Maximum results
- `agent_id` (string, optional): Filter by agent

**Response:**
```json
{
  "pending_requests": [
    {
      "request_id": "APPR-ABC123",
      "agent_id": "backup_agent",
      "action": "delete_backup",
      "description": "Delete old backup files",
      "payload": {"backup_id": "backup-2026-01-01"},
      "priority": "high",
      "status": "pending",
      "created_at": "2026-02-01T12:00:00Z"
    }
  ],
  "count": 1,
  "qms_status": "Thank_You"
}
```

### Get Approval Request

```
GET /v1/approvals/{request_id}
```

### Approve Request

```
POST /v1/approvals/{request_id}/approve
```

**Request Body:**
```json
{
  "decided_by": "admin@example.com",
  "notes": "Approved - old backup no longer needed"
}
```

**Response:**
```json
{
  "request_id": "APPR-ABC123",
  "status": "approved",
  "decided_by": "admin@example.com",
  "qms_status": "Thank_You"
}
```

### Reject Request

```
POST /v1/approvals/{request_id}/reject
```

**Request Body:**
```json
{
  "decided_by": "admin@example.com",
  "notes": "Rejected - backup still needed for audit"
}
```

### Request More Information

```
POST /v1/approvals/{request_id}/request-info
```

**Request Body:**
```json
{
  "decided_by": "admin@example.com",
  "questions": [
    "What is the size of this backup?",
    "Are there any dependent backups?"
  ]
}
```

---

## Anomalies

### List Anomalies

```
GET /v1/anomalies/
```

**Query Parameters:**
- `unresolved_only` (bool, default true)
- `agent_id` (string, optional)
- `severity` (string, optional): low, medium, high, critical
- `limit` (int, default 100)

**Response:**
```json
{
  "anomalies": [
    {
      "anomaly_id": "ANOM-000001",
      "agent_id": "research_agent",
      "anomaly_type": "rate_spike",
      "severity": "medium",
      "description": "Activity rate 15.2/min is 4.3 std devs above baseline",
      "detected_at": "2026-02-01T12:00:00Z",
      "evidence": {
        "current_rate": 15.2,
        "baseline_avg": 3.1,
        "z_score": 4.3
      },
      "requires_human_review": false,
      "resolved": false
    }
  ],
  "count": 1,
  "qms_status": "Thank_You"
}
```

### Dashboard Summary

```
GET /v1/anomalies/dashboard/summary
```

**Response:**
```json
{
  "total_unresolved": 3,
  "requires_human_review": 1,
  "by_severity": {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 0
  },
  "by_type": {
    "rate_spike": 2,
    "capability_probe": 1
  },
  "by_agent": {
    "research_agent": 2,
    "backup_agent": 1
  },
  "qms_status": "Thank_You"
}
```

### Resolve Anomaly

```
POST /v1/anomalies/{anomaly_id}/resolve
```

**Request Body:**
```json
{
  "resolution_notes": "False positive - agent was processing batch job"
}
```

---

## Federation

### Get This Instance's Identity

```
GET /v1/federation/identity
```

**Response:**
```json
{
  "identity": {
    "instance_id": "firm-a-001",
    "organization_name": "Smith & Associates",
    "fingerprint": "A1B2C3D4E5F6",
    "created_at": "2026-01-15T00:00:00Z",
    "version": "3.0.0"
  },
  "qms_status": "Thank_You"
}
```

### Create Trust Invitation

```
POST /v1/federation/invitations
```

**Request Body:**
```json
{
  "trust_level": "standard",
  "allowed_agents": ["research_agent", "document_agent"],
  "allowed_actions": ["message", "query"],
  "expires_in_hours": 72
}
```

**Response:**
```json
{
  "invitation": {
    "invitation_id": "INV-ABC123",
    "type": "trust_invitation",
    "from_identity": {...},
    "proposed_trust_level": "standard",
    "expires_at": "2026-02-04T12:00:00Z",
    "signature": "..."
  },
  "instructions": "Share this invitation through a secure channel",
  "qms_status": "Please"
}
```

### Process Trust Invitation

```
POST /v1/federation/invitations/process
```

**Query Parameters:**
- `auto_accept` (bool, default false): Automatically establish trust

**Request Body:** The invitation object received from the other instance.

### List Relationships

```
GET /v1/federation/relationships
```

**Query Parameters:**
- `status` (string, optional): pending_inbound, established, revoked

### Accept Trust

```
POST /v1/federation/relationships/{relationship_id}/accept
```

**Request Body:**
```json
{
  "decided_by": "managing_partner@firm.com"
}
```

### Revoke Trust

```
POST /v1/federation/relationships/{relationship_id}/revoke
```

**Request Body:**
```json
{
  "reason": "Security incident at remote instance",
  "revoked_by": "security@firm.com"
}
```

**Response:**
```json
{
  "relationship_id": "REL-ABC123",
  "status": "revoked",
  "reason": "Security incident at remote instance",
  "qms_status": "Thank_You_But_No"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**HTTP Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 401 | Authentication required or failed |
| 403 | Permission denied |
| 404 | Resource not found |
| 500 | Internal server error |
| 503 | Service unavailable (e.g., Celery down) |

---

## QMS™ Status Codes

Responses include a `qms_status` field following the Qualified Message Standard (QMS™):

| Status | Meaning |
|--------|---------|
| `Please` | Request received, processing |
| `Thank_You` | Request completed successfully |
| `Thank_You_But_No` | Request completed but with failure/rejection |
| `Excuse_Me` | More information requested |
| `Awaiting_Approval` | Request pending human approval |

---

## MCP Gateway (Goose / Claude Desktop Integration)

TelsonBase exposes its management capabilities as MCP (Model Context Protocol) tools at `/mcp`.
Operators using **Goose** (by Block), **Claude Desktop**, or any MCP-compatible AI agent can connect
and drive TelsonBase workflows through natural language - no REST wrappers, no custom scripts.

> **Security boundary:** The MCP gateway is an **operator interface**, not a public API.
> All tool calls require a valid Bearer token and are logged to the immutable audit chain.
> Any agent action that would cross TelsonBase's external data boundary is automatically
> **queued as a HITL approval request** in the toolroom. Nothing leaves the sovereign perimeter
> without an explicit human decision. The MCP tools give operators *visibility and control*
> over that queue - they do not bypass it.

### Connection

```
Transport: Streamable HTTP (SSE)
Endpoint:  http://<host>:8000/mcp        (dev)
           https://<domain>/mcp          (production via Traefik)
Auth:      Authorization: Bearer <TelsonBase API key>
Config:    See goose.yaml at project root
```

### Available MCP Tools

| Tool | Category | Description |
|------|----------|-------------|
| `system_status` | System | Full health: redis, agents, audit chain, resource usage |
| `get_health` | System | Quick liveness check (redis, API) |
| `list_agents` | Agents | List registered OpenClaw agents (active or all) |
| `get_agent` | Agents | Full details for a specific agent by instance_id |
| `register_as_agent` | Agents | Register the calling session as an OpenClaw instance (starts in quarantine) |
| `list_tenants` | Tenancy | List tenant organisations |
| `create_tenant` | Tenancy | Create a new tenant org |
| `list_matters` | Tenancy | List client-matters under a tenant |
| `get_audit_chain_status` | Audit | Chain state: entry count, last sequence, last hash |
| `verify_audit_chain` | Audit | Cryptographic chain integrity check (up to 1000 entries) |
| `get_recent_audit_entries` | Audit | Browse recent entries, filter by event_type |
| `list_pending_approvals` | Approvals | View queued HITL approval requests |
| `approve_tool_request` | Approvals | Approve a pending toolroom request |

### Example Goose Session

```
$ goose session

Goose: Connected to TelsonBase MCP server. 13 tools available.

You: What's the system status?
Goose → system_status()
← { redis: "healthy", agents: { total: 3, active: 2, suspended: 1 },
     audit_chain: { entry_count: 4821, last_sequence: 4821 }, qms_status: "Thank_You" }

You: Show me all pending approvals.
Goose → list_pending_approvals()
← { count: 2, approvals: [ { request_id: "APPR-001", agent: "web_agent", action: "POST /api/external" }, ... ] }

You: Approve APPR-001 - I've reviewed it.
Goose → approve_tool_request(request_id="APPR-001", approved_by="operator@telsonbase.com")
← { approved: true, qms_status: "Thank_You" }

You: Register me as a Goose agent at probation trust level.
Goose → register_as_agent(name="ops-goose-session", api_key="...", initial_trust_level="probation",
                           override_reason="Operator session, manually verified")
← { instance_id: "oc-xxxx", trust_level: "probation", qms_status: "Thank_You" }
```

### Tool Response Format

All tools return the QMS status field:

| `qms_status` | Meaning |
|---|---|
| `Thank_You` | Tool call succeeded |
| `Thank_You_But_No` | Tool call failed (see `error` field) |

### Connecting Goose

1. Install Goose: `curl -fsSL https://github.com/block/goose/releases/latest/download/install.sh | bash`
2. Copy `goose.yaml` from project root → `~/.config/goose/config.yaml`
3. Set `TELSONBASE_API_KEY` to your TelsonBase API key
4. Run `goose session` - tools are auto-discovered

---

## Python Client Examples

### Basic Setup

```python
import requests
from typing import Optional, Dict, Any

class TelsonBaseClient:
    """Simple Python client for TelsonBase API."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers["X-API-Key"] = api_key

    def health(self) -> Dict[str, Any]:
        """Check system health (no auth required)."""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    def status(self) -> Dict[str, Any]:
        """Get detailed system status."""
        response = self.session.get(f"{self.base_url}/v1/system/status")
        response.raise_for_status()
        return response.json()

    def list_agents(self) -> Dict[str, Any]:
        """List all registered agents."""
        response = self.session.get(f"{self.base_url}/v1/agents/")
        response.raise_for_status()
        return response.json()

    def dispatch_task(
        self,
        task_name: str,
        args: list = None,
        kwargs: dict = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """Dispatch a task to an agent."""
        payload = {
            "task_name": task_name,
            "args": args or [],
            "kwargs": kwargs or {},
            "priority": priority
        }
        response = self.session.post(
            f"{self.base_url}/v1/tasks/dispatch",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Check task completion status."""
        response = self.session.get(f"{self.base_url}/v1/tasks/{task_id}")
        response.raise_for_status()
        return response.json()

    def list_pending_approvals(self, limit: int = 50) -> Dict[str, Any]:
        """List pending approval requests."""
        response = self.session.get(
            f"{self.base_url}/v1/approvals/",
            params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()

    def approve_request(
        self,
        request_id: str,
        decided_by: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Approve a pending request."""
        response = self.session.post(
            f"{self.base_url}/v1/approvals/{request_id}/approve",
            json={"decided_by": decided_by, "notes": notes}
        )
        response.raise_for_status()
        return response.json()

    def get_anomaly_summary(self) -> Dict[str, Any]:
        """Get anomaly dashboard summary."""
        response = self.session.get(
            f"{self.base_url}/v1/anomalies/dashboard/summary"
        )
        response.raise_for_status()
        return response.json()


# Usage example
if __name__ == "__main__":
    client = TelsonBaseClient(
        base_url="http://localhost:8000",
        api_key="your_api_key_here"
    )

    # Check health
    print(client.health())

    # Get system status
    status = client.status()
    print(f"Registered agents: {status['security_status']['registered_agents']}")

    # List agents
    agents = client.list_agents()
    for agent in agents["agents"]:
        print(f"  - {agent['agent_id']}")

    # Dispatch a task
    result = client.dispatch_task(
        task_name="backup_agent.perform_backup",
        kwargs={"backup_type": "incremental"}
    )
    print(f"Task dispatched: {result['task_id']}")
```

### Async Client (for high-performance applications)

```python
import httpx
import asyncio
from typing import Dict, Any

class AsyncTelsonBaseClient:
    """Async Python client for TelsonBase API."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key} if api_key else {}

    async def health(self) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    async def dispatch_and_wait(
        self,
        task_name: str,
        kwargs: dict = None,
        timeout: int = 300,
        poll_interval: int = 2
    ) -> Dict[str, Any]:
        """Dispatch task and wait for completion."""
        async with httpx.AsyncClient(headers=self.headers) as client:
            # Dispatch
            response = await client.post(
                f"{self.base_url}/v1/tasks/dispatch",
                json={"task_name": task_name, "kwargs": kwargs or {}}
            )
            response.raise_for_status()
            task_id = response.json()["task_id"]

            # Poll for completion
            elapsed = 0
            while elapsed < timeout:
                response = await client.get(f"{self.base_url}/v1/tasks/{task_id}")
                status = response.json()

                if status.get("ready"):
                    return status

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")


# Async usage example
async def main():
    client = AsyncTelsonBaseClient(
        base_url="http://localhost:8000",
        api_key="your_api_key_here"
    )

    # Check health
    health = await client.health()
    print(f"Status: {health['status']}")

    # Dispatch and wait for result
    result = await client.dispatch_and_wait(
        task_name="document_agent.extract_text",
        kwargs={"file_path": "/data/document.pdf"},
        timeout=60
    )
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Error Handling

```python
import requests
from requests.exceptions import HTTPError

def safe_api_call(client: TelsonBaseClient):
    """Example of proper error handling."""
    try:
        result = client.dispatch_task(
            task_name="backup_agent.delete_backup",
            kwargs={"backup_id": "backup-001"}
        )

        # Check QMS status
        if result.get("qms_status") == "Thank_You":
            print("Task completed successfully")
        elif result.get("qms_status") == "Awaiting_Approval":
            print(f"Approval required: {result.get('approval_id')}")
        elif result.get("qms_status") == "Thank_You_But_No":
            print(f"Task failed: {result.get('error')}")

    except HTTPError as e:
        if e.response.status_code == 401:
            print("Authentication failed - check API key")
        elif e.response.status_code == 403:
            print("Permission denied - check agent capabilities")
        elif e.response.status_code == 404:
            print("Resource not found")
        else:
            print(f"API error: {e.response.status_code} - {e.response.text}")
    except requests.ConnectionError:
        print("Connection failed - is the server running?")
```

---

## Rate Limiting

TelsonBase implements rate limiting via production middleware (`core/middleware.py`) to prevent abuse and ensure fair resource allocation.

### Global Rate Limits

| Limit Type | Value | Description |
|------------|-------|-------------|
| Requests per minute | 120 | Token bucket rate limit per client |
| Burst allowance | 20 | Additional requests allowed in burst |
| Request size | 10 MB | Maximum request body size |

### Per-Agent Rate Limits

Agents are additionally rate-limited based on their trust level:

| Trust Level | Requests/min | Concurrent Tasks |
|-------------|--------------|------------------|
| QUARANTINE | 10 | 1 |
| PROBATION | 30 | 3 |
| RESIDENT | 60 | 5 |
| CITIZEN | 120 | 10 |

### Rate Limit Headers

All responses include rate limit information:

```http
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 115
X-RateLimit-Reset: 1706799600
```

### Rate Limit Exceeded Response

```json
{
  "detail": "Rate limit exceeded. Try again in 5 seconds.",
  "retry_after": 5
}
```

HTTP Status: `429 Too Many Requests`

---

## Webhooks

TelsonBase supports webhook callbacks for async operations, particularly approval workflows.

### Webhook Callback Format

When an approval decision is made and a `callback_url` was provided:

```json
{
  "event": "approval.decided",
  "approval_id": "APPR-ABC123",
  "status": "approved",
  "decided_by": "admin@example.com",
  "decision_time": "2026-02-04T12:05:00Z",
  "original_request": {
    "agent": "document_agent",
    "action": "redact",
    "payload": {"file_path": "/data/sensitive.pdf"}
  },
  "result": null,
  "notes": "Approved for compliance review"
}
```

### Webhook Delivery

- **Method:** POST
- **Content-Type:** application/json
- **Timeout:** 30 seconds
- **Retries:** 3 attempts with exponential backoff

### Webhook Security

- Verify the source by checking the `X-TelsonBase-Signature` header
- Signature is HMAC-SHA256 of the request body using your API key
- Example verification (Python):

```python
import hmac
import hashlib

def verify_webhook(body: bytes, signature: str, api_key: str) -> bool:
    expected = hmac.new(
        api_key.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### MCP / Goose Approval Notifications

When an approval is decided, the result is visible to Goose sessions via the `list_pending_approvals` and `approve_tool_request` tools. Operators polling with Goose will see approvals transition from `pending` to `approved` or `rejected` in real time.

For programmatic notification, subscribe to the audit chain SSE stream at `/v1/audit/stream` and filter for `approval.decided` events.

See [MCP Gateway](#mcp-gateway-goose--claude-desktop-integration) for complete Goose integration details.

---

## Related Documentation

- [Developer Guide](DEVELOPER_GUIDE.md) - Building agents
- [Security Architecture](SECURITY_ARCHITECTURE.md) - Security model
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
