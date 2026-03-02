# TelsonBase/celery_app/worker.py
# REM: =======================================================================================
# REM: CELERY WORKER CONFIGURATION FOR THE TelsonBase
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: This is the Celery application configuration. It defines the
# REM: distributed task queue that powers agent execution. Workers pick up tasks from
# REM: Redis and execute them asynchronously.
# REM: =======================================================================================

import logging
from celery import Celery
from celery.schedules import crontab
from core.config import get_settings

settings = get_settings()

# REM: Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# REM: Create the Celery application
app = Celery(
    "telsonbase",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        # REM: List all agent modules that contain Celery tasks
        "agents.backup_agent",
        "agents.demo_agent",
        "agents.memory_agent",
        "agents.transaction_agent",
        "agents.compliance_check_agent",
        "agents.doc_prep_agent",
        "toolroom.foreman",
    ]
)

# REM: Celery configuration
app.conf.update(
    # REM: Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # REM: Result expiration (keep results for 24 hours)
    result_expires=86400,
    
    # REM: Worker settings
    worker_prefetch_multiplier=1,  # Don't prefetch tasks (fair scheduling)
    worker_concurrency=2,  # Adjust based on available resources
    
    # REM: Task acknowledgment - don't ack until task completes
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # REM: Task routing (can be expanded for agent-specific queues)
    task_routes={
        "backup_agent.*": {"queue": "backup"},
        "foreman_agent.*": {"queue": "toolroom"},
        "*": {"queue": "default"},
    },
    
    # REM: Beat schedule for automated tasks
    beat_schedule={
        # REM: Daily backup at 2:00 AM UTC
        "daily-backup": {
            "task": "backup_agent.scheduled_backup",
            "schedule": crontab(hour=2, minute=0),
            "args": ["daily"],
            "options": {"queue": "backup"}
        },
        # REM: Foreman daily GitHub update check at 3:00 AM UTC
        # REM: Checks APPROVED_GITHUB_SOURCES for updates, proposes to HITL.
        # REM: Does NOT auto-install — all installs require human approval.
        "foreman-daily-update-check": {
            "task": "foreman_agent.daily_update_check",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "toolroom"}
        },
        # REM: Transaction agent — check deadlines at 7:00 AM UTC daily
        "transaction-deadline-check": {
            "task": "transaction_agent.check_deadlines",
            "schedule": crontab(hour=7, minute=0),
            "args": [7],  # 7-day lookahead
            "options": {"queue": "default"}
        },
        # REM: Compliance agent — daily license/CE sweep at 7:30 AM UTC
        "compliance-daily-check": {
            "task": "compliance_check_agent.daily_check",
            "schedule": crontab(hour=7, minute=30),
            "options": {"queue": "default"}
        },
    }
)

# REM: Signal handlers for startup/shutdown logging
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    logger.info("REM: Celery Beat scheduler configured_Thank_You")


@app.task(bind=True, name="celery.ping")
def ping(self):
    """REM: Simple ping task for health checks."""
    return "pong"


logger.info("REM: Celery worker application initialized_Thank_You")
