# TelsonBase Toolroom

## REM: Architect: ::Quietfire AI Project::
## REM: Date: February 23, 2026
## REM: Version: 4.6.0CC

---

## What Is the Toolroom?

The Toolroom is the **single source of truth** for all tools available to agents on base. Think of it as a machine shop tool crib — nothing leaves without being signed out, nothing returns without being inspected, and one supervisor (the Foreman) manages everything.

**Core principle:** All agents draw from the same Toolroom. No agent accesses external tools directly. No shadow tooling.

---

## The Foreman Agent

The Foreman is a **supervisor-level agent** responsible for:

| Responsibility | How It Works |
|---|---|
| **Maintain tools** | Install, update, deprecate, quarantine tools |
| **Daily updates** | Checks approved GitHub repos via semantic versioning (Celery Beat) |
| **Auth check** | Verifies agent trust level and permissions before checkout |
| **Usage tracking** | Every checkout and return is logged and audited |
| **New tool requests** | Agents can request tools they need; Foreman routes to HITL |
| **HITL gate** | ANY operation requiring API/external access notifies human first |
| **Execute tools** | Routes invocations to subprocess or function execution engine |

### Security Constraints

- **GitHub access ONLY** — the Foreman can only pull from explicitly approved repositories listed in `APPROVED_GITHUB_SOURCES`
- **HITL gate on ALL external operations** — the Foreman will notify the human operator and **wait for explicit authorization** before any install, update, or API-access operation
- **Cannot modify its own capabilities** — defense-in-depth
- **All actions audited** — hash-chained audit logs via `core/audit.py`
- **Approval state persisted in Redis** — survives worker restarts (fixes race condition from v4.5.0)

---

## How Agents Use the Toolroom

### 1. Checking Out a Tool

```
Agent → Foreman: "Checkout_Tool_Please ::agent_id:: ::tool_id::"
Foreman checks:
  1. Does tool exist?
  2. Is agent authorized?
  3. Does agent meet trust level requirement?
  4. Does tool require API access? → HITL gate
Foreman → Agent: "Tool_Checkout_Thank_You ::CHKOUT-xxxxx::"
```

### 2. Executing a Tool (v4.6.0CC)

After checkout, agents can execute tools through the Foreman:

```
Agent → Foreman: "Tool_Execute_Please ::tool_id:: checkout=CHKOUT-xxxxx inputs={...}"
Foreman:
  1. Verifies active checkout exists for this agent+tool
  2. Routes to function execution (in-house tools) or subprocess execution (git-cloned tools)
  3. Collects result, logs execution, returns output
Foreman → Agent: "Tool_Execute_Thank_You ::{output}::"
```

**Subprocess tools** run with: scoped environment, restricted PATH, timeout enforcement, and unprivileged execution context.

**Function tools** run as direct Python callables with timeout protection and exception isolation.

### 3. Returning a Tool

```
Agent → Foreman: "Tool_Return_Please ::CHKOUT-xxxxx::"
Foreman → Agent: "Tool_Return_Thank_You ::CHKOUT-xxxxx::"
```

### 4. Requesting a New Tool

```
Agent → Foreman: "New_Tool_Request_Please ::description:: from @@agent_id@@"
Foreman → HITL: "New tool request from agent — awaiting review"
HITL → Foreman: approve/reject
```

---

## Tool Manifest (v4.6.0CC)

Every executable tool must provide a `tool_manifest.json` at its root. The manifest is the contract between the tool and the execution engine.

```json
{
  "name": "pgcli",
  "version": "4.1.0",
  "description": "PostgreSQL CLI with auto-completion",
  "entry_point": "pgcli/main.py",
  "runtime": "python3",
  "input_params": {
    "query": {"type": "string", "required": true},
    "database": {"type": "string", "required": true}
  },
  "output_format": "json",
  "sandbox_level": "restricted",
  "timeout_seconds": 30,
  "requires_network": false,
  "dependencies": ["psycopg2-binary"]
}
```

**Validation rules:**
- `name`, `entry_point`, `version` are required
- Entry points are checked for shell injection characters (`;`, `|`, `` ` ``, `$(`)
- `sandbox_level` must be one of: `none`, `restricted`, `isolated`
- `timeout_seconds` must be 1–3600
- `requires_network` without sandbox generates a warning

Tools installed without a manifest are registered but **cannot be executed** until a manifest is provided.

---

## Function Tools (v4.6.0CC)

For in-house Python tools, use the `@register_function_tool` decorator instead of git repos:

```python
from toolroom.function_tools import register_function_tool

@register_function_tool(
    name="Hash Calculator",
    category="crypto",
    description="Compute SHA-256 hash of input text",
)
def hash_text(text: str, algorithm: str = "sha256") -> dict:
    import hashlib
    h = hashlib.new(algorithm, text.encode()).hexdigest()
    return {"hash": h, "algorithm": algorithm}
```

Function tools:
- Auto-generate a manifest from the decorator parameters
- Are synced into the main tool registry via `foreman_agent.sync_function_tools`
- Use the same checkout/return tracking as git-cloned tools
- Execute as direct callables — no subprocess overhead
- Have timeout protection and exception isolation

---

## Uploading Git-Cloned Tools

The human operator can install tools from approved GitHub repos:

1. **Propose** — creates HITL approval request:
```bash
docker-compose exec worker celery -A celery_app.worker call \
  foreman_agent.propose_tool_install \
  --args='["dbcli/pgcli", "pgcli", "PostgreSQL CLI", "database", false]'
```

2. **Approve** — human approves via approval API

3. **Execute install** — after approval:
```bash
docker-compose exec worker celery -A celery_app.worker call \
  foreman_agent.execute_tool_install \
  --args='["dbcli/pgcli", "pgcli", "PostgreSQL CLI", "database", "latest", false, "operator", "APPR-xxxxx"]'
```

Or register a manually uploaded tool:

```bash
docker-compose exec worker celery -A celery_app.worker call \
  foreman_agent.register_uploaded_tool \
  --args='["sqlite_tools", "SQLite CLI", "database", "/app/toolroom/tools/tool_sqlite", "3.45.0", false]'
```

---

## Daily Update Cycle

The Foreman runs a daily update check via Celery Beat:

1. **Check** — queries GitHub API for each tool's source repo
2. **Compare** — uses semantic versioning (`packaging.version.parse`) to detect actual version changes. Handles `v` prefixes, pre-release tags, and patch increments correctly.
3. **Propose** — if updates found, creates proposals for HITL review
4. **Wait** — does NOT auto-install. Human must approve each update
5. **Install** — after HITL approval, Foreman pulls update and verifies integrity (SHA-256)

---

## API Access Gate

This is non-negotiable:

> Any tool or operation that requires external API access triggers a HITL notification. The Foreman **cannot proceed** without explicit human authorization. Period.

This keeps API access centralized through one managed agent, preventing credential sprawl and unauthorized external communication.

---

## Directory Structure

```
toolroom/
├── __init__.py          # Package exports
├── foreman.py           # Foreman agent (supervisor-level)
├── registry.py          # Tool registry, metadata, checkout system
├── manifest.py          # Tool manifest schema and validation (v4.6.0CC)
├── executor.py          # Subprocess and function execution engine (v4.6.0CC)
├── function_tools.py    # @register_function_tool decorator system (v4.6.0CC)
├── TOOLROOM.md          # This file
└── tools/               # Actual tool packages
    └── (uploaded/installed tools go here)
```

---

## Celery Tasks

| Task Name | Trigger | HITL Required |
|---|---|---|
| `foreman_agent.daily_update_check` | Celery Beat (daily 3AM) | Updates require approval |
| `foreman_agent.checkout_tool` | Agent request | Only if tool needs API access |
| `foreman_agent.return_tool` | Agent request | No |
| `foreman_agent.register_uploaded_tool` | Human upload | No (human is uploading) |
| `foreman_agent.request_new_tool` | Agent request | Request goes to HITL |
| `foreman_agent.toolroom_status` | On-demand | No |
| `foreman_agent.propose_tool_install` | Agent/human request | Creates HITL approval |
| `foreman_agent.execute_tool_install` | Post-HITL approval | Verifies approval first |
| `foreman_agent.complete_api_checkout` | Post-HITL approval | Verifies approval first |
| `foreman_agent.execute_tool` | Agent request (v4.6.0CC) | Requires active checkout |
| `foreman_agent.sync_function_tools` | Startup/on-demand (v4.6.0CC) | No |

---

## API Endpoints

### GET Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /v1/toolroom/tools` | List all registered tools |
| `GET /v1/toolroom/tools/{tool_id}` | Get specific tool details |
| `GET /v1/toolroom/checkouts` | List active checkouts |
| `GET /v1/toolroom/checkouts/{agent_id}` | Checkouts for specific agent |
| `GET /v1/toolroom/requests` | Pending tool requests from agents |
| `GET /v1/toolroom/status` | Full toolroom status report |
| `GET /v1/toolroom/history` | Checkout history |

### POST Endpoints

| Endpoint | Purpose | HITL |
|---|---|---|
| `POST /v1/toolroom/checkout` | Agent checks out a tool | If API-access tool |
| `POST /v1/toolroom/return` | Agent returns a tool | No |
| `POST /v1/toolroom/install/propose` | Propose tool install from GitHub | Creates approval |
| `POST /v1/toolroom/install/execute` | Execute approved install | Verifies approval |
| `POST /v1/toolroom/request` | Agent requests new tool | Goes to HITL |
| `POST /v1/toolroom/checkout/api-complete` | Complete API-access checkout | Verifies approval |
| `POST /v1/toolroom/execute` | Execute a checked-out tool (v4.6.0CC) | Requires checkout |

---

## Capability Profile

```python
"foreman_agent": [
    "filesystem.read:/app/toolroom/*",
    "filesystem.write:/app/toolroom/tools/*",
    "filesystem.read:/data/*",
    "external.read:github.com",
    "external.read:api.github.com",
    "external.read:raw.githubusercontent.com",
    "agent.execute:*",
    "redis.read:toolroom:*",
    "redis.write:toolroom:*",
]
```

---

## QMS Reference

| Message | Meaning |
|---|---|
| `Foreman_Daily_Update_Please` | Trigger daily update check |
| `Foreman_Checkout_Tool_Please ::agent:: ::tool::` | Agent requests tool |
| `Tool_Checkout_Thank_You ::CHKOUT-xxxxx::` | Checkout successful |
| `Tool_Checkout_Thank_You_But_No ::reason::` | Checkout denied |
| `Tool_Execute_Please ::tool_id::` | Agent executes checked-out tool (v4.6.0CC) |
| `Tool_Execute_Thank_You ::tool_id::` | Execution successful |
| `Tool_Execute_Thank_You_But_No ::reason::` | Execution failed |
| `Foreman_API_Access_Required_Pretty_Please ::reason::` | HITL gate triggered |
| `Foreman_Install_Tool_Please ::source::` | Propose tool install |
| `Foreman_Install_Execute_Thank_You ::tool_id::` | Post-approval install complete |
| `New_Tool_Request_Please ::desc:: from @@agent@@` | Agent wants new tool |
| `Toolroom_Status_Please` | Get full status report |
| `Sync_Function_Tools_Please` | Sync function tools to registry |
| `Tool_Manifest_Validate_Please` | Validate manifest on install |
| `Register_Function_Tool_Please` | Register in-house function tool |
| `Approval_Status_Check_Please ::request_id::` | Check approval in Redis |

---

## Test Coverage (v4.6.0CC)

129 toolroom tests, 201 total suite. All passing.

| Test Class | Count | Coverage |
|---|---|---|
| TestToolMetadata | 6 | ToolMetadata creation, defaults, round-trip |
| TestToolRegistry | 12 | Register, get, list, categories, status, persistence |
| TestToolCheckout | 12 | Checkout, return, active checkouts, audit |
| TestToolRequest | 6 | Submit, get, list pending |
| TestForemanCheckout | 8 | Auth, trust levels, API gate, approval |
| TestForemanReturn | 3 | Return success, not found |
| TestForemanDailyCheck | 5 | Update detection, approved source validation |
| TestForemanInstall | 7 | Propose, execute, approval verification |
| TestForemanUpload | 3 | Upload registration, path validation |
| TestToolroomEndpoints (GET/POST) | 21 | All endpoints, auth, validation |
| TestToolManifest | 5 | Creation, defaults, round-trip, unknown fields |
| TestManifestValidation | 10 | Required fields, injection, sandbox, timeout |
| TestManifestFileLoading | 5 | Load from disk, missing, invalid |
| TestFunctionToolRegistry | 7 | Register, get, list, unregister |
| TestRegisterFunctionToolDecorator | 2 | Decorator behavior |
| TestExecutionResult | 2 | Success/failure results |
| TestFunctionToolExecution | 4 | Execute, return types, exceptions |
| TestApprovalStatusLookup | 4 | In-memory, completed, not found, dict format |
| TestSemanticVersionComparison | 7 | Newer, v-prefix, same, older, prerelease, patch |
| TestToolroomExecuteEndpoint | 3 | Auth, validation, no-checkout |
| TestForemanExecution | 4 | No checkout, function tool, no manifest, sync |
| TestToolMetadataV460 | 5 | manifest_data, execution_type fields |

---

## Version History

| Version | What Changed |
|---|---|
| 4.4.0CC | Initial Toolroom + Foreman: registry, checkout/return, HITL gates, daily updates |
| 4.5.0CC | Prefixed IDs (CHKOUT-, TOOLREQ-, APPR-), 13 API endpoints, 140 tests |
| 4.6.0CC | Execution engine: manifests, subprocess isolation, function tools, semantic versioning, Redis-backed approval lookup. 129 toolroom tests, 201 total suite |
