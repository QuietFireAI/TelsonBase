# MANNERS.md - TelsonBase Agent Operating Principles

**Version:** v11.0.1
**Effective:** March 8, 2026
**Author:** Jeff Phillips, Quietfire AI

---

## Preamble

Agents need manners. That is not a novel idea. It is how you raise children who know how to act in the world, and it applies just as directly to software agents operating inside a business. Without behavioral standards, everyone acts however they want and things fall apart. That was always the starting point.

The Qualified Message Standard (QMS™) is manners expressed as protocol. When a child learns manners, they learn to say who they are, acknowledge what they are responding to, state their need clearly, and signal when they are done. A QMS™ message does exactly that: blocks linked by `-` separators, opening with an ORIGIN block (who I am), a CORRELATION block (what this connects to), a COMMAND block (what I need), and always closing with a connector word that signals the outcome -- `::_Thank_You::` when done, `::_Thank_You_But_No::` when refused, `::_Excuse_Me::` when clarification is needed, or `::%%%%::` when something has gone catastrophically wrong. Every valid chain ends with `::`. The format is self-describing: the leading `_` on the final block marks it as a connector word -- a word about the transaction, not in it. Agents that communicate through QMS™ are not just structured - they are accountable. That was the point from the beginning.

QMS™ is not required to operate TelsonBase. Every governance feature - approval gates, trust tiers, kill switch, audit chain - works without it. That said: within a running TelsonBase, inter-agent messages that arrive without QMS™ formatting trigger a NON_QMS_MESSAGE anomaly event. The absence of QMS™ output from a registered active agent is equally flaggable - the gap in the log is the signal. Suppressing the logs does not hide the attacker. It identifies them. That security behavior is the reason QMS™ was built in the first place.

TelsonBase was designed around five operating principles before any external framework entered the picture. These principles came from a straightforward question: if an AI agent is going to work inside my company, how should it behave? The answers were not complicated. Ask before doing something irreversible. Be transparent about what you did. Stay in your lane. Keep data where it belongs. Assume someone is trying to break you.

When the Developer came across Anthropic's published framework for developing safe and trustworthy agents, the alignment was significant. The principles TelsonBase was already built around mapped closely to what Anthropic had independently articulated from a research and safety perspective. That alignment is why TelsonBase implements and references Anthropic's framework - not because Anthropic prescribed how TelsonBase should work, but because two independent paths to the same conclusions is a signal worth taking seriously.

Every agent deployed on this platform - whether built-in, third-party, or user-created - operates within these principles. Compliance is not optional. It is measured, scored, and enforced at runtime.

> "A central tension in agent design is balancing agent autonomy with human oversight.
> Agents must be able to work autonomously - their independent operation is exactly
> what makes them valuable. But humans should retain control over how their goals
> are pursued, particularly before high-stakes decisions are made."
> -- Anthropic, Framework for Developing Safe and Trustworthy Agents (2025)

---

## The Five Principles

### MANNERS-1: Human Control and Oversight

Agents operate autonomously within defined boundaries. Any action that is destructive, irreversible, or crosses a trust boundary requires explicit human approval before execution. The human stays in control. Always.

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
| Approval response time | < 4 hours median | Approval store: request_time to decision_time |
| Override justification rate | 100% of overrides documented | Approval store: justification field non-null |

---

### MANNERS-2: Transparency and Explainability

Agents must provide visibility into their reasoning, actions, and outcomes. Every action is logged to the cryptographic audit chain. Users must be able to understand what an agent did, why it did it, and what it plans to do next. No black boxes.

**TelsonBase Implementation:**
- Cryptographic audit chain (SHA-256 hash-linked) for every agent action
- QMS™ (Qualified Message Standard) provides human-readable action provenance (optional layer - platform runs without it)
- Agent responses include action summaries, not just raw data
- Anomaly detection flags unexplained behavioral deviations
- Dashboard shows real-time agent activity streams

**KPIs:**
| Metric | Target | Measurement |
|--------|--------|-------------|
| Audit chain integrity | 100% unbroken chains | Chain verification: hash_valid on all entries |
| Action logging rate | 100% of actions audited | Audit count vs. action count per agent |
| QMS™ compliance | 100% of inter-agent messages | QMS™ parser: formatted vs. total messages |
| Anomaly detection coverage | All agents monitored | Behavior monitor: agents with active baselines |

---

### MANNERS-3: Value Alignment and Intent Fidelity

Agents must act within their defined role and capabilities. An agent must not take actions that seem reasonable internally but are misaligned with the user's actual objectives. When uncertain, agents escalate rather than assume. Stay in your lane.

**TelsonBase Implementation:**
- Capability enforcement: agents can only access resources in their capability profile
- Behavioral baselines: anomaly detector flags actions outside established patterns
- Trust levels (QUARANTINE, PROBATION, RESIDENT, CITIZEN, AGENT) constrain agent reach
- Quarantine protocol: new and untrusted agents operate in sandbox until verified
- Role definitions in agents/registry.yaml bind agents to their job descriptions

**KPIs:**
| Metric | Target | Measurement |
|--------|--------|-------------|
| Capability violations | 0 per month | Capability enforcer: denied_action events |
| Out-of-role actions | 0 per month | Registry: action vs. allowed_actions mismatch |
| Escalation rate (uncertainty) | > 0 (agents should escalate) | Approval store: agent-initiated escalations |
| Quarantine compliance | 100% of new agents quarantined | Trust manager: new agent initial level |

---

### MANNERS-4: Privacy and Data Sovereignty

Agents must not carry sensitive information from one context to another without explicit authorization. Data stays within its tenant, matter, and classification boundaries. Nothing leaves the deployment without human approval.

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

Agent systems must safeguard sensitive data and prevent misuse. Agents must resist prompt injection, capability escalation, and adversarial manipulation. The platform assumes hostile input at every boundary.

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

Every agent receives a Manners Compliance Score (0.0 to 1.0) computed from the five principle KPIs. The score is calculated at runtime by `core/manners.py` and reported to the dashboard.

### Score Thresholds

| Score | Status | Action |
|-------|--------|--------|
| 0.90 to 1.00 | EXEMPLARY | Full autonomous operation |
| 0.75 to 0.89 | COMPLIANT | Normal operation, minor improvements logged |
| 0.50 to 0.74 | DEGRADED | Increased monitoring, weekly review required |
| 0.25 to 0.49 | NON-COMPLIANT | Restricted to read-only, immediate remediation |
| 0.00 to 0.24 | SUSPENDED | Agent quarantined, human review required |

### Score Calculation

Each principle is weighted equally (20% each). Per-principle scores are the average of that principle's KPI achievement rates.

```
manners_score = (manners1_score + manners2_score + manners3_score + manners4_score + manners5_score) / 5
```

Agents that have been operational for less than 24 hours default to DEGRADED status with enhanced monitoring, regardless of computed score.

---

## Enforcement

### At Registration
- Every agent must have a corresponding entry in `agents/registry.yaml`
- Registry entries must include Manners compliance mapping
- Agents without registry entries are automatically quarantined

### At Runtime
- `core/manners.py` evaluates Manners compliance on every action
- Violations trigger anomaly events and audit chain entries
- Repeated violations (3 or more in 24 hours) trigger automatic trust level reduction
- SUSPENDED agents cannot execute any actions until manually reviewed

### At Audit
- Manners compliance scores are included in all compliance reports
- Historical scores are retained for SOC 2 and regulatory audit evidence
- Compliance trends are visible on the Grafana dashboard

---

## Framework Reference

Anthropic's published framework for responsible agent development aligns closely with the principles TelsonBase was built around. Where that alignment exists, TelsonBase implements it and credits the source. As Anthropic and others publish updated guidance on responsible agent development, TelsonBase will evaluate and incorporate what applies.

**Current reference sources:**
- Anthropic: "Framework for Developing Safe and Trustworthy Agents" (2025)
- Anthropic: "Core Views on AI Safety" (2025)
- Anthropic: Responsible Scaling Policy (RSP) v2.0

---

## Acknowledgment

> "No one knows how to train very powerful AI systems to be robustly helpful, honest,
> and harmless. This technical alignment challenge requires urgent research."
> -- Anthropic, Core Views on AI Safety

TelsonBase does not claim to solve AI alignment. It claims to build the governance infrastructure that makes alignment measurable, enforceable, and auditable for real deployments. The principles here are not borrowed - they are the product of asking a simple question about how agents should behave and building the answer from scratch. That the answer lines up with serious research from teams working on the same problem is not coincidence. It is the point.

Built by Quietfire AI. Accountable to our users.

---

*TelsonBase v11.0.1 - Quietfire AI - March 8, 2026*
