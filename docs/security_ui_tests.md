# TelsonBase v7.1.0CC — Admin Console UI Test Plan

**Date:** 2026-02-12
**Tester:** Jeff
**URL:** `http://localhost:8000/dashboard`
**Mode:** Start in Demo, then repeat key tests in Live

---

## 1. Page Load & Header

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 1.1 | Open `/dashboard` in browser | Page loads without console errors, dark theme renders |  |
| 1.2 | Header shows version | "v7.1.0CC" visible next to Quietfire AI |  |
| 1.3 | DEMO badge visible | Amber "DEMO" badge shows in header when disconnected |  |
| 1.4 | Tab bar renders all 15 tabs | Scroll horizontally if needed — all visible: Overview → Users & Roles → Sessions → Agents → Approvals → Anomalies → Audit Trail → Tenants → Compliance → Security → Toolroom → LLM / Chat → Federation → QMS Log → Sovereign |  |
| 1.5 | Tab overflow scrolls | On narrow window, tab bar scrolls horizontally without breaking layout |  |

---

## 2. Connection Panel

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 2.1 | Click Offline button | Connection panel slides in from right |  |
| 2.2 | Enter bad API key, click Connect | Error message: "Invalid API key" or "Connection failed" |  |
| 2.3 | Enter valid key + URL, click Connect | Panel closes, header shows green "Live", DEMO badge disappears |  |
| 2.4 | Current user appears in header | Username + role badge visible next to refresh button |  |
| 2.5 | Logout button works | Click logout icon → reverts to demo mode, user display clears |  |
| 2.6 | Disconnect from panel | Open panel while connected → Disconnect button → reverts to demo |  |

---

## 3. Overview Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 3.1 | Top row: 4 status cards | System Status, Pending Approvals, Unresolved Anomalies, Registered Agents |  |
| 3.2 | Second row: 4 new cards | Users (5 active), Tenants (3 tenants), Active Sessions (4), Audit Chain (Valid) |  |
| 3.3 | Compliance summary row | 5 small cards: Legal Holds, Open Breaches, Training Overdue, HITRUST %, Active BAAs |  |
| 3.4 | Click any compliance card | Navigates to Compliance tab |  |
| 3.5 | Sovereign gauge clickable | Click gauge → navigates to Sovereign tab |  |
| 3.6 | Services grid shows 6 services | redis, mqtt, ollama, celery, toolroom, federation — all green dots |  |
| 3.7 | Recent QMS Activity | Shows last 5 QMS entries with colored chains |  |

---

## 4. Users & Roles Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 4.1 | User table renders | 5 demo users with columns: User, Email, Roles, MFA, Status, Last Login, Sessions |  |
| 4.2 | Role badges color-coded | super_admin=red, admin=orange, security_officer=yellow, operator=blue, viewer=gray |  |
| 4.3 | MFA column shows status | "Enrolled" (green check) or "Not enrolled" (gray) |  |
| 4.4 | Active/Disabled badges | Active=green badge, Disabled=red badge (agarcia should be disabled) |  |
| 4.5 | Session count column | Numbers, cyan when >0, gray when 0 |  |
| 4.6 | Create User button | Click → prompts for username, email, password, role → new row appears in table |  |
| 4.7 | Cancel create flow | Click Create User → cancel any prompt → no new user added |  |

---

## 5. Sessions Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 5.1 | Summary cards | 3 cards: Total Active (4), By Admin Role (count of admin/super_admin), Idle >5min (varies) |  |
| 5.2 | Session table renders | 4 rows with: Session ID, User, IP, Client, Role, Idle, Actions |  |
| 5.3 | Idle time color-coded | Green (<5min), Yellow (5-10min), Red (>10min) — values depend on when page loaded |  |
| 5.4 | Terminate button | Click Terminate on a session → row disappears from table |  |
| 5.5 | Cleanup Expired button | Click → removes sessions with idle >10min |  |
| 5.6 | Role badges in table | Each session shows role as cyan badge |  |

---

## 6. Agents Tab (existing — verify unchanged)

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 6.1 | 4 agent cards render | backup_agent, ollama_agent, monitor_agent, web_agent |  |
| 6.2 | Signing key indicator | Green pulse for registered, red dot for web_agent |  |
| 6.3 | Expand capabilities | Click "Show capabilities" → list appears |  |

---

## 7. Approvals Tab (existing — verify unchanged)

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 7.1 | 2 pending approvals render | Delete_Expired_Snapshots (normal) and Download_Model (high) |  |
| 7.2 | Approve/Reject works | Click Approve → card disappears, "Demo mode — actions simulated" note visible |  |

---

## 8. Anomalies Tab (existing — verify unchanged)

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 8.1 | 1 anomaly renders | web_agent unsigned_request, medium severity |  |
| 8.2 | Evidence expandable | Click "Show evidence" → JSON appears |  |

---

## 9. Audit Trail Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 9.1 | 4 status cards | Chain ID, Entries (1247), Integrity (Valid/green), and action buttons card |  |
| 9.2 | Verify Chain button | Click → alert shows "Chain integrity: VALID (demo)" |  |
| 9.3 | Export JSON button | Click → downloads `audit_export.json` file |  |
| 9.4 | Open exported file | Valid JSON with 5 audit entries |  |
| 9.5 | Entry table renders | 5 rows: sequence, timestamp, event_type badge, actor, description, hash |  |
| 9.6 | Event type badges | Purple-styled badges (auth.login, approval.decided, etc.) |  |
| 9.7 | Hash column | Green monospace hash snippets |  |

---

## 10. Tenants & Matters Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 10.1 | 3 tenant cards | Quietfire AI Legal (law_firm), Anderson Brokerage, Internal Ops |  |
| 10.2 | Tenant status badges | All show green "active" |  |
| 10.3 | Type and matter count | Each card shows type and matter count |  |
| 10.4 | New Tenant button | Click → prompts name + type → new card appears |  |
| 10.5 | Matters table renders | 3 rows: Smith v. Anderson, Estate of Williams, SEC Filing Q4 |  |
| 10.6 | Litigation hold badge | Smith v. Anderson shows amber "HOLD" badge |  |
| 10.7 | Matter status badges | active=green, closed=gray |  |
| 10.8 | Matter type badges | litigation, estate, regulatory in purple |  |

---

## 11. Compliance Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 11.1 | Sub-navigation renders | 6 pill buttons: Overview, Legal Holds, Breach, Training, HITRUST, BAA |  |
| 11.2 | Overview sub-tab (default) | 5 status cards with counts |  |
| 11.3 | Legal Holds sub-tab | Active (2) and Total (5) counters |  |
| 11.4 | Breach sub-tab | Open (0), Total (1), Overdue Notifications (0) |  |
| 11.5 | Training sub-tab | Completed (4), Total (5), Overdue (1) + progress bar at 80% |  |
| 11.6 | HITRUST sub-tab | 87% posture, 42/48 controls, blue progress bar |  |
| 11.7 | BAA sub-tab | Active (3), Expiring Soon (1), Total (4) |  |
| 11.8 | Sub-tab switching | Click between pills — content swaps without page reload |  |
| 11.9 | Active pill highlighted | Selected pill is solid blue, others are outlined |  |

---

## 12. Security Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 12.1 | 3 summary cards | MFA Adoption (3/5, 60%), Emergency Access (0), Email Verified (4/5) |  |
| 12.2 | MFA Status by User panel | Lists all 5 users with "MFA Enrolled" or "Not Enrolled" badges |  |
| 12.3 | Emergency Access panel | Green "No active emergency access" message |  |
| 12.4 | Layout: 2-column grid | MFA panel left, Emergency panel right |  |

---

## 13. Toolroom Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 13.1 | 3 summary cards | Registered Tools (4), Active Checkouts (2), Restricted Tools (1) |  |
| 13.2 | Tool Registry table | 4 rows: web_scraper, pdf_parser, email_sender, db_query |  |
| 13.3 | Tool status badges | approved=green, restricted=yellow |  |
| 13.4 | Category badges | Purple badges for each category |  |
| 13.5 | Active Checkouts table | 2 rows: web_agent has web_scraper, monitor_agent has db_query |  |
| 13.6 | Checkout timestamps | Readable date/time in mono font |  |

---

## 14. LLM / Chat Tab (existing — verify works under new name)

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 14.1 | Tab labeled "LLM / Chat" | Icon is cpu, not messageCircle |  |
| 14.2 | Chat interface renders | Model selector, message area, input box |  |
| 14.3 | Demo models listed | llama3.2 (demo), mistral (demo) |  |
| 14.4 | Send demo message | Type message → Enter → demo response appears |  |

---

## 15. Federation Tab (existing — verify unchanged)

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 15.1 | 1 federation card | Quietfire AI Ohio East, established, standard trust |  |

---

## 16. QMS Log Tab (existing — verify unchanged)

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 16.1 | Filter bar renders | Status buttons + agent dropdown |  |
| 16.2 | 10 QMS entries visible | Colored chains with hashes |  |
| 16.3 | Filters work | Click "PLEASE" filter → only Please entries shown |  |

---

## 17. Sovereign Tab (existing — verify unchanged)

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 17.1 | Large gauge shows 94 | Green "Sovereign" label |  |
| 17.2 | 5 factor breakdown | LLM Locality, Data Residency, Network Exposure, Backup Sovereignty, Auth Posture |  |

---

## 18. Cross-Cutting / Responsiveness

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 18.1 | Resize to mobile width (~400px) | Cards stack single-column, tables scroll horizontally, no content overflow |  |
| 18.2 | Resize to tablet (~768px) | 2-column grids where specified |  |
| 18.3 | Full desktop (~1440px) | Max-width container centered, 3-4 column grids |  |
| 18.4 | Auto-refresh when connected | Data refreshes every 30 seconds (check refresh spinner) |  |
| 18.5 | Manual refresh button | Click refresh icon → spinner animates → data reloads |  |
| 18.6 | Demo note on each new tab | "Demo data — connect to API for..." message at bottom of each new tab |  |
| 18.7 | Browser console clean | No React errors, no 404s, no uncaught exceptions in demo mode |  |

---

## How to Run

1. Start TelsonBase: `docker compose up -d` (or however the stack runs)
2. Open `http://localhost:8000/dashboard`
3. Run through tests **in demo mode first** (no connection)
4. Connect with valid API key
5. Re-run tests 2.3–2.5, then spot-check each tab with live data
6. Screenshot anything broken or unexpected
7. Note any layout/UX issues in the Pass? column

---

## Known Limitations (Demo Mode)

- Create User uses `prompt()` dialogs — functional but not pretty
- Session idle times are computed from page load, so colors shift over time
- Compliance sub-panels show summary counts only (no individual record lists in demo)
- Toolroom and Security don't have live API wiring yet (read-only demo data)
- No pagination on audit entries or QMS log yet
