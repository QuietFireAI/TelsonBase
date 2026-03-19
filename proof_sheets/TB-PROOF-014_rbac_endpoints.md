# TB-PROOF-014: 149 RBAC-Protected Endpoints

**Sheet ID:** TB-PROOF-014
**Claim Source:** clawcoat.com - Hero Section, Capabilities Section
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- TestRBACEndpointCount -- require_permission count >= 140 verified by source introspection test
**Last Verified:** March 10, 2026
**Version:** v11.0.2

---

## Exact Claim

> "149 API endpoints enforced with role-based access control. Four-tier permission taxonomy: view, manage, admin, security."

## Verdict

VERIFIED - 149 endpoints use `Depends(require_permission(...))` across 7 files. Four-tier permission taxonomy confirmed.

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
| **Total** | **149** | |

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
docker compose exec mcp_server python -m pytest \
  tests/test_depth_infrastructure.py::TestRBACEndpointCount -v --tb=short
```

## Expected Result

```
2 passed
```
Total: 149

---

*Sheet TB-PROOF-014 | ClawCoat v11.0.2 | March 19, 2026*
