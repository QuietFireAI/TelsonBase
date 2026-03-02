# TB-PROOF-021: Multi-Tenant Data Isolation

**Sheet ID:** TB-PROOF-021
**Claim Source:** telsonbase.com — Capabilities Section
**Status:** VERIFIED
**Last Verified:** March 1, 2026
**Version:** 9.0.0B

---

## Exact Claim

> "Every client's data is namespaced at the Redis key level. Litigation holds block deletion across tenant boundaries. Four-tier data classification with minimum necessary enforcement per HIPAA."

## Verdict

VERIFIED — Multi-tenancy with Redis key namespacing, per-tenant rate limiting, litigation hold support, 4-tier data classification, and actor-scoped access control (v9.0.0B).

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/tenancy.py` | `Tenant` dataclass, `TenantManager` | Tenant lifecycle, `allowed_actors` field, `grant_tenant_access()` |
| `api/tenancy_routes.py` | `_require_tenant_access()`, all tenant/matter routes | Route-layer access enforcement, HTTP 403 on unauthorized cross-tenant access |
| `core/tenant_rate_limiting.py` | Full file | Redis sliding-window per-tenant rate limiting |
| `core/legal_hold.py` | Full file | Litigation hold implementation |
| `core/data_classification.py` | Full file | 4-tier data classification |
| `core/minimum_necessary.py` | Full file | HIPAA minimum necessary standard |

### Data Classification Tiers

| Tier | Classification | Examples |
|---|---|---|
| 1 | Public | Marketing materials, public API docs |
| 2 | Internal | Agent configurations, system logs |
| 3 | Confidential | Client data, transaction records |
| 4 | Restricted | PHI, PII, encryption keys |

### Tenant Isolation Features

- **Redis key namespacing**: All keys prefixed with tenant ID via `tenant_scoped_key()` in `core/tenancy.py`
- **Per-tenant rate limiting**: Redis sliding window, configurable per tier
- **Litigation holds**: Block data deletion when legal hold is active
- **Actor-scoped access control (v9.0.0B)**: Every tenant stores `created_by` and `allowed_actors`. All tenant and matter routes call `_require_tenant_access()` which returns HTTP 403 if `auth.actor` is not in `allowed_actors`. Admins (`admin:config` or `*`) bypass for management operations. See TB-PROOF-042 for full detail.

> **Correction (v9.0.0B, March 1, 2026):** Prior version of this sheet claimed "Cross-tenant query prevention: Data queries scoped to authenticated tenant." That claim was inaccurate — the routes lacked user-to-tenant binding checks. This has been corrected: `allowed_actors` enforcement is now implemented at the route layer and verified by E2E test `test_cross_tenant_access_rejected`.

## Verification Command

```bash
# Confirm _require_tenant_access is called in all tenant-scoped routes
grep -n "_require_tenant_access" api/tenancy_routes.py

# Confirm allowed_actors field exists on Tenant dataclass
grep -n "allowed_actors" core/tenancy.py

# Run the cross-tenant access E2E test
pytest tests/test_e2e_integration.py::TestTenantIsolation::test_cross_tenant_access_rejected -v
```

## Expected Result

- `_require_tenant_access` appears in all tenant-scoped GET/POST routes
- `allowed_actors` field confirmed in `Tenant` dataclass and `to_dict()`
- E2E test passes: HTTP 403 returned for unauthorized cross-tenant access

---

*Sheet TB-PROOF-021 | TelsonBase v9.0.0B | March 1, 2026*
