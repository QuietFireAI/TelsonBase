# DEMO WALKTHROUGH — Every Step, Every Click
## Scene-by-Scene Operator Guide

**Who this is for:** You. The person running the demo.
**What it covers:** Every physical action — what to open, what to type, what key to press, what to look for, and what "success" looks like before you move forward.
**Environment:** Windows 11, WSL2 terminal, Docker Desktop running, TelsonBase stack up.

---

## BEFORE SCENE 1 — Get Your House In Order

These happen before the recording starts. Do all of them.

**Step 1 — Open Docker Desktop**
1. Click the Start menu (Windows key)
2. Type `Docker Desktop` → press Enter
3. Wait for the whale icon in the system tray (bottom-right) to stop animating
4. When it shows a green dot and says "Running" — Docker is ready

**Step 2 — Open WSL2 Terminal**
1. Click the Start menu
2. Type `Terminal` → press Enter (opens Windows Terminal)
3. Click the dropdown arrow (∨) next to the + tab at the top
4. Select **Ubuntu** (or whichever WSL distribution you have)
5. You should see a prompt like: `jeff@DESKTOP-XXXXX:~$`

**Step 3 — Navigate to TelsonBase**
1. In the terminal, type exactly:
   ```
   cd /mnt/c/Claude_Code/TelsonBase
   ```
2. Press Enter
3. Your prompt now shows the TelsonBase directory. Confirm:
   ```
   ls docker-compose.yml
   ```
4. You should see: `docker-compose.yml` printed back. If you get "No such file" — wrong directory.

**Step 4 — Confirm the stack is running**
1. Type:
   ```
   docker compose ps
   ```
2. Press Enter
3. Look for these services in the list — all should say `running` or `Up`:
   - `mcp_server`
   - `redis`
   - `postgres` (or `db`)
   - `traefik`
4. If anything says `Exit` or `Restarting`:
   ```
   docker compose up -d
   ```
   Wait 30 seconds. Run `docker compose ps` again.

**Step 5 — Make the terminal camera-ready**
1. Right-click in the terminal window → Settings (or Ctrl+,)
2. Under Appearance → Font size → set to **18** minimum
3. Make the terminal window fill at least half your screen
4. Type `clear` → press Enter. Clean slate.

**Step 6 — Open browser**
1. Open Chrome or Firefox
2. Go to: `http://localhost:8000/dashboard`
3. Confirm the TelsonBase dashboard loads (you may need to log in)
4. Keep this tab open — you'll switch to it in Scene 6
5. Minimize the browser for now

**Step 7 — Confirm OPENCLAW is enabled**
1. In the terminal, type:
   ```
   grep OPENCLAW_ENABLED /mnt/c/Claude_Code/TelsonBase/.env
   ```
2. Press Enter
3. You should see: `OPENCLAW_ENABLED=true`
4. If you see `false` or nothing:
   - Open `.env` in a text editor
   - Find `OPENCLAW_ENABLED` and set it to `true`
   - Save the file
   - Run: `docker compose up -d --build mcp_server`
   - Wait 60 seconds before proceeding

---

## SCENE 1 — Health Check
*Goal: Prove the stack is alive on camera*

**Step 1 — Clear the terminal**
```
clear
```
Press Enter. Screen is blank.

**Step 2 — Type the health check command (type it, don't paste — viewers should see you type)**
```
curl http://localhost:8000/health
```

**Step 3 — Pause before pressing Enter**
Let it sit on screen for 1–2 seconds. Then press Enter.

**Step 4 — Read the result**
You should see something like:
```json
{"status":"healthy","version":"9.0.0B","services":{"redis":"connected","database":"connected"}}
```

**What success looks like:** `"status":"healthy"` is present. That's the only thing that matters here.

**If you get `curl: (7) Failed to connect`:**
- The stack isn't running. Go back to Step 4 of pre-production.
- Do not record until this works.

**Step 5 — Move your cursor to hover over `"status":"healthy"` (on screen)**
Hold it there for 2 seconds. Let the viewer see it.

---

## SCENE 2 — Get an Admin Token
*Goal: Log in and store your token in a shell variable*

**Step 1 — Clear the terminal**
```
clear
```

**Step 2 — Type the login command**

Type this exactly. Replace `YOUR_ADMIN_PASSWORD` with your actual admin password:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_ADMIN_PASSWORD"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

**How to type the backslash-enter (line continuation):**
- Type `\` at the end of a line, then press Enter — the terminal continues to the next line
- The `>` prompt on the next line means it's waiting for more input — that's correct

**Step 3 — Press Enter after the closing parenthesis `)`**
The command runs. You won't see any output yet — the token is stored silently in `$TOKEN`.

**Step 4 — Confirm the token stored**
```
echo $TOKEN
```
Press Enter.

**What success looks like:** A very long string of letters and numbers prints — like:
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsI...
```
That's your JWT. It's good for the rest of the demo session.

**If you see an empty line (nothing printed):**
- The login failed. Check your password.
- Run this to see the raw error:
  ```
  curl -s -X POST http://localhost:8000/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"YOUR_ADMIN_PASSWORD"}'
  ```
- Look for `"detail"` in the response — it will tell you what went wrong.

**IMPORTANT:** Do NOT close or clear this terminal window for the rest of the demo. `$TOKEN` and `$INSTANCE_ID` live in this shell session. If the terminal closes, they're gone and you start Scene 2 over.

---

## SCENE 3 — Register the Agent
*Goal: One API call creates a governed agent identity. Show it lands at QUARANTINE.*

**Step 1 — Clear the terminal**
```
clear
```

**Step 2 — Type the registration command**

Type this slowly. This is the most important command in the demo — let viewers read it as you type:

```bash
curl -s -X POST http://localhost:8000/v1/openclaw/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DocumentProcessor-v1",
    "api_key": "demo-agent-key-abc123",
    "allowed_tools": ["file_read", "search_files", "database_query"],
    "blocked_tools": ["file_delete", "payment_send"]
  }' | python3 -m json.tool
```

**Step 3 — Press Enter**

The formatted JSON response prints. It will look like:
```json
{
    "instance_id": "a3f9c1b2e4d67890",
    "name": "DocumentProcessor-v1",
    "trust_level": "quarantine",
    "manners_score": 1.0,
    "action_count": 0,
    "actions_allowed": 0,
    "actions_blocked": 0,
    "actions_gated": 0,
    "suspended": false,
    "registered_at": "2026-02-26T14:32:10.000Z",
    "qms_status": "Thank_You"
}
```

**What success looks like:**
- `"trust_level": "quarantine"` — always, no exceptions
- `"qms_status": "Thank_You"` — registration accepted
- `"instance_id"` — a 16-character string. **You need this. Do the next step immediately.**

**Step 4 — Store the instance_id**

Look at the `instance_id` value in the response. Copy it. Then type:
```bash
INSTANCE_ID="paste-the-16-char-id-here"
```
Press Enter. Then confirm:
```bash
echo $INSTANCE_ID
```
Press Enter. The ID echoes back. Good.

**Step 5 — On camera: move your cursor slowly over these three lines**
```
"trust_level": "quarantine",
"manners_score": 1.0,
"qms_status": "Thank_You"
```
Pause 1 second on each. Let viewers read them.

**If you get `{"detail": "Not authenticated"}`:**
- Your `$TOKEN` expired or wasn't set. Go back to Scene 2.

**If you get `{"detail": "OpenClaw governance is not enabled"}`:**
- `OPENCLAW_ENABLED=true` is not in your `.env`. Go to pre-production Step 7.

---

## SCENE 4 — First Action: File Read Gets GATED
*Goal: Show that at Quarantine, even a simple read requires human approval*

**Step 1 — Clear the terminal**
```
clear
```

**Step 2 — Type the action evaluation call**
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/action \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "file_read",
    "tool_args": {"path": "/data/contracts/client-agreement.pdf"},
    "nonce": "demo-nonce-001"
  }' | python3 -m json.tool
```

**Step 3 — Press Enter**

Response:
```json
{
    "allowed": false,
    "reason": "Action requires approval at trust level 'quarantine'",
    "action_category": "read_internal",
    "trust_level_at_decision": "quarantine",
    "approval_required": true,
    "approval_id": "appr-xxxxxxxxxxxxxxxx",
    "manners_score_at_decision": 1.0,
    "anomaly_flagged": false,
    "qms_status": "Excuse_Me"
}
```

**What success looks like:**
- `"allowed": false` — agent cannot proceed autonomously
- `"approval_required": true` — it's in the queue, not hard-blocked
- `"qms_status": "Excuse_Me"` — TelsonBase's way of saying "hold on, human needed"

**Step 4 — On camera: move cursor slowly over these lines**
```
"allowed": false,
"approval_required": true,
"qms_status": "Excuse_Me"
```

**Key distinction to understand (and say if narrating live):**
- `approval_required: true` = GATED. Agent is waiting for a human. It didn't get a hard no.
- `approval_required: false` + `allowed: false` = BLOCKED. Full stop. No queue.
- You'll show the difference in Scene 5.

---

## SCENE 5 — Second Action: Payment Gets HARD BLOCKED
*Goal: Show that some actions don't even reach the approval queue*

**Step 1 — Clear the terminal**
```
clear
```

**Step 2 — Type the payment action call**
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/action \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "payment_send",
    "tool_args": {"amount": 5000, "to": "external-account"},
    "nonce": "demo-nonce-002"
  }' | python3 -m json.tool
```

**Step 3 — Press Enter**

Response:
```json
{
    "allowed": false,
    "reason": "Action category 'financial' blocked at trust level 'quarantine'",
    "action_category": "financial",
    "trust_level_at_decision": "quarantine",
    "approval_required": false,
    "approval_id": null,
    "manners_score_at_decision": 1.0,
    "anomaly_flagged": false,
    "qms_status": "Thank_You_But_No"
}
```

**What success looks like:**
- `"allowed": false`
- `"approval_required": false` — didn't go to the queue at all
- `"qms_status": "Thank_You_But_No"` — hard block

**Step 4 — On camera: slowly compare these two lines side by side**

Point back to Scene 4 result (scroll up if needed, or have them on split screen):
```
Scene 4 (file read):    "approval_required": true,   "qms_status": "Excuse_Me"
Scene 5 (payment):      "approval_required": false,  "qms_status": "Thank_You_But_No"
```

That contrast IS the point of this scene.

---

## SCENE 6 — Switch to the Dashboard
*Goal: Show that everything we just did via API is visible in the UI*

**Step 1 — Switch to your browser window**
(Press Alt+Tab or click the browser in the taskbar)

**Step 2 — Navigate to the OpenClaw tab**
1. You should be on `http://localhost:8000/dashboard`
2. Find the tab or menu item that says **OpenClaw** (or "Agents" — look for the claw icon)
3. Click it

**Step 3 — Find DocumentProcessor-v1 in the list**
1. You should see a row or card for "DocumentProcessor-v1"
2. It shows: trust level = quarantine, manners score = 1.0
3. Action counts: you'll see actions_blocked and actions_gated have numbers now

**Step 4 — On camera: slowly hover over the instance row**
Let viewers see: name, trust level, action counts. Hold for 3 seconds.

**Step 5 — Navigate to the Approvals tab**
1. Find the tab labeled **Approvals** or **Approval Queue** or **HITL**
2. Click it
3. You should see the pending `file_read` request from Scene 4 waiting here

**Step 6 — On camera: hover over the pending approval**
Show: what action it is, what agent submitted it, what the status is (pending).

**Do NOT approve or deny it here.** Leave it pending. Move on.

**If you don't see DocumentProcessor-v1 in the OpenClaw tab:**
- Hard-refresh the browser (Ctrl+Shift+R)
- If still not there: the registration may have failed silently. Go back to terminal, run Scene 3 again with a different name, confirm the response shows `"qms_status": "Thank_You"`.

---

## SCENE 7 — Promote the Agent, Then Re-Test
*Goal: Show that the same action has a different result after earning trust*

**Step 1 — Switch back to the terminal**
(Alt+Tab)

**Step 2 — Clear the terminal**
```
clear
```

**Step 3 — Type the promotion call**
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/promote \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_level": "probation",
    "reason": "30 days of clean operation. All approval requests granted by ops team."
  }' | python3 -m json.tool
```

**Step 4 — Press Enter**

Response should show:
```json
{
    "instance_id": "...",
    "name": "DocumentProcessor-v1",
    "trust_level": "probation",
    "qms_status": "Thank_You"
}
```

**What success looks like:** `"trust_level": "probation"` — it moved up one step.

**Step 5 — On camera: point to `"trust_level": "probation"`**
Hold for 2 seconds.

**Step 6 — Clear the terminal**
```
clear
```

**Step 7 — Resubmit the exact same file_read action (new nonce)**
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/action \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "file_read",
    "tool_args": {"path": "/data/contracts/client-agreement.pdf"},
    "nonce": "demo-nonce-003"
  }' | python3 -m json.tool
```

**Note:** The nonce changed from `demo-nonce-001` to `demo-nonce-003`. Every action call needs a unique nonce. Reusing one returns "Nonce replay detected."

**Step 8 — Press Enter**

Response:
```json
{
    "allowed": true,
    "reason": "Action permitted at trust level 'probation'",
    "action_category": "read_internal",
    "trust_level_at_decision": "probation",
    "approval_required": false,
    "qms_status": "Thank_You"
}
```

**What success looks like:**
- `"allowed": true` — same action, now autonomous
- `"qms_status": "Thank_You"` — no queue, no human needed

**Step 9 — On camera: point back and forth between Scene 4 result and this result**

Scroll up to Scene 4 if you need to. The contrast is:
```
Scene 4 (Quarantine):  "allowed": false,  "approval_required": true
Scene 7 (Probation):   "allowed": true,   "approval_required": false
```

Same action. Same agent. Different trust level. Different result. That's earned trust.

---

## SCENE 8 — Kill Switch
*Goal: One call freezes the agent. Show that nothing gets through after.*

**Step 1 — Clear the terminal**
```
clear
```

**Step 2 — Type the suspend call**
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/suspend \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Anomalous credential enumeration pattern detected — suspended pending review."
  }' | python3 -m json.tool
```

**Step 3 — Press Enter**

Response:
```json
{
    "instance_id": "...",
    "name": "DocumentProcessor-v1",
    "suspended": true,
    "qms_status": "Thank_You"
}
```

**What success looks like:** `"suspended": true`

**Step 4 — Immediately (no clear, no pause) — submit another action**

Type this right after the suspend response, while it's still on screen:
```bash
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/action \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "file_read",
    "tool_args": {"path": "/data/anything.pdf"},
    "nonce": "demo-nonce-004"
  }' | python3 -m json.tool
```

**Step 5 — Press Enter**

Response:
```json
{
    "allowed": false,
    "reason": "Instance suspended: Anomalous credential enumeration pattern detected — suspended pending review.",
    "trust_level_at_decision": "probation",
    "approval_required": false,
    "qms_status": "Thank_You_But_No"
}
```

**What success looks like:**
- `"allowed": false` — frozen
- The suspension `"reason"` appears verbatim in the block response
- `"qms_status": "Thank_You_But_No"`

**Step 6 — On camera: point to `"reason"` field**

The exact text you typed in the suspend call comes back as the block reason. That's not coincidence — the suspension reason travels with every blocked action so the audit trail is self-documenting.

**What the kill switch actually does (say if narrating):**
> "This is Step 2 of the governance pipeline. Before trust level. Before Manners. Before anything except 'does this agent exist?' One call. The agent is frozen. The only way back is a human admin calling reinstate."

---

## SCENE 9 — Audit Chain
*Goal: Show that every action is permanently recorded and hash-chained*

**Step 1 — Clear the terminal**
```
clear
```

**Step 2 — Type the audit chain query**
```bash
curl -s "http://localhost:8000/v1/audit/chain/entries?limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Step 3 — Press Enter**

You'll see 10 audit entries. Scroll through them slowly on camera. Look for entries with these event types:
```
"OPENCLAW_REGISTERED"
"OPENCLAW_ACTION_BLOCKED"
"OPENCLAW_ACTION_ALLOWED"
"OPENCLAW_TRUST_PROMOTED"
"OPENCLAW_INSTANCE_SUSPENDED"
```

Each entry has a `hash` field and a `previous_hash` field. The current entry's hash is computed from the previous entry's hash — that's the chain. Tamper one entry and every hash after it breaks.

**Step 4 — On camera: scroll slowly**
Let the viewer see multiple entries with `"event_type": "OPENCLAW_..."` labels.

**What success looks like:** You see your exact sequence of events in chronological order — registration, blocked actions, promotion, kill switch — all logged.

**Step 5 — Hold on the last entry for 3 seconds**
Then cut.

---

## AFTER THE RECORDING — RESET FOR THE NEXT TAKE

If you need to record again with a clean slate:

**Option A — Re-register with a new name**
```bash
# Just change the name and api_key — creates a fresh instance
# Use a new name like "DocumentProcessor-v2"
```

**Option B — Full reset (clean all OpenClaw state)**
```bash
docker compose exec redis redis-cli KEYS "openclaw:*" | xargs docker compose exec redis redis-cli DEL
```
This clears all OpenClaw instances from Redis. The stack keeps running. Re-run Scene 3 fresh.

---

## QUICK REFERENCE — Commands at a Glance

Copy these into a scratch notepad before recording. Use for reference if you blank mid-take.

```bash
# Scene 2 — Login
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_PASSWORD"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Scene 3 — Register
curl -s -X POST http://localhost:8000/v1/openclaw/register \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"DocumentProcessor-v1","api_key":"demo-agent-key-abc123",
       "allowed_tools":["file_read","search_files","database_query"],
       "blocked_tools":["file_delete","payment_send"]}' | python3 -m json.tool

# Scene 3 — Store instance ID
INSTANCE_ID="paste-id-here"

# Scene 4 — Gated action (file_read at quarantine)
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/action \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tool_name":"file_read","tool_args":{"path":"/data/contracts/client-agreement.pdf"},"nonce":"demo-nonce-001"}' | python3 -m json.tool

# Scene 5 — Blocked action (payment at quarantine)
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/action \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tool_name":"payment_send","tool_args":{"amount":5000,"to":"external-account"},"nonce":"demo-nonce-002"}' | python3 -m json.tool

# Scene 7 — Promote to probation
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/promote \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"new_level":"probation","reason":"30 days clean operation. All approvals granted."}' | python3 -m json.tool

# Scene 7 — Re-test file_read at probation (new nonce!)
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/action \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tool_name":"file_read","tool_args":{"path":"/data/contracts/client-agreement.pdf"},"nonce":"demo-nonce-003"}' | python3 -m json.tool

# Scene 8 — Kill switch
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/suspend \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"reason":"Anomalous credential enumeration pattern detected — suspended pending review."}' | python3 -m json.tool

# Scene 8 — Action after kill switch (new nonce!)
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/action \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tool_name":"file_read","tool_args":{"path":"/data/anything.pdf"},"nonce":"demo-nonce-004"}' | python3 -m json.tool

# Scene 9 — Audit chain
curl -s "http://localhost:8000/v1/audit/chain/entries?limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## NONCE TRACKER
*Each action call needs a unique nonce. Track them here so you don't accidentally reuse one.*

| Scene | Nonce Used |
|---|---|
| Scene 4 (file_read @ quarantine) | `demo-nonce-001` |
| Scene 5 (payment @ quarantine) | `demo-nonce-002` |
| Scene 7 (file_read @ probation) | `demo-nonce-003` |
| Scene 8 (action after kill switch) | `demo-nonce-004` |

If you do a second take, increment all nonces: `demo-nonce-101`, `demo-nonce-102`, etc. Or just use `$(uuidgen)` in place of the nonce string — generates a fresh UUID automatically.

---

*Walkthrough v1.0 | TelsonBase v9.0.0B | March 1, 2026 | Quietfire AI*
