# TelsonBase/core/phi.py
# REM: Alias module — routes import from core.phi using phi_manager,
# REM: actual impl is core.phi_disclosure using phi_disclosure_manager
# REM: v7.2.0CC: Created to resolve module naming + variable naming mismatch
from core.phi_disclosure import PHIDisclosureManager, PHIDisclosureRecord
from core.phi_disclosure import phi_disclosure_manager as phi_manager

__all__ = ["phi_manager", "PHIDisclosureManager", "PHIDisclosureRecord"]
