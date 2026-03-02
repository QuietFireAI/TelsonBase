# TelsonBase/alembic/env.py
# REM: =======================================================================================
# REM: ALEMBIC MIGRATION ENVIRONMENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM: v6.3.0CC: Migration environment for PostgreSQL schema management
# REM: QMS Protocol: SCHEMA-MIG-001 — Runtime migration configuration
# REM: =======================================================================================

import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# REM: Ensure the project root is on sys.path so core.* imports resolve
# REM: Inside Docker the app lives at /app; locally it may differ
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# REM: Import the declarative Base whose .metadata knows about all tables
from core.database import Base

# REM: Import all models so that Base.metadata is fully populated before
# REM: Alembic inspects it for autogenerate diffing
from core.models import (  # noqa: F401
    UserModel,
    AuditEntryModel,
    TenantModel,
    ComplianceRecordModel,
)

# REM: Import settings to get the authoritative DATABASE_URL
from core.config import get_settings

# -- Alembic Config object --------------------------------------------------------
config = context.config

# REM: Interpret the config file for Python logging (unless we are in testing)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# REM: Target metadata for autogenerate support
target_metadata = Base.metadata

# REM: Override sqlalchemy.url with the value from core.config so that
# REM: Docker secrets / env vars are the single source of truth
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


# ====================================================================================
# REM: OFFLINE MIGRATIONS — generate SQL scripts without a live database connection
# ====================================================================================
def run_migrations_offline() -> None:
    """
    REM: Run migrations in 'offline' mode.
    REM: Emits SQL to stdout (or a file) without connecting to the database.
    REM: Useful for generating SQL review scripts per QMS Protocol SCHEMA-MIG-001.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ====================================================================================
# REM: ONLINE MIGRATIONS — apply directly against a live PostgreSQL instance
# ====================================================================================
def run_migrations_online() -> None:
    """
    REM: Run migrations in 'online' mode.
    REM: Creates an Engine and associates a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# REM: Dispatch to the appropriate migration mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
