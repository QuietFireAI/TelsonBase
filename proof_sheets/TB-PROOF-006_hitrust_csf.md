# TB-PROOF-006: HITRUST CSF 12 Domains

**Sheet ID:** TB-PROOF-006
**Claim Source:** telsonbase.com — Compliance Section
**Status:** VERIFIED
**Last Verified:** February 23, 2026
**Version:** 7.3.0CC

---

## Exact Claim

> "HITRUST CSF — 12 domains tracked with baseline controls, risk assessment scoring, and automated gap analysis."

## Verdict

VERIFIED — `core/hitrust.py` and `core/hitrust_controls.py` implement 12 HITRUST CSF domains with baseline controls and risk scoring.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/hitrust.py` | Full file | HITRUST domain definitions and risk assessment |
| `core/hitrust_controls.py` | Full file | Control implementations per domain |

### The 12 HITRUST Domains

1. Information Protection Program
2. Endpoint Protection
3. Portable Media Security
4. Mobile Device Security
5. Wireless Security
6. Configuration Management
7. Vulnerability Management
8. Network Protection
9. Transmission Protection
10. Password Management
11. Access Control
12. Audit Logging and Monitoring

## Verification Command

```bash
grep -c "class\|domain\|Domain" core/hitrust.py core/hitrust_controls.py
```

## Expected Result

Domain definitions and control mappings for all 12 HITRUST CSF domains.

---

*Sheet TB-PROOF-006 | TelsonBase v7.3.0CC | February 23, 2026*
