# TelsonBase/core/hitrust.py
# REM: Alias module — routes import from core.hitrust, actual impl is core.hitrust_controls
# REM: v7.2.0CC: Created to resolve module naming mismatch
from core.hitrust_controls import HITRUSTManager, hitrust_manager

__all__ = ["hitrust_manager", "HITRUSTManager"]
