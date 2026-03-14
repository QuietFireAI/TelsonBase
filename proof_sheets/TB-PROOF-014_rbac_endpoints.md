# TB-PROOF-014: 150 RBAC-Protected Endpoints

**Sheet ID:** TB-PROOF-014
**Claim Source:** clawcoat.com - Hero Section, Capabilities Section
**Status:** VERIFIED
**Last Verified:** March 10, 2026
**Version:** v11.0.1

---

## Exact Claim

> "150 API endpoints enforced with role-based access control. Four-tier permission taxonomy: view, manage, admin, security."

## Verdict

VERIFIED - 150 endpoints use `Depends(require_permission(...))` across 7 files. Four-tier permission taxonomy confirmed.

## Evidence

### Source Files
| File | RBAC Endpoints | What It Proves |
|---|---|---|
| `main.py` | 66 | Core API RBAC |
| `api/compliance_routes.py` | 40 | Compliance endpoints |
| `api/security_routes.py` | 20 | Security endpoints |
| `api/tenancy_routes.py` | 12 | Tenancy endpoints |
| `api/openclaw_routes.py` | 2 | OpenClaw governance endpoints |
| `api/identiclaw_routes.py` | 7 | Identity endpoints |
| `core/tenant_rate_limiting.py` | 3 | Rate limit endpoints |
| `api/auth_routes.py` | 0 | Auth (pre-authentication) |
| `api/mcp_gateway.py` | 0 | MCP gateway (mounted sub-app) |
| **Total** | **150** | |

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
main.py:66
api/compliance_routes.py:40
api/security_routes.py:20
api/tenancy_routes.py:12
api/openclaw_routes.py:2
api/identiclaw_routes.py:7
core/tenant_rate_limiting.py:3
```
Total: 150

---

*Sheet TB-PROOF-014 | TelsonBase v11.0.1 | March 10, 2026*
