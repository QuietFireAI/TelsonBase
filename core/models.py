# TelsonBase/core/models.py
# REM: =======================================================================================
# REM: SQLALCHEMY ORM MODELS FOR POSTGRESQL
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM: v6.3.0CC: Foundation models for durable compliance storage
# REM: =======================================================================================

from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, Index, Integer,
                        String, Text)

from core.database import Base


class UserModel(Base):
    """REM: Durable user records for compliance auditing."""
    __tablename__ = "users"

    user_id = Column(String(64), primary_key=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    roles = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, default=True)
    mfa_enabled = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True), nullable=True)


class AuditEntryModel(Base):
    """REM: Durable audit log entries for compliance queries and legal discovery."""
    __tablename__ = "audit_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sequence = Column(Integer, nullable=False)
    chain_id = Column(String(32), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    message = Column(Text, nullable=False)
    actor = Column(String(255), nullable=False, index=True)
    actor_type = Column(String(32), default="system")
    resource = Column(String(255), nullable=True)
    details = Column(JSON, default=dict)
    entry_hash = Column(String(64), nullable=False)
    previous_hash = Column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_audit_chain_sequence", "chain_id", "sequence"),
    )


class TenantModel(Base):
    """REM: Durable tenant records for multi-tenancy management."""
    __tablename__ = "tenants"

    tenant_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    tenant_type = Column(String(32), nullable=False)
    is_active = Column(Boolean, default=True)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deactivated_at = Column(DateTime(timezone=True), nullable=True)


class ComplianceRecordModel(Base):
    """
    REM: Generic compliance record for legal holds, breach assessments,
    REM: BAAs, sanctions, training, and other regulatory data.
    REM: Uses JSON data column for flexible schema per record_type.
    """
    __tablename__ = "compliance_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_type = Column(String(64), nullable=False, index=True)
    record_id = Column(String(64), nullable=False, unique=True, index=True)
    tenant_id = Column(String(64), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="active")
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_compliance_type_tenant", "record_type", "tenant_id"),
    )


class AgentIdentityModel(Base):
    """
    REM: v7.3.0CC — Durable storage for W3C DID-based agent identities.
    REM: Redis is the hot cache; PostgreSQL is the durable store for compliance
    REM: queries and legal discovery.
    """
    __tablename__ = "agent_identities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    did = Column(String(512), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    public_key_hex = Column(String(128), nullable=False)
    did_document_json = Column(JSON, nullable=False, default=dict)
    active_credentials = Column(JSON, default=list)
    telsonbase_permissions = Column(JSON, default=list)
    trust_level = Column(String(32), default="quarantine")
    registered_at = Column(DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, default=False)
    revoked_by = Column(String(255), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(String(1024), nullable=True)
    manners_md_path = Column(String(512), nullable=True)
    profession_md_path = Column(String(512), nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_agent_identities_trust", "trust_level"),
    )


class OpenClawInstanceModel(Base):
    """
    REM: v7.4.0CC — Durable storage for governed OpenClaw instances.
    REM: Redis is the hot cache; PostgreSQL is the durable store for compliance
    REM: queries, trust level auditing, and legal discovery.
    """
    __tablename__ = "openclaw_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    trust_level = Column(String(32), default="quarantine")
    api_key_hash = Column(String(128), nullable=False)
    allowed_tools = Column(JSON, default=list)
    blocked_tools = Column(JSON, default=list)
    manners_score = Column(Float, default=1.0)
    action_count = Column(Integer, default=0)
    actions_allowed = Column(Integer, default=0)
    actions_blocked = Column(Integer, default=0)
    actions_gated = Column(Integer, default=0)
    suspended = Column(Boolean, default=False)
    suspended_by = Column(String(255), nullable=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    suspended_reason = Column(String(1024), nullable=True)
    registered_at = Column(DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    last_action_at = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_openclaw_trust", "trust_level"),
        Index("ix_openclaw_suspended", "suspended"),
    )
