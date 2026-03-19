# TB-PROOF-045 - Security Battery: Access Control

**Sheet ID:** TB-PROOF-045
**Claim Source:** tests/test_security_battery.py::TestAccessControl
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- TestAccessControl -- 13 behavioral tests
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "177 RBAC-Protected Endpoints - 4-tier permissions, deny overrides allow" - README capability table

This sheet proves the **Access Control** category of the TelsonBase security battery. 13 tests covering role-based permission enforcement, custom grants and denials, user deactivation, session management, and MFA enforcement for privileged roles.

## Verdict

VERIFIED - All 13 tests pass. RBAC enforces hard permission walls between roles: viewers cannot manage agents, operators cannot access admin config, admins have management permissions, and super admins have full access. Custom denials override role-level grants. User deactivation immediately blocks access. MFA is enforced for privileged roles before session creation.

## Test Functions

| # | Function | Proves |
|---|---|---|
| 1 | `test_viewer_cannot_manage_agents` | The VIEWER role is denied agent management permissions |
| 2 | `test_operator_cannot_admin_config` | The OPERATOR role is denied admin configuration access |
| 3 | `test_admin_has_management_permissions` | The ADMIN role holds all management-level permissions |
| 4 | `test_super_admin_has_all_permissions` | The SUPER_ADMIN role holds every defined permission |
| 5 | `test_permission_check_denies_unlisted` | Any permission not explicitly granted is denied by default |
| 6 | `test_role_assignment_audit_logged` | Role assignments are written to the audit chain |
| 7 | `test_custom_permission_grants_work` | Custom per-user grants extend beyond the base role |
| 8 | `test_custom_denial_overrides_role_grant` | A custom denial on a user overrides what the role would allow |
| 9 | `test_user_deactivation_blocks_access` | Deactivating a user immediately prevents authentication |
| 10 | `test_session_creation_requires_valid_user` | Sessions can only be created for active, valid users |
| 11 | `test_session_invalidation_on_user_deactivation` | Existing sessions are invalidated when a user is deactivated |
| 12 | `test_mfa_enforcement_blocks_unenrolled_privileged` | Privileged roles without MFA enrollment cannot create sessions |
| 13 | `test_session_creation_blocked_for_inactive_user` | Inactive user accounts are blocked at session creation |

## Source Files Tested

- `tests/test_security_battery.py::TestAccessControl`
- `core/rbac.py` - Role definitions, permission checks, custom grants/denials
- `core/auth.py` - User authentication, session creation
- `core/session_management.py` - Session lifecycle
- `core/audit.py` - Role assignment audit logging
- `core/mfa.py` - MFA enrollment status enforcement

## Verification Command

```bash
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestAccessControl -v --tb=short
```

## Expected Result

```
13 passed
```

---

*Sheet TB-PROOF-045 | ClawCoat v11.0.2 | March 19, 2026*
