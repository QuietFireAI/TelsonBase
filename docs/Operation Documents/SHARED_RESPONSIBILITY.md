# TelsonBase — Shared Responsibility Matrix

# REM: =======================================================================================
# REM: SHARED RESPONSIBILITY MATRIX
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: AI Model Collaborators: Claude Opus 4.6
# REM: Date: February 23, 2026
# REM: =======================================================================================

## Model Overview

TelsonBase is self-hosted software deployed on customer-controlled infrastructure via Docker Compose. As with all self-hosted platforms, security responsibility is shared: TelsonBase is responsible for the security of the software -- application logic, cryptographic controls, access management, and audit mechanisms -- while the customer is responsible for the security of the environment -- hardware, network, operating system, certificates, and operational procedures. Neither party can achieve a complete security posture independently; both must fulfill their respective obligations.

---

## Responsibility Matrix

| Security Domain | TelsonBase (Software) | Customer (Infrastructure) |
|---|---|---|
| **Application Security** | RBAC enforcement on all 140+ endpoints, MFA (TOTP + backup codes), session management with HIPAA idle timeouts, input validation and error sanitization | Manage user accounts and role assignments, enforce least-privilege access policies |
| **Data Encryption (Transit)** | TLS termination via Traefik, automatic HTTP-to-HTTPS redirect, HSTS headers (1 year, includeSubdomains, preload), security headers middleware | Obtain and renew TLS certificates, configure DNS records, maintain certificate lifecycle |
| **Data Encryption (Rest)** | Fernet encryption (AES-128-CBC + HMAC-SHA256) for secrets in Redis, AES-256-GCM for sensitive fields, bcrypt (12 rounds) for passwords | Enable volume-level encryption on all storage (LUKS on Linux, BitLocker on Windows, FileVault on macOS) |
| **Authentication** | JWT tokens (HS256), API key management, MFA via TOTP with encrypted secret storage, account lockout (5 attempts / 15 min), password strength enforcement (12+ chars, mixed) | Enforce MFA enrollment policy for all users, manage credential distribution, revoke access for departed staff |
| **Audit & Logging** | Cryptographic audit chain (SHA-256 hash-linked, Redis-persisted), structured JSON logging, tamper-evident chain integrity verification | Retain logs per organizational policy, forward to SIEM, monitor alerts, preserve logs for litigation holds |
| **Network Security** | Docker network isolation between services, per-tenant rate limiting (Redis sliding window), per-user request limits, IP-based throttling | Configure host firewall rules, deploy VPN for remote access, implement network segmentation, restrict inbound ports |
| **Backup & Recovery** | Automated backup scripts (Redis BGSAVE + pg_dump + secrets archive), restore scripts with integrity verification, RPO 24hr / RTO 15min targets | Schedule backup execution (cron/Task Scheduler), test disaster recovery regularly, store backups offsite or in secondary location |
| **Physical Security** | N/A | Secure server hardware, restrict data center or server room access, maintain physical access logs, protect against theft and environmental hazards |
| **Patch Management** | Release security updates and version patches, document CVE remediations in changelogs | Apply TelsonBase updates promptly, monitor dependency CVEs, keep host OS and Docker runtime current |
| **Compliance** | Compliance modules (legal hold, breach notification, data retention, sanctions screening, BAA tracking, HITRUST controls, PHI handling), SOC 2 Type I documentation, audit controls mapped to 51 controls across 5 Trust Service Criteria | Obtain required certifications (SOC 2, HIPAA, CJIS), conduct risk assessments, maintain written security policies, complete staff training |
| **Availability** | Docker health checks on all services, automatic container restart policies, Prometheus alerting (ServiceDown, HighErrorRate, HighLatency), Grafana dashboards | Provide redundant hardware, uninterruptible power supply (UPS), high-availability infrastructure (Swarm/K8s), geographic redundancy if required |
| **Incident Response** | Breach notification module with configurable timelines, anomaly detection, authentication failure spike alerts, audit chain integrity monitoring | Maintain and execute incident response plan, notify regulators and affected parties per legal requirements, conduct post-incident review |

---

## Key Principle

**TelsonBase secures the software. The customer secures the environment.**

---

## References

- [Encryption at Rest Guide](ENCRYPTION_AT_REST.md) -- Volume encryption guidance, application-level cryptography, compliance mapping
- [Backup & Recovery Guide](BACKUP_RECOVERY.md) -- Backup scripts, restore procedures, RPO/RTO targets
- [Deployment Guide](DEPLOYMENT_GUIDE.md) -- Installation, configuration, Docker Compose setup (forthcoming)
- [SOC 2 Type I Documentation](SOC2_TYPE_I.md) -- 51 controls, Trust Service Criteria, Complementary User Entity Controls
