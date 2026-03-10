# TelsonBase/agents/backup_agent.py
# REM: =======================================================================================
# REM: BACKUP AGENT - DEMONSTRATES SECURITY FLOW
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: This agent demonstrates:
# REM:   - Capability-based permissions (can read /data/*, write to /app/backups/*)
# REM:   - Approval gates (delete operations require human approval)
# REM:   - Message signing (inter-agent communication)
# REM:   - Behavioral monitoring (actions are tracked for anomaly detection)
# REM: =======================================================================================

import hashlib
import logging
import os
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from celery import shared_task

logger = logging.getLogger(__name__)

# REM: =======================================================================================
# REM: AGENT CONFIGURATION
# REM: =======================================================================================

AGENT_ID = "backup_agent"

# REM: Capabilities declare what this agent CAN do.
# REM: The system enforces these - attempts to exceed them are blocked and logged.
CAPABILITIES = [
    "filesystem.read:/data/*",
    "filesystem.write:/app/backups/*",
    "filesystem.read:/app/backups/*",
    "external.none",  # REM: This agent has NO external network access
]

# REM: Actions that require human approval before execution
REQUIRES_APPROVAL_FOR = [
    "delete_backup",
    "restore_backup",
]


# REM: =======================================================================================
# REM: CELERY TASKS
# REM: =======================================================================================

@shared_task(name="backup_agent.list_volumes")
def list_volumes() -> Dict[str, Any]:
    """
    REM: List available data volumes that can be backed up.
    REM: No approval required - read-only operation.
    """
    logger.info(f"REM: {AGENT_ID} received: 'list_volumes_Please'")
    
    data_dir = Path("/data")
    volumes = []
    
    if data_dir.exists():
        for item in data_dir.iterdir():
            if item.is_dir():
                size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                volumes.append({
                    "name": item.name,
                    "path": str(item),
                    "size_bytes": size,
                    "size_human": _human_size(size)
                })
    
    logger.info(f"REM: {AGENT_ID} completed: 'list_volumes_Thank_You' - Found {len(volumes)} volumes")
    
    return {
        "status": "success",
        "volumes": volumes,
        "count": len(volumes),
        "qms_status": "Thank_You"
    }


@shared_task(name="backup_agent.create_backup")
def create_backup(volume_name: str, backup_type: str = "manual") -> Dict[str, Any]:
    """
    REM: Create a backup of a specified volume.
    REM: No approval required - non-destructive operation.
    """
    logger.info(f"REM: {AGENT_ID} received: 'create_backup_Please' for volume ::{volume_name}::")
    
    source_path = Path(f"/data/{volume_name}")
    backup_dir = Path("/app/backups") / backup_type
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    if not source_path.exists():
        logger.error(f"REM: {AGENT_ID} error: Volume ::{volume_name}:: not found_Thank_You_But_No")
        return {
            "status": "error",
            "error": f"Volume '{volume_name}' not found",
            "qms_status": "Thank_You_But_No"
        }
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{volume_name}_backup_{timestamp}.tar.gz"
    backup_path = backup_dir / backup_filename
    
    try:
        # REM: Create compressed archive
        with tarfile.open(backup_path, "w:gz") as tar:
            tar.add(source_path, arcname=volume_name)
        
        # REM: Calculate checksum for integrity verification
        checksum = _calculate_checksum(backup_path)
        file_size = backup_path.stat().st_size
        
        logger.info(
            f"REM: {AGENT_ID} completed: 'create_backup_Thank_You' - "
            f"Created ::{backup_filename}:: ($${ _human_size(file_size)}$$)"
        )
        
        return {
            "status": "success",
            "backup_file": str(backup_path),
            "filename": backup_filename,
            "size_bytes": file_size,
            "size_human": _human_size(file_size),
            "checksum_sha256": checksum,
            "timestamp": timestamp,
            "qms_status": "Thank_You"
        }
        
    except Exception as e:
        logger.error(f"REM: {AGENT_ID} error: Backup failed - ::{e}::_Thank_You_But_No")
        return {
            "status": "error",
            "error": str(e),
            "qms_status": "Thank_You_But_No"
        }


@shared_task(name="backup_agent.list_backups")
def list_backups(backup_type: Optional[str] = None) -> Dict[str, Any]:
    """
    REM: List existing backups.
    REM: No approval required - read-only operation.
    """
    logger.info(f"REM: {AGENT_ID} received: 'list_backups_Please'")
    
    backup_root = Path("/app/backups")
    backups = []
    
    if backup_type:
        search_dirs = [backup_root / backup_type]
    else:
        search_dirs = [d for d in backup_root.iterdir() if d.is_dir()] if backup_root.exists() else []
    
    for backup_dir in search_dirs:
        if not backup_dir.exists():
            continue
        for backup_file in backup_dir.glob("*.tar.gz"):
            stat = backup_file.stat()
            backups.append({
                "filename": backup_file.name,
                "path": str(backup_file),
                "type": backup_dir.name,
                "size_bytes": stat.st_size,
                "size_human": _human_size(stat.st_size),
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            })
    
    # REM: Sort by creation time, newest first
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    
    logger.info(f"REM: {AGENT_ID} completed: 'list_backups_Thank_You' - Found {len(backups)} backups")
    
    return {
        "status": "success",
        "backups": backups,
        "count": len(backups),
        "qms_status": "Thank_You"
    }


@shared_task(name="backup_agent.delete_backup")
def delete_backup(backup_path: str, approval_id: Optional[str] = None) -> Dict[str, Any]:
    """
    REM: Delete a backup file.
    REM: REQUIRES APPROVAL - destructive operation.
    
    REM: In production, the orchestrator checks REQUIRES_APPROVAL_FOR before
    REM: allowing this task to execute. The approval_id proves human authorization.
    """
    logger.info(f"REM: {AGENT_ID} received: 'delete_backup_Please' for ::{backup_path}::")
    
    # REM: Verify this is actually in our allowed backup directory
    backup_file = Path(backup_path)
    allowed_root = Path("/app/backups")
    
    try:
        backup_file.relative_to(allowed_root)
    except ValueError:
        logger.error(f"REM: {AGENT_ID} SECURITY: Attempted delete outside backup dir_Thank_You_But_No")
        return {
            "status": "error",
            "error": "Path outside allowed backup directory",
            "qms_status": "Thank_You_But_No"
        }
    
    if not backup_file.exists():
        return {
            "status": "error",
            "error": "Backup file not found",
            "qms_status": "Thank_You_But_No"
        }
    
    try:
        filename = backup_file.name
        backup_file.unlink()
        
        logger.warning(
            f"REM: {AGENT_ID} completed: 'delete_backup_Thank_You' - "
            f"Deleted ::{filename}:: (approval: ::{approval_id}::)"
        )
        
        return {
            "status": "success",
            "deleted": filename,
            "approval_id": approval_id,
            "qms_status": "Thank_You"
        }
        
    except Exception as e:
        logger.error(f"REM: {AGENT_ID} error: Delete failed - ::{e}::_Thank_You_But_No")
        return {
            "status": "error",
            "error": str(e),
            "qms_status": "Thank_You_But_No"
        }


@shared_task(name="backup_agent.verify_backup")
def verify_backup(backup_path: str, expected_checksum: Optional[str] = None) -> Dict[str, Any]:
    """
    REM: Verify backup integrity by checking checksum.
    REM: No approval required - read-only operation.
    """
    logger.info(f"REM: {AGENT_ID} received: 'verify_backup_Please' for ::{backup_path}::")
    
    backup_file = Path(backup_path)
    
    if not backup_file.exists():
        return {
            "status": "error",
            "error": "Backup file not found",
            "qms_status": "Thank_You_But_No"
        }
    
    actual_checksum = _calculate_checksum(backup_file)
    
    if expected_checksum:
        is_valid = actual_checksum == expected_checksum
        status = "valid" if is_valid else "corrupted"
        qms = "Thank_You" if is_valid else "Thank_You_But_No"
        
        logger.info(
            f"REM: {AGENT_ID} completed: 'verify_backup_{qms}' - "
            f"Backup is ::{status}::"
        )
    else:
        status = "calculated"
        qms = "Thank_You"
        logger.info(f"REM: {AGENT_ID} completed: 'verify_backup_Thank_You' - Checksum calculated")
    
    return {
        "status": status,
        "checksum_sha256": actual_checksum,
        "expected": expected_checksum,
        "match": actual_checksum == expected_checksum if expected_checksum else None,
        "qms_status": qms
    }


@shared_task(name="backup_agent.restore_backup")
def restore_backup(
    backup_path: str,
    target_path: Optional[str] = None,
    approval_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    REM: Restore a backup to the original or specified location.
    REM: REQUIRES APPROVAL - potentially destructive operation.

    Args:
        backup_path: Path to the backup archive
        target_path: Optional override destination (defaults to /data/{volume_name})
        approval_id: Required approval ID from human operator
    """
    logger.info(f"REM: {AGENT_ID} received: 'restore_backup_Please' for ::{backup_path}::")

    backup_file = Path(backup_path)
    allowed_root = Path("/app/backups")

    try:
        backup_file.relative_to(allowed_root)
    except ValueError:
        logger.error(f"REM: {AGENT_ID} SECURITY: Restore from outside backup dir_Thank_You_But_No")
        return {
            "status": "error",
            "error": "Backup path outside allowed directory",
            "qms_status": "Thank_You_But_No"
        }

    if not backup_file.exists():
        return {
            "status": "error",
            "error": "Backup file not found",
            "qms_status": "Thank_You_But_No"
        }

    try:
        with tarfile.open(backup_file, "r:gz") as tar:
            members = tar.getnames()
            if not members:
                return {
                    "status": "error",
                    "error": "Empty backup archive",
                    "qms_status": "Thank_You_But_No"
                }

            volume_name = members[0].split("/")[0]
            restore_target = Path(target_path) if target_path else Path(f"/data/{volume_name}")

            restore_target.mkdir(parents=True, exist_ok=True)

            restore_abs = restore_target.resolve()
            for member in tar.getmembers():
                # Reject absolute paths, any '..' component, or paths that escape the target dir
                member_path = (restore_target / member.name).resolve()
                if (member.name.startswith("/")
                        or ".." in Path(member.name).parts
                        or not str(member_path).startswith(str(restore_abs))):
                    logger.error(f"REM: {AGENT_ID} SECURITY: Path traversal attempt_Thank_You_But_No")
                    return {
                        "status": "error",
                        "error": "Archive contains unsafe paths",
                        "qms_status": "Thank_You_But_No"
                    }

            # filter='data' (backported in Python 3.11.4+) provides a second layer of protection
            tar.extractall(path=restore_target.parent, filter='data')

        logger.warning(
            f"REM: {AGENT_ID} completed: 'restore_backup_Thank_You' - "
            f"Restored ::{volume_name}:: to ::{restore_target}:: (approval: ::{approval_id}::)"
        )

        return {
            "status": "success",
            "restored_from": str(backup_file),
            "restored_to": str(restore_target),
            "volume_name": volume_name,
            "approval_id": approval_id,
            "qms_status": "Thank_You"
        }

    except Exception as e:
        logger.error(f"REM: {AGENT_ID} error: Restore failed - ::{e}::_Thank_You_But_No")
        return {
            "status": "error",
            "error": str(e),
            "qms_status": "Thank_You_But_No"
        }


@shared_task(name="backup_agent.apply_retention_policy")
def apply_retention_policy(
    backup_type: str = "manual",
    max_count: int = 10,
    max_age_days: int = 30
) -> Dict[str, Any]:
    """
    REM: Apply retention policy to backups - delete old/excess backups.
    REM: No approval required when invoked by schedule, uses policy rules.

    Args:
        backup_type: Type of backups to apply policy to
        max_count: Maximum number of backups to keep
        max_age_days: Delete backups older than this many days
    """
    logger.info(
        f"REM: {AGENT_ID} received: 'apply_retention_policy_Please' - "
        f"type={backup_type}, max_count={max_count}, max_age_days={max_age_days}"
    )

    backup_dir = Path("/app/backups") / backup_type
    if not backup_dir.exists():
        return {
            "status": "success",
            "deleted_count": 0,
            "message": f"No {backup_type} backups directory exists",
            "qms_status": "Thank_You"
        }

    now = datetime.now(timezone.utc)
    cutoff_date = now - timedelta(days=max_age_days)

    backups = []
    for backup_file in backup_dir.glob("*.tar.gz"):
        stat = backup_file.stat()
        created = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        backups.append({
            "path": backup_file,
            "created": created,
            "size": stat.st_size
        })

    backups.sort(key=lambda x: x["created"], reverse=True)

    to_delete = []

    for backup in backups:
        if backup["created"] < cutoff_date:
            to_delete.append(backup)

    for backup in backups[max_count:]:
        if backup not in to_delete:
            to_delete.append(backup)

    deleted_count = 0
    freed_bytes = 0
    errors = []

    for backup in to_delete:
        try:
            backup["path"].unlink()
            deleted_count += 1
            freed_bytes += backup["size"]
            logger.info(f"REM: {AGENT_ID} retention: Deleted ::{backup['path'].name}::_Thank_You")
        except Exception as e:
            errors.append({"file": backup["path"].name, "error": str(e)})

    logger.info(
        f"REM: {AGENT_ID} completed: 'apply_retention_policy_Thank_You' - "
        f"Deleted {deleted_count} backups, freed {_human_size(freed_bytes)}"
    )

    return {
        "status": "success" if not errors else "partial",
        "deleted_count": deleted_count,
        "freed_bytes": freed_bytes,
        "freed_human": _human_size(freed_bytes),
        "remaining_count": len(backups) - deleted_count,
        "errors": errors if errors else None,
        "qms_status": "Thank_You"
    }


@shared_task(name="backup_agent.scheduled_backup")
def scheduled_backup(volume_name: str, retention_count: int = 7) -> Dict[str, Any]:
    """
    REM: Create a scheduled backup with automatic retention.
    REM: Called by Celery Beat for scheduled backups.
    """
    logger.info(f"REM: {AGENT_ID} received: 'scheduled_backup_Please' for ::{volume_name}::")

    backup_result = create_backup(volume_name, backup_type="scheduled")

    if backup_result["status"] != "success":
        return backup_result

    retention_result = apply_retention_policy(
        backup_type="scheduled",
        max_count=retention_count,
        max_age_days=30
    )

    logger.info(
        f"REM: {AGENT_ID} completed: 'scheduled_backup_Thank_You' - "
        f"Created backup, {retention_result['deleted_count']} old backups cleaned"
    )

    return {
        "status": "success",
        "backup": backup_result,
        "retention": retention_result,
        "qms_status": "Thank_You"
    }


@shared_task(name="backup_agent.get_backup_schedule")
def get_backup_schedule() -> Dict[str, Any]:
    """
    REM: Get current backup schedule configuration.
    """
    return {
        "status": "success",
        "schedules": [
            {
                "name": "daily_backup",
                "volume": "*",
                "cron": "0 2 * * *",
                "retention_count": 7,
                "enabled": True
            },
            {
                "name": "weekly_backup",
                "volume": "*",
                "cron": "0 3 * * 0",
                "retention_count": 4,
                "enabled": True
            }
        ],
        "qms_status": "Thank_You"
    }


@shared_task(name="backup_agent.get_status")
def get_status() -> Dict[str, Any]:
    """
    REM: Get agent status and health information.
    """
    backup_dir = Path("/app/backups")
    total_size = 0
    backup_count = 0
    by_type = {}

    if backup_dir.exists():
        for f in backup_dir.rglob("*.tar.gz"):
            total_size += f.stat().st_size
            backup_count += 1
            backup_type = f.parent.name
            by_type[backup_type] = by_type.get(backup_type, 0) + 1

    return {
        "agent_id": AGENT_ID,
        "status": "healthy",
        "capabilities": CAPABILITIES,
        "requires_approval_for": REQUIRES_APPROVAL_FOR,
        "stats": {
            "total_backups": backup_count,
            "total_size_bytes": total_size,
            "total_size_human": _human_size(total_size),
            "by_type": by_type
        },
        "qms_status": "Thank_You"
    }


# REM: =======================================================================================
# REM: HELPER FUNCTIONS
# REM: =======================================================================================

def _calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
