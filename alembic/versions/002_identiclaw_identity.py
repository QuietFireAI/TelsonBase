"""Add agent_identities table for Identiclaw MCP-I integration

Revision ID: 002_identiclaw_identity
Revises: 001_initial_schema
Create Date: 2026-02-17

REM: =======================================================================================
REM: IDENTICLAW IDENTITY SCHEMA MIGRATION
REM: =======================================================================================
REM: Architect: ::Quietfire AI Project::
REM: Date: February 23, 2026
REM: v7.3.0CC: Adds durable storage for DID-based agent identities from Identiclaw.
REM: Redis is the hot cache for auth-path performance; PostgreSQL provides durable
REM: storage for compliance queries and legal discovery.
REM:
REM: Tables created:
REM:   1. agent_identities — DID-authenticated agent records with kill switch support
REM: =======================================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_identiclaw_identity"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_identities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("did", sa.String(512), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("public_key_hex", sa.String(128), nullable=False),
        sa.Column("did_document_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("active_credentials", sa.JSON, server_default="[]"),
        sa.Column("telsonbase_permissions", sa.JSON, server_default="[]"),
        sa.Column("trust_level", sa.String(32), server_default="quarantine"),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean, server_default="false"),
        sa.Column("revoked_by", sa.String(255), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(1024), nullable=True),
        sa.Column("manners_md_path", sa.String(512), nullable=True),
        sa.Column("profession_md_path", sa.String(512), nullable=True),
        sa.Column("metadata", sa.JSON, server_default="{}"),
    )
    op.create_index("ix_agent_identities_did", "agent_identities", ["did"], unique=True)
    op.create_index("ix_agent_identities_trust", "agent_identities", ["trust_level"])


def downgrade() -> None:
    op.drop_index("ix_agent_identities_trust", table_name="agent_identities")
    op.drop_index("ix_agent_identities_did", table_name="agent_identities")
    op.drop_table("agent_identities")
