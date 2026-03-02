# TelsonBase — Secrets Management Guide
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM: v6.2.0CC: Secrets management documentation
# REM: =======================================================================================

## Secrets Inventory

| Secret File                     | Purpose                                  |
|---------------------------------|------------------------------------------|
| `telsonbase_mcp_api_key`        | Master API key for MCP server access     |
| `telsonbase_jwt_secret`         | JWT token signing key (HS256)            |
| `telsonbase_encryption_key`     | AES-256-GCM master encryption key        |
| `telsonbase_encryption_salt`    | PBKDF2 key derivation salt               |
| `telsonbase_webui_secret`       | Open-WebUI session signing secret        |
| `telsonbase_grafana_password`   | Grafana admin dashboard password         |
| `telsonbase_postgres_password`  | PostgreSQL database authentication       |
| `telsonbase_redis_password`     | Redis server authentication password     |
| `telsonbase_mqtt_password`      | Mosquitto MQTT broker password           |

## How Secrets Are Loaded

TelsonBase uses a three-layer resolution strategy (see `core/config.py`):

1. **Docker secrets** (`/run/secrets/<name>`) — highest priority, production path
2. **Environment variables** (from `.env` or shell) — development convenience
3. **Hardcoded defaults** — insecure, triggers warnings; blocked in production

Docker Compose mounts files from `./secrets/` into containers at `/run/secrets/`.
These files are never baked into images and never written to container disk layers.

## Generating Secrets

```bash
chmod +x scripts/generate_secrets.sh
./scripts/generate_secrets.sh
```

This creates the `./secrets/` directory with one file per secret, each with
mode 600 (owner-read/write only) inside a mode 700 directory.

## Rotation Procedure

1. Back up the current `./secrets/` directory
2. Run: `./scripts/generate_secrets.sh --rotate`
3. Type `ROTATE` when prompted to confirm
4. Restart the full stack: `docker-compose down && docker-compose up -d --build`
5. Verify services are healthy: `docker-compose ps`
6. Update any external integrations that reference rotated keys

The `--rotate` flag forces regeneration of ALL secrets. All existing sessions,
JWT tokens, and cached credentials will be invalidated.

## Verification Without Changes

```bash
./scripts/generate_secrets.sh --check
```

This verifies that all expected secret files exist, are non-empty, and have
correct file permissions. No secrets are generated or modified.

## Docker Secrets vs .env File

| Aspect              | Docker Secrets (`./secrets/`)       | `.env` File                        |
|---------------------|-------------------------------------|------------------------------------|
| Visibility          | Not in `docker inspect`             | Visible in `docker inspect`        |
| Storage             | tmpfs mount at `/run/secrets/`      | Process environment                |
| Use for             | Passwords, API keys, signing keys   | Domains, log levels, feature flags |
| Commit to git?      | NEVER                               | OK (no real secrets in it)         |

## What to Back Up

- `./secrets/` directory — back up to Drobo NAS or AWS Snowball device
- `./backups/` directory — application data backups
- `acme.json` (Let's Encrypt certificates) — stored in the `letsencrypt_data` volume

## What to NEVER Commit

- `./secrets/` — must be in `.gitignore`
- Any file containing raw passwords or API keys
- `acme.json` — contains private TLS keys

## Rotation Reminder

The `SECRETS_ROTATION_REMINDER_DAYS` setting (default: 90) controls how often
the system surfaces a rotation reminder. Set this in `.env` or as an
environment variable to adjust the interval for your compliance requirements.
