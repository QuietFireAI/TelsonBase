# Dashboard Agent Registration — Reference Sheet

**What this covers:** How to add an agent to TelsonBase from the dashboard UI (no terminal required).

---

## Yes — The Dashboard Has a Register Agent Form

The "Register Agent" button lives on the **Agents tab** (not the OpenClaw tab).
Three places trigger the same modal:
- Top-right of the Agents tab header
- Inside the empty state message if no agents exist yet
- A "Pre-register Agent" button in the empty state description

---

## The Form — Five Fields

| Field | Type | Notes |
|---|---|---|
| Agent Type | Dropdown | OpenClaw / Generic / DID Agent |
| Agent Name | Text | Goes into audit log as-is |
| API Key | Text | The key this agent authenticates with — hashed before storage |
| Starting Trust Level | Dropdown | Quarantine (default) through Agent |
| Trust Override Justification | Text | Blank for Quarantine; required and enforced if you pick anything higher |

---

## What Happens on Submit

- DID Agent selected → redirects to Identity tab
- Above Quarantine with no justification → form blocks before the API call fires
- Live mode → POSTs to /v1/openclaw/register, refreshes OpenClaw instance list
- Demo mode → adds a local instance so the UI populates for demos

---

## One Thing to Know Before Using the Form

The API Key field has a hint: "Get one from the Connection panel."
The form does NOT generate a new key — it registers a key you already have.

**Two-step UI flow:**
1. Generate the API key (Connection panel or API)
2. Come back here and register the agent with that key

---

## Agents Tab vs. OpenClaw Tab

| Tab | Purpose |
|---|---|
| Agents tab | Register agents, see all agent types in one place |
| OpenClaw tab | Monitor registered instances — trust levels, action counts, manners scores |

Once registered via the Agents tab, the instance immediately appears in the OpenClaw tab.

---

## Click Path for Demo

1. Dashboard → Agents tab
2. Click Register Agent (top right)
3. Fill in the 5 fields
4. Submit
5. Switch to OpenClaw tab — instance appears at Quarantine

---

## Terminal vs. Dashboard — Which to Show

| Option | Shows |
|---|---|
| Terminal path | The raw machinery — API calls, JSON responses, nonces |
| Dashboard path | Accessible to non-developers — form, dropdowns, visual confirmation |

Both call the same backend endpoint. Both produce the same audit trail.

---

*Reference Sheet | TelsonBase v9.0.0B | March 1, 2026 | Quietfire AI*
