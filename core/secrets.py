# TelsonBase/core/secrets.py
# REM: =======================================================================================
# REM: SECRETS PROVIDER — THE LAST LINE OF DEFENSE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v5.1.0CC: New feature - Docker secrets integration
#
# REM: Mission Statement: This module is the single point of access for ALL sensitive
# REM: configuration values. It implements a layered resolution strategy:
#
# REM:   1. Docker secrets (files at /run/secrets/) — PRODUCTION standard
# REM:   2. Environment variables — DEVELOPMENT fallback
# REM:   3. Hard error — if neither exists and the value is required
#
# REM: This eliminates plaintext .env files from production entirely. Secrets are
# REM: mounted as tmpfs-backed files by Docker, never written to disk in the container,
# REM: and never baked into images. The .env file remains useful for development but
# REM: is never the source of truth in production.
#
# REM: Threat Model Addressed:
# REM:   - .env file exposure via git commit → secrets/ dir is gitignored
# REM:   - .env readable by any process in container → /run/secrets/ is mount-restricted
# REM:   - Accidental logging of secrets → SecretValue masks repr/str
# REM:   - Default values in production → startup guard blocks launch
#
# REM: QMS Integration:
# REM:   - Startup: Secrets_Validation_Please → Secrets_Loaded_Thank_You
# REM:   - Failure: Secrets_Missing_::secret_name::_Thank_You_But_No
# REM:   - Audit: All secret access logged (without values)
# REM: =======================================================================================

import os
import logging
import warnings
from pathlib import Path
from typing import Optional, Dict, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# REM: Standard Docker secrets mount point
DOCKER_SECRETS_DIR = Path("/run/secrets")

# REM: Known insecure default values that MUST NOT be used in production
INSECURE_DEFAULTS = frozenset({
    "CHANGE_ME_IN_PRODUCTION_GENERATE_WITH_OPENSSL",
    "CHANGE_ME_IN_PRODUCTION",
    "CHANGE_ME_generate_with_openssl_rand_hex_32",
    "CHANGE_ME_secure_password",
    "secret",
    "changeme",
    "password",
    "admin",
    "test",
    "MyOpenWebUISecureKey123ABC",
    "My_Api_Key_8C7F447616D37CC656BFF2A2AC21D",
})


class SecretValue:
    """
    REM: A wrapper that prevents secrets from leaking into logs, repr, or str output.
    
    The actual value is accessible via .get() — forcing intentional access.
    Any accidental print/log/format shows '***REDACTED***' instead.
    """
    __slots__ = ('_value', '_name')

    def __init__(self, value: str, name: str = "unknown"):
        self._value = value
        self._name = name

    def get(self) -> str:
        """REM: Intentional access to the secret value."""
        return self._value

    def __str__(self) -> str:
        return "***REDACTED***"

    def __repr__(self) -> str:
        return f"SecretValue(name='{self._name}', value='***REDACTED***')"

    def __eq__(self, other) -> bool:
        if isinstance(other, SecretValue):
            return self._value == other._value
        if isinstance(other, str):
            return self._value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __len__(self) -> int:
        return len(self._value)

    def __bool__(self) -> bool:
        return bool(self._value)


@dataclass
class SecretDefinition:
    """REM: Defines a secret that the system requires."""
    name: str                           # REM: Canonical name (e.g., 'mcp_api_key')
    env_var: str                        # REM: Environment variable name (e.g., 'MCP_API_KEY')
    docker_secret_name: str             # REM: Docker secret file name (e.g., 'telsonbase_mcp_api_key')
    required: bool = True               # REM: If True, startup fails without it
    min_length: int = 32                # REM: Minimum acceptable length
    description: str = ""               # REM: Human-readable purpose


# REM: ===================================================================================
# REM: SECRET REGISTRY — Every secret the system uses, defined in one place
# REM: ===================================================================================

SECRET_REGISTRY: Dict[str, SecretDefinition] = {
    "mcp_api_key": SecretDefinition(
        name="mcp_api_key",
        env_var="MCP_API_KEY",
        docker_secret_name="telsonbase_mcp_api_key",
        required=True,
        min_length=32,
        description="Master API key for TelsonBase instance access"
    ),
    "jwt_secret_key": SecretDefinition(
        name="jwt_secret_key",
        env_var="JWT_SECRET_KEY",
        docker_secret_name="telsonbase_jwt_secret",
        required=True,
        min_length=32,
        description="HMAC key for JWT token signing (HS256)"
    ),
    "encryption_key": SecretDefinition(
        name="encryption_key",
        env_var="TELSONBASE_ENCRYPTION_KEY",
        docker_secret_name="telsonbase_encryption_key",
        required=True,
        min_length=32,
        description="Master key for AES-256-GCM encryption at rest"
    ),
    "encryption_salt": SecretDefinition(
        name="encryption_salt",
        env_var="TELSONBASE_ENCRYPTION_SALT",
        docker_secret_name="telsonbase_encryption_salt",
        required=True,
        min_length=16,
        description="Salt for PBKDF2 key derivation"
    ),
    "webui_secret_key": SecretDefinition(
        name="webui_secret_key",
        env_var="WEBUI_SECRET_KEY",
        docker_secret_name="telsonbase_webui_secret",
        required=False,
        min_length=32,
        description="Session secret for Open-WebUI"
    ),
    "grafana_admin_password": SecretDefinition(
        name="grafana_admin_password",
        env_var="GRAFANA_ADMIN_PASSWORD",
        docker_secret_name="telsonbase_grafana_password",
        required=False,
        min_length=12,
        description="Grafana admin dashboard password"
    ),
}


class SecretsProvider:
    """
    REM: Central secrets provider with layered resolution.

    Resolution order:
      1. Docker secrets file at /run/secrets/<docker_secret_name>
      2. Environment variable
      3. Hard error (if required) or None (if optional)

    Usage:
        provider = SecretsProvider()
        provider.load_all()
        api_key = provider.get("mcp_api_key")  # Returns SecretValue
        raw = api_key.get()                      # Returns actual string
    """

    def __init__(self, secrets_dir: Path = DOCKER_SECRETS_DIR):
        self._secrets_dir = secrets_dir
        self._cache: Dict[str, SecretValue] = {}
        self._sources: Dict[str, str] = {}  # REM: Track where each secret came from
        self._loaded = False
        self._is_production = os.environ.get("TELSONBASE_ENV", "development").lower() == "production"

    @property
    def is_production(self) -> bool:
        return self._is_production

    def _read_docker_secret(self, secret_name: str) -> Optional[str]:
        """REM: Read a secret from Docker secrets mount."""
        secret_path = self._secrets_dir / secret_name
        try:
            if secret_path.exists() and secret_path.is_file():
                value = secret_path.read_text().strip()
                if value:
                    return value
        except (PermissionError, OSError) as e:
            logger.warning(
                f"REM: Cannot read Docker secret ::{secret_name}:: - {e}_Thank_You_But_No"
            )
        return None

    def _read_env_var(self, env_var: str) -> Optional[str]:
        """REM: Read a secret from environment variable."""
        value = os.environ.get(env_var)
        if value and value.strip():
            return value.strip()
        return None

    def _validate_value(self, definition: SecretDefinition, value: str) -> bool:
        """REM: Validate a secret value against its definition."""
        # REM: Check for known insecure defaults
        if value in INSECURE_DEFAULTS:
            if self._is_production:
                logger.error(
                    f"REM: FATAL — Secret ::{definition.name}:: uses an insecure default "
                    f"value in PRODUCTION mode_Thank_You_But_No"
                )
                return False
            else:
                warnings.warn(
                    f"SECURITY WARNING: Secret '{definition.name}' uses an insecure default. "
                    f"Generate a proper value with: openssl rand -hex 32",
                    UserWarning,
                    stacklevel=3
                )

        # REM: Check minimum length
        if len(value) < definition.min_length:
            if self._is_production:
                logger.error(
                    f"REM: FATAL — Secret ::{definition.name}:: is too short "
                    f"({len(value)} < {definition.min_length})_Thank_You_But_No"
                )
                return False
            else:
                warnings.warn(
                    f"SECURITY WARNING: Secret '{definition.name}' is only {len(value)} chars "
                    f"(minimum: {definition.min_length}). Use: openssl rand -hex 32",
                    UserWarning,
                    stacklevel=3
                )

        return True

    def load_secret(self, name: str) -> Optional[SecretValue]:
        """
        REM: Load a single secret using the resolution chain.

        Args:
            name: Secret name from SECRET_REGISTRY

        Returns:
            SecretValue wrapping the secret, or None if not found and not required

        Raises:
            RuntimeError: If secret is required but not found (production)
        """
        definition = SECRET_REGISTRY.get(name)
        if not definition:
            raise ValueError(f"Unknown secret: '{name}'. Not in SECRET_REGISTRY.")

        # REM: Resolution Layer 1 — Docker secrets file
        value = self._read_docker_secret(definition.docker_secret_name)
        if value:
            source = "docker_secret"
            logger.debug(f"REM: Secret ::{name}:: loaded from Docker secrets_Thank_You")
        else:
            # REM: Resolution Layer 2 — Environment variable
            value = self._read_env_var(definition.env_var)
            if value:
                source = "env_var"
                if self._is_production:
                    logger.warning(
                        f"REM: Secret ::{name}:: loaded from env var (Docker secrets preferred "
                        f"in production)_Thank_You_But_No"
                    )
                else:
                    logger.debug(f"REM: Secret ::{name}:: loaded from env var_Thank_You")

        # REM: Resolution Layer 3 — Not found
        if not value:
            if definition.required:
                msg = (
                    f"REM: FATAL — Required secret ::{name}:: not found. "
                    f"Checked: /run/secrets/{definition.docker_secret_name}, "
                    f"${definition.env_var}_Thank_You_But_No"
                )
                if self._is_production:
                    logger.error(msg)
                    raise RuntimeError(msg)
                else:
                    logger.warning(
                        f"REM: Required secret ::{name}:: not found — "
                        f"set ${definition.env_var} or create Docker secret "
                        f"'{definition.docker_secret_name}'_Thank_You_But_No"
                    )
                    return None
            return None

        # REM: Validate
        if not self._validate_value(definition, value):
            if self._is_production:
                raise RuntimeError(
                    f"Secret '{name}' failed validation in production mode. "
                    f"See logs for details."
                )

        secret = SecretValue(value, name=name)
        self._cache[name] = secret
        self._sources[name] = source
        return secret

    def load_all(self) -> Dict[str, Optional[SecretValue]]:
        """
        REM: Load all registered secrets.

        Returns:
            Dict mapping secret names to SecretValue (or None if optional and missing)
        """
        results = {}
        errors = []

        logger.info("REM: Secrets_Validation_Please — Loading all registered secrets...")

        for name in SECRET_REGISTRY:
            try:
                results[name] = self.load_secret(name)
            except RuntimeError as e:
                errors.append(str(e))
                results[name] = None

        if errors:
            error_summary = "; ".join(errors)
            logger.error(
                f"REM: Secrets_Loading_Failed — {len(errors)} secret(s) failed: "
                f"{error_summary}_Thank_You_But_No"
            )
            if self._is_production:
                raise RuntimeError(
                    f"FATAL: {len(errors)} required secret(s) failed validation. "
                    f"Cannot start in production mode. See logs."
                )
        else:
            # REM: Report sources (without values)
            source_summary = {
                name: self._sources.get(name, "not_loaded")
                for name in SECRET_REGISTRY
            }
            logger.info(
                f"REM: Secrets_Loaded_Thank_You — "
                f"All secrets loaded. Sources: {source_summary}"
            )

        self._loaded = True
        return results

    def get(self, name: str) -> Optional[SecretValue]:
        """
        REM: Get a previously loaded secret.

        Returns:
            SecretValue, or loads on demand if not cached
        """
        if name in self._cache:
            return self._cache[name]
        return self.load_secret(name)

    def get_raw(self, name: str) -> Optional[str]:
        """
        REM: Get the raw string value of a secret.
        Use sparingly — prefer SecretValue wrapper.
        """
        secret = self.get(name)
        return secret.get() if secret else None

    def report_status(self) -> Dict[str, dict]:
        """
        REM: Generate a status report for all secrets (safe — no values exposed).
        Suitable for health check endpoints and audit logs.
        """
        report = {}
        for name, definition in SECRET_REGISTRY.items():
            cached = self._cache.get(name)
            report[name] = {
                "loaded": cached is not None,
                "source": self._sources.get(name, "not_loaded"),
                "required": definition.required,
                "length": len(cached) if cached else 0,
                "meets_min_length": len(cached) >= definition.min_length if cached else False,
            }
        return report


# REM: ===================================================================================
# REM: SINGLETON INSTANCE
# REM: ===================================================================================
# REM: One provider per process. Loaded during startup.

_provider_instance: Optional[SecretsProvider] = None


def get_secrets_provider() -> SecretsProvider:
    """REM: Get or create the singleton SecretsProvider."""
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = SecretsProvider()
    return _provider_instance


def init_secrets() -> SecretsProvider:
    """
    REM: Initialize secrets at application startup.
    Call this in main.py lifespan, BEFORE any other initialization.
    """
    provider = get_secrets_provider()
    provider.load_all()
    return provider


def get_secret(name: str) -> Optional[str]:
    """
    REM: Convenience function for quick secret access.
    Returns raw string value. Use in config.py field defaults.
    """
    provider = get_secrets_provider()
    return provider.get_raw(name)
