# TelsonBase/core/config.py
# REM: =======================================================================================
# REM: CENTRALIZED CONFIGURATION FOR THE TelsonBase
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: v7.2.0CC: Third Floor — Real Estate Agents (transaction, compliance, doc prep)
# REM: v7.1.0CC: User Console (Layer B) — operator-facing UI
# REM: v7.0.0CC: Production hardening roadmap complete (22 items)
# REM: v6.2.0CC: Secrets management hardening
# REM:   - Production validation for POSTGRES_PASSWORD, REDIS_PASSWORD, MOSQUITTO_PASSWORD
# REM:   - secrets_rotation_reminder_days setting (default 90)
# REM:
# REM: v4.2.0CC: Enhanced security features
# REM:   - Agent trust levels and promotion system
# REM:   - Secret rotation with grace periods
# REM:   - Mutual TLS for federation
# REM:   - Per-agent rate limiting
# REM:   - Capability delegation
# REM:   - Semantic action matching
# REM:   - RBAC for operators
# REM:   - Compliance export
# REM:
# REM: Mission Statement: Single source of truth for all configuration. Environment
# REM: variables are validated at startup, not scattered throughout the codebase.
# REM: =======================================================================================

# REM: Version constant for API responses and dashboard
VERSION = "9.5.0B"

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional
from functools import lru_cache
import warnings
import secrets
import os
from pathlib import Path

# REM: ===================================================================================
# REM: DOCKER SECRETS RESOLUTION — Read secrets from /run/secrets/ before env vars
# REM: ===================================================================================
# REM: This function is called in Field(default_factory=...) to resolve secrets at
# REM: Settings construction time, BEFORE Pydantic reads .env. Docker secrets take
# REM: priority over environment variables, which take priority over defaults.
# REM: ===================================================================================

DOCKER_SECRETS_DIR = Path("/run/secrets")


def _resolve_secret(docker_name: str, env_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    REM: Resolve a secret value using the layered strategy.
    Called during Settings construction.
    """
    # REM: Layer 1 — Docker secrets file
    secret_path = DOCKER_SECRETS_DIR / docker_name
    try:
        if secret_path.exists() and secret_path.is_file():
            value = secret_path.read_text().strip()
            if value:
                return value
    except (PermissionError, OSError):
        pass

    # REM: Layer 2 — Environment variable (Pydantic handles this too, but we check
    # REM: here for the default_factory path)
    value = os.environ.get(env_name)
    if value and value.strip():
        return value.strip()

    # REM: Layer 3 — Provided default (may be insecure — validated below)
    return default


class Settings(BaseSettings):
    """
    REM: Application settings loaded from Docker secrets → environment variables → defaults.
    REM: Pydantic validates these at startup - fail fast if misconfigured.
    REM:
    REM: v5.1.0CC: Docker secrets integration. Sensitive fields now resolve from
    REM: /run/secrets/ files first. Run scripts/generate_secrets.sh to bootstrap.
    """

    # --- API Security ---
    # REM: The master API key for accessing this instance. Required.
    # REM: Docker secret: telsonbase_mcp_api_key | Env: MCP_API_KEY
    mcp_api_key: str = Field(
        default_factory=lambda: _resolve_secret(
            "telsonbase_mcp_api_key", "MCP_API_KEY",
            default=None  # REM: No default — must be provided
        ) or "MISSING_API_KEY",
        env="MCP_API_KEY"
    )

    # REM: Secret key for JWT token signing.
    # REM: Docker secret: telsonbase_jwt_secret | Env: JWT_SECRET_KEY
    jwt_secret_key: str = Field(
        default_factory=lambda: _resolve_secret(
            "telsonbase_jwt_secret", "JWT_SECRET_KEY",
            default="CHANGE_ME_IN_PRODUCTION_GENERATE_WITH_OPENSSL"
        ),
        env="JWT_SECRET_KEY"
    )

    @field_validator('jwt_secret_key')
    @classmethod
    def validate_jwt_secret(cls, v):
        insecure_defaults = [
            "CHANGE_ME_IN_PRODUCTION_GENERATE_WITH_OPENSSL",
            "CHANGE_ME_IN_PRODUCTION",
            "secret",
            "changeme",
        ]
        if v in insecure_defaults or len(v) < 32:
            is_production = os.environ.get("TELSONBASE_ENV", "").lower() == "production"
            if is_production:
                raise ValueError(
                    "FATAL: JWT secret is insecure in PRODUCTION mode! "
                    "Run: scripts/generate_secrets.sh"
                )
            warnings.warn(
                "SECURITY WARNING: JWT secret is insecure! "
                "Run: scripts/generate_secrets.sh or set JWT_SECRET_KEY",
                UserWarning
            )
        return v
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(default=24, env="JWT_EXPIRATION_HOURS")
    
    # --- Database ---
    database_url: str = Field(
        default="postgresql://telsonbase:telsonbase_dev@postgres:5432/telsonbase",
        env="DATABASE_URL"
    )

    # --- Service URLs (Internal Docker Network) ---
    redis_password: str = Field(default="telsonbase_redis_dev", env="REDIS_PASSWORD")
    redis_url: str = Field(default="redis://redis:6379/0", env="REDIS_URL")

    @field_validator('redis_url')
    @classmethod
    def inject_redis_password(cls, v, info):
        """REM: Inject Redis password into URL if not already present."""
        if '@' not in v:
            password = info.data.get('redis_password', '')
            if password:
                v = v.replace('redis://', f'redis://:{password}@', 1)
        return v
    mosquitto_host: str = Field(default="mosquitto", env="MOSQUITTO_HOST")
    mosquitto_port: int = Field(default=1883, env="MOSQUITTO_PORT")
    # REM: MQTT authentication credentials (v5.2.1CC)
    # REM: Docker secret: telsonbase_mqtt_user | Env: MOSQUITTO_USER
    mosquitto_user: Optional[str] = Field(
        default_factory=lambda: _resolve_secret(
            "telsonbase_mqtt_user", "MOSQUITTO_USER", default=None
        ),
        env="MOSQUITTO_USER"
    )
    # REM: Docker secret: telsonbase_mqtt_password | Env: MOSQUITTO_PASSWORD
    mosquitto_password: Optional[str] = Field(
        default_factory=lambda: _resolve_secret(
            "telsonbase_mqtt_password", "MOSQUITTO_PASSWORD", default=None
        ),
        env="MOSQUITTO_PASSWORD"
    )
    ollama_base_url: str = Field(default="http://ollama:11434", env="OLLAMA_BASE_URL")
    
    # --- External API Whitelist ---
    # REM: CRITICAL: Only these domains can be reached by agents.
    # REM: All external calls go through the egress gateway which enforces this list.
    allowed_external_domains: List[str] = Field(
        default=[
            "api.anthropic.com",
            "api.perplexity.ai", 
            "api.venice.ai",
        ],
        env="ALLOWED_EXTERNAL_DOMAINS"
    )
    
    # --- Egress Gateway ---
    egress_gateway_url: str = Field(default="http://egress-gateway:8080", env="EGRESS_GATEWAY_URL")
    
    # --- Backup Configuration ---
    backup_dir: str = Field(default="/app/backups", env="BACKUP_DIR")
    
    # --- Logging ---
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    audit_log_path: str = Field(default="/app/logs/audit.log", env="AUDIT_LOG_PATH")
    
    # --- Traefik (for reference, used in docker-compose) ---
    traefik_acme_email: str = Field(default="", env="TRAEFIK_ACME_EMAIL")
    traefik_domain: str = Field(default="localhost", env="TRAEFIK_DOMAIN")
    
    # --- Infrastructure Settings (Added v4.0.0c - Gemini test discovery) ---
    # REM: These fields were missing, causing ValidationError when .env contained them
    backup_dir_host_path: str = Field(default="./backups", env="BACKUP_DIR_HOST_PATH")
    
    # REM: Docker secret: telsonbase_webui_secret | Env: WEBUI_SECRET_KEY
    webui_secret_key: str = Field(
        default_factory=lambda: _resolve_secret(
            "telsonbase_webui_secret", "WEBUI_SECRET_KEY",
            default="CHANGE_ME_IN_PRODUCTION"
        ),
        env="WEBUI_SECRET_KEY"
    )
    grafana_admin_user: str = Field(default="admin", env="GRAFANA_ADMIN_USER")
    
    # REM: Docker secret: telsonbase_grafana_password | Env: GRAFANA_ADMIN_PASSWORD
    grafana_admin_password: str = Field(
        default_factory=lambda: _resolve_secret(
            "telsonbase_grafana_password", "GRAFANA_ADMIN_PASSWORD",
            default="CHANGE_ME_IN_PRODUCTION"
        ),
        env="GRAFANA_ADMIN_PASSWORD"
    )

    # --- CORS Settings (Added for security hardening) ---
    # REM: v6.2.0CC: Default changed from ["*"] to localhost-only. Set CORS_ORIGINS env var to customize.
    cors_origins: List[str] = Field(default=["http://localhost:8000", "http://localhost:3000"], env="CORS_ORIGINS")

    @field_validator('cors_origins')
    @classmethod
    def validate_cors_origins(cls, v):
        if v == ["*"] or "*" in v:
            is_production = os.environ.get("TELSONBASE_ENV", "").lower() == "production"
            if is_production:
                warnings.warn(
                    "SECURITY WARNING: CORS allows all origins in PRODUCTION! "
                    "Set CORS_ORIGINS to restrict.",
                    UserWarning
                )
            else:
                warnings.warn(
                    "SECURITY WARNING: CORS allows all origins! "
                    "Set CORS_ORIGINS env var to restrict (e.g., '[\"https://app.example.com\"]')",
                    UserWarning
                )
        return v

    # --- Rate Limiting ---
    # REM: Global rate limiter settings (v6.0.0CC)
    rate_limit_per_minute: int = Field(default=300, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_burst: int = Field(default=60, env="RATE_LIMIT_BURST")

    # --- Identiclaw / MCP-I Identity Integration (v7.3.0CC) ---
    # REM: DID-based agent identity via Identiclaw. Master switch: IDENTICLAW_ENABLED.
    # REM: When disabled (default), DID auth headers are silently ignored.
    identiclaw_enabled: bool = Field(default=False, env="IDENTICLAW_ENABLED")
    identiclaw_registry_url: str = Field(
        default="https://identity.identiclaw.com",
        env="IDENTICLAW_REGISTRY_URL"
    )
    identiclaw_did_cache_ttl_hours: int = Field(default=24, env="IDENTICLAW_DID_CACHE_TTL_HOURS")
    identiclaw_vc_cache_ttl_hours: int = Field(default=12, env="IDENTICLAW_VC_CACHE_TTL_HOURS")
    identiclaw_known_issuers: List[str] = Field(
        default=["did:web:identiclaw.com"],
        env="IDENTICLAW_KNOWN_ISSUERS"
    )

    # --- OpenClaw Governance Integration (v7.4.0CC) ---
    # REM: "Control Your Claw" — governed MCP proxy for OpenClaw autonomous agents.
    # REM: When disabled (default), OpenClaw routes are not registered.
    openclaw_enabled: bool = Field(default=False, env="OPENCLAW_ENABLED")
    openclaw_default_trust_level: str = Field(default="quarantine", env="OPENCLAW_DEFAULT_TRUST")
    openclaw_auto_demote_manners_threshold: float = Field(default=0.50, env="OPENCLAW_AUTO_DEMOTE_THRESHOLD")
    openclaw_max_instances: int = Field(default=10, env="OPENCLAW_MAX_INSTANCES")
    openclaw_action_log_ttl_hours: int = Field(default=24, env="OPENCLAW_ACTION_LOG_TTL_HOURS")

    # --- Secrets Rotation Reminder (v6.2.0CC) ---
    # REM: Number of days before a rotation reminder is surfaced in the dashboard
    secrets_rotation_reminder_days: int = Field(default=90, env="SECRETS_ROTATION_REMINDER_DAYS")

    # --- Audit Chain Persistence (v6.3.0CC) ---
    # REM: Max audit chain entries persisted in Redis sorted set
    audit_max_redis_entries: int = Field(default=100000, env="AUDIT_MAX_REDIS_ENTRIES")

    # --- Environment Mode ---
    # REM: Set TELSONBASE_ENV=production to enable strict secrets validation
    telsonbase_env: str = Field(default="development", env="TELSONBASE_ENV")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # REM: Allow docker-compose vars (POSTGRES_PASSWORD, etc.) in .env


@lru_cache()
def get_settings() -> Settings:
    """
    REM: Cached settings loader. Called once at startup, reused thereafter.
    REM: The lru_cache ensures we don't re-parse environment on every request.
    """
    return Settings()


def validate_production_secrets(settings: Settings) -> list:
    """
    REM: Validate that all secrets meet production standards.
    Returns list of error messages (empty = all good).
    
    Called during startup in main.py lifespan.
    """
    errors = []
    
    insecure_values = {
        "CHANGE_ME_IN_PRODUCTION_GENERATE_WITH_OPENSSL",
        "CHANGE_ME_IN_PRODUCTION",
        "CHANGE_ME_generate_with_openssl_rand_hex_32",
        "CHANGE_ME_secure_password",
        "MISSING_API_KEY",
        "secret",
        "changeme",
    }
    
    checks = [
        ("MCP_API_KEY", settings.mcp_api_key, 32),
        ("JWT_SECRET_KEY", settings.jwt_secret_key, 32),
        ("WEBUI_SECRET_KEY", settings.webui_secret_key, 32),
        ("GRAFANA_ADMIN_PASSWORD", settings.grafana_admin_password, 12),
    ]

    for name, value, min_len in checks:
        if value in insecure_values:
            errors.append(f"{name}: uses insecure default value")
        elif len(value) < min_len:
            errors.append(f"{name}: too short ({len(value)} < {min_len})")

    # REM: v6.2.0CC — Infrastructure password checks for production
    # REM: Extract PostgreSQL password from DATABASE_URL
    db_url = settings.database_url or ""
    if "telsonbase_dev" in db_url:
        errors.append(
            "POSTGRES_PASSWORD: must not be 'telsonbase_dev' in production — "
            "run scripts/generate_secrets.sh and update DATABASE_URL"
        )

    # REM: Redis password must not be the dev default
    if settings.redis_password == "telsonbase_redis_dev":
        errors.append(
            "REDIS_PASSWORD: must not be 'telsonbase_redis_dev' in production — "
            "run scripts/generate_secrets.sh and set REDIS_PASSWORD"
        )

    # REM: MQTT password must not contain 'dev'
    mqtt_pw = settings.mosquitto_password or ""
    if "dev" in mqtt_pw.lower():
        errors.append(
            "MOSQUITTO_PASSWORD: must not contain 'dev' in production — "
            "run scripts/generate_secrets.sh and set MOSQUITTO_PASSWORD"
        )

    return errors
