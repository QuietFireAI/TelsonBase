# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
# TelsonBase/api/hermes_routes.py
# REM: =======================================================================================
# REM: HERMES OPERATIONAL API — THE OPERATOR'S AGENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: July 10, 2026
#
# REM: Mission Statement: The runnable surface for Hermes, the operator's native governed
# REM: agent. This is the reference "how an agent is operated on TelsonBase" endpoint set.
# REM:
# REM:   POST /v1/agents/hermes/ask            - reason via the LOCAL sovereign LLM (no gate)
# REM:   POST /v1/agents/hermes/dispatch       - request a cross-agent dispatch (HITL PAUSE)
# REM:   POST /v1/agents/hermes/dispatch/execute - complete a dispatch AFTER human approval
# REM:   GET  /v1/agents/hermes/status         - Hermes's own governance status
# REM:
# REM: Governance: dispatch never runs synchronously — it creates a human approval request
# REM: and returns immediately. The task only sends after a human approves (execute). This
# REM: preserves the HITL guarantee without blocking an HTTP worker.
# REM: =======================================================================================

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from agents.hermes_agent import get_hermes
from agents.base import AgentRequest
from core.auth import AuthResult, authenticate_request, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/agents/hermes", tags=["Hermes"])


class AskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=32000)
    system: Optional[str] = None
    model: Optional[str] = None


class DispatchRequest(BaseModel):
    target_agent: str = Field(..., min_length=1, max_length=100)
    target_action: str = Field(..., min_length=1, max_length=100)
    target_payload: Dict[str, Any] = Field(default_factory=dict)


class DispatchExecuteRequest(BaseModel):
    approval_request_id: str = Field(..., min_length=8)
    target_agent: str = Field(..., min_length=1, max_length=100)
    target_action: str = Field(..., min_length=1, max_length=100)
    target_payload: Dict[str, Any] = Field(default_factory=dict)


@router.post("/ask")
async def hermes_ask(
    request: AskRequest,
    auth: AuthResult = Depends(require_permission("manage:agents")),
):
    """REM: Reason over a prompt with the local sovereign LLM. Read-only, no HITL gate."""
    hermes = get_hermes()
    req = AgentRequest(
        action="ask", requester=auth.actor,
        payload={"prompt": request.prompt, "system": request.system, "model": request.model},
    )
    resp = hermes.handle_request(req)
    return {"success": resp.success, "result": resp.result, "error": resp.error,
            "qms_status": resp.qms_status}


@router.post("/dispatch", status_code=202)
async def hermes_dispatch(
    request: DispatchRequest,
    auth: AuthResult = Depends(require_permission("manage:agents")),
):
    """REM: Request a cross-agent dispatch. Creates a HITL approval and returns immediately.
    REM: Nothing is sent until a human approves and /dispatch/execute is called."""
    hermes = get_hermes()
    return hermes.submit_dispatch(
        payload={"target_agent": request.target_agent,
                 "target_action": request.target_action,
                 "target_payload": request.target_payload},
        requester=auth.actor,
    )


@router.post("/dispatch/execute")
async def hermes_dispatch_execute(
    request: DispatchExecuteRequest,
    auth: AuthResult = Depends(require_permission("manage:agents")),
):
    """REM: Complete a dispatch AFTER a human has approved it. Verifies approval, then sends."""
    hermes = get_hermes()
    return hermes.complete_dispatch(
        approval_request_id=request.approval_request_id,
        payload={"target_agent": request.target_agent,
                 "target_action": request.target_action,
                 "target_payload": request.target_payload},
    )


@router.get("/status")
async def hermes_status(
    auth: AuthResult = Depends(require_permission("view:agents")),
):
    """REM: Hermes's own governance status (trust level, capabilities, pending approvals)."""
    return get_hermes()._status()
