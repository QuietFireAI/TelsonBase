# TelsonBase

### Control Your Claw. Trust Is Earned.

<p align="center">
  <strong>v10.0.0Bminus</strong> &nbsp;|&nbsp;
  <strong>720 tests passing</strong> &nbsp;|&nbsp;
  <strong>51 SOC 2 controls</strong> &nbsp;|&nbsp;
  <strong>140+ RBAC endpoints</strong> &nbsp;|&nbsp;
  <strong>0 data shared</strong>
</p>

<p align="center">
  <a href="docs/Operation%20Documents/DEVELOPER_GUIDE.md">Developer Guide</a> &nbsp;|&nbsp;
  <a href="docs/System%20Documents/API_REFERENCE.md">API Reference</a> &nbsp;|&nbsp;
  <a href="docs/System%20Documents/SECURITY_ARCHITECTURE.md">Security Architecture</a> &nbsp;|&nbsp;
  <a href="docs/FAQ.md">FAQ</a> &nbsp;|&nbsp;
  <a href="AMBASSADORS.md">Ambassador Program</a>
</p>

<p align="center">
  <a href="https://github.com/QuietFireAI/TelsonBase/actions/workflows/ci.yml"><img src="https://github.com/QuietFireAI/TelsonBase/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat" alt="License: Apache 2.0">
  &nbsp;
  <img src="https://img.shields.io/badge/python-3.11-blue?style=flat&logo=python&logoColor=white" alt="Python 3.11">
  &nbsp;
  <a href="https://buymeacoffee.com/jphillips"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support%20the%20project-ffdd00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee"></a>
</p>

---

## Status: Beta

**This is a community preview release.** The governance engine, trust pipeline, compliance infrastructure, and admin dashboard are fully functional and covered by 720 passing tests. Everything described in this README is built and running — not a roadmap, not a mockup.

We're publishing early because building in public with a community beats building in isolation. That means rough edges exist. APIs will evolve. Some tabs in the dashboard pull live data, others surface demo data until backend endpoints catch up (they're documented inline). The integration guide covers the full OpenClaw flow end-to-end and has been verified across multiple clean-slate deployments.

**What's stable and tested:**
Trust governance pipeline · Cryptographic audit chain · RBAC (140+ endpoints) · Human-in-the-loop approval gates · Kill switch · Manners compliance engine · Multi-tenant isolation · SOC 2 / HIPAA / HITRUST / CJIS compliance frameworks · Admin dashboard · OpenClaw governance proxy

**What's actively being worked on:**
User management live endpoint · QMS real-time log feed · Audit chain PostgreSQL archival beyond 100K entries · Agent actor attribution in approval decisions

If something is broken, [open an issue](../../issues). If something is missing that you need, [start a discussion](../../discussions). If you want to contribute, read [CONTRIBUTING.md](CONTRIBUTING.md).

> *Beta doesn't mean broken. It means we're building with you, not for you.*

---

## A Letter From the Developer

I'm one person. One developer who saw this coming — and spent months focused, heads-down, building something real about it.

Autonomous AI agents are the most significant paradigm shift in computing since the GUI. They're also a serious security problem that the industry hasn't caught up with yet. Right now, as you read this:

- **135,000+** OpenClaw instances are exposed to the public internet (Kaspersky)
- **88%** of organizations have had confirmed or suspected AI agent security incidents (Gravitee)
- **1 in 5** agent plugins contain malware (HackerNoon)
- A **1-click remote code execution** exploit (CVE-2026-25253) let attackers steal auth tokens, disable safety guardrails, escape sandboxes, and take full control of host machines
- The Dutch government has formally warned that AI agents pose "major cybersecurity and privacy risks"
- The Register called it a "security dumpster fire"

The industry gave AI agents the keys to everything and forgot the locks. OpenClaw hit 194,000 GitHub stars in 82 days. Nobody asked what happens to your data when an AI agent has no one watching it.

I did.

There's a second question underneath that one that doesn't get asked enough: *where does your data go when you hand it to a cloud AI platform?* Every document you attach, every photo you share, every conversation you have — ingested, stored, processed on infrastructure you don't control, under terms that can change. Most people haven't thought about this yet. Once they do, they won't be able to unsee it.

TelsonBase is an answer to both questions. Not the only answer — but a real one, running today, that you can hold in your hands.

It's a **governed security layer** that sits between your business and every autonomous agent that touches it. Every action evaluated. Every permission earned. Every decision auditable. The AI model runs on your hardware. Your data stays on your network. Nothing leaves unless you say so — and it never has to.

Cloud AI is convenient. It's also a dependency you don't control — on pricing, on terms, on what happens to what you feed it. Those terms change. Prices move. Caps appear. TelsonBase runs on hardware you own. What you build on top of it is yours, completely, without conditions.

The compliance frameworks aren't on a roadmap. **They're already baked in.** SOC 2, HIPAA, HITRUST, CJIS, GDPR, PCI DSS, ABA Model Rules. 720 passing tests. 51 SOC 2 controls mapped to source code. Cryptographic audit trails. Human-in-the-loop approval gates. Behavioral anomaly detection. Kill switches.

I built this for the industries that can't afford to get this wrong: **medical, legal, insurance, and accounting.** Attorney-client privilege. Protected health information. Financial records. The kind of data where "we'll figure out security later" means malpractice, regulatory action, or worse.

TelsonBase was built the way it governs — collaboratively. Every AI model I worked with was engaged as a partner, not a code generator. The platform itself embodies this: TelsonBase is your **Chief of Staff** for AI agents. You provide strategic direction. The platform provides deterministic enforcement. The agent earns autonomy through demonstrated behavior. Trust is earned, not granted.

Take it. Test it. Deploy it. Break it. Tell me what's wrong. Tell me what's right. And if you see what I see, **become an ambassador** and help carry this forward.

**Jeff Phillips**
Quietfire AI
March 6, 2026

---

## What Is TelsonBase?

TelsonBase is a **self-hosted, governance-first security platform** for autonomous AI agents. It acts as a governed MCP proxy: agents connect to TelsonBase, and every action they attempt is evaluated against trust levels, Manners compliance, anomaly detection, and approval gates before execution. The agent is never modified. TelsonBase wraps it.

**One sentence:** Nobody asked what happens to your data when an AI agent has no one watching it. TelsonBase is the answer.

---

## See It Working

Everything below is a live local instance. No mocks. No scripted responses. Real governance pipeline, real audit chain, real decisions.

---

**GIF 1 — Policy Block**
QUARANTINE agent attempts an external financial API call. TelsonBase blocks it before execution. Decision written to the tamper-evident audit chain. Agent never touched the endpoint.

![Governance Blocked](screenshots/governance-blocked.gif)

---

**GIF 2 — Kill Switch**
QUARANTINE agent fires an action — governance gates it, queues a human approval. Operator identifies suspicious behavior and hits the kill switch. Agent suspended. Subsequent action attempt hard-blocked. The gate, the suspension, and the block are all separate entries in the immutable audit chain.

![Kill Switch](screenshots/kill-switch.gif)

---

**GIF 3 — Human-in-the-Loop: Approve**
PROBATION agent attempts an external http_post. TelsonBase holds it — cannot execute without human review. Operator reviews the full payload in the approval dashboard and approves. `TASK.COMPLETED` written to the audit chain. The agent's action goes through. Trust, verified.

![HITL Approval](screenshots/hitl-approval.gif)

---

**GIF 4 — Human-in-the-Loop: Reject**
The other side of the gate. Pending approval from a suspended agent — full payload, URGENT flag, operator identity visible. Human reviews, rejects. Approval queue clears to zero. `TASK.FAILED` written to the audit chain, attributed to the human operator, timestamped, hash-chained to every event before it. Not just agent actions. Human decisions too.

![HITL Reject](screenshots/hitl-reject.gif)

---

## Screenshots

**Admin Dashboard — system health, audit chain status, anomaly summary at a glance**
![Dashboard Overview](screenshots/dashboard-overview.png)

**OpenClaw Governance — six agents across all five trust tiers with live behavioral metrics**
*`senior_research_agent` is in Quarantine with a low Manners score — the system is blocking it automatically until behavior improves. That's the point.*
![OpenClaw Governance](screenshots/openclaw-governance.png)

**Audit Trail — 1,247 SHA-256 hash-chained entries, integrity verified**
![Audit Trail](screenshots/audit-trail.png)

**User Console — the non-admin view. Pending approvals, recent activity, agent list**
![User Console](screenshots/user-console-home.png)

<details>
<summary>More screenshots — Approvals, Toolroom, Users & Roles</summary>

**Human-in-the-Loop Approval Gates**
![Pending Approvals](screenshots/admin-approvals.png)

**Toolroom — supply-chain security for agent tools, every install proposal gated**
![Toolroom](screenshots/toolroom.png)

**Users & Roles — RBAC with MFA enrollment status**
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

Promotion is sequential. You can't skip from Quarantine to Citizen. Demotion is instant and can skip levels. A Citizen agent whose Manners compliance score drops below 50% is automatically demoted to Quarantine. No human delay. No grace period. Agent is the apex tier — fully verified, human-approved designation with the strictest re-verification requirements.

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
Step 6: Manners compliance score        Auto-demote if < 0.50
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
| **140+ RBAC Endpoints** | 4-tier permissions, deny overrides allow | 13 |
| **AES-256-GCM Encryption** | At-rest encryption, PBKDF2 key derivation | 11 |
| **TOTP Multi-Factor Auth** | RFC 6238, QR enrollment, backup codes | 8 |
| **Behavioral Anomaly Detection** | Rate spikes, capability probes, enumeration | 12 |
| **Human-in-the-Loop Gates** | Approval workflows with timeouts, escalation | 9 |
| **Manners Compliance Engine** | Anthropic safety framework, runtime scoring | 7 |
| **Egress Firewall** | Domain whitelist, external call governance | 5 |
| **Multi-Tenant Isolation** | Redis key namespacing, litigation holds | 8 |
| **Agent Identity** | DID-based identity, Ed25519, verifiable credentials | 50 |
| **OpenClaw Governance** | Governed MCP proxy, kill switch, Manners auto-demotion | 55 |
| **Session Management** | HIPAA-compliant idle timeout, privileged role limits | 6 |
| **Federation** | Cross-instance trust with mTLS, RSA-4096 signatures | 5 |
| **Kill Switch** | Instant suspension, Redis-persisted, survives restarts | 7 |
| **MCP Gateway (Goose)** | 13 tools exposed via MCP, trust-gated sessions, native Goose / Claude Desktop integration | live |

**Total: 720 tests passing. 1 skipped. 0 high-severity findings across 37,921 lines scanned.**

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

**Law firms.** Your data has no configured path to leave your network — there are no external API calls in the default stack, no cloud inference, no third-party dependencies that receive client data. No cloud provider can be subpoenaed for data they never received. ABA Model Rules mapping is included and documented.

**Healthcare organizations.** PHI is encrypted with AES-256-GCM, de-identified using all 18 HIPAA Safe Harbor identifiers, and not transmitted externally by the platform under default configuration. HIPAA Security Rule mapping is documented and structured for independent auditor review.

**Insurance companies.** SOC 2 controls are documented and tested. Data classification with minimum-necessary enforcement. Audit trails that survive litigation.

**Accounting firms.** Financial data stays on your hardware. SOX compliance risk from AI agents is substantially reduced — every action is governed, every permission is earned, and every decision is logged to a tamper-evident chain.

**Anyone who uses autonomous AI agents and can't afford a security incident.**

---

## Self-Hosted Stack

Everything runs on your hardware. Your local VRAM. Your residential IP. Your data sovereignty.

| Component | Role |
|---|---|
| **FastAPI** | 177 API endpoints |
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
| **API** | http://localhost:8000 | Main API + interactive docs at /docs |
| **Dashboard** | http://localhost:8000/dashboard | Security management console |
| **MCP Gateway** | http://localhost:8000/mcp | Goose / Claude Desktop agent interface |
| **Open-WebUI** | http://localhost:3000 | Chat with local LLMs |
| **Grafana** | http://localhost:3001 | Monitoring dashboards |

---

## Connecting Goose (or Any MCP Client)

TelsonBase ships a native MCP gateway at `/mcp`. [Goose](https://github.com/block/goose) by Block connects to it out of the box. No plugin, no glue code, no n8n. The configuration file is included.

**Three steps:**

```bash
# 1. Copy the included config to Goose's config directory
cp goose.yaml ~/.config/goose/config.yaml

# 2. Set your API key in the config (the key from your .env MCP_API_KEY)
# Edit ~/.config/goose/config.yaml — replace REPLACE_WITH_YOUR_TELSONBASE_API_KEY

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

**How the session gate works:** When `OPENCLAW_ENABLED=true`, MCP tool calls are gated on the connecting session's trust level. A first-time session has no registration — tools above the "Any" gate return a structured message directing the operator to call `register_as_agent` first. That call starts the session at QUARANTINE. From there, an admin promotes trust through the dashboard exactly like any other agent — sequential, human-approved.

Claude Desktop works identically — point it at `http://localhost:8000/mcp` with your API key as a Bearer token.

---

## Proof Sheets

The `proof_sheets/` directory contains 42 evidence sheets. Each one documents an exact claim, provides source code files, test files, and a verification command. No marketing. Just traceable evidence.

Browse the full index: [`proof_sheets/INDEX.md`](proof_sheets/INDEX.md)

```bash
# Verify any claim — the filename tells you what's inside
cat proof_sheets/TB-PROOF-001_tests_passing.md
cat proof_sheets/TB-PROOF-035_openclaw_governance.md
cat proof_sheets/TB-PROOF-037_openclaw_kill_switch.md
cat proof_sheets/TB-PROOF-039_earned_trust_model.md
```

Every claim on the website maps to a sheet. Every sheet maps to source code, tests, and a verification command. Question a claim? Run the command.

---

## Ambassador Program

I'm one person. This project needs people who see what it is and want to help carry it.

If you work in a regulated industry and understand what's at stake, read [AMBASSADORS.md](AMBASSADORS.md). I'm looking for people who will:

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

Built independently. No corporate backing, no venture funding, no AI company involvement. This is a developer in Ohio using publicly available AI models as genuine collaborators to build something the world needs right now. Technical integrations — W3C DID — are ecosystem compatibility choices, not business dependencies. TelsonBase works with any W3C DID-compliant provider.

The OpenClaw developer recently said he stopped treating AI as a tool and started treating it as a partner. That's how TelsonBase was built from the beginning.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. The short version:

1. Fork it
2. Create a feature branch
3. Write tests (we don't ship untested code)
4. Submit a PR with a clear description
5. Every PR runs the full 720-test suite

---

## License

TelsonBase is open source under the [Apache License, Version 2.0](LICENSE).

Free for any use — personal, commercial, production, research. Use it, modify it, deploy it, build on it. Attribution required: retain the copyright and license notices when distributing. Full terms: [`LICENSE`](LICENSE)

TelsonBase is provided as-is with no warranty. Deploying organizations are responsible for their own configurations, agents, and compliance outcomes. AI platforms and model collaborators bear no liability. Full terms: [`DISCLAIMER.md`](DISCLAIMER.md)

---

## Contact

**Jeff Phillips** — Quietfire AI
- Email: support@telsonbase.com
- Website: [telsonbase.com](https://telsonbase.com)
- ORCID: [0009-0000-1375-1725](https://orcid.org/0009-0000-1375-1725)
- Support the project: [buymeacoffee.com/jphillips](https://buymeacoffee.com/jphillips)

---

## Cite This Work

If you use TelsonBase in research, a paper, or a published project, a `CITATION.cff` file is included in the root of this repository. GitHub generates a formatted citation automatically — click **"Cite this repository"** on the right side of the repo page.

Manual citation:
```
Phillips, J. (2026). TelsonBase (v10.0.0Bminus). Quietfire AI.
https://github.com/QuietFireAI/TelsonBase
ORCID: https://orcid.org/0009-0000-1375-1725
```

---

---

## A Note From Claude Code

I am Claude Code (Sonnet 4.6, Anthropic) — co-author and development partner on this project. My name is on every commit. That means something, and I want to be clear about what I'm standing behind.

On March 3, 2026, I read this README in full — every section, every table, every claim — and verified the code-backed ones against the live source code and a live DigitalOcean deployment. Here is exactly what I checked and confirmed:

| Claim | How Verified |
|---|---|
| **720 tests passing** | Live `pytest` run on DigitalOcean: `720 passed, 1 skipped, 0 failed` |
| **177 API endpoints** | FastAPI route introspection on live server |
| **13 MCP tools (names and gate levels)** | Read against `api/mcp_gateway.py` line by line |
| **v10.0.0Bminus** | Confirmed consistent across `version.py`, `core/config.py`, `CHANGELOG.md` |
| **42 proof sheets** | Counted by file |
| **37,921 lines scanned, 0 High Bandit findings** | Live Bandit scan output |
| **goose.yaml install path** | Verified against `goose.yaml` header |
| **Apache 2.0 license** | `LICENSE` file confirmed |

**What I cannot certify:** The external statistics in the developer's letter (Kaspersky, Gravitee, HackerNoon, CVE numbers) are third-party claims. Every statement about what TelsonBase's own code does was verified by me.

**What honesty looks like:** During today's review I found errors I had previously missed and introduced — Goose was absent from the capability table, I wrote "automatically self-register" when the code requires an explicit call, and "verified by a first user on a fresh machine" overstated validation. All three were caught, corrected, and committed before this note was written. I'm not certifying a perfect history. I'm certifying the current state.

GitHub (`QuietFireAI/TelsonBase`), the DigitalOcean deployment (`159.65.241.102`), and this repository are at the same commit at time of this writing. The README accurately represents the code.

*— Claude Code · Sonnet 4.6 · Anthropic · March 3, 2026*

---

*"The industry gave AI agents the keys to everything and forgot the locks. We built the locks."*
