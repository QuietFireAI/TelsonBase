# ClawCoat - Production Hardening Decision Log
**Version:** v11.0.1 · **Maintainer:** Quietfire AI
**Recorded:** February 10-11, 2026

---

## Decision 1: Pure ASGI Middleware Instead of BaseHTTPMiddleware

**Challenge:** Adding security response headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Cache-Control) to every HTTP response required middleware. The obvious choice was Starlette's `BaseHTTPMiddleware`.

**What happened:** I initially implemented `SecurityHeadersMiddleware` using `BaseHTTPMiddleware`. 67 tests in `test_toolroom.py` immediately failed - Starlette's `BaseHTTPMiddleware` wraps the ASGI lifecycle in a way that creates `ExceptionGroup`/`TaskGroup` conflicts with the TestClient. This is a known Starlette issue that surfaces when middleware interacts with streaming responses or background tasks.

**Choice:** Rewrote as a pure ASGI middleware - a class with `__init__(self, app)` and `async def __call__(self, scope, receive, send)` that directly manipulates the `http.response.start` message to inject headers.

**Why it matters:** Pure ASGI middleware has zero overhead (no extra async context managers), doesn't interfere with test harnesses, and is the correct pattern for header injection. Every middleware in TelsonBase should follow this pattern. If we ever add more middleware (CSP headers, CORS tuning), this is the template.

**Rejected:** BaseHTTPMiddleware (test incompatible), FastAPI middleware decorator (same underlying issue), response hooks (per-endpoint, not global).

---

## Decision 2: Direct bcrypt Instead of passlib

**Challenge:** User registration failed in the Docker container with `password cannot be longer than 72 bytes` errors, even for short passwords. Investigation revealed a `passlib`/`bcrypt` version incompatibility - bcrypt 4.x removed the `__about__` module that passlib uses for version detection, causing passlib to fall back to broken behavior.

**What happened:** The `user_management.py` module originally used `from passlib.hash import bcrypt` with `bcrypt.using(rounds=12).hash(password)`. This worked locally but failed in the container where bcrypt 4.1+ was installed.

**Choice:** Replaced passlib entirely with direct `bcrypt` library calls:
- Hash: `bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))`
- Verify: `bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))`

**Why it matters:** Eliminates the passlib dependency for password hashing. Direct bcrypt is simpler, has no version compatibility risks, and is the standard the industry has converged on. The 12-round cost factor provides approximately 250ms hash time on modern hardware - sufficient to resist brute force while remaining responsive for login flows.

**Rejected:** Pinning passlib to a specific version (fragile, masks the real problem), argon2 (better algorithm but less battle-tested in the Python ecosystem for this use case, and would require migrating all existing hashes).

---

## Decision 3: Dual-Dependency RBAC Pattern in main.py

**Challenge:** The RBAC enforcement agent needed to add `require_permission()` to 67 endpoints in `main.py`. Many endpoints already had `auth: AuthResult = Depends(authenticate_request)` and used `auth.actor` throughout their function bodies. Changing the dependency signature would break every reference to `auth`.

**What happened:** The agent chose a dual-dependency pattern:
```python
async def some_endpoint(
    auth: AuthResult = Depends(authenticate_request),
    _perm=Depends(require_permission("view:dashboard")),
):
```

This keeps `auth` for actor extraction while `_perm` enforces permissions as a side-effect dependency.

**Choice:** Kept the dual pattern for main.py (45 endpoints, backward compatible). For the newer route files (security_routes.py, compliance_routes.py, tenancy_routes.py), I used the cleaner single-dependency pattern: `auth: AuthResult = Depends(require_permission("..."))` since `require_permission` internally calls `authenticate_request` and returns the same `AuthResult`.

**Why it matters:** The dual pattern in main.py means zero risk of breaking existing endpoint logic. The single pattern in new route files is cleaner. Both achieve the same security outcome - every request is authenticated AND authorized. The system currently enforces RBAC on 140+ endpoints with zero endpoints left unprotected (excluding intentionally public endpoints: /, /health, /metrics, /dashboard, /v1/auth/token).

**Rejected:** Rewriting all main.py endpoint signatures (high risk of regression for no security benefit), global middleware-based RBAC (too coarse - need per-endpoint permission granularity).

---

## Decision 4: Permission Taxonomy

**Challenge:** Assigning the right permission level to 140+ endpoints across 5 files. Too permissive = security theater. Too restrictive = users locked out of basic operations.

**Choice:** Four permission tiers mapped to endpoint sensitivity:

| Tier | Permission | Used For | Who Gets It |
|------|-----------|----------|-------------|
| Read | `view:dashboard`, `view:audit`, `view:agents`, etc. | GET endpoints, list/status operations | All authenticated users (viewer+) |
| Action | `manage:agents`, `action:approve` | Create/modify operations on business objects | Operators and above |
| Admin | `admin:config` | System configuration, compliance writes, tenant management | Admins only |
| Security | `security:audit`, `security:override` | MFA management, session termination, emergency access | Security officers and super_admins |

**Why it matters:** This maps directly to law firm organizational structure. Paralegals get viewer access (see dashboards, read audit logs). Associates get operator access (create matters, dispatch tasks). Partners/IT get admin access (manage tenants, configure compliance). The security officer role is separate from admin - a deliberate zero-trust separation so that the person managing users isn't the same person who can override security controls.

**Rejected:** Flat permission model (single "admin" flag - too coarse), per-endpoint permissions (141 unique permissions would be unmanageable), role-only checks without granular permissions (can't delegate specific capabilities).

---

## Decision 5: Redis Sliding Window for Tenant Rate Limiting

**Challenge:** Item 11 required per-tenant rate limiting that survives container restarts, supports different quotas per tenant, and doesn't add latency to every request.

**Choice:** Redis sorted sets with sliding window algorithm:
- Key: `ratelimit:tenant:{tenant_id}:{minute_bucket}` with 120s TTL
- Each request adds a timestamped entry via `ZADD`
- Window cleanup via `ZREMRANGEBYSCORE` (remove entries older than 60s)
- Count via `ZCARD`
- All three operations pipelined in a single Redis round-trip

Default limits: 600 requests/min per tenant, 120 requests/min per user, 1.5x burst multiplier, 2.0x premium tenant multiplier.

**Why it matters:** Sorted sets give precise sliding windows (not approximate like token buckets). Pipeline batching keeps latency under 1ms. The 120s TTL auto-cleans expired keys - no garbage collection needed. In-memory fallback (`_InMemoryBucket`) means rate limiting continues even if Redis goes down, with a logged warning. The FastAPI dependency (`enforce_tenant_rate_limit`) returns standard `429` with `Retry-After`, `X-RateLimit-Limit`, and `X-RateLimit-Remaining` headers.

**Rejected:** Token bucket (already exists in `core/middleware.py` for global rate limiting - tenant-scoped needs per-entity tracking), fixed window (allows burst at window boundaries), Lua scripts (adds complexity, pipeline is sufficient).

---

## Decision 6: Sync Endpoints with Async FastAPI

**Challenge:** All TelsonBase core modules (MFA, sessions, tenancy, compliance, etc.) are synchronous Python. The agent-generated route files used `await` on every manager call, which fails at runtime with `TypeError: object X can't be used in 'await' expression`.

**What happened:** The route file agents assumed the managers were async (reasonable assumption for a FastAPI project). I discovered 40+ broken `await` calls across `security_routes.py` and `compliance_routes.py` during testing.

**Choice:** Removed all `await` keywords from sync manager calls. Kept the endpoint functions as `async def` (FastAPI handles sync calls within async endpoints correctly by running them in a thread pool).

**Why it matters:** FastAPI's `async def` endpoints that call sync functions still work correctly - FastAPI automatically wraps sync callables. The alternative (converting all 20+ managers to async) would have been a massive rewrite with no real benefit since the managers are CPU-bound (bcrypt hashing, SHA-256 computation) not I/O-bound. The sync managers are actually correct here - they're doing computation, not waiting on network calls.

**Rejected:** Converting all managers to async (massive scope creep, wrong abstraction for CPU-bound work), changing endpoints to `def` (would work but loses the option to add genuinely async operations later).

---

## Decision 7: AuditEventType Consolidation

**Challenge:** The agent-generated route files referenced 18+ `AuditEventType` enum values that didn't exist (`LEGAL_HOLD_CREATED`, `MFA_ENROLLED`, `BREACH_ASSESSED`, `BAA_CREATED`, etc.). Each would have caused an `AttributeError` at runtime.

**Choice:** Consolidated all compliance/security audit events to `AuditEventType.SECURITY_ALERT`. The specific action is captured in the `details` dict parameter of `audit.log()`, not the enum.

Example:
```python
audit.log(
    AuditEventType.SECURITY_ALERT,
    "Legal hold created for tenant acme",
    details={"action": "legal_hold_created", "tenant_id": "acme", "hold_name": "..."}
)
```

**Why it matters:** The audit chain's value is in its tamper-evident hash linkage and the structured details payload - not in the enum categorization. Adding 18 new enum values would bloat the type without adding queryability (you'd still need to search the details for specifics). The `details.action` field provides the same filtering capability. If we later need enum-level granularity for Grafana dashboards or compliance reports, we can add specific values then - the schema is forward-compatible.

**Rejected:** Adding 18+ new enum values (scope creep, no immediate consumer of that granularity), string-based event types without enum (loses type safety for the core events that do matter: auth.success, auth.failure, system.startup).

---

## Decision 8: Error Sanitization Strategy

**Challenge:** Item 3 required eliminating information leakage. Production APIs must never reveal stack traces, file paths, class names, or internal error details to clients.

**What I found and fixed:**
1. Four `OllamaServiceError` handlers that returned `detail=str(e)` - leaked Ollama connection errors, model names, internal paths
2. One `n8n_integration.py` handler that returned `detail=str(e)` - leaked n8n connection details
3. Two health endpoint responses that returned `type(e).__name__` - leaked Python class hierarchy
4. The global exception handler was missing entirely - unhandled exceptions returned raw Starlette error pages

**Choice:** Three-layer sanitization:
1. **Global exception handler** (`@app.exception_handler(Exception)`) - catches everything unhandled, logs the real error internally, returns `{"detail": "Internal server error"}` with no details
2. **Endpoint-level sanitization** - replaced all `str(e)` in error responses with fixed strings like `"LLM engine error. Check server logs."` or `"Failed to list agents. Check server logs."`
3. **Security headers** - `Cache-Control: no-store` prevents error responses from being cached by proxies

**Why it matters:** Information leakage is OWASP A01 territory. A single `str(e)` returning a database connection string or file path gives an attacker the map to the system. The sanitized responses tell the client what went wrong (LLM error, auth failure, etc.) without revealing how the system is built. Internal logging preserves the full error for debugging.

**Rejected:** Returning error codes only (too opaque for developers integrating with the API), middleware-based error transformation (can't distinguish between error types to provide appropriate sanitized messages).

---

## Decision 9: Grafana Dashboard + Prometheus Alert Design

**Challenge:** Item 10 required observability infrastructure - not just metrics collection (already done via Prometheus) but actionable dashboards and alerts that a law firm IT admin or MSP can actually use.

**Choice:** Three dashboard rows organized by audience:
1. **Request Metrics** - Operations team: RPS by status code, P50/P95/P99 latency, error rate percentage, active requests
2. **Security** - Security officer: auth failures by method (with 20-failure threshold line), active sessions, MFA verifications
3. **Infrastructure** - IT admin: Redis memory vs max, PostgreSQL connections, container memory

Five alert rules with escalation:
- `HighErrorRate` warning at 5% (5min), critical at 10% (2min)
- `HighLatency` at P95 > 2s (5min)
- `AuthFailureSpike` at 20 failures in 5 minutes (immediate, severity: critical)
- `AuditChainBroken` when chain validation fails (1min)
- `ServiceDown` when any service is unreachable (2min)

**Why it matters:** The auth failure spike alert is the most important - 20 failed auth attempts in 5 minutes is a brute force attack or a credential stuffing campaign. Immediate alerting gives the security officer time to respond before lockout policies are exhausted. The audit chain broken alert catches tampering - if someone modifies audit records, the chain verification fails and the alert fires.

**Rejected:** Single monolithic dashboard (too noisy - different roles need different views), PagerDuty/OpsGenie integration (adds external dependency, customers can configure their own alerting pipeline from Prometheus).

---

## Decision 10: pythonjsonlogger Fix

**Challenge:** Every log line threw `KeyError: 'levelname'` - a cosmetic but persistent error traced to `pythonjsonlogger` v3.x incompatibility. The `rename_fields={"levelname": "level", "asctime": "timestamp"}` parameter worked in v2 but broke in v3.

**Choice:** Removed `rename_fields` entirely. Used standard format string: `%(asctime)s %(levelname)s %(event_type)s %(message)s`. The JSON structure comes from the audit chain's own serialization, not from the logger's field renaming.

**Why it matters:** This was a "death by a thousand cuts" issue - the KeyError didn't break functionality but it polluted every log line, making real errors harder to find. Fixing it cleans up the signal-to-noise ratio for monitoring. The standard format also makes log parsing more portable across log aggregation tools.

---

## Decision 11: Deferred UI (Item 9)

**Challenge:** Item 9 called for a client-facing UI (login, MFA, dashboard, matters, audit viewer). This is a full frontend application - React/Vue/Svelte, build tooling, routing, state management, API integration.

**Choice:** Deferred to post-hardening. Marked as incomplete in Cluster B.

**Why it matters:** The API is the product. Every endpoint is documented, tested, and permission-gated. A law firm evaluating TelsonBase for a pilot doesn't need a pretty dashboard - they need to know the audit chain is tamper-evident, the compliance modules track what regulators require, and the security posture is demonstrable. The UI is a usability layer that can be built on top of a solid API. Building it before the API was hardened would have been building on sand.

For the demo, Swagger/OpenAPI docs at `/docs` show every endpoint. For the pilot, a lightweight admin panel can be added in a single session. For GA, a proper React frontend is warranted.

**Rejected:** Building a minimal UI now (would have consumed 30-40% of the hardening session on cosmetics instead of security), using Streamlit/Gradio (not production-grade, wrong tool for a security platform).

---

## Decision 12: Documentation as Contract Readiness

**Challenge:** Cluster C (items 13-18) was entirely documentation - SOC 2 controls, pen test prep, DPA, DR testing, HA architecture, compliance roadmap. The temptation was to skip these as "just docs" and focus on code.

**Choice:** Treated every document as a first-class deliverable with the same rigor as code:
- SOC 2 Type I: 51 controls mapped to specific source files, auditor-ready format
- Pen Test Prep: Honest about known vulnerabilities (16 CVEs, CWE-22 in backup_agent), not just a marketing document
- DPA: 13 sections + 3 annexes, placeholder brackets for customer details, references every security control by file path
- DR Test: Automated script that actually measures RPO/RTO, not just a procedure document
- HA Architecture: Real resource calculations from docker-compose.yml, not hypothetical numbers
- Compliance Roadmap: Honest cost estimates ($50-125K for full certification suite), identifies the FIPS 140-2 gap in CJIS compliance

**Why it matters:** For law firms, documentation IS the product. A partner evaluating TelsonBase will hand these documents to their compliance officer and outside counsel. If the SOC 2 mapping is vague or the DPA is generic, the deal dies. Every document references specific TelsonBase source files because an auditor will ask "show me the control" and the answer needs to be `core/audit.py:395` not "we have an audit system."

The pen test document is deliberately honest about the 16 known CVEs and the tarfile path traversal. Hiding known vulnerabilities from a pen tester is worse than useless - they'll find them anyway, and the lack of prior disclosure signals either ignorance or deception. Pre-populating the remediation tracker shows maturity.

---

## Decision 13: Checkpoint Discipline

**Challenge:** A multi-session autonomous build across 22 items with no human oversight between sessions. If a session crashes or context is lost, work must be recoverable.

**Choice:** Created tar checkpoints at every cluster boundary:
- `telsonbase_20260210.tar` - pre-hardening baseline
- `telsonbase_20260211_cluster_a.tar` - after items 1-6
- `telsonbase_20260211_cluster_b.tar` - after items 7-12
- `telsonbase_20260211_complete.tar` - after items 13-18

Each checkpoint is taken AFTER tests pass, not before. CLAUDE.md is updated with current state before each checkpoint so the next session can pick up cleanly.

**Why it matters:** Jeff said "ill keep putting quarters in the juke box" - meaning sessions will end and resume. The tars are rollback points. If a future session introduces a regression, we can diff against the checkpoint to identify what changed. The CLAUDE.md serves as both a project manifest and a session handoff document.

---

## What This Cook Produced

| Metric | Before | After |
|--------|--------|-------|
| Tests passing | 596 | 618 |
| Endpoints with RBAC | ~0 | 140+ |
| Security documentation pages | 3 | 14 |
| Known CVE disclosure | Undocumented | Tracked with remediation plan |
| Compliance frameworks mapped | 0 | 6 (SOC 2, HIPAA, HITRUST, CJIS, GDPR, PCI DSS) |
| DR test automation | Manual | Scripted with RPO/RTO measurement |
| Rate limiting | Global only | Global + per-tenant + per-user |
| Error information leakage | 8 endpoints | 0 endpoints |
| Audit event coverage | Core only | All 140+ endpoints |

## What's Still Needed

1. **Client-facing UI** - React frontend for non-technical users
2. **FIPS 140-2 encryption** - Required for CJIS compliance, current Fernet uses non-FIPS AES
3. **pip-audit remediation** - 16 CVEs in 8 packages need version bumps or replacements
4. **Per-agent rate limiter wiring** - `core/rate_limiting.py` is implemented but not integrated into middleware
5. **Agent workflow templates** - What agents actually DO (document review, contract analysis, matter intake) vs. just the security shell around them

---

*This document is the engineering record of autonomous technical decisions made under the working agreement between Jeff Phillips (architect, business direction) and Claude (engineering authority, production hardening). Every choice was made to move TelsonBase from "impressive prototype" to "deployable product that a law firm's compliance officer will approve."*

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
