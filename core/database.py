# TelsonBase/core/database.py
# REM: =======================================================================================
# REM: POSTGRESQL DATABASE LAYER
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: v6.3.0CC: PostgreSQL foundation for durable structured storage
# REM:
# REM: Mission Statement: Redis is the hot cache. PostgreSQL is the durable store for
# REM: compliance-queryable structured data (audit entries, users, tenants, compliance records).
# REM: =======================================================================================

import logging
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# REM: SQLAlchemy engine with connection pooling
engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

# REM: Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# REM: Declarative base for ORM models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    REM: FastAPI dependency for database sessions.
    REM: Yields a session and ensures cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    REM: Create all tables defined in models.
    REM: Called during application startup.
    """
    try:
        import core.models  # noqa: F401 — ensure models are registered with Base
        Base.metadata.create_all(bind=engine)
        logger.info("REM: PostgreSQL tables initialized_Thank_You")
    except Exception as e:
        logger.warning(f"REM: PostgreSQL not available: {e}_Excuse_Me")


def check_db_health() -> bool:
    """REM: Check PostgreSQL connectivity."""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception:
        return False
