---
title: TelsonBase
emoji: 🦞
colorFrom: purple
colorTo: indigo
sdk: gradio
sdk_version: "5.20.0"
app_file: app.py
pinned: true
license: apache-2.0
tags:
  - ai-governance
  - ai-agents
  - zero-trust
  - security
  - mcp
  - self-hosted
  - goose
  - human-in-the-loop
  - kill-switch
  - audit-trail
short_description: Live demo — zero-trust governance for AI agents.
---

# TelsonBase — Live Governance Demo

**Zero-trust governance for autonomous AI agents. Self-hosted. No cloud AI. Every action earned.**

This Space connects to a **live TelsonBase server** running the real governance pipeline.
Select a demo agent, pick an action, and see an actual governance decision in real time.

## What the Demo Shows

- **Governance pipeline evaluation** — 8 steps, real decisions, real server
- **Five trust tiers** — QUARANTINE / PROBATION / RESIDENT / CITIZEN / AGENT, each with different permissions
- **Kill switch** — suspend an agent, watch Step 2 reject every subsequent action instantly
- **HITL gating** — some actions held for human approval regardless of trust level

## Trust Tier Flow

```
QUARANTINE ──► PROBATION ──► RESIDENT ──► CITIZEN ──► AGENT
 (all gated)  (internal ok) (read/write)  (autonomous)  (apex)
```

Every agent starts at Quarantine. Trust is earned through demonstrated behavior.
Demotion is instant and automatic. The kill switch is always available to a human.

## Full Repository

**→ [github.com/QuietFireAI/TelsonBase](https://github.com/QuietFireAI/TelsonBase)**

Source code, documentation, proof sheets, quick start, and full test suite.
746 tests passing. 0 high-severity findings. Apache 2.0.

---

*TelsonBase v11.0.1 · Quietfire AI · Apache 2.0*
