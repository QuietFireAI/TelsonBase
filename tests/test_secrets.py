# TelsonBase/tests/test_secrets.py
# REM: =======================================================================================
# REM: TEST SUITE — SECRETS MANAGEMENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v5.1.0CC: Tests for Docker secrets integration, SecretValue wrapper,
# REM: SecretsProvider resolution chain, production startup guard, and
# REM: validate_production_secrets.
# REM: =======================================================================================

import os
import pytest
import tempfile
import warnings
from pathlib import Path
from unittest.mock import patch, MagicMock


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 1: SecretValue Wrapper
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecretValue:
    """REM: Tests that SecretValue prevents accidental secret leakage."""

    def test_str_is_redacted(self):
        """REM: str() must never reveal the secret."""
        from core.secrets import SecretValue
        sv = SecretValue("super_secret_key_12345", name="test")
        assert str(sv) == "***REDACTED***"
        assert "super_secret" not in str(sv)

    def test_repr_is_redacted(self):
        """REM: repr() must never reveal the secret."""
        from core.secrets import SecretValue
        sv = SecretValue("super_secret_key_12345", name="test_key")
        r = repr(sv)
        assert "***REDACTED***" in r
        assert "super_secret" not in r
        assert "test_key" in r  # Name is safe to show

    def test_get_returns_actual_value(self):
        """REM: .get() is the only way to access the raw value."""
        from core.secrets import SecretValue
        sv = SecretValue("my_actual_secret", name="test")
        assert sv.get() == "my_actual_secret"

    def test_equality_with_string(self):
        """REM: SecretValue can be compared to plain strings."""
        from core.secrets import SecretValue
        sv = SecretValue("abc123", name="test")
        assert sv == "abc123"
        assert sv != "wrong"

    def test_equality_with_secret_value(self):
        """REM: Two SecretValues with same content are equal."""
        from core.secrets import SecretValue
        sv1 = SecretValue("same", name="a")
        sv2 = SecretValue("same", name="b")
        assert sv1 == sv2

    def test_len(self):
        """REM: len() returns length of the secret, not the redacted string."""
        from core.secrets import SecretValue
        sv = SecretValue("1234567890", name="test")
        assert len(sv) == 10

    def test_bool_truthy(self):
        """REM: Non-empty secret is truthy."""
        from core.secrets import SecretValue
        assert bool(SecretValue("value", name="test")) is True

    def test_bool_falsy(self):
        """REM: Empty secret is falsy."""
        from core.secrets import SecretValue
        assert bool(SecretValue("", name="test")) is False

    def test_hash(self):
        """REM: SecretValue is hashable (can be used in sets/dicts)."""
        from core.secrets import SecretValue
        sv = SecretValue("hashable", name="test")
        s = {sv}  # Should not raise
        assert len(s) == 1

    def test_fstring_is_safe(self):
        """REM: f-strings must not leak the secret value."""
        from core.secrets import SecretValue
        sv = SecretValue("leaked_if_visible", name="test")
        result = f"The key is: {sv}"
        assert "leaked_if_visible" not in result
        assert "***REDACTED***" in result

    def test_format_is_safe(self):
        """REM: format() must not leak the secret value."""
        from core.secrets import SecretValue
        sv = SecretValue("leaked_if_visible", name="test")
        result = "Key: {}".format(sv)
        assert "leaked_if_visible" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 2: Secret Registry
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecretRegistry:
    """REM: Tests the SECRET_REGISTRY definitions."""

    def test_registry_has_required_secrets(self):
        """REM: All critical secrets must be in the registry."""
        from core.secrets import SECRET_REGISTRY
        required = ["mcp_api_key", "jwt_secret_key", "encryption_key", "encryption_salt"]
        for name in required:
            assert name in SECRET_REGISTRY, f"Missing required secret: {name}"
            assert SECRET_REGISTRY[name].required is True

    def test_registry_has_optional_secrets(self):
        """REM: Optional secrets must be marked as such."""
        from core.secrets import SECRET_REGISTRY
        optional = ["webui_secret_key", "grafana_admin_password"]
        for name in optional:
            assert name in SECRET_REGISTRY, f"Missing optional secret: {name}"
            assert SECRET_REGISTRY[name].required is False

    def test_all_secrets_have_docker_names(self):
        """REM: Every secret must have a Docker secret file name."""
        from core.secrets import SECRET_REGISTRY
        for name, defn in SECRET_REGISTRY.items():
            assert defn.docker_secret_name, f"Secret {name} missing docker_secret_name"
            assert defn.docker_secret_name.startswith("telsonbase_"), \
                f"Secret {name} docker name should start with 'telsonbase_'"

    def test_all_secrets_have_env_vars(self):
        """REM: Every secret must have an environment variable mapping."""
        from core.secrets import SECRET_REGISTRY
        for name, defn in SECRET_REGISTRY.items():
            assert defn.env_var, f"Secret {name} missing env_var"

    def test_min_length_requirements(self):
        """REM: Critical secrets must have >= 32 char minimum."""
        from core.secrets import SECRET_REGISTRY
        for name in ["mcp_api_key", "jwt_secret_key", "encryption_key"]:
            assert SECRET_REGISTRY[name].min_length >= 32


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 3: SecretsProvider Resolution Chain
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecretsProvider:
    """REM: Tests the layered secret resolution: Docker secrets → env vars → error."""

    def test_reads_from_docker_secret_file(self):
        """REM: Layer 1 — Docker secret files take priority."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir)
            # Write a mock Docker secret file
            secret_file = secrets_dir / "telsonbase_mcp_api_key"
            secret_file.write_text("docker_secret_value_" + "a" * 44)
            
            provider = SecretsProvider(secrets_dir=secrets_dir)
            result = provider.load_secret("mcp_api_key")
            
            assert result is not None
            assert result.get() == "docker_secret_value_" + "a" * 44

    def test_docker_secret_overrides_env_var(self):
        """REM: Docker secret must take priority over env var."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir)
            secret_file = secrets_dir / "telsonbase_mcp_api_key"
            secret_file.write_text("from_docker_" + "x" * 52)
            
            with patch.dict(os.environ, {"MCP_API_KEY": "from_env_" + "y" * 55}):
                provider = SecretsProvider(secrets_dir=secrets_dir)
                result = provider.load_secret("mcp_api_key")
                assert result.get().startswith("from_docker_")

    def test_falls_back_to_env_var(self):
        """REM: Layer 2 — Env var used when Docker secret not present."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty secrets dir — no Docker secret files
            with patch.dict(os.environ, {"MCP_API_KEY": "env_value_" + "z" * 54}):
                provider = SecretsProvider(secrets_dir=Path(tmpdir))
                result = provider.load_secret("mcp_api_key")
                assert result is not None
                assert result.get().startswith("env_value_")

    def test_required_secret_missing_development(self):
        """REM: In development, missing required secret returns None with warning."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            env_clean = {k: v for k, v in os.environ.items() if k != "MCP_API_KEY"}
            with patch.dict(os.environ, env_clean, clear=True):
                os.environ.pop("MCP_API_KEY", None)
                provider = SecretsProvider(secrets_dir=Path(tmpdir))
                provider._is_production = False
                result = provider.load_secret("mcp_api_key")
                assert result is None

    def test_required_secret_missing_production_raises(self):
        """REM: In production, missing required secret raises RuntimeError."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            env_clean = {k: v for k, v in os.environ.items() if k != "MCP_API_KEY"}
            with patch.dict(os.environ, env_clean, clear=True):
                os.environ.pop("MCP_API_KEY", None)
                provider = SecretsProvider(secrets_dir=Path(tmpdir))
                provider._is_production = True
                with pytest.raises(RuntimeError, match="Required secret"):
                    provider.load_secret("mcp_api_key")

    def test_insecure_default_blocked_in_production(self):
        """REM: Known insecure defaults must be rejected in production."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir)
            secret_file = secrets_dir / "telsonbase_mcp_api_key"
            secret_file.write_text("CHANGE_ME_IN_PRODUCTION_GENERATE_WITH_OPENSSL")
            
            provider = SecretsProvider(secrets_dir=secrets_dir)
            provider._is_production = True
            with pytest.raises(RuntimeError, match="failed validation"):
                provider.load_secret("mcp_api_key")

    def test_insecure_default_warns_in_development(self):
        """REM: Known insecure defaults emit warning in development."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir)
            secret_file = secrets_dir / "telsonbase_mcp_api_key"
            secret_file.write_text("CHANGE_ME_IN_PRODUCTION_GENERATE_WITH_OPENSSL")
            
            provider = SecretsProvider(secrets_dir=secrets_dir)
            provider._is_production = False
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = provider.load_secret("mcp_api_key")
                # Should warn but still return
                assert any("insecure" in str(warning.message).lower() for warning in w)

    def test_too_short_secret_blocked_in_production(self):
        """REM: Secrets below min_length must be rejected in production."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir)
            secret_file = secrets_dir / "telsonbase_mcp_api_key"
            secret_file.write_text("short")  # Way below 32 char minimum
            
            provider = SecretsProvider(secrets_dir=secrets_dir)
            provider._is_production = True
            with pytest.raises(RuntimeError, match="failed validation"):
                provider.load_secret("mcp_api_key")

    def test_unknown_secret_raises_value_error(self):
        """REM: Requesting an unregistered secret name raises ValueError."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = SecretsProvider(secrets_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="Unknown secret"):
                provider.load_secret("nonexistent_secret")

    def test_load_all_returns_all_secrets(self):
        """REM: load_all() must attempt every registered secret."""
        from core.secrets import SecretsProvider, SECRET_REGISTRY
        
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir)
            # Create valid files for all required secrets
            for name, defn in SECRET_REGISTRY.items():
                secret_file = secrets_dir / defn.docker_secret_name
                secret_file.write_text("valid_secret_" + "x" * 51)
            
            provider = SecretsProvider(secrets_dir=secrets_dir)
            results = provider.load_all()
            
            assert set(results.keys()) == set(SECRET_REGISTRY.keys())
            for name, defn in SECRET_REGISTRY.items():
                if defn.required:
                    assert results[name] is not None, f"Required secret {name} was None"

    def test_source_tracking(self):
        """REM: Provider must track where each secret came from."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir)
            # Docker secret for mcp_api_key
            (secrets_dir / "telsonbase_mcp_api_key").write_text("a" * 64)
            
            # Env var for jwt_secret_key
            with patch.dict(os.environ, {"JWT_SECRET_KEY": "b" * 64}):
                provider = SecretsProvider(secrets_dir=secrets_dir)
                provider.load_secret("mcp_api_key")
                provider.load_secret("jwt_secret_key")
                
                assert provider._sources["mcp_api_key"] == "docker_secret"
                assert provider._sources["jwt_secret_key"] == "env_var"

    def test_report_status_no_values_exposed(self):
        """REM: Status report must NEVER contain actual secret values."""
        from core.secrets import SecretsProvider
        
        the_secret = "this_must_never_appear_in_report_" + "q" * 32
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir)
            (secrets_dir / "telsonbase_mcp_api_key").write_text(the_secret)
            
            provider = SecretsProvider(secrets_dir=secrets_dir)
            provider.load_secret("mcp_api_key")
            
            report = provider.report_status()
            report_str = str(report)
            assert the_secret not in report_str
            assert report["mcp_api_key"]["loaded"] is True
            assert report["mcp_api_key"]["source"] == "docker_secret"

    def test_strips_whitespace_from_docker_secrets(self):
        """REM: Docker secret files often have trailing newlines — must strip."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir)
            (secrets_dir / "telsonbase_mcp_api_key").write_text("clean_value_" + "x" * 52 + "\n\n")
            
            provider = SecretsProvider(secrets_dir=secrets_dir)
            result = provider.load_secret("mcp_api_key")
            assert result.get() == "clean_value_" + "x" * 52  # No trailing newlines

    def test_empty_docker_secret_file_ignored(self):
        """REM: Empty or whitespace-only Docker secret files should be treated as absent."""
        from core.secrets import SecretsProvider
        
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_dir = Path(tmpdir)
            (secrets_dir / "telsonbase_mcp_api_key").write_text("   \n  ")
            
            with patch.dict(os.environ, {"MCP_API_KEY": "from_env_" + "z" * 55}):
                provider = SecretsProvider(secrets_dir=secrets_dir)
                result = provider.load_secret("mcp_api_key")
                # Should fall through to env var since Docker secret was empty
                assert result.get().startswith("from_env_")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 4: Production Startup Guard
# ═══════════════════════════════════════════════════════════════════════════════

class TestProductionStartupGuard:
    """REM: Tests validate_production_secrets() used in main.py lifespan."""

    def test_insecure_defaults_flagged(self):
        """REM: Known insecure default values must be flagged."""
        from core.config import validate_production_secrets
        
        settings = MagicMock()
        settings.mcp_api_key = "CHANGE_ME_IN_PRODUCTION_GENERATE_WITH_OPENSSL"
        settings.jwt_secret_key = "valid_secret_" + "x" * 51
        settings.webui_secret_key = "valid_secret_" + "x" * 51
        settings.grafana_admin_password = "valid_password_12345"
        
        errors = validate_production_secrets(settings)
        assert len(errors) == 1
        assert "MCP_API_KEY" in errors[0]

    def test_too_short_flagged(self):
        """REM: Secrets below minimum length must be flagged."""
        from core.config import validate_production_secrets
        
        settings = MagicMock()
        settings.mcp_api_key = "valid_" + "x" * 58
        settings.jwt_secret_key = "short"  # < 32
        settings.webui_secret_key = "valid_" + "x" * 58
        settings.grafana_admin_password = "valid_password_12345"
        
        errors = validate_production_secrets(settings)
        assert len(errors) == 1
        assert "JWT_SECRET_KEY" in errors[0]
        assert "too short" in errors[0]

    def test_all_valid_no_errors(self):
        """REM: Properly configured secrets should produce zero errors."""
        from core.config import validate_production_secrets
        
        settings = MagicMock()
        settings.mcp_api_key = "a" * 64
        settings.jwt_secret_key = "b" * 64
        settings.webui_secret_key = "c" * 64
        settings.grafana_admin_password = "d" * 24
        
        errors = validate_production_secrets(settings)
        assert errors == []

    def test_multiple_errors_all_reported(self):
        """REM: Multiple bad secrets should all be reported, not just the first."""
        from core.config import validate_production_secrets
        
        settings = MagicMock()
        settings.mcp_api_key = "MISSING_API_KEY"
        settings.jwt_secret_key = "CHANGE_ME_IN_PRODUCTION"
        settings.webui_secret_key = "CHANGE_ME_IN_PRODUCTION"
        settings.grafana_admin_password = "short"
        
        errors = validate_production_secrets(settings)
        assert len(errors) == 4


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 5: Docker Compose Secrets Configuration
# ═══════════════════════════════════════════════════════════════════════════════

class TestDockerComposeSecrets:
    """REM: Tests that docker-compose.yml is correctly configured for secrets.
    REM: These tests read files excluded from Docker build context by .dockerignore,
    REM: so they are skipped when running inside a container (e.g., via run_tests.bat).
    """

    @staticmethod
    def _require_file(path):
        """REM: Skip test if file doesn't exist (excluded from Docker build context)."""
        if not path.exists():
            pytest.skip(f"{path.name} not available inside container (excluded by .dockerignore)")

    def test_docker_compose_has_secrets_section(self):
        """REM: docker-compose.yml must define top-level secrets."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        self._require_file(compose_path)
        content = compose_path.read_text()
        assert "secrets:" in content
        assert "telsonbase_mcp_api_key" in content
        assert "telsonbase_jwt_secret" in content
        assert "telsonbase_encryption_key" in content
        assert "telsonbase_encryption_salt" in content

    def test_secrets_reference_files(self):
        """REM: All secrets must use file: directive pointing to ./secrets/."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        self._require_file(compose_path)
        content = compose_path.read_text()
        assert "file: ./secrets/telsonbase_mcp_api_key" in content
        assert "file: ./secrets/telsonbase_jwt_secret" in content

    def test_mcp_server_has_secrets(self):
        """REM: mcp_server service must have secrets mounted."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        self._require_file(compose_path)
        content = compose_path.read_text()
        # Check that secrets appear in the mcp_server service context
        mcp_section = content[content.index("mcp_server:"):content.index("worker:")]
        assert "telsonbase_mcp_api_key" in mcp_section
        assert "telsonbase_jwt_secret" in mcp_section

    def test_grafana_uses_file_based_secret(self):
        """REM: Grafana must use __FILE convention, not plain env var for password."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        self._require_file(compose_path)
        content = compose_path.read_text()
        assert "GF_SECURITY_ADMIN_PASSWORD__FILE=/run/secrets/telsonbase_grafana_password" in content

    def test_secrets_dir_in_dockerignore(self):
        """REM: secrets/ must be excluded from Docker build context."""
        dockerignore_path = Path(__file__).parent.parent / ".dockerignore"
        self._require_file(dockerignore_path)
        content = dockerignore_path.read_text()
        assert "secrets/" in content

    def test_secrets_dir_in_gitignore(self):
        """REM: secrets/ must be excluded from git."""
        gitignore_path = Path(__file__).parent.parent / ".gitignore"
        self._require_file(gitignore_path)
        content = gitignore_path.read_text()
        assert "secrets/" in content

    def test_env_example_documents_telsonbase_env(self):
        """REM: .env.example must document the TELSONBASE_ENV variable."""
        env_example_path = Path(__file__).parent.parent / ".env.example"
        content = env_example_path.read_text()
        assert "TELSONBASE_ENV" in content
        assert "production" in content
        assert "development" in content


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 6: Config.py Docker Secrets Resolution
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfigDockerResolution:
    """REM: Tests that config.py resolves secrets from Docker files first."""

    def test_resolve_secret_from_file(self):
        """REM: _resolve_secret must read from Docker secret file."""
        from core.config import _resolve_secret
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Temporarily monkey-patch the DOCKER_SECRETS_DIR
            import core.config as config_module
            original_dir = config_module.DOCKER_SECRETS_DIR
            config_module.DOCKER_SECRETS_DIR = Path(tmpdir)
            
            try:
                secret_file = Path(tmpdir) / "test_secret"
                secret_file.write_text("from_file_value")
                
                result = _resolve_secret("test_secret", "TEST_ENV_VAR", "default")
                assert result == "from_file_value"
            finally:
                config_module.DOCKER_SECRETS_DIR = original_dir

    def test_resolve_secret_env_fallback(self):
        """REM: _resolve_secret falls back to env var when no Docker secret."""
        from core.config import _resolve_secret
        
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.config as config_module
            original_dir = config_module.DOCKER_SECRETS_DIR
            config_module.DOCKER_SECRETS_DIR = Path(tmpdir)
            
            try:
                with patch.dict(os.environ, {"FALLBACK_VAR": "from_env"}):
                    result = _resolve_secret("nonexistent", "FALLBACK_VAR", "default")
                    assert result == "from_env"
            finally:
                config_module.DOCKER_SECRETS_DIR = original_dir

    def test_resolve_secret_default_fallback(self):
        """REM: _resolve_secret uses default when neither file nor env exists."""
        from core.config import _resolve_secret
        
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.config as config_module
            original_dir = config_module.DOCKER_SECRETS_DIR
            config_module.DOCKER_SECRETS_DIR = Path(tmpdir)
            
            try:
                env_clean = {k: v for k, v in os.environ.items() if k != "NONEXISTENT_VAR"}
                with patch.dict(os.environ, env_clean, clear=True):
                    result = _resolve_secret("nonexistent", "NONEXISTENT_VAR", "my_default")
                    assert result == "my_default"
            finally:
                config_module.DOCKER_SECRETS_DIR = original_dir


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 7: Generate Secrets Script
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateSecretsScript:
    """REM: Tests that the secret generation script exists and is valid."""

    def test_script_exists(self):
        """REM: generate_secrets.sh must exist."""
        script_path = Path(__file__).parent.parent / "scripts" / "generate_secrets.sh"
        assert script_path.exists()

    def test_script_is_executable_content(self):
        """REM: Script must start with shebang and contain expected secret names."""
        script_path = Path(__file__).parent.parent / "scripts" / "generate_secrets.sh"
        content = script_path.read_text()
        assert content.startswith("#!/bin/bash")
        assert "telsonbase_mcp_api_key" in content
        assert "telsonbase_jwt_secret" in content
        assert "telsonbase_encryption_key" in content
        assert "telsonbase_encryption_salt" in content
        assert "telsonbase_grafana_password" in content
        assert "openssl rand" in content

    def test_script_creates_restricted_directory(self):
        """REM: Script must create secrets/ with 700 permissions."""
        script_path = Path(__file__).parent.parent / "scripts" / "generate_secrets.sh"
        content = script_path.read_text()
        assert "chmod 700" in content

    def test_script_creates_restricted_files(self):
        """REM: Script must set 644 permissions on secret files (readable by container app user)."""
        script_path = Path(__file__).parent.parent / "scripts" / "generate_secrets.sh"
        content = script_path.read_text()
        assert "chmod 644" in content
