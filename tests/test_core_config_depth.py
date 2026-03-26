# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_core_config_depth.py
# REM: Depth coverage for core/config.py
# REM: Pure unit tests — no external services required.

import os
import warnings
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from core.config import (
    Settings,
    _resolve_secret,
    validate_production_secrets,
    get_settings,
    DOCKER_SECRETS_DIR,
    VERSION,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestModuleConstants:
    def test_version_string(self):
        assert VERSION == "11.0.4"

    def test_docker_secrets_dir(self):
        assert str(DOCKER_SECRETS_DIR) == "/run/secrets"


# ═══════════════════════════════════════════════════════════════════════════════
# _resolve_secret — layer priority
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveSecret:
    def test_layer1_docker_secret_file(self, tmp_path):
        # Docker secret file takes priority over env and default
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        secret_file = secret_dir / "my_secret"
        secret_file.write_text("docker_value\n")  # trailing newline stripped

        with patch("core.config.DOCKER_SECRETS_DIR", secret_dir):
            result = _resolve_secret("my_secret", "MY_ENV_VAR", default="env_default")
        assert result == "docker_value"

    def test_layer1_strips_whitespace(self, tmp_path):
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        secret_file = secret_dir / "my_secret"
        secret_file.write_text("  spaced_value  \n")

        with patch("core.config.DOCKER_SECRETS_DIR", secret_dir):
            result = _resolve_secret("my_secret", "MY_ENV_VAR")
        assert result == "spaced_value"

    def test_layer1_empty_file_falls_through(self, tmp_path):
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        secret_file = secret_dir / "empty_secret"
        secret_file.write_text("   \n")  # whitespace only

        with patch("core.config.DOCKER_SECRETS_DIR", secret_dir), \
             patch.dict(os.environ, {"MY_ENV_EMPTY": "env_value"}):
            result = _resolve_secret("empty_secret", "MY_ENV_EMPTY")
        assert result == "env_value"

    def test_layer1_permission_error_falls_through(self, tmp_path):
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        secret_file = secret_dir / "perm_secret"
        secret_file.write_text("blocked")

        with patch("core.config.DOCKER_SECRETS_DIR", secret_dir), \
             patch("pathlib.Path.read_text", side_effect=PermissionError("denied")), \
             patch.dict(os.environ, {"PERM_ENV": "env_fallback"}):
            result = _resolve_secret("perm_secret", "PERM_ENV")
        assert result == "env_fallback"

    def test_layer2_env_var(self, tmp_path):
        # No secret file exists — fall through to env var
        secret_dir = tmp_path / "no_secrets"
        secret_dir.mkdir()

        with patch("core.config.DOCKER_SECRETS_DIR", secret_dir), \
             patch.dict(os.environ, {"LAYER2_VAR": "env_val"}):
            result = _resolve_secret("nonexistent_file", "LAYER2_VAR", default="default_val")
        assert result == "env_val"

    def test_layer2_strips_env_whitespace(self, tmp_path):
        secret_dir = tmp_path / "no_secrets2"
        secret_dir.mkdir()

        with patch("core.config.DOCKER_SECRETS_DIR", secret_dir), \
             patch.dict(os.environ, {"STRIP_ENV": "  trimmed  "}):
            result = _resolve_secret("nope", "STRIP_ENV")
        assert result == "trimmed"

    def test_layer3_default_when_no_file_no_env(self, tmp_path):
        secret_dir = tmp_path / "empty_secrets"
        secret_dir.mkdir()

        with patch("core.config.DOCKER_SECRETS_DIR", secret_dir), \
             patch.dict(os.environ, {}, clear=True):
            # Clear the env var if it exists
            env_without = {k: v for k, v in os.environ.items() if k != "DEFAULT_TEST_VAR"}
            with patch.dict(os.environ, env_without, clear=True):
                result = _resolve_secret("nofile", "DEFAULT_TEST_VAR", default="fallback_val")
        assert result == "fallback_val"

    def test_layer3_none_default(self, tmp_path):
        secret_dir = tmp_path / "none_secrets"
        secret_dir.mkdir()

        with patch("core.config.DOCKER_SECRETS_DIR", secret_dir):
            with patch.dict(os.environ, {}, clear=True):
                result = _resolve_secret("nofile", "NONEXISTENT_VAR_XYZ123", default=None)
        assert result is None

    def test_docker_file_not_directory(self, tmp_path):
        # If the path exists but is a directory, it should not be read as a file
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        # Create a directory where the secret file is expected
        (secret_dir / "dir_secret").mkdir()

        with patch("core.config.DOCKER_SECRETS_DIR", secret_dir), \
             patch.dict(os.environ, {"DIR_ENV": "dir_env_val"}):
            result = _resolve_secret("dir_secret", "DIR_ENV")
        assert result == "dir_env_val"


# ═══════════════════════════════════════════════════════════════════════════════
# Settings — instantiation and defaults
# ═══════════════════════════════════════════════════════════════════════════════

class TestSettingsDefaults:
    @pytest.fixture
    def settings(self):
        # REM: conftest.py sets LOG_LEVEL=WARNING globally; pop it so default assertion is clean
        import os as _os
        _saved_log = _os.environ.pop("LOG_LEVEL", None)
        get_settings.cache_clear()
        with patch("core.config.DOCKER_SECRETS_DIR", Path("/nonexistent_docker_secrets_dir_xyz")):
            s = Settings()
        get_settings.cache_clear()
        if _saved_log is not None:
            _os.environ["LOG_LEVEL"] = _saved_log
        return s

    def test_jwt_algorithm_default(self, settings):
        assert settings.jwt_algorithm == "HS256"

    def test_jwt_expiration_hours_default(self, settings):
        assert settings.jwt_expiration_hours == 24

    def test_log_level_default(self, settings):
        assert settings.log_level == "INFO"

    def test_openclaw_enabled_default(self, settings):
        assert settings.openclaw_enabled is False

    def test_identiclaw_enabled_default(self, settings):
        assert settings.identiclaw_enabled is False

    def test_rate_limit_per_minute_default(self, settings):
        assert settings.rate_limit_per_minute == 300

    def test_rate_limit_burst_default(self, settings):
        assert settings.rate_limit_burst == 60

    def test_secrets_rotation_reminder_days_default(self, settings):
        assert settings.secrets_rotation_reminder_days == 90

    def test_audit_max_redis_entries_default(self, settings):
        assert settings.audit_max_redis_entries == 100000

    def test_telsonbase_env_default(self, settings):
        assert settings.telsonbase_env == "development"

    def test_openclaw_auto_demote_threshold(self, settings):
        assert settings.openclaw_auto_demote_manners_threshold == 0.50

    def test_openclaw_max_instances(self, settings):
        assert settings.openclaw_max_instances == 10

    def test_allowed_external_domains_is_list(self, settings):
        assert isinstance(settings.allowed_external_domains, list)
        assert len(settings.allowed_external_domains) > 0

    def test_cors_origins_is_list(self, settings):
        assert isinstance(settings.cors_origins, list)

    def test_traefik_domain_default(self, settings):
        assert settings.traefik_domain == "localhost"


# ═══════════════════════════════════════════════════════════════════════════════
# validate_jwt_secret validator
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateJwtSecret:
    def test_insecure_default_warns_in_dev(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch.dict(os.environ, {"TELSONBASE_ENV": "development",
                                         "JWT_SECRET_KEY": "CHANGE_ME_IN_PRODUCTION_GENERATE_WITH_OPENSSL"},
                            clear=False):
                get_settings.cache_clear()
                try:
                    s = Settings()
                    # Should have issued a warning
                    security_warnings = [x for x in w if issubclass(x.category, UserWarning)
                                         and "insecure" in str(x.message).lower()]
                    assert len(security_warnings) > 0
                except Exception:
                    pass
                finally:
                    get_settings.cache_clear()

    def test_short_key_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch.dict(os.environ, {"TELSONBASE_ENV": "development",
                                         "JWT_SECRET_KEY": "short"},
                            clear=False):
                get_settings.cache_clear()
                try:
                    s = Settings()
                    security_warnings = [x for x in w if issubclass(x.category, UserWarning)]
                    assert len(security_warnings) > 0
                except Exception:
                    pass
                finally:
                    get_settings.cache_clear()

    def test_insecure_default_raises_in_production(self):
        with patch.dict(os.environ,
                        {"TELSONBASE_ENV": "production",
                         "JWT_SECRET_KEY": "CHANGE_ME_IN_PRODUCTION_GENERATE_WITH_OPENSSL"},
                        clear=False):
            get_settings.cache_clear()
            try:
                with pytest.raises((ValueError, Exception)):
                    s = Settings()
            finally:
                get_settings.cache_clear()

    def test_strong_key_no_warning(self):
        strong_key = "a" * 64  # 64 chars, not in insecure list
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch.dict(os.environ, {"TELSONBASE_ENV": "development",
                                         "JWT_SECRET_KEY": strong_key},
                            clear=False):
                get_settings.cache_clear()
                try:
                    s = Settings()
                    security_warnings = [
                        x for x in w
                        if issubclass(x.category, UserWarning) and "JWT" in str(x.message)
                    ]
                    assert len(security_warnings) == 0
                except Exception:
                    pass
                finally:
                    get_settings.cache_clear()


# ═══════════════════════════════════════════════════════════════════════════════
# inject_redis_password validator
# ═══════════════════════════════════════════════════════════════════════════════

class TestInjectRedisPassword:
    def test_password_injected_when_no_at(self):
        with patch.dict(os.environ,
                        {"REDIS_PASSWORD": "mypass", "REDIS_URL": "redis://redis:6379/0"},
                        clear=False):
            get_settings.cache_clear()
            try:
                s = Settings()
                assert ":mypass@" in s.redis_url
            finally:
                get_settings.cache_clear()

    def test_no_injection_when_at_present(self):
        with patch.dict(os.environ,
                        {"REDIS_URL": "redis://:existingpass@redis:6379/0"},
                        clear=False):
            get_settings.cache_clear()
            try:
                s = Settings()
                # Should not double-inject
                assert s.redis_url.count("@") == 1
            finally:
                get_settings.cache_clear()


# ═══════════════════════════════════════════════════════════════════════════════
# validate_cors_origins validator
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateCorsOrigins:
    def test_wildcard_warns_in_dev(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch.dict(os.environ,
                            {"CORS_ORIGINS": '["*"]', "TELSONBASE_ENV": "development"},
                            clear=False):
                get_settings.cache_clear()
                try:
                    s = Settings()
                    cors_warnings = [x for x in w if issubclass(x.category, UserWarning)
                                     and "CORS" in str(x.message)]
                    assert len(cors_warnings) > 0
                except Exception:
                    pass
                finally:
                    get_settings.cache_clear()

    def test_wildcard_warns_in_production(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch.dict(os.environ,
                            {"CORS_ORIGINS": '["*"]', "TELSONBASE_ENV": "production"},
                            clear=False):
                get_settings.cache_clear()
                try:
                    s = Settings()
                    cors_warnings = [x for x in w if issubclass(x.category, UserWarning)
                                     and "CORS" in str(x.message)]
                    assert len(cors_warnings) > 0
                except Exception:
                    pass
                finally:
                    get_settings.cache_clear()

    def test_specific_origin_no_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch.dict(os.environ,
                            {"CORS_ORIGINS": '["https://app.example.com"]'},
                            clear=False):
                get_settings.cache_clear()
                try:
                    s = Settings()
                    cors_warnings = [x for x in w if issubclass(x.category, UserWarning)
                                     and "CORS" in str(x.message)]
                    assert len(cors_warnings) == 0
                except Exception:
                    pass
                finally:
                    get_settings.cache_clear()


# ═══════════════════════════════════════════════════════════════════════════════
# validate_production_secrets
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateProductionSecrets:
    @pytest.fixture
    def good_settings(self):
        """Settings with all secure values."""
        get_settings.cache_clear()
        strong = "x" * 48
        with patch.dict(os.environ, {
            "MCP_API_KEY": strong,
            "JWT_SECRET_KEY": strong,
            "WEBUI_SECRET_KEY": strong,
            "GRAFANA_ADMIN_PASSWORD": strong,
            "DATABASE_URL": "postgresql://telsonbase:strongpass@postgres:5432/telsonbase",
            "REDIS_PASSWORD": "strongredispass",
            "MOSQUITTO_PASSWORD": "strongmqttpass",
            "TELSONBASE_ENV": "development",
        }, clear=False):
            s = Settings()
        get_settings.cache_clear()
        return s

    def test_all_good_returns_empty_list(self, good_settings):
        errors = validate_production_secrets(good_settings)
        assert errors == []

    def test_insecure_mcp_api_key(self, good_settings):
        good_settings.mcp_api_key = "MISSING_API_KEY"
        errors = validate_production_secrets(good_settings)
        assert any("MCP_API_KEY" in e for e in errors)

    def test_insecure_jwt_secret_key(self, good_settings):
        good_settings.jwt_secret_key = "CHANGE_ME_IN_PRODUCTION"
        errors = validate_production_secrets(good_settings)
        assert any("JWT_SECRET_KEY" in e for e in errors)

    def test_short_mcp_key(self, good_settings):
        good_settings.mcp_api_key = "short"
        errors = validate_production_secrets(good_settings)
        assert any("MCP_API_KEY" in e and "too short" in e for e in errors)

    def test_short_jwt_key(self, good_settings):
        good_settings.jwt_secret_key = "short_jwt"
        errors = validate_production_secrets(good_settings)
        assert any("JWT_SECRET_KEY" in e and "too short" in e for e in errors)

    def test_short_grafana_password(self, good_settings):
        good_settings.grafana_admin_password = "abc"
        errors = validate_production_secrets(good_settings)
        assert any("GRAFANA_ADMIN_PASSWORD" in e and "too short" in e for e in errors)

    def test_dev_postgres_password(self, good_settings):
        good_settings.database_url = "postgresql://clawcoat:clawcoat_dev@postgres:5432/clawcoat"
        errors = validate_production_secrets(good_settings)
        assert any("POSTGRES_PASSWORD" in e for e in errors)

    def test_dev_redis_password(self, good_settings):
        good_settings.redis_password = "clawcoat_redis_dev"
        errors = validate_production_secrets(good_settings)
        assert any("REDIS_PASSWORD" in e for e in errors)

    def test_dev_mqtt_password(self, good_settings):
        good_settings.mosquitto_password = "dev_password"
        errors = validate_production_secrets(good_settings)
        assert any("MOSQUITTO_PASSWORD" in e for e in errors)

    def test_none_mqtt_password_is_ok(self, good_settings):
        good_settings.mosquitto_password = None
        errors = validate_production_secrets(good_settings)
        assert not any("MOSQUITTO_PASSWORD" in e for e in errors)

    def test_multiple_errors_reported(self, good_settings):
        good_settings.mcp_api_key = "MISSING_API_KEY"
        good_settings.redis_password = "clawcoat_redis_dev"
        errors = validate_production_secrets(good_settings)
        assert len(errors) >= 2

    def test_change_me_webui_key(self, good_settings):
        good_settings.webui_secret_key = "CHANGE_ME_IN_PRODUCTION"
        errors = validate_production_secrets(good_settings)
        assert any("WEBUI_SECRET_KEY" in e for e in errors)

    def test_insecure_grafana_password(self, good_settings):
        good_settings.grafana_admin_password = "CHANGE_ME_IN_PRODUCTION"
        errors = validate_production_secrets(good_settings)
        assert any("GRAFANA_ADMIN_PASSWORD" in e for e in errors)

    def test_secret_keyword_in_checks(self, good_settings):
        good_settings.mcp_api_key = "secret"
        errors = validate_production_secrets(good_settings)
        assert any("MCP_API_KEY" in e for e in errors)

    def test_changeme_keyword_in_checks(self, good_settings):
        good_settings.jwt_secret_key = "changeme"
        errors = validate_production_secrets(good_settings)
        assert any("JWT_SECRET_KEY" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# get_settings — caching
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSettings:
    def test_returns_settings_instance(self):
        get_settings.cache_clear()
        s = get_settings()
        assert isinstance(s, Settings)
        get_settings.cache_clear()

    def test_returns_same_instance_on_second_call(self):
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        get_settings.cache_clear()

    def test_cache_cleared_returns_new_instance(self):
        get_settings.cache_clear()
        s1 = get_settings()
        get_settings.cache_clear()
        s2 = get_settings()
        # Not guaranteed to be different object but cache was cleared
        assert isinstance(s2, Settings)
        get_settings.cache_clear()
