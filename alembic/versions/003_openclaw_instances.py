"""Add openclaw_instances table for OpenClaw governance integration

Revision ID: 003_openclaw_instances
Revises: 002_identiclaw_identity
Create Date: 2026-02-18

REM: =======================================================================================
REM: OPENCLAW GOVERNANCE SCHEMA MIGRATION
REM: =======================================================================================
REM: Architect: ::Quietfire AI Project::
REM: Date: February 23, 2026
REM: v7.4.0CC: Adds durable storage for governed OpenClaw instances.
REM: Redis is the hot cache for governance pipeline performance; PostgreSQL provides
REM: durable storage for trust level auditing and compliance queries.
REM:
REM: Tables created:
REM:   1. openclaw_instances — Governed claw records with trust levels and kill switch
REM: =======================================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_openclaw_instances"
down_revision: Union[str, None] = "002_identiclaw_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "openclaw_instances",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("trust_level", sa.String(32), server_default="quarantine"),
        sa.Column("api_key_hash", sa.String(128), nullable=False),
        sa.Column("allowed_tools", sa.JSON, server_default="[]"),
        sa.Column("blocked_tools", sa.JSON, server_default="[]"),
        sa.Column("manners_score", sa.Float, server_default="1.0"),
        sa.Column("action_count", sa.Integer, server_default="0"),
        sa.Column("actions_allowed", sa.Integer, server_default="0"),
        sa.Column("actions_blocked", sa.Integer, server_default="0"),
        sa.Column("actions_gated", sa.Integer, server_default="0"),
        sa.Column("suspended", sa.Boolean, server_default="false"),
        sa.Column("suspended_by", sa.String(255), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_reason", sa.String(1024), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON, server_default="{}"),
    )
    op.create_index("ix_openclaw_instance_id", "openclaw_instances", ["instance_id"], unique=True)
    op.create_index("ix_openclaw_trust", "openclaw_instances", ["trust_level"])
    op.create_index("ix_openclaw_suspended", "openclaw_instances", ["suspended"])


def downgrade() -> None:
    op.drop_index("ix_openclaw_suspended", table_name="openclaw_instances")
    op.drop_index("ix_openclaw_trust", table_name="openclaw_instances")
    op.drop_index("ix_openclaw_instance_id", table_name="openclaw_instances")
    op.drop_table("openclaw_instances")
