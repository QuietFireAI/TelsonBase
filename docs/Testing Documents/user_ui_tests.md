# ClawCoat v10.0.0Bminus - User Console UI Test Plan

**Date:** 2026-02-12
**Tester:** Jeff
**URL:** `http://localhost:8000/console`
**Mode:** Start in Demo, then repeat key tests in Live
**Companion file:** `security_ui_tests.md` (Admin Console tests - retained locally, not in repo)

---

## 1. Page Load & Header

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 1.1 | Open `/console` in browser | Page loads without console errors, dark theme renders |  |
| 1.2 | Header shows "User Console" label | Indigo "User Console" badge next to TelsonBase title |  |
| 1.3 | Header shows version | "v10.0.0Bminus" visible under Quietfire AI |  |
| 1.4 | DEMO badge visible | Amber "DEMO" badge shows in header when disconnected |  |
| 1.5 | Current user displayed | "kparker" with "operator" role badge visible in header |  |
| 1.6 | System health dot | Green pulsing dot visible in header (healthy) |  |
| 1.7 | Admin Console link | "Admin" link with external icon visible in header |  |
| 1.8 | Click Admin link | Navigates to `/dashboard` (Admin Console) |  |
| 1.9 | Tab bar renders 5 tabs | Home, Chat, Agents, My Approvals, Activity - centered, no overflow |  |
| 1.10 | Tab bar fits on mobile | All 5 tabs visible without horizontal scroll at ~375px width |  |

---

## 2. Connection Panel

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 2.1 | Click Offline button | Connection panel slides in from right |  |
| 2.2 | Enter bad API key, click Connect | Error message: "Invalid API key" or "Connection failed" |  |
| 2.3 | Enter valid key + URL, click Connect | Panel closes, header shows green "Live", DEMO badge disappears |  |
| 2.4 | Disconnect button works | Open panel while connected → Disconnect → reverts to demo |  |
| 2.5 | Logout button works | Click logout icon in header → reverts to demo mode |  |
| 2.6 | Shared API key with Admin Console | Connect in User Console → open `/dashboard` → already connected (same localStorage key) |  |
| 2.7 | Shared API key reverse | Connect in Admin Console → open `/console` → already connected |  |

---

## 3. Home Tab (Default)

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 3.1 | Home is default tab | Page loads with Home tab active and selected |  |
| 3.2 | Welcome card renders | Shows "Welcome back, K. Parker" with gradient background |  |
| 3.3 | Welcome card shows role | Role: "operator" in cyan mono text |  |
| 3.4 | Welcome card shows health | System: "Healthy" in green |  |
| 3.5 | Quick stats row: 3 cards | Active Agents (3), Pending Approvals (2, yellow), System Health (Healthy, green) |  |
| 3.6 | Approvals card subtitle | Shows "1 high priority" (the Download_Model request) |  |
| 3.7 | Quick action: New Chat | Card with indigo icon, click → navigates to Chat tab |  |
| 3.8 | Quick action: View Agents | Card with cyan icon, click → navigates to Agents tab |  |
| 3.9 | Quick action: Check Approvals | Card with green icon, shows "2 pending decisions", click → navigates to Approvals tab |  |
| 3.10 | Recent activity feed | 5 audit entries with timestamps, event type badges, descriptions, actors |  |
| 3.11 | Activity event type badges | Color-coded: login=blue, approval=green, security=red, default=gray |  |
| 3.12 | "View all activity" link | Click → navigates to Activity tab |  |
| 3.13 | Demo note at bottom | "Demo data - connect to API for live data" text present |  |

---

## 4. Chat Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 4.1 | Chat interface renders | Header with title, model selector, clear button; message area; input box |  |
| 4.2 | DEMO badge on chat | Amber "DEMO" badge next to "Chat" title |  |
| 4.3 | Demo models listed | Dropdown shows "llama3.2 (demo)" and "mistral (demo)" |  |
| 4.4 | Empty state message | "Chat with your local LLM" centered message with icon |  |
| 4.5 | Privacy message | "All inference runs on your hardware. Zero data leaves this machine." |  |
| 4.6 | Send demo message | Type "Hello" → Enter → user bubble appears right-aligned, indigo |  |
| 4.7 | Demo response appears | After ~800ms, assistant response appears left-aligned with model name |  |
| 4.8 | Response content | Includes "This is a demo response" and echoes the user's message |  |
| 4.9 | Timestamps visible | Both user and assistant messages show time in bottom-right |  |
| 4.10 | Thinking indicator | While waiting for response, bouncing dots appear |  |
| 4.11 | Clear button | Click "Clear" → all messages removed, empty state returns |  |
| 4.12 | Shift+Enter for newline | Pressing Shift+Enter adds a line break instead of sending |  |
| 4.13 | Send button disabled when empty | Send button at 30% opacity when input is empty |  |
| 4.14 | Chat area height | Takes most of the viewport - significantly larger than admin console's chat |  |
| 4.15 | Multiple messages | Send 3-4 messages → all visible, auto-scrolls to bottom |  |
| 4.16 | Error message (system) | If connected and Ollama down, red system message appears |  |

---

## 5. Agents Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 5.1 | Header shows count | "Agents (3 registered)" |  |
| 5.2 | 3 agent cards render | backup_agent, ollama_agent, monitor_agent |  |
| 5.3 | Agent card layout | Each card: icon, agent_id (mono), capability count, signing key dot |  |
| 5.4 | Signing key indicators | All 3 demo agents show green pulsing dot (keys registered) |  |
| 5.5 | Expand capabilities - backup_agent | Click "Show capabilities" → "perform_automated_backup", "snapshot_volumes" |  |
| 5.6 | Expand capabilities - ollama_agent | "generate_text", "summarize", "classify" |  |
| 5.7 | Expand capabilities - monitor_agent | "health_check", "anomaly_scan", "metric_collect" |  |
| 5.8 | Collapse capabilities | Click "Hide capabilities" → list collapses |  |
| 5.9 | No admin controls | No edit, delete, register, or configuration buttons visible |  |
| 5.10 | 3-column layout on desktop | Cards arrange in 3 columns at full width |  |
| 5.11 | Demo note at bottom | "Demo data - connect to API for live agent list" |  |

---

## 6. My Approvals Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 6.1 | Header shows count | "My Approvals (2 pending)" |  |
| 6.2 | Tab shows count badge | "2" badge on "My Approvals" tab button |  |
| 6.3 | 2 approval cards render | Delete_Expired_Snapshots (normal) and Download_Model (high) |  |
| 6.4 | Priority badges | "normal" in cyan, "high" in orange |  |
| 6.5 | Request IDs visible | apr-a8f3c200 and apr-b2e1d400 in mono gray |  |
| 6.6 | Agent names | backup_agent and ollama_agent shown with zap icon |  |
| 6.7 | Payload preview | JSON payload visible in each card (target, count for backup; model, size_gb for download) |  |
| 6.8 | Notes input field | Text input with "Decision notes (optional)" placeholder |  |
| 6.9 | Approve button | Green "Approve" button with check icon |  |
| 6.10 | Reject button | Red "Reject" button with X icon |  |
| 6.11 | Approve action (demo) | Click Approve → card disappears from list |  |
| 6.12 | Reject action (demo) | Click Reject → card disappears from list |  |
| 6.13 | Demo mode note | "Demo mode - actions simulated" visible on each card |  |
| 6.14 | All approved → empty state | Approve both → shows "No pending approvals" with "You're all caught up!" message |  |
| 6.15 | Tab badge updates | After approving one, tab badge changes from "2" to "1" |  |
| 6.16 | 2-column layout on desktop | Cards in 2 columns at full width |  |

---

## 7. Activity Tab

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 7.1 | Tab title | "Activity" with purple activity icon |  |
| 7.2 | QMS Log section | Card titled "QMS Log" with purple terminal icon |  |
| 7.3 | 5 QMS entries visible | All 5 demo QMS entries with timestamps, status badges, chains, hashes |  |
| 7.4 | QMS status badges | PLEASE (blue), THANK YOU (green), EXCUSE ME (yellow), PRIORITY (orange pulsing) |  |
| 7.5 | QMS chain coloring | Agent names in cyan, request IDs in purple, suffixes color-coded |  |
| 7.6 | Hash markers | Green check marks for verified hashes |  |
| 7.7 | Anomaly Alerts section | "Anomaly Alerts (1 unresolved)" header with orange icon |  |
| 7.8 | 1 anomaly card | web_agent unsigned_request, medium severity (yellow badge) |  |
| 7.9 | Anomaly "Review" badge | Yellow "Review" badge since requires_human_review is true |  |
| 7.10 | Expand anomaly evidence | Click "Show evidence" → JSON with action and target |  |
| 7.11 | No resolve button | Anomaly cards are read-only - no "Resolve" action (admin territory) |  |
| 7.12 | Audit Entries section | "Recent Audit Entries" card with blue clock icon |  |
| 7.13 | 5 audit entries | Sequence numbers, timestamps, event type badges, descriptions, actors, hashes |  |
| 7.14 | Audit sequence numbers | #1247, #1246, #1245, #1244, #1243 in mono |  |
| 7.15 | Audit hash markers | Green verified hash markers on each entry |  |
| 7.16 | Demo note at bottom | "Demo data - connect to API for live activity feed" |  |

---

## 8. Cross-Console Navigation

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 8.1 | User Console → Admin Console | Click "Admin" link in User Console header → `/dashboard` loads |  |
| 8.2 | Admin Console → User Console | Click "User Console" link in Admin Console header → `/console` loads |  |
| 8.3 | Both consoles load independently | `/console` and `/dashboard` both work when opened in separate tabs |  |
| 8.4 | API key shared | Connect in one console → other console auto-detects connection |  |
| 8.5 | Disconnect propagation | Disconnect in User Console → refresh Admin Console → also disconnected |  |

---

## 9. Tab Switching & Navigation

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 9.1 | Home → Chat | Click Chat tab → chat interface appears, Home content gone |  |
| 9.2 | Chat → Agents | Click Agents tab → agent cards appear |  |
| 9.3 | Agents → My Approvals | Click My Approvals → approval cards appear |  |
| 9.4 | My Approvals → Activity | Click Activity → QMS + anomalies + audit appear |  |
| 9.5 | Activity → Home | Click Home → welcome card + stats return |  |
| 9.6 | Active tab indicator | Active tab has cyan bottom border and cyan text |  |
| 9.7 | Inactive tab styling | Inactive tabs are gray, hover turns white |  |
| 9.8 | Count badges on tabs | Agents shows count, My Approvals shows count |  |
| 9.9 | No console errors on switch | Open browser DevTools → switch through all tabs → zero errors |  |
| 9.10 | Chat state preserved | Send messages in Chat → switch to Home → switch back → messages still there |  |

---

## 10. Responsiveness

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 10.1 | Mobile (~375px) | All cards stack single column, tab labels still readable |  |
| 10.2 | Tablet (~768px) | Stats row: 2 columns on Home, approval cards 1 column |  |
| 10.3 | Desktop (~1440px) | Stats 3 columns, agents 3 columns, approvals 2 columns |  |
| 10.4 | Header wraps gracefully | On narrow screens, header elements don't overflow |  |
| 10.5 | Chat input usable on mobile | Textarea and send button accessible, not cut off |  |
| 10.6 | QMS chains wrap | Long QMS chains wrap within their container, no horizontal overflow |  |

---

## 11. Auto-Refresh & Live Data

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 11.1 | Auto-refresh interval | When connected, data refreshes every 30 seconds (watch refresh icon) |  |
| 11.2 | Manual refresh button | Click refresh icon → spinner animates → data reloads |  |
| 11.3 | Refresh only when connected | In demo mode, refresh button does nothing (correct behavior) |  |
| 11.4 | Approval count updates | Approve an item in another tab/API → count updates on next refresh |  |

---

## 12. Visual Differences from Admin Console

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 12.1 | Same dark theme | Color palette matches Admin Console exactly |  |
| 12.2 | Same card styling | Cards have same border, hover, radius as Admin Console |  |
| 12.3 | "User Console" label | Header clearly distinguishes from Admin Console |  |
| 12.4 | Only 5 tabs | Not 15 - simpler navigation |  |
| 12.5 | Tabs centered | Tab bar is centered, not left-aligned with overflow scroll |  |
| 12.6 | Wider content area | max-w-6xl (User) vs max-w-7xl (Admin) - content feels roomier |  |
| 12.7 | Larger chat area | Chat uses more vertical space (calc(100vh - 160px)) than admin (180px) |  |
| 12.8 | Welcome card on Home | Dashboard-style welcome - not present in Admin Console |  |
| 12.9 | Quick action cards | 3 clickable action cards - unique to User Console |  |
| 12.10 | No admin features | No Users & Roles, Sessions, Tenants, Compliance, Security, Toolroom, Federation, Sovereign, or QMS filter tabs |  |
| 12.11 | Footer present | "TelsonBase User Console v10.0.0Bminus" footer at bottom |  |

---

## 13. Edge Cases

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 13.1 | `/console` with no frontend file | If user-console.html missing → "User Console not found" message |  |
| 13.2 | `/dashboard` still works | Admin Console loads unchanged after User Console deployment |  |
| 13.3 | Empty approval list | When all approvals processed, empty state renders cleanly |  |
| 13.4 | Empty agent list | If API returns 0 agents, "No agents registered" empty state |  |
| 13.5 | Rapid tab switching | Click tabs quickly 10 times → no crashes, no stuck states |  |
| 13.6 | Chat while switching tabs | Start a chat, switch to Home mid-response → switch back → response arrived |  |
| 13.7 | Double-click approve | Click Approve twice quickly → only processes once, no error |  |

---

## How to Run

1. Start TelsonBase: `docker compose up -d`
2. Open `http://localhost:8000/console`
3. Run through tests **in demo mode first** (no connection)
4. Verify cross-links: `/console` ↔ `/dashboard`
5. Connect with valid API key
6. Re-run tests 2.3-2.5, then spot-check each tab with live data
7. Open `/dashboard` in another tab - confirm Admin Console still works
8. Screenshot anything broken or unexpected
9. Note any layout/UX issues in the Pass? column

---

## Known Limitations (Demo Mode)

- Demo user is hardcoded as "kparker" / "operator" - live mode would pull from auth
- Approvals are not filtered by user scope in demo (shows all pending)
- Activity tab QMS log uses static demo data (not live QMS feed)
- Anomaly cards are read-only - resolve action is intentionally admin-only
- No pagination on audit entries, QMS log, or agent list
- Chat model list in demo is hardcoded - live mode queries Ollama API
- Auto-refresh only fires when connected (demo mode is static)

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
