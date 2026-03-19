# TB-PROOF-006: HITRUST CSF 12 Domains

**Sheet ID:** TB-PROOF-006
**Claim Source:** clawcoat.com - Compliance Section
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- TestHITRUSTDepth -- 8 depth tests cover all 12 domains, all 5 statuses, gap analysis, risk scoring
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "HITRUST CSF - 12 domains tracked with baseline controls, risk assessment scoring, and automated gap analysis."

## Verdict

VERIFIED - `core/hitrust.py` and `core/hitrust_controls.py` implement 12 HITRUST CSF domains with baseline controls and risk scoring.

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

## Certification Boundary

> **VERIFIED means:** All 12 HITRUST CSF domains are defined, baseline controls register and produce a posture score, gap analysis runs, risk assessments are recorded. Verified by automated tests.
>
> **VERIFIED does not mean:** A HITRUST-authorized external assessor has completed a CSF assessment via the MyCSF platform. Formal HITRUST certification requires that engagement. The implementation is built and assessor-ready. The formal certification is a funded next step. See `docs/WHATS_NEXT.md` — Certification Boundary section.

## Verification Command

```bash
docker compose exec mcp_server python -m pytest \
  tests/test_compliance_depth.py::TestHITRUSTDepth \
  tests/test_security_battery.py::TestComplianceInfrastructure::test_hitrust_controls_registered_and_assessed \
  tests/test_security_battery.py::TestComplianceInfrastructure::test_hitrust_compliance_posture_calculation \
  -v --tb=short
```

## Expected Result

All 12 domains confirmed, all 5 control statuses present, posture score calculated, risk assessment recorded, gap analysis returns list.

---

*Sheet TB-PROOF-006 | ClawCoat v11.0.2 | March 19, 2026*
