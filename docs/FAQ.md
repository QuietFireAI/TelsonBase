# TelsonBase — Frequently Asked Questions

**Version:** 9.0.0B
**Maintained by:** Quietfire AI — support@telsonbase.com

Every answer here traces to source code. Where a verification command exists, it's provided.
The same standard applies here as in the proof sheets — no claim without a source.

---

## Table of Contents

1. [How do you add an agent?](#1-how-do-you-add-an-agent)
2. [How do agents communicate with each other?](#2-how-do-agents-communicate-with-each-other)
3. [How does an agent get access to a tool?](#3-how-does-an-agent-get-access-to-a-tool)
4. [What happens when an agent is blocked from an action?](#4-what-happens-when-an-agent-is-blocked-from-an-action)
5. [Can an operator reach a restricted agent?](#5-can-an-operator-reach-a-restricted-agent)
6. [What governs inbound communications from unknown sources?](#6-what-governs-inbound-communications-from-unknown-sources)
7. [What happens when an audit chain verification fails?](#7-what-happens-when-an-audit-chain-verification-fails)
8. [Can TelsonBase track token usage for external API calls?](#8-can-telsonbase-track-token-usage-for-external-api-calls)
9. [How does TelsonBase respond to security attacks?](#9-how-does-telsonbase-respond-to-security-attacks)
10. [Is TelsonBase MCP compatible?](#10-is-telsonbase-mcp-compatible)
11. [Can Android or iOS apps communicate with TelsonBase?](#11-can-android-or-ios-apps-communicate-with-telsonbase)
12. [Does TelsonBase communicate with Anthropic, Venice.ai, or external AI providers?](#12-does-telsonbase-communicate-with-anthropic-veniceai-or-external-ai-providers)
13. [Is TelsonBase HIPAA, SOC 2, or HITRUST compliant?](#13-is-telsonbase-hipaa-soc-2-or-hitrust-compliant)
14. [Has TelsonBase been independently audited or pen tested?](#14-has-telsonbase-been-independently-audited-or-pen-tested)
15. [Who built this and why should I trust a solo developer?](#15-who-built-this-and-why-should-i-trust-a-solo-developer)
16. [What happens if the developer stops maintaining it?](#16-what-happens-if-the-developer-stops-maintaining-it)
17. [Can TelsonBase scale beyond a single machine?](#17-can-telsonbase-scale-beyond-a-single-machine)
18. [What AI models does TelsonBase support?](#18-what-ai-models-does-telsonbase-support)
19. [What is the license and what can I do with TelsonBase?](#19-what-is-the-license-and-what-can-i-do-with-telsonbase)
20. [What are the performance characteristics?](#20-what-are-the-performance-characteristics)

---

## 1. How do you add an agent?

**Plain answer:**
Two ways. An agent can self-register the moment it makes its first request through the MCP
gateway — TelsonBase intercepts it, assigns an instance ID, and places it in QUARANTINE
automatically. Or an operator pre-registers an agent through the dashboard before it ever
connects, using the Register Agent button in the Agents tab.

Either way, every agent always starts at QUARANTINE with zero autonomous permissions.
No exceptions. No shortcuts.

**Source files:**
- `core/openclaw.py` — `register_instance()` — registration logic
- `api/openclaw_routes.py` — `POST /v1/openclaw/register` — API endpoint
- `frontend/index.html` — `RegisterAgentModal` component — dashboard UI

**Verification:**
```bash
# Register an agent via API
curl -X POST http://localhost:8000/v1/openclaw/register \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"instance_id":"test-001","name":"test_agent","capabilities":["read_file"]}'

# Confirm it landed in quarantine
curl http://localhost:8000/v1/openclaw/instances/test-001 \
  -H "X-API-Key: $API_KEY"
# trust_level should be "quarantine"
```

**Skeptic follow-up:** *"What stops someone from registering a rogue agent?"*
Nonce replay protection and API key authentication are required on every action evaluation.
An unregistered agent is rejected at Step 1 of the 8-step governance pipeline before any
action is processed. See `core/openclaw.py` — `evaluate_action()`.

---

## 2. How do agents communicate with each other?

**Plain answer:**
Through MQTT via the Mosquitto message bus built into the stack. Every message is wrapped
in QMS (Qualified Message Standard), which stamps it with provenance — who sent it, what
it contained, and when. That record is hash-linked into the audit chain. No agent-to-agent
communication happens outside the bus. TelsonBase's MCP gateway acts as the intermediary —
agents don't talk directly to each other, they communicate through TelsonBase, which mediates
and logs everything.

**Source files:**
- `core/mqtt_bus.py` — MQTT message bus
- `core/qms.py` — QMS message wrapping and provenance
- `api/mcp_gateway.py` — MCP intermediary layer

**Verification:**
```bash
# Check MQTT bus status
curl http://localhost:8000/v1/system/status \
  -H "X-API-Key: $API_KEY" | python -m json.tool | grep mosquitto
```

**Skeptic follow-up:** *"OpenClaw agents don't natively speak MQTT — how does this work?"*
Correct. TelsonBase's MCP gateway is the communication layer. Agents interact with
TelsonBase's governance layer via MCP. TelsonBase routes, mediates, and logs. The agent
never communicates directly — it communicates through the governed proxy.

---

## 3. How does an agent get access to a tool?

**Plain answer:**
Through the Toolroom. An agent requests a tool; it enters the Approvals queue where a human
operator approves or rejects it. Every tool is pre-categorized — read, write, external,
financial, destructive — and those categories map directly to trust tier requirements.
A QUARANTINE agent cannot autonomously use any tool. A CITIZEN agent can use pre-approved
tools autonomously. The trust tier determines the threshold; the operator controls promotion.

**Source files:**
- `core/approval.py` — approval gate logic
- `api/toolroom` (routes in `main.py`) — Toolroom endpoints
- `core/openclaw.py` — `TOOL_CATEGORY_MAP` — tool-to-category mapping
- `frontend/index.html` — `ToolroomTab` component

**Verification:**
```bash
# List available tools in the Toolroom
curl http://localhost:8000/v1/toolroom/tools \
  -H "X-API-Key: $API_KEY"

# List pending approval requests
curl http://localhost:8000/v1/approval/requests \
  -H "X-API-Key: $API_KEY"
```

**Skeptic follow-up:** *"Can an agent claim a tool it already has access to without re-evaluation?"*
No. Every tool call passes through the 8-step governance pipeline regardless of prior
approvals. Trust level is re-evaluated on every single action in real time.

---

## 4. What happens when an agent is blocked from an action?

**Plain answer:**
Three outcomes, depending on severity:

1. **Blocked** — Action rejected immediately. Audit logged. Agent receives a rejection
   response and continues running. No interruption to the agent process itself.

2. **Gated** — Action queued as a human approval request with an APPR- prefixed ID.
   Visible in the dashboard Approvals tab with full payload and context. Agent waits.
   Operator approves or rejects.

3. **Auto-demoted** — If the agent's Manners compliance score drops below 50%, it is
   immediately demoted to QUARANTINE with no human delay and no grace period. The action
   that triggered the evaluation is already affected. The agent remains registered but
   cannot take any autonomous action until reinstated by a human operator.

The kill switch is a fourth path: one API call suspends any agent instantly. All subsequent
actions are rejected at Step 2 of the pipeline — before trust levels, before Manners,
before everything except "does this agent exist?"

**Source files:**
- `core/openclaw.py` — `evaluate_action()` — 8-step pipeline
- `core/openclaw.py` — `_check_manners_compliance()` — auto-demotion logic
- `api/openclaw_routes.py` — `POST /v1/openclaw/kill-switch/{instance_id}`

**Verification:**
```bash
# Trigger the kill switch on an agent
curl -X POST http://localhost:8000/v1/openclaw/kill-switch/test-001 \
  -H "X-API-Key: $API_KEY"

# Attempt an action — should be rejected at Step 2
curl -X POST http://localhost:8000/v1/openclaw/evaluate \
  -H "X-API-Key: $API_KEY" \
  -d '{"instance_id":"test-001","tool":"read_file","nonce":"abc123"}'
# response: blocked, reason: agent_suspended
```

See also: `proof_sheets/TB-PROOF-037_openclaw_kill_switch.md`

**Skeptic follow-up:** *"What if the agent retries the blocked action repeatedly?"*
Anomaly detection flags repetitive blocked actions as a behavioral deviation. Rate limiting
fires at 300 requests per minute. Repeated violations accumulate in the Manners score.

---

## 5. Can an operator reach a restricted agent?

**Plain answer:**
Yes. Restrictions govern what an agent can initiate outbound. The operator-to-agent
communication channel through the MCP gateway is always open — you can always send
instructions to a restricted or suspended agent. The agent can respond back through
TelsonBase. What it cannot do is make outbound calls on its own initiative.
Inbound and outbound are governed independently.

**Source files:**
- `api/mcp_gateway.py` — operator→agent instruction path
- `core/openclaw.py` — outbound action evaluation (separate from inbound channel)

**Verification:**
```bash
# Operator sends instruction via MCP gateway even to a suspended agent
# Connect via Goose or Claude Desktop pointed at http://localhost:8000/mcp
# Governance restriction affects agent-initiated actions, not operator-initiated contact
```

---

## 6. What governs inbound communications from unknown sources?

**Plain answer:**
All inbound connections to TelsonBase require Bearer token or X-API-Key authentication.
Unknown connections receive a 401 before they reach any protected resource. The MCP gateway
validates instance ID and a cryptographic nonce on every action evaluation — replayed nonces
are rejected at Step 3 of the pipeline. Rate limiting fires at 300 requests per minute
with a burst allowance of 60. All connection attempts are logged to the audit chain.
An unrecognized OpenClaw instance is rejected at Step 1 — not registered, full stop.

**Source files:**
- `core/auth.py` — authentication layer
- `core/middleware.py` — rate limiting (token bucket)
- `core/openclaw.py` — nonce replay protection (Step 3 of pipeline)
- `api/openclaw_routes.py` — instance registration check (Step 1)

**Verification:**
```bash
# Attempt connection without authentication
curl http://localhost:8000/v1/system/status
# Expected: 401 Unauthorized

# Attempt with replayed nonce (second call with same nonce)
# Expected: rejected at Step 3 — nonce_already_used
```

---

## 7. What happens when an audit chain verification fails?

**Plain answer:**
Two distinct failure types with different meanings:

- **chain_break** — A gap in sequence numbers from a container restart or Redis flush.
  This is a documented boundary event, not a security incident. The chain continues from
  a new genesis hash. Prior entries before the break are unaffected.

- **hash_mismatch** — An entry's stored hash does not match the recomputed hash of its
  content. This means an entry was modified after it was written. This is a security alert.
  It is flagged in the dashboard, logged, and the chain is considered compromised at that
  point forward.

Because each entry's hash includes the previous entry's hash, tampering with any single
entry invalidates every subsequent entry in the chain. Tampering cannot be hidden — it
can only be detected.

**Source files:**
- `core/audit.py` — `verify_chain()` — full verification loop (line ~525)
- `core/audit.py` — `_create_chain_entry()` — SHA-256 hash computation
- `frontend/index.html` — Verify Chain button and result banner

**Verification:**
```bash
# Verify the current chain from the API
curl -X POST http://localhost:8000/v1/audit/verify \
  -H "Authorization: Bearer $TOKEN"
# Returns: verified=true, entry_count, or hash_mismatch with sequence number
```

See also: `proof_sheets/TB-PROOF-004_audit_chain_integrity.md`

**Skeptic follow-up:** *"What if someone flushes Redis?"*
Redis flush = chain_state lost, new genesis starts. This is a known architectural limit,
documented in `docs/TECHNICAL_DEFENSE_BRIEF.md`. PostgreSQL archival for entries beyond
100K is on the roadmap. A flush is detectable as an unusually early genesis in the chain
history. Physical access to flush Redis is itself a security event — outside TelsonBase's
threat model (assumes secure infrastructure).

---

## 8. Can TelsonBase track token usage for external API calls?

**Plain answer:**
TelsonBase logs that an external call was made — to which whitelisted domain, by which
agent, at what time, and that it was authorized. It does not currently parse API response
bodies to count LLM tokens consumed in those calls.

What is verifiable: the call happened, it was authorized, it went to an approved domain,
and it was initiated by an agent at a specific trust level.

What is not yet built: token counting from external LLM API responses. This is a monitoring
feature gap, not a security gap. It is flagged for post-drop development.

**Source files:**
- `core/openclaw.py` — egress firewall, domain whitelist enforcement
- `core/audit.py` — external call logging

**Skeptic follow-up:** *"So you can't prove API spend?"*
We can prove the call was authorized, logged, and compliant with governance rules. Token
cost attribution requires parsing provider-specific response formats — a monitoring feature,
currently on the roadmap.

---

## 9. How does TelsonBase respond to security attacks?

**Plain answer:**
Multiple layers fire in parallel:

- **Behavioral anomaly detection** — rate spikes, capability probing, and enumeration
  patterns trigger alerts visible in the Anomalies tab
- **Account lockout** — 5 failed authentication attempts in 15 minutes locks the account
- **Rate limiting** — 429 response after 300 requests per minute, logged
- **CAPTCHA** — automated registration blocked at the registration form
- **Audit logging** — every security event written to the tamper-evident chain
- **Grafana dashboards** — Prometheus metrics surfaced in real time

Push notifications (email, PagerDuty, Slack) require configuring Prometheus AlertManager
— the infrastructure is present, not pre-configured. Alerts are visible in the dashboard
and Grafana out of the box.

**Source files:**
- `core/anomaly.py` — behavioral anomaly detection
- `core/user_management.py` — account lockout logic
- `core/middleware.py` — rate limiting
- `core/captcha.py` — CAPTCHA challenge engine
- `monitoring/prometheus/alerts.yml` — alert rules

**Verification:**
```bash
# Trigger rate limiter
for i in $(seq 1 350); do curl -s http://localhost:8000/health > /dev/null; done
# Request ~301 should return 429

# Check anomaly log
curl http://localhost:8000/v1/anomaly/alerts \
  -H "X-API-Key: $API_KEY"
```

---

## 10. Is TelsonBase MCP compatible?

**Plain answer:**
Yes. TelsonBase exposes an MCP gateway at `/mcp` with 13 tools covering system status,
agent management, tenant operations, audit chain access, and approval workflows.
It uses StreamableHTTP transport and Bearer token authentication.

Compatible clients today: Goose, Claude Desktop, and any MCP-compliant client built
to the MCP specification.

**Available MCP tools:**
`system_status` · `get_health` · `list_agents` · `get_agent` · `register_as_agent`
· `list_tenants` · `create_tenant` · `list_matters` · `get_audit_chain_status`
· `verify_audit_chain` · `get_recent_audit_entries` · `list_pending_approvals`
· `approve_tool_request`

**Source files:**
- `api/mcp_gateway.py` — all 13 MCP tools
- `goose.yaml` — Goose connection configuration (project root)

**Verification:**
```bash
# Connect via Goose
# Copy goose.yaml to ~/.config/goose/config.yaml
# Run: goose session start
# Ask: "What is the TelsonBase system status?"
```

**Skeptic follow-up:** *"What other MCP products does it work with?"*
The MCP ecosystem is early. Goose and Claude Desktop are the primary clients today.
TelsonBase will be compatible with any client built to the MCP spec as the ecosystem grows.

---

## 11. Can Android or iOS apps communicate with TelsonBase?

**Plain answer:**
Yes. TelsonBase is a REST API — any HTTP client on any platform connects to it.
Android apps, iOS apps, mobile browsers, and desktop clients all use the same API
with JWT Bearer token authentication.

The admin dashboard (`/dashboard`) and user console (`/console`) are web applications
accessible from any mobile browser without installation.

For native mobile app integration: standard REST calls with JWT auth against the 151
documented API endpoints. Full API reference at `/docs` when the stack is running.

No native mobile SDK exists currently — that is a post-drop development item.

**Source files:**
- `main.py` — 151 API endpoints
- `docs/API_REFERENCE.md` — full endpoint documentation
- `frontend/index.html` — admin dashboard (web, mobile-accessible)
- `frontend/user-console.html` — user console (web, mobile-accessible)

---

## 12. Does TelsonBase communicate with Anthropic, Venice.ai, or external AI providers?

**Plain answer:**
No. TelsonBase sends nothing to anyone by default. Zero telemetry. No phone-home.
No data leaves the network unless an operator explicitly whitelists a domain in the
egress firewall and an agent with sufficient trust level initiates a call to it.

If you want to use Anthropic, Venice.ai, or any external AI provider as a backend,
you whitelist that domain and TelsonBase mediates, governs, and logs every call to it.
The call is authorized by the governance pipeline before it leaves the network.

The Manners compliance framework is modeled on Anthropic's safety principles but runs
entirely locally. It does not connect to Anthropic. It does not phone home. It does not
receive updates automatically. Your governance engine runs under your control.

**Source files:**
- `core/openclaw.py` — egress firewall, domain whitelist
- `core/manners.py` — local Manners compliance engine
- `core/config.py` — no external telemetry endpoints configured

**Verification:**
```bash
# Confirm no outbound connections at startup (run with network monitor)
docker compose up -d
# Monitor outbound traffic — zero external connections initiated by TelsonBase itself
```

**Skeptic follow-up:** *"So there's no automatic safety update if Anthropic releases one?"*
Correct — and that is by design. Data sovereignty means the governance engine runs on
your hardware under your control. You choose when to update. No external party can push
changes to your governance rules without your action.

---

## 13. Is TelsonBase HIPAA, SOC 2, or HITRUST compliant?

**Plain answer:**
The compliance infrastructure is fully built and mapped to source code. Every control
references the file that implements it and the test that verifies it. Formal certification
is the third-party recognition of what is already there — and that process grows with
the project.

What is built today:

| Framework | Status | Coverage |
|---|---|---|
| **SOC 2 Type I** | 51 controls documented and mapped to source | All 5 Trust Service Criteria |
| **HIPAA Security Rule** | Full control mapping | Administrative, Physical, Technical, Organizational |
| **HITRUST CSF** | 12 domains | Baseline controls, risk scoring, gap analysis |
| **CJIS** | Mapped | Advanced auth, media protection, audit controls |
| **GDPR** | Mapped | Data minimization, encryption, right to erasure |
| **PCI DSS** | Mapped | Encryption, segmentation, access control, logging |
| **ABA Model Rules** | Mapped | Rules 1.6, 1.7/1.10, 5.3, Formal Opinion 512 |
| **HITECH Act** | Mapped | Breach notification, 60-day tracking, safe harbor |

The distinction between "compliance-ready" and "certified" is the third-party audit.
TelsonBase has built the controls. Formal certification (SOC 2 Type II audit, HIPAA SRA,
HITRUST assessment) is the next step as the project scales. Every control is already
mapped to source code and a passing test — the audit trail is ready when the auditor
arrives.

**Source files:**
- `docs/SOC2_TYPE_I.md` — 51 controls with source evidence
- `docs/System Documents/COMPLIANCE_ROADMAP.md` — 6-phase certification roadmap
- `proof_sheets/` — 39 evidence sheets, all compliance claims traced

**Verification:**
```bash
# Review SOC 2 control mapping
cat docs/SOC2_TYPE_I.md

# Run compliance framework tests
docker compose exec mcp_server python -m pytest tests/ -k "compliance" -v
```

**Skeptic follow-up:** *"Compliance-ready isn't the same as compliant."*
Correct. The controls are implemented and tested. Certification is formal third-party
recognition. A law firm deploying TelsonBase today has working HIPAA controls — AES-256-GCM
encryption, 18-identifier de-identification, tamper-evident audit trail, automatic logoff.
Those controls exist whether or not a certification badge has been issued.

---

## 14. Has TelsonBase been independently audited or pen tested?

**Plain answer:**
Static analysis and automated security testing have been run against the full codebase.
Results are documented and public:

- **Bandit (static analysis):** 0 high-severity findings across 37,921 lines scanned.
  8 medium findings, all non-actionable: 2 are expected `0.0.0.0` bind addresses in
  `if __name__ == "__main__":` dev-only blocks in `main.py` and `gateway/egress_proxy.py`
  (Gunicorn binds via command line in production — these lines never execute in the
  container). 6 are `requests.get/post` calls without an explicit timeout in
  `scripts/test_security_flow.py`, a manually-invoked diagnostic script, not production
  code. No production code findings.
- **pip-audit (dependency CVEs):** 1 known CVE — `ecdsa` CVE-2024-23342. No upstream fix
  exists. Accepted risk — TelsonBase uses HS256 (HMAC), not ECDSA. `ecdsa` is an unused
  transitive dependency that has been removed from the production image.
- **Schemathesis (API contract testing):** 720 tests passing. Server errors reduced
  from 657 → 0 across hardening sessions.
- **Pen test preparation documentation:** Full attack surface inventory, OWASP Top 10
  mapping, and scoped test plan available in `docs/PENTEST_PREPARATION.md`.

Independent third-party penetration testing is on the roadmap as the project scales.
The infrastructure to support and respond to a formal pen test is already in place.

**Source files:**
- `docs/PENTEST_PREPARATION.md` — attack surface inventory and test plan
- `.github/workflows/ci.yml` — automated security scan on every commit
- `docs/TECHNICAL_DEFENSE_BRIEF.md` — answers to every anticipated technical challenge

---

## 15. Who built this and why should I trust a solo developer?

**Plain answer:**
TelsonBase was built by Jeff Phillips (Quietfire AI) through genuine human-AI collaboration
across multiple models over several years. The platform is self-taught, independently funded,
and carries no corporate backing or venture influence.

The answer to "why trust it" is not credentials — it is evidence:

- **720 passing tests** that you can run yourself in under five minutes
- **40 proof sheets** that map every public claim to source code and a verification command
- **0 high-severity findings** in static analysis across 37,921 lines
- **Full source available** — read every line, verify every claim, run every test

The credibility of TelsonBase is not a function of who built it. It is a function of
whether the claims hold up under inspection. The proof sheets exist precisely so that
the work speaks for itself.

**Skeptic follow-up:** *"AI wrote this code — how do you know it's trustworthy?"*
Every AI model was engaged as a collaborator, not a code generator. The architecture,
security decisions, and engineering choices were made by a human architect who reviewed,
tested, and challenged every output. The test suite, the static analysis, and the proof
sheets are the verification layer. Run them. That's the deal.

---

## 16. What happens if the developer stops maintaining it?

**Plain answer:**
TelsonBase is open source under Apache 2.0. If development stopped today, anyone could
fork the repository, continue development, and redistribute under the same terms. The
entire codebase, all documentation, all proof sheets, and all test infrastructure are
publicly available.

A governance platform that depends on a single vendor for survival is itself a governance
risk. TelsonBase is designed so that the community can carry it forward.

**Source files:**
- `LICENSE` — Apache 2.0 terms
- `CONTRIBUTING.md` — contribution guidelines
- `docs/DEVELOPER_GUIDE.md` — full architecture documentation for new contributors

---

## 17. Can TelsonBase scale beyond a single machine?

**Plain answer:**
Yes. The current Docker Compose deployment is single-node and production-appropriate for
most small and mid-market deployments. Horizontal scaling has two documented paths:

- **Phase 1 — Docker Swarm:** 2–3 days of configuration. Adds multi-node redundancy,
  rolling updates, and basic load distribution. Appropriate for organizations with
  moderate load and existing Docker infrastructure.

- **Phase 2 — Kubernetes:** Full orchestration, auto-scaling, self-healing deployments.
  Appropriate for large enterprise and multi-tenant production environments.

The architecture is stateless at the API layer (Redis handles shared state, PostgreSQL
handles persistence) — horizontal scaling is a deployment configuration, not a
re-architecture.

**Source files:**
- `docs/System Documents/HA_ARCHITECTURE.md` — full scaling roadmap, component HA
  strategies, decision matrix by user scale

**Skeptic follow-up:** *"Single gunicorn worker — isn't that a bottleneck?"*
Single worker is the correct choice for this workload. FastAPI + uvicorn handles all
concurrency async within one process. Multi-worker caused an audit chain fork at startup
(WATCH/MULTI/EXEC now makes the chain safe for any worker count). See
`docs/TECHNICAL_DEFENSE_BRIEF.md` — gunicorn section for the full rationale.

---

## 18. What AI models does TelsonBase support?

**Plain answer:**
Any model available through Ollama runs locally on your hardware with zero cloud dependency.
This includes Llama 3, Mistral, Gemma, Phi, Qwen, DeepSeek, and dozens of others.
No data leaves your network. No API key required for local inference.

For external AI providers (Anthropic, OpenAI, Venice.ai, etc.), you whitelist the domain
in the egress firewall, and TelsonBase mediates, logs, and governs every call. The
provider receives only what the agent is authorized to send at its current trust level.

**Source files:**
- `core/ollama_service.py` — local LLM inference service
- `main.py` — LLM endpoints (`/v1/llm/*`)

**Verification:**
```bash
# List available local models
curl http://localhost:8000/v1/llm/models \
  -H "X-API-Key: $API_KEY"

# Pull a model
curl -X POST http://localhost:8000/v1/llm/pull \
  -H "X-API-Key: $API_KEY" \
  -d '{"model":"llama3.2"}'
```

---

## 19. What is the license and what can I do with TelsonBase?

**Plain answer:**
TelsonBase is open source under the Apache License, Version 2.0.

**What Apache 2.0 means:** Free for any use — personal, commercial, production, research.
Use it, modify it, deploy it, build products on it, charge customers for it. No commercial
license required. No AGPL network-service disclosure requirements.

**What is required:**
- Retain the copyright and license notices when distributing TelsonBase or derivative works
- If you modify files, carry prominent notices stating you changed them

**Full terms:** `LICENSE` — or the official text at https://www.apache.org/licenses/LICENSE-2.0

**Support and consulting:** Quietfire AI offers enterprise support, consulting, and
compliance guidance for production deployments. Apache 2.0 means you are not obligated
to pay anything — but if you are deploying TelsonBase in healthcare, legal, or insurance
and want expert help, that is available. Contact support@telsonbase.com.

---

## 20. What are the performance characteristics?

**Plain answer:**
Load tested at 200 concurrent requests over 10 seconds against a self-hosted deployment:

| Metric | Result |
|---|---|
| p50 latency | 33ms |
| p95 latency | 47ms |
| p99 latency | 81ms |
| Error rate | 0% |
| Authenticated endpoint p50 | 80ms |
| Authenticated endpoint p95 | 202ms |
| Rate limiter trigger | ~request 98 at sustained load |

The governance pipeline adds latency to agent action evaluation — each of the 8 steps
is a Redis operation or in-memory check. In load testing, the governance overhead is
within acceptable bounds for the use case: governed AI agent actions are not
latency-sensitive at the millisecond level.

**Source files:**
- `run_advanced_tests.bat` — Level 4 performance test suite
- `monitoring/prometheus/alerts.yml` — HighLatency alert rule (>500ms p95)

---

## How to Verify Any Claim

Every answer in this document references source files. To verify any claim:

```bash
# Start the stack
docker compose up -d

# Run the full test suite
docker compose exec mcp_server python -m pytest tests/ -v --tb=short

# Browse the proof sheets for deeper evidence
cat proof_sheets/INDEX.md
```

**Questions not answered here?**
Open an issue on GitHub or email support@telsonbase.com

---

*TelsonBase v9.0.0B — Quietfire AI — support@telsonbase.com*
