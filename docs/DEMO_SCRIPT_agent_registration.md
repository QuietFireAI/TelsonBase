# DEMO SCRIPT: How Agents Get On The Base
## Director's Cut — Screen Recording Edition

**Production:** TelsonBase by Quietfire AI
**Runtime target:** 6–8 minutes
**Format:** Screen recording with narration (record first, narrate in post OR narrate live)
**Audience:** Developers, technical evaluators, security-conscious ops teams

---

## PRE-PRODUCTION CHECKLIST
*Do this before hitting record. No exceptions.*

```
[ ] Docker stack is running: docker compose up -d
[ ] Verify health: curl http://localhost:8000/health → {"status":"healthy"}
[ ] Dashboard is reachable: http://localhost:8000/dashboard → loads
[ ] Terminal is clean — clear it, bump font to 18pt minimum
[ ] Browser is clean — close extra tabs, use Incognito or fresh profile
[ ] OBS or Loom is armed and tested — check audio levels
[ ] Notepad/scratch pad open with your admin password ready to paste
[ ] OPENCLAW_ENABLED=true is set in .env (restart containers if you just changed this)
```

---

## SCENE 1 — ESTABLISH THE GROUND RULES
*Runtime: ~45 seconds*

**[DIRECTOR: Open a clean terminal. Nothing else on screen.]*

**ACTION:** Type this. Don't run it yet. Let it sit on screen.

```bash
curl http://localhost:8000/health
```

**[DIRECTOR: Pause 2 seconds. Then run it.]*

**[DIRECTOR: Let the response land. Point your cursor at "status: healthy". Let the viewer read it.]*

**NARRATION (if live):**
> "Stack is up. That's the only prerequisite. TelsonBase is running.
> Now — we're going to add an agent to the governed environment.
> From scratch. One API call at a time. Watch what the system does at each step."

**[DIRECTOR: Clear the terminal.]*

---

## SCENE 2 — GET AN ADMIN TOKEN
*Runtime: ~30 seconds*

**[DIRECTOR: Type this command. Swap in your real admin password.]*

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_ADMIN_PASSWORD"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo $TOKEN
```

**[DIRECTOR: Run it. A long JWT string prints. Good.]*

**NARRATION:**
> "This is my admin token. Every call to TelsonBase requires authentication.
> The governance system doesn't take anonymous requests."

**[DIRECTOR: Do NOT clear the terminal — TOKEN is in shell memory. You need it for every subsequent call.]*

---

## SCENE 3 — REGISTER THE AGENT
*Runtime: ~60 seconds. This is the money shot.*

**[DIRECTOR: Type this out slowly. This is the key call. Let viewers read it as you type.]*

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

**[DIRECTOR: Run it. Formatted JSON prints. Move cursor slowly over these three lines:]*

```
"trust_level": "quarantine",
"manners_score": 1.0,
"qms_status": "Thank_You"
```

**NARRATION:**
> "There it is. The agent is registered. It has an instance_id — that's its governed identity.
> Trust level: quarantine. That's where every agent starts. No exceptions.
> Manners score: 1.0 — clean slate. No violations yet.
> The audit chain has already logged this registration. It's in the tamper-evident record. Permanent."

**[DIRECTOR: Copy the instance_id from the response. Paste it into a variable.]*

```bash
INSTANCE_ID="paste-the-id-here"
echo $INSTANCE_ID
```

**[DIRECTOR: instance_id echoes back cleanly. Move on.]*

---

## SCENE 4 — SUBMIT AN ACTION. WATCH IT GET GATED.
*Runtime: ~60 seconds. This is the "oh, I see what this does" moment.*

**[DIRECTOR: Before typing — say this out loud.]*

**NARRATION:**
> "The agent is registered. Now it wants to do something. It wants to read a file.
> At quarantine, nothing is autonomous. Everything is gated. Watch."

**[DIRECTOR: Type and run:]*

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

**[DIRECTOR: Response prints. Move cursor slowly over:]*

```
"allowed": false,
"approval_required": true,
"trust_level_at_decision": "quarantine",
"action_category": "read_internal",
"qms_status": "Excuse_Me"
```

**NARRATION:**
> "Not blocked. Gated. There's a difference.
> 'Excuse_Me' means: hold on, a human needs to see this first.
> The agent can't execute autonomously at Quarantine. This action is now sitting
> in the approval queue — visible in the dashboard, waiting for a human decision.
> The agent didn't get a no. It got a 'wait.'"

**[DIRECTOR: Let that land for 3 seconds.]*

---

## SCENE 5 — SUBMIT A BLOCKED ACTION
*Runtime: ~30 seconds. Short and punchy.*

**NARRATION:**
> "Now let's try something that doesn't even make it to the queue."

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

**[DIRECTOR: Response prints. Point to:]*

```
"allowed": false,
"approval_required": false,
"trust_level_at_decision": "quarantine",
"action_category": "financial",
"qms_status": "Thank_You_But_No"
```

**NARRATION:**
> "Thank_You_But_No. Hard block. No queue, no approval, no second chance.
> Financial actions are blocked entirely at Quarantine. This didn't touch the approval system.
> The pipeline stopped it at Step 7 — trust level matrix — before it got anywhere near execution."

---

## SCENE 6 — SWITCH TO THE DASHBOARD
*Runtime: ~60 seconds. Visual proof.*

**[DIRECTOR: Switch to browser. Navigate to http://localhost:8000/dashboard]*

**[DIRECTOR: Find the OpenClaw tab. Click it.]*

**[DIRECTOR: Point cursor to "DocumentProcessor-v1" in the instance list. Hold.]*

**NARRATION:**
> "Everything we just did via API is visible right here.
> The agent. Its trust level — Quarantine. Manners score — 1.0.
> Action counts: you can see what was blocked, what was gated, what was allowed."

**[DIRECTOR: Click over to the Approvals tab.]*

**NARRATION:**
> "And here's that file_read request, sitting in the approval queue.
> A human operator can approve or deny it right here.
> The agent is waiting. It can't proceed until this decision is made."

**[DIRECTOR: Don't approve it yet. Navigate back to OpenClaw tab.]*

---

## SCENE 7 — PROMOTE THE AGENT ONE STEP
*Runtime: ~45 seconds. Show the ladder.*

**[DIRECTOR: Back to terminal.]*

**NARRATION:**
> "Let's say this agent has behaved well. We want to give it more autonomy.
> Promotion is one step at a time. Quarantine goes to Probation. That's the only move."

```bash
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/promote \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_level": "probation",
    "reason": "30 days of clean operation. All approval requests granted by ops team."
  }' | python3 -m json.tool
```

**[DIRECTOR: Response shows updated trust_level. Point to it.]*

```
"trust_level": "probation",
"qms_status": "Thank_You"
```

**NARRATION:**
> "Probation. That promotion — and the reason we gave — is now in the audit chain.
> Permanent record. If this agent later misbehaves, the auditor can trace exactly
> when it was promoted and who authorized it and why."

**[DIRECTOR: Now resubmit the file_read action with a new nonce.]*

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

**[DIRECTOR: Point to the change.]*

```
"allowed": true,
"approval_required": false,
"trust_level_at_decision": "probation",
"qms_status": "Thank_You"
```

**NARRATION:**
> "Same action. Different result. At Probation, internal reads are autonomous.
> The agent earned that. It didn't just get it."

---

## SCENE 8 — KILL SWITCH
*Runtime: ~30 seconds. Make it feel consequential.*

**NARRATION:**
> "Now watch what happens when we pull the kill switch."

```bash
curl -s -X POST http://localhost:8000/v1/openclaw/$INSTANCE_ID/suspend \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Anomalous credential enumeration pattern detected — suspended pending review."
  }' | python3 -m json.tool
```

**[DIRECTOR: Confirm suspended: true in response. Now immediately send an action.]*

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

**[DIRECTOR: Point to this.]*

```
"allowed": false,
"reason": "Instance suspended: Anomalous credential enumeration pattern...",
"qms_status": "Thank_You_But_No"
```

**NARRATION:**
> "Kill switch is Step 2 of the pipeline. Before trust level. Before Manners. Before everything.
> One call. The agent is frozen. Only a human admin can reinstate it.
> This is the lock the industry forgot to put on the door."

---

## SCENE 9 — CLOSING SHOT
*Runtime: ~20 seconds.*

**[DIRECTOR: Switch back to terminal. Type — don't run — one final command.]*

```bash
curl -s http://localhost:8000/v1/audit/chain/entries?limit=10 \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**[DIRECTOR: Run it. Scroll the audit entries slowly. Let viewer see openclaw.* event types.]*

**NARRATION:**
> "Everything that just happened — registration, actions, promotion, kill switch —
> it's all here. SHA-256 hash-chained. Each entry includes the hash of the one before it.
> Tamper it, and the chain breaks. That's not marketing. That's math.
>
> This is TelsonBase. This is how agents get on the base."

**[DIRECTOR: Let the audit chain sit on screen for 3 seconds. Fade or cut.]*

---

## POST-PRODUCTION NOTES

**If you're narrating in post (recording silent first):**
- Record at 1x — speak normally during post, the footage determines the pace
- Each scene has a natural pause point marked `[DIRECTOR: Let it land]` — hold 2 extra seconds there before cutting
- Don't rush Scene 3 (registration) or Scene 4 (first gated action) — those are the "I get it" moments

**Text overlays to consider (optional):**
- Scene 3: overlay "STEP: Registration → Redis + Audit Chain" in lower third
- Scene 4: overlay "PIPELINE STEP 7: Trust Level Matrix → GATED"
- Scene 5: overlay "PIPELINE STEP 7: Trust Level Matrix → BLOCKED (no queue)"
- Scene 8: overlay "PIPELINE STEP 2: Kill Switch → Checked Before Everything Else"

**Thumbnail frame:** Scene 8 terminal output — `"allowed": false` with the suspension reason. That's the frame that stops the scroll.

**Title card options:**
- "How AI Agents Get Governed (Not Just Monitored)"
- "One API Call. Then Trust Is Earned."
- "This Is What Agent Governance Actually Looks Like"

---

## DRY RUN CHECKLIST
*Walk through this once before hitting record.*

```
[ ] Scene 1: health check returns healthy
[ ] Scene 2: TOKEN is set in shell — echo $TOKEN shows a long string, not empty
[ ] Scene 3: registration returns JSON with trust_level: quarantine
[ ] Scene 3: INSTANCE_ID variable is set — echo $INSTANCE_ID shows a 16-char string
[ ] Scene 4: file_read action returns allowed: false, approval_required: true
[ ] Scene 5: payment_send action returns allowed: false, approval_required: false
[ ] Scene 6: dashboard OpenClaw tab shows DocumentProcessor-v1
[ ] Scene 6: Approvals tab shows the pending file_read request
[ ] Scene 7: promote to probation returns trust_level: probation
[ ] Scene 7: resubmit file_read returns allowed: true
[ ] Scene 8: suspend returns suspended: true
[ ] Scene 8: post-suspend action returns allowed: false with suspension reason
[ ] Scene 9: audit chain shows openclaw.* events in chronological order
```

If any step fails during dry run, stop and fix before recording. The worst thing for a demo is an unexpected error mid-take.

---

*Demo Script v1.0 | TelsonBase v9.0.0B | March 1, 2026 | Quietfire AI*
