# TelsonBase/core/breach.py
# REM: Alias module — routes import from core.breach, actual impl is core.breach_notification
# REM: v7.2.0CC: Created to resolve module naming mismatch
from core.breach_notification import (BreachAssessment, BreachManager,
                                      BreachSeverity, NotificationRecord)

breach_manager = BreachManager()

__all__ = ["breach_manager", "BreachManager", "BreachAssessment", "BreachSeverity", "NotificationRecord"]
