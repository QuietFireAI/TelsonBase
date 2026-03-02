# TelsonBase — GIF Recording Guide

**Purpose:** Step-by-step instructions for capturing the three developer-trust GIFs.
**Setup time:** ~5 minutes. **Recording time per GIF:** 20–40 seconds.
**Tools needed:** Browser + one terminal window open alongside it.

---

## One-Time Setup (Do This First, Not On Camera)

### 1. Enable OpenClaw

OpenClaw is off by default in `.env`. Turn it on before recording:

```bash
# In your TelsonBase directory
# Edit .env and change:
OPENCLAW_ENABLED=true

# Then restart just the API server (takes ~5 seconds):
docker compose restart mcp_server
sleep 5
```

Verify it's on:
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy","redis":"healthy",...}
```

### 2. Get Your API Key

```bash
cat secrets/telsonbase_mcp_api_key
# Copy the key — you'll paste it into the commands below as YOUR_API_KEY
```

### 3. Register Three Agents (One Per GIF)

Run these three commands. Each takes 2 seconds. Copy the `instance_id` from each response.

```bash
# Agent for GIF 1 — will be in QUARANTINE, action gets BLOCKED
curl -s -X POST http://localhost:8000/v1/openclaw/register \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "research_agent", "api_key": "demo-key-001"}' | python3 -m json.tool

# Agent for GIF 2 — will demonstrate the KILL SWITCH
curl -s -X POST http://localhost:8000/v1/openclaw/register \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "data_agent", "api_key": "demo-key-002"}' | python3 -m json.tool

# Agent for GIF 3 — promote to PROBATION so external action creates HITL pending
curl -s -X POST http://localhost:8000/v1/openclaw/register \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "integration_agent", "api_key": "demo-key-003"}' | python3 -m json.tool
```

Each response gives you an `instance_id`. Write them down:
```
GIF1_ID = (instance_id from research_agent)
GIF2_ID = (instance_id from data_agent)
GIF3_ID = (instance_id from integration_agent)
```

### 4. Promote GIF 3 Agent to PROBATION

```bash
curl -s -X POST http://localhost:8000/v1/openclaw/GIF3_ID/promote \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"new_level": "probation", "reason": "Ready for integration work"}'
```

---

## GIF 1 — Governance Decision: Action Blocked in Real Time

**What it shows:** An agent tries to take an action. TelsonBase evaluates it, rejects it, returns the reason. The agent never touches the resource. 20 seconds.

**Screen layout:** Browser open to `localhost:8000/dashboard` → OpenClaw page. Terminal alongside it.

### Steps:

**1.** Open browser: `http://localhost:8000/dashboard` → click **OpenClaw** in the left nav.
You should see `research_agent` listed in QUARANTINE.

**2.** Start recording.

**3.** In terminal, paste this command (replace GIF1_ID and YOUR_API_KEY):
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/GIF1_ID/action \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "http_post",
    "tool_args": {"url": "https://api.stripe.com/charges", "body": "amount=5000"}
  }' | python3 -m json.tool
```

**4.** Hit Enter. The response comes back in under a second:
```json
{
  "allowed": false,
  "reason": "BLOCKED: trust_tier=quarantine | category=external | tool=http_post",
  "trust_level": "quarantine",
  "action_category": "external"
}
```

**5.** Switch to browser — Audit Trail page. Scroll to the top. The blocked action is entry #1 with timestamp now. Hash visible.

**6.** Stop recording.

**Caption for README:** *"QUARANTINE agent attempts an external API call. TelsonBase blocks it in under 100ms and writes the decision to the tamper-evident audit chain."*

---

## GIF 2 — Kill Switch: Instant Agent Suspension

**What it shows:** One API call suspends an agent. Every subsequent action is rejected immediately — no trust level check, no Manners check, nothing. Kill switch fires at Step 2 of the pipeline. 30 seconds.

**Screen layout:** Browser open to `localhost:8000/dashboard` → OpenClaw page. Terminal alongside.

### Steps:

**1.** Open browser to OpenClaw page. `data_agent` should show as QUARANTINE, not suspended.

**2.** Start recording.

**3.** In terminal — fire a normal action first to show the agent is live:
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/GIF2_ID/action \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "read_file", "tool_args": {"path": "/data/report.txt"}}' \
  | python3 -m json.tool
```
Response will show `"allowed": false` with reason `trust_tier=quarantine` — agent is alive and being governed normally.

**4.** Now hit the kill switch:
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/GIF2_ID/suspend \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Suspicious behavior detected — immediate suspension"}' \
  | python3 -m json.tool
```
Response: `{"suspended": true, ...}`

**5.** Refresh browser — `data_agent` card now shows **SUSPENDED** badge.

**6.** Fire the same action again:
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/GIF2_ID/action \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "read_file", "tool_args": {"path": "/data/report.txt"}}' \
  | python3 -m json.tool
```
Response: `"allowed": false, "reason": "KILL SWITCH ACTIVE — instance suspended"` — trust level is irrelevant. Suspension trumps everything.

**7.** Stop recording.

**Caption for README:** *"Kill switch: one API call suspends an agent. All subsequent actions rejected immediately — before trust level, before Manners, before everything. Redis-persisted: survives restarts."*

---

## GIF 3 — HITL Approval: Action Held Pending Human Sign-Off

**What it shows:** An external action from a PROBATION agent hits the HITL gate. It sits in the approvals queue — not allowed, not blocked, pending. Human clicks Approve. Done. 40 seconds.

**Screen layout:** Browser open to `localhost:8000/dashboard` → Approvals page. Terminal alongside.

### Steps:

**1.** Open browser to Approvals page. Queue should be empty (or have prior items — that's fine).

**2.** Start recording.

**3.** In terminal — `integration_agent` is PROBATION. Send an external action:
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/GIF3_ID/action \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "http_post",
    "tool_args": {"url": "https://api.example.com/submit", "body": "data"}
  }' | python3 -m json.tool
```
Response: `"allowed": false, "approval_required": true, "reason": "GATED: trust_tier=probation | category=external"`

**4.** Refresh browser (Approvals page). The action now appears as a pending card with:
- Agent name: `integration_agent`
- Tool: `http_post`
- Decision notes field
- **Approve** and **Reject** buttons

**5.** Pause 2 seconds so the viewer reads the card.

**6.** Click **Approve**.

**7.** Card disappears from queue. Switch to Audit Trail — approval decision is entry #1.

**8.** Stop recording.

**Caption for README:** *"HITL approval gate: external action from a PROBATION agent is held pending human sign-off. Approve or reject from the dashboard. Decision logged to the audit chain."*

---

## ScreenToGif — Concrete Setup and Recording Steps

### Install

1. Go to **screentogif.com** → Download → `ScreenToGif.exe` (portable, no install needed)
2. Double-click to open. You'll see three buttons: Recorder, Webcam, Board. Use **Recorder**.

---

### Configure Before First Recording (One-Time)

Click **Recorder**. A transparent capture window appears with a red toolbar at the bottom.

**Set frame rate:**
- In the toolbar at the bottom of the capture window, find the **FPS** field
- Set it to **10** (down from default 15)
- Lower FPS = smaller file, still smooth enough for a governance demo

**Set capture region size:**
- Drag the corners of the transparent window to cover exactly what you want recorded
- **Target size:** roughly 1100 × 650 pixels — covers browser + terminal side by side without recording your full desktop
- You'll see pixel dimensions in the toolbar as you resize

**Pre-recording checklist:**
- Browser zoomed to **85%** (`Ctrl + -` twice) — fits more dashboard without scrolling
- Terminal font set to **16pt** — JSON responses need to be readable in the GIF
- Terminal window background: **black**, text: **white or green** — high contrast reads well compressed
- Both windows arranged: browser left (~65% of width), terminal right (~35%)
- Dashboard logged in, correct page loaded, ready to go

---

### Recording Each GIF

**Step 1 — Frame your shot**
- Position the ScreenToGif transparent window over your browser + terminal
- Don't include your taskbar, desktop icons, or other windows
- You want the viewer focused entirely on the platform

**Step 2 — Start recording**
- Click the **red circle** (Record) button in the ScreenToGif toolbar
- You'll see a countdown: 3... 2... 1... then it's live
- A frame counter appears — it's counting frames in real time

**Step 3 — Execute your demo steps**
- Work deliberately — pause 1–2 seconds before each action
- Pause 2 seconds after the terminal response appears so the viewer can read it
- Pause 2 seconds after switching to the browser so the viewer can take in the screen

**Step 4 — Stop recording**
- Click the **square** (Stop) button in the toolbar
- ScreenToGif opens its **editor** automatically showing all captured frames

**Step 5 — Trim dead frames in the editor**
- Scroll the frame strip at the bottom to find dead frames at the start/end
- Click the first dead frame, Shift+click the last dead frame, press Delete
- You want to start on a frame where the screen is already set up, not on a loading state

**Step 6 — Export**
- Click **File → Save As**
- Format: **GIF**
- Click **Options** (gear icon next to the format dropdown):
  - **Quantizer:** Octree
  - **Color count:** 128 (not 256 — halves palette size, barely visible difference)
  - **Looping:** Forever
- Click **Save**
- ScreenToGif shows the output file size when done

---

### File Size Reality Check

At 10fps, 1100×650px, with 128 colors:

| Duration | Approx File Size | Notes |
|---|---|---|
| 20 seconds | 1.5 – 2 MB | GIF 1 target — governance blocked |
| 30 seconds | 2 – 3 MB | GIF 2 target — kill switch |
| 40 seconds | 3 – 4.5 MB | GIF 3 target — HITL approval |

**GitHub README limit for embedded images: 10MB.** You have headroom.

If a GIF comes out over 5MB:
- Drop color count from 128 → 64 in export options (try this first)
- Reduce capture region size by 10%
- Drop FPS from 10 → 8

**3MB at 10fps is roughly 25–30 seconds of recording.** That's the sweet spot — long enough to tell the story, short enough that a developer actually watches it.

---

### After Export

1. Rename the file to something clean:
   - `governance-blocked.gif`
   - `kill-switch.gif`
   - `hitl-approval.gif`

2. Drop them in `C:\claude_code\Telsonbase\screenshots\`

3. They're already referenced in the README — just use these exact filenames and the images will appear automatically once pushed to GitHub.

---

## After Recording — Re-Disable OpenClaw (Optional)

OpenClaw can stay enabled — it's production-ready. If you want to reset `.env` to the default:
```bash
# Edit .env:
OPENCLAW_ENABLED=false
docker compose restart mcp_server
```

---

*TelsonBase v9.0.0B · Quietfire AI · March 2, 2026*
