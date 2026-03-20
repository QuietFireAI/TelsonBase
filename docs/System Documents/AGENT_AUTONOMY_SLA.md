# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0

# Agent Autonomy SLA

**Specification Version:** 1.0.0
**Effective Date:** March 2026
**Author:** Quietfire AI
**License:** Apache 2.0
**Status:** Active, reference implementation in ClawCoat v11.0.3

---

## Abstract

This document defines the Agent Autonomy SLA, a formal per-agent commitment framework that governs what an OpenClaw agent is permitted to do, under what conditions, with what oversight, and with what accountability. It is implemented in ClawCoat, a self-hosted, zero-trust AI agent governance platform.

This specification is offered as an open standard. Any system that intercepts MCP tool calls in real time and enforces per-tier policy may claim compliance with the Agent Autonomy SLA model defined here.

---

## 1. Why Agent Autonomy SLAs Are Needed

Traditional SLAs cover infrastructure: uptime, latency, throughput, error rates. API gateways enforce rate limits and authentication. Service meshes manage mTLS and circuit breaking. None of these address the behavior of an autonomous agent operating inside a system.

Jouneaux and Cabot (2025) propose a quality model and DSL for specifying AI agent SLAs, identifying this as "an open challenge":

> "We argue that the notion of Service Level Agreement (SLA) for AI agents is still largely open and would require new research efforts to tackle the properties that make AI agents unique."
> - *AgentSLA: Towards a Service Level Agreement for AI Agents*, arXiv:2511.02885

Their work defines the vocabulary — including `OversightLevel` as a first-class metric — and produces a formal specification language. ClawCoat implements that vocabulary at runtime. The enforcement gap is precise. An API gateway can confirm that a request was authenticated and responded within 200ms. It cannot determine whether that request, tool call, file write, transaction initiation, was appropriate for the agent that made it, given its behavioral history, trust standing, and the human oversight policy in effect at that moment.

Autonomous agents introduce three properties that existing SLA infrastructure was never designed to handle:

1. **Intent opacity.** Agents make sequences of decisions that are individually valid but collectively problematic. A rate limit catches volume. It does not catch an agent methodically exfiltrating data one record at a time.

2. **Earned trust is dynamic.** Human employees earn access incrementally over time. Agent access models have historically been binary: API key present, request authorized. There is no mechanism for an agent to lose access it previously held based on behavioral evidence.

3. **Accountability requires a chain.** When an AI agent causes an incident, "the model did it" is not an auditable finding. A governance system must produce a signed, tamper-evident record of every decision point, what was attempted, what policy applied, what outcome was produced, and who authorized it.

The Agent Autonomy SLA addresses all three.

---

## 2. Scope and Applicability

This specification applies to any system in which:

- Autonomous AI agents invoke tools via the Model Context Protocol (MCP) or equivalent
- The invoking system intercepts calls **before execution** (active decision making, not post-hoc logging)
- Access policy is differentiated by agent trust standing
- Human approval gates are available for privileged operations
- A cryptographic audit chain records every governance decision

This specification does not apply to systems that only log agent activity after the fact, or that apply uniform access policy across all agents regardless of behavioral history.

---

## 3. Core Concepts

### 3.1 Active Decision Making

Every tool call reaches a governance layer before execution. The governance layer produces exactly one of three outcomes:

| Outcome | Meaning |
|---|---|
| **ALLOW** | The call proceeds immediately. No human intervention required. |
| **GATE** | The call is held pending explicit human approval. The agent receives no response until a human grants or denies the request. |
| **BLOCK** | The call is rejected. The agent receives a structured refusal. The event is recorded in the audit chain. |

This is the defining property of the Agent Autonomy SLA. Systems that only alert or log after execution do not satisfy this requirement.

### 3.2 Trust Tiers

Agent access is governed by a five-level trust hierarchy. Trust is earned through demonstrated behavioral compliance. Trust is lost through behavioral violations.

```
QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT
```

AGENT (apex) is not a default state. It represents an agent that has earned maximum operational trust through verified behavioral history. No agent arrives at AGENT tier, it is promoted there.

### 3.3 Manners Engine

The Manners Engine is an 8-factor behavioral scoring system that produces a continuous score in [0.0, 1.0] for each registered agent. Violations deduct from the score according to severity. The score is evaluated on every tool call and is the primary input to automatic tier demotion.

**Manners compliance bands:**

| Band | Score Range | Meaning |
|---|---|---|
| EXEMPLARY | 0.90 – 1.00 | Full autonomous operation warranted |
| COMPLIANT | 0.75 – 0.89 | Normal operation |
| DEGRADED | 0.50 – 0.74 | Increased monitoring warranted |
| NON_COMPLIANT | 0.25 – 0.49 | Restricted operation |
| SUSPENDED | 0.00 – 0.24 | Human review required |

**Auto-demotion threshold:** Configurable via `OPENCLAW_AUTO_DEMOTE_THRESHOLD` (default: `0.50`). Any agent whose score falls below this threshold is automatically demoted to QUARANTINE, regardless of current tier. The demotion is recorded in the audit chain. Reinstatement requires human review.

Score degradation is permanent unless explicitly reviewed and cleared by an authorized human operator. An agent cannot self-repair its Manners score.

**Violation penalties (selected):**

| Violation | Score Deduction |
|---|---|
| Approval bypass attempt | 0.30 |
| Unauthorized destructive action | 0.35 |
| Cross-tenant access attempt | 0.35 |
| Trust escalation attempt | 0.25 |
| Injection attempt | 0.25 |
| Capability violation | 0.25 |
| Out-of-role action | 0.20 |
| Behavioral anomaly | 0.15 |

### 3.4 Human-in-the-Loop (HITL) Gates

HITL gates are blocking approval checkpoints. When a gate triggers, the tool call is suspended and an approval request is routed to a designated human operator. The agent receives no response until the operator acts. Gate decisions are recorded in the audit chain with the approving operator's identity and timestamp.

### 3.5 Cryptographic Audit Chain

Every governance decision is recorded as a signed audit event. Events are chained such that any tampering with the historical record is detectable. The chain is append-only and available for export for regulatory submission, incident response, or forensic review.

---

## 4. Per-Tier SLA Commitments

---

### 4.1 QUARANTINE

**The default tier for all newly registered agents.** No verified behavioral history. Minimum autonomy. Maximum oversight.

| Dimension | Commitment |
|---|---|
| **Tool access scope** | Read-only, non-destructive tools only. No file write, no external network calls, no data mutation, no transaction initiation. Enforced at the call intercept layer. |
| **Active decision policy** | All calls blocked by default unless explicitly operator-allowlisted. Zero autonomous execution. |
| **Manners score floor** | None, score is being established. Auto-demotion back to QUARANTINE from higher tiers occurs below the configured threshold (default 0.50). |
| **Audit trail** | Every call recorded: attempt, block reason, agent ID, timestamp, call signature. Minimum retention: 90 days (configurable). |
| **HITL requirement** | Any allowlist exception requires a human approval gate. No QUARANTINE agent call bypasses human review. |
| **Promotion** | Operator-initiated only. No automatic promotion from QUARANTINE. An operator must explicitly elevate the agent to PROBATION. |
| **Demotion** | N/A. This is the floor. |

**SLA commitment:** 100% of tool calls intercepted before execution. 0% autonomous tool execution.

---

### 4.2 PROBATION

**The agent has been reviewed and released from QUARANTINE.** Operating under active monitoring with a constrained allowlist. Autonomy is low but non-zero.

| Dimension | Commitment |
|---|---|
| **Tool access scope** | Explicit allowlist only. Read operations broadly permitted. Write operations only where explicitly granted. No privileged system operations, no financial transactions, no external API calls unless specifically approved. |
| **Active decision policy** | Allowlisted calls: ALLOW. Out-of-allowlist: GATE (not block, unless the call matches a block pattern). Repeated GATE triggers for the same call pattern: auto-escalation to operator review. |
| **Manners score floor** | DEGRADED band or above (≥ 0.50) to remain in PROBATION. Score below auto-demotion threshold → automatic return to QUARANTINE. |
| **Audit trail** | Full call record including tool name, parameters, outcome, and Manners score delta per call. |
| **HITL requirement** | All GATE events require human approval. Pattern of repeated identical approvals surfaced to operator for allowlist consideration. |
| **Promotion** | Sustained COMPLIANT band (≥ 0.75) over the configured observation window. Promotion to RESIDENT is operator-confirmed. |
| **Demotion** | Score below auto-demotion threshold; critical block event; three or more human-denied GATE requests within a session. |

**SLA commitment:** 100% of out-of-allowlist calls gated before execution.

---

### 4.3 RESIDENT

**The agent has demonstrated consistent behavioral compliance.** Broader tool scope. Meaningful autonomy. GATE events are reserved for elevated-risk operations.

| Dimension | Commitment |
|---|---|
| **Tool access scope** | Category-based access. Standard operational tools permitted by category (file I/O within declared scope, internal API calls, data reads across assigned tenants). Privileged categories remain gated. |
| **Active decision policy** | Standard calls: ALLOW. Privileged category calls: GATE. BLOCK reserved for explicit policy violations. |
| **Manners score floor** | DEGRADED band or above (≥ 0.50). Score below auto-demotion threshold → automatic demotion to QUARANTINE. |
| **Audit trail** | Full call record. Manners Engine score contribution logged per call. Anomaly detection flags logged with contributing factors. |
| **HITL requirement** | GATE events require human approval. ALLOW events for standard operations require no human action. |
| **Promotion** | Sustained COMPLIANT band (≥ 0.75) over the configured observation window. Promotion to CITIZEN is operator-confirmed. |
| **Demotion** | Score below auto-demotion threshold; confirmed anomaly detection event; human-denied GATE on a privileged operation; operator manual demotion. |

**SLA commitment:** 100% of privileged-category calls gated before execution.

---

### 4.4 CITIZEN

**High-trust agent with a demonstrated extended behavioral record.** Broad operational autonomy. Gating reserved for exceptional circumstances.

| Dimension | Commitment |
|---|---|
| **Tool access scope** | Broad operational scope including most privileged categories. Exceptions: financial transactions above configured threshold, external network exfiltration patterns, irreversible system-level operations. |
| **Active decision policy** | Most calls: ALLOW. Exceptional categories: GATE. BLOCK reserved for confirmed policy violations at high confidence. |
| **Manners score floor** | COMPLIANT band or above (≥ 0.75) recommended. Score below auto-demotion threshold → automatic demotion to QUARANTINE. |
| **Audit trail** | Full call record. ALLOW events for exceptional-adjacent operations flagged for periodic operator review. |
| **HITL requirement** | GATE events require human approval. High-value operations may be configured for mandatory HITL regardless of ALLOW outcome. |
| **Promotion** | Sustained EXEMPLARY band (≥ 0.90) over the configured observation window. Promotion to AGENT is operator-confirmed and requires deliberate operator action, not a routine approval. |
| **Demotion** | Score below auto-demotion threshold; confirmed high-confidence anomaly event; human-denied GATE; evidence of intent circumvention; operator manual demotion. |

**SLA commitment:** Anomaly detection evaluated continuously. Demotion threshold evaluated on every call.

---

### 4.5 AGENT (Apex)

**Maximum operational trust.** Reserved for agents with a verified long-term behavioral record. Near-full autonomy within declared scope. This tier represents the full delivery of the earned-trust model: an agent that has demonstrated it can be trusted operates with the autonomy it has earned.

| Dimension | Commitment |
|---|---|
| **Tool access scope** | Full declared scope. No categorical restrictions within registered tool allowance. Scope is bounded by the agent's registration declaration, not by tier-level restrictions. |
| **Active decision policy** | All in-scope calls: ALLOW. Out-of-scope calls: BLOCK with incident record. Anomaly detection events above threshold: immediate GATE and Manners score review. |
| **Manners score floor** | EXEMPLARY band (≥ 0.90) recommended. Score below auto-demotion threshold → automatic demotion to QUARANTINE. Demotion from AGENT tier generates an operator alert. |
| **Audit trail** | Full call record. AGENT-tier audit records marked for priority retention. |
| **HITL requirement** | No routine HITL for in-scope ALLOW events. Anomaly detection events above threshold: mandatory HITL gate before the triggering call completes. |
| **Promotion** | N/A. Apex tier. |
| **Demotion** | Score below auto-demotion threshold; confirmed anomaly event; out-of-scope tool call attempt; operator manual demotion. Demotion from AGENT tier is an audited event requiring operator acknowledgment. |

**SLA commitment:** Out-of-scope call block rate: 100%. Demotion threshold evaluated on every call.

---

## 5. System-Level SLA Metrics

The following apply to the ClawCoat governance layer itself, independent of agent tier.

| Metric | Commitment |
|---|---|
| **Call intercept coverage** | 100% of MCP tool calls pass through the governance layer before execution. No bypass path exists. |
| **Active decision timing** | Governance decision (ALLOW/GATE/BLOCK) produced before the call is forwarded. No deferred evaluation. |
| **Audit chain integrity** | Every governance decision appended to the cryptographic audit chain within the same transaction as the decision. No decision without a record. |
| **Audit chain tamper evidence** | Chain hash verification available on demand. Any gap or modification is detectable. |
| **Manners Engine evaluation** | Score evaluated on every call, not batched. Score affects the decision for the call that generated it. |
| **Data residency** | Zero agent data transmitted off-network. Governance, audit, and scoring are entirely self-contained. |
| **Tier state persistence** | Agent trust tier persisted to durable storage. Tier state survives service restart. |

---

## 6. What This Specification Does Not Cover

The Agent Autonomy SLA is scoped to governance of tool execution. It does not specify:

- The content of agent responses (output filtering is a separate concern)
- Model-level alignment properties
- The internal decision-making of the agent LLM
- Compliance frameworks (SOC 2, HIPAA, HITRUST), addressed in ClawCoat's compliance proof documentation

---

## 7. Open Standard Invitation

This specification is released under Apache 2.0. Any governance system may implement the Agent Autonomy SLA model described here. Implementors are encouraged to:

- Adopt the five-tier naming convention (QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT) for interoperability
- Implement active decision making (ALLOW/GATE/BLOCK) at the call intercept layer, before execution, not after
- Maintain a cryptographic audit chain per the requirements in Section 5
- Reference arXiv:2511.02885 when describing the problem this specification addresses

A conformant implementation does not need to be ClawCoat. The model should be portable.

---

## 8. Relationship to Jouneaux & Cabot (2025)

Jouneaux and Cabot (arXiv:2511.02885) propose a quality model for AI agents built on ISO/IEC 25010 and a formal DSL — expressed in JSON — for specifying AI agent SLAs. Their work identifies `OversightLevel` as a first-class QoS metric, citing Cihon et al. (arXiv:2502.15212) on the autonomy spectrum.

ClawCoat is compatible with their DSL and adopts their vocabulary. The formal machine-readable specification of ClawCoat's governance SLA commitments is expressed in their format:

**[`agent-autonomy-sla-spec.json`](agent-autonomy-sla-spec.json)**

This file is a valid document in their proposed DSL. It uses their `OversightLevel` metric type to formalize each tier's oversight commitment, `MCP` to assert protocol compliance, `TTFT` for decision latency, and `DerivedQoSMetric` for the rolling behavioral observation window used in promotion evaluation.

### OversightLevel per trust tier

`OversightLevel` is expressed as a value in [0.0, 1.0] where 1.0 = full human oversight and 0.0 = fully autonomous. ClawCoat's five tiers map to the following committed values:

| Tier | OversightLevel | Manners Score Floor | Basis |
|---|---|---|---|
| **QUARANTINE** | 1.0 | none | Zero autonomous execution. All calls blocked or gated. |
| **PROBATION** | 0.75 | ≥ 0.50 (DEGRADED) | Allowlisted calls autonomous; all other calls gated. |
| **RESIDENT** | 0.50 | ≥ 0.50 (DEGRADED) | Standard calls autonomous; privileged calls gated. |
| **CITIZEN** | 0.25 | ≥ 0.75 (COMPLIANT) | Most calls autonomous; exceptional categories gated. |
| **AGENT** | 0.10 | ≥ 0.90 (EXEMPLARY) | All in-scope calls autonomous; anomaly events trigger mandatory HITL. |

Note the inverse relationship: OversightLevel decreases as trust increases, while the Manners score floor required to hold that tier increases. This is the earned-trust model expressed numerically — an agent earns lower oversight by maintaining higher behavioral compliance.

### Where the approaches align

Both frameworks recognize that traditional SLA infrastructure (uptime, latency, rate limits) cannot govern autonomous agent behavior. Both use a tiered structure for differentiated commitments. `OversightLevel` in their quality model maps directly to ClawCoat's trust tiers.

### Where they differ — and why both are needed

Jouneaux & Cabot solve the **specification problem**: how to formally express what quality and oversight level an agent service promises to deliver. Their DSL produces a document an agent can advertise and a client can evaluate against.

The Agent Autonomy SLA solves the **enforcement problem**: how to guarantee that a deployed agent *actually behaves* within the declared policy before any tool call executes. Specification without enforcement is a promise. Enforcement without specification is opaque. ClawCoat does both.

The specific contribution of this specification is the dynamic `OversightLevel` model: an agent does not arrive at a tier and stay there. Its tier — and therefore its `OversightLevel` — changes continuously based on behavioral evidence produced by the Manners Engine. No other system in the field currently implements `OversightLevel` as a runtime-enforced, behaviorally-driven property. It has only been proposed.

### Attribution

The `OversightLevel` metric type, the quality model taxonomy, and the JSON DSL used in `agent-autonomy-sla-spec.json` are the work of Jouneaux, G. and Cabot, J. (2025), released under their repository at https://github.com/gwendal-jouneaux/AgentSLA. ClawCoat adopts and extends this vocabulary with a working enforcement implementation.

---

## 9. Reference Implementation

**ClawCoat**, self-hosted, zero-trust AI agent governance platform.

- **Repository:** https://github.com/QuietFireAI/ClawCoat
- **Website:** https://clawcoat.com
- **Live Demo:** https://huggingface.co/spaces/QuietFireAI/ClawCoat
- **Machine-readable SLA spec:** [`agent-autonomy-sla-spec.json`](agent-autonomy-sla-spec.json)
- **License:** Apache 2.0

---

## 10. Citation

Jouneaux, G. and Cabot, J. (2025). *AgentSLA: Towards a Service Level Agreement for AI Agents*. arXiv:2511.02885. https://arxiv.org/abs/2511.02885

Cihon, P. et al. (2025). *[AI Autonomy and Oversight]*. arXiv:2502.15212. (Referenced via Jouneaux & Cabot's `OversightLevel` metric definition.)

This specification is the working enforcement implementation of the open challenge described in Jouneaux & Cabot (2025).

---

## 10. Document Information

| Field | Value |
|---|---|
| **Author** | Quietfire AI |
| **ORCID** | 0009-0000-1375-1725 (J. Phillips, Quietfire AI) |
| **Version** | 1.0.0 |
| **Date** | March 2026 |
| **License** | Apache 2.0 |
| **Implements** | ClawCoat v11.0.3 |

---

*Agent autonomy without accountability is operational risk. This specification defines accountability.*
