# ClawCoat - Security Policy
**Version:** v11.0.1 · **Maintainer:** Quietfire AI - security@clawcoat.com

TelsonBase is built on zero-trust principles. Every agent message is cryptographically signed, every action requires declared capabilities, and behavioral anomalies trigger automatic quarantine.

**This is security infrastructure for AI agents.** We take vulnerabilities seriously.

---

## Supported Versions

| Version | Supported |
|---|---|
| **v11.0.1** (Current) | ✅ Active - full support |
| v10.0.0Bminus | ✅ Security updates only |
| < v10.0.0Bminus | ❌ Not supported |

---

## Reporting a Vulnerability

**DO NOT** open a public GitHub issue for security vulnerabilities.

### Contact

Email: **security@clawcoat.com**

> **URGENT:** All security vulnerabilities must be reported exclusively to security@clawcoat.com. Do not open public issues or use general support channels for security disclosures.

Include:
1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact assessment
4. Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Resolution Timeline**: Depends on severity
 - Critical: 24-72 hours
 - High: 7 days
 - Medium: 30 days
 - Low: Next release

### Scope

In-scope vulnerabilities:
- Authentication/authorization bypass
- Cryptographic signature forgery or bypass
- Capability escalation
- Agent quarantine escape
- Egress gateway bypass
- SQL/NoSQL injection
- Remote code execution
- Data exfiltration paths
- Trust tier bypass or privilege escalation
- QMS™ validation bypass in the Foreman agent

Out of scope:
- Denial of service (unless trivially reproducible)
- Social engineering
- Physical access attacks
- Issues in dependencies (report upstream)

---

## Security Architecture Overview

TelsonBase's security model is documented across the following sources. There is no single architecture document - the architecture is verified through proof sheets and explained through the technical reference.

| Document | What It Covers |
|---|---|
| `docs/System Documents/AUDIT_TRAIL.md` | Hash-chained audit trail: entry structure, storage architecture, API, real-time stream, verification, offline verification |
| `docs/System Documents/TOOLROOM_TRUST_MATRIX.md` | Tool access control: `min_trust_level`, `requires_api_access` HITL gate, designation by category |
| `docs/FAQ.md` | 8-step governance pipeline, Manners compliance, trust promotion, egress control |
| `proof_sheets/INDEX.md` | 788 proof documents - every security claim traced to source code and a verification command |

**Security-specific proof sheets:**

| Sheet | Claim |
|---|---|
| `TB-PROOF-009` | SHA-256 hash-chained audit trail |
| `TB-PROOF-013` | Cryptographic message signing (HMAC-SHA256) |
| `TB-PROOF-019` | Human-in-the-loop approval gates |
| `TB-PROOF-020` | Behavioral anomaly detection |
| `TB-PROOF-027` | Static analysis - 0 high-severity findings |
| `TB-PROOF-028` | Zero data leaves the network |
| `TB-PROOF-035` | OpenClaw 8-step governance pipeline |
| `TB-PROOF-037` | Kill switch - instant agent suspension |
| `TB-PROOF-038` | Manners auto-demotion |
| `TB-PROOF-043` | Authentication security battery |
| `TB-PROOF-044` | Encryption integrity battery |
| `TB-PROOF-045` | Access control battery |
| `TB-PROOF-046` | Audit trail integrity battery |
| `TB-PROOF-047` | Network security battery |

---

## v11.0.1 Security Posture

Current verified security status as of March 8, 2026:

- **720 tests passing** - 0 failures, 1 expected skip (Alembic idempotency test, requires live DB)
- **96 dedicated security tests** - authentication, encryption, access control, audit trail, network, data protection, compliance, cryptography, runtime boundaries
- **Bandit static analysis** - 0 high-severity findings across 37,921 lines of source code
- **Server errors under fuzzing** - 657 reduced to 0 across hardening sessions
- **QMS™ validation as security gate** - non-QMS messages to the Foreman are discarded and logged as `NON_QMS_MESSAGE` anomaly events; never processed
- **8-step governance pipeline** - every agent action evaluated on all 8 steps with no bypass path
- **AGENT apex tier** - 99.9% success rate, zero anomaly tolerance, re-verification every 3 days; anomalies at this tier are advisory, not gating
- **Hash-chained audit trail** - Redis WATCH/MULTI/EXEC; race-free under any worker count
- **Manners auto-demotion** - agents dropping below 50% behavioral compliance score are demoted to QUARANTINE automatically, no human delay
- **CAPTCHA replay protection** - challenges consumed on first redemption, preventing automation bypass
- **Secret isolation** - all secrets in Docker secrets files, never in environment variables, never in container layers

---

## Responsible Disclosure

We follow responsible disclosure practices:

1. Reporter contacts us privately at security@clawcoat.com
2. We confirm and assess the vulnerability within 7 days
3. We develop and test a fix
4. We release the fix
5. We credit the reporter (unless they prefer anonymity)
6. Public disclosure after patch is available

---

## Bug Bounty

No formal bug bounty program currently. Significant security findings will be acknowledged in the CHANGELOG and, where appropriate, with a thank-you in project documentation.

---

## Security Updates

Security patches are announced via:
- GitHub Security Advisories
- CHANGELOG.md entries marked with `[SECURITY]`
- Email to registered security contacts

---

*"Data sovereignty is security sovereignty."* - Quietfire AI

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
