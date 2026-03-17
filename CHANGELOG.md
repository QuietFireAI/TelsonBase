# CHANGELOG - TelsonBase

All notable changes to this project are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [11.0.2] - 2026-03-17 (Coverage depth — 650+ new tests, CI gate 40%→58%)

**Status:** 1,295+ passed, 0 failed. CI verified 58.48% coverage on run #260.
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Added
- 470 coverage-boost tests (compliance, semantic matching, auth helpers, rotation dataclasses)
- 180+ depth tests: security routes (MFA/sessions/email/captcha/emergency), tenancy routes, auth routes, delegation manager, MCP gateway tools
- AGENT_AUTONOMY_SLA.md — formal 5-tier open-standard SLA spec, cites arXiv:2511.02885
- REUSE compliance: LICENSES/Apache-2.0.txt, .reuse/DEP5, SPDX headers on 250 Python files

### Changed
- CI coverage gate: 40% → 58% (calibrated to verified 58.48%)
- `.dockerignore`: docs/ restored to container for compliance file-existence tests
- README: certification boundary disclosure, RBAC role count corrected (4-tier → 5-role)

### Fixed
- Proof sheets: HIPAA/HITRUST/SOC2 rating corrections
- Stale numbers corrected in README and proof index

---

## [11.0.1] - 2026-03-08 (Public launch - full documentation sweep and pre-drop polish)

**Status:** 746 passed, 1 skipped, 0 failed. Public GitHub drop. DO server synced.
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Added
- `GOVERNANCE.md` - Project governance, decision process, release procedure, contributor path
- `SUPPORT.md` - Support channels, response times, bug report guidance (GitHub surfaces this automatically)
- `NOTICE` - Apache 2.0 required attribution file, third-party component summary
- `.github/CODEOWNERS` - Auto-review assignment for security-sensitive paths and legal files
- `docs/DASHBOARD_agent_registration.md` - Full video-ready agent registration walkthrough: connect, register, promote, verify governance loop, audit trail
- `docs/Operation Documents/INSTALLATION_GUIDE_WINDOWS.md` - New file: fresh Windows install guide, Docker Desktop through first agent

### Changed
- **Terminology:** "governance layer" replaced with "guiding layer" in user-facing and positioning contexts. "governance layer" preserved in compliance-specific and regulated-industry contexts (hybrid approach)
- `docs/Operation Documents/INSTALLATION_GUIDE_WINDOWS.md` - OPENCLAW_ENABLED step changed from optional to required with copy-paste sed/PowerShell commands; service count corrected (12 -> 11 for standard start, MailHog is dev-profile only); port conflict fix now a copy-paste command instead of manual file edit
- `docs/DASHBOARD_agent_registration.md` - All curl commands use $API_KEY variable pattern; Git Bash context explicit; step-by-step video walkthrough with expected responses documented
- `agents/doc_prep_agent.py` - Hardcoded version string `v9.0.0B` replaced with `APP_VERSION` import from `version.py`
- `proof_sheets/TB-PROOF-001` through `TB-PROOF-042` - Bulk version update to v11.0.1, Last Verified date to March 8, 2026
- `docs/System Documents/PROJECT_OVERVIEW.md` - v10.0.0Bminus -> v11.0.1, Architect line removed, header normalized
- `docs/System Documents/ENCRYPTION_AT_REST.md` - REM block replaced with standard version header
- `docs/System Documents/ENV_CONFIGURATION.md` - AI Model Collaborators line removed
- `docs/System Documents/HA_ARCHITECTURE.md` - Stale "Applies to: TelsonBase v6.3.0CC" corrected to v11.0.1
- `docs/Operation Documents/OPENCLAW_OPERATIONS.md` - Missing citizen->agent promotion path added
- `docs/Operation Documents/SHARED_RESPONSIBILITY.md` - REM block replaced with version header
- `docs/Testing Documents/HARDENING_CC.md` - REM block replaced with version header and recorded date
- `docs/Testing Documents/DISASTER_RECOVERY_TEST.md` - Version and date updated, Architect line removed
- `docs/QMS Documents/QMS_SPECIFICATION.md` - Architect -> Maintainer; footer added
- `docs/Compliance Documents/MANNERS_COMPLIANCE.md` - Version header and footer added (had neither)
- `docs/Compliance Documents/PENTEST_PREPARATION.md` - REM block replaced with clean version header
- Multiple compliance, backup, and operation docs - Version strings, dates, and footer standardization across the full doc tree
- `PROJECT_STRUCTURE.md` - Removed five deleted file references; Testing Documents section updated to reflect actual files

### Fixed
- `agents/doc_prep_agent.py` - Generated document footers were showing `TelsonBase v9.0.0B`; now tracks `APP_VERSION`
- `docs/Compliance Documents/HEALTHCARE_COMPLIANCE.md` and `LEGAL_COMPLIANCE.md` - QMS version corrected from v2.2.0 to v2.1.6
- `docs/Operation Documents/OPENCLAW_OPERATIONS.md` - citizen->agent promotion path was missing from the documented promotion targets list

---

## [10.0.0Bminus] - 2026-03-03 (Full documentation audit - 34 stale files corrected)

**Status:** Documentation accuracy pass complete. All public-facing docs audited and corrected.
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Changed
- Full audit of all docs, licenses, HuggingFace space, USER_GUIDE, README, and proof sheets
- 34 stale documents corrected: version headers, test counts, trust tier counts, n8n references removed, tenant API paths corrected
- `licenses/N8N-Sustainable-Use.txt` removed - n8n removed from stack Feb 2026
- `licenses/THIRD_PARTY_NOTICES.md` updated: Pydantic 2.9.2, httpx 0.28.1, starlette >=0.47.2, mcp >=1.2.0, n8n row removed
- `huggingface_space/README.md` and `app.py` corrected: five trust tiers (not three), AGENT as apex
- `USER_GUIDE.md`: alembic step added, CORS/rate-limit defaults corrected, tenant API paths corrected, trust tier descriptions corrected

---

## [9.6.0B] - 2026-03-03 (First green CI - verified build milestone)

**Status:** 720 passed, 1 skipped, 0 failed - CI green for the first time in repo history
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Milestone
- **CI green** - TelsonBase CI passes all 5 stages on every push for the first time
- All 26 prior CI runs were red; fixed root causes rather than symptoms

### Fixed
- `core/openclaw.py` - multi-worker Redis eviction: `evaluate_action()` local_fallback rescue, `_persist_instance()` always writes local cache, mutation methods no longer use destructive pop
- `toolroom/foreman.py` + `toolroom/executor.py` - `TOOLROOM_PATH` hardcoded to `/app/toolroom/tools`; now env-var configurable (same pattern as `CAGE_PATH`)
- `.github/workflows/ci.yml` - Docker Build missing `.env` file; added `cp .env.example .env`; added `TOOLROOM_PATH=/tmp/telsonbase_toolroom` to all test env sections

### Security
- `gateway/requirements.txt` - upgraded fastapi 0.109.2 → 0.125.0, httpx 0.26.0 → 0.28.1, pydantic 2.6.1 → 2.9.2; added `starlette>=0.47.2` floor (closes Dependabot HIGH #3, MODERATE #4)
- `requirements.txt` - explicit `starlette>=0.47.2` floor added (closes Dependabot HIGH #3, MODERATE #4 on main app)

---

## [9.5.0B] - 2026-03-03 (HuggingFace live demo + distribution strategy)

**Status:** 720 tests, 1 skipped, 0 failed - OPENCLAW enabled on DO, all 5 demo agents live
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### HuggingFace Live Demo Space
- `huggingface_space/app.py`: Gradio app connecting to live TelsonBase DO server
 - All 5 trust tiers represented (QUARANTINE through AGENT apex)
 - Governance Pipeline Explorer: agent + tool picker, real 8-step pipeline decision
 - Kill Switch Demo: suspend demo_citizen, verify Step 2 rejection, reinstate
 - API credentials loaded from HF Space secrets - not in code
- `huggingface_space/README.md`: SDK changed static → gradio, updated description
- `huggingface_space/requirements.txt`: gradio>=4.0.0, requests>=2.31.0

### Demo Agents (registered on live DO server, all verified)
| Agent | Instance ID | Trust Tier | Key behavior |
|---|---|---|---|
| demo_quarantine | 60b364aacef04beb | QUARANTINE | file_read → HITL gated, file_delete → blocked |
| demo_probation  | 2c2ce1b0a2364c50 | PROBATION  | file_read → autonomous, email_send → HITL gated, payment_send → blocked |
| demo_resident   | e64a3549463c48f6 | RESIDENT   | file_write → autonomous, email_send → HITL gated |
| demo_citizen    | 9856076620944eeb | CITIZEN    | most autonomous - kill switch target |
| demo_agent      | db59ef829ac04d9e | AGENT      | payment_send, file_delete, config_update - all autonomous |

### OPENCLAW_ENABLED=true on DO server
- Governance pipeline now active on live server
- 720/720 tests pass with OPENCLAW enabled (confirmed)

### Legal / Distribution
- `DISCLAIMER.md`: New - explicit NOT RESPONSIBLE, AI platform disclaimer, beta warning
- `docs/System Documents/SOC2_TYPE_I.md`: Management Assertion updated v9.5.0B, Mar 6 2026
- `README.md`: 6 absolute guarantee claims softened to design intent, DISCLAIMER.md linked
- `README.md`: "A Note From Claude Code" certification section with verified claim table
- `README.md`: Goose MCP gateway section added (3-step setup, 13-tool table, gate levels)

### Distribution Strategy
- `docs/LAUNCH_SOCIAL_CHECKLIST.md`: HuggingFace Phase 1, full setup steps, sequencing table
- ProductHunt strategy: week 2 post-momentum - not day one

### CI
- `api/__init__.py`: Removed stale n8n_integration import (CI was failing)
- `.github/workflows/ci.yml`: Dummy secrets created before docker compose config validation

---

## [9.1.0B] - 2026-03-02 (Full .md audit + GitHub launch prep)

**Status:** 720 tests, 0 failed - 32 documentation files corrected, GitHub repo live
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Documentation - Full .md Audit (107 files read, 32 corrected)

Critical fixes:
- `secrets/api_key` → `secrets/telsonbase_mcp_api_key` in `OPENCLAW_INTEGRATION_GUIDE.md` (3 locations) - would have broken all deployments following that guide
- Wrong trust tier names in `MANNERS.md` (fictional names → QUARANTINE/PROBATION/RESIDENT/CITIZEN/AGENT)
- MIT license → Apache 2.0 in `PROJECT_OVERVIEW.md`
- WEB_CONCURRENCY=2 → WEB_CONCURRENCY=1 throughout `TECHNICAL_DEFENSE_BRIEF.md`
- `brokerage` tenant type removed from `DATA_PROCESSING_AGREEMENT.md`

Numbers corrected: 151 endpoints → 177, 93 security tests → 96, 2 Bandit medium → 8, 40 proof sheets → 42, 709 tests → 720, 4-tier trust → 5-tier + AGENT in 6 files. GitHub URLs fixed in 8 files. Version headers updated in 15 files.

### GitHub Repository Created

- `QuietFireAI/TelsonBase` - private until March 6, 2026 drop
- `CITATION.cff`: ORCID 0009-0000-1375-1725 (J. Phillips / Quietfire AI), Apache 2.0
- README: AGENT tier diagram, nav links, clone URL, proof sheet count, ORCID + citation section, 9 screenshots wired
- 10 repo topics: ai-governance, ai-agents, zero-trust, self-hosted, human-in-the-loop, kill-switch, audit-trail, mcp, fastapi, docker

---

## [9.0.0B] - 2026-03-02 (LAUNCH PREP - v9.0.0B_20260302d - Math CAPTCHA + Screenshots)

**Status:** 720 tests, 0 failed
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### UX - CAPTCHA Changed to Math-Only

- **`core/captcha.py`** - Default challenge type changed from `random.choice(list(ChallengeType))` to `ChallengeType.MATH`. Word scramble and text-reverse challenges are still available via explicit `challenge_type` parameter but will no longer appear in the registration flow.
- Number ranges simplified: addition uses 2-20, subtraction uses 10-25 minus 1-(a), multiplication uses 2-9 × 2-9. Results are unambiguous for any human, still require computation for a bot.
- Multiplication display changed from `*` to `x` for cleaner user-facing rendering.

### Screenshots Added

- **`screenshots/`** folder created with 9 dashboard screenshots (March 2, 2026).
- **README.md** updated with inline screenshots: dashboard overview, OpenClaw governance, audit trail, user console. Three additional screens in collapsible `<details>` block.
- **`screenshots/README.md`** documents which shots use live data vs demo data and how to replace them.

---

## [9.0.0B] - 2026-03-02 (LAUNCH PREP - v9.0.0B_20260302b - Pre-drop claims audit)

**Status:** 720 tests, 0 failed - 22 stale claims resolved across 10 files
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Pre-Drop Claims Audit - All Findings Resolved

Complete audit of every public-facing claim against live test output, live bandit scan, and live route count. Zero open findings at close.

| Finding | Files | Resolution |
|---|---|---|
| "709 tests" stale | README, CONTRIBUTING, TB-PROOF-001, INDEX, SECURITY_TESTING_STACK | Updated to 720 |
| Identiclaw test count "26" | README capability table | Updated to 50 (actual: `test_identiclaw.py --collect-only`) |
| OpenClaw test count "54" | README, TB-PROOF-001 | Updated to 55 |
| Security battery "93" | TB-PROOF-001, INDEX, SECURITY_TESTING_STACK | Updated to 96 |
| E2E count "22/27" | TB-PROOF-001, SECURITY_TESTING_STACK | Updated to 29 |
| Contracts count "6" | TB-PROOF-001 | Updated to 7 |
| Toolroom/API approx counts | TB-PROOF-001 | Updated to actual (129/19) |
| Bandit "27,540 lines" | README, FAQ | Updated to 37,921 (live scan) |
| Bandit "2 medium" | FAQ | Updated to 8 medium (live scan) |
| "151 API endpoints" | README stack table | Updated to 177 (live route count) |
| "4-tier earned trust" | README capability table | Updated to 5-tier |
| "6-step pipeline" (3x) | WHATS_NEXT | Updated to 8-step |
| Trust chain missing AGENT | OPENCLAW_INTEGRATION_GUIDE, OPENCLAW_OPERATIONS | Added AGENT to chain |
| "four trust levels" docstring | test_behavioral.py | Updated to five trust levels |

New file: `docs/Testing Documents/PRE_DROP_AUDIT.md` - permanent audit record, referenced in CLAUDE.md for every session.

---

## [9.0.0B] - 2026-03-02 (LAUNCH PREP - v9.0.0B_20260302a - AGENT 5th tier)

**Status:** 720 tests, 0 failed - AGENT apex tier fully wired
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Trust Governance - AGENT as 5th Trust Tier

- **`core/trust_levels.py`** - `AgentTrustLevel.AGENT` added as apex tier. Wired into: `TRUST_LEVEL_CONSTRAINTS` (300 actions/min, all capabilities unlocked), `REVERIFICATION_CONFIG` (strictest: 3-day interval, 99.9% success rate, 0 anomalies, min 50 actions/period), `PROMOTION_REQUIREMENTS` for CITIZEN→AGENT (90 days at CITIZEN, 5,000 successful actions, 99.9% success rate, 0 anomalies, 0 denied approvals, human approval required), `level_order` in both `promote()` and `demote()`, `check_promotion_eligibility()` ceiling updated from CITIZEN to AGENT.
- **`tests/test_contracts.py`** - `EXPECTED` set updated to include `"agent"`. Promotion path docstring and ordered list updated: QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT.
- **`tests/test_behavioral.py`** - `test_GIVEN_trust_levels_THEN_citizen_is_most_trusted` renamed to `test_GIVEN_trust_levels_THEN_agent_is_most_trusted` and updated to assert AGENT has the highest rate limit. CITIZEN capability assertions retained. `test_GIVEN_trust_levels_THEN_exactly_four_levels_exist` renamed to `test_GIVEN_trust_levels_THEN_exactly_five_levels_exist`, expected set updated to include `"agent"`.

---

## [9.0.0B] - 2026-03-01 (LAUNCH PREP - v9.0.0B_20260301i - Apache 2.0)

**Status:** 720 tests, 0 failed - ninth archive - launch candidate
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### License - Apache 2.0 (replaces AGPL v3 dual-license)

- **LICENSE** - replaced AGPL v3 / commercial dual-license with Apache License, Version 2.0. Full standard license text + copyright + social impact commitment. No commercial license required for any use.
- **COMMERCIAL_LICENSE.md** - retired. File now contains a short redirect notice explaining the move to Apache 2.0.
- **README.md** - license section updated to Apache 2.0. Removed dual-license description and "commercial license required" language.
- **website/index.html** - all AGPL-3.0 references updated to Apache 2.0 across 5 occurrences (feature card, FAQ, CTA section, open-source modal intro, modal for-home card).
- **docs/LAUNCH_DRAFTS.md** - 3 occurrences of AGPL/commercial-license language updated to Apache 2.0.
- **docs/FAQ.md** - Q16 updated (AGPL → Apache 2.0); Q19 rewritten as "What is the license and what can I do with TelsonBase?" - explains Apache 2.0 permissions, attribution requirement, and consulting availability.
- **docs/TECHNICAL_DEFENSE_BRIEF.md** - Section 11 rewritten as "The License - Apache 2.0"; table row updated.
- **docs/WHATS_NEXT.md** - "commercial license customers" → "consulting customers and enterprise sponsors".
- **docs/System Documents/OPENCLAW_SECURITY_ANALYSIS.md** - "source-available under AGPL v3" → "open source under Apache 2.0".
- **PROJECT_STRUCTURE.md** - LICENSE file description updated.

---

## [9.0.0B] - 2026-03-01 (LAUNCH PREP - v9.0.0B_20260301g)

**Status:** 720 tests, 0 failed - seventh consecutive clean-slate deployment - launch candidate
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Security - OpenClaw Mutation Operation Cache Eviction (Multi-Worker Fix)

`promote_trust()`, `demote_trust()`, `suspend_instance()`, `reinstate_instance()` in `core/openclaw.py` all called `get_instance()` which served stale in-memory state on the calling worker. Applied the same fix as `evaluate_action()` (which received this fix in the previous session): `self._instances.pop(instance_id, None)` before every authoritative Redis read in mutation operations. Prevents a worker from operating on stale trust level or suspension state when a parallel worker made the change.

### Governance - Specific Decision Reasons in All Governance Paths

`evaluate_action()` now returns structured, specific reason strings for all three outcomes:
- **Blocked:** `"BLOCKED: 'quarantine' tier prohibits 'external_request' actions - tool='http_request', category='external_request', trust='quarantine' - promote instance to enable this action category"`
- **Gated:** `"HITL gate: 'probation' tier requires human approval for 'external_request' - tool='http_request', approval_id=<id>"`
- **Allowed:** `"Autonomous: 'probation' tier permits 'read_internal' - tool='read_file' allowed without HITL"`
Every governance decision now includes trust level, action category, tool name, and disposition in the reason field.

### Governance - Demotion Review Framework

Any trust demotion (manual or Manners auto-demotion) now sets a Redis-backed demotion review flag:
- `_set_review_required()` stores demotion context: who demoted, reason, action count, review_note ("Review last N actions for cross-infection")
- `_is_review_required()` - Redis-backed check (multi-worker safe)
- `get_review_status()` - returns flag details or None
- `clear_review()` - admin sign-off method, deletes flag, writes to audit trail
- Advisory mode in beta: promotion proceeds with audit warning if review is pending. Infrastructure is in place; hard-block is one line change post-launch.

### API - Agent Status Announcement Endpoint

New `GET /v1/openclaw/{instance_id}/status`:
- Trust tier, suspended state, Manners score, action count, last_action_at
- Full capability matrix: `{"autonomous": [...], "gated": [...], "blocked": [...]}`
- `review_required: true/false` (demotion review pending)
- Pre-flight handshake for agent-to-agent communication: Agent B calls this before delegating to Agent A to route around capability gaps rather than experiencing silent blocking

### API - Clear-Review Endpoint

New `POST /v1/openclaw/{instance_id}/clear-review`:
- Admin-only (`admin:config` permission required)
- Human acknowledges review of last-N-actions audit for cross-infection
- Clears the demotion review flag, writes signed entry to audit chain
- Returns `{"review_cleared": true, "actions_reviewed": N, "cleared_by": "admin"}`

### Configuration - WEB_CONCURRENCY=1 for Beta

`docker-compose.yml` WEB_CONCURRENCY set to `"1"` (was `"2"`). Beta safety measure: `RBACManager._users` is in-memory only (no Redis persistence). Under multiple workers, a user registered on Worker A cannot log in via Worker B. Single worker eliminates this failure mode for beta deployments. Post-launch fix: Redis-persist the RBAC user dict.

### Docs - Launch Date Updated to March 6, 2026

- `README.md` letter date updated: February 23 → March 6, 2026
- `website/index.html` all "March 1, 2026" references updated to "March 6, 2026"
- `docs/LAUNCH_DRAFTS.md` HN post context date updated

### Docs - WHATS_NEXT.md Created

New `docs/WHATS_NEXT.md` - honest account of what's shipped, known beta limitations with mitigations, near-term priorities, and integration roadmap. Written for enterprise evaluators and community contributors.

---

## [9.0.0B] - 2026-03-01 (FINAL - v9.0.0B_20260301f)

**Status:** 720 tests, 0 failed - fifth consecutive clean-slate deployment confirmed - engineering hardening complete
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Security - Multi-Worker Tenant Manager Redis Fallback (Gap 1)

Under `WEB_CONCURRENCY=2` (enabled in this version), Worker B could return HTTP 404 for tenants created on Worker A because each worker had its own in-memory `_tenants` dict. Fixed by applying the same Redis fallback pattern already used in `OpenClawManager.get_instance()`.

- `TenantManager.get_tenant()` now checks in-memory first, then queries Redis if not found, then caches in this worker's memory for subsequent requests
- Failure mode is safe (warn + return None) - Redis fault does not crash the request

### Security - Grant-Access Tests Added (Gap 2)

Two new E2E tests added to `TestTenantIsolation`:

1. `test_admin_grant_access_allows_user` - full positive path: admin creates tenant → User C gets 403 → admin grants access → User C gets 200 → re-grant is idempotent (200)
2. `test_cross_tenant_denial_is_audit_logged` - verifies that HTTP 403 denials are written to the tamper-evident audit chain with `auth.failure` event type and the tenant_id as resource

### Governance - Smoke Test Script

`scripts/governance_smoke_test.sh` - new curl-based post-deploy verification script:
- Verifies API liveness + Redis health
- Registers a test agent (quarantine)
- Exercises all trust tier transitions (quarantine → probation)
- Verifies quarantine gate (read blocked, external write blocked)
- Verifies probation autonomy (read allowed)
- Verifies probation HITL gate (external write gated)
- Tests kill switch (suspend → action blocked → reinstate)
- Verifies audit chain integrity (SHA-256 hash chain, 0 breaks)
- Gracefully skips governance steps when `OPENCLAW_ENABLED=false`
- Validated live: 13/13 passed on DigitalOcean server (March 1, 2026)

### Security - Multi-Worker OpenClaw evaluate_action Fix

Under `WEB_CONCURRENCY=2`, governance decisions in `evaluate_action()` could use stale in-memory trust tier and suspension state from the registering worker, ignoring subsequent promotions/demotions applied on a different worker.

**Root cause:** `get_instance()` returns cached in-memory data when the key exists, regardless of whether Redis has newer state. The promoting worker updates Redis correctly; the evaluating worker's cache is never invalidated.

**Fix:** `evaluate_action()` now calls `self._instances.pop(instance_id, None)` before `get_instance()`, evicting any stale local copy and forcing a fresh Redis read. Governance decisions are always authoritative.

Found by: live governance smoke test - step 6 (probation allows internal read) returned `trust_level_at_decision: quarantine` under 2-worker load, failing with allowed=False when it should pass.

### Changed - Agent Registry (n8n → Goose)

- `agents/__init__.py`: `n8n_developer_agent` metadata entry removed. Replaced with `goose_operator` - documents Goose (by Block) as the native MCP operator integration
- Module header updated: "n8n integration" → "Goose/MCP integration"
- n8n workflow JSON files in `scripts/` remain as legacy/reference artifacts (already documented as such in PROJECT_STRUCTURE.md and CLAUDE.md)

### API Documentation - Swagger Pass

- `api/tenancy_routes.py`: Added `summary` and `description` to all tenant route decorators
- The `grant-access` endpoint now clearly documents admin-only requirement, idempotency, and audit trail behavior in `/docs`

### Tests - Total 720 (up from 718)

Two new E2E tests (grant-access positive + audit log denial):

| Suite | Before | After |
|---|---|---|
| E2E integration | 27 | 29 |
| All other suites | 691 | 691 |
| **Total (excl. MQTT stress)** | **718** | **720** |

CI threshold: `716 → 718`

---

## [9.0.0B] - 2026-03-01 (multi-tenancy access control fix)

**Status:** Deployment milestone - third clean-slate deployment confirmed + CAPTCHA replay fix + 8 new tests + multi-tenancy access control fix
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Security - Multi-Tenant Access Control (v9.0.0B, March 1 continuation)

Prior versions stored tenants without recording which user created them. Any authenticated user with `view:dashboard` (the default viewer role) could query any tenant's client matters by guessing a `tenant_id`. This was a HIPAA/SOC2 access control gap - no user-to-tenant binding existed at the route layer.

**Fix:**
- `Tenant` dataclass now stores `created_by` (set from `auth.actor` at creation, never user-supplied) and `allowed_actors: List[str]` initialized to `[created_by]`
- `TenantManager.grant_tenant_access(tenant_id, actor_id)` - admin-only method to expand access
- `_require_tenant_access(tenant_id, auth)` - route-layer helper called in every tenant-scoped and matter-scoped route. Returns HTTP 403 and writes an `AUTH_FAILURE` audit entry for unauthorized access
- Admins (`admin:config` or `*`) bypass - full access to all tenants
- `POST /v1/tenancy/tenants/{id}/grant-access` - admin endpoint to delegate tenant access
- `GET /tenants` filtered by `actor_filter` for non-admins - non-admins see only their own tenants
- README quick-start: added missing `alembic upgrade head` step (first-run 500 errors without it)

**Proof sheets:** TB-PROOF-021 updated (corrects false "cross-tenant query prevention" claim), TB-PROOF-042 created (new - documents `allowed_actors` enforcement model)

### Security - CAPTCHA Replay Attack Fix

- **Bug fixed:** `auth_routes.py` used `captcha_manager.is_solved()` which checked the solved flag but never deleted the challenge. A solved `captcha_challenge_id` could be replayed to register unlimited accounts without solving a new challenge.
- **Fix:** Added `consume_challenge()` to `CAPTCHAManager` (`core/captcha.py`) - checks solved status AND deletes from in-memory store and Redis on first redemption. Registration endpoint (`api/auth_routes.py`) now calls `consume_challenge()` instead of `is_solved()`.
- **Proof:** `test_captcha_solved_challenge_is_single_use` (E2E) - second registration with same `challenge_id` rejected HTTP 400.

### Tests - Gap Coverage (718 total, up from 709)

9 new tests closing previously identified coverage gaps:

1. **Cross-tenant access rejection** - `test_e2e_integration.py::TestTenantIsolation::test_cross_tenant_access_rejected` (HTTP 403 for unauthorized actor)
2. **CAPTCHA replay** - `test_e2e_integration.py::TestSecurityEndpoints::test_captcha_solved_challenge_is_single_use`
3. **Tenant data isolation** - `test_e2e_integration.py::TestTenantIsolation::test_tenant_matter_lists_are_isolated`
4. **Rate limiter boundary wall** - `test_security_battery.py::TestRuntimeBoundaries::test_rate_limiter_blocks_at_burst_limit`
5. **CAPTCHA challenge expiry** - `test_security_battery.py::TestRuntimeBoundaries::test_captcha_expired_challenge_rejected`
6. **Email token expiry** - `test_security_battery.py::TestRuntimeBoundaries::test_email_verification_expired_token_rejected`
7. **Concurrent audit linearity** - `test_integration.py::TestAuditChain::test_audit_chain_concurrent_writes_remain_linear`
8. **Kill switch Redis persistence** - `test_openclaw.py::TestKillSwitch::test_kill_switch_survives_cache_clear`
9. **Alembic migration idempotency** - `test_contracts.py::TestOperationalContracts::test_alembic_upgrade_head_is_idempotent`

**Test suite breakdown:**
| Suite | Before | After |
|---|---|---|
| Security battery | 93 | 96 |
| E2E integration | 24 | 27 |
| Core + all others | 592 | 595 |
| **Total (excl. MQTT stress)** | **709** | **718** |

CI threshold: `701 → 716`

### Changed

- Version jump to 9.0.0B marks first confirmed end-to-end clean deployment from a blank server
- Tarball deployment: fresh directory → `.env` → `generate_secrets.sh` → `docker compose up --build -d` → migrations → 709/709 tests, first try, zero errors

### Fixed

- Test suite: 9 failures resolved
 - CAPTCHA not solved in `_register_user` helper (E2E tests)
 - Email not verified before login in `_register_user` helper
 - `brokerage` tenant type replaced with `real_estate` (removed from valid list)
 - `conftest.py` REDIS_URL hardcoded to localhost (fails inside Docker containers)
 - `test_secrets.py` asserting `chmod 600` (script now uses `chmod 644`)
 - `test_observability.py` looking for `provider.yml` (renamed to `dashboards.yml`)
- `monitoring/mosquitto/password_file` excluded from tarball (platform-specific bcrypt; now generated fresh on each deployment by `generate_secrets.sh`)

### Deployment Guide (DEPLOYMENT_GUIDE.md)

- Version bumped to 9.0.0B, date to March 1, 2026
- `docker compose up -d` → `docker compose up --build -d` (required on first deploy)
- Health check: `https://your-domain.com/health` → `http://localhost:8000/health` (works pre-TLS)
- Registration: `full_name` field replaced with `username` (matches current API schema)
- Added CAPTCHA note for subsequent user registrations
- New step **3h - Security Verification**: run 96-test security battery before registering users

---

## [8.0.2] - 2026-02-21

**Status:** Container security hardening - Docker Scout CVE remediation
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Security

- **CVE-2024-23342 (HIGH, CVSS 7.4) - ecdsa timing side-channel** - `ecdsa` package removed
  from runtime image. It was a transitive dependency of `python-jose` but is not used:
  TelsonBase uses `JWT_ALGORITHM=HS256` (HMAC), and `python-jose[cryptography]` routes all
  cryptographic operations through the `cryptography` library backend. No upstream fix exists
  for this CVE; removal is the correct remediation.

- **CVE-2026-24049 (HIGH, CVSS 7.1) - wheel 0.45.1** - `wheel` upgraded to `0.46.2` enforced
  explicitly in both `Dockerfile` and `gateway/Dockerfile` pip upgrade step.

- **13 LOW binutils CVEs eliminated via multi-stage Dockerfile** - `gcc` (which depends on
  `binutils`) is now confined to a builder stage only. The runtime image is built from a
  clean `python:3.11-slim-bookworm` base with only pip-installed packages copied in from
  the builder. `binutils` never ships in the production container. CVEs addressed:
  CVE-2025-1178, CVE-2025-11494, CVE-2025-11413, CVE-2025-66866, CVE-2025-66862,
  CVE-2025-11840, CVE-2025-1182, CVE-2024-53589, CVE-2024-57360, CVE-2025-1148,
  CVE-2025-1179, CVE-2025-5245, CVE-2018-20673.

- **CVE-2025-14831, CVE-2025-9820 (MEDIUM - gnutls28), CVE-2025-45582 (MEDIUM - tar)** -
  `apt-get upgrade -y` added to both Dockerfiles' runtime stage, applying all available
  Debian Bookworm security patches on each image build.

- **6 curl LOW CVEs + 5 openldap LOW CVEs eliminated** - `curl` package removed from the
  runtime image entirely. It was only installed for the healthcheck (`curl -f ...`). In
  Debian, `curl` depends on `libcurl4` which depends on `libldap-2.5-0` (openldap client
  library), so removing `curl` also removes `openldap`. The Dockerfile HEALTHCHECK now uses
  Python's built-in `urllib.request` instead - no external binary required. curl CVEs:
  CVE-2025-10966, CVE-2025-15079, CVE-2025-0725, CVE-2024-2379, CVE-2025-15224,
  CVE-2025-14017. openldap CVEs: CVE-2026-22185, CVE-2015-3276, CVE-2017-17740,
  CVE-2020-15719, CVE-2017-14159.

### Accepted Residual Risk (No Action Taken)

- **CVE-2011-3389 (gnutls28 - BEAST attack)** - No upstream fix; mitigated by TLS 1.2+
  enforcement in Traefik which prohibits CBC cipher suites used by BEAST.

- **CVE-2005-2541 (tar - 2005)** - No upstream fix; not exploitable in this context (tar
  is a system utility, not exposed to untrusted input via the TelsonBase API).

- **CVE-2019-9192, CVE-2018-20796, CVE-2019-1010025, CVE-2019-1010024 (glibc)** - Debian
  has formally classified these as "won't fix" / "unimportant". They appear in essentially
  every Debian/Ubuntu container image. The findings relate to ASLR predictability and regex
  edge cases with no practical exploit path. No action available.

---

## [8.0.1] - 2026-02-21

**Status:** Startup stability patch - three service issues resolved, PRE-002 security fix
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Fixed

- **Celery Beat crash loop** - beat service was exiting with code 0 immediately on every start.
  Root cause: `depends_on: redis` used the default condition (container started, not healthy),
  allowing beat to attempt broker connection before Redis was ready. Fix: changed to
  `condition: service_healthy` on beat → redis, and added `--pidfile=/tmp/celerybeat.pid
  --schedule=/tmp/celerybeat-schedule` to prevent stale file issues. Same health condition
  applied to mcp_server and worker for startup ordering correctness.

- **Traefik ACME constant error loop** - Traefik was attempting Let's Encrypt certificate
  acquisition on every startup using `admin@example.com` against `localhost` (LE rejects
  both). Fix: removed ACME from base `docker-compose.yml` (local dev runs HTTP only).
  Created `docker-compose.prod.yml` overlay for production: adds ACME, HTTP→HTTPS redirect,
  and HSTS security headers. `.env` updated with real email.
  Production command: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

- **Grafana duplicate dashboard UIDs** - two identical provisioning config files
  (`dashboards.yml` and `provider.yml`) in `monitoring/grafana/provisioning/dashboards/`
  caused every dashboard UID to be registered twice. Both files defined the same provider
  name pointing to the same path. Deleted `provider.yml`.

- **Grafana operations dashboard hardcoded datasource UID** - `telsonbase-operations.json`
  used `PBFA97CFB590B2093` as the Prometheus datasource UID, which Grafana cannot resolve
  unless the UID is pinned in the datasource config. Fixed: added `uid: PBFA97CFB590B2093`
  to `monitoring/grafana/provisioning/datasources/datasource.yml`.

- **Grafana overview dashboard template variables** - `telsonbase_overview.json` used
  `${DS_PROMETHEUS}` variable references (import-time syntax) instead of a stable UID.
  File provisioning does not resolve `__inputs` templates. Fixed: replaced all 27
  `${DS_PROMETHEUS}` references with `PBFA97CFB590B2093`; removed `__inputs` and
  `__requires` sections.

- **PRE-002 tarfile path traversal (CWE-22)** - `backup_agent.py` path validation
  only checked `startswith("..")` and `startswith("/")`, missing embedded traversal
  components like `legit/../../../etc`. Fixed: replaced with `Path.resolve()`-based
  check that validates each archive member resolves within the restore target directory.
  `filter='data'` (Python 3.11.4+ backport of PEP 706) retained as second layer.
  PENTEST_PREPARATION.md PRE-002 updated to Fixed status.

- **Documentation** - AWS_TESTING_GUIDE.md vague login comment `admin / admin (or whatever
  was generated)` replaced with precise instruction referencing the secrets file.

---

## [8.0.0] - 2026-02-21

**Status:** First public release - drop-ready
**Contributors:** Jeff Phillips (Quietfire AI), Claude Code (Anthropic)

### Milestone

Version 8.0.0 marks TelsonBase's first public release. The CC suffix is retired -
version numbers are pure semver going forward. The engineering checklist is complete.
clawcoat.com is live. The governance pipeline is proven.

### OpenClaw Governance - Live Test Complete (10/10)

Full end-to-end governance pipeline validated against a live Docker stack
(mcp_server, PostgreSQL 16, Redis 7). All 10 steps passed:

1. Registration at QUARANTINE trust level
2. read_file gated at QUARANTINE (approval required) ✓
3. Promotion QUARANTINE → PROBATION ✓
4. read_file autonomous at PROBATION ✓
5. http_request gated at PROBATION (external_request category) ✓
6. Kill switch (suspend) ✓
7. Action while suspended → hard block, not gated ✓
8. Trust report - correct history, action counts, timestamps ✓
9. Reinstatement ✓
10. read_file autonomous post-reinstatement ✓

### Bugs Found and Fixed During Live Test

- **TOOL_CATEGORY_MAP**: `read_file`, `read_files`, `list_directory`, `search_files`
  were missing from the map. Governance engine fell back to unknown category and
  misclassified read actions. Added all variants → `READ_INTERNAL`.

- **is_suspended() bypass**: `evaluate_action()` Step 2 (kill switch check) used
  `instance.suspended or instance_id in self._suspended_ids` - both in-memory only.
  `is_suspended()` existed with Redis fallback but was never called. Under multi-worker
  or restart conditions the check could silently pass. Fixed: changed check to call
  `self.is_suspended(instance_id)` (in-memory + Redis-backed). Critical safety fix.

### Alembic Migration Validation

Migrations 001→002→003 applied cleanly against live PostgreSQL 16 in-container.
Database confirmed at `003_openclaw_instances (head)`.

Also fixed: `alembic.ini` used Windows-style `REM` comment headers which broke
Python's `configparser` INI parser. Converted to `#` comments.

### Dashboard

- OpenClaw tab now populated with demo data: 5 instances showing all four trust
  levels (CITIZEN, RESIDENT, PROBATION, QUARANTINE) plus one suspended instance
  to demonstrate the kill switch in the UI
- Version string updated to 8.0.0 across both consoles

### Infrastructure

- clawcoat.com live - deep purple glassmorphism, "Control Your Claw" hero,
  Chief of Staff framing, trust level pipeline visualization
- Pre-drop engineering checklist: 10/10 complete
- Validation report: `docs/Testing Documents/VALIDATION_REPORT_v7.4.0CC.md`

### Test Results

- **727 tests passing**, 1 skipped, 0 failures (verified in-container)

---

## [7.2.0CC] - 2026-02-13

**Status:** Third Floor - Real Estate Agents + Manners Compliance Framework
**Contributors:** Claude Code (Opus 4.6)

### Added
- **MANNERS.md** - Anthropic-aligned agent operating principles. Five binding principles (Human Control, Transparency, Value Alignment, Privacy, Security) with measurable KPIs. Compliance scoring (0.0-1.0) with five status tiers from EXEMPLARY to SUSPENDED. Auto-suspension at 3+ violations in 24 hours.
- **core/manners.py** (~400 lines) - Runtime Manners compliance engine. Singleton `manners_engine` tracks violations per agent per principle, computes weighted scores with time-decay, integrates with anomaly detection and trust levels. Convenience functions: `manners_check()`, `manners_violation()`, `manners_score()`, `manners_status()`. Redis persistence for violation history.
- **agents/registry.yaml** - Centralized HR registry for all 10 agents. Each entry: display_name, floor, role, description, actions, requires_approval, capabilities, trust_level, rate_limit, expected_responses, manners_compliance mapping. Covers ground level (4), mezzanine (1), third floor RE (3), n8n integration (1).
- **n8n Developer Agent** registered in `agents/__init__.py` metadata - visible on dashboard with actions, capabilities, and workflow file reference.
- **Manners API endpoints** in `main.py`: `GET /v1/manners/status` (all-agent summary), `GET /v1/manners/agent/{name}` (per-agent report), `GET /v1/manners/violations/{name}` (violation history).
- **docs/MANNERS_COMPLIANCE.md** - Full compliance guide with scoring methodology, violation types table, API reference, integration examples, and audit evidence documentation.
- **Transaction Coordinator Agent** (`agents/transaction_agent.py`, ~600 lines) - full closing lifecycle: create/update/close/cancel transactions, 19-item purchase checklist, 11-item lease checklist, party management (10 roles), 14 document types tracked per purchase, deadline monitoring with overdue detection, transaction summaries. 3 pre-seeded demo transactions. Celery tasks with daily deadline check at 7:00 AM UTC.
- **Compliance Check Agent** (`agents/compliance_check_agent.py`, ~550 lines) - Ohio-specific license tracking (ORC 5302.30, ORC 4735.56, 42 USC 4852d, ORC 4112.02), fair housing red flag scanner (17 phrases), continuing education tracking (30hr/3yr Ohio requirement), brokerage-wide compliance reports, violation management. 4 demo licenses (incl. 1 expired), daily compliance sweep at 7:30 AM UTC.
- **Document Preparation Agent** (`agents/doc_prep_agent.py`, ~500 lines) - 7 templates (purchase agreement, seller disclosure, agency disclosure, closing checklist, listing agreement, CMA report, lead paint disclosure), template field validation, generate/preview/finalize workflow with SHA-256 hashing. 3 pre-seeded demo documents.
- Agent registry updated: 3 new entries in `agents/__init__.py` (class registry + metadata)
- Celery worker updated: 3 new task modules + 2 scheduled beats (deadline check, compliance sweep)
- Seed data updated: real estate agent capabilities, 3 new approval requests, 3 new behavioral baselines

### Fixed
- User Console (`frontend/user-console.html`): added `/v1/auth/profile` fetch to `fetchLiveData()`. Previously used hardcoded demo user (`kparker`) even when connected to live API - approval decisions now use the real authenticated user.

---

## [7.1.0CC] - 2026-02-12

**Status:** User Console (Layer B) - operator-facing interface
**Contributors:** Claude Code (Opus 4.6)

### Added

- **User Console SPA** - `frontend/user-console.html` (~550 lines). 5-tab interface for day-to-day operators (paralegals, associates, case managers):
 - **Home:** Welcome card with user/role, quick stats (agents/approvals/health), quick-action cards (New Chat, View Agents, Check Approvals), recent activity feed
 - **Chat:** Full LLM chat interface ported from admin console. Model selector, demo responses, message history
 - **Agents:** Read-only agent cards with capability drill-down. No admin controls
 - **My Approvals:** Approve/reject with notes field, count badge on tab. Filtered to pending
 - **Activity:** Combined QMS log + anomaly alerts + audit entries. Read-only (no resolve)
- **`GET /console` route** in `main.py` - same pattern as `/dashboard`
- **Cross-links** - Admin Console header links to User Console; User Console header links to Admin Console
- **`user_ui_tests.md`** - 13 sections, 100+ test cases covering all tabs, cross-console navigation, responsiveness, edge cases
- **`clausenotes.md`** - Session log with architecture decisions and next steps

### Design Decisions

- Separate file, not hidden tabs - different layout, different focus
- Same design system (CSS variables, dark theme, card/badge patterns)
- Shared `telsonbase_api_key` in localStorage - connect once, both consoles work
- Read-only where appropriate (agents, anomalies). Only chat and approvals are write surfaces
- 5 tabs vs 15 - no compliance, sessions, federation, sovereign, toolroom, tenants, users, security, audit chain, or QMS filter views

---

## [7.0.0CC] - 2026-02-11

**Status:** Production Hardening Roadmap Complete - 22 items, 3 clusters, fully autonomous
**Contributors:** Claude Code (Opus 4.6)

### Summary

Complete execution of the 22-item production hardening roadmap across 6 sessions. TelsonBase is now pilot-ready for law firm deployments with full compliance documentation, security infrastructure, and business positioning.

### Cluster A: Pre-Demo Essentials (Items 1-6)

- **TLS termination** - Traefik HTTP→HTTPS redirect, HSTS (1yr, includeSubdomains, preload), security headers middleware (nosniff, frameDeny, XSS protection)
- **Per-user auth** - `core/user_management.py` (509 lines), `api/auth_routes.py` (484 lines). Register, login, MFA onboarding, change password, profile, logout. bcrypt 12 rounds, account lockout (5 attempts/15min), password strength (12+ chars, mixed)
- **Error sanitization** - Global exception handler, sanitized responses (no stack traces/paths), SecurityHeadersMiddleware (pure ASGI), fixed 8 `str(e)` leaks
- **Alembic migrations** - `alembic.ini`, `alembic/env.py`, initial migration (4 tables: users, audit_entries, tenants, compliance_records)
- **Backup & recovery** - `scripts/backup.sh` (155 lines), `scripts/restore.sh` (175 lines). RPO=24hr, RTO=15min
- **Secrets management** - `generate_secrets.sh` updated with `--rotate`/`--check` flags, 3 new production validators

### Cluster B: Pilot Readiness (Items 7-12)

- **E2E integration tests** - `tests/test_e2e_integration.py` (658 lines, 22 tests). 5 test classes: UserLifecycle, TenantWorkflow, SecurityEndpoints, AuditChainIntegrity, ErrorSanitization
- **RBAC enforcement** - `require_permission()` on all 140+ endpoints across 4 files. Permission taxonomy: view:*, manage:*, admin:*, security:*
- **Observability** - Grafana dashboard (`telsonbase_overview.json`), Prometheus alert rules (HighErrorRate, HighLatency, AuthFailureSpike, AuditChainBroken, ServiceDown)
- **Tenant-scoped rate limiting** - `core/tenant_rate_limiting.py` (674 lines). Redis sliding window, per-tenant (600/min), per-user (120/min), premium multiplier, in-memory fallback
- **Encryption at rest** - Volume-level (LUKS/BitLocker) recommended, pgcrypto supplementary, compliance mapping (HIPAA, CJIS, SOC 2, PCI DSS, GDPR)

### Cluster C: Contract Readiness (Items 13-18)

- **SOC 2 Type I** - 51 controls across 5 Trust Service Criteria, management assertion, evidence locations mapped to source files
- **Pen test preparation** - Attack surface inventory (140+ endpoints, 8 network services), OWASP Top 10 mapping, 5 known vulns in remediation tracker
- **Data Processing Agreement** - 13 sections + 3 annexes, placeholder brackets for customer details
- **Disaster recovery test** - `scripts/dr_test.sh` (--quick/--full), automated backup→stop→restore→verify→report
- **HA architecture** - Phase 1 Docker Swarm (2-3 days), Phase 2 Kubernetes (1-2 weeks), decision matrix by scale
- **Compliance roadmap** - HITRUST CSF, HIPAA SRA, SOC 2 Type II, CJIS, GDPR, PCI DSS. 6-phase, $50-125K, 12-18 months

### Post-Hardening (Items 19-22)

- **Competitive positioning** - 2-page, 5-competitor matrix, ICP definition, pricing advantage
- **Pricing model** - 3 tiers (Starter $150, Professional $400, Enterprise $750-1000/seat/month)
- **Deployment guide** - Prerequisites, 10-step install, post-install checklist, upgrade procedure
- **Shared responsibility matrix** - 1-page, 12-domain responsibility table

### Engineering Decisions (13 autonomous choices documented)

- Pure ASGI middleware (replaced BaseHTTPMiddleware for Starlette TestClient compatibility)
- Direct bcrypt library (replaced passlib - bcrypt 4.x removed `__about__` module)
- Dual-dependency RBAC pattern (`auth` + `_perm`) for backward-compatible permission enforcement
- Four-tier permission taxonomy: view:*, manage:*, admin:*, security:*
- AuditEventType consolidation (SECURITY_ALERT + `details.action` for specificity)
- Full decision log: `docs/HARDENING_CC.md`

### Test Results

- **618 passed**, 0 failed, 6 skipped (503 core + 93 security + 22 E2E)

### New Files

| File | Lines | Purpose |
|------|-------|---------|
| `core/user_management.py` | 509 | Per-user auth with bcrypt, lockout, password strength |
| `api/auth_routes.py` | 484 | Registration, login, MFA, profile endpoints |
| `core/tenant_rate_limiting.py` | 674 | Per-tenant Redis sliding window rate limiting |
| `core/auth_dependencies.py` | ~150 | Composable MFA + session FastAPI dependencies |
| `tests/test_e2e_integration.py` | 658 | 22 end-to-end integration tests |
| `docs/SOC2_TYPE_I.md` | ~800 | 51 SOC 2 controls with evidence mapping |
| `docs/PENTEST_PREPARATION.md` | ~500 | Attack surface inventory, OWASP mapping |
| `docs/DATA_PROCESSING_AGREEMENT.md` | ~600 | Customer-ready DPA template |
| `docs/ENCRYPTION_AT_REST.md` | ~400 | Volume encryption guidance |
| `docs/HA_ARCHITECTURE.md` | ~500 | Swarm → Kubernetes HA path |
| `docs/COMPLIANCE_ROADMAP.md` | ~400 | 6-framework certification roadmap |
| `docs/DISASTER_RECOVERY_TEST.md` | ~300 | DR test documentation |
| `docs/COMPETITIVE_POSITIONING.md` | ~300 | 5-competitor matrix |
| `docs/PRICING_MODEL.md` | ~400 | 3-tier pricing with revenue projections |
| `docs/DEPLOYMENT_GUIDE.md` | ~500 | 10-step production install guide |
| `docs/SHARED_RESPONSIBILITY.md` | ~200 | 12-domain responsibility matrix |
| `docs/HARDENING_CC.md` | ~400 | 13 engineering decisions with rationale |
| `scripts/dr_test.sh` | ~200 | Automated DR test script |
| `scripts/backup.sh` | 155 | Automated backup script |
| `scripts/restore.sh` | 175 | Automated restore script |

---

## [6.1.0CC] - 2026-02-10

**Status:** Dependency CVE remediation + production hardening
**Contributors:** Claude Code (Opus 4.6)

### Security - Dependency CVE Remediation (16 → 1)

| Package | Before | After | CVEs Fixed |
|---------|--------|-------|------------|
| fastapi | 0.109.2 | 0.125.0 | (pulls starlette fix) |
| starlette | 0.36.3 | 0.50.0 | CVE-2024-47874, CVE-2025-54121, CVE-2025-62727 |
| cryptography | 42.0.4 | 46.0.4 | GHSA-h4gh-qq45-vh27, CVE-2024-12797 |
| gunicorn | 21.2.0 | 25.0.3 | CVE-2024-1135, CVE-2024-6827 |
| requests | 2.31.0 | 2.32.5 | CVE-2024-35195, CVE-2024-47081 |
| python-jose | 3.3.0 | 3.5.0 | PYSEC-2024-232, PYSEC-2024-233 |
| pip | 24.0 | 26.0.1 | CVE-2025-8869, CVE-2026-1703 |
| wheel | 0.45.1 | 0.46.2 | CVE-2026-24049 |

**Remaining:** ecdsa 0.19.1 (CVE-2024-23342) - no fix version available, transitive dep of python-jose.

### Security - Bandit CWE-22 Fix
- `backup_agent.py:347`: Added `filter='data'` to `tarfile.extractall()` to prevent path traversal

### Infrastructure
- beat container memory limit: 64M → 128M (was at 95% utilization)
- mosquitto container memory limit: 64M → 128M (was at 94% utilization)
- Rate limiting now configurable via `.env`: `RATE_LIMIT_PER_MINUTE=300`, `RATE_LIMIT_BURST=60`
- Rate limit fields added to Settings class in `core/config.py`

### Test Results
- 503 passed, 6 skipped, 0 failed (10.26s)

---

## [6.0.0CC] - 2026-02-09

**Status:** Advanced testing validation - 5-level test infrastructure verified
**Contributors:** Claude Code (Opus 4.6)

### Rate Limiting Configuration

- Added `RATE_LIMIT_PER_MINUTE` and `RATE_LIMIT_BURST` to Settings class in `core/config.py`
- Configurable via `.env` file (previously only hardcoded defaults in middleware)
- Updated defaults: **300 req/min** (was 120), **60 burst** (was 20)
- Env vars: `RATE_LIMIT_PER_MINUTE=300`, `RATE_LIMIT_BURST=60`

### Advanced Test Suite (`run_advanced_tests.bat`)

New 20-test-group automated validation suite across 5 levels:

#### Level 1: Security Testing (S1-S6) - 6/6 PASS
- **S1** SQL/NoSQL injection - Pydantic rejects malformed params (422), no query execution
- **S2** QMS chain injection - Malicious `::SYSTEM_HALT::` and origin spoofing payloads safely handled
- **S3** Path traversal + command injection - `../../../etc/passwd` and `repo; curl | bash` both rejected by approved-sources gate
- **S4** JWT tampering - Expired, wrong-algo, empty, and garbage tokens all return 401
- **S5** Oversized payloads - 1MB payload and 100-level nested JSON handled gracefully (no crash/OOM)
- **S6** Header injection - CRLF injection and Host header spoofing return normal 200

#### Level 2: Chaos/Resilience (C1-C4) - 4/4 PASS
- **C1** Redis down - API reports `redis: unhealthy`, fully recovers after restart
- **C2** Ollama down - Health stays 200, LLM endpoints show unreachable, recovers after restart
- **C3** Mosquitto down - API continues, MQTT reports disconnected, recovers
- **C4** Concurrent stress - 50/50 parallel requests all return 200 (RunspacePool)

#### Level 3: Contract/Schema (K1-K3) - 2/3 PASS
- **K1** Schemathesis - OpenAPI contract testing integrated (`st run` CLI)
- **K2** OpenAPI completeness - 69 documented endpoints confirmed
- **K3** Content-Type consistency - All 7 tested endpoints return `application/json`

#### Level 4: Performance (P1-P3) - 3/3 PASS
- **P1** Sustained load - 200/200 requests, p50=41ms, p95=55ms, p99=71ms, 0 errors
- **P2** Authenticated latency - 20/20 requests, p50=86ms, p99=194ms, 0 errors
- **P3** Rate limiter - Wall confirmed at request #25 (working as designed)

#### Level 5: Static Analysis (A1-A4) - 3/4 PASS
- **A1** Bandit - 1 high (tarfile.extractall in backup_agent.py CWE-22), 2 medium (0.0.0.0 binds - expected in Docker)
- **A2** pip-audit - 16 CVEs in 8 packages flagged (cryptography, gunicorn, python-jose, requests, starlette, pip, wheel, ecdsa)
- **A3** Import health - All 18 core modules import successfully
- **A4** Dead endpoints - 15/15 endpoints responding, 0 errors

### Test Infrastructure Improvements
- Bat file uses PowerShell `Invoke-WebRequest` for injection payloads (avoids cmd.exe metacharacter issues)
- Temp-file approach for JSON payloads with `|`, `;`, `::` characters
- `RunspacePool` for true parallel concurrency (replaced `Start-Job`)
- PowerShell-based Content-Type and endpoint detection (replaced `for /f` curl loops)
- Schemathesis CLI at `/home/aiagent/.local/bin/st` with correct flags for v4.10.1

### Summary
- **19/20 test groups PASS** (1 known: dependency CVEs need upgrade)
- **503 unit tests pass**, 6 skipped, 0 failures
- **18,281 lines of code** scanned by bandit

---

## [5.5.2CC] - 2026-02-09

**Status:** Test suite fixes and Docker secrets hardening
**Contributors:** Claude Code (Opus 4.6)

### Test Fixes (15 failures → 0)

- **LLM endpoint tests** (`tests/test_ollama.py`) - 5 tests used `MagicMock` for async service methods (`ahealth_check`, `alist_models`, `aget_recommended_models`, `agenerate`, `achat`). Changed to `AsyncMock` to match the `await` calls in `main.py` endpoints.
- **Egress gateway tests** (`tests/test_integration.py`) - 2 tests failed because `ALLOWED_EXTERNAL_DOMAINS` was set in JSON array format (`["a.com","b.com"]`) but `egress_proxy.py` only handled comma-separated. Now strips brackets and quotes from env var values.
- **Docker Compose secrets tests** (`tests/test_secrets.py`) - 6 tests failed because `docker-compose.yml`, `.dockerignore`, and `.gitignore` are excluded by `.dockerignore` and don't exist inside containers. Tests now `pytest.skip()` when files are unavailable.
- **QMS halt test** (`tests/test_qms.py`) - `test_spec_example_halt_with_reason` expected string didn't include the `::!URGENT!::` priority prefix added in v2.2.0 (v5.5.0CC). Updated expected value.
- **Toolroom install test** (`tests/test_toolroom.py`) - `test_execute_install_without_approval_warns` didn't mock `load_manifest_from_tool_dir` or `cage.archive_tool`, both required since v5.4.0CC. Added mocks.

### Docker Compose Hardening

- **Top-level `secrets:` section** - 5 file-based secrets defined (`telsonbase_mcp_api_key`, `telsonbase_jwt_secret`, `telsonbase_encryption_key`, `telsonbase_encryption_salt`, `telsonbase_grafana_password`)
- **`mcp_server` service** - secrets mounted at `/run/secrets/`
- **Grafana** - switched from `GF_SECURITY_ADMIN_PASSWORD` (plaintext env var) to `GF_SECURITY_ADMIN_PASSWORD__FILE=/run/secrets/telsonbase_grafana_password`

### Egress Gateway Fix

- **`gateway/egress_proxy.py`** - `ALLOWED_EXTERNAL_DOMAINS` parsing now handles both comma-separated (`a.com,b.com`) and JSON array format (`["a.com","b.com"]`). Strips `[]`, `"`, and `'` from individual domain entries.

---

## [5.5.1CC] - 2026-02-09

**Status:** P0/P1 bug fixes from senior dev review + LLM chat interface
**Contributors:** Claude Code (Opus 4.6)

### P0 Bug Fixes (Crash Prevention)

- **`ToolMetadata.from_dict` / `ToolCheckout.from_dict`** - Now filter to known dataclass fields before construction. Prevents `TypeError` crash when Redis contains records from older/newer schema versions. This was a data migration time bomb.
- **`execute_tool_install`** (`toolroom/foreman.py`) - Removed `mkdir` before `git clone`. Git clone creates its own directory; pre-creating it caused "destination already exists" failures. Now cleans stale directories before cloning.
- **`cage.py` import safety** - Lazy `core.audit` imports (try/except inside methods). `Cage.__init__` catches `PermissionError`/`OSError` for graceful degradation in dev/test environments where `/app` doesn't exist. `CAGE_PATH` now configurable via environment variable.

### P1 Bug Fixes (Logic Corrections)

- **Cage `verify_tool` hash consistency** - `_hash_directory` now applies the same exclusion rules (`.git`, `__pycache__`, `node_modules`, `.pyc`, etc.) as `_archive_directory`. Previously, the live tool hash included files the archive excluded, causing false "tampered" alerts on every verification. Also includes relative file paths in hash so file renames are detected.
- **Cage symlink safety** - `_archive_directory` no longer follows symlinks. Malicious tool packages with symlinks to `/etc/passwd` or similar can no longer exfiltrate data into the cage archive.
- **Foreman hash delegation** - `ForemanAgent._hash_directory` now delegates to `Cage._hash_directory` for consistent hashing across both systems.
- **Repo normalization** - `propose_tool_install`, `execute_tool_install`, and `check_for_updates` all normalize repo names to lowercase before comparing against `APPROVED_GITHUB_SOURCES`.
- **Stale checkout cleanup** - New `cleanup_stale_checkouts(max_age_hours=24)` method on `ToolRegistry`. Prevents permanently locked tools when a worker crashes mid-checkout.
- **`qms_endpoint` decorator** - Now handles both sync and async functions correctly using `asyncio.iscoroutinefunction`. Uses `functools.wraps` for proper metadata preservation.

### UI: Chat Interface

- **New "Chat" tab** in the dashboard - standard LLM conversation interface
- Model selector dropdown (auto-fetches available models from `/v1/llm/models`)
- Message bubbles with user/assistant distinction, timestamps
- Enter to send, Shift+Enter for new line
- Demo mode with simulated responses when disconnected
- Footer reminder: "All inference local via Ollama"

---

## [5.5.0CC] - 2026-02-09

**Status:** QMS v2.2.0 - message priority, correlation TTL, schema registry
**Contributors:** Claude Code (Opus 4.6)

### QMS v2.2.0 Improvements

- **Message priority levels** (`core/qms.py`)
 - New `PRIORITY` block type: `::!URGENT!::`, `::!P1!::`, `::!P2!::`, `::!P3!::`
 - Optional prefix before origin block - backward compatible with v2.1.6
 - Halt chains automatically default to `URGENT` priority
 - Invalid priorities logged with warning and defaulted to `P2`
 - Priority exposed via `QMSChain.priority` property

- **Correlation TTL** (`core/qms.py`)
 - Embedded in correlation block: `::@@REQ_id@@TTL_30s@@::`
 - Agents know when to stop waiting for a response - prevents hung states
 - Default TTLs per priority: URGENT=10s, P1=30s, P2=120s, P3=600s
 - TTL exposed via `QMSChain.ttl_seconds` property
 - `build_chain(ttl_seconds=30)` parameter for easy usage

- **Schema registry** (`core/qms_schema.json`)
 - JSON file defining 10 message types with required/optional blocks
 - `validate_chain_semantics()` - checks action, status, priority validity per type
 - `get_message_schema()` - lookup schema by action name
 - `get_default_ttl()` - get default TTL for a priority level
 - Unknown message types warn but don't block (extensibility preserved)

- All v2.1.6 chains remain fully valid (no breaking changes)
- `build_chain()` and `build_halt_chain()` accept optional `priority` and `ttl_seconds` parameters

---

## [5.4.0CC] - 2026-02-09

**Status:** Toolroom hardening and completion. All 6 senior dev review toolroom gaps closed.
**Contributors:** Claude Code (Opus 4.6)

### Toolroom Hardening

- **Runtime-managed approved GitHub sources** (`toolroom/foreman.py`)
 - `APPROVED_GITHUB_SOURCES` now Redis-backed with API endpoints for add/remove
 - Seeded with 3 vetted defaults: `jqlang/jq`, `dbcli/pgcli`, `dbcli/mycli`
 - Adding sources requires HITL approval; removing does not (tightening is safe)

- **Exclusive tool checkout** (`toolroom/registry.py`)
 - `max_concurrent_checkouts` field on `ToolMetadata` (default 1 for subprocess, 0=unlimited for function tools)
 - Returns `::tool_busy::` with holder info when checkout denied

- **Manifest validation blocks installation** (`toolroom/foreman.py`)
 - Missing/invalid manifest → cleanup cloned directory + error (no zombie registry entries)
 - `allow_no_manifest` override for operator edge cases

- **Daily update check creates ApprovalRequests** (`toolroom/foreman.py`)
 - Each update proposal now creates a tracked `ApprovalRequest` visible in the approval API

- **Trust level default fail-safe** (`toolroom/foreman.py`)
 - Unknown tool trust level now defaults to CITIZEN (most restrictive), not RESIDENT
 - Warning logs when defaults are used

- **Tool version history and rollback** (`toolroom/registry.py`)
 - `version_history` field (capped at 10 entries, oldest trimmed)
 - `rollback_tool()` method with audit trail
 - `GET /v1/toolroom/tools/{id}/versions` and `POST /v1/toolroom/tools/{id}/rollback` endpoints

### The Cage - Compliance Archive

- **`toolroom/cage.py`** (NEW) - Secured archive for tool provenance
 - Every tool installation/update archived with timestamped receipt
 - `CageReceipt` records: SHA-256, source, approver, approval ID, timestamp
 - `verify_tool()` - integrity check comparing live tool against cage archive
 - Auto-purge oldest entries beyond 20 per tool
 - `GET /v1/toolroom/cage` - inventory listing
 - `GET /v1/toolroom/cage/{receipt_id}` - specific receipt
 - `POST /v1/toolroom/cage/verify/{tool_id}` - integrity verification

### New API Endpoints (10 total)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/toolroom/sources` | GET | List approved sources |
| `/v1/toolroom/sources` | POST | Propose adding source (HITL) |
| `/v1/toolroom/sources/execute-add` | POST | Add source after approval |
| `/v1/toolroom/sources/{owner}/{name}` | DELETE | Remove source |
| `/v1/toolroom/tools/{id}/versions` | GET | Version history |
| `/v1/toolroom/tools/{id}/rollback` | POST | Rollback to previous version |
| `/v1/toolroom/cage` | GET | Cage inventory |
| `/v1/toolroom/cage/{receipt_id}` | GET | Cage receipt detail |
| `/v1/toolroom/cage/verify/{tool_id}` | POST | Integrity verification |

### Documentation

- **GLOSSARY.md** - Added 25+ new terms (Cage, Foreman, Pinch Point, Rollback, etc.)
- **CHANGELOG.md** - Brought current through v5.4.0CC (was missing v5.2.0-v5.3.0)
- **USER_GUIDE.md** - New solopreneur-friendly guide to running TelsonBase
- **docs/claude_code_comments.md** - New unfiltered commentary section (v5.2.0-v5.4.0)

---

## [5.3.0CC] - 2026-02-09

**Status:** Senior dev gap fixes - 11 non-test gaps closed. 509+ tests passing.
**Contributors:** Claude Code (Opus 4.6)

### Security Fixes

- **JWT token revocation list** (`core/auth.py`) - Redis-backed `jti` revocation with TTL auto-cleanup
- **API key registry** (`core/auth.py`) - Multi-key support with per-key scoped permissions, SHA-256 hashed storage, zero-downtime rotation
- **Capability deny check bug** (`core/capabilities.py`) - Deny loop now checks action field (was only checking resource+scope)
- **Timing attack fix** - `hmac.compare_digest()` for API key comparison (v5.2.0CC)

### Architecture Fixes

- **Delegation Redis persistence** (`core/delegation.py`) - Delegations survive container restarts
- **Cascading delegation expiry** (`core/delegation.py`) - Children expire when parent expires
- **Delegation public API** (`core/delegation.py`) - `get_delegation_ids_by_grantor/grantee()` replaces private attribute access
- **EnforcedFilesystem async methods** (`core/capabilities.py`) - `aread()`, `awrite()`, `alist_dir()` via `asyncio.to_thread()`
- **`_handle_block_external()` honesty** (`core/threat_response.py`) - Returns `False` (was returning `True` for a no-op)
- **QMS regex fix** (`core/qms.py`) - Colons in block content (URLs, paths) no longer break parsing
- **Dockerfile HEALTHCHECK** - `curl -f http://localhost:8000/health`
- **Dead code removal** - Unused `passlib` import removed from `core/auth.py`

---

## [5.2.1CC] - 2026-02-09

**Status:** P2 production hardening. 509+ tests passing.
**Contributors:** Claude Code (Opus 4.6)

### Performance & Reliability

- **`redis.keys()` → `scan_iter()`** (`core/persistence.py`) - Non-blocking key enumeration
- **Async httpx for Ollama** (`core/ollama_service.py`) - No longer blocks event loop
- **MQTT authentication** (`core/mqtt_bus.py`) - Supports `MOSQUITTO_USER`/`MOSQUITTO_PASSWORD`
- **RBAC `require_permission` rewrite** (`core/rbac.py`) - Functional FastAPI dependency
- **Rate limiter stale bucket cleanup** (`core/middleware.py`) - Prevents unbounded memory growth

---

## [5.2.0CC] - 2026-02-09

**Status:** P0/P1 bug fix sweep - 19 fixes across 18 files. 509+ tests passing.
**Contributors:** Claude Code (Opus 4.6)

### Critical Fixes

- 8 missing packages in `requirements.txt` (root cause of Colab failures)
- 3 missing `AuditEventType` enum members
- `document_agent.py` abstract method not implemented
- `federation/trust.py` auto_accept tuple mismatch + singleton fix
- Timing attack fix in API key comparison (`hmac.compare_digest`)
- `n8n_integration.py` ApprovalRule creation fix
- AWS testing guide corrections (5 endpoint/auth errors)
- Docker Compose: Added Prometheus + Grafana services
- Celery beat schedule task name fix

---

## [5.1.0CC] - 2026-02-07

**Status:** 483 tests passing (48 new secrets tests + 435 existing). Zero failures.
**Contributors:** Claude

### Major: Docker Secrets Management - Closing the Last Critical Gap

The one security gap that existed in BOTH the inner TelsonBase codebase and the outer TelsonBase wrapper: secrets stored in plaintext `.env` files. This release eliminates that gap entirely for production deployments.

### Architecture

**Resolution Chain (layered, deterministic):**
1. Docker secrets files at `/run/secrets/<name>` - **production standard**
2. Environment variables from `.env` - **development fallback**
3. Hard error or warning - depending on `TELSONBASE_ENV` mode

**Threat model addressed:**
- `.env` file exposure via accidental git commit → `secrets/` dir is gitignored + dockerignored
- `.env` readable by any process in container → `/run/secrets/` is mount-restricted (tmpfs)
- Accidental logging of secret values → `SecretValue` wrapper masks `str()`, `repr()`, `format()`, f-strings
- Insecure default values in production → startup guard blocks launch when `TELSONBASE_ENV=production`
- Secrets baked into Docker images → `secrets/` excluded from build context via `.dockerignore`

### New Files

| File | Lines | Purpose |
|------|-------|---------|
| `core/secrets.py` | 310 | SecretsProvider, SecretValue wrapper, SECRET_REGISTRY |
| `scripts/generate_secrets.sh` | 130 | One-command bootstrap for all Docker secret files |
| `tests/test_secrets.py` | 380 | 48 tests across 7 test classes |
| `.gitignore` | 40 | Git exclusions (secrets/, .env, __pycache__, etc.) |

### Modified Files

| File | Changes |
|------|---------|
| `core/config.py` | Added `_resolve_secret()` for Docker secrets → env var resolution; `validate_production_secrets()` startup guard; `TELSONBASE_ENV` field; version bump to 5.1.0CC |
| `docker-compose.yml` | Added top-level `secrets:` section (6 file-based secrets); added `secrets:` to mcp_server, worker, beat services; added `TELSONBASE_ENV` environment variable; Grafana updated to use `GF_SECURITY_ADMIN_PASSWORD__FILE` |
| `.dockerignore` | Added `secrets/` directory exclusion |
| `.env.example` | Rewritten with secrets management documentation, `TELSONBASE_ENV` variable, Docker secrets instructions |
| `main.py` | Added `validate_production_secrets` import and call in lifespan; production mode blocks startup on insecure secrets |
| `version.py` | 5.0.0CC → 5.1.0CC |

### Secret Registry

| Secret | Docker File | Env Var | Required | Min Length |
|--------|------------|---------|----------|------------|
| `mcp_api_key` | `telsonbase_mcp_api_key` | `MCP_API_KEY` | Yes | 32 |
| `jwt_secret_key` | `telsonbase_jwt_secret` | `JWT_SECRET_KEY` | Yes | 32 |
| `encryption_key` | `telsonbase_encryption_key` | `TELSONBASE_ENCRYPTION_KEY` | Yes | 32 |
| `encryption_salt` | `telsonbase_encryption_salt` | `TELSONBASE_ENCRYPTION_SALT` | Yes | 16 |
| `webui_secret_key` | `telsonbase_webui_secret` | `WEBUI_SECRET_KEY` | No | 32 |
| `grafana_admin_password` | `telsonbase_grafana_password` | `GRAFANA_ADMIN_PASSWORD` | No | 12 |

### Test Suite - Full Output

```
tests/test_api.py            - 19 passed
tests/test_capabilities.py   - 15 passed
tests/test_signing.py        - 13 passed
tests/test_qms.py            - 115 passed
tests/test_behavioral.py     - 30 passed
tests/test_ollama.py         - 69 passed
tests/test_toolroom.py       - 134 passed
tests/test_observability.py  - 40 passed
tests/test_secrets.py        - 48 passed
                                ──────────
                                483 passed in 7.99s
```

---

## [5.0.0CC] - 2026-02-07

**Status:** 435 tests passing (40 new observability tests + 395 existing). Zero failures.
**Contributors:** Claude

### Major: Observability Stack & Agent Communication Bus

Closes the three remaining architectural gaps identified in the production audit. TelsonBase now has full Prometheus/Grafana monitoring, instrumented metrics on every API request, and a wired MQTT bus for real-time agent-to-agent communication.

#### New: Prometheus & Grafana Configuration (`monitoring/`)

- **`monitoring/prometheus.yml`** - Complete scrape configuration targeting all 5 service tiers: TelsonBase API (10s interval), Redis exporter, node-exporter, cAdvisor, and Prometheus self-monitoring. Organized by security zone matching docker-compose network segmentation.
- **`monitoring/grafana/provisioning/datasources/prometheus.yml`** - Auto-provisions Prometheus as Grafana's default datasource on first boot. Zero manual setup.
- **`monitoring/grafana/provisioning/dashboards/provider.yml`** - Auto-loads pre-built dashboards from the mounted directory.
- **`monitoring/grafana/dashboards/telsonbase-operations.json`** - Pre-built Grafana dashboard with 4 panel rows: API Security (auth failures, rate limits, anomalies), HTTP Traffic (request rate, p95 latency), Agent Activity & QMS Protocol (message counts by status, agent actions), Infrastructure (host CPU/memory/disk gauges, Redis memory).

#### New: Prometheus Metrics Instrumentation (`core/metrics.py`)

- **`/metrics` endpoint** - Unauthenticated Prometheus-compatible endpoint. Accessible only from internal Docker monitoring network, not publicly exposed via Traefik.
- **`MetricsMiddleware`** - Automatic HTTP request tracking: count, duration histogram (11 buckets from 5ms to 10s), in-progress gauge. Path normalization prevents label cardinality explosion.
- **12 metric families**: `telsonbase_http_requests_total`, `telsonbase_http_request_duration_seconds`, `telsonbase_auth_total`, `telsonbase_qms_messages_total`, `telsonbase_agent_actions_total`, `telsonbase_anomalies_total`, `telsonbase_rate_limited_total`, `telsonbase_approvals_pending`, `telsonbase_approvals_total`, `telsonbase_federation_messages_total`, `telsonbase_sovereign_score`, `telsonbase_sovereign_factor`.
- **Helper functions** for recording business events: `record_auth()`, `record_qms_message()`, `record_agent_action()`, `record_anomaly()`, `set_sovereign_score()`, etc.

#### New: MQTT Agent-to-Agent Communication Bus (`core/mqtt_bus.py`)

- **`MQTTBus` class** - Singleton connection manager with auto-reconnect, background thread loop, and thread-safe handler registration.
- **Topic structure**: `telsonbase/agents/{id}/inbox` (direct), `telsonbase/agents/{id}/outbox` (audit trail), `telsonbase/broadcast/all` (system-wide), `telsonbase/events/{type}` (anomaly/approval/federation events).
- **`AgentMessage` envelope** - Structured message format with source/target agent, QMS-formatted message_type, payload, signature field, priority level, and reply_to topic. Full JSON serialization/deserialization.
- **Lifecycle integration** - Bus initializes on application startup (lifespan), subscribes to system events, and shuts down gracefully on exit.
- **Health check integration** - `/health` endpoint now reports MQTT bus connection status.
- **Security**: Malformed messages on the bus are caught and logged as `SECURITY_ALERT` audit events.

#### New: Test Suite (`tests/test_observability.py`)

40 new tests across 5 test classes:
- `TestPrometheusMetrics` (12 tests) - Counter increments, gauge sets, histogram observation, path normalization, metrics response format
- `TestAgentMessage` (5 tests) - Creation, serialization, broadcast, priority, reply_to
- `TestMQTTBus` (9 tests) - Connection, subscribe, publish, disconnect, callbacks, malformed message handling
- `TestMQTTBusSingleton` (1 test) - Singleton pattern verification
- `TestMonitoringConfigs` (8 tests) - File existence, content validation, JSON parsing for all config files
- `TestMetricsEndpoint` (3 tests) - HTTP endpoint accessibility, content verification

#### Production Audit Gap Closure

| Gap | Status Before | Status After |
|-----|---------------|--------------|
| Authentication layer | ✅ Already implemented | ✅ Confirmed |
| Network segmentation | ✅ Already implemented (6 networks) | ✅ Confirmed |
| Prometheus/Grafana observability | ⚠️ Containers defined, no configs | ✅ Complete with configs, instrumentation, dashboard |
| Metrics endpoint | ❌ Missing | ✅ /metrics with 12 metric families |
| MQTT agent-to-agent communication | ⚠️ Mosquitto running, no wiring | ✅ Full pub/sub bus with QMS integration |
| Web agent | ❌ Pseudocode | ❌ Intentionally deferred |

### Files Changed

| File | Change |
|------|--------|
| `core/metrics.py` | **NEW** - Prometheus instrumentation (220 lines) |
| `core/mqtt_bus.py` | **NEW** - MQTT agent communication bus (340 lines) |
| `monitoring/prometheus.yml` | **NEW** - Prometheus scrape config |
| `monitoring/grafana/provisioning/datasources/prometheus.yml` | **NEW** - Grafana auto-provisioning |
| `monitoring/grafana/provisioning/dashboards/provider.yml` | **NEW** - Dashboard provider |
| `monitoring/grafana/dashboards/telsonbase-operations.json` | **NEW** - Pre-built Grafana dashboard |
| `tests/test_observability.py` | **NEW** - 40 tests |
| `main.py` | Added /metrics endpoint, MetricsMiddleware, MQTT lifecycle, MQTT health status |
| `version.py` | `4.9.0CC` → `5.0.0CC` |

### Test Suite - Full Output

```
tests/test_api.py            - 19 passed
tests/test_capabilities.py   - 15 passed
tests/test_signing.py        - 13 passed
tests/test_qms.py            - 115 passed
tests/test_behavioral.py     - 30 passed
tests/test_ollama.py         - 69 passed
tests/test_toolroom.py       - 134 passed
tests/test_observability.py  - 40 passed
                                ──────────
                                435 passed in 7.67s
```

## [4.9.0CC] - 2026-02-07

**Status:** 365 tests passing (49 new Ollama tests + 316 existing). Zero failures.
**Contributors:** Claude (bug fix, integration verification)

### Ollama/LLM Integration - Verified Complete

Full investigation of the three-layer Ollama architecture confirmed all components were already implemented. One capability system bug prevented agent instantiation.

#### Bug Fix

- **`core/capabilities.py`** - Added `MANAGE = "manage"` to `ActionType` enum
 - Root cause: `OllamaAgent` declared `ollama.manage:*` capabilities but the enum only had read/write/execute/publish/subscribe/none
 - `ValueError: 'manage' is not a valid ActionType` on agent construction
 - All 12 agent-layer tests were failing from this single missing enum value

#### Verified Components (already existed, no changes needed)

- **`core/ollama_service.py`** (570 lines) - Direct httpx→Ollama REST client
 - Health, list, info, pull, delete, generate, chat
 - Recommended models registry with tier classification
 - QMS protocol throughout, singleton pattern
- **`agents/ollama_agent.py`** (345 lines) - SecureAgent wrapper
 - 9 supported actions: generate, chat, list_models, model_info, pull_model, delete_model, health_check, recommended, set_default
 - Approval required for pull_model, delete_model
 - Full error handling for Ollama exception hierarchy
- **`main.py /v1/llm/*`** (lines 1644-1920) - 9 API endpoints
 - GET health, models, recommended, model detail
 - POST pull, generate, chat; DELETE model; PUT default
 - All auth-gated, audit-logged, QMS-compliant
- **`tests/test_ollama.py`** (834 lines) - 49 tests across all three layers
- **`requirements.txt`** - ollama client removed, httpx direct (no version pin conflict)

---

## [4.7.0CC] - 2026-02-07

**Status:** 316 tests passing (115 new QMS tests + 201 existing). Zero failures.
**Contributors:** Claude (specification synthesis, test suite, documentation)

### QMS v2.1.6 Formal Chain Specification

Synthesized from 8 source documents into a single canonical reference. Implemented three new v2.1.6 additions based on collaborative design session.

#### New Features

- **QMS_SPECIFICATION.md** - Complete formal reference for QMS v2.1.6
 - Guiding philosophy, core components, validation rules, block types
 - Use cases with TelsonBase-specific examples (toolroom, backup, federation)
 - Implementation status and migration path from legacy format
 - Design rationale (auditability, radio analogy, defense in depth)

- **Agent Identity Origin Block** `::<agent_id>::`
 - Mandatory position 1 in every chain - the "radio callsign"
 - Supports numerical IDs: `::<backup_agent/007>::`
 - Supports federation: `::<alpha_instance/sync_agent/012>::`
 - Missing origin = anonymous transmission = security alert
 - Analogy: no radio on the hotel comms network = suspect

- **Correlation Block** `::@@REQ_id@@::`
 - Mandatory position 2 - links request to response
 - Auto-generated `REQ_` + 8 hex chars (from UUID4)
 - Enables `grep @@REQ_id@@` to get complete conversation thread
 - Without this, 15 concurrent agents produce unintelligible log interleaving

- **System Halt Postscript** `::%%%%::-::%%reason%%::`
 - The siren fires first (`::%%%%::`), incident report follows (`::%%reason%%::`)
 - Only `%%...%%` string block may follow halt (validated)
 - Only ONE block may follow halt (validated)
 - Bare halt (no reason) valid but produces warning

#### New Test Coverage (115 tests in `tests/test_qms.py`)

| Section | Tests | Coverage |
|---------|-------|----------|
| Block Detection | 18 | All qualifier types, edge cases |
| Block Object | 10 | Construction, inner_value extraction |
| Chain Building | 10 | Origin, correlation, action, data, all 5 statuses |
| Halt Chain | 6 | Bare halt, with reason, siren ordering, data |
| Chain Parsing | 10 | Simple, data, halt, embedded text, roundtrip |
| Find Chains | 4 | Single, multiple, empty, surrounding text |
| Chain Validation | 11 | All rules: origin, correlation, command, halt postscript |
| Security Flagging | 8 | Chain detection, anonymous transmission, legacy rejection |
| Chain Properties | 7 | Data extraction, null handling |
| Qualifier Wrapping | 11 | All qualifier types |
| Legacy Compatibility | 9 | format_qms, parse_qms, dual-format detection |
| Constants/Enums | 7 | Spec alignment verification |
| Spec Examples | 4 | Exact reproduction of specification examples |

### Files Changed

| File | Action | Description |
|------|--------|-------------|
| `QMS_SPECIFICATION.md` | **NEW** | Complete v2.1.6 formal reference |
| `tests/test_qms.py` | **NEW** | 115 tests for chain subsystem |
| `version.py` | Updated | 4.6.0CC → 4.7.0CC |
| `CHANGELOG.md` | Updated | This entry |

### Core Implementation (unchanged - already built in 4.6.0CC)

The `core/qms.py` module already contained the v2.1.6 chain infrastructure:
`build_chain()`, `build_halt_chain()`, `parse_chain()`, `find_chains()`,
`validate_chain()`, `validate_chain_string()`, `is_chain_formatted()`,
`log_qms_chain()`. This release adds the specification document and test coverage
that validates and documents that implementation.

---

## [4.3.3CC] - 2026-02-04

**Status:** Documentation completeness - Gemini review (Perspective 3/4)
**Contributors:** Claude Code, Gemini 3 - Documentation Analysis

### Documentation Enhancements

Based on Gemini's comprehensive documentation analysis (Grade: A):

- **README.md**
 - Added link to local development setup (non-Docker)
 - Added reference to Windows Installation Guide
 - Version updated to 4.3.3CC

- **CONTRIBUTING.md**
 - Added "Good First Issues" section with starter areas:
   - Documentation improvements
   - Test coverage expansion
   - Dashboard UI enhancements
   - Agent templates

- **docs/TROUBLESHOOTING.md**
 - Added Python/pip dependency troubleshooting
 - Added virtual environment issues section
 - Added network/firewall troubleshooting
 - Added SSL/TLS certificate issues section

- **docs/API_REFERENCE.md**
 - Added "Rate Limiting" section documenting middleware limits
 - Added per-agent trust-based rate limits
 - Added "Webhooks" section with callback format and security

- **docs/SECURITY_ARCHITECTURE.md**
 - Added "Compliance Considerations" section (HIPAA, GDPR, Financial)
 - Added dedicated "Incident Response" section with quick reference
 - Enhanced "Related Documents" with incident response emphasis

### Version Updates

- `core/config.py` VERSION → 4.3.3CC
- All documentation version headers updated

---

## [4.3.2CC] - 2026-02-04

**Status:** Comprehensive analysis integration - Gemini review (Perspective 2/4)
**Contributors:** Claude Code, Gemini 3 - Validation & Review

### Documentation

- **INSTALLATION_GUIDE_WINDOWS.md** (NEW)
 - Step-by-step Docker Desktop installation
 - PowerShell commands for key generation
 - Common Windows-specific issues and solutions
 - WSL 2 and Hyper-V troubleshooting

### Naming Standardization

- Project name standardized to **TelsonBase** across all documentation
- GitHub URLs updated to `github.com/quietfire/telsonbase`
- AI collaborator credits reframed as "Model Versions" (removed company names)
- Updated README contributor methodology description

### Validation (Gemini Perspective 2)

- Confirmed code fulfillment of all stated objectives:
 - Zero-trust security ✓
 - Data sovereignty ✓
 - Secure agent collaboration ✓
 - Auditable operations ✓
 - Anomaly detection & human oversight ✓
 - Controlled external access ✓
- All prior code deficiencies (v4.0.x-4.1.x) confirmed resolved

---

## [4.3.1CC] - 2026-02-04

**Status:** Documentation milestone - Gemini review integration (Perspective 1/4)
**Contributors:** Claude Code, Gemini 3 - Review

### Documentation Improvements

Based on Gemini's documentation analysis and recommendations:

- **TROUBLESHOOTING.md** (NEW)
 - Common startup issues (Docker, ValidationError, auth failures)
 - Redis connection troubleshooting
 - Port conflicts, test failures, federation issues
 - Anomaly detection false positives
 - Diagnostic command reference

- **ENV_CONFIGURATION.md** (NEW)
 - Detailed explanation of all environment variables
 - Type conversions and format requirements
 - Development vs. production configuration examples
 - Security considerations for each variable

- **API_REFERENCE.md** (ENHANCED)
 - Added Python client class examples (sync and async)
 - Error handling patterns
 - QMS status code handling
 - Related documentation links

- **DEVELOPER_GUIDE.md** (ENHANCED)
 - Non-Docker local development setup
 - Virtual environment instructions
 - Minimal component testing without full stack
 - Feature availability matrix (local vs Docker)

### AI Collaboration Documentation

- Added `docs/claude_code_comments.md` - Claude Code's project observations
- Added `docs/gemini_comments.md` - Template for Gemini's observations
- Updated README.md with AI collaborator credits and human oversight note

---

## [4.1.0CC] - 2026-02-04

**Status:** Production hardening release - Full Redis persistence + Integration tests
**Contributor:** Claude Code (Anthropic)

### Major Enhancements

- **Redis Persistence** (All security modules now persist to Redis)
 - `core/signing.py` - Agent keys persist across restarts
 - `core/approval.py` - Pending approvals survive container restarts
 - `core/anomaly.py` - Behavioral baselines and anomalies persisted
 - `federation/trust.py` - Trust relationships persisted (session keys excluded for security)

- **Key Revocation Mechanism** (`core/signing.py`)
 - Added `revoke_agent(agent_id, reason, revoked_by)` with full audit trail
 - Revoked agents tracked and cannot be re-registered without explicit clearing
 - `clear_revocation()` for security-reviewed re-registration
 - `is_revoked()` check before message verification

- **Federation Session Key Exchange** (`federation/trust.py`)
 - Fixed critical gap: session keys now properly exchanged using RSA-OAEP encryption
 - `accept_trust()` returns encrypted session key in acceptance response
 - New `process_trust_acceptance()` to decrypt and store session key
 - Session keys NOT persisted (must re-exchange after restart for security)

### Security Improvements

- **CORS Wildcard Warning** (`core/config.py`)
 - Added `@field_validator` to warn if CORS allows all origins (`["*"]`)
 - Emits warning at startup for production awareness

### Testing

- **Integration Test Suite** (`tests/test_integration.py`)
 - Federation handshake end-to-end test
 - Egress gateway domain blocking tests
 - Approval workflow (approve/reject) tests
 - Cross-agent signed messaging tests
 - Key revocation tests
 - Anomaly detection (capability probe) tests

---

## [4.0.5CC] - 2026-02-04

**Status:** Security hardening release - All 47 tests passing
**Contributor:** Claude Code (Anthropic)

### Security Improvements
- **JWT Secret Validation** (`core/config.py`)
 - Added `@field_validator` to detect insecure default secrets
 - Emits warning if JWT_SECRET_KEY is placeholder or < 32 chars

- **Configurable CORS** (`main.py`, `core/config.py`)
 - CORS origins now configurable via `CORS_ORIGINS` env var
 - Defaults to `["*"]` but can be locked down for production

- **TrustLevel Validation** (`main.py`)
 - Added validation for federation trust_level enum
 - Returns 400 with valid options if invalid value provided
 - Validates expires_in_hours > 0

### Bug Fixes
- **Fixed bare `except:` handlers** (security best practice)
 - `agents/document_agent.py:216` - Now catches `(IOError, OSError, UnicodeDecodeError)`
 - `agents/document_agent.py:515` - Now catches `(IOError, OSError)`
 - `main.py:306` - Now catches `Exception` with logging

- **Fixed HTTPException format** (`main.py:396`)
 - `detail` parameter now string, not dict (FastAPI convention)

- **Fixed Starlette 0.50+ compatibility** (`core/middleware.py:460`)
 - Changed `response.headers.pop()` to check-then-delete pattern

### Enhancements
- **Webhook callbacks on approval decisions** (`main.py`)
 - Approve/reject endpoints now trigger n8n webhook callbacks
 - Enables proper async workflow completion in n8n

- **Improved memory management** (`core/signing.py`)
 - Message ID cleanup threshold reduced from 10,000 to 100
 - Prevents unbounded memory growth in high-volume scenarios

- **Callback TTL cleanup** (`api/n8n_integration.py`)
 - Added 24-hour TTL for pending approval callbacks
 - Prevents memory leak from orphaned callbacks

---

## [4.0.1C] - 2026-02-04

**Status:** Documentation release - GitHub-ready  
**Contributor:** Claude (Anthropic)

### Added
- `LICENSE` - MIT License with Quietfire AI social impact commitment
- `SECURITY.md` - Vulnerability reporting procedures
- `CONTRIBUTING.md` - Project-specific contribution guide with QMS conventions
- `CODE_OF_CONDUCT.md` - Community standards
- `GLOSSARY.md` - 25+ term definitions
- `PROJECT_STRUCTURE.md` - Accurate directory documentation
- `.github/ISSUE_TEMPLATE/bug_report.md` - Bug report template
- `.github/ISSUE_TEMPLATE/feature_request.md` - Feature request template
- `.github/PULL_REQUEST_TEMPLATE.md` - PR checklist

### Changed
- Consolidated `CHANGELOG_v3.0.1.md`, `CHANGELOG_v3.0.2.md`, `CHANGELOG_v3.0.3.md` into single `CHANGELOG.md`

---

## [4.0.0C] - 2026-02-04

**Status:** Bug fix release - Config validation  
**Contributor:** Claude (Anthropic)  
**Bug Source:** Gemini Colab test run v4.0.0G

### Fixed
- `core/config.py` - Added missing Settings fields causing `ValidationError`:
 - `backup_dir_host_path`
 - `webui_secret_key`
 - `grafana_admin_user`
 - `grafana_admin_password`

---

## [3.0.3] - 2026-02-03

**Status:** Major feature release - Production hardening + Complete agent ecosystem  
**Contributor:** Claude (Anthropic)

### Added
- **n8n Integration** (`api/n8n_integration.py`)
 - `/v1/n8n/execute` - Execute agent actions from n8n
 - `/v1/n8n/agents` - List available agents
 - `/v1/n8n/approvals/{id}/status` - Poll approval status
 - Webhook callbacks for async approval workflows

- **Production Middleware** (`core/middleware.py`)
 - Rate limiting (token bucket: 120/min, burst 20)
 - Request size limits (10MB max)
 - Circuit breaker for external service failures
 - Request ID tracking
 - Slow request logging (>5 seconds)
 - Security headers (X-Frame-Options, XSS protection)

- **Alien Adapter** (`agents/alien_adapter.py`)
 - Quarantine system for LangChain/external frameworks
 - Status levels: QUARANTINE → PROBATION → RESIDENT → CITIZEN
 - `LangChainAdapter` class for tool creation
 - Promotion/revocation functions

- **Document Processor Agent** (`agents/document_agent.py`)
 - Actions: extract_text, summarize, search, get_metadata, list_documents, redact
 - Sensitive data detection (SSN, phone, email, credit card, DOB)
 - Approval gate for redaction operations

- **Example Workflow** (`scripts/n8n_workflow_document_processing.json`)

---

## [3.0.2] - 2026-02-03

**Status:** Feature release - QMS integration  
**Contributor:** Claude (Anthropic)

### Added
- **QMS Module** (`core/qms.py`)
 - `QMSStatus` enum (Please, Thank_You, Thank_You_But_No, Excuse_Me, Pretty_Please)
 - `validate_qms()` - Validate message format
 - `parse_qms()` - Parse into structured QMSMessage
 - `format_qms()` - Format outgoing messages
 - `qms_endpoint` decorator
 - `log_qms_transaction()` - Audit trail logging

- **Audit Event Types** (`core/audit.py`)
 - `SECURITY_ALERT`
 - `SECURITY_QMS_BYPASS`
 - `AGENT_ACTION`

- **Alien Quarantine Zone** (`requirements.txt`)
 - LangChain dependencies (isolated, not integrated)

### Changed
- `main.py` - Added QMS protocol documentation header
- `agents/base.py` - Added QMS protocol documentation
- `core/__init__.py` - QMS exports

---

## [3.0.1] - 2026-02-03

**Status:** Bug fix release - All 47 tests passing  
**Bug Source:** Gemini Colab test run  
**Contributor:** Claude (Anthropic)

### Fixed
- **Bug 1:** `federation/trust.py` - FederatedMessage dataclass field ordering
 - Error: `TypeError: non-default argument 'action' follows default argument`
 - Fix: Reordered fields so required fields precede optional fields

- **Bug 2:** `core/auth.py` - AuditEventType import
 - Error: `AttributeError: 'AuditLogger' object has no attribute 'AuditEventType'`
 - Fix: Added `AuditEventType` to imports, fixed references

- **Bug 3:** `requirements.txt` - Dependency conflicts
 - `httpx==0.26.0` → `httpx==0.25.2` (ollama compatibility)
 - `pytest==8.0.0` → `pytest==7.4.4` (pytest-asyncio compatibility)
 - Removed duplicate sections

---

## [3.0.0] - 2026-02-03

**Status:** Major release - Zero-trust agent security  
**Contributor:** Claude (Anthropic)

### Added
- **Cryptographic Message Signing** (`core/signing.py`)
 - HMAC-SHA256 signatures
 - Nonce for replay protection
 - Timestamp validation

- **Capability System** (`core/capabilities.py`)
 - Explicit permission declarations
 - No wildcard capabilities
 - Runtime enforcement

- **Behavioral Anomaly Detection** (`core/anomaly.py`)
 - Baseline tracking
 - Deviation scoring
 - Automatic alerting

- **Approval Gates** (`core/approval.py`)
 - Human-in-the-loop for sensitive operations
 - Configurable timeout and escalation
 - Audit trail

- **Federation** (`federation/trust.py`)
 - RSA-4096 keypairs
 - Trust levels (MINIMAL, STANDARD, ELEVATED, FULL)
 - Invitation/acceptance protocol
 - Cross-instance messaging

- **Frontend Dashboard** (`frontend/Dashboard.jsx`)
 - Agent management
 - Approval queue
 - Anomaly monitoring
 - Federation relationships

---

## [2.0.0] - 2026-02-03

**Status:** Production-ready foundation  
**Contributor:** Claude (Anthropic)

### Added
- Network segmentation (Docker networks: frontend, backend, data)
- Authentication middleware (JWT tokens)
- Audit logging (`core/audit.py`)
- Egress gateway (`gateway/egress_proxy.py`)

---

## [1.0.1] - 2026-02 (Initial)

**Status:** Proof of concept
**Architect:** Jeff Phillips

### Added
- Initial codebase structure
- Docker Compose orchestration
- Basic API endpoints
- Backup agent (partially functional)

---

## Contributors

| Suffix | Contributor |
|--------|-------------|
| G | Gemini (Google) - Testing, validation, documentation review |
| C | Claude (Anthropic) - Implementation, architecture |
| CC | Claude Code (Anthropic) - Production hardening, security, toolroom |

---

**Architect:** Jeff Phillips - support@clawcoat.com
**Project:** TelsonBase by Quietfire AI
