# TelsonBase Toolroom
**Version:** v11.0.1

---

## What Is the Toolroom?

The Toolroom is the **single source of truth** for all tools available to agents on base. Think of it as a machine shop tool crib - nothing leaves without being signed out, nothing returns without being inspected, and one supervisor (the Foreman) manages everything.

**Core principle:** All agents draw from the same Toolroom. No agent accesses external tools directly. No shadow tooling.

---

**Tool access by trust tier:** See [`docs/TOOLROOM_TRUST_MATRIX.md`](../docs/System%20Documents/TOOLROOM_TRUST_MATRIX.md) for the full matrix - what's available at each tier, how to set tool designations, and recommended defaults by tool category.

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

### QMS™ as Security Gate

The Foreman validates QMS™ formatting on every incoming message before processing it. A non-QMS message reaching the Foreman is not treated as a malformed request - it is treated as a security event.

Every valid inbound message must arrive as a proper QMS™ chain:

```
::agent_id::-::@@correlation_id@@::-::action::-::data::-::_command::
```

If the Foreman receives a message without this structure, it logs a `NON_QMS_MESSAGE` anomaly event and does not execute the request. The origin block is the identity check. The correlation block is the audit thread. The command block is the intent. A message missing any of these is missing accountability - and the Foreman does not work with unaccountable inputs.

This also means silence is a signal. A registered agent that stops producing QMS™-formatted messages is as anomalous as one sending malformed messages. The behavioral baseline tracks both.

### Security Constraints

- **GitHub access ONLY** - the Foreman can only pull from explicitly approved repositories listed in `APPROVED_GITHUB_SOURCES`
- **HITL gate on ALL external operations** - the Foreman will notify the human operator and **wait for explicit authorization** before any install, update, or API-access operation
- **Cannot modify its own capabilities** - defense-in-depth
- **All actions audited** - hash-chained audit logs via `core/audit.py`
- **Approval state persisted in Redis** - survives worker restarts

---

## How Agents Use the Toolroom

All Foreman interactions use QMS™ chains. The origin block is the agent's registered ID. The correlation block links request to response. The command block signals intent. Every chain ends with `::`.

### 1. Checking Out a Tool

Request:
```
::agent_id::-::@@TOOLREQ-xxxxx@@::-::Checkout_Tool::-::##tool_id##::-::_Please::
```

Foreman checks: tool exists, agent authorized, trust level met, API access required (HITL gate if yes).

Success response:
```
::foreman::-::@@TOOLREQ-xxxxx@@::-::Checkout_Granted::-::##CHKOUT-xxxxx##::-::_Thank_You::
```

Denied response:
```
::foreman::-::@@TOOLREQ-xxxxx@@::-::Checkout_Denied::-::##reason##::-::_Thank_You_But_No::
```

### 2. Executing a Tool

After checkout, agents execute through the Foreman:

Request:
```
::agent_id::-::@@EXEC-xxxxx@@::-::Execute_Tool::-::##tool_id##::-::##CHKOUT-xxxxx##::-::_Please::
```

Foreman verifies active checkout, routes to function or subprocess execution, logs result.

Success response:
```
::foreman::-::@@EXEC-xxxxx@@::-::Execution_Complete::-::##output##::-::_Thank_You::
```

Failure response:
```
::foreman::-::@@EXEC-xxxxx@@::-::Execution_Failed::-::##reason##::-::_Thank_You_But_No::
```

**Subprocess tools** run with: scoped environment, restricted PATH, timeout enforcement, and unprivileged execution context.

**Function tools** run as direct Python callables with timeout protection and exception isolation.

### 3. Returning a Tool

```
::agent_id::-::@@RET-xxxxx@@::-::Return_Tool::-::##CHKOUT-xxxxx##::-::_Thank_You::
```

Foreman acknowledges:
```
::foreman::-::@@RET-xxxxx@@::-::Tool_Returned::-::##CHKOUT-xxxxx##::-::_Thank_You::
```

### 4. Requesting a New Tool

Agents use `::_Pretty_Please::` for escalation - this signals urgency to the HITL queue:

```
::agent_id::-::@@TOOLREQ-xxxxx@@::-::New_Tool_Needed::-::##description##::-::_Pretty_Please::
```

Foreman routes to HITL and waits for human decision.

### 5. HITL Gate Triggered

When the Foreman must escalate to a human, it uses `::_Pretty_Please::` to signal the approval request:

```
::foreman::-::@@HITL-xxxxx@@::-::API_Access_Required::-::##reason##::-::_Pretty_Please::
```

---

## Tool Manifest

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
- `timeout_seconds` must be 1-3600
- `requires_network` without sandbox generates a warning

Tools installed without a manifest are registered but **cannot be executed** until a manifest is provided.

---

## Function Tools

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
- Execute as direct callables - no subprocess overhead
- Have timeout protection and exception isolation

---

## Uploading Git-Cloned Tools

The human operator can install tools from approved GitHub repos:

1. **Propose** - creates HITL approval request:
```bash
docker compose exec worker celery -A celery_app.worker call \
  foreman_agent.propose_tool_install \
  --args='["dbcli/pgcli", "pgcli", "PostgreSQL CLI", "database", false]'
```

2. **Approve** - human approves via approval API

3. **Execute install** - after approval:
```bash
docker compose exec worker celery -A celery_app.worker call \
  foreman_agent.execute_tool_install \
  --args='["dbcli/pgcli", "pgcli", "PostgreSQL CLI", "database", "latest", false, "operator", "APPR-xxxxx"]'
```

Or register a manually uploaded tool:

```bash
docker compose exec worker celery -A celery_app.worker call \
  foreman_agent.register_uploaded_tool \
  --args='["sqlite_tools", "SQLite CLI", "database", "/app/toolroom/tools/tool_sqlite", "3.45.0", false]'
```

---

## Daily Update Cycle

The Foreman runs a daily update check via Celery Beat:

1. **Check** - queries GitHub API for each tool's source repo
2. **Compare** - uses semantic versioning (`packaging.version.parse`) to detect actual version changes. Handles `v` prefixes, pre-release tags, and patch increments correctly.
3. **Propose** - if updates found, creates proposals for HITL review
4. **Wait** - does NOT auto-install. Human must approve each update
5. **Install** - after HITL approval, Foreman pulls update and verifies integrity (SHA-256)

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
├── manifest.py          # Tool manifest schema and validation
├── executor.py          # Subprocess and function execution engine
├── function_tools.py    # @register_function_tool decorator system
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
| `foreman_agent.execute_tool` | Agent request | Requires active checkout |
| `foreman_agent.sync_function_tools` | Startup/on-demand | No |

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
| `POST /v1/toolroom/execute` | Execute a checked-out tool | Requires checkout |

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

## QMS™ Reference

All Foreman messages follow QMS™ chain format. The grammar:
- Blocks delimited by `::...::`, linked by `-` separators: `::BLOCK::-::BLOCK::`
- Leading `_` marks connector/command words (`::_Thank_You::`) - words *about* the transaction
- No leading `_` marks action/data words (`::Checkout_Tool::`) - words *in* the transaction
- Internal `_` is a word separator (`::New_Tool_Needed::`)
- Every valid chain ends with `::`

| Operation | QMS™ Chain |
|---|---|
| Checkout request | `::agent::-::@@TOOLREQ-xxxxx@@::-::Checkout_Tool::-::##tool_id##::-::_Please::` |
| Checkout granted | `::foreman::-::@@TOOLREQ-xxxxx@@::-::Checkout_Granted::-::##CHKOUT-xxxxx##::-::_Thank_You::` |
| Checkout denied | `::foreman::-::@@TOOLREQ-xxxxx@@::-::Checkout_Denied::-::##reason##::-::_Thank_You_But_No::` |
| Execute request | `::agent::-::@@EXEC-xxxxx@@::-::Execute_Tool::-::##tool_id##::-::##CHKOUT-xxxxx##::-::_Please::` |
| Execution success | `::foreman::-::@@EXEC-xxxxx@@::-::Execution_Complete::-::##output##::-::_Thank_You::` |
| Execution failed | `::foreman::-::@@EXEC-xxxxx@@::-::Execution_Failed::-::##reason##::-::_Thank_You_But_No::` |
| Return tool | `::agent::-::@@RET-xxxxx@@::-::Return_Tool::-::##CHKOUT-xxxxx##::-::_Thank_You::` |
| New tool request | `::agent::-::@@TOOLREQ-xxxxx@@::-::New_Tool_Needed::-::##description##::-::_Pretty_Please::` |
| HITL gate raised | `::foreman::-::@@HITL-xxxxx@@::-::API_Access_Required::-::##reason##::-::_Pretty_Please::` |
| Daily update check | `::foreman::-::@@SCHED-xxxxx@@::-::Daily_Update_Check::-::_Please::` |
| Sync function tools | `::foreman::-::@@SYNC-xxxxx@@::-::Sync_Function_Tools::-::_Please::` |
| Toolroom status | `::agent::-::@@STAT-xxxxx@@::-::Toolroom_Status::-::_Please::` |

Non-QMS messages received by the Foreman are rejected and logged as `NON_QMS_MESSAGE` anomaly events before any processing occurs.

---

## Test Coverage

129 toolroom tests. All passing.

| Test Class | Count | Coverage |
|---|---|---|
| TestToolMetadata | 3 | ToolMetadata construction, defaults, round-trip |
| TestToolCheckout | 2 | ToolCheckout creation and round-trip |
| TestToolRegistry | 11 | Register, list, checkout, return, request tools; active checkout filtering |
| TestTrustLevelNormalization | 6 | Lowercase, uppercase, mixed-case, and cross-tier trust level strings |
| TestForemanCheckout | 5 | Auth by trust level, HITL trigger for API-access tools |
| TestForemanInstall | 4 | Unapproved source rejection, approval creation, approval validation |
| TestToolroomStore | 4 | Singleton existence, required methods, get_store helper |
| TestCeleryConfiguration | 3 | Foreman in Celery include, daily update beat schedule, task routing |
| TestToolroomAPI | 8 | Status, list tools, get tool, checkouts, history, requests, usage report via REST |
| TestApprovalIntegration | 2 | Approval rule registration and config |
| TestToolroomPostCheckout | 4 | POST /checkout auth and response |
| TestToolroomPostReturn | 3 | POST /return and checkout release |
| TestToolroomPostInstallPropose | 4 | POST /install/propose source validation and approval creation |
| TestToolroomPostInstallExecute | 2 | POST /install/execute approval enforcement |
| TestToolroomPostRequest | 4 | POST /request unapproved tool flow |
| TestToolroomPostApiCheckoutComplete | 3 | POST /checkout/complete HITL completion |
| TestToolManifest | 5 | Manifest structure, defaults, round-trip, JSON round-trip, unknown fields |
| TestManifestValidation | 13 | Required fields, injection prevention, sandbox level, timeout range, network warning |
| TestManifestFileLoading | 5 | Load from file, missing directory, missing manifest, invalid JSON, invalid manifest |
| TestFunctionToolRegistry | 7 | Register, auto-manifest, get by name, list, unregister, unregister nonexistent |
| TestRegisterFunctionToolDecorator | 2 | Decorator registers with metadata and preserves callable |
| TestExecutionResult | 2 | Success/failure result construction |
| TestFunctionToolExecution | 4 | Execute: success, string return, None return, exception isolation |
| TestApprovalStatusLookup | 4 | Pending, completed, not found, dict format |
| TestSemanticVersionComparison | 7 | Newer, v-prefix, same, older, prerelease, v-prefix vs no-prefix, patch increment |
| TestToolroomExecuteEndpoint | 3 | POST /execute auth, payload validation, no-checkout error |
| TestForemanExecution | 4 | No checkout fails, function tool execution, no manifest fails, sync function tools |
| TestToolMetadataV460 | 5 | manifest_data field, manifest_data default, execution_type field, execution_type default, round-trip |

---

## Version History

| Version | What Changed |
|---|---|
| 4.4.0CC | Initial Toolroom + Foreman: registry, checkout/return, HITL gates, daily updates |
| 4.5.0CC | Prefixed IDs (CHKOUT-, TOOLREQ-, APPR-), 13 API endpoints, 140 tests |
| 4.6.0CC | Execution engine: manifests, subprocess isolation, function tools, semantic versioning, Redis-backed approval lookup |
| v11.0.1 | QMS™ validation as Foreman security gate, updated chain syntax throughout |

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
