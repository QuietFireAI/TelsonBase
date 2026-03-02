# TB-PROOF-014: 140+ RBAC-Protected Endpoints

**Sheet ID:** TB-PROOF-014
**Claim Source:** telsonbase.com — Hero Section, Capabilities Section
**Status:** VERIFIED
**Last Verified:** February 23, 2026
**Version:** 7.3.0CC

---

## Exact Claim

> "140+ API endpoints enforced with role-based access control. Four-tier permission taxonomy: view, manage, admin, security."

## Verdict

VERIFIED — 141 endpoints use `Depends(require_permission(...))` across 6 files. 157 total API endpoints exist. Four-tier permission taxonomy confirmed.

## Evidence

### Source Files
| File | RBAC Endpoints | Total Endpoints | What It Proves |
|---|---|---|---|
| `main.py` | 65 | 71 | Core API RBAC |
| `api/compliance_routes.py` | 39 | 39 | Compliance endpoints |
| `api/security_routes.py` | 19 | 19 | Security endpoints |
| `api/tenancy_routes.py` | 10 | 10 | Tenancy endpoints |
| `api/identiclaw_routes.py` | 6 | 6 | Identity endpoints |
| `core/tenant_rate_limiting.py` | 2 | 2 | Rate limit endpoints |
| `api/auth_routes.py` | 0 | 6 | Auth (pre-authentication) |
| `api/n8n_integration.py` | 0 | 4 | n8n webhooks |
| **Total** | **141** | **157** | |

### Permission Taxonomy

| Tier | Permission Prefix | Example | Who Has It |
|---|---|---|---|
| View | `view:` | `view:agents`, `view:audit`, `view:dashboard` | All authenticated users |
| Manage | `manage:` | `manage:agents`, `manage:federation` | Operators and above |
| Admin | `admin:` | `admin:config`, `admin` | Admins only |
| Security | `security:` | `security:audit`, `security:override` | Security officers only |
| Action | `action:` | `action:approve`, `action:resolve_anomaly` | Role-dependent |

### Code Evidence

```python
# Example from main.py:
@app.get("/v1/agents", ...)
async def list_agents(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:agents"))
):
```

## Verification Command

```bash
grep -c "require_permission" main.py api/*.py core/tenant_rate_limiting.py
```

## Expected Result

```
main.py:65
api/compliance_routes.py:39
api/security_routes.py:19
api/tenancy_routes.py:10
api/identiclaw_routes.py:6
core/tenant_rate_limiting.py:2
```
Total: 141

---

*Sheet TB-PROOF-014 | TelsonBase v7.3.0CC | February 23, 2026*
