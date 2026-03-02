# TelsonBase — GIF Voice-Over Script

**Purpose:** Read these aloud while recording. Speak deliberately — one beat between sentences.
**Pace:** ~90 words/minute (explanation pace, not conversational). Each script is timed to its GIF.

---

## GIF 1 — Governance Blocked (~20 seconds)

**Word count:** ~35 words | **Pace:** Slow and clear

> "This is a research agent — sitting in quarantine, the lowest trust tier.
> Watch what happens when it tries to make an external API call to Stripe.
> TelsonBase blocks it in under a hundred milliseconds.
> The agent never touches the resource. Decision written to the audit chain."

**Timing cue:**
- Open sentence while pointing at agent card in browser
- Pause 1 second before hitting Enter on the curl command
- Read "blocks it in under a hundred milliseconds" as the response lands
- Switch to audit trail — read final sentence as the entry appears

---

## GIF 2 — Kill Switch (~30 seconds)

**Word count:** ~52 words | **Pace:** Measured — let the second rejection land

> "The data agent is live. Governed, but active — watch it respond normally.
> This is the kill switch. One API call.
> Agent suspended.
> Now watch what happens to every action it tries after that.
> Rejected — before trust level, before behavioral scoring, before anything.
> The suspension is Redis-persisted. It survives restarts."

**Timing cue:**
- Read first sentence while firing the pre-suspension action
- Pause after "One API call" — let the suspend command sit in terminal before hitting Enter
- Read "Agent suspended" as the response lands
- Pause 1 second, then fire the post-suspension action
- Read "Rejected" as that response lands
- Read Redis line while pointing at the SUSPENDED badge in browser

---

## GIF 3 — HITL Approval (~40 seconds)

**Word count:** ~65 words | **Pace:** Deliberate — pause at the pending state so viewer reads the card

> "Integration agent is on probation — one tier up from quarantine.
> It attempts an external API call.
> TelsonBase doesn't block it. It doesn't allow it either.
> It holds it.
> Refresh the approvals queue — the action is sitting here, pending human sign-off.
> The agent is paused. Nothing moves until a human decides.
> Approve.
> Decision logged to the audit chain. That's the human-in-the-loop gate."

**Timing cue:**
- Read opening two sentences while firing the curl command
- Read "holds it" as the `approval_required: true` response lands — pause 2 seconds
- Read approvals queue sentence while refreshing the browser
- Pause 2 seconds after "pending human sign-off" — let viewer read the card
- Read "Approve" exactly when you click the button
- Read final sentence as the card clears and you switch to audit trail

---

## Recording Tips

**Before you start each GIF:**
- Read through the script once out loud to check your pace
- The pauses matter as much as the words — dead air on screen needs narration, and narration needs the screen to catch up

**If your recording runs long:**
- Cut the last sentence of each script — they're all elaboration
- GIF 1 cuts to: "...The agent never touches the resource."
- GIF 2 cuts to: "...Rejected before anything."
- GIF 3 cuts to: "...Nothing moves until a human decides. Approve."

**Post-production option:**
- Record audio separately (voice memo, Audacity) and sync to GIF timing in any editor
- Alternatively, render as MP4 with audio instead of GIF — GitHub README supports video via `<video>` tags, and MP4 with voice-over is more compelling than a silent GIF

---

*TelsonBase v9.0.0B · Quietfire AI · March 2, 2026*
