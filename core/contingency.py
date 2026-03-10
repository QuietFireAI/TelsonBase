# TelsonBase/core/contingency.py
# REM: Alias module — routes import from core.contingency, actual impl is core.contingency_testing
# REM: v7.2.0CC: Created to resolve module naming mismatch
from core.contingency_testing import (ContingencyTest, ContingencyTestManager,
                                      contingency_manager)

__all__ = ["contingency_manager", "ContingencyTestManager", "ContingencyTest"]
