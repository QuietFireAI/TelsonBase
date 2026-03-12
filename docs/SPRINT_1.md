# TelsonBase — Sprint 1 Backlog

Post-launch hardening. These are known gaps — documented, not forgotten.

---

## Backend

### RBAC Redis Persistence
**What:** `RBAC._users` is in-memory only. On restart or multi-worker deploy, users reset.
**Why it matters:** Blocks `WEB_CONCURRENCY=2`. Production deployments need persistence.
**Constraint:** `WEB_CONCURRENCY=1` until fixed.

### Agent Deregister Endpoint
**What:** No `DELETE /v1/openclaw/{id}` endpoint exists.
**Why it matters:** No clean way to remove an agent from governance. Workaround: delete Redis keys manually on server.

### Governance Events in Audit Chain
**What:** Promote, demote, register, suspend actions are not written to the audit chain.
**Why it matters:** The audit trail should record every governance decision. Currently only shows `security.alert`, `system.startup`, `auth.success` etc.
**Visible symptom:** Agent Governance detail panel shows empty audit trail after promote/demote.

### Demotion Review Hard-Block
**What:** Demotion from AGENT tier should require a review step before taking effect.
**Why it matters:** Prevents accidental apex-tier demotion without a paper trail.

### Federation (TelsonBase-to-TelsonBase)
**What:** New Federation Connection modal is functional but the backend endpoint errors out.
**Why it matters:** Multi-node TelsonBase deployments can't federate.
**Notes:** UI modal is complete and light-themed. Backend wiring is the gap.

---

## Frontend

### Replace Demo-Data Screenshots
**What:** `users-and-roles.png` and `user-console-agents.png` in `/screenshots/` still show demo users (jthompson, schen, etc.).
**Fix:** Take fresh screenshots from live server once real users are in place.

### Users & Roles — Real Users
**What:** Admin panel Users & Roles tab shows demo users in the sidebar/overview.
**Fix:** Jeff to take screenshot after live user creation.

### User Console Screenshot
**What:** No live screenshot of `user-console.html` exists for the README.
**Fix:** Take screenshot from live server.

---

## Social / Website

### HubSpot Integration
**What:** `HS_PORTAL_ID` and `HS_FORM_GUID` in `website/script.js` are placeholders.
**Fix:** Replace with real HubSpot portal and form IDs.

### Social Media Links
**What:** Nav and footer `href="#"` placeholders for social links.
**Fix:** Add real URLs when social accounts are active.

---

## Ops

### QMS Log — Live Data
**What:** QMS Log tab shows demo data in connected mode.
**Status:** Under investigation — backend may not be streaming QMS events to the panel.

---

*Last updated: 2026-03-12*
