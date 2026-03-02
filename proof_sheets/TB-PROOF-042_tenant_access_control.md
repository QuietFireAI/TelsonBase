# TB-PROOF-042: Tenant Access Control — allowed_actors Enforcement

**Sheet ID:** TB-PROOF-042
**Claim Source:** TelsonBase architecture — multi-tenancy security model
**Status:** VERIFIED
**Last Verified:** March 1, 2026
**Version:** 9.0.0B

---

## Claim

> "Tenants are access-controlled. Users can only view and query tenants they created or were explicitly granted access to by an administrator. Admins can access all tenants."

---

## Verdict

VERIFIED — `Tenant.allowed_actors` is populated on creation with `auth.actor` (the authenticated creator's identity). All tenant-scoped and matter-scoped API routes call `_require_tenant_access()` before returning data. Unauthorized access returns HTTP 403 with `qms_status: Thank_You_But_No`. Access denial is audit-logged.

---

## Evidence

### Access Control Model

| Actor permission | Tenant access |
|---|---|
| `*` (master API key / super_admin) | All tenants — admin bypass |
| `admin:config` | All tenants — admin bypass |
| `manage:agents`, `view:dashboard` | Only tenants where `auth.actor in tenant.allowed_actors` |

### Data Model — `core/tenancy.py`

`Tenant` dataclass has two access control fields added in v9.0.0B:

```python
# REM: v9.0.0B — Access control: creator and explicitly granted actors only
created_by: str = "system"
allowed_actors: List[str] = field(default_factory=list)
```

`TenantManager.create_tenant()` initializes `allowed_actors = [created_by]` where `created_by = auth.actor` (always set from the authenticated request, never user-supplied).

`TenantManager.grant_tenant_access(tenant_id, actor_id, granted_by)` is an admin-only method that appends to `allowed_actors` and persists to Redis.

### Route Enforcement — `api/tenancy_routes.py`

`_require_tenant_access(tenant_id, auth)` is called in every tenant-scoped and matter-scoped route:

| Route | Access check |
|---|---|
| `GET /v1/tenancy/tenants` | `list_tenants(actor_filter=auth.actor)` for non-admins |
| `GET /v1/tenancy/tenants/{id}` | `_require_tenant_access(tenant_id, auth)` |
| `POST /v1/tenancy/tenants/{id}/deactivate` | `_require_tenant_access(tenant_id, auth)` |
| `POST /v1/tenancy/tenants/{id}/matters` | `_require_tenant_access(tenant_id, auth)` |
| `GET /v1/tenancy/tenants/{id}/matters` | `_require_tenant_access(tenant_id, auth)` |
| `GET /v1/tenancy/matters/{matter_id}` | `_require_tenant_access(matter.tenant_id, auth)` |
| `POST /v1/tenancy/matters/{matter_id}/close` | `_require_tenant_access(matter.tenant_id, auth)` |
| `POST /v1/tenancy/matters/{matter_id}/hold` | `_require_tenant_access(matter.tenant_id, auth)` |
| `POST /v1/tenancy/matters/{matter_id}/release-hold` | `_require_tenant_access(matter.tenant_id, auth)` |

`_require_tenant_access` logic:
1. Returns HTTP 404 if tenant not found
2. Returns tenant if actor has `admin:config` or `*` (admin bypass)
3. Returns HTTP 403 and writes an `AUTH_FAILURE` audit entry if actor is not in `allowed_actors`

### Admin Grant-Access Endpoint

`POST /v1/tenancy/tenants/{tenant_id}/grant-access` (requires `admin:config`) accepts `{ "user_id": "..." }` and calls `tenant_manager.grant_tenant_access()`, adding the user to `allowed_actors`.

### Persistence

`allowed_actors` is included in `Tenant.to_dict()` and stored in Redis via `_save_tenant()`. It is deserialized in `_load_from_redis()` via `tenant_data.get("allowed_actors", [])`. Access control persists across server restarts.

---

## Verification Commands

```bash
# 1. Confirm allowed_actors field in Tenant dataclass
grep -n "allowed_actors\|created_by" core/tenancy.py | head -20

# 2. Confirm _require_tenant_access is called in every tenant-scoped route
grep -n "_require_tenant_access" api/tenancy_routes.py

# 3. Confirm grant_tenant_access method exists
grep -n "def grant_tenant_access" core/tenancy.py

# 4. Run the cross-tenant access rejection E2E test
pytest tests/test_e2e_integration.py::TestTenantIsolation::test_cross_tenant_access_rejected -v
```

## Expected Results

1. `allowed_actors` and `created_by` fields visible in `Tenant` dataclass and `to_dict()`
2. `_require_tenant_access` present in 9+ route locations
3. `grant_tenant_access` method confirmed in `TenantManager`
4. E2E test `test_cross_tenant_access_rejected` passes — HTTP 403 returned for unauthorized actor

---

## Test Coverage

| Test | File | What it verifies |
|---|---|---|
| `TestTenantIsolation::test_cross_tenant_access_rejected` | `tests/test_e2e_integration.py` | User B (viewer) gets HTTP 403 on tenant created by admin |
| `TestTenantIsolation::test_tenant_matter_lists_are_isolated` | `tests/test_e2e_integration.py` | Matter data from Tenant A does not appear in Tenant B's list |

---

*Sheet TB-PROOF-042 | TelsonBase v9.0.0B | March 1, 2026*
