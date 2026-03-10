# TelsonBase/core/sessions.py
# REM: Alias module — routes import from core.sessions, actual impl is core.session_management
# REM: v7.2.0CC: Created to resolve module naming mismatch
from core.session_management import SessionManager, session_manager

__all__ = ["session_manager", "SessionManager"]
