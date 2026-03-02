# TelsonBase/core/legal_holds.py
# REM: Alias module — routes import from core.legal_holds, actual impl is core.legal_hold
# REM: v7.2.0CC: Created to resolve module naming mismatch + create singleton instance
from core.legal_hold import HoldManager, LegalHold

legal_hold_manager = HoldManager()

__all__ = ["legal_hold_manager", "HoldManager", "LegalHold"]
