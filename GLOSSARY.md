# TelsonBase Glossary

Definitions of key terms used throughout TelsonBase documentation and code.

---

## A

### Agent
A software component that performs tasks autonomously. In TelsonBase, agents are isolated, capability-restricted, and cryptographically verified. Each agent has a trust level, declared capabilities, and a signed identity.

### Agent Trust Level
Progression system for agent permissions: `QUARANTINE` (new/untrusted) → `PROBATION` (limited) → `RESIDENT` (standard) → `CITIZEN` (full trust). Higher trust unlocks more tool access and capabilities. See `core/trust_levels.py`.

### Alien
Code or frameworks from external sources (LangChain, AutoGPT, etc.) that haven't been verified against TelsonBase security standards. Aliens run in quarantine with restricted capabilities. See `agents/alien_adapter.py`.

### Anomaly Detection
Behavioral monitoring that establishes baselines for agent activity and flags deviations. Triggers include unusual request rates, unexpected capability usage, or out-of-hours activity. See `core/anomaly.py`.

### API Key Registry
Redis-backed multi-key authentication system (v5.3.0CC). Supports multiple API keys with per-key scoped permissions, labels, and zero-downtime rotation. Keys are SHA-256 hashed before storage. See `core/auth.py`.

### Approval Gate
A checkpoint requiring human authorization before sensitive operations proceed. Configured per-capability with timeout and escalation rules. See `core/approval.py`.

### Approved Sources
GitHub repositories whitelisted for tool installation. Runtime-managed via Redis with API endpoints for add/remove. The Foreman can only pull tools from these repos. See `APPROVED_GITHUB_SOURCES` in `toolroom/foreman.py`.

### Audit Event
A logged security event with structured metadata. Types include: `SYSTEM_STARTUP`, `AUTH_TOKEN_ISSUED`, `AUTH_FAILURE`, `SECURITY_ALERT`, `AGENT_ACTION`, `FEDERATION_EVENT`, `TOOL_CHECKOUT`, `TOOL_REGISTERED`, `TOOL_UPDATE`, `TOOL_QUARANTINED`, `TOOL_HITL_GATE`, `TOOL_REQUEST`.

### Audit Chain
SHA-256 hash-chained audit log entries. Each entry includes the hash of the previous entry, creating a tamper-evident chain. See `core/audit.py`.

---

## B

### Baseline (Behavioral)
Statistical profile of an agent's normal operation patterns. Used by anomaly detection to identify suspicious behavior.

---

## C

### Cage
The secured archive within the toolroom where copies of all installed tools are stored for compliance and provenance tracking. Every tool installation, update, and rollback creates a timestamped cage receipt. Named after the locked cage in physical production toolrooms. See `toolroom/cage.py`.

### Cage Receipt
Provenance record created when a tool is archived in the cage. Contains: tool ID, version, SHA-256 hash, source, who approved it, approval request ID, timestamp. ID format: `CAGE-{uuid}`.

### Capability
A specific permission granted to an agent. Format: `resource.action:scope` (e.g., `filesystem.read:/data/*`, `external.none`). Deny rules (prefixed with `!`) take precedence over allow rules. See `core/capabilities.py`.

### Celery
Distributed task queue used for background processing. The Foreman's daily update checks, tool installations, and other async operations run as Celery tasks with Redis as the broker.

### Checkout
The process of an agent borrowing a tool from the toolroom. Creates a `ToolCheckout` record with a prefixed ID (`CHKOUT-{uuid}`). Subprocess tools have exclusive checkout (one agent at a time). See `toolroom/registry.py`.

### Circuit Breaker
Protection mechanism that stops requests to a failing service after repeated failures. Prevents cascade failures across the system. See `core/middleware.py`.

### Compliance Export
Ability to export audit logs, approval decisions, and security events in structured format for regulatory review. See `core/rbac.py`.

### Correlation Block
QMS v2.1.6 element (`::@@REQ_id@@::`) that links request to response. Mandatory position 2 in every QMS chain. Enables `grep @@REQ_id@@` to thread a complete conversation.

---

## D

### Data Sovereignty
The principle that data should remain under the owner's control, on hardware they own, without dependency on external cloud services.

### Delegation
Capability delegation system where one agent (grantor) can delegate a subset of its own capabilities to another agent (grantee). Supports expiry, revocation, and cascading (children expire with parent). Redis-persisted. See `core/delegation.py`.

---

## E

### Egress Gateway
Secure proxy that controls all outbound network traffic from agents. Enforces domain whitelisting — only pre-approved external APIs can be reached. See `gateway/egress_proxy.py`.

### Egress Whitelist
List of approved external domains agents can contact. Configured in `core/config.py` via `ALLOWED_EXTERNAL_DOMAINS`.

### Exclusive Checkout
Constraint (v5.4.0CC) preventing multiple agents from checking out the same subprocess tool simultaneously. Prevents disk-level conflicts. Function tools (stateless) are exempt.

---

## F

### Federation
Protocol allowing multiple TelsonBase instances to establish trust relationships and securely exchange messages across organizational boundaries. Uses RSA-4096 keypairs and mTLS. See `federation/trust.py`.

### Federation Invitation
Cryptographic token (RSA-4096 signed) used to initiate trust between TelsonBase instances. Contains instance identity, public key, and trust parameters.

### Foreman
Supervisor-level agent managing the Toolroom. The only agent permitted to access GitHub repositories. All tool installations, updates, and external access go through the Foreman with HITL approval. See `toolroom/foreman.py`.

### Function Tool
A Python function registered via `@register_function_tool` decorator for in-process execution. No subprocess overhead. Auto-generates a manifest from the function signature. See `toolroom/function_tools.py`.

---

## H

### HMAC-SHA256
Hash-based Message Authentication Code using SHA-256. Used for signing agent messages to ensure integrity and authenticity.

### Human-in-the-Loop (HITL)
Design pattern where critical operations require explicit human approval before execution. In TelsonBase, ALL external API access triggers HITL — no exceptions. Implemented via approval gates.

---

## I

### Instance ID
Unique identifier for a TelsonBase deployment. Used in federation to distinguish between trusted instances.

---

## J

### JWT (JSON Web Token)
Token format used for API authentication. Contains claims (user identity, permissions, `jti` for revocation) signed with the instance's secret key. Supports revocation via Redis-backed revocation list (v5.3.0CC).

---

## M

### MCP (Model Context Protocol)
Standard protocol for AI model communication. TelsonBase uses MCP-compatible message structures for agent interactions.

### Manifest (Tool)
JSON file (`tool_manifest.json`) that defines a tool's execution contract: entry point, inputs, outputs, sandbox level, timeout, dependencies. Required for tool installation (v5.4.0CC). See `toolroom/manifest.py`.

### MQTT Bus
Agent-to-agent communication system using Mosquitto. Topic structure: `telsonbase/agents/{id}/inbox` (direct), `telsonbase/broadcast/all` (system-wide). Messages use QMS format. See `core/mqtt_bus.py`.

---

## O

### Ollama
Local LLM inference engine. TelsonBase runs Ollama in Docker for sovereign AI — all inference happens on your hardware. Accessed via `core/ollama_service.py` and the `agents/ollama_agent.py` wrapper.

### Origin Block
QMS v2.1.6 element (`::<agent_id>::`) identifying the sending agent. Mandatory position 1 in every QMS chain — the "radio callsign." Missing origin = anonymous transmission = security alert.

---

## P

### Pinch Point
Architectural term for a controlled bottleneck where all access must flow through a single, auditable mechanism. QMS and the Toolroom are pinch points by design — built tight with the ability to loosen.

### Prefixed ID
Identifier format used throughout the toolroom for QMS parseability: `CHKOUT-{uuid}` (checkouts), `TOOLREQ-{uuid}` (tool requests), `APPR-{uuid}` (approvals), `CAGE-{uuid}` (cage receipts).

---

## Q

### QMS (Qualified Message Standard)
TelsonBase's internal messaging convention (v2.1.6) that embeds human-readable semantics into agent communications. Uses suffixes (`_Please`, `_Thank_You`, etc.), field markers (`::value::`), and formal chain syntax. See `core/qms.py` and `QMS_SPECIFICATION.md`.

### QMS Chain
Structured message format: `::origin::-::@@correlation@@::-::action::-::data::`. Supports halt postscript (`::%%%%::-::%%reason%%::`) for emergency stops.

### QMS Suffixes
| Suffix | Meaning |
|--------|---------|
| `_Please` | Request initiation |
| `_Thank_You` | Successful completion |
| `_Thank_You_But_No` | Failed with explanation |
| `_Excuse_Me` | Needs clarification |
| `_Pretty_Please` | High priority / escalation |

### Quarantine
Lowest trust level for agents. Quarantined agents have minimal capabilities and enhanced monitoring. Also: the restricted execution environment for unverified external code (aliens).

---

## R

### Rate Limiting
Control mechanism restricting request frequency per client/agent. Supports per-agent trust-based limits. Includes stale bucket cleanup (v5.2.1CC). See `core/middleware.py`.

### RBAC (Role-Based Access Control)
Permission system for human operators. Roles define what API endpoints and operations a user can access. See `core/rbac.py`.

### REM Comment
Documentation comment style (`# REM:`) used in TelsonBase to explain architectural decisions and security rationale. Named after the BASIC language remark statement.

### Rollback (Tool)
Ability (v5.4.0CC) to revert a tool to a previous version from its version history. Updates registry metadata. See `ToolRegistry.rollback_tool()` in `toolroom/registry.py`.

### RSA-4096
Asymmetric encryption algorithm used for federation trust establishment. Each instance generates a keypair for signing invitations and messages.

---

## S

### Sandbox Level
Tool execution isolation level: `none` (in-process function), `subprocess` (scoped env, restricted PATH), `container` (future: Docker per-execution). See `toolroom/manifest.py`.

### Secret Rotation
Managed rotation of cryptographic secrets (JWT keys, API keys, encryption keys) with grace periods allowing the old secret to remain valid temporarily. See `core/config.py`.

### Signing Key
Cryptographic key used to sign agent messages. Per-agent keys stored in Redis. See `core/signing.py`.

### Signing Service
Component (`core/signing.py`) that handles message signing and verification using HMAC-SHA256. Includes key revocation mechanism with audit trail.

### Sovereign Score
0-100 metric measuring how independent a TelsonBase instance is from external services. Factors: LLM locality (35%), data residency (25%), network exposure (20%), backup sovereignty (10%), auth posture (10%).

---

## T

### Toolroom
Centralized tool management system. Agents access tools exclusively through the toolroom via the Foreman. Includes: registry (inventory), checkout/return system, cage (archive), execution engine, and update management. See `toolroom/` directory.

### Tool Registry
Master inventory of all tools available to agents. Tracks metadata, status, active checkouts, usage history, and version history. Redis-persisted. See `toolroom/registry.py`.

### Trust Level (Agent)
See **Agent Trust Level**.

### Trust Level (Federation)
Federation parameter indicating the degree of trust between instances. Levels: `MINIMAL`, `STANDARD`, `ELEVATED`, `FULL`.

### Trust Relationship
Established connection between two TelsonBase instances allowing secure message exchange. Created via invitation/acceptance protocol.

---

## V

### Version History
Per-tool record (v5.4.0CC) of previous version snapshots stored in `ToolMetadata.version_history`. Capped at 10 entries. Enables rollback. Each entry stores: version, SHA-256 hash, install date, source.

---

## Z

### Zero-Trust
Security model where no agent, message, or request is trusted by default. Every interaction requires cryptographic verification regardless of source.

---

## Version Suffixes

| Suffix | Meaning |
|--------|---------|
| `G` | Gemini save/contribution |
| `C` | Claude save/contribution |
| `CC` | Claude Code save/contribution |

---

*For detailed technical documentation, see `docs/SECURITY_ARCHITECTURE.md` and `docs/DEVELOPER_GUIDE.md`.*
