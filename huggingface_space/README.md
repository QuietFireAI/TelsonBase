---
title: TelsonBase
emoji: 🦞
colorFrom: purple
colorTo: indigo
sdk: static
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
short_description: Zero-trust governance platform for autonomous AI agents. Self-hosted. No cloud dependencies.
---

# TelsonBase

**Zero-trust governance for autonomous AI agents. Self-hosted. No cloud AI. Every action earned.**

TelsonBase is the security layer that should have existed before anyone gave an AI agent access to a file system.

## What It Does

Autonomous AI agents are powerful and ungoverned. TelsonBase wraps every agent in a deterministic governance layer — trust levels, kill switches, human-in-the-loop approval gates, cryptographic audit chains, and behavioral anomaly detection — without modifying the agent itself.

Every agent starts at **Quarantine** and earns trust through demonstrated behavior. Promotion is sequential and human-approved. Demotion is instant and automatic.

```
QUARANTINE ──► PROBATION ──► RESIDENT ──► CITIZEN ──► AGENT
 (all gated)  (internal ok) (read/write)  (autonomous)  (apex)
```

## Key Facts

- **720 tests passing** · 0 high-severity findings · 37,921 lines scanned
- **Native MCP gateway** — Goose and Claude Desktop connect out of the box
- **Self-hosted** — your hardware, your data, no external API calls in the default stack
- **8-step governance pipeline** — kill switch at Step 2, before trust levels, before everything
- **Apache 2.0** — free for any use

## Full Repository

**→ [github.com/QuietFireAI/TelsonBase](https://github.com/QuietFireAI/TelsonBase)**

Source code, documentation, proof sheets, quick start, and full test suite.

## Who This Is For

Developers building agent pipelines who need governance infrastructure. Organizations in regulated industries (legal, healthcare, insurance, accounting) deploying autonomous agents. Security engineers who want deterministic enforcement outside the model.

## Built With

Human-AI collaboration. Jeff Phillips (Quietfire AI) as architect. Claude (Anthropic) as primary development partner. Every AI model engaged as a collaborator, not a code generator.

---

*TelsonBase v9.1.0B · Quietfire AI · Apache 2.0*
