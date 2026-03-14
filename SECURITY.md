# ClawCoat - Security Policy

**Version:** v11.0.1 · **Maintainer:** Quietfire AI - security@clawcoat.com

## Supported Versions

| Version | Supported |
|---|---|
| **v11.0.1** (Current) | ✅ Active - full support |
| v10.0.0Bminus | ✅ Security updates only |
| < v10.0.0Bminus | ❌ Not supported |

Only the latest minor release receives security patches. Upgrade to the current version before reporting.

---

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

### Disclosure Process

1. **Email:** Send details to **security@clawcoat.com** with subject line `[SECURITY] TelsonBase - <brief description>`

   > **URGENT:** Security vulnerabilities must be reported to security@clawcoat.com only. Do not use general support channels for security disclosures.
2. **Include:**
  - Description of the vulnerability
  - Steps to reproduce (or proof of concept)
  - Affected version(s)
  - Impact assessment (what an attacker could do)
  - Suggested fix (if you have one)
3. **Response timeline:**
  - Acknowledgment within **48 hours**
  - Initial assessment within **5 business days**
  - Fix target within **14 days** for critical, **30 days** for high severity
4. **Coordinated disclosure:** We request 90 days before public disclosure to allow time for a patch. We will credit reporters in the release notes unless anonymity is requested.

### What Qualifies

- Authentication or authorization bypass
- Remote code execution
- SQL injection, command injection, SSRF
- Credential exposure or secret leakage
- Privilege escalation between trust levels
- Cryptographic weaknesses (signature bypass, key exposure)
- Cross-site scripting (XSS) in the dashboard
- Container escape or network segmentation bypass

### What Does NOT Qualify

- Denial of service via rate limiting (rate limiter is working as designed)
- Self-XSS (requires victim to paste code into their own console)
- Missing security headers on `/health` endpoint (public by design)
- Vulnerabilities in dependencies without a demonstrated exploit path against TelsonBase
- Social engineering attacks

---

## Security Architecture

TelsonBase is built on a zero-trust model. See [docs/System Documents/SECURITY_ARCHITECTURE.md](docs/System%20Documents/SECURITY_ARCHITECTURE.md) for the full design.

### Key Security Controls

| Layer | Control | Implementation |
|---|---|---|
| **Authentication** | Three methods | API key (X-API-Key), JWT (Bearer), DID signature (X-DID-Auth) |
| **Authorization** | Role-based + capability-based | RBAC with 4 roles, per-agent capability enforcement |
| **Network** | Five-tier segmentation | `data` and `ai` networks are `internal: true` (no external access) |
| **Secrets** | Docker secrets + env layering | Secrets resolved from `/run/secrets/` first, then env vars |
| **Audit** | Immutable hash chain | Every state change logged with SHA-256 chain integrity |
| **Egress** | Domain whitelist | External API calls restricted to approved domains |
| **Agent Trust** | Five-tier progression | Quarantine → Probation → Resident → Citizen → Agent |
| **Approval Gates** | Human-in-the-loop | High-risk actions require explicit approval before execution |
| **Rate Limiting** | Per-tenant Redis-backed | Configurable requests/minute with burst allowance |
| **Kill Switch** | Instant agent revocation | Redis-persisted, checked before any crypto verification |
| **Encryption** | At rest + in transit | AES-GCM for stored data, TLS for all network traffic |
| **MFA** | TOTP (RFC 6238) | Optional per-user multi-factor authentication |

### Container Security

- All containers run as **non-root users** (UID 1000)
- Base images are **slim variants** (reduced attack surface)
- Dependencies are **pinned to exact versions** (reproducible builds)
- Health checks on **every service** (automatic restart on failure)
- Resource limits enforce **CPU and memory bounds** per container
- Docker socket mounted **read-only** to Traefik (required for service discovery)

### Cryptographic Primitives

| Purpose | Algorithm | Library |
|---|---|---|
| JWT signing | HMAC-SHA256 | python-jose |
| Password hashing | bcrypt (cost 12) | bcrypt (direct) |
| Federation trust | RSA-4096 + PSS padding | cryptography |
| DID verification | Ed25519 | cryptography |
| Audit chain | SHA-256 | hashlib (stdlib) |
| Encryption at rest | AES-256-GCM | cryptography |
| Secret generation | CSPRNG | `openssl rand -hex 32` |

---

## Hardening Checklist

Before deploying TelsonBase in production:

- [ ] Run `scripts/generate_secrets.sh` to create fresh cryptographic secrets
- [ ] Set `TELSONBASE_ENV=production` in `.env` (enables strict validation)
- [ ] Change all default passwords (Postgres, Redis, MQTT, Grafana)
- [ ] Replace `MCP_API_KEY` and `JWT_SECRET_KEY` with 32+ byte random hex values
- [ ] Configure `CORS_ORIGINS` to your specific domains (not `["*"]`)
- [ ] Set `TRAEFIK_ACME_EMAIL` to a real email for Let's Encrypt certificates
- [ ] Ensure `data`, `ai`, and `monitoring` Docker networks remain `internal: true`
- [ ] Review `ALLOWED_EXTERNAL_DOMAINS` egress whitelist
- [ ] Enable MFA for all admin accounts
- [ ] Set `RATE_LIMIT_PER_MINUTE` appropriate to your usage
- [ ] Run `docker compose exec mcp_server python -m pytest tests/ -v` to verify all tests pass
- [ ] Review agent trust levels - new agents should start at `quarantine`

---

## Dependencies

TelsonBase monitors dependencies for known vulnerabilities. See [licenses/THIRD_PARTY_NOTICES.md](licenses/THIRD_PARTY_NOTICES.md) for the complete dependency inventory.

We recommend enabling [GitHub Dependabot](https://docs.github.com/en/code-security/dependabot) on your fork for automated security updates.

---

## Bug Bounty

TelsonBase does not currently operate a paid bug bounty program. Security researchers who report valid vulnerabilities will be credited in release notes and the CONTRIBUTORS section of the repository.

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
