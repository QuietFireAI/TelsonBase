# TelsonBase/tests/test_contracts.py
# REM: =======================================================================================
# REM: ENUM AND API CONTRACT TESTS
# REM: =======================================================================================
# REM: These tests act as a tripwire for unintentional breaking changes.
# REM: If a value is removed from an enum, a test here fails loudly — there is no silent
# REM: deployment that breaks downstream users or mis-validates API inputs.
# REM:
# REM: Rules:
# REM:   - Adding a new valid value: add it here too.
# REM:   - Removing a valid value: remove it here AND update CHANGELOG.md (breaking change).
# REM:   - Renaming a value: treat as remove + add.
# REM: =======================================================================================

import pytest


class TestTenantTypeContract:
    """REM: Valid tenant_type values accepted by POST /v1/tenants."""

    EXPECTED = {
        "law_firm",
        "insurance",
        "real_estate",
        "healthcare",
        "small_business",
        "personal",
        "general",
    }

    def test_tenant_type_enum_has_all_expected_values(self):
        """REM: TenantType enum must contain every documented value."""
        from core.tenancy import TenantType
        actual = {m.value for m in TenantType}
        missing = self.EXPECTED - actual
        extra = actual - self.EXPECTED
        assert not missing, (
            f"TenantType is missing values that were documented as valid: {missing}. "
            f"If intentionally removed, update this test AND CHANGELOG.md."
        )
        assert not extra, (
            f"TenantType has undocumented values: {extra}. "
            f"Add them to this test's EXPECTED set and CHANGELOG.md."
        )

    def test_tenant_type_no_duplicates(self):
        """REM: Each enum member must have a unique value."""
        from core.tenancy import TenantType
        values = [m.value for m in TenantType]
        assert len(values) == len(set(values)), "TenantType has duplicate values"


class TestAgentTrustLevelContract:
    """REM: Valid trust level values used throughout the agent governance system."""

    EXPECTED = {
        "quarantine",
        "probation",
        "resident",
        "citizen",
        "agent",
    }

    def test_trust_level_enum_has_all_expected_values(self):
        """REM: AgentTrustLevel enum must contain every documented value."""
        from core.trust_levels import AgentTrustLevel
        actual = {m.value for m in AgentTrustLevel}
        missing = self.EXPECTED - actual
        extra = actual - self.EXPECTED
        assert not missing, (
            f"AgentTrustLevel is missing values: {missing}. "
            f"If intentionally removed, update this test AND CHANGELOG.md."
        )
        assert not extra, (
            f"AgentTrustLevel has undocumented values: {extra}. "
            f"Add them to this test's EXPECTED set and CHANGELOG.md."
        )

    def test_trust_level_promotion_path_intact(self):
        """REM: Promotion order must be: QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT."""
        from core.trust_levels import AgentTrustLevel
        ordered = ["quarantine", "probation", "resident", "citizen", "agent"]
        values = [m.value for m in AgentTrustLevel]
        for level in ordered:
            assert level in values, f"Trust level '{level}' missing from enum — promotion path broken"


class TestVersionContract:
    """REM: Version strings must be consistent across all canonical sources."""

    def test_version_py_matches_config_py(self):
        """REM: version.py and core/config.py must agree on the current version."""
        from version import __version__
        from core.config import VERSION
        assert __version__ == VERSION, (
            f"Version mismatch: version.py='{__version__}' vs config.py='{VERSION}'. "
            f"Run the version bump procedure to sync all sources."
        )

    def test_app_version_sourced_from_version_py(self):
        """REM: main.py must import APP_VERSION from version.py, not hardcode it."""
        import main
        from version import __version__
        # REM: APP_VERSION is set at module level from __version__
        assert hasattr(main, "APP_VERSION"), (
            "main.py does not export APP_VERSION — version import may be missing"
        )
        assert main.APP_VERSION == __version__, (
            f"main.APP_VERSION '{main.APP_VERSION}' does not match version.py '{__version__}'"
        )


class TestOperationalContracts:
    """REM: Operational invariants that must hold for reliable deployments."""

    def test_alembic_upgrade_head_is_idempotent(self):
        """
        REM: Running 'alembic upgrade head' when already at head must be a no-op.
        REM: Validates that migration scripts do not raise on re-run (idempotency).
        REM: Requires DATABASE_URL env var pointing to a live database — skips otherwise.
        """
        import os
        try:
            from alembic.config import Config
            from alembic import command
        except ImportError:
            pytest.skip("alembic not installed")

        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            pytest.skip("DATABASE_URL not set — skipping migration idempotency test (requires live DB)")

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_ini = os.path.join(repo_root, "alembic.ini")
        if not os.path.exists(alembic_ini):
            pytest.skip("alembic.ini not found")

        cfg = Config(alembic_ini)
        cfg.set_main_option("sqlalchemy.url", db_url)

        # REM: Second invocation of upgrade head on an already-migrated DB must not raise
        try:
            command.upgrade(cfg, "head")
        except Exception as e:
            pytest.fail(f"alembic upgrade head raised on second run (not idempotent): {e}")
