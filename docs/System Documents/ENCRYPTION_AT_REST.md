# TelsonBase — Encryption at Rest Guide

# REM: =======================================================================================
# REM: ENCRYPTION AT REST FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: AI Model Collaborators: Claude Opus 4.6
# REM: Date: February 23, 2026
# REM: =======================================================================================

## Overview

This document describes the encryption-at-rest posture of TelsonBase, a zero-trust AI agent security platform deployed on customer premises via Docker Compose. It covers what is encrypted today at the application level, what options exist for encrypting the underlying storage (PostgreSQL 16, Redis), and what steps customers must take to achieve full encryption at rest on their deployment hardware (Drobo, NAS, or other self-hosted infrastructure).

This guide is intended for law firm IT administrators, managed service providers (MSPs), and compliance officers responsible for the physical deployment environment.

---

## Current State: What Is Encrypted Today

TelsonBase provides several layers of application-level cryptographic protection out of the box. These operate independently of any volume or disk encryption the customer may configure.

| Data | Protection | Mechanism | Reversible? |
|------|-----------|-----------|-------------|
| MFA secrets in Redis | Symmetric encryption | Fernet (AES-128-CBC + HMAC-SHA256) via `SecureRedisStore` | Yes (with key) |
| Sensitive Redis fields | Symmetric encryption | AES-256-GCM via `SecureStorageManager` (PBKDF2-derived key) | Yes (with key) |
| User passwords | One-way hash | bcrypt, 12 rounds | No |
| JWT tokens | Signed | HMAC-SHA256 (`HS256`) | N/A (integrity, not confidentiality) |
| Audit chain entries | Hash-linked | SHA-256 chaining (tamper-evident) | N/A (integrity, not confidentiality) |
| Data in transit | TLS termination | Traefik reverse proxy, HTTPS with Let's Encrypt | N/A |
| Inter-agent messages | Signed | HMAC-SHA256 per-message signatures | N/A |
| Federation payloads | Encrypted + signed | AES-256-GCM session keys, RSA-4096 identity keys | Yes (with key) |

**Key point:** Application-level encryption protects specific sensitive fields (MFA secrets, signing keys, API keys). It does not encrypt the entire database or all data written to disk. General application data stored in PostgreSQL and Redis is written to Docker volumes in plaintext unless the customer enables volume-level encryption.

**Implementation references:**
- `core/secure_storage.py` -- AES-256-GCM encryption for Redis fields
- `core/auth.py` -- bcrypt password hashing, JWT signing
- `core/signing.py` -- HMAC-SHA256 message signing
- `core/audit.py` -- SHA-256 hash-chained audit entries

---

## PostgreSQL Encryption Options

PostgreSQL 16 stores data in Docker volumes mounted from the host filesystem. Three approaches exist for encrypting this data at rest.

### Option A: Volume-Level Encryption (Recommended)

Encrypt the host filesystem or block device that backs the PostgreSQL Docker volume.

| Platform | Technology | Command Example |
|----------|-----------|----------------|
| Linux | LUKS / dm-crypt | `cryptsetup luksFormat /dev/sdX` |
| Windows | BitLocker | Enable via Control Panel or `manage-bde` |
| macOS | FileVault | Enable via System Preferences |
| Synology NAS | Shared Folder Encryption | Enable per shared folder in DSM |
| QNAP NAS | Volume Encryption | Enable during volume creation |
| Drobo | Varies by model | Consult Drobo documentation |

**Pros:**
- Transparent to PostgreSQL -- no application or configuration changes required
- Encrypts everything: tables, indexes, WAL files, temp files, pg_stat
- Well-tested, OS-level implementation with hardware acceleration (AES-NI)
- No performance penalty on modern hardware (typically under 3%)
- Works with existing backup and restore procedures

**Cons:**
- Data is decrypted while the volume is mounted and the system is running
- Does not protect against a compromised application or SQL injection reading data in memory
- Requires customer action -- TelsonBase cannot enable this for you
- Key management is the customer's responsibility

**This is the recommended approach for all TelsonBase deployments.**

### Option B: Column-Level Encryption (pgcrypto)

Use the PostgreSQL `pgcrypto` extension to encrypt specific columns containing sensitive data.

```sql
-- Enable the extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Encrypt a value
INSERT INTO sensitive_data (field)
VALUES (pgp_sym_encrypt('secret_value', 'encryption_key'));

-- Decrypt a value
SELECT pgp_sym_decrypt(field, 'encryption_key') FROM sensitive_data;
```

**Pros:**
- Granular: encrypt only PHI, PII, or other regulated fields
- Data remains encrypted even if the database process is compromised (attacker needs the key)
- Can satisfy compliance requirements for field-level encryption (HIPAA, CJIS)
- No OS-level changes required

**Cons:**
- Requires application code changes for every encrypted field
- Encrypted columns cannot be indexed or searched efficiently
- Key must be passed to the database at query time (key management complexity)
- Does not encrypt WAL, temp files, or indexes
- Performance overhead on encrypt/decrypt operations

**Use this as a supplementary measure for specific high-sensitivity fields, not as a primary encryption strategy.**

### Option C: Transparent Data Encryption (TDE)

PostgreSQL 16 and later have community-contributed TDE patches that encrypt entire tablespaces transparently.

**Pros:**
- Transparent to the application (no code changes)
- Encrypts tablespace data files, including indexes
- More granular than volume-level (can encrypt specific tablespaces)

**Cons:**
- Not part of core PostgreSQL -- requires patched builds or specific distributions
- Not available in the standard `postgres:16` Docker image used by TelsonBase
- WAL encryption support varies by implementation
- Less mature than volume-level encryption
- Adds operational complexity (custom Docker image, key management daemon)

**Not recommended for TelsonBase at this time.** Volume-level encryption (Option A) provides equivalent protection with less complexity. Revisit if TDE becomes part of core PostgreSQL in a future release.

---

## Redis Encryption at Rest

Redis stores all data in memory and periodically writes snapshots (RDB) and append-only files (AOF) to disk. Redis does not natively encrypt data at rest on disk.

### Current Protections

| Protection | Status |
|-----------|--------|
| `requirepass` authentication | Enforced via `redis.conf` and Docker secrets |
| Network isolation | Redis runs on the internal `data` Docker network (`internal: true`) |
| Application-level encryption | MFA secrets and sensitive fields are Fernet/AES-256-GCM encrypted before storage |
| TLS for Redis connections | Available, configurable (defense in depth) |

### Recommendation

1. **Run Redis on an encrypted volume** (same approach as PostgreSQL -- see Option A above). This encrypts RDB snapshots and AOF files on disk.
2. **Continue relying on application-level encryption** for sensitive fields. The `SecureRedisStore` and `SecureStorageManager` classes already encrypt MFA secrets, signing keys, API keys, tokens, passwords, private keys, and session keys before they reach Redis. Even if the Redis volume were accessed by an attacker, these fields are ciphertext.
3. **Do not store plaintext secrets in Redis.** Any new sensitive data types added to TelsonBase must use `SecureStorageManager` for encryption before storage.

---

## Recommended Implementation for TelsonBase Customers

### Primary: Volume-Level Encryption

Enable full-disk or full-volume encryption on every host or NAS device that stores TelsonBase Docker volumes. This covers:

- PostgreSQL data volume (`telsonbase_postgres_data`)
- Redis data volume (`telsonbase_redis_data`)
- Backup volumes (`./backups/`)
- Secrets directory (`./secrets/`)
- Let's Encrypt certificates (`letsencrypt_data`)

### Supplementary: Application-Level Encryption (pgcrypto)

If your compliance framework requires field-level encryption (for example, HIPAA for PHI or CJIS for criminal justice data), use `pgcrypto` for specific PostgreSQL columns:

- Patient health information (PHI)
- Social Security numbers or government identifiers
- Financial account numbers
- MFA secrets (if migrated from Redis to PostgreSQL in a future release)

This is in addition to, not a replacement for, volume-level encryption.

### Key Management

Encryption is only as strong as key management. Follow these principles:

1. **Separate keys from data.** The volume encryption key (or key protector) must not be stored on the same volume it encrypts.
2. **Back up encryption keys offline.** Store recovery keys on a separate physical device (USB drive in a safe, printed recovery key in a sealed envelope).
3. **Document the key location.** Your disaster recovery runbook must include where encryption keys are stored and who has access.
4. **For LUKS:** Back up the LUKS header separately: `cryptsetup luksHeaderBackup /dev/sdX --header-backup-file luks-header.bak`
5. **For BitLocker:** Save the recovery key to Active Directory, Azure AD, or a printed copy. Do not store it only on the encrypted drive.
6. **For NAS devices:** Follow the manufacturer's key escrow or recovery key procedures. Losing the key means losing the data.

---

## Implementation Checklist

Use this checklist during initial deployment or when hardening an existing installation.

### Volume Encryption

- [ ] Enable volume encryption on the host/NAS volume backing PostgreSQL data
- [ ] Enable volume encryption on the host/NAS volume backing Redis data
- [ ] Enable volume encryption on the host/NAS volume backing `./backups/`
- [ ] Enable volume encryption on the host/NAS volume backing `./secrets/`
- [ ] Verify encryption is active: confirm the volume is reported as encrypted by the OS or NAS management interface

### Application-Level Encryption

- [ ] Verify MFA secrets are Fernet-encrypted in Redis (check `SecureRedisStore` usage in application logs)
- [ ] Verify sensitive Redis fields are AES-256-GCM encrypted via `SecureStorageManager`
- [ ] Verify password hashes use bcrypt (not reversible encryption) -- check `core/auth.py`
- [ ] Verify `TELSONBASE_ENCRYPTION_KEY` and `TELSONBASE_ENCRYPTION_SALT` are set via Docker secrets (not hardcoded defaults)

### Network and Transport Encryption

- [ ] Verify TLS is active on the Traefik reverse proxy (HTTPS for all external traffic)
- [ ] Configure PostgreSQL `ssl = on` for inter-container connections (optional, defense in depth)
- [ ] Configure Redis TLS for inter-container connections (optional, defense in depth)

### Key Management and Recovery

- [ ] Document the encryption key backup procedure for your volume encryption method
- [ ] Store volume encryption recovery keys in a separate, secure location
- [ ] Store TelsonBase application encryption keys (`./secrets/`) on encrypted media, separate from data
- [ ] Test backup and restore with encrypted volumes -- confirm backups can be restored on a new system
- [ ] Test disaster recovery -- confirm the system can be rebuilt from backups with encryption keys

### Ongoing Operations

- [ ] Include encryption key recovery in the disaster recovery runbook
- [ ] Schedule periodic verification that volume encryption remains enabled
- [ ] Rotate `TELSONBASE_ENCRYPTION_KEY` per your compliance schedule (see `SECRETS_MANAGEMENT.md`)
- [ ] Audit access to encryption keys and recovery keys

---

## Shared Responsibility Model

TelsonBase encryption at rest follows a shared responsibility model between the platform and the customer.

### TelsonBase Provides (Application Level)

| Responsibility | Implementation |
|---------------|----------------|
| Encrypt MFA secrets before storage | `SecureRedisStore` (Fernet) |
| Encrypt sensitive Redis fields before storage | `SecureStorageManager` (AES-256-GCM, PBKDF2) |
| Hash passwords irreversibly | bcrypt, 12 rounds |
| Sign JWT tokens | HMAC-SHA256 |
| Chain audit entries cryptographically | SHA-256 hash linking |
| Encrypt federation payloads | AES-256-GCM with RSA-4096 key exchange |
| Provide TLS termination configuration | Traefik with Let's Encrypt |
| Warn on insecure defaults | Startup warnings for default keys |

### Customer Provides (Infrastructure Level)

| Responsibility | Action Required |
|---------------|-----------------|
| Volume/disk encryption | Enable LUKS, BitLocker, FileVault, or NAS encryption on all data volumes |
| Encryption key management | Store and back up volume encryption keys separately from data |
| Physical security | Secure the hardware running TelsonBase (locked server room, restricted access) |
| Backup encryption | Ensure backups are stored on encrypted media or encrypted before transfer |
| Network security | Firewall rules, VPN access, restrict management ports |
| Compliance documentation | Maintain records of encryption status for auditors |

**TelsonBase cannot enable volume-level encryption on your behalf.** This is an infrastructure decision that depends on your operating system, hardware, and compliance requirements. TelsonBase provides the application-level encryption layer; the customer provides the infrastructure-level encryption layer.

---

## Compliance Relevance

| Framework | Encryption at Rest Requirement | How TelsonBase + Volume Encryption Satisfies |
|-----------|-------------------------------|----------------------------------------------|
| HIPAA (164.312(a)(2)(iv)) | Encryption of ePHI at rest | Volume encryption for all data; pgcrypto for PHI columns |
| CJIS Security Policy (5.10.1.2) | Encryption of CJI at rest | Volume encryption; application-level encryption for sensitive fields |
| SOC 2 (CC6.1, CC6.7) | Logical and physical access controls including encryption | Volume encryption + application-level field encryption |
| PCI DSS (Req 3.4) | Render PAN unreadable wherever stored | pgcrypto for cardholder data columns; volume encryption |
| GDPR (Art. 32) | Appropriate technical measures including encryption | Volume encryption + application-level encryption |

For detailed compliance documentation, see [LEGAL_COMPLIANCE.md](LEGAL_COMPLIANCE.md) and [HEALTHCARE_COMPLIANCE.md](HEALTHCARE_COMPLIANCE.md).

---

## Related Documents

- [Security Architecture](SECURITY_ARCHITECTURE.md) -- Full security layer overview including Layer 9 (Encryption at Rest)
- [Secrets Management](SECRETS_MANAGEMENT.md) -- How encryption keys and other secrets are stored and rotated
- [Backup and Recovery](BACKUP_RECOVERY.md) -- Backup procedures (must work with encrypted volumes)
- [Disaster Recovery](DISASTER_RECOVERY.md) -- Recovery procedures including key recovery
- [Legal Compliance](LEGAL_COMPLIANCE.md) -- Regulatory compliance mapping
- [Healthcare Compliance](HEALTHCARE_COMPLIANCE.md) -- HIPAA-specific guidance
