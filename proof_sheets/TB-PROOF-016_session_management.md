# TB-PROOF-016: HIPAA-Compliant Session Management

**Sheet ID:** TB-PROOF-016
**Claim Source:** telsonbase.com — Capabilities Section
**Status:** VERIFIED
**Last Verified:** February 23, 2026
**Version:** 7.3.0CC

---

## Exact Claim

> "HIPAA-compliant automatic logoff (15-minute idle, 10-minute for privileged roles)."

## Verdict

VERIFIED — `core/session_management.py` implements role-based session timeouts per 45 CFR 164.312(a)(2)(iii).

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/session_management.py` | Line 9 | HIPAA citation: 45 CFR 164.312(a)(2)(iii) |
| `core/session_management.py` | Line 37 | Privileged roles: `{"admin", "security_officer", "super_admin"}` |
| `core/session_management.py` | Line 38 | `PRIVILEGED_IDLE_MINUTES = 10` |
| `core/session_management.py` | Line 47 | `max_idle_minutes: int = 15` (default) |
| `core/session_management.py` | Line 48 | `max_session_hours: int = 8` (absolute max) |
| `core/session_management.py` | Line 49 | `warning_before_logoff_seconds: int = 60` |
| `core/session_management.py` | Lines 161-165 | Role-based timeout selection |

### Session Timeout Configuration

| Setting | Value | HIPAA Requirement |
|---|---|---|
| Standard idle timeout | 15 minutes | 45 CFR 164.312(a)(2)(iii) |
| Privileged idle timeout | 10 minutes | Enhanced for admin/security roles |
| Maximum session duration | 8 hours | Absolute session limit |
| Warning before logoff | 60 seconds | User notification |
| Privileged roles | admin, security_officer, super_admin | Shorter timeout required |

### Code Evidence

```python
PRIVILEGED_IDLE_MINUTES = 10
PRIVILEGED_ROLES = {"admin", "security_officer", "super_admin"}

max_idle_minutes: int = 15
max_session_hours: int = 8

def _get_idle_timeout(self, role):
    if role in PRIVILEGED_ROLES:
        return PRIVILEGED_IDLE_MINUTES
    return self.max_idle_minutes
```

## Verification Command

```bash
grep -n "idle\|PRIVILEGED\|timeout\|164.312" core/session_management.py
```

## Expected Result

15-minute default, 10-minute privileged, with HIPAA CFR citation.

---

*Sheet TB-PROOF-016 | TelsonBase v7.3.0CC | February 23, 2026*
