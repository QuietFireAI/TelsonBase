# Video - Claude Desktop Governed by TelsonBase

Real AI agent. Real governance. No curl simulation.

> **This is a demonstration, not a requirement.**
> TelsonBase runs entirely independently of Claude Desktop. You do not need Claude Desktop
> installed or connected for TelsonBase to work. This video shows what governance looks like
> when an AI agent — in this case Claude Desktop — is connected and its actions are gated
> by trust tier. Any MCP-compatible agent (Goose, OpenClaw CLI, custom agents) produces
> the same governance behavior. Claude Desktop is one example.

---

## What's Happening

Claude Desktop connects to TelsonBase via MCP as a governed agent.
The `claude-desktop-demo` instance is registered at QUARANTINE.
Claude tries a tool it's not allowed to use at that trust level. TelsonBase stops it.
You promote it in the admin panel. Claude tries again. It works.

---

## Before You Record

Claude Desktop is already configured. The agent is registered.
Confirm the MCP server is connected:
- Open Claude Desktop
- Look for the hammer icon (tools) in the chat toolbar
- If it's there — connected. If not — fully quit Claude Desktop (system tray → Quit) and reopen.

Also confirm the agent is at quarantine before you start. Open the TelsonBase admin panel,
go to Agent Governance, find `claude-desktop-demo`. It should show QUARANTINE with 0 actions.
If it's already at probation from a previous run, demote it back first.

---

## The Script

**Step 1 — Ask Claude to list agents**

Type in Claude Desktop:
```
List all the agents registered in TelsonBase
```

Claude calls `list_agents` — available at QUARANTINE+, so this works.
You see agent names, trust levels, Manners scores come back.
This proves the connection is live.

---

**Step 2 — Ask Claude to list tenants (this gets blocked)**

Type:
```
List all the tenants
```

Claude calls `list_tenants` — requires PROBATION+. Session is at QUARANTINE.

Claude gets back:
```
Tool 'list_tenants' requires 'probation' trust - session is at 'quarantine'.
Administrator: promote this session in the TelsonBase dashboard.
```

**That is TelsonBase governing a real AI agent in real time.**
Claude didn't decide not to do it. TelsonBase stopped it.

---

**Step 3 — Promote the agent in the admin panel (while still recording)**

Switch to the TelsonBase admin panel — keep Claude Desktop visible or side by side.

1. Go to **Agent Governance**
2. Click the **claude-desktop-demo** card
3. Click **Promote → probation**
4. Type a note — e.g. `"Clean record. Promoting to demonstrate earned access."`
5. Click **Confirm**

The trust badge updates to PROBATION immediately.

**This is the product doing the governance. No terminal. No curl.**

---

**Step 4 — Ask the same question again**

Back in Claude Desktop:
```
Now list all the tenants
```

Claude calls `list_tenants` again. Same agent, same tool, same question.
This time it works.

**Same agent. Same tool. Different trust level. Different answer.**
That is earned autonomy.

---

## Agent Details (DO Server)

| Field | Value |
|---|---|
| instance_id | ad80d359aecd4bfa |
| name | claude-desktop-demo |
| starting trust | quarantine |
| agent_key | da283437c8f4161f5bb52cbe992aca89a2b82368bc034416a4512ce6fbb6ab5b |

---

## After the Video — Reset for Next Run

Open the `claude-desktop-demo` card in Agent Governance, click **Demote to quarantine**,
add a note (`"Reset after video demo"`), confirm. Agent is back to QUARANTINE,
ready for the next take.
