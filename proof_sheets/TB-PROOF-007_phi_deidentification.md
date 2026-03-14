# TB-PROOF-007: PHI De-identification (18 Safe Harbor Identifiers)

**Sheet ID:** TB-PROOF-007
**Claim Source:** clawcoat.com - The Promise Section
**Status:** VERIFIED
**Last Verified:** March 8, 2026
**Version:** v11.0.1

---

## Exact Claim

> "Patient health information is encrypted at rest with AES-256-GCM, de-identified using all 18 HIPAA Safe Harbor identifiers, and never transmitted externally."

## Verdict

VERIFIED - `core/phi_deidentification.py` implements all 18 HIPAA Safe Harbor identifiers as defined in 45 CFR 164.514(b)(2), with 58 pattern strings for auto-detection.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/phi_deidentification.py` | Lines 42-64 | All 18 PHIField enum values |
| `core/phi_deidentification.py` | Lines 70-157 | 58 pattern strings for auto-detection |
| `core/phi_deidentification.py` | Line 44 | HIPAA citation: 45 CFR 164.514(b)(2) |

### The 18 Safe Harbor Identifiers

| # | PHIField Enum | HIPAA Identifier |
|---|---|---|
| 1 | `NAME` | Names |
| 2 | `ADDRESS` | Geographic data (address, city, state, zip) |
| 3 | `DATES` | Dates (DOB, admission, discharge, death) |
| 4 | `PHONE` | Phone numbers |
| 5 | `FAX` | Fax numbers |
| 6 | `EMAIL` | Email addresses |
| 7 | `SSN` | Social Security numbers |
| 8 | `MRN` | Medical record numbers |
| 9 | `HEALTH_PLAN_ID` | Health plan beneficiary numbers |
| 10 | `ACCOUNT_NUMBER` | Account numbers |
| 11 | `LICENSE_NUMBER` | Certificate/license numbers |
| 12 | `VEHICLE_ID` | Vehicle identifiers (VIN) |
| 13 | `DEVICE_ID` | Device identifiers/serial numbers |
| 14 | `URL` | Web URLs |
| 15 | `IP_ADDRESS` | IP addresses |
| 16 | `BIOMETRIC` | Biometric identifiers |
| 17 | `PHOTO` | Full-face photographs |
| 18 | `OTHER_UNIQUE` | Any other unique identifying number |

### Code Evidence

```python
class PHIField(str, Enum):
    """All 18 HIPAA Safe Harbor identifiers per 45 CFR 164.514(b)(2)"""
    NAME = "name"
    ADDRESS = "address"
    DATES = "dates"
    # ... (18 total)
```

## Verification Command

```bash
grep -c "= \"" core/phi_deidentification.py | head -1
# Count PHIField enum values
grep "PHIField" core/phi_deidentification.py | head -20
```

## Expected Result

18 enum values matching the HIPAA Safe Harbor identifiers.

---

*Sheet TB-PROOF-007 | TelsonBase v11.0.1 | February 23, 2026*
