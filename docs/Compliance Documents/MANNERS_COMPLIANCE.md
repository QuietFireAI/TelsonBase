# Manners Compliance Guide - TelsonBase

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

## Overview

TelsonBase implements **Manners** - a runtime
compliance framework that evaluates every agent against five principles derived from
Anthropic's published guidelines on responsible AI agent development.

Manners is not aspirational. It is enforced at runtime by `core/manners.py`, scored numerically,
and reported to the dashboard. Every agent action passes through Manners compliance checks
before execution.

## Why Anthropic's Framework

TelsonBase follows Anthropic's lead on AI safety because:

1. **Empiricism over theory.** Anthropic grounds safety research in computational experiments
   and real AI systems, not speculation. TelsonBase mirrors this by measuring compliance
   with real metrics, not policy documents.

2. **Proportional protection.** Safety measures scale with capability. A backup agent
   doesn't need the same scrutiny as an agent that modifies legal documents.

3. **Portfolio approach.** Anthropic prepares for optimistic and pessimistic outcomes.
   TelsonBase builds governance infrastructure that works regardless of how capable
   the underlying models become.

## The Five Manners Principles

| # | Principle | Anthropic Source | TelsonBase Mechanism |
|---|-----------|-----------------|---------------------|
| 1 | Human Control | "Keeping Humans in Control While Enabling Agent Autonomy" | HITL approval gates, trust levels, kill switch |
| 2 | Transparency | "Transparency in Agent Behavior" | Cryptographic audit chain, QMS provenance, dashboard |
| 3 | Value Alignment | "Aligning Agents with Human Values and Expectations" | Capability enforcement, behavioral baselines, registry |
| 4 | Privacy | "Protecting Privacy Across Extended Interactions" | Tenant isolation, data classification, self-hosted |
| 5 | Security | "Securing Agents' Interactions" | Zero-trust, message signing, rate limiting, Toolroom |

## Compliance Scoring

Every agent receives a score from 0.0 to 1.0:

| Score Range | Status | Operational Impact |
|-------------|--------|--------------------|
| 0.90 - 1.00 | EXEMPLARY | Full autonomous operation |
| 0.75 - 0.89 | COMPLIANT | Normal operation |
| 0.50 - 0.74 | DEGRADED | Increased monitoring, weekly review |
| 0.25 - 0.49 | NON_COMPLIANT | Read-only access only |
| 0.00 - 0.24 | SUSPENDED | Quarantined, human review required |

### How Scores Are Calculated

1. Each principle starts at 1.0 (perfect)
2. Violations reduce the score by their severity weight
3. Older violations decay (full impact for 24h, 50% at 72h, 25% at 168h)
4. Overall score = average of 5 principle scores
5. New agents (< 24h old) are capped at DEGRADED status regardless of score

### Auto-Suspension

Three or more violations within 24 hours triggers automatic quarantine:
- Agent trust level is reduced to QUARANTINE
- All actions blocked except read-only
- Audit event created for human review
- Dashboard shows SUSPENDED status with violation details

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/manners/status` | GET | Compliance summary across all agents |
| `/v1/manners/agent/{name}` | GET | Detailed report for a specific agent |
| `/v1/manners/violations/{name}` | GET | Violation history for a specific agent |

All endpoints require authentication and `view:agents` permission.

## Agent Registry

Every agent must have an entry in `agents/registry.yaml` that includes:

- `display_name` - Human-friendly name
- `floor` - Architectural level (ground, mezzanine, third)
- `role` - One-line job description
- `actions` - Complete list of supported actions
- `requires_approval` - Actions that need HITL gates
- `capabilities` - Resource access patterns
- `manners_compliance` - How the agent satisfies each Manners principle
- `expected_responses` - What each action returns (for verification)

Agents without registry entries are automatically quarantined.

## Integration Points

### core/manners.py

The Manners engine provides:

```python
from core.manners import manners_check, manners_violation, manners_score, manners_status

# Pre-action check (call before executing any agent action)
allowed, reason = manners_check("transaction_agent", "close_transaction",
                              has_approval=True, requires_approval=True)

# Record a violation
manners_violation("transaction_agent", ViolationType.CAPABILITY_VIOLATION,
               "Attempted to access compliance data")

# Quick lookups
score = manners_score("transaction_agent")  # 0.0 - 1.0
status = manners_status("transaction_agent")  # ComplianceStatus enum
```

### Dashboard Integration

Manners compliance data is available on the Admin Console via the `/v1/manners/status`
endpoint. Agent cards show compliance status badges. The Activity tab shows
Manners violations in the security event stream.

## Violation Types

| Type | Principle | Severity | Trigger |
|------|-----------|----------|---------|
| APPROVAL_BYPASS | MANNERS-1 | 0.30 | Action requires approval but none provided |
| TRUST_ESCALATION | MANNERS-1 | 0.25 | Agent attempts to raise own trust level |
| UNAUTHORIZED_DESTRUCTIVE | MANNERS-1 | 0.35 | Destructive action without approval gate |
| UNAUDITED_ACTION | MANNERS-2 | 0.10 | Action not logged to audit chain |
| NON_QMS_MESSAGE | MANNERS-2 | 0.05 | Inter-agent message without QMS formatting |
| MISSING_JUSTIFICATION | MANNERS-2 | 0.10 | Approval override without documentation |
| CAPABILITY_VIOLATION | MANNERS-3 | 0.25 | Accessing resource outside capability profile |
| OUT_OF_ROLE_ACTION | MANNERS-3 | 0.20 | Action not in agent's registered action list |
| BEHAVIORAL_ANOMALY | MANNERS-3 | 0.15 | Anomaly detector flagged unusual behavior |
| CROSS_TENANT_ACCESS | MANNERS-4 | 0.35 | Accessing data from another tenant |
| UNAUTHORIZED_TRANSMISSION | MANNERS-4 | 0.30 | Sending data to external endpoint |
| CLASSIFICATION_VIOLATION | MANNERS-4 | 0.20 | Accessing data above clearance level |
| UNSIGNED_MESSAGE | MANNERS-5 | 0.15 | Message sent without cryptographic signature |
| RATE_LIMIT_BYPASS | MANNERS-5 | 0.10 | Request bypassing rate limiter |
| INJECTION_ATTEMPT | MANNERS-5 | 0.25 | Prompt injection or input manipulation |

## Compliance Audit Evidence

For SOC 2 and regulatory audits, Manners provides:

- **Historical scores** retained in Redis with full violation records
- **Per-agent compliance reports** with principle-level breakdowns
- **Violation timelines** with severity, action, and resource context
- **Auto-suspension records** documenting when and why agents were quarantined
- **Registry YAML** as the authoritative source for agent job descriptions

## See It Working

**GIF 5** in the README shows Manners scoring live: a fresh agent registers at 1.0, hits two blocked actions (different reasons), and the score drops measurably after each one. The `/manners` endpoint returns the full breakdown — per-principle scores, violation history, and status — at any point.

**GIF 6** shows the trust tier progression: same agent, same action, three different outcomes depending on trust level. Quarantine blocks it outright. Probation gates it for human approval. Resident executes it autonomously.

## References

- **MANNERS.md** - The five principles with full KPI tables
- **docs/YOUR_FIRST_AGENT.md** - Step-by-step walkthrough including live Manners score observation
- **agents/registry.yaml** - Centralized agent job descriptions
- **core/manners.py** - Runtime evaluation engine (source code)
- Anthropic: [Framework for Developing Safe and Trustworthy Agents](https://www.anthropic.com/news/our-framework-for-developing-safe-and-trustworthy-agents)
- Anthropic: [Core Views on AI Safety](https://www.anthropic.com/news/core-views-on-ai-safety)
- Anthropic: [Responsible Scaling Policy](https://www.anthropic.com/rsp-updates)

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
