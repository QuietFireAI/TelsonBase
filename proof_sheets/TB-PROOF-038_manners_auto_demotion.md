# TB-PROOF-038: Manners Auto-Demotion

**Sheet ID:** TB-PROOF-038
**Claim Source:** telsonbase.com — Control Your Claw
**Status:** VERIFIED
**Last Verified:** February 23, 2026
**Version:** 7.4.0CC

---

## Exact Claim

> "Manners compliance scores below 50% trigger automatic demotion to Quarantine."

## Verdict

VERIFIED — `OpenClawManager.evaluate_action()` Step 6 checks Manners compliance score against `openclaw_auto_demote_manners_threshold` (default 0.50). When score drops below threshold, the instance is automatically demoted to QUARANTINE trust level before the trust permission check at Step 7, meaning the current action is immediately affected.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/openclaw.py` | `evaluate_action()` Step 6 | Manners score checked, auto-demote triggered |
| `core/openclaw.py` | `demote_trust()` | Demotion logic with skip-level support |
| `core/openclaw.py` | `update_manners_score()` | Manners score update mechanism |
| `core/config.py` | `openclaw_auto_demote_manners_threshold` | Configurable threshold (default 0.50) |
| `core/audit.py` | `OPENCLAW_TRUST_DEMOTED` | Audit event for trust demotion |
| `tests/test_openclaw.py` | `TestMannersAutoDemotion` | 3+ tests verifying auto-demotion behavior |

### Auto-Demotion Flow
```
Step 6 of Governance Pipeline:
  1. Read instance.manners_score
  2. Compare against settings.openclaw_auto_demote_manners_threshold (0.50)
  3. If score < threshold:
     a. Call demote_trust(instance_id, "quarantine", reason="Manners auto-demotion")
     b. Log AuditEventType.OPENCLAW_TRUST_DEMOTED
     c. Logger emits "REM: Manners auto-demotion" warning
  4. Continue to Step 7 (trust level check) — now at QUARANTINE
```

### Why Step 6 Before Step 7
The Manners auto-demotion is intentionally placed BEFORE the trust level permission check. This means:
- A CITIZEN agent whose Manners score drops below 0.50 is demoted to QUARANTINE
- The CURRENT action (the one that triggered evaluation) is evaluated at QUARANTINE level
- The agent cannot "sneak in" one last autonomous action before demotion takes effect

### Demotion vs. Promotion Asymmetry
| Direction | Behavior |
|---|---|
| **Promotion** | Sequential only: QUARANTINE → PROBATION → RESIDENT → CITIZEN |
| **Demotion** | Skip-capable: CITIZEN → QUARANTINE (instant, no intermediate steps) |

### Test Coverage
- `test_manners_auto_demotion_triggers` — Score below threshold triggers demotion to quarantine
- `test_manners_auto_demotion_threshold` — Score at exactly threshold does NOT trigger demotion
- `test_manners_above_threshold_no_demotion` — Score above threshold allows normal operation

## Verification Command

```bash
grep -n "manners.*demot\|auto.demot\|manners_score\|Manners" core/openclaw.py | head -10
```

## Expected Result

References to Manners score checking, auto-demotion logic, and threshold comparison in evaluate_action Step 6.

---

*Sheet TB-PROOF-038 | TelsonBase v7.4.0CC | February 23, 2026*
