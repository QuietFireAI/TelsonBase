# TB-PROOF-017: Account Lockout After 5 Failed Attempts

**Sheet ID:** TB-PROOF-017
**Claim Source:** clawcoat.com - Capabilities Section
**Status:** VERIFIED
**Last Verified:** March 8, 2026
**Version:** v11.0.1

---

## Exact Claim

> "Account lockout after 5 failed attempts."

## Verdict

VERIFIED - `core/user_management.py` implements account lockout after 5 failed login attempts with a 15-minute lockout duration.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/user_management.py` | Line 40 | `MAX_FAILED_ATTEMPTS = 5` |
| `core/user_management.py` | Line 41 | `LOCKOUT_DURATION_MINUTES = 15` |
| `core/user_management.py` | Lines 145-154 | `_is_account_locked()` check |
| `core/user_management.py` | Lines 156-178 | `_record_failed_attempt()` with lockout trigger |
| `core/user_management.py` | Lines 180-183 | `_clear_failed_attempts()` on success |
| `core/user_management.py` | Lines 283-286 | Lockout enforced before password check |

### Code Evidence

```python
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

def _is_account_locked(self, username: str) -> bool:
    # Check lockout_until dict, auto-clear expired lockouts
    ...

def _record_failed_attempt(self, username: str):
    # Increment counter, trigger lockout at MAX_FAILED_ATTEMPTS
    ...
```

### Lockout Flow

1. User submits credentials
2. `_is_account_locked()` checked **before** password verification
3. If locked: return remaining seconds, deny login
4. If password wrong: `_record_failed_attempt()` increments counter
5. At 5 failures: lockout triggered for 15 minutes
6. On successful login: `_clear_failed_attempts()` resets counter
7. All lockout events logged to audit chain

## Verification Command

```bash
grep -n "MAX_FAILED\|LOCKOUT_DURATION\|_is_account_locked\|_record_failed" core/user_management.py
```

## Expected Result

```
40:MAX_FAILED_ATTEMPTS = 5
41:LOCKOUT_DURATION_MINUTES = 15
```

---

*Sheet TB-PROOF-017 | TelsonBase v11.0.1 | February 23, 2026*
