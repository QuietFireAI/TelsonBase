# TelsonBase Environment Configuration Reference

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

---

## Overview

TelsonBase uses environment variables for configuration. Copy `.env.example` to `.env` and customize for your deployment.

```bash
cp .env.example .env
```

**Security Warning:** Never commit `.env` to version control. It contains secrets.

---

## Required Variables

These must be set for the system to start.

### MCP_API_KEY

```bash
MCP_API_KEY=your_secure_api_key_here
```

**Purpose:** Master API key for authenticating requests to the API.

**Generation:**
```bash
openssl rand -hex 32
```

**Usage:** Include in requests as `X-API-Key` header:
```bash
curl -H "X-API-Key: your_key" http://localhost:8000/v1/system/status
```

---

### JWT_SECRET_KEY

```bash
JWT_SECRET_KEY=your_jwt_secret_minimum_32_chars
```

**Purpose:** Secret key for signing JWT tokens. Used for stateless authentication.

**Requirements:**
- Minimum 32 characters
- Should be cryptographically random
- System warns at startup if using insecure defaults

**Generation:**
```bash
openssl rand -hex 32
```

**Security Note:** If this key is compromised, all issued JWTs become untrusted. Rotate immediately if leaked.

---

## Security Variables

### CORS_ORIGINS

```bash
# Development (allow all - NOT for production)
CORS_ORIGINS=["*"]

# Production (restrict to specific domains)
CORS_ORIGINS=["https://app.example.com","https://admin.example.com"]
```

**Purpose:** Controls which web origins can make cross-origin requests to the API.

**Format:** JSON array of allowed origins.

**Warning:** `["*"]` allows any website to make requests. Always restrict in production.

---

### ALLOWED_EXTERNAL_DOMAINS

```bash
ALLOWED_EXTERNAL_DOMAINS=api.anthropic.com,api.perplexity.ai,api.venice.ai
```

**Purpose:** Whitelist of external domains that agents can contact through the egress gateway.

**Format:** Comma-separated list (NOT JSON).

**Security:** This is a critical security control. Only add domains that agents legitimately need to reach. The egress gateway blocks all other outbound traffic.

**Common additions:**
```bash
# AI APIs
api.anthropic.com
api.openai.com
api.perplexity.ai

# Notification services
api.slack.com
hooks.slack.com

# Custom internal services
api.internal.yourcompany.com
```

---

### JWT_EXPIRATION_HOURS

```bash
JWT_EXPIRATION_HOURS=24
```

**Purpose:** How long JWT tokens remain valid after issuance.

**Default:** 24 hours

**Considerations:**
- Shorter = more secure (tokens expire quickly if leaked)
- Longer = more convenient (fewer re-authentications)
- For automated systems, consider longer durations with IP restrictions

---

## Encryption Variables (v4.3.0+)

### TelsonBase_ENCRYPTION_KEY

```bash
TelsonBase_ENCRYPTION_KEY=your_encryption_key_here
```

**Purpose:** Master key for encrypting sensitive data at rest in Redis.

**Generation:**
```bash
openssl rand -hex 32
```

**What's Encrypted:**
- Agent signing keys
- API keys
- Session tokens
- Private keys
- Passwords

**Critical:** If this key is lost, encrypted data cannot be recovered. Store securely (HSM, vault, or encrypted offline backup).

---

### TelsonBase_ENCRYPTION_SALT

```bash
TelsonBase_ENCRYPTION_SALT=your_salt_here
```

**Purpose:** Salt for key derivation (PBKDF2).

**Generation:**
```bash
openssl rand -hex 16
```

**Note:** Must remain constant for the lifetime of your encrypted data. Changing it invalidates all encrypted values.

---

## Infrastructure Variables

### TRAEFIK_ACME_EMAIL

```bash
TRAEFIK_ACME_EMAIL=admin@yourcompany.com
```

**Purpose:** Email for Let's Encrypt certificate notifications (expiry warnings, etc.).

**Required for:** Production deployments with automatic HTTPS.

---

### TRAEFIK_DOMAIN

```bash
TRAEFIK_DOMAIN=telsonbase.yourcompany.com
```

**Purpose:** Public domain name for the deployment.

**Requirements:**
- DNS must point to your server's IP
- Port 80/443 must be accessible for certificate validation

**Development:**
```bash
TRAEFIK_DOMAIN=localhost
```

---

### LOG_LEVEL

```bash
LOG_LEVEL=INFO
```

**Purpose:** Controls logging verbosity.

**Options:**
| Level | Description |
|-------|-------------|
| `DEBUG` | All messages, including detailed trace info |
| `INFO` | Normal operation messages (default) |
| `WARNING` | Warnings and errors only |
| `ERROR` | Errors only |
| `CRITICAL` | Critical failures only |

**Recommendation:**
- Development: `DEBUG`
- Production: `INFO` or `WARNING`

---

### AUDIT_LOG_PATH

```bash
AUDIT_LOG_PATH=/app/logs/audit.log
```

**Purpose:** Path for audit log file inside the container.

**Default:** `/app/logs/audit.log`

**Note:** Ensure the directory exists and is writable. In Docker, this path is typically inside the container; map a volume if you need persistence.

---

## Backup Variables

### BACKUP_DIR_HOST_PATH

```bash
BACKUP_DIR_HOST_PATH=./backups
```

**Purpose:** Host machine path where backups are stored.

**Mapped to:** `/app/backups` inside the container.

**Recommendation:** Use an absolute path in production:
```bash
BACKUP_DIR_HOST_PATH=/var/telsonbase/backups
```

---

### External Backup Paths (Optional)

```bash
TITAN_SECURE_AI_SNAPSHOTS_PATH=/mnt/nas/snapshots
TITAN_SECURE_AI_DYNAMIC_RECOVERY_PATH=/mnt/nas/recovery
```

**Purpose:** Paths to external storage (NAS, external drives) for off-site backup replication.

---

## Optional Service Variables

### WEBUI_SECRET_KEY

```bash
WEBUI_SECRET_KEY=your_webui_secret_here
```

**Purpose:** Secret key for Open-WebUI session management.

**Required if:** Using Open-WebUI integration.

---

### GRAFANA_ADMIN_USER / GRAFANA_ADMIN_PASSWORD

```bash
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=secure_password_here
```

**Purpose:** Credentials for Grafana monitoring dashboard.

**Required if:** Using Grafana for metrics visualization.

**Warning:** Change defaults before production deployment.

---

## Configuration Parsing in Code

Environment variables are parsed by `core/config.py` using Pydantic:

```python
from core.config import settings

# Access configuration
print(settings.mcp_api_key)
print(settings.allowed_external_domains)  # Returns list
print(settings.cors_origins)  # Returns list
```

**Type Conversions:**
| Variable | .env Format | Python Type |
|----------|-------------|-------------|
| `MCP_API_KEY` | String | `str` |
| `JWT_EXPIRATION_HOURS` | Integer | `int` |
| `ALLOWED_EXTERNAL_DOMAINS` | Comma-separated | `List[str]` |
| `CORS_ORIGINS` | JSON array | `List[str]` |
| `LOG_LEVEL` | String | `str` |

---

## Environment Examples

### Development

```bash
MCP_API_KEY=dev_test_key_12345
JWT_SECRET_KEY=dev_secret_for_local_testing_only_32chars
JWT_EXPIRATION_HOURS=168
CORS_ORIGINS=["*"]
ALLOWED_EXTERNAL_DOMAINS=api.anthropic.com,api.perplexity.ai
LOG_LEVEL=DEBUG
TRAEFIK_DOMAIN=localhost
```

### Production

```bash
MCP_API_KEY=<generated with openssl rand -hex 32>
JWT_SECRET_KEY=<generated with openssl rand -hex 32>
JWT_EXPIRATION_HOURS=24
CORS_ORIGINS=["https://app.yourcompany.com"]
ALLOWED_EXTERNAL_DOMAINS=api.anthropic.com,api.perplexity.ai
LOG_LEVEL=INFO
TRAEFIK_ACME_EMAIL=admin@yourcompany.com
TRAEFIK_DOMAIN=telsonbase.yourcompany.com
TelsonBase_ENCRYPTION_KEY=<generated with openssl rand -hex 32>
TelsonBase_ENCRYPTION_SALT=<generated with openssl rand -hex 16>
GRAFANA_ADMIN_PASSWORD=<secure password>
```

---

## Validation Errors

If you see `pydantic ValidationError` on startup, check:

1. **All required variables are set**
2. **Format is correct** (especially `CORS_ORIGINS` as JSON, `ALLOWED_EXTERNAL_DOMAINS` as comma-separated)
3. **No quotes around values** (`.env` files don't need quotes for simple strings)
4. **No trailing whitespace**

See [Troubleshooting](TROUBLESHOOTING.md) for specific error solutions.

---

*For security best practices, see [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md).*
