# TB-PROOF-036: Trust Level Permission Matrix

**Sheet ID:** TB-PROOF-036
**Claim Source:** clawcoat.com - OpenClaw Integration
**Status:** VERIFIED
**Last Verified:** March 8, 2026
**Version:** v11.0.1

---

## Exact Claim

> "Earned trust - degraded permissions that earn their way up, not blanket autonomy. QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT."

## Verdict

VERIFIED - `core/openclaw.py` implements a **5-level trust model** with enforced sequential promotion path, skip-capable demotion, and per-level permission matrices covering 6 action categories. AGENT tier added February 25, 2026 - anomalies advisory only, pre-authorized action profile.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/openclaw.py` | `TrustLevel` enum (lines 60-65) | 5 trust levels defined |
| `core/openclaw.py` | `VALID_PROMOTIONS` (lines 68-74) | Sequential promotion: Q→P→R→C→A |
| `core/openclaw.py` | `VALID_DEMOTIONS` (lines 76-81) | Skip-capable demotion including from AGENT |
| `core/openclaw.py` | `TRUST_PERMISSION_MATRIX` (lines 153-198) | Per-level autonomous/gated/blocked |
| `core/openclaw.py` | `ActionCategory` enum | 6 action categories |
| `tests/test_openclaw.py` | `TestTrustLevels` | Full trust level test suite |
| `tests/test_openclaw.py` | `TestPermissionMatrix` | Matrix consistency tests |

### Trust Level Permission Matrix
| Trust Level | Autonomous | Approval Required | Blocked |
|---|---|---|---|
| **QUARANTINE** | None | Read-only | Write, Delete, External, Financial, System Config |
| **PROBATION** | Read-only | Write, External | Delete, Financial, System Config |
| **RESIDENT** | Read, Write | Delete, External, Financial, System Config | None |
| **CITIZEN** | All 6 categories | Anomaly-flagged only | None |
| **AGENT** | All 6 categories | None (anomalies advisory, not gated) | None |

### 6 Action Categories
| Category | Example Tools |
|---|---|
| `read_internal` | file_read, database_query, search, email_read |
| `write_internal` | file_write, database_insert, calendar_create |
| `delete` | file_delete, database_delete |
| `external_request` | http_request, email_send, webhook_send |
| `financial` | payment_send, invoice_create, transaction_execute |
| `system_config` | config_update, service_restart |

### Promotion Path Enforcement
```
QUARANTINE → [PROBATION]         (only one step up)
PROBATION  → [RESIDENT]          (only one step up)
RESIDENT   → [CITIZEN]           (only one step up)
CITIZEN    → [AGENT]             (only one step up)
AGENT      → []                  (top tier, cannot promote further)
```

### Demotion Path (instant consequences)
```
AGENT      → [CITIZEN, RESIDENT, PROBATION, QUARANTINE]  (can skip levels)
CITIZEN    → [RESIDENT, PROBATION, QUARANTINE]           (can skip levels)
RESIDENT   → [PROBATION, QUARANTINE]                     (can skip levels)
PROBATION  → [QUARANTINE]
QUARANTINE → []                                          (already at bottom)
```

### Manners Auto-Demotion
When Manners compliance score drops below threshold (default 0.50), the instance is automatically demoted to QUARANTINE regardless of current trust level - including AGENT.

### AGENT Tier - Anomaly Behavior
At AGENT tier, anomaly detection still runs (Step 8 of governance pipeline). The difference: anomalies log loudly but do **not** gate execution. Code reference: `core/openclaw.py` line 655-660 - `if anomaly_flagged and trust_level == TrustLevel.AGENT: audit.log(... "Advisory anomaly (AGENT tier - not gated)")`.

## Verification Command

```bash
grep -n "TRUST_PERMISSION_MATRIX\|VALID_PROMOTIONS\|VALID_DEMOTIONS\|TrustLevel.AGENT" core/openclaw.py
```

## Expected Result

5 trust levels in enum. VALID_PROMOTIONS includes `TrustLevel.CITIZEN: [TrustLevel.AGENT]` and `TrustLevel.AGENT: []`. TRUST_PERMISSION_MATRIX includes AGENT entry with all 6 categories autonomous.

## Toolroom Access by Trust Tier

For how trust levels govern tool checkout eligibility, `min_trust_level` designation, and the `requires_api_access` gate, see [`docs/TOOLROOM_TRUST_MATRIX.md`](../docs/System%20Documents/TOOLROOM_TRUST_MATRIX.md).

---

*Sheet TB-PROOF-036 | TelsonBase v11.0.1 | Updated March 8, 2026*
