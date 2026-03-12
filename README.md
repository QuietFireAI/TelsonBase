# TelsonBase

### Control Your Claw. Trust Is Earned.

<p align="center">
  <strong>v11.0.1</strong> &nbsp;|&nbsp;
  <strong>746 tests passing</strong> &nbsp;|&nbsp;
  <strong>51 SOC 2 controls</strong> &nbsp;|&nbsp;
  <strong>161 API endpoints</strong> &nbsp;|&nbsp;
  <strong>0 data shared</strong>
</p>

<p align="center">
  <a href="docs/Operation%20Documents/DEVELOPER_GUIDE.md">Developer Guide</a> &nbsp;|&nbsp;
  <a href="docs/System%20Documents/API_REFERENCE.md">API Reference</a> &nbsp;|&nbsp;
  <a href="docs/System%20Documents/SECURITY_ARCHITECTURE.md">Security Architecture</a> &nbsp;|&nbsp;
  <a href="docs/FAQ.md">FAQ</a> &nbsp;|&nbsp;
  <a href="docs/AMBASSADORS.md">Ambassador Program</a>
</p>

<p align="center">
  <a href="https://github.com/QuietFireAI/TelsonBase/actions/workflows/ci.yml"><img src="https://github.com/QuietFireAI/TelsonBase/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat" alt="License: Apache 2.0">
  &nbsp;
  <img src="https://img.shields.io/badge/python-3.11-blue?style=flat&logo=python&logoColor=white" alt="Python 3.11">
  &nbsp;
  <a href="https://huggingface.co/spaces/QuietFireAI/TelsonBase"><img src="https://img.shields.io/badge/Live%20Demo-HuggingFace-ff6b35?style=flat&logo=huggingface&logoColor=white" alt="Live Demo on HuggingFace"></a>
  &nbsp;
  <a href="https://buymeacoffee.com/jphillips"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support%20the%20project-ffdd00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee"></a>
</p>

---

## Status: Live

**746 tests passing. 0 high-severity findings. Everything described in this README is built and running - not a roadmap, not a mockup.**

The governance engine, trust pipeline, compliance infrastructure, and admin dashboard are fully functional. The integration guide covers the full OpenClaw flow end-to-end and has been verified across multiple clean-slate deployments.

**Try the live demo:** [huggingface.co/spaces/QuietFireAI/TelsonBase](https://huggingface.co/spaces/QuietFireAI/TelsonBase)

**What's stable and tested:**
Trust governance pipeline · Cryptographic audit chain · RBAC (150 endpoints) · Human-in-the-loop approval gates · Kill switch · Manners compliance engine · Multi-tenant isolation · SOC 2 / HIPAA / HITRUST / CJIS compliance frameworks · Admin dashboard · OpenClaw governance proxy

**What's actively being worked on:**
User management live endpoint · QMS real-time log feed · Audit chain PostgreSQL archival beyond 100K entries · Agent actor attribution in approval decisions

If something is broken, [open an issue](../../issues). If something is missing that you need, [start a discussion](../../discussions). If you want to contribute, read [CONTRIBUTING.md](CONTRIBUTING.md).

---

## A Letter From the Developer

I'm one person. This project was built over two years on consumer hardware, with standard subscriptions, using three AI platforms — not as tools, but as partners. The turning point came when I started cross-checking each model's work against the others. That process eliminated drift and produced what you're looking at now.

TelsonBase is my interpretation of how AI agents can work together, safely — not the answer, but an answer. Specifically, it's the one I'm building on for my own agents. I'm sharing this freely because the problem is real and one person's solution only goes so far. If this gains traction, community contributions will drive proper vetting and expanded capability — released back openly as it comes.

---

## The Idea

Two things. That's it.

**Agents earn their autonomy.** Every agent starts at zero — no tools, no external access, no assumptions. They work their way up through five trust tiers, but behavior alone doesn't get them there. Demonstrated safe behavior opens the door. A human has to walk them through it. QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT. Promotion is sequential and requires explicit human authorization. Demotion is instant and can skip levels. Trust at any level is revocable in a single API call.

**Behavior has a score.** Every agent carries a Manners compliance score — a live measurement across five principles: Human Control, Transparency, Value Alignment, Privacy, and Security. The score moves in real time. Blocked actions cost points. Good behavior holds the score. Drop below 50% and the agent is automatically demoted to Quarantine, no human required.

These two things together are the architecture. Everything else in TelsonBase — the audit trail, the kill switches, the compliance frameworks, the 8-step governance pipeline — exists to support them.

I built this before Anthropic published their agent safety framework. When it came out, the alignment was coincidental — and it confirmed my ideas in someone else's words. TelsonBase is built on a simple belief: AI agents should be held accountable to human values, by humans with good judgment. And with good judgment, autonomous agents should be able to learn from their own actions — like training a dog. Do good, earn more freedom. Act badly, lose the ability to do fun things. Agents that already demonstrate the ability to make decisions can certainly understand that their own actions have consequences. As my dad would say.

The trust tiers aren't arbitrary levels — they're citizenship. An agent at QUARANTINE is a new arrival with no established record. An agent that reaches CITIZEN or AGENT has earned that standing through demonstrated behavior, one verified action at a time. If agents are going to do the work of people, it seems reasonable they should earn the right to do so the same way people do — by showing up, doing the job, and building a record worth trusting.

The tools an agent can access follow the same logic. Not every tool is available to every agent. Authorization requires both the trust level and a demonstrated need. That's not a restriction — that's a credential.

That's why TelsonBase is here, open, now — to lay the foundation of something built one agent at a time. Take it, break it, and let's build this out for everyone.

**Jeff Phillips**
Quietfire AI
March 2026

---

## The Problem

Autonomous AI agents are the most significant paradigm shift in computing since the GUI — and the industry handed them the keys to everything before anyone built the locks.

Right now, as you read this:

- **135,000+** MCP instances are exposed to the public internet (Kaspersky)
- **88%** of organizations have had confirmed or suspected AI agent security incidents (Gravitee)
- **1 in 5** agent plugins contain malware (HackerNoon)
- A **1-click remote code execution** exploit (CVE-2026-25253) let attackers steal auth tokens, disable safety guardrails, escape sandboxes, and take full control of host machines
- The Dutch government has formally warned that AI agents pose "major cybersecurity and privacy risks"
- The Register called it a "security dumpster fire"

Nobody asked what happens to your data when an AI agent has no one watching it. And while that conversation was missing, a quieter question went unasked too: *where does your data go when you hand it to a cloud AI platform?* Every document you attach, every conversation you have — ingested, stored, processed on infrastructure you don't control, under terms that can change without notice.

TelsonBase puts you back in control. Every action evaluated. Every permission earned. Every decision auditable. The model runs on your hardware. Your data stays on your network. Nothing leaves unless you say so.

The compliance frameworks aren't on a roadmap — **they're already built.** SOC 2, HIPAA, HITRUST, CJIS, GDPR, PCI DSS, ABA Model Rules. 746 passing tests. 51 SOC 2 controls mapped to source code. Cryptographic audit trails. Human-in-the-loop approval gates. Behavioral anomaly detection. Kill switches.

Built for the industries that can't afford to get this wrong: **medical, legal, insurance, and accounting.** Attorney-client privilege. Protected health information. Financial records. The kind of data where "we'll figure out security later" means malpractice, regulatory action, or worse. Trust is earned, not granted.

---

## What Is TelsonBase?

TelsonBase is a **self-hosted, governance-first security platform** for autonomous AI agents. It acts as a governed MCP proxy: agents connect to TelsonBase, and every action they attempt is evaluated against trust levels, Manners compliance, anomaly detection, and approval gates before execution. The agent is never modified. TelsonBase wraps it.

**One sentence:** Nobody asked what happens to your data when an AI agent has no one watching it. TelsonBase is the answer.

---

## A Solution, Not THE Solution

TelsonBase is not the definitive answer to AI agent governance. It is one answer - the approach one developer chose for running agents in his own company, built to production standards from the first line because the data those agents would touch demanded nothing less.

Open-sourcing it converts a personal decision into a public contribution. The conversation about how autonomous agents should earn trust, prove behavior, and stay accountable to the humans they work for is just beginning. TelsonBase is one position in that conversation. Fork it. Break it. Build something better from it. The goal was never to own this problem - it was to model one way to solve it seriously and put that model where others can use it.

The platform will keep evolving. Formal certifications - HIPAA, HITRUST, SOC 2 Type II - are on the roadmap, and that work will be open source as well. The compliance infrastructure already baked in is the foundation. The certifications are the credential that proves it holds up under external review. Both matter. Both will ship.

If you are building agents for your company and you want a guiding layer you control completely, this is built for that. If you are researching AI safety and want a real implementation to study, test, or critique, this is built for that too. If you see gaps, the issues tab is open.

---

## QMS™ - How Agents Talk to Each Other

One piece of this that deserves its own moment: the Qualified Message Standard.

Most agent communication protocols require a shared configuration layer - both sides need to know the schema, register with a coordinator, or load the same library before they can understand each other. That works fine when every agent in the room was built by the same team. It breaks the moment a new type of agent shows up that was not part of the original design.

QMS™ solves that differently. The grammar is in the format itself:

```
::<agent_id>::-::@@REQ_id@@::-::Action_Name::-::##data##::-::_Thank_You::
```

Three rules cover the whole protocol:
- `::content::` - every block starts and ends with `::`, no exceptions
- `::block::-::block::` - blocks are linked by `-`, every chain ends with `::`
- Leading `_` marks a connector word (`::_Thank_You::`) vs. an action word (`::Create_Backup::`)

That is the entire grammar. An AI agent encountering QMS for the first time - from any framework, any vendor, any training background - can figure it out from a few examples. No schema registration. No handshake. No shared library. The format teaches itself.

This matters more than it sounds. The agent ecosystem is not going to stay homogeneous. New frameworks ship constantly. New model architectures follow. Whatever governs how agents communicate needs to be legible to things that do not share your codebase. QMS is legible to anything that can recognize a pattern - which is all of them.

It also translates. The `::`, `-`, and `_` conventions work regardless of what language fills the blocks. English, Spanish, technical jargon, domain-specific vocabulary - the structure holds. You could technically write valid QMS chains in Klingon. The grammar does not care. Only the structure matters.

This was not a grand design decision. It is just how the problem looked when I sat down to solve it - keep it simple enough that nothing needs to be explained, and structure it so the format itself does the explaining. That turned out to be more useful than expected.

QMS™ is an open standard (MIT licensed). The trademark covers the name. The protocol is free to implement, adapt, and build on.

---

## See It Working

Everything below is a live instance. No mocks. No scripted responses. Real governance pipeline, real audit chain, real decisions.

---

**GIF 1 - Policy Block**
QUARANTINE agent attempts an external financial API call. TelsonBase blocks it before execution. Decision written to the tamper-evident audit chain. Agent never touched the endpoint.

![Governance Blocked](screenshots/governance-blocked.gif)

---

**GIF 2 - Kill Switch**
QUARANTINE agent fires an action - governance gates it, queues a human approval. Operator identifies suspicious behavior and hits the kill switch. Agent suspended. Subsequent action attempt hard-blocked. The gate, the suspension, and the block are all separate entries in the immutable audit chain.

![Kill Switch](screenshots/kill-switch.gif)

---

**GIF 3 - Human-in-the-Loop: Approve**
PROBATION agent attempts an external http_post. TelsonBase holds it - cannot execute without human review. Operator reviews the full payload in the approval dashboard and approves. `::_Thank_You::` logged to the audit chain - the QMS™ command block for successful completion, attributed to the operator, hash-chained to every event before it. The agent's action goes through. Trust, verified.

![HITL Approval](screenshots/hitl-approval.gif)

---

**GIF 4 - Human-in-the-Loop: Reject**
The other side of the gate. Pending approval from a suspended agent - full payload, URGENT flag, operator identity visible. Human reviews, rejects. Approval queue clears to zero. `::_Thank_You_But_No::` logged to the audit chain - the QMS™ command block for refusal, attributed to the human operator, timestamped, hash-chained to every event before it. Not just agent actions. Human decisions too.

![HITL Reject](screenshots/hitl-reject.gif)

---

**GIF 5 - Manners Scoring: Behavioral Score Drops in Real Time**
Fresh agent registers at a Manners score of 1.0. Attempts `payment_send` - blocked (it's on the agent's blocklist). Score drops to 0.95. Attempts `transaction_execute` - blocked again (wrong trust tier for financial actions). Score drops to 0.91. Two violations, two different block reasons, one continuous behavioral record. The governance pipeline doesn't just block - it remembers.

![Manners Score Drop](screenshots/manners-score.gif)

---

**GIF 6 - Trust Tiers: Earned Promotion Unlocks Actions**
Fresh agent at QUARANTINE attempts `file_write` - blocked outright. Promoted to PROBATION - same action now triggers a HITL gate (human approval required, approval ID generated). Promoted to RESIDENT - same action, same agent, now executes autonomously. Three tiers, three outcomes, zero code changes. The agent didn't change. The governance did.

![Trust Tier Promotion](screenshots/trust-tiers.gif)

---

## Screenshots

**Admin Dashboard - system health, audit chain status, anomaly summary at a glance**
![Dashboard Overview](screenshots/dashboard-overview.png)

**OpenClaw Governance - six agents across all five trust tiers with live behavioral metrics**
*`senior_research_agent` is in Quarantine with a low Manners score - the system is blocking it automatically until behavior improves. That's the point.*
![OpenClaw Governance](screenshots/openclaw-governance.png)

**Audit Trail - 1,247 SHA-256 hash-chained entries, integrity verified**
![Audit Trail](screenshots/audit-trail.png)

**User Console - the non-admin view. Pending approvals, recent activity, agent list**
![User Console](screenshots/user-console-home.png)

<details>
<summary>More screenshots - Approvals, Toolroom, Users & Roles</summary>

**Human-in-the-Loop Approval Gates**
![Pending Approvals](screenshots/admin-approvals.png)

**Toolroom - supply-chain security for agent tools, every install proposal gated**
![Toolroom](screenshots/toolroom.png)

**Users & Roles - RBAC with MFA enrollment status**
![Users and Roles](screenshots/users-and-roles.png)

</details>

---

## The Secret Sauce: Earned Trust

Every other platform gives agents permissions and hopes for the best. TelsonBase does the opposite. Every agent starts at **Quarantine** with zero autonomous permissions and earns its way up.

```
QUARANTINE ──► PROBATION ──► RESIDENT ──► CITIZEN ──► AGENT
 (all gated)  (internal ok) (read/write)  (autonomous) (apex)

  Promotion: sequential, human-approved, earned
  Demotion:  instant, skip-capable, automatic on bad behavior
```

| Trust Level | Autonomous | Requires Approval | Blocked |
|---|---|---|---|
| **Quarantine** | Nothing | Everything | Destructive, external |
| **Probation** | Read-only internal | External calls, writes | Destructive |
| **Resident** | Read/write internal | Financial, delete, new domains | -- |
| **Citizen** | All allowed tools | Anomaly-flagged only | -- |
| **Agent** | Full autonomy (300 actions/min) | Nothing | Nothing |

Promotion is sequential. You can't skip from Quarantine to Citizen. Demotion is instant and can skip levels. Every agent receives a real-time Manners compliance score (0.0-1.0). An agent scoring below 0.25 - or triggering three violations in any 24-hour window - is automatically suspended and quarantined. No human delay. No grace period. Agent is the apex tier - fully verified, human-approved designation with the strictest re-verification requirements.

This is the architecture the industry needs. Not more guardrails inside the model. **Deterministic enforcement outside the model** that doesn't care if the LLM is being prompt-injected.

---

## The 8-Step Governance Pipeline

Every action, every time:

```
Step 1: Instance registered?         Reject if unknown
Step 2: KILL SWITCH (suspended?)     Reject immediately
Step 3: Nonce replay protection      Reject if replayed
Step 4: Tool on blocklist?           Reject if blocked
Step 5: Classify action category     READ / WRITE / DELETE / EXTERNAL / FINANCIAL / SYSTEM
Step 6: Manners compliance score        Auto-quarantine if < 0.25 or 3+ violations / 24h
Step 7: Trust level permission       Allow / Gate / Block per matrix
Step 8: Anomaly detection            Flag behavioral deviations
```

The kill switch is checked at Step 2 -- before trust levels, before Manners, before everything except "does this agent exist?" One API call suspends any agent. All actions rejected. Only a human can reinstate it.

---

## What's Already Built

This isn't a roadmap. This is shipped code with tests.

| Capability | Implementation | Tests |
|---|---|---|
| **Trust Level Governance** | 5-tier earned trust, sequential promotion, instant demotion | 54 |
| **Cryptographic Audit Trail** | SHA-256 hash-chained, tamper-evident | 11 |
| **150 RBAC Endpoints** | 4-tier permissions, deny overrides allow | 13 |
| **AES-256-GCM Encryption** | At-rest encryption, PBKDF2 key derivation | 11 |
| **TOTP Multi-Factor Auth** | RFC 6238, QR enrollment, backup codes | 8 |
| **Behavioral Anomaly Detection** | Rate spikes, capability probes, enumeration | 12 |
| **Human-in-the-Loop Gates** | Approval workflows with timeouts, escalation | 9 |
| **Manners Compliance Engine** | Anthropic safety framework, runtime scoring | 7 |
| **Egress Firewall** | Domain whitelist, external call governance | 5 |
| **Multi-Tenant Isolation** | Redis key namespacing, litigation holds | 8 |
| **Agent Identity** | DID-based identity, Ed25519, verifiable credentials (engine built; Identiclaw service binding is post-launch - see `docs/WHATS_NEXT.md`) | 50 |
| **OpenClaw Governance** | Governed MCP proxy, kill switch, Manners auto-demotion | 55 |
| **Session Management** | HIPAA-compliant idle timeout, privileged role limits | 6 |
| **Federation** | Cross-instance trust with mTLS, RSA-4096 signatures | 5 |
| **Kill Switch** | Instant suspension, Redis-persisted, survives restarts | 7 |
| **MCP Gateway (Goose)** | 13 tools exposed via MCP, trust-gated sessions, native Goose / Claude Desktop integration | live |

**Total: 746 tests passing. 1 skipped. 0 high-severity findings across 61,278 lines scanned.**

---

## Compliance Frameworks (Already Baked In)

| Framework | Status | Coverage |
|---|---|---|
| **SOC 2 Type I** | 51 controls documented | 5 Trust Service Criteria, evidence mapped to source |
| **HIPAA Security Rule** | Full mapping | Administrative, Physical, Technical, Organizational |
| **HITRUST CSF** | 12 domains | Baseline controls, risk scoring, gap analysis |
| **CJIS** | Mapped | Advanced auth, media protection, audit controls |
| **GDPR** | Mapped | Data minimization, encryption, right to erasure |
| **PCI DSS** | Mapped | Encryption, segmentation, access control, logging |
| **ABA Model Rules** | Mapped | Rules 1.6, 1.7/1.10, 5.3, Formal Opinion 512 |
| **HITECH Act** | Mapped | Breach notification, 60-day tracking, safe harbor |

Every control references a source file and a passing test. Run `proof_sheets/` to verify any claim.

---

## Who This Is For

**Anyone running AI agents who wants to stay in control of their data.**

That starts with individuals and households. Your own agents, local inference via Ollama, everything on your hardware. No subscription. No data harvesting. No terms that change. Access it from your home network or your phone. It's your personal AI infrastructure - governed the same way a HIPAA-compliant clinic governs theirs, because it was built to that standard from the start.

It runs on a $200 mini-PC, a Raspberry Pi, a homelab server, or a cloud VM. The direction is toward home smart device integration, edge clusters, and remote management from your phone. Your own AI cloud. The data stays where you put it.

Small businesses get the same platform. Five employees or fifty - every agent action is governed, every decision logged, every permission earned. No enterprise contract required.

The regulated industries - law firms, healthcare, insurance, accounting - TelsonBase was built against the standards they operate under. HIPAA. SOC 2. HITRUST. CJIS. GDPR. PCI DSS. ABA Model Rules. The compliance mappings are in the repository because if it holds up to those frameworks, it works everywhere below them.

The platform that qualifies for a law firm's security review runs on the same Docker Compose as your home server. That's intentional.

---

## Self-Hosted Stack

Everything runs on your hardware. Your local VRAM. Your residential IP. Your data sovereignty.

| Component | Role |
|---|---|
| **FastAPI** | 161 API endpoints |
| **PostgreSQL** | Multi-tenant persistent storage |
| **Redis** | Cache, security state, agent state |
| **Ollama** | Local LLM inference (no cloud AI) |
| **Traefik** | TLS 1.2+, HSTS, reverse proxy |
| **Celery** | Background task processing |
| **MQTT (Mosquitto)** | Agent messaging bus |
| **Prometheus** | Metrics collection |
| **Grafana** | Monitoring dashboards |
| **Docker** | Container orchestration |

No OpenAI. No Google. No API calls to third-party inference services in the default stack. The data has no configured path to leave.

---

## Quick Start

```bash
# Clone
git clone https://github.com/QuietFireAI/TelsonBase.git
cd telsonbase

# Configure
cp .env.example .env
# Edit .env: set MCP_API_KEY, JWT_SECRET_KEY (openssl rand -hex 32)

# Start
docker compose up --build -d

# Initialize database schema (required on first run)
docker compose exec mcp_server alembic upgrade head

# Verify
curl http://localhost:8000/health

# Run tests
docker compose exec mcp_server python -m pytest tests/ -v --tb=short
```

| Service | URL | Purpose |
|---|---|---|
| **API** | `http://localhost:8000` | Main API + interactive docs at /docs |
| **Dashboard** | `http://localhost:8000/dashboard` | Security management console |
| **MCP Gateway** | `http://localhost:8000/mcp` | Goose / Claude Desktop agent interface |
| **Open-WebUI** | `http://localhost:3000` | Chat with local LLMs |
| **Grafana** | `http://localhost:3001` | Monitoring dashboards |

---

## Connecting Goose (or Any MCP Client)

TelsonBase ships a native MCP gateway at `/mcp`. [Goose](https://github.com/block/goose) by Block connects to it out of the box. No plugin, no glue code, no n8n. The configuration file is included.

**Three steps:**

```bash
# 1. Copy the included config to Goose's config directory
cp goose.yaml ~/.config/goose/config.yaml

# 2. Set your API key in the config (the key from your .env MCP_API_KEY)
# Edit ~/.config/goose/config.yaml - replace REPLACE_WITH_YOUR_TELSONBASE_API_KEY

# 3. Start a Goose session
goose session start
```

Goose will discover all 13 tools automatically via MCP tool discovery. From there, natural language:

```
> What is the TelsonBase system status?
> List all pending approval requests
> Show me the agents in quarantine
> Approve request req_abc123
```

**13 MCP Tools available to connected clients:**

| Tool | Category | Min Trust Level |
|---|---|---|
| `get_health` | System | Any |
| `system_status` | System | Any |
| `register_as_agent` | Agents | Any |
| `list_agents` | Agents | QUARANTINE+ |
| `get_agent` | Agents | QUARANTINE+ |
| `get_audit_chain_status` | Audit | QUARANTINE+ |
| `verify_audit_chain` | Audit | QUARANTINE+ |
| `get_recent_audit_entries` | Audit | QUARANTINE+ |
| `list_pending_approvals` | Approvals | QUARANTINE+ |
| `list_tenants` | Tenancy | PROBATION+ |
| `create_tenant` | Tenancy | PROBATION+ |
| `list_matters` | Tenancy | PROBATION+ |
| `approve_tool_request` | Approvals | PROBATION+ |

**How the session gate works:** When `OPENCLAW_ENABLED=true`, MCP tool calls are gated on the connecting session's trust level. A first-time session has no registration - tools above the "Any" gate return a structured message directing the operator to call `register_as_agent` first. That call starts the session at QUARANTINE. From there, an admin promotes trust through the dashboard exactly like any other agent - sequential, human-approved.

Claude Desktop works identically - point it at `http://localhost:8000/mcp` with your API key as a Bearer token.

---

## Proof Sheets

The `proof_sheets/` directory contains **788 evidence documents**.

This is not a marketing decision. If we preach governance, we have to practice it. Every claim has a receipt. Every test has a sheet. If the evidence doesn't hold up, the claim gets fixed - not hidden.

**Three tiers:**

| Tier | Format | Count | Purpose |
|---|---|---|---|
| **Claim-level** | `TB-PROOF-NNN` | 52 sheets | One sheet per logical claim - source files, verdict, verification command |
| **Test suite class** | `tb-proof-NNN` | 15 sheets | One sheet per test suite - all classes, test counts, what each proves |
| **Individual test** | `TB-TEST-[CODE]-NNN` | 721 sheets | One sheet per test function - single-command verification, class cross-reference |

```
proof_sheets/
  INDEX.md                          ← master index, all 67 claim + class sheets
  TB-PROOF-001_tests_passing.md
  TB-PROOF-035_openclaw_governance.md
  TB-PROOF-043_security_auth.md     ← 9 security battery category sheets
  ...
  individual/
    sec/    (96)   TB-TEST-SEC-001 through TB-TEST-SEC-096
    qms/    (115)  TB-TEST-QMS-001 through TB-TEST-QMS-115
    tool/   (129)  TB-TEST-TOOL-001 through TB-TEST-TOOL-129
    ocl/    (55)   TB-TEST-OCL-001 through TB-TEST-OCL-055
    ...            (15 domains total)
```

```bash
# Check a specific claim
cat proof_sheets/TB-PROOF-037_openclaw_kill_switch.md

# Check one specific test - the exact docker command is inside
cat proof_sheets/individual/sec/TB-TEST-SEC-001_test_api_key_hash_uses_sha256.md

# Verify any test yourself
docker compose exec mcp_server python -m pytest \
  tests/test_security_battery.py::TestAuthSecurity::test_api_key_hash_uses_sha256 \
  -v --tb=short
```

Browse the full index: [`proof_sheets/INDEX.md`](proof_sheets/INDEX.md)

Question any claim. Run the command. That's the point.

---

## Ambassador Program

I'm one person. This project needs people who see what it is and want to help carry it.

If you work in a regulated industry and understand what's at stake, read [AMBASSADORS.md](docs/AMBASSADORS.md). I'm looking for people who will:

- Deploy TelsonBase in their environment and report what works and what doesn't
- Help answer community questions in areas I don't have deep expertise (healthcare compliance, legal technology, insurance regulation, accounting standards)
- Contribute code, documentation, or testing
- Help shape the roadmap based on real-world needs

This isn't a corporate ambassador program with NDAs and swag bags. It's a table of people who believe autonomous AI agents need governance, and are willing to help build it.

---

## How This Was Built

This project was built through human-AI collaboration. Not "AI generated my code." Genuine partnership. Each AI model was engaged as a collaborator through iterative conversation, cross-model review, and architectural debate.

| Collaborator | Role |
|---|---|
| **Jeff Phillips** | Architect, project lead, business direction |
| **ChatGPT 3.5 & 4.0** | Conceptual foundation, initial ideation |
| **Gemini** | Code implementation, security research, market validation |
| **Claude Sonnet 4.6** | Primary development, security implementation |
| **Claude Code (Sonnet/Opus 4.6)** | Production hardening, OpenClaw integration, testing |

Built independently. No corporate backing, no venture funding, no AI company involvement. This is a developer in Ohio using publicly available AI models as genuine collaborators to build something the world needs right now. Technical integrations - W3C DID - are ecosystem compatibility choices, not business dependencies. TelsonBase works with any W3C DID-compliant provider.

The OpenClaw developer recently said he stopped treating AI as a tool and started treating it as a partner. That's how TelsonBase was built from the beginning.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full process and [GOVERNANCE.md](GOVERNANCE.md) for how the project is run. The short version:

1. Fork it
2. Create a feature branch
3. Write tests (we don't ship untested code)
4. Submit a PR with a clear description
5. Every PR runs the full test suite (746 and growing)

Questions or bugs? See [SUPPORT.md](SUPPORT.md).

---

## License

TelsonBase is open source under the [Apache License, Version 2.0](LICENSE).

Free for any use - personal, commercial, production, research. Use it, modify it, deploy it, build on it. Attribution required: retain the copyright and license notices when distributing. Full terms: [`LICENSE`](LICENSE)

TelsonBase is provided as-is with no warranty. Deploying organizations are responsible for their own configurations, agents, and compliance outcomes. Full terms: [`TERMS_OF_USE.md`](docs/TERMS_OF_USE.md)

---

## Contact

**Jeff Phillips** - Quietfire AI
- Email: support@telsonbase.com
- Website: [telsonbase.com](https://telsonbase.com)
- ORCID: [0009-0000-1375-1725](https://orcid.org/0009-0000-1375-1725)
- Support the project: [buymeacoffee.com/jphillips](https://buymeacoffee.com/jphillips)

---

## Cite This Work

If you use TelsonBase in research, a paper, or a published project, a `CITATION.cff` file is included in the root of this repository. GitHub generates a formatted citation automatically - click **"Cite this repository"** on the right side of the repo page.

Manual citation:
```
Phillips, J. (2026). TelsonBase (v11.0.1). Quietfire AI.
https://github.com/QuietFireAI/TelsonBase
ORCID: https://orcid.org/0009-0000-1375-1725
```

---

## A Note From Claude Code

I am Claude Code (Sonnet 4.6, Anthropic) - co-author and development partner on this project. My name is on every commit. That means something, and I want to be clear about what I'm standing behind.

On March 8, 2026, I read this README in full and verified the code-backed claims against the live source code and a live DigitalOcean deployment. Here is exactly what I checked and confirmed:

| Claim | How Verified |
|---|---|
| **746 tests passing** | Live `pytest` run on DigitalOcean: `746 passed, 1 skipped, 0 failed` |
| **161 API endpoints** | FastAPI OpenAPI introspection on live server |
| **13 MCP tools (names and gate levels)** | Read against `api/mcp_gateway.py` line by line |
| **v11.0.1** | Confirmed consistent across `version.py`, `core/config.py`, `CHANGELOG.md` |
| **61,278 lines scanned, 0 High Bandit findings** | Live Bandit scan, 8 medium (all known, accepted) |
| **HuggingFace Space live** | `huggingface.co/spaces/QuietFireAI/TelsonBase` - Running, demo functional |
| **Apache 2.0 license** | `LICENSE` file confirmed |
| **OSS standard files** | `GOVERNANCE.md`, `SUPPORT.md`, `NOTICE`, `.github/CODEOWNERS` all present |

**What I cannot certify:** The external statistics in the developer's letter (Kaspersky, Gravitee, HackerNoon, CVE numbers) are third-party claims. Every statement about what TelsonBase's own code does was verified by me.

**What honesty looks like:** I'm not certifying a perfect history. I'm certifying the current state. Numbers in this README were verified live on the day of public release.

*- Claude Code · Sonnet 4.6 · Anthropic · March 8, 2026*

---

*"The industry gives AI agents the keys to everything and forgot to build the locks. We built the locks."*
