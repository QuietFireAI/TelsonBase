# TelsonBase/core/retention.py
# REM: Alias module — routes import from core.retention, actual impl is core.data_retention
# REM: v7.2.0CC: Created to resolve module naming mismatch
from core.data_retention import (DeletionRequest, RetentionManager,
                                 RetentionPolicy)

retention_manager = RetentionManager()

__all__ = ["retention_manager", "RetentionManager", "RetentionPolicy", "DeletionRequest"]
