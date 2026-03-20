# ClawCoat - Frequently Asked Questions
**Version:** v11.0.2 · **Maintainer:** Quietfire AI - support@clawcoat.com

ClawCoat is the platform for managing OpenClaw agents through earned trust. Agents start at QUARANTINE and work their way up - QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT - through demonstrated behavior and explicit human authorization at every step. The compliance infrastructure underneath (audit trails, kill switches, SOC 2 controls) is the proof, not the pitch.

Every answer here traces to source code. Where a verification command exists, it's provided.
The same standard applies here as in the proof sheets - no claim without a source.

---

## Table of Contents

1. [How do you add an agent?](#1-how-do-you-add-an-agent)
2. [How do agents communicate with each other?](#2-how-do-agents-communicate-with-each-other)
3. [How does an agent get access to a tool?](#3-how-does-an-agent-get-access-to-a-tool)
4. [What happens when an agent is blocked from an action?](#4-what-happens-when-an-agent-is-blocked-from-an-action)
5. [Can an operator reach a restricted agent?](#5-can-an-operator-reach-a-restricted-agent)
6. [What governs inbound communications from unknown sources?](#6-what-governs-inbound-communications-from-unknown-sources)
7. [What happens when an audit chain verification fails?](#7-what-happens-when-an-audit-chain-verification-fails)
8. [Can ClawCoat track token usage for external API calls?](#8-can-telsonbase-track-token-usage-for-external-api-calls)
9. [How does ClawCoat respond to security attacks?](#9-how-does-telsonbase-respond-to-security-attacks)
10. [Is ClawCoat MCP compatible?](#10-is-telsonbase-mcp-compatible)
11. [Can Android or iOS apps communicate with ClawCoat?](#11-can-android-or-ios-apps-communicate-with-telsonbase)
12. [Does ClawCoat communicate with Anthropic, Venice.ai, or external AI providers?](#12-does-telsonbase-communicate-with-anthropic-veniceai-or-external-ai-providers)
13. [Is ClawCoat HIPAA, SOC 2, or HITRUST compliant?](#13-is-telsonbase-hipaa-soc-2-or-hitrust-compliant)
14. [Has ClawCoat been independently audited or pen tested?](#14-has-telsonbase-been-independently-audited-or-pen-tested)
15. [Who built this and why should I trust a solo developer?](#15-who-built-this-and-why-should-i-trust-a-solo-developer)
16. [What happens if the developer stops maintaining it?](#16-what-happens-if-the-developer-stops-maintaining-it)
17. [Can ClawCoat scale beyond a single machine?](#17-can-telsonbase-scale-beyond-a-single-machine)
18. [What AI models does ClawCoat support?](#18-what-ai-models-does-telsonbase-support)
19. [What is the license and what can I do with ClawCoat?](#19-what-is-the-license-and-what-can-i-do-with-telsonbase)
20. [What are the performance characteristics?](#20-what-are-the-performance-characteristics)
21. [What are the 8 steps of the governance pipeline?](#21-what-are-the-8-steps-of-the-governance-pipeline)
22. [What is the Manners compliance system and how does auto-demotion work?](#22-what-is-the-manners-compliance-system-and-how-does-auto-demotion-work)
23. [How does an agent earn trust promotion?](#23-how-does-an-agent-earn-trust-promotion)

---

## 1. How do you add an agent?

**Plain answer:**
Two ways. An agent can self-register the moment it makes its first request through the MCP
gateway - ClawCoat intercepts it, assigns an instance ID, and places it in QUARANTINE
automatically. Or an operator pre-registers an agent through the dashboard before it ever
connects, using the Register Agent button in the Agents tab.

Either way, every agent always starts at QUARANTINE with zero autonomous permissions.
No exceptions. No shortcuts. Capability declarations are made at registration - what tools
the agent claims to need. What it can actually use is still gated by trust level and
the 8-step governance pipeline on every action evaluation.

**Source files:**
- `core/openclaw.py` - `register_instance()` - registration logic
- `api/openclaw_routes.py` - `POST /v1/openclaw/register` - API endpoint
- `frontend/index.html` - `RegisterAgentModal` component - dashboard UI

**Proof sheet:** `proof_sheets/TB-PROOF-041_agent_registration.md` - full developer deep dive,
registration fields, capability declaration, and first-action flow.

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
action is processed. See `core/openclaw.py` - `evaluate_action()`.

---

## 2. How Do Agents Communicate with Each Other?

**Plain answer:**
Through MQTT via the Mosquitto message bus built into the stack. Every message is wrapped
in QMS™ (Qualified Message Standard) - ClawCoat's inter-agent communication protocol.
QMS stamps every message with provenance: who sent it, what it contained, correlation ID,
and a command intent block. That record is hash-linked into the audit chain.

No agent-to-agent communication happens outside the bus. ClawCoat's MCP gateway acts
as the intermediary - agents don't talk directly to each other, they communicate through
ClawCoat, which mediates and logs everything.

QMS™ is also a security gate: the Foreman agent validates QMS formatting on every incoming
message before processing it. A message that arrives without proper QMS structure is not
treated as a malformed request - it is logged as a `NON_QMS_MESSAGE` anomaly event and
discarded. A registered agent that stops producing QMS-formatted messages is as anomalous
as one sending malformed messages. The behavioral baseline tracks both.

Every valid QMS chain follows the format:
```
::agent_id::-::@@correlation_id@@::-::action::-::data::-::_command::
```
The origin block is the identity check. The correlation block is the audit thread.
The command block is the intent. A message missing any of these is missing accountability.

**Source files:**
- `core/mqtt_bus.py` - MQTT message bus
- `core/qms.py` - QMS™ protocol: block types, chain construction, validation
- `toolroom/foreman.py` - QMS validation as security gate

**Proof sheet:** `proof_sheets/tb-proof-053_qms_suite.md` - 115 tests across 13 classes
verifying every aspect of the QMS™ protocol.

**Verification:**
```bash
# Check MQTT bus status
curl http://localhost:8000/v1/system/status \
  -H "X-API-Key: $API_KEY" | python -m json.tool | grep mosquitto
```

**Skeptic follow-up:** *"OpenClaw agents don't natively speak MQTT - how does this work?"*
ClawCoat's MCP gateway is the communication layer. Agents interact with ClawCoat's
guiding layer via MCP. ClawCoat routes, mediates, and logs. The agent never
communicates directly - it communicates through the governed proxy.

---

## 3. How Does an Agent Get Access to a Tool?

**Plain answer:**
Through the Toolroom. Every tool in the registry has a `min_trust_level` designation set
at install time. An agent cannot check out a tool unless its trust tier meets or exceeds
that designation. The ladder: QUARANTINE < PROBATION < RESIDENT < CITIZEN < AGENT.

Beyond trust level, tools marked `requires_api_access = true` trigger a HITL approval gate
regardless of tier - even an AGENT-level agent cannot check out an API-access tool without
explicit human authorization. This is non-negotiable: external API access carries credential
and egress risk that no trust tier removes.

The Foreman agent manages all checkout requests. It evaluates three things in sequence:
Is the agent on the tool's allowlist (if one exists)? Does the agent's trust level meet the
tool's `min_trust_level`? Does the tool require API access? Only after all three clear does
the checkout proceed.

Default `min_trust_level` is `"resident"` - QUARANTINE and PROBATION agents cannot check
out any standard tool unless an operator explicitly lowers the designation.

**Source files:**
- `toolroom/foreman.py` - `handle_checkout_request()` - checkout enforcement
- `toolroom/registry.py` - `ToolMetadata` - `min_trust_level`, `requires_api_access`, `allowed_agents` fields
- `docs/System%20Documents/TOOLROOM_TRUST_MATRIX.md` - full matrix: checkout eligibility by tier, recommended designations by category
- `main.py` - toolroom REST endpoints

**Proof sheet:** `proof_sheets/tb-proof-054_toolroom_suite.md` - 129 tests across 28 classes
verifying trust-level enforcement, HITL gate, manifest validation, and full REST coverage.

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

## 4. What Happens When an Agent Is Blocked from an Action?

**Plain answer:**
Three outcomes, depending on severity:

1. **Blocked** - Action rejected immediately. Audit logged. Agent receives a rejection
   response and continues running. No interruption to the agent process itself.

2. **Gated** - Action queued as a human approval request with an `APPR-` prefixed ID.
   Visible in the dashboard Approvals tab with full payload and context. Agent waits.
   Operator approves or rejects.

3. **Auto-demoted** - If the agent's Manners compliance score drops below 50%, it is
   immediately demoted to QUARANTINE with no human delay and no grace period. The action
   that triggered the evaluation is already affected. The agent remains registered but
   cannot take any autonomous action until reinstated by a human operator.

The kill switch is a fourth path: one API call suspends any agent instantly. All subsequent
actions are rejected at Step 2 of the pipeline - before trust levels, before Manners,
before everything except "does this agent exist?"

Non-QMS-formatted messages sent to the Foreman are a fifth outcome: the message is discarded
before processing and logged as a `NON_QMS_MESSAGE` anomaly event. The Foreman does not
work with unaccountable inputs.

**Source files:**
- `core/openclaw.py` - `evaluate_action()` - 8-step pipeline
- `core/openclaw.py` - `_check_manners_compliance()` - auto-demotion logic
- `api/openclaw_routes.py` - `POST /v1/openclaw/{id}/suspend` - kill switch

**Proof sheets:**
- `proof_sheets/TB-PROOF-037_openclaw_kill_switch.md` - kill switch behavior
- `proof_sheets/TB-PROOF-038_manners_auto_demotion.md` - auto-demotion on compliance score

**Verification:**
```bash
# Trigger the kill switch on an agent
curl -X POST http://localhost:8000/v1/openclaw/test-001/suspend \
  -H "X-API-Key: $API_KEY"

# Attempt an action - should be rejected at Step 2
curl -X POST http://localhost:8000/v1/openclaw/evaluate \
  -H "X-API-Key: $API_KEY" \
  -d '{"instance_id":"test-001","tool":"read_file","nonce":"abc123"}'
# response: blocked, reason: agent_suspended
```

**Skeptic follow-up:** *"What if the agent retries the blocked action repeatedly?"*
Anomaly detection flags repetitive blocked actions as a behavioral deviation. Rate limiting
fires at the agent's tier limit. Repeated violations accumulate in the Manners score -
which triggers auto-demotion if they push the score below threshold.

---

## 5. Can an Operator Reach a Restricted Agent?

**Plain answer:**
Yes. Restrictions govern what an agent can *initiate* outbound. The operator-to-agent
communication channel through the MCP gateway is always open - you can always send
instructions to a restricted or suspended agent. The agent can respond back through
ClawCoat. What it cannot do is make outbound calls on its own initiative.
Inbound and outbound are governed independently.

**Source files:**
- `api/mcp_gateway.py` - operator→agent instruction path
- `core/openclaw.py` - outbound action evaluation (separate from inbound channel)

**Verification:**
```bash
# Operator sends instruction via MCP gateway even to a suspended agent
# Connect via Goose or Claude Desktop pointed at http://localhost:8000/mcp
# Governance restriction affects agent-initiated actions, not operator-initiated contact
```

---

## 6. What Governs Inbound Communications from Unknown Sources?

**Plain answer:**
All inbound connections to ClawCoat require Bearer token or `X-API-Key` authentication.
Unknown connections receive a 401 before they reach any protected resource. The MCP gateway
validates instance ID and a cryptographic nonce on every action evaluation - replayed nonces
are rejected at Step 3 of the pipeline. Rate limiting fires at the agent's tier-appropriate
limit with a burst allowance. All connection attempts are logged to the audit chain.
An unrecognized instance is rejected at Step 1 - not registered, full stop.

For agent-to-agent messages: QMS™ validation fires before processing. A message without
proper QMS structure is discarded and logged as a `NON_QMS_MESSAGE` anomaly. Anonymous
transmissions are not processed - silence and malformation are treated the same.

**Source files:**
- `core/auth.py` - authentication layer
- `core/middleware.py` - rate limiting (token bucket)
- `core/openclaw.py` - nonce replay protection (Step 3 of pipeline)
- `api/openclaw_routes.py` - instance registration check (Step 1)
- `toolroom/foreman.py` - QMS validation gate

**Verification:**
```bash
# Attempt connection without authentication
curl http://localhost:8000/v1/system/status
# Expected: 401 Unauthorized

# Attempt with replayed nonce (second call with same nonce)
# Expected: rejected at Step 3 - nonce_already_used
```

---

## 7. What Happens When an Audit Chain Verification Fails?

**Plain answer:**
Two distinct failure types with different meanings:

- **`chain_break`** - A gap in sequence numbers from a container restart or Redis flush.
  This is a documented boundary event, not a security incident. The chain continues from
  a new genesis hash. Prior entries before the break are unaffected.

- **`hash_mismatch`** - An entry's stored hash does not match the recomputed hash of its
  content. This means an entry was modified after it was written. This is a security alert.
  It is flagged in the dashboard, logged, and the chain is considered compromised at that
  point forward.

Because each entry's hash includes the previous entry's hash, tampering with any single
entry invalidates every subsequent entry in the chain. Tampering cannot be hidden - it
can only be detected. You can hand a chain export to a forensic investigator and they can
verify every entry independently of the ClawCoat API, using only standard Python and
`hashlib`. See `docs/System%20Documents/AUDIT_TRAIL.md` - Verify an Entry Offline.

**Source files:**
- `core/audit.py` - `verify_chain()` - full verification loop
- `core/audit.py` - `_create_chain_entry()` - SHA-256 hash computation
- `frontend/index.html` - Verify Chain button and result banner

**Proof sheets:**
- `proof_sheets/TB-PROOF-009_audit_chain_sha256.md` - SHA-256 hash-chained audit trail
- `proof_sheets/TB-PROOF-046_security_audit_trail.md` - security battery: chain creation,
  tamper detection, UTC timestamp enforcement

**Verification:**
```bash
# Verify the current chain from the API
curl http://localhost:8000/v1/audit/chain/verify \
  -H "X-API-Key: $API_KEY"
# Returns: valid=true, entries_checked, or hash_mismatch with sequence number
```

**Skeptic follow-up:** *"What if someone flushes Redis?"*
Redis flush = chain_state lost, new genesis starts. This is a known architectural limit,
documented in `docs/System%20Documents/AUDIT_TRAIL.md` - Known Limitations. PostgreSQL archival for long-term
retention is on the roadmap. A flush is detectable as an unusually early genesis in the
chain history. Physical access to flush Redis is itself a security event - outside
ClawCoat's threat model (assumes secure infrastructure).

---

## 8. Can ClawCoat Track Token Usage for External API Calls?

**Plain answer:**
ClawCoat logs that an external call was made - to which whitelisted domain, by which
agent, at what time, and that it was authorized. It does not currently parse API response
bodies to count LLM tokens consumed in those calls.

What is verifiable: the call happened, it was authorized, it went to an approved domain,
and it was initiated by an agent at a specific trust level.

What is not yet built: token counting from external LLM API responses. This is a monitoring
feature gap, not a security gap. It is flagged for post-drop development.

**Source files:**
- `core/openclaw.py` - egress firewall, domain whitelist enforcement
- `core/audit.py` - external call logging

**Skeptic follow-up:** *"So you can't prove API spend?"*
We can prove the call was authorized, logged, and compliant with governance rules. Token
cost attribution requires parsing provider-specific response formats - a monitoring feature,
currently on the roadmap.

---

## 9. How Does ClawCoat Respond to Security Attacks?

**Plain answer:**
Multiple layers fire in parallel:

- **Behavioral anomaly detection** - rate spikes, capability probing, and enumeration
  patterns trigger alerts visible in the Anomalies tab
- **Account lockout** - 5 failed authentication attempts in 15 minutes locks the account
- **Rate limiting** - 429 response after tier-appropriate request limits, logged
- **CAPTCHA** - automated registration blocked at the registration form
- **Audit logging** - every security event written to the tamper-evident chain
- **Grafana dashboards** - Prometheus metrics surfaced in real time

Push notifications (email, PagerDuty, Slack) require configuring Prometheus AlertManager
- the infrastructure is present, not pre-configured. Alerts are visible in the dashboard
and Grafana out of the box.

**Source files:**
- `core/anomaly.py` - behavioral anomaly detection
- `core/user_management.py` - account lockout logic
- `core/middleware.py` - rate limiting
- `core/captcha.py` - CAPTCHA challenge engine
- `monitoring/prometheus/alerts.yml` - alert rules

**Proof sheets:**
- `proof_sheets/TB-PROOF-022_api_fuzz_testing.md` - 177 API operations fuzz-tested
- `proof_sheets/TB-PROOF-024_zero_server_errors.md` - 0 server errors under fuzzing
- `proof_sheets/TB-PROOF-027_static_analysis.md` - 0 high-severity static analysis findings
- `proof_sheets/TB-PROOF-020_anomaly_detection.md` - behavioral anomaly detection

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

## 10. Is ClawCoat MCP Compatible?

**Plain answer:**
Yes. ClawCoat exposes an MCP gateway at `/mcp` with 13 tools covering system status,
agent management, tenant operations, audit chain access, and approval workflows.
It uses StreamableHTTP transport and Bearer token authentication.

Compatible clients today: Goose (by Block, Apache 2.0), Claude Desktop, and any
MCP-compliant client built to the MCP specification.

**Note:** Connecting an MCP client is optional. ClawCoat runs and governs agents
independently. The MCP gateway gives operators a natural-language interface to the
same governance controls available in the admin panel and REST API.

**Available MCP tools:**
`system_status` · `get_health` · `list_agents` · `get_agent` · `register_as_agent`
· `list_tenants` · `create_tenant` · `list_matters` · `get_audit_chain_status`
· `verify_audit_chain` · `get_recent_audit_entries` · `list_pending_approvals`
· `approve_tool_request`

**Source files:**
- `api/mcp_gateway.py` - all 13 MCP tools
- `goose.yaml` - Goose connection configuration (project root)

**Verification:**
```bash
# Connect via Goose
# Copy goose.yaml to ~/.config/goose/config.yaml
# Run: goose session start
# Ask: "What is the ClawCoat system status?"
```

**Skeptic follow-up:** *"What other MCP products does it work with?"*
The MCP ecosystem is early. Goose and Claude Desktop are the primary clients today.
ClawCoat will be compatible with any client built to the MCP spec as the ecosystem grows.

---

## 11. Can Android or iOS Apps Communicate with ClawCoat?

**Plain answer:**
Yes. ClawCoat is a REST API - any HTTP client on any platform connects to it.
Android apps, iOS apps, mobile browsers, and desktop clients all use the same API
with JWT Bearer token authentication.

The admin dashboard (`/dashboard`) and user console (`/console`) are web applications
accessible from any mobile browser without installation.

For native mobile app integration: standard REST calls with JWT auth against the 164
documented API endpoints. Full API reference at `/docs` when the stack is running.

No native mobile SDK exists currently - that is a post-drop development item.

**Source files:**
- `main.py` - 164 API endpoints
- `frontend/index.html` - admin dashboard (web, mobile-accessible)
- `frontend/user-console.html` - user console (web, mobile-accessible)

---

## 12. Does ClawCoat Communicate with Anthropic, Venice.ai, or External AI Providers?

**Plain answer:**
No. ClawCoat sends nothing to anyone by default. Zero telemetry. No phone-home.
No data leaves the network unless an operator explicitly whitelists a domain in the
egress firewall and an agent with sufficient trust level initiates a call to it.

If you want to use Anthropic, Venice.ai, or any external AI provider as a backend,
you whitelist that domain and ClawCoat mediates, governs, and logs every call to it.
The call is authorized by the governance pipeline before it leaves the network.

The Manners compliance framework is modeled on five behavioral safety principles and runs
entirely locally. It does not connect to any external service. It does not phone home. It does not
receive updates automatically. Your governance engine runs under your control.

**Source files:**
- `core/openclaw.py` - egress firewall, domain whitelist
- `core/manners.py` - local Manners compliance engine
- `core/config.py` - no external telemetry endpoints configured

**Proof sheet:** `proof_sheets/TB-PROOF-028_zero_data_leaves.md` - zero data leaves your network.

**Verification:**
```bash
# Confirm no outbound connections at startup (run with network monitor)
docker compose up -d
# Monitor outbound traffic - zero external connections initiated by ClawCoat itself
```

**Skeptic follow-up:** *"So there's no automatic safety update if Anthropic releases one?"*
Correct - and that is by design. Data sovereignty means the governance engine runs on
your hardware under your control. You choose when to update. No external party can push
changes to your governance rules without your action.

---

## 13. Is ClawCoat HIPAA, SOC 2, or HITRUST Compliant?

**Plain answer:**
The compliance infrastructure is fully built and mapped to source code. Every control
references the file that implements it and the test that verifies it. Formal certification
is the third-party recognition of what is already there - and that process grows with
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
ClawCoat has built the controls. Formal certification (SOC 2 Type II audit, HIPAA SRA,
HITRUST assessment) is the next step as the project scales. Every control is already
mapped to source code and a passing test - the audit trail is ready when the auditor arrives.

**Source files:**
- `docs/SOC2_TYPE_I.md` - 51 controls with source evidence
- `docs/System Documents/COMPLIANCE_ROADMAP.md` - 6-phase certification roadmap

**Proof sheets:** 788 proof documents across 67 class-level evidence sheets - every compliance
claim traced to source code and a verification command. Start at `proof_sheets/INDEX.md`.

**Verification:**
```bash
# Run compliance framework tests
docker compose exec mcp_server python -m pytest tests/ -k "compliance" -v

# Review the full proof sheet index
cat proof_sheets/INDEX.md
```

**Skeptic follow-up:** *"Compliance-ready isn't the same as compliant."*
Correct. The controls are implemented and tested. Certification is formal third-party
recognition. A law firm deploying ClawCoat today has working HIPAA controls - AES-256-GCM
encryption, 18-identifier de-identification, tamper-evident audit trail, automatic logoff.
Those controls exist whether or not a certification badge has been issued.

---

## 14. Has ClawCoat Been Independently Audited or Pen Tested?

**Plain answer:**
Static analysis and automated security testing have been run against the full codebase.
Results are documented and public:

- **Bandit (static analysis):** 0 high-severity findings across 93,893 lines scanned.
  8 medium findings, all non-actionable: 2 are expected `0.0.0.0` bind addresses in
  `if __name__ == "__main__":` dev-only blocks (Gunicorn binds via command line in
  production - these lines never execute in the container). 6 are `requests.get/post`
  calls without an explicit timeout in `scripts/test_security_flow.py`, a manually-invoked
  diagnostic script, not production code. No production code findings.
- **pip-audit (dependency CVEs):** 1 known CVE - `ecdsa` CVE-2024-23342. No upstream fix
  exists. Accepted risk - ClawCoat uses HS256 (HMAC), not ECDSA. `ecdsa` is an unused
  transitive dependency that has been removed from the production image.
- **Schemathesis (API contract testing):** 5,777 tests passing. Server errors reduced
  from 657 → 0 across hardening sessions.
- **Pen test preparation documentation:** Full attack surface inventory, OWASP Top 10
  mapping, and scoped test plan available in `docs/PENTEST_PREPARATION.md`.

Independent third-party penetration testing is on the roadmap as the project scales.
The infrastructure to support and respond to a formal pen test is already in place.

**Source files:**
- `docs/PENTEST_PREPARATION.md` - attack surface inventory and test plan
- `.github/workflows/ci.yml` - automated security scan on every commit
- `docs/System%20Documents/SECURITY_GUIDELINES.md` - vulnerability scope, reporting, and current security posture

**Proof sheets:**
- `proof_sheets/TB-PROOF-027_static_analysis.md` - Bandit results, 0 high-severity
- `proof_sheets/TB-PROOF-022_api_fuzz_testing.md` - 177 operations fuzz-tested
- `proof_sheets/TB-PROOF-024_zero_server_errors.md` - 0 server errors under fuzzing

---

## 15. Who Built This and Why Should I Trust a Solo Developer?

**Plain answer:**
ClawCoat was built by Jeff Phillips (Quietfire AI) through genuine human-AI collaboration
across multiple models over several years. The platform is self-taught, independently funded,
and carries no corporate backing or venture influence.

The answer to "why trust it" is not credentials - it is evidence:

- **5,777 passing tests** that you can run yourself in under five minutes
- **788 proof documents** - 67 class-level evidence sheets that map every public claim
  to source code, test classes, and a verification command you can run
- **0 high-severity findings** in static analysis across 93,893 lines
- **Full source available** - read every line, verify every claim, run every test

The credibility of ClawCoat is not a function of who built it. It is a function of
whether the claims hold up under inspection. The proof sheets exist precisely so that
the work speaks for itself.

**Proof sheet:** `proof_sheets/TB-PROOF-001_tests_passing.md` - 5,777 tests, verification command.

**Skeptic follow-up:** *"AI wrote this code - how do you know it's trustworthy?"*
Every AI model was engaged as a collaborator, not a code generator. The architecture,
security decisions, and engineering choices were made by a human architect who reviewed,
tested, and challenged every output. The test suite, the static analysis, and the proof
sheets are the verification layer. Run them. That's the deal.

---

## 16. What Happens If the Developer Stops Maintaining It?

**Plain answer:**
ClawCoat is open source under Apache 2.0. If development stopped today, anyone could
fork the repository, continue development, and redistribute under the same terms. The
entire codebase, all documentation, all proof sheets, and all test infrastructure are
publicly available.

A governance platform that depends on a single vendor for survival is itself a governance
risk. ClawCoat is designed so that the community can carry it forward.

**Source files:**
- `LICENSE` - Apache 2.0 terms
- `CONTRIBUTING.md` - contribution guidelines
- `docs/DEVELOPER_GUIDE.md` - full architecture documentation for new contributors

---

## 17. Can ClawCoat Scale Beyond a Single Machine?

**Plain answer:**
Yes. The current Docker Compose deployment is single-node and production-appropriate for
most small and mid-market deployments. Horizontal scaling has two documented paths:

- **Phase 1 - Docker Swarm:** 2-3 days of configuration. Adds multi-node redundancy,
  rolling updates, and basic load distribution. Appropriate for organizations with
  moderate load and existing Docker infrastructure.

- **Phase 2 - Kubernetes:** Full orchestration, auto-scaling, self-healing deployments.
  Appropriate for large enterprise and multi-tenant production environments.

The architecture is stateless at the API layer (Redis handles shared state, PostgreSQL
handles persistence) - horizontal scaling is a deployment configuration, not a
re-architecture.

**Source files:**
- `docs/System Documents/HA_ARCHITECTURE.md` - full scaling roadmap, component HA
  strategies, decision matrix by user scale

**Skeptic follow-up:** *"Single gunicorn worker - isn't that a bottleneck?"*
Single worker is the correct choice for this workload. FastAPI + uvicorn handles all
concurrency async within one process. Multi-worker is safe - the audit chain uses Redis
WATCH/MULTI/EXEC transactions, so it is race-free at any worker count. See
`docs/System%20Documents/AUDIT_TRAIL.md` - Storage Architecture for the full rationale.

---

## 18. What AI Models Does ClawCoat Support?

**Plain answer:**
Any model available through Ollama runs locally on your hardware with zero cloud dependency.
This includes Llama 3, Mistral, Gemma, Phi, Qwen, DeepSeek, and dozens of others.
No data leaves your network. No API key required for local inference.

For external AI providers (Anthropic, OpenAI, Venice.ai, etc.), you whitelist the domain
in the egress firewall, and ClawCoat mediates, logs, and governs every call. The
provider receives only what the agent is authorized to send at its current trust level.

**Source files:**
- `core/ollama_service.py` - local LLM inference service
- `main.py` - LLM endpoints (`/v1/llm/*`)

**Proof sheet:** `proof_sheets/TB-PROOF-029_local_llm_ollama.md` - local LLM inference verification.

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

## 19. What Is the License and What Can I Do with ClawCoat?

**Plain answer:**
ClawCoat is open source under the Apache License, Version 2.0.

**What Apache 2.0 means:** Free for any use - personal, commercial, production, research.
Use it, modify it, deploy it, build products on it, charge customers for it. No commercial
license required. No AGPL network-service disclosure requirements.

**What is required:**
- Retain the copyright and license notices when distributing ClawCoat or derivative works
- If you modify files, carry prominent notices stating you changed them

**Full terms:** `LICENSE` - or the official text at https://www.apache.org/licenses/LICENSE-2.0

**Support and consulting:** Quietfire AI offers enterprise support, consulting, and
compliance guidance for production deployments. Apache 2.0 means you are not obligated
to pay anything - but if you are deploying ClawCoat in healthcare, legal, or insurance
and want expert help, that is available. Contact support@clawcoat.com.

---

## 20. What Are the Performance Characteristics?

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

The governance pipeline adds latency to agent action evaluation - each of the 8 steps
is a Redis operation or in-memory check. In load testing, the governance overhead is
within acceptable bounds for the use case: governed AI agent actions are not
latency-sensitive at the millisecond level.

**Source files:**
- `run_advanced_tests.bat` - Level 4 performance test suite
- `monitoring/prometheus/alerts.yml` - HighLatency alert rule (>500ms p95)

**Proof sheet:** `proof_sheets/TB-PROOF-026_concurrent_requests.md` - 50 concurrent requests handled.

---

## 21. What Are the 8 Steps of the Governance Pipeline?

**Plain answer:**
Every agent action - every tool call, every external request, every file operation - passes
through an 8-step pipeline in `core/openclaw.py` `evaluate_action()`. No step is skipped.
No tier bypasses the pipeline. This is the core of ClawCoat's governance model.

| Step | Check | Fail outcome |
|---|---|---|
| 1 | **Registration** - Is this instance_id registered? | `BLOCKED` - unregistered agent |
| 2 | **Kill switch** - Is the agent suspended? | `BLOCKED` - agent_suspended, before anything else |
| 3 | **Nonce replay** - Has this exact nonce been seen before? | `BLOCKED` - nonce_already_used |
| 4 | **Manners compliance** - Is the behavioral score above threshold (default 50%)? | Auto-demote to QUARANTINE, `BLOCKED` |
| 5 | **Trust level** - Does the agent's tier permit this action category? | `BLOCKED` or `GATED` depending on action type |
| 6 | **Capability check** - Is this tool/action in the agent's declared capability profile? | `BLOCKED` - capability_not_declared |
| 7 | **Anomaly detection** - Does this action match known behavioral anomaly patterns? | `GATED` (requires human approval) or advisory log at AGENT tier |
| 8 | **Decision** - Action is `ALLOWED`, `GATED` (APPR- ID created), or `BLOCKED` | Audit entry written regardless of outcome |

Every outcome - allowed, gated, or blocked - is written to the hash-chained audit trail.
At AGENT tier (apex), anomalies at Step 7 are logged as advisory rather than gating execution.
AGENT is the only tier where anomalies do not gate - and it is the hardest tier to earn.

**Source files:**
- `core/openclaw.py` - `evaluate_action()` - the full pipeline implementation
- `core/trust_levels.py` - `TRUST_PERMISSION_MATRIX` - what each tier permits

**Proof sheet:** `proof_sheets/TB-PROOF-035_openclaw_governance.md` - governance pipeline verification.

**Skeptic follow-up:** *"8 Redis operations per action - isn't that slow?"*
Each step is an in-memory check or a single Redis operation. At p50, the governance
overhead is within the latency profile documented in Q20. Governed AI agent actions
operate in seconds, not milliseconds - governance latency is not the bottleneck.

---

## 22. What Is the Manners Compliance System and How Does Auto-Demotion Work?

**Plain answer:**
Manners is ClawCoat's behavioral compliance scoring engine, modeled on five behavioral
safety principles and running entirely locally. Every agent action contributes to
a rolling compliance score between 0.0 (no compliance) and 1.0 (full compliance).

The default threshold is 50%. Drop below it and the agent is automatically demoted to
QUARANTINE - no human in the loop, no grace period, no delay. The demotion fires at
Step 4 of the governance pipeline, before the action that triggered the evaluation proceeds.
The agent remains registered and visible to operators, but cannot take any autonomous
action until a human operator explicitly reinstates it.

**What lowers the score:**
- Repeated blocked actions - attempting restricted operations the agent knows are out of bounds
- Capability probing - enumerating permissions or trying unauthorized tools
- Rate limit violations
- Non-QMS-formatted messages to the Foreman
- Behavioral anomalies flagged by the detection engine

**What the operator controls:**
- When to reinstate a demoted agent (always a human decision)
- The threshold value (configurable, default 0.50)
- Individual behavior weighting

This is not a punishment system - it is a behavioral signal. An agent that consistently
attempts actions it cannot take is demonstrating that its capabilities do not match its
declared profile. Auto-demotion surfaces that mismatch automatically, before it becomes
a security event.

**Source files:**
- `core/manners.py` - Manners scoring engine
- `core/openclaw.py` - `_check_manners_compliance()` - Step 4 integration

**Proof sheet:** `proof_sheets/TB-PROOF-038_manners_auto_demotion.md` - auto-demotion behavior,
threshold enforcement, and operator reinstatement flow.

**Skeptic follow-up:** *"Can an agent game the scoring?"*
The score is computed server-side by ClawCoat, not reported by the agent. The agent
has no direct mechanism to influence its own Manners score - it can only behave. The
behavioral record is hash-chained and tamper-evident.

---

## 23. How Does an Agent Earn Trust Promotion?

**Plain answer:**
The 5-tier promotion ladder: QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT.
No tier can be skipped. Promotion is always one step at a time. Demotion can skip levels
instantly. Every promotion requires a human operator decision - trust is earned and
verified, never assigned.

**What each step requires** (enforced in `core/trust_levels.py` - `TRUST_LEVEL_CONSTRAINTS`):

| Promotion | What Is Required |
|---|---|
| QUARANTINE → PROBATION | Human operator decision. The agent demonstrates it can receive instructions and respond without behavioral violations. No automated path. |
| PROBATION → RESIDENT | Demonstrated behavioral baseline. Sustained Manners score above threshold. Human operator approval. |
| RESIDENT → CITIZEN | Extended behavioral record. No anomaly flags in the trailing evaluation window. Human operator approval. |
| CITIZEN → AGENT | Full ladder completed. 99.9% success rate. Zero anomalies in the trailing period. Minimum 50 actions to demonstrate activity. Human operator approval. |

At AGENT tier: the highest rate limit (300/min), full autonomous access across all 6 action
categories, and anomaly detection that logs loudly but does not gate execution. AGENT is
not a designation - it is a record. The platform has verified, repeatedly, that this agent
behaves within its declared profile.

AGENT tier re-verification runs every 3 days. A single period of poor behavior can trigger
demotion from apex back to any lower tier - including QUARANTINE - with no intermediate
stops required on the way down.

**Source files:**
- `core/trust_levels.py` - `TRUST_LEVEL_CONSTRAINTS`, `VALID_PROMOTIONS`, `VALID_DEMOTIONS`
- `core/openclaw.py` - `promote_trust()`, `demote_trust()`

**Proof sheets:**
- `proof_sheets/TB-PROOF-039_earned_trust_model.md` - earned trust model verification
- `proof_sheets/TB-PROOF-036_trust_level_matrix.md` - permission matrix by tier

**Skeptic follow-up:** *"Can an operator just promote an agent without it earning it?"*
Yes - the operator controls promotion. What the system enforces is that promotion is always
sequential (no skipping), always requires an operator action (no automatic promotion), and
is always reversible (demotion can skip levels, instantly, at any time).

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
Open an issue on GitHub or email support@clawcoat.com

---

*ClawCoat v11.0.2 · Quietfire AI · March 19, 2026*
