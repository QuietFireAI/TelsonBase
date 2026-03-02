# TelsonBase/api/__init__.py
# REM: API module exports

from api.n8n_integration import router as n8n_router
from api.security_routes import router as security_router
from api.compliance_routes import router as compliance_router
from api.tenancy_routes import router as tenancy_router

__all__ = ["n8n_router", "security_router", "compliance_router", "tenancy_router"]
