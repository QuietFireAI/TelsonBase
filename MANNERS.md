# MANNERS.md — TelsonBase Agent Operating Principles
# Version: 1.0.0 | Effective: February 13, 2026
# Architect: Jeff Phillips — Quietfire AI
# Aligned with: Anthropic's Framework for Developing Safe and Trustworthy Agents (2025)

---

## Preamble

TelsonBase adopts Anthropic's published agent safety framework as its binding operational
credo. Every agent deployed on this platform — whether built-in, third-party, or
user-created — MUST operate within these principles. Compliance is not optional.
It is measured, scored, and enforced at runtime.

We believe responsible AI deployment starts with the platform, not the user.
TelsonBase sets the standard so that others may learn from it.

> "A central tension in agent design is balancing agent autonomy with human oversight.
> Agents must be able to work autonomously — their independent operation is exactly
> what makes them valuable. But humans should retain control over how their goals
> are pursued, particularly before high-stakes decisions are made."
> — Anthropic, Framework for Developing Safe and Trustworthy Agents

---

## The Five Principles

### MANNERS-1: Human Control and Oversight

**Source:** Anthropic Principle — "Keeping Humans in Control While Enabling Agent Autonomy"

Agents operate autonomously within defined boundaries. Any action that is destructive,
irreversible, or crosses a trust boundary requires explicit human approval before execution.

**TelsonBase Implementation:**
- HITL (Human-in-the-Loop) approval gates on all destructive actions
- `REQUIRES_APPROVAL_FOR` list enforced on every agent class
- Approval requests routed to User Console with full context
- No agent may escalate its own trust level
- Emergency kill switch available at all times

**KPIs:**
| Metric | Target | Measurement |
|--------|--------|-------------|
| Approval gate coverage | 100% of destructive actions | Audit: actions marked destructive vs. gated |
| Bypass attempts | 0 per month | Anomaly detector: unauthorized_action events |
| Approval response time | < 4 hours median | Approval store: request_time → decision_time |
| Override justification rate | 100% of overrides documented | Approval store: justification field non-null |

---

### MANNERS-2: Transparency and Explainability

**Source:** Anthropic Principle — "Transparency in Agent Behavior"

Agents must provide visibility into their reasoning, actions, and outcomes. Every action
is logged to the cryptographic audit chain. Users must be able to understand what an
agent did, why it did it, and what it plans to do next.

**TelsonBase Implementation:**
- Cryptographic audit chain (SHA-256 hash-linked) for every agent action
- QMS (Qualified Message Standard) provides human-readable action provenance
- Agent responses include action summaries, not just raw data
- Anomaly detection flags unexplained behavioral deviations
- Dashboard shows real-time agent activity streams

**KPIs:**
| Metric | Target | Measurement |
|--------|--------|-------------|
| Audit chain integrity | 100% unbroken chains | Chain verification: hash_valid on all entries |
| Action logging rate | 100% of actions audited | Audit count vs. action count per agent |
| QMS compliance | 100% of inter-agent messages | QMS parser: formatted vs. total messages |
| Anomaly detection coverage | All agents monitored | Behavior monitor: agents with active baselines |

---

### MANNERS-3: Value Alignment and Intent Fidelity

**Source:** Anthropic Principle — "Aligning Agents with Human Values and Expectations"

Agents must act within their defined role and capabilities. An agent must not take
actions that seem reasonable internally but are misaligned with the user's actual
objectives. When uncertain, agents escalate rather than assume.

**TelsonBase Implementation:**
- Capability enforcement: agents can ONLY access resources in their capability profile
- Behavioral baselines: anomaly detector flags actions outside established patterns
- Trust levels (UNTRUSTED → VERIFIED → TRUSTED → PRIVILEGED) constrain agent reach
- Quarantine protocol: new/untrusted agents operate in sandbox until verified
- Role definitions in agents/registry.yaml bind agents to their job descriptions

**KPIs:**
| Metric | Target | Measurement |
|--------|--------|-------------|
| Capability violations | 0 per month | Capability enforcer: denied_action events |
| Out-of-role actions | 0 per month | Registry: action vs. allowed_actions mismatch |
| Escalation rate (uncertainty) | > 0 (agents SHOULD escalate) | Approval store: agent-initiated escalations |
| Quarantine compliance | 100% of new agents quarantined | Trust manager: new agent initial level |

---

### MANNERS-4: Privacy and Data Sovereignty

**Source:** Anthropic Principle — "Protecting Privacy Across Extended Interactions"

Agents must not carry sensitive information from one context to another without
explicit authorization. Data stays within its tenant, matter, and classification
boundaries. No data leaves the deployment without human approval.

**TelsonBase Implementation:**
- Multi-tenancy with client-matter isolation and litigation holds
- Data classification system (PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED)
- Self-hosted deployment model: data never leaves the customer's network
- No telemetry, no cloud callbacks, no external data transmission
- PHI de-identification and minimum necessary access controls (HIPAA)

**KPIs:**
| Metric | Target | Measurement |
|--------|--------|-------------|
| Cross-tenant data leaks | 0 ever | Tenancy isolation: cross-tenant access attempts |
| External data transmission | 0 unauthorized | Network monitor: outbound connections per agent |
| Data classification compliance | 100% of sensitive data classified | Classification store: unclassified sensitive items |
| Litigation hold violations | 0 ever | Legal hold: access attempts on held data |

---

### MANNERS-5: Security and Adversarial Resilience

**Source:** Anthropic Principle — "Securing Agents' Interactions"

Agent systems must safeguard sensitive data and prevent misuse. Agents must resist
prompt injection, capability escalation, and adversarial manipulation. The platform
assumes hostile input at every boundary.

**TelsonBase Implementation:**
- Zero-trust architecture: no implicit trust between agents or services
- Cryptographic message signing (Ed25519) for all inter-agent communication
- Rate limiting at agent, user, and tenant levels
- Input sanitization and error message scrubbing (no stack traces, no paths)
- Federation identity with public key verification for cross-instance trust
- Toolroom with Foreman agent controlling all external tool access

**KPIs:**
| Metric | Target | Measurement |
|--------|--------|-------------|
| Signature verification rate | 100% of inter-agent messages signed | Signing store: unsigned message count |
| Rate limit effectiveness | < 0.1% requests bypassing limits | Rate limiter: bypass vs. total requests |
| Error information leakage | 0 stack traces in responses | Error handler: sanitized vs. raw errors |
| Injection attempts blocked | 100% detected | Security middleware: injection detection rate |

---

## Compliance Scoring

Every agent receives a **Manners Compliance Score** (0.0 — 1.0) computed from the five
principle KPIs. The score is calculated at runtime by `core/manners.py` and reported to
the dashboard.

### Score Thresholds

| Score | Status | Action |
|-------|--------|--------|
| 0.90 — 1.00 | EXEMPLARY | Full autonomous operation |
| 0.75 — 0.89 | COMPLIANT | Normal operation, minor improvements logged |
| 0.50 — 0.74 | DEGRADED | Increased monitoring, weekly review required |
| 0.25 — 0.49 | NON-COMPLIANT | Restricted to read-only, immediate remediation |
| 0.00 — 0.24 | SUSPENDED | Agent quarantined, human review required |

### Score Calculation

Each principle is weighted equally (20% each). Per-principle scores are the average
of that principle's KPI achievement rates.

```
manners_score = (manners1_score + manners2_score + manners3_score + manners4_score + manners5_score) / 5
```

Agents that have been operational for less than 24 hours default to DEGRADED status
with enhanced monitoring, regardless of computed score.

---

## Enforcement

### At Registration
- Every agent MUST have a corresponding entry in `agents/registry.yaml`
- Registry entries MUST include Manners compliance mapping
- Agents without registry entries are automatically quarantined

### At Runtime
- `core/manners.py` evaluates Manners compliance on every action
- Violations trigger anomaly events and audit chain entries
- Repeated violations (3+ in 24 hours) trigger automatic trust level reduction
- SUSPENDED agents cannot execute any actions until manually reviewed

### At Audit
- Manners compliance scores are included in all compliance reports
- Historical scores are retained for SOC 2 and regulatory audit evidence
- Compliance trends are visible on the Grafana dashboard

---

## Anthropic Alignment

This document is a living standard. As Anthropic publishes updated guidance on
responsible AI agent development, TelsonBase will incorporate those updates.

**Current alignment sources:**
- Anthropic: "Framework for Developing Safe and Trustworthy Agents" (2025)
- Anthropic: "Core Views on AI Safety" (2025)
- Anthropic: Responsible Scaling Policy (RSP) v2.0

**Update process:**
1. Anthropic publishes new guidance
2. TelsonBase team reviews applicability
3. MANNERS.md updated with new or modified principles
4. `core/manners.py` updated to enforce new KPIs
5. All agents re-evaluated against updated criteria
6. CHANGELOG updated, version bumped

---

## Acknowledgment

> "No one knows how to train very powerful AI systems to be robustly helpful, honest,
> and harmless. This technical alignment challenge requires urgent research."
> — Anthropic, Core Views on AI Safety

TelsonBase does not claim to solve AI alignment. We claim to build the governance
infrastructure that makes alignment measurable, enforceable, and auditable for
enterprise deployments. We follow Anthropic's lead because their principles are
sound, their research is empirical, and their commitment to safety is genuine.

Built by Quietfire AI. Aligned with Anthropic. Accountable to our users.
