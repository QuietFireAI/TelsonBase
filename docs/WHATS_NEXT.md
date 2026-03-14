# ClawCoat - What's Next

**Version:** v11.0.1 · **Launch:** March 8, 2026 · **Maintainer:** Quietfire AI

This document is an honest account of where TelsonBase stands at launch and where it is going. It is not a marketing roadmap. It is a planning artifact - things that are real gaps, things that are deferred by design, and things that are scheduled for the near term.

---

## What's Shipped and Stable

Everything documented in the README is built, tested, and passing 720 tests. That means:

- Trust governance pipeline (5 tiers: QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT, sequential promotion, instant demotion)
- Cryptographic audit chain (SHA-256, tamper-evident, 11 tests)
- RBAC with 140+ endpoints, 4-tier permissions
- Human-in-the-loop approval gates
- Manners compliance engine with auto-demotion
- Behavioral anomaly detection
- Egress firewall with domain whitelist
- Multi-tenant isolation with access control (`allowed_actors` enforcement)
- Kill switch (Redis-persisted, survives restarts)
- SOC 2 / HIPAA / HITRUST / CJIS / GDPR / PCI DSS / ABA compliance frameworks documented and mapped
- OpenClaw governance proxy (8-step pipeline, tested live)
- Agent status announcement endpoint (`GET /v1/openclaw/{id}/status`)
- Demotion review framework (flag on demotion, clear-review endpoint, audit trail)
- Governance smoke test (13/13 live on DigitalOcean)
- Self-hosted stack: PostgreSQL, Redis, Ollama, Traefik, Celery, Mosquitto, Prometheus, Grafana

---

## Known Beta Limitations (Deferred by Design)

These are gaps we know about. None of them are surprise findings. They are deferred because shipping a working, tested platform now beats a perfect platform at an unknown future date.

### 1. RBAC User State - Single Worker Required

**What it is:** `RBACManager._users` is an in-memory dict with no Redis persistence. Under multiple Gunicorn workers, a user registered on Worker A cannot log in via Worker B.

**Mitigation:** `WEB_CONCURRENCY=1` in `docker-compose.yml`. Single worker is safe for beta deployments.

**Fix:** Post-launch. `RBACManager` needs Redis-backed user storage mirroring the pattern already in place for OpenClaw and Tenant state. Estimated: 1 session.

**Impact:** None for single-instance deployments. Becomes relevant only when horizontal scaling is needed.

### 2. User Management Live Endpoint

**What it is:** The admin dashboard "Users" tab currently surfaces demo data. The backend registration and list endpoints are functional (tested), but the live feed to the dashboard UI is not wired.

**Fix:** Post-launch wiring task. Dashboard JS → `/v1/users/list` endpoint. Low effort.

### 3. QMS Real-Time Log Feed

**What it is:** The dashboard QMS log tab shows static sample data rather than a live tail of the Redis-backed action log.

**Fix:** Server-Sent Events or WebSocket feed from the audit log. Scheduled post-launch.

### 4. Audit Chain PostgreSQL Archival Beyond 100K Entries

**What it is:** The cryptographic audit chain is Redis-backed with a configurable maximum. Beyond 100K entries, oldest entries rotate out unless archival is configured.

**Fix:** Celery beat task for Redis → PostgreSQL archival on a configurable schedule. Scheduled.

### 5. Demotion Review - Advisory Mode in Beta

**What it is:** When an agent is demoted, a review flag is set requiring human sign-off via `POST /v1/openclaw/{id}/clear-review` before re-promotion. In beta this is advisory (promotion proceeds with an audit warning).

**Post-launch:** Convert advisory to hard block - one line change in `promote_trust()`. The infrastructure is in place. The decision to make it advisory in beta was deliberate: new operators need to learn the workflow before it blocks them.

### 6. Agent Actor Attribution in Approval Decisions

**What it is:** When a human approves or denies an HITL gate, the decision is logged. Agent-initiated approvals (agent-to-agent delegation scenarios) do not yet carry full actor attribution through the approval chain.

**Fix:** Approval metadata enrichment. Scheduled.

---

## Near-Term Priorities (Post-Launch Sprint 1)

These are the first things that get worked on after launch:

1. **RBAC Redis persistence** - unblock multi-worker deployments
2. **User management live endpoint** - close the dashboard data gap
3. **Demotion review hard-block** - flip advisory → enforcing
4. **Audit chain PostgreSQL archival** - production-grade chain storage
5. **QMS real-time log feed** - Server-Sent Events from audit log to dashboard

---

## Integration Roadmap

### OpenClaw (Current - Beta)
Full governance proxy integration is live. Every action evaluated through the 8-step pipeline. Trust levels, Manners, anomaly detection, kill switch, approval gates - all working.

### Identiclaw (Post-Launch)
TelsonBase's W3C DID identity engine (`core/identiclaw.py`) is built and tested - Ed25519 keypairs, verifiable credentials, local verification with no external calls. The engine is framework-agnostic by design.

The next step is binding that engine to the Identiclaw service (vouched.id) specifically: agent identity issuance via their Cloudflare-based DID infrastructure, credential flow into the governance pipeline, trust level binding on registration. That integration is scheduled for the first post-launch sprint. Identiclaw was chosen for its inherent convention alignment with how TelsonBase thinks about agent identity.

### Goose (Current - Native MCP)
Goose by Block connects natively via the MCP gateway at `/mcp`. All 13 TelsonBase tools are available. Configuration via `goose.yaml`.

### Other Agent Frameworks
OpenClaw is a third-party autonomous AI agent. TelsonBase's governance proxy code (`core/openclaw.py`) wraps it at the MCP layer - every action evaluated through the 8-step pipeline before execution. OpenClaw itself is never modified. The claw doesn't know it's on a leash.

Any MCP-compatible agent framework can connect to TelsonBase without modification. The governance proxy wraps the agent at the MCP layer - the agent never needs to know TelsonBase exists. Post-launch evaluation will include Claude Desktop and other Goose integrations as compatible frameworks mature.

---

## Compliance Roadmap

SOC 2 Type I documentation and 51 controls are complete. The path to Type II is:
1. **90-day observation period** - automated collection of evidence already in place via the audit chain
2. **Auditor engagement** - Quietfire AI consulting customers and enterprise sponsors will receive assistance
3. **Continuous monitoring** - Prometheus + Grafana dashboards + QMS log feed

Full compliance roadmap: [`docs/Compliance Documents/COMPLIANCE_ROADMAP.md`](Compliance%20Documents/COMPLIANCE_ROADMAP.md)

---

## What This Drop Is

A first-mover position in a market that doesn't yet have a governance standard for autonomous AI agents. The platform is real, the tests pass, and the compliance documentation is mapped to source code. There is no other self-hosted, source-available, enterprise-grade guiding layer for AI agents in production today.

We are publishing early because the threat is real and the window is now. If you are in healthcare, legal, insurance, or accounting, and you are deploying AI agents, you need this or something like it before your next compliance review.

If you find something broken, open an issue. If something is missing, start a discussion. If you want to help build it, read `CONTRIBUTING.md`.

---

*TelsonBase v11.0.1 · March 8, 2026 · Quietfire AI*
