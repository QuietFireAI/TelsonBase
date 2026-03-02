# TB-PROOF-018: Built on Anthropic's Agent Safety Framework (Manners)

**Sheet ID:** TB-PROOF-018
**Claim Source:** telsonbase.com — AI Safety Section
**Status:** VERIFIED
**Last Verified:** February 23, 2026
**Version:** 7.3.0CC

---

## Exact Claim

> "TelsonBase adopts Anthropic's published guidelines for developing safe and trustworthy AI agents as binding operational principles. Every agent is scored against five measurable standards at runtime. Compliance is not optional — it is enforced, audited, and reported."

## Verdict

VERIFIED — `MANNERS.md` defines the 5 principles, `core/manners.py` implements the runtime scoring engine with 15 violation types and automatic quarantine, `agents/registry.yaml` maps every agent to all 5 principles.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `MANNERS.md` | Full file | 5 principles defined with Anthropic attribution |
| `core/manners.py` | Lines 57-63 | `MannersPrinciple` enum: 5 principles |
| `core/manners.py` | Lines 66-72 | Compliance status thresholds (EXEMPLARY to SUSPENDED) |
| `core/manners.py` | Lines 75-116 | 15 violation types mapped to principles |
| `core/manners.py` | Lines 119-135 | Severity weights (0.05 to 0.35) |
| `core/manners.py` | Lines 329-363 | Score computation with time decay |
| `core/manners.py` | Lines 138-139 | Auto-suspension: 3+ violations in 24 hours |
| `agents/registry.yaml` | All agent entries | manners_compliance mappings for every agent |

### The 5 Manners Principles

| Principle | Enum | Score Range | Enforcement |
|---|---|---|---|
| MANNERS-1: Human Control | `manners_1_human_control` | 0.0-1.0 | Approval gates on destructive actions |
| MANNERS-2: Transparency | `manners_2_transparency` | 0.0-1.0 | All actions logged to audit chain |
| MANNERS-3: Value Alignment | `manners_3_value_alignment` | 0.0-1.0 | Agents confined to declared role |
| MANNERS-4: Privacy | `manners_4_privacy` | 0.0-1.0 | Tenant isolation, no external data transmission |
| MANNERS-5: Security | `manners_5_security` | 0.0-1.0 | Input validation, rate limiting |

### Compliance Thresholds

| Status | Score Range | Consequence |
|---|---|---|
| EXEMPLARY | 0.90-1.00 | Full operational freedom |
| COMPLIANT | 0.75-0.89 | Normal operations |
| DEGRADED | 0.50-0.74 | Increased monitoring |
| NON_COMPLIANT | 0.25-0.49 | Restricted actions |
| SUSPENDED | 0.00-0.24 | **Cannot execute any actions** |

### Code Evidence

```python
class MannersPrinciple(str, Enum):
    HUMAN_CONTROL = "manners_1_human_control"
    TRANSPARENCY = "manners_2_transparency"
    VALUE_ALIGNMENT = "manners_3_value_alignment"
    PRIVACY = "manners_4_privacy"
    SECURITY = "manners_5_security"
```

Auto-suspension trigger:
```python
# 3+ violations in 24 hours → automatic quarantine
```

### Anthropic Attribution

From `MANNERS.md`: Based on Anthropic's "Framework for Developing Safe and Trustworthy Agents" (2025).

## Verification Command

```bash
docker compose exec mcp_server python -m pytest tests/ -v -k "manners" --tb=short -q
```

## Expected Result

All Manners compliance tests pass.

---

*Sheet TB-PROOF-018 | TelsonBase v7.3.0CC | February 23, 2026*
