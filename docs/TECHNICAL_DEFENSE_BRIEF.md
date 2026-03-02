# TelsonBase — Technical Defense Brief
## Know-Cold Reference for Launch Q&A

> Prepared Feb 25, 2026. For GitHub drop, HN, Reddit, and any technical interview.
> This is not a pitch doc — it's the 20 things someone can ask you that you should be
> able to answer without hesitation.

---

## 1. The Audit Chain — WATCH/MULTI/EXEC

**What it is:**
Redis optimistic locking. When writing a new audit entry, the system:
1. Issues `WATCH audit:chain:state` — Redis marks this key as watched
2. Reads the current state (last sequence number + last hash)
3. Computes the new entry hash in Python (SHA-256 over 9 fields)
4. Opens a `MULTI` block (transaction)
5. Writes the new state + the new entry atomically
6. Calls `EXECUTE` — if anything touched `audit:chain:state` between WATCH and EXECUTE,
   Redis aborts the transaction and returns a WatchError
7. On WatchError: retry with fresh state (up to 20 attempts with backoff)

**Why not a Lua script?**
SHA-256 must run in Python. Redis's Lua scripting environment has no crypto primitives.
WATCH/MULTI/EXEC achieves the same atomicity guarantee while keeping the hash computation
in Python.

**Why not a distributed lock (the old approach)?**
The old lock had a timeout fallback path. If the lock wasn't acquired within 2 seconds,
the code fell through and wrote with stale in-memory state — which is how the duplicate
sequence numbers appeared. WATCH/MULTI/EXEC has no fallback path: it either commits with
consistent state or retries.

**If asked:** *"Explain your audit chain concurrency model."*
> "We use Redis optimistic locking — WATCH/MULTI/EXEC. The key insight is that SHA-256
> has to run in Python, so we can't use a Lua script. We read state under WATCH, compute
> the hash, and commit atomically. Any concurrent write causes a WatchError and we retry
> with fresh state. Redis is the single source of truth — in-memory state is only updated
> after a successful commit."

---

## 2. SHA-256 Hash Chaining — How the Chain Actually Works

**The 9 fields that get hashed (core/audit.py:68):**
sequence, timestamp, event_type, message, actor, actor_type, resource, details, previous_hash

**The math:**
```
entry_hash = SHA256(field1 + "|" + field2 + ... + field9)
```
Each entry's `previous_hash` = the prior entry's `entry_hash`.
The first entry's `previous_hash` = `"0000000000000000..."` (GENESIS_HASH, 64 zeroes).

**What verification does:**
`GET /v1/audit/chain/verify` reads entries from Redis in sequence order, recomputes the
expected hash for each one, and checks that `entry.entry_hash == computed_hash` AND
`entry.previous_hash == prior_entry.entry_hash`. If either fails anywhere in the chain,
it returns `status: invalid` with the specific sequence numbers that broke.

**What tampering looks like:**
If someone modifies entry #47's message field: the hash stored for #47 no longer matches
the recomputed hash → `hash_mismatch` at seq 47. Every entry after 47 also fails because
their `previous_hash` links to the now-invalid #47 hash.

**If asked:** *"Can someone just recompute all the hashes after tampering?"*
> "Yes — if they have direct Redis write access, they could rewrite the chain and recompute
> all hashes. Redis is not WORM storage. The chain detects application-layer tampering —
> anything going through TelsonBase — not insider attacks with direct database access. For
> that threat model you'd add external append-only storage (S3 Object Lock, etc.) as a
> supplement. We document this. No database-backed audit log prevents this — including the
> ones banks use."

---

## 3. gunicorn WEB_CONCURRENCY — Multi-Worker, Race-Free

**What gunicorn -w N means:**
N separate OS processes, each running a full copy of the app. They share nothing in memory.
Each has its own Python interpreter, its own copy of all in-memory variables.

**Current configuration: WEB_CONCURRENCY=2 (default), configurable at runtime.**
The Dockerfile uses `exec gunicorn ... -w ${WEB_CONCURRENCY:-2}`. `exec` ensures Docker's
SIGTERM goes directly to gunicorn (PID 1), not to sh — enabling graceful in-flight shutdown.

**Why the audit chain is safe under multiple workers:**
`_create_chain_entry()` uses Redis WATCH/MULTI/EXEC optimistic locking. The sequence:
1. WATCH the chain key
2. Read `last_sequence` and `last_hash`
3. Compute new entry
4. MULTI — if the watched key changed between step 2 and 4, the transaction aborts
5. EXEC — atomic write or retry

Redis is the single source of truth. Two workers racing to write the same sequence number
results in one succeeding and one retrying — never a forked chain. The previous `-w 1`
constraint predated this implementation (added Feb 25, 2026) and was a historical artifact.

**MQTT startup events and duplicate handling:**
Both workers fire a startup audit event. Each goes through WATCH/MULTI/EXEC — they get
sequential sequence numbers, not a fork. The events are logged; only the first one "wins"
the sequence slot it targeted.

**If asked:** *"Is the audit chain safe under load?"*
> "Yes. Redis WATCH/MULTI/EXEC gives us optimistic locking. Two workers can't write the
> same sequence number — one wins, one retries. The chain is linear. 720 tests verify this,
> including adversarial concurrency scenarios."

**If asked:** *"This doesn't scale beyond 2 workers."*
> "WEB_CONCURRENCY is configurable. The constraint is Redis throughput and the optimistic
> retry loop under very high contention — not the architecture. For a governance platform
> workload, 2 workers is appropriate. Add more at runtime if you need them."

---

## 4. ecdsa Removal — CVE-2024-23342

**What ecdsa is:**
A Python library that implements Elliptic Curve Digital Signature Algorithm. Used for
signing/verifying data with EC keys.

**Why it was a dependency:**
`python-jose` (the JWT library TelsonBase uses) lists `ecdsa` as an optional dependency
for EC-based JWT algorithms: ES256, ES384, ES512.

**Why it was safe to remove:**
TelsonBase uses `JWT_ALGORITHM=HS256` — HMAC-SHA256. This is a *symmetric* algorithm.
It uses the `cryptography` library (libssl-backed) for signing and verification, not `ecdsa`.
The `ecdsa` library is the fallback for EC-based algorithms that TelsonBase does not use.
Removing it eliminates the attack surface with zero functional impact.

**The CVE (CVSS 7.4, HIGH):**
Timing side-channel in `ecdsa`'s signature verification. An attacker who can make many
repeated verification requests and precisely measure response times can potentially extract
the private key. Not exploitable in TelsonBase's architecture even if the library were
present (we don't do EC signatures), but removing it is cleaner.

**The Dockerfile line:**
```dockerfile
RUN pip uninstall -y ecdsa || true
```
The `|| true` means if ecdsa somehow isn't installed, the build doesn't fail. It runs
*after* all requirements are installed, so it strips it from the final image.

**If asked:** *"Did you verify JWT still works after removing ecdsa?"*
> "Yes. python-jose's HS256 path uses the `cryptography` library, not `ecdsa`. We run
> 720 tests including auth flows. JWT signing, verification, and refresh all pass.
> ecdsa is the EC algorithm backend — we don't use EC algorithms."

---

## 5. JWT — HS256 vs RS256/ES256, and Why HS256 is Correct Here

**HS256 (what TelsonBase uses):**
HMAC-SHA256. Symmetric. One secret key both signs and verifies tokens. Fast. Simple.

**RS256 / ES256 (asymmetric alternatives):**
RSA or EC. Private key signs. Public key verifies. Needed when *multiple separate services*
need to verify tokens without sharing a secret.

**Why HS256 is appropriate:**
TelsonBase is a self-hosted monolith. The service that creates tokens and the service that
verifies tokens are the same process. There is no microservice architecture where external
services need to independently verify JWTs without access to the secret. HS256 is the
correct algorithm for this deployment model.

**If asked:** *"HS256 is weak — why not RS256?"*
> "RS256 is necessary when you have distributed token verification across services that
> can't share a secret. TelsonBase is a monolith — the issuer and verifier are the same
> service. HS256 is faster and simpler, and appropriate for this architecture. If we were
> federating identity across multiple services, RS256 would be the call."

**If asked:** *"What if your secret key leaks?"*
> "Then you rotate it — update SECRET_KEY in .env and restart. Same exposure model as a
> leaked database password. If an attacker has your .env file, they have everything else
> too — that's a different incident response."

---

## 6. Token Revocation — How TelsonBase Makes JWTs Revocable

**The problem with standard JWTs:**
A JWT is valid until it expires, period. If a user logs out or an admin terminates a session,
the token technically still works until the expiry timestamp.

**TelsonBase's solution:**
Redis revocation list keyed by JTI (JWT ID — a unique identifier embedded in every token).

**How it works:**
1. Every JWT issued by TelsonBase includes a `jti` claim (UUID)
2. On logout or admin session termination: `SETEX revoked:jti:{jti} {remaining_ttl} "1"`
3. Every authenticated request: check `EXISTS revoked:jti:{jti}` in Redis
4. If found → 401 Unauthorized, regardless of token signature validity
5. The Redis key auto-expires when the token would have expired anyway (no cleanup needed)

**Performance cost:** One Redis read per authenticated request. Redis reads are sub-millisecond.
This is negligible.

**If asked:** *"JWTs can't be revoked."*
> "By default, correct. TelsonBase maintains a Redis revocation list keyed by JTI. Every
> authenticated request does a Redis lookup. If the JTI is in the revocation set — whether
> from logout, admin termination, or security event — the request is rejected with 401.
> The keys auto-expire with the token's natural lifetime. One Redis read per request."

---

## 7. Trust Tier Enforcement — Server-Side, Not UI

**The critical question:** Is the trust gating enforced in the API or only in the dashboard?

**The answer:** Server-side, in `api/openclaw_routes.py` → `core/openclaw.py`.

**What happens when an agent calls evaluate_action:**
1. API receives the action request with agent's `claw_id`
2. `get_instance(claw_id)` fetches trust level from Redis (not memory — Redis)
3. `evaluate_action()` applies trust-level rules:
   - QUARANTINE: every action → `REQUIRES_APPROVAL`
   - PROBATION: read/internal → `ALLOW`, external/destructive → `REQUIRES_APPROVAL`
   - RESIDENT: read+write internal → `ALLOW`, external → `REQUIRES_APPROVAL`
   - CITIZEN: most autonomous, delete/high-risk → `REQUIRES_APPROVAL`
   - AGENT: advisory anomalies only, near-full autonomy
   - SUSPENDED (any tier): → `DENY` immediately, no evaluation
4. Returns HTTP 200 with `{status: "ALLOW"}`, 202 with `{status: "REQUIRES_APPROVAL", approval_id: "APPR-..."}`, or 403 with `{status: "DENY"}`
5. The dashboard reads these responses. It does not set them.

**If asked:** *"Can an agent bypass the trust tier by calling the API directly?"*
> "No. The trust evaluation is in the API layer, not the UI. A direct curl to
> /v1/openclaw/{id}/evaluate_action gets the same enforcement. The trust level is fetched
> from Redis on every call — it's not in the request, the agent can't spoof it."

**If asked:** *"What stops an agent from just registering a new instance?"*
> "Registration requires a valid API key with the `agent:register` permission scope. API
> keys are admin-issued. A compromised agent can't self-register a new identity — it needs
> a human to provision credentials."

---

## 8. The Redis Tamper-Evidence Limitation — The Honest Answer

**What TelsonBase's audit chain detects:**
- Any modification to audit entry content through the TelsonBase application layer
- Missing entries (gaps in sequence numbers)
- Reordered entries
- Corruption in transit or storage (bit rot, etc.)

**What it does NOT detect:**
An attacker with direct Redis CLI access who rewrites both the entries AND recomputes all
the hashes in the correct order. This is the "privileged insider with database access"
threat model.

**Why this is not unique to TelsonBase:**
Every database-backed audit log — including the ones used in banking, healthcare, and
government — has this property. Oracle, PostgreSQL, SQL Server audit logs can all be
tampered with by a DBA with sufficient access. The standard mitigation is not to make the
DB tamper-proof but to:
1. Restrict who has direct DB access (operational security)
2. Ship logs to external append-only storage (S3 Object Lock, WORM drives)

**What TelsonBase's README should say (and does):**
The chain is an integrity layer for application-level tamper detection. For regulated
environments requiring cryptographic proof against insider threats with direct DB access,
supplement with external append-only log shipping.

**If asked:** *"This is security theater — someone with Redis access can rewrite the whole chain."*
> "Correct — and so can someone with DBA access to your Oracle database. The threat model
> for application-layer audit chains is unauthorized modification through the application,
> not privileged insiders with direct database access. That's an ops/access-control problem,
> not an audit chain problem. We document this. If you need WORM-level guarantees, ship
> to S3 Object Lock in addition. We don't pretend to be a blockchain."

---

## 9. HIPAA / HITRUST — What TelsonBase Claims and What It Doesn't

**What TelsonBase IS:**
Compliance management tooling. It helps healthcare organizations track and demonstrate
their AI governance posture across metrics relevant to HITRUST controls.

**What TelsonBase IS NOT:**
- A HITRUST-certified product
- A guarantee of HIPAA compliance
- A substitute for legal review or a compliance officer
- An attestation that any org using it is compliant with anything

**The language that matters:**
"Helps you track compliance posture" — defensible.
"HIPAA compliant" — dangerous. Never say this about TelsonBase itself.
"Supports HITRUST CSF controls related to AI agent governance" — specific and accurate.

**If asked:** *"You claim HITRUST compliance but you're not certified."*
> "TelsonBase tracks compliance posture — it doesn't certify anything. The HITRUST tab
> shows your organization's posture metrics. TelsonBase itself is not HITRUST certified
> and doesn't claim to be. It's a tool, not a certification body."

**Action item:** The dashboard's "Compliance" tab framing and the README should have a
one-line disclaimer visible without scrolling. Not buried in a LICENSE footer.

---

## 10. The AI Development Process — Your Actual Answer

**What happened:**
TelsonBase was developed collaboratively with Claude Code over an extended period. Every
architectural decision, every product requirement, every security call was made by a human.
Claude Code was the implementation tool — the same way a senior engineer uses a framework,
an IDE with autocomplete, or Stack Overflow.

**The CLAUDE.md file:**
It's in the repo. It's there intentionally. It's the project memory — the running log of
every engineering decision, every session, every accepted risk. It's more documentation
than most open source projects have.

**The dual-model verification:**
Key decisions were cross-checked against Gemini. Two independent AI models reaching the
same architectural conclusion is stronger than one. This is how serious AI-assisted
engineering should work.

**The comparison that lands:**
Salesforce engineers use GitHub Copilot. Amazon engineers use CodeWhisperer. Google uses
internal models for code review. The question isn't "did AI help?" — the question is
"does the engineer understand what was built and can they defend it?" The answer here
is yes, demonstrated by the fact that this document exists.

**If asked:** *"Did AI write this?"*
> "AI was my primary development tool. Every decision in this repo is mine — the
> architecture, the security model, the trust tier design, the audit chain approach.
> I can explain any line. The alternative framing: I built this with AI the same way
> engineers at every major company are building now. The difference is I'm honest about
> it. What specifically do you want me to walk you through?"

---

## 11. The License — Apache 2.0

**Structure:**
TelsonBase is open source under the Apache License, Version 2.0. No commercial license
required. No non-commercial restrictions. Free for any use.

**What Apache 2.0 permits:**
- Personal use, commercial use, production deployments, SaaS offerings, modified versions
- Distribution and sublicensing

**What Apache 2.0 requires:**
- Retain copyright and license notices in redistributions
- Carry notices on modified files

**If asked:** *"Why Apache 2.0 instead of AGPL?"*
> "Apache 2.0 is the right choice for infrastructure that needs to be adopted widely and
> trusted broadly. AGPL network-service provisions create friction for enterprise adopters
> even when adoption is exactly what we want. Apache 2.0 removes that friction. Revenue
> comes from services, support, and consulting — not license fees. The code is the product
> and the credibility. Broader adoption makes TelsonBase the governance standard."

---

## 12. The Scaling Question — Multi-Worker Today, More Tomorrow

**Current state:**
`WEB_CONCURRENCY=2` (default). Redis for all persistent state. PostgreSQL for relational data.
In-memory caches for read performance, populated from Redis. Audit chain uses WATCH/MULTI/EXEC.

**What the current architecture supports:**
- Multiple workers: ✓ (WATCH/MULTI/EXEC prevents race conditions)
- Graceful shutdown: ✓ (`exec gunicorn` — SIGTERM goes to PID 1, not sh)
- Horizontal instance scaling: partial — session state must move fully to Redis first

**What full horizontal scaling (multiple Docker replicas) requires:**
1. All remaining in-memory read/write paths moved to Redis exclusively
2. MQTT event handling must be idempotent (duplicate startup events across replicas)
3. Session affinity or fully stateless request routing behind a load balancer
4. External append-only audit storage for multi-instance integrity guarantees

**Startup event behavior under multiple workers:**
All N workers fire a startup audit event. Each goes through WATCH/MULTI/EXEC — they get
sequential sequence numbers. The chain remains linear. No fork.

**Honest position:**
For the governance workload TelsonBase is designed for, 2 workers with async I/O is
appropriate. `WEB_CONCURRENCY` is configurable at deploy time. Multi-replica horizontal
scaling is a post-1.0 roadmap item.

---

## Quick-Reference Card — Questions and One-Line Answers

| Question | One-liner |
|---|---|
| "Did AI write this?" | "AI was my development tool. I made every decision. Ask me anything specific." |
| "Redis isn't tamper-proof" | "Neither is Oracle. Application-layer integrity, not insider-threat WORM. We document this." |
| "Why HS256?" | "Symmetric is correct for a monolith. RS256 is for distributed token verification." |
| "Why only 2 workers?" | "WEB_CONCURRENCY is configurable. 2 is the default. WATCH/MULTI/EXEC makes any number safe." |
| "Trust enforcement is just UI?" | "Same API response whether you curl it or use the dashboard. Trust level comes from Redis." |
| "HITRUST certified?" | "TelsonBase is tooling, not a certification body. We track posture, not certify it." |
| "ecdsa removal breaks things?" | "We use HS256. ecdsa is the EC algorithm backend. 720 tests pass." |
| "This doesn't scale" | "WEB_CONCURRENCY is configurable. Audit chain is WATCH/MULTI/EXEC safe. Horizontal replicas are roadmap." |
| "Is this really open source?" | "Apache 2.0. OSI-certified. Free for any use, personal or commercial. No restrictions." |
| "Who are you?" | "The code is the credential. What specifically do you want to review?" |

---

*Last updated: Feb 25, 2026*
*Review before: GitHub drop, HN submission, any technical interview*
