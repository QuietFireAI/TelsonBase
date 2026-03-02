# Security Policy

## TelsonBase Security Model

TelsonBase is built on zero-trust principles. Every agent message is cryptographically signed, every action requires declared capabilities, and behavioral anomalies trigger automatic quarantine.

**This is security infrastructure for AI agents.** We take vulnerabilities seriously.

---

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 4.0.2+  | :white_check_mark: (Current) |
| 4.0.x   | :white_check_mark: |
| 3.0.x   | :warning: Security updates only |
| < 3.0   | :x:                |

---

## Reporting a Vulnerability

**DO NOT** open a public GitHub issue for security vulnerabilities.

### Contact

Email: **security@telsonbase.com**

> **URGENT:** All security vulnerabilities must be reported exclusively to security@telsonbase.com. Do not open public issues or use general support channels for security disclosures.

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

Out of scope:
- Denial of service (unless trivial)
- Social engineering
- Physical access attacks
- Issues in dependencies (report upstream)

---

## Security Architecture Overview

See `docs/SECURITY_ARCHITECTURE.md` for detailed documentation of:

- Zero-trust verification chain
- Cryptographic message signing (HMAC-SHA256)
- Capability-based permission system
- Behavioral anomaly detection
- Approval gates for sensitive operations
- Egress firewall and domain whitelisting
- Federation trust protocols (RSA-4096)

### v4.0.2 Security Hardening

- **JWT Secret Validation**: Warns at startup if using insecure default secrets
- **Configurable CORS**: Lock down origins via `CORS_ORIGINS` environment variable
- **Input Validation**: Federation trust_level and expires_in_hours validated
- **Exception Handling**: Removed bare `except:` handlers that could mask errors
- **Memory Management**: Improved cleanup of replay protection caches

---

## Responsible Disclosure

We follow responsible disclosure practices:

1. Reporter contacts us privately
2. We confirm and assess the vulnerability
3. We develop and test a fix
4. We release the fix
5. We credit the reporter (unless they prefer anonymity)
6. Public disclosure after patch is available

---

## Bug Bounty

Currently no formal bug bounty program. However, significant security findings will be acknowledged in the CHANGELOG and, where appropriate, with a thank-you in project documentation.

---

## Security Updates

Security patches are announced via:
- GitHub Security Advisories
- CHANGELOG.md entries marked with `[SECURITY]`
- Email to registered security contacts (future)

---

*"Data sovereignty is security sovereignty."* — Quietfire AI
