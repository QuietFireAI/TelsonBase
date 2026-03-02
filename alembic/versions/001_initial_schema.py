"""Initial schema — users, audit_entries, tenants, compliance_records

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-02-10

REM: =======================================================================================
REM: INITIAL DATABASE SCHEMA MIGRATION
REM: =======================================================================================
REM: Architect: ::Quietfire AI Project::
REM: Date: February 23, 2026
REM: v6.3.0CC: Creates the four foundation tables for TelsonBase durable storage
REM: QMS Protocol: SCHEMA-MIG-001 — Initial schema baseline for compliance audit trail
REM:
REM: Tables created:
REM:   1. users              — Durable user records for compliance auditing
REM:   2. audit_entries      — Immutable audit log with hash-chain integrity
REM:   3. tenants            — Multi-tenancy management records
REM:   4. compliance_records — Flexible compliance data (legal holds, BAAs, etc.)
REM: =======================================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # REM: TABLE 1 — users
    # REM: Durable user records for compliance auditing
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("username", sa.String(255), unique=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("roles", sa.JSON, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("mfa_enabled", sa.Boolean, default=False),
        sa.Column("email_verified", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    # REM: Index on username for fast lookups (matches model index=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ------------------------------------------------------------------
    # REM: TABLE 2 — audit_entries
    # REM: Immutable audit log with hash-chain integrity for legal discovery
    # ------------------------------------------------------------------
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("chain_id", sa.String(32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("actor_type", sa.String(32), default="system"),
        sa.Column("resource", sa.String(255), nullable=True),
        sa.Column("details", sa.JSON),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
    )
    # REM: Individual column indexes (match model index=True declarations)
    op.create_index("ix_audit_entries_timestamp", "audit_entries", ["timestamp"])
    op.create_index("ix_audit_entries_event_type", "audit_entries", ["event_type"])
    op.create_index("ix_audit_entries_actor", "audit_entries", ["actor"])
    # REM: Composite index for chain traversal queries
    op.create_index("ix_audit_chain_sequence", "audit_entries", ["chain_id", "sequence"])

    # ------------------------------------------------------------------
    # REM: TABLE 3 — tenants
    # REM: Multi-tenancy management records
    # ------------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tenant_type", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("settings", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # REM: TABLE 4 — compliance_records
    # REM: Flexible compliance data for legal holds, breach assessments,
    # REM: BAAs, sanctions, training, and other regulatory data
    # ------------------------------------------------------------------
    op.create_table(
        "compliance_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("record_type", sa.String(64), nullable=False),
        sa.Column("record_id", sa.String(64), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    # REM: Individual column indexes (match model index=True declarations)
    op.create_index("ix_compliance_records_record_type", "compliance_records", ["record_type"])
    op.create_index("ix_compliance_records_record_id", "compliance_records", ["record_id"], unique=True)
    op.create_index("ix_compliance_records_tenant_id", "compliance_records", ["tenant_id"])
    # REM: Composite index for type+tenant queries
    op.create_index("ix_compliance_type_tenant", "compliance_records", ["record_type", "tenant_id"])


def downgrade() -> None:
    # REM: Drop in reverse order to respect any future FK dependencies
    op.drop_index("ix_compliance_type_tenant", table_name="compliance_records")
    op.drop_index("ix_compliance_records_tenant_id", table_name="compliance_records")
    op.drop_index("ix_compliance_records_record_id", table_name="compliance_records")
    op.drop_index("ix_compliance_records_record_type", table_name="compliance_records")
    op.drop_table("compliance_records")

    op.drop_table("tenants")

    op.drop_index("ix_audit_chain_sequence", table_name="audit_entries")
    op.drop_index("ix_audit_entries_actor", table_name="audit_entries")
    op.drop_index("ix_audit_entries_event_type", table_name="audit_entries")
    op.drop_index("ix_audit_entries_timestamp", table_name="audit_entries")
    op.drop_table("audit_entries")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
