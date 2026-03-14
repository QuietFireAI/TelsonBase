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
 - trust-tiers
 - manners-score
 - mcp
 - self-hosted
 - goose
 - human-in-the-loop
 - kill-switch
 - audit-trail
short_description: Manners Score + 5 trust tiers. Trust is earned by agents.
---

# ClawCoat - Live Governance Demo

**Five trust tiers. One Manners Score. Trust is earned by agents, granted by humans.**

This Space connects to a **live TelsonBase server** running the real governance pipeline.
Select a demo agent, pick an action, and see an actual governance decision in real time.

## What the Demo Shows

- **Manners Score** - every action scored against five behavioral principles in real time (0.0–1.0)
- **Five trust tiers** - QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT, earned sequentially
- **Governance pipeline** - 8 steps, real decisions, real server — Allowed, Gated, or Blocked
- **Kill switch** - suspend an agent instantly, watch every subsequent action rejected at Step 2
- **HITL gating** - actions held for human approval regardless of trust level

## Trust Tier Flow

```
QUARANTINE ──► PROBATION ──► RESIDENT ──► CITIZEN ──► AGENT
 (all gated)  (internal ok) (read/write)  (autonomous)  (apex)
```

Every agent starts at Quarantine. Trust is earned through demonstrated behavior, one tier at a time.
The Manners Score drives it — drop below 0.25 and the agent auto-suspends. No human delay required.
Demotion is instant. The kill switch is always available to a human admin.

## Full Repository

**→ [github.com/QuietFireAI/ClawCoat](https://github.com/QuietFireAI/ClawCoat)**

Source code, documentation, proof sheets, quick start, and full test suite.
746 tests passing. 0 high-severity findings. Apache 2.0.

---

*TelsonBase v11.0.1 · Quietfire AI · Apache 2.0*
