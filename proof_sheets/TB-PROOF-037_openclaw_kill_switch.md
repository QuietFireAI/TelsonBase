# TB-PROOF-037: OpenClaw Kill Switch

**Sheet ID:** TB-PROOF-037
**Claim Source:** telsonbase.com — OpenClaw Integration
**Status:** VERIFIED
**Last Verified:** February 23, 2026
**Version:** 7.4.0CC

---

## Exact Claim

> "Kill switch — immediately suspend any OpenClaw instance. All actions rejected until human review and reinstatement."

## Verdict

VERIFIED — `OpenClawManager.suspend_instance()` immediately suspends a claw. The kill switch is checked at Step 2 of the governance pipeline — before trust levels, before Manners, before everything except "does this claw exist?"

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/openclaw.py` | `suspend_instance()` | Kill switch implementation |
| `core/openclaw.py` | `reinstate_instance()` | Human-reviewed reinstatement |
| `core/openclaw.py` | `is_suspended()` | Redis-backed suspension check |
| `core/openclaw.py` | `evaluate_action()` Step 2 | Kill switch checked before trust level |
| `api/openclaw_routes.py` | `POST /{id}/suspend` | REST endpoint for kill switch |
| `api/openclaw_routes.py` | `POST /{id}/reinstate` | REST endpoint for reinstatement |
| `tests/test_openclaw.py` | `TestKillSwitch` | 7 kill switch test cases |

### Kill Switch Behavior
| State | Action Result |
|---|---|
| **Active** | Normal governance pipeline applies |
| **Suspended** | ALL actions immediately rejected (Step 2) |
| **Reinstated** | Returns to previous trust level, normal governance resumes |

### What Happens on Suspend
1. `instance.suspended = True` set in memory
2. `_suspended_ids` set updated (fast lookup)
3. Persisted to Redis key `openclaw:suspended:{id}` (survives restarts)
4. `AuditEventType.OPENCLAW_SUSPENDED` logged to cryptographic audit chain
5. Logger emits `REM: KILL SWITCH` warning

### What Happens on Reinstate
1. `instance.suspended = False` cleared
2. `_suspended_ids` entry removed
3. Redis key `openclaw:suspended:{id}` deleted
4. `AuditEventType.OPENCLAW_REINSTATED` logged
5. Instance resumes at its existing trust level (not reset)

### Kill Switch Priority in Governance Pipeline
```
Step 1: Instance exists?        → reject if not
Step 2: KILL SWITCH (suspended?) → reject IMMEDIATELY ← HERE
Step 3: Nonce replay?           → (not reached if suspended)
Step 4: Tool blocked?           → (not reached if suspended)
Step 5: Classify action          → (not reached if suspended)
Step 6: Manners compliance          → (not reached if suspended)
Step 7: Trust level check        → (not reached if suspended)
Step 8: Anomaly detection        → (not reached if suspended)
```

### Test Coverage
- `test_suspend_blocks_all_actions` — Suspended instance has ALL actions rejected
- `test_suspend_sets_metadata` — Suspension metadata correctly set
- `test_reinstate_allows_actions` — Actions work again after reinstatement
- `test_reinstate_clears_metadata` — All suspension metadata cleared
- `test_reinstate_nonsuspended_fails` — Cannot reinstate non-suspended instance
- `test_suspend_nonexistent_fails` — Cannot suspend nonexistent instance
- `test_kill_switch_checked_before_trust` — Even CITIZEN level is blocked when suspended

## Verification Command

```bash
grep -n "suspend\|kill.switch\|KILL SWITCH\|reinstate" core/openclaw.py | head -15
```

## Expected Result

References to suspend_instance, reinstate_instance, kill switch check at Step 2, and Redis persistence.

---

*Sheet TB-PROOF-037 | TelsonBase v7.4.0CC | February 23, 2026*
