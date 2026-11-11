# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: MIT
# TelsonBase/agents/hermes_agent.py
# REM: =======================================================================================
# REM: HERMES — THE OPERATOR'S AGENT (THE MESSENGER)
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: July 10, 2026
# REM:
# REM: Mission Statement: Hermes is the operator's own agent — a first-class, TelsonBase-native
# REM: citizen that reasons with the LOCAL sovereign LLM (Ollama) and dispatches work to other
# REM: agents on the operator's behalf. Where OpenClaw is an EXTERNAL autonomous agent that
# REM: TelsonBase must leash, Hermes is the opposite: it is native and law-abiding BY
# REM: CONSTRUCTION. It inherits SecureBaseAgent, so every action it takes is signed,
# REM: capability-checked, trust-gated, anomaly-monitored, and — for anything that reaches
# REM: outside itself — paused for human approval.
# REM:
# REM: Hermes is the reference implementation of "how to build a governed agent on TelsonBase."
# REM:
# REM: Trust posture:
# REM:   Hermes starts at PROBATION, not RESIDENT. It can reason locally immediately, but
# REM:   dispatching an action to another agent (reaching outside itself) is a sensitive
# REM:   operation that PAUSES for a human approval gate. Trust is earned, never assumed —
# REM:   even for the operator's own agent. This is the whole TelsonBase thesis, applied to
# REM:   the tool the operator uses most.
# REM:
# REM: QMS Protocol:
# REM:   Hermes_Ask_Please       -> Hermes_Ask_Thank_You            (reason via local LLM)
# REM:   Hermes_Dispatch_Please  -> (HITL pause) -> Dispatch_Thank_You   (route task to agent)
# REM:   Hermes_Status_Please    -> Hermes_Status_Thank_You         (own governance status)
# REM: =======================================================================================

import logging
from typing import Any, Dict, List, Optional

from agents.base import AgentRequest, SecureBaseAgent
from core.audit import AuditEventType, audit
from core.config import get_settings
from core.qms import QMSStatus, format_qms
from core.trust_levels import AgentTrustLevel, trust_manager

settings = get_settings()
logger = logging.getLogger(__name__)


class HermesAgent(SecureBaseAgent):
    """
    REM: The operator's agent. Reasons locally (Ollama), dispatches under governance.
    REM: Native and law-abiding by construction — the counterpart to the leashed OpenClaw.
    """

    AGENT_NAME = "hermes_agent"

    # REM: Tightly scoped. Hermes reasons via the LOCAL LLM and can message other agents.
    # REM: It has NO direct external access — anything external must route through a governed
    # REM: tool/agent, which carries its own HITL gate. Sovereign by design.
    CAPABILITIES = [
        "ollama.execute:*",                  # Reason with the local sovereign LLM
        "ollama.manage:list",                # See which models are available
        "agent.execute:*",                   # Message other agents (dispatch)
        "filesystem.read:/app/hermes/*",     # Read its own workspace only
        "external.none",                     # No direct external network
    ]

    # REM: Dispatching to another agent reaches OUTSIDE Hermes — it pauses for a human.
    REQUIRES_APPROVAL_FOR = ["dispatch"]

    # REM: Earned trust, not assumed. Hermes starts at PROBATION: it can reason locally
    # REM: right away, but cross-agent dispatch and anything sensitive gates on approval.
    INITIAL_TRUST_LEVEL = AgentTrustLevel.PROBATION
    SKIP_QUARANTINE = False

    SUPPORTED_ACTIONS = ["ask", "dispatch", "status"]

    def __init__(self):
        super().__init__()
        # REM: Lazy Ollama handle — Hermes must be constructable even if the LLM is down,
        # REM: so it can still report status and register with governance.
        self._service = None

    def _ollama(self):
        if self._service is None:
            from core.ollama_service import get_ollama_service
            self._service = get_ollama_service()
        return self._service

    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        """
        REM: Called by SecureBaseAgent.handle_request() AFTER all security checks
        REM: (signing, capability enforcement, trust gating, approval) have passed.
        """
        action = request.action.lower()
        payload = request.payload or {}

        if action not in self.SUPPORTED_ACTIONS:
            raise ValueError(
                f"Unknown action: ::{action}::. Supported: {self.SUPPORTED_ACTIONS}"
            )

        if action == "ask":
            return self._ask(payload)
        if action == "dispatch":
            return self._dispatch(payload)
        if action == "status":
            return self._status()
        return None

    # REM: -----------------------------------------------------------------------------------
    # REM: ACTIONS
    # REM: -----------------------------------------------------------------------------------

    def _ask(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Reason over an operator prompt using the local sovereign LLM. Read-only,
        REM: no side effects, no external calls — safe at PROBATION without approval.
        """
        prompt = (payload.get("prompt") or "").strip()
        if not prompt:
            return {
                "qms": format_qms("Hermes_Ask", QMSStatus.EXCUSE_ME, question="prompt_missing"),
                "message": "No prompt provided.",
            }
        system = payload.get(
            "system",
            "You are Hermes, the operator's local assistant running under TelsonBase "
            "governance. You are sovereign and local. Be concise and truthful.",
        )
        model = payload.get("model")
        try:
            result = self._ollama().generate(prompt=prompt, model=model, system=system)
        except Exception as e:  # noqa: BLE001 — surface the real failure via QMS, don't crash the agent
            logger.error(f"REM: Hermes_Ask_Thank_You_But_No ::llm_error:: ::{e}::")
            return {
                "qms": format_qms("Hermes_Ask", QMSStatus.THANK_YOU_BUT_NO, reason=str(e)),
                "error": str(e),
            }
        return {
            "qms": format_qms("Hermes_Ask", QMSStatus.THANK_YOU),
            "response": result.get("response", ""),
            "model": result.get("model"),
        }

    def _dispatch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Route a task to another agent. This reaches OUTSIDE Hermes, so it is listed in
        REM: REQUIRES_APPROVAL_FOR — SecureBaseAgent.handle_request() will have already
        REM: created the HITL pause before this method is reached on an approved request.
        REM: The message to the target agent is cryptographically signed.
        """
        target = (payload.get("target_agent") or "").strip()
        target_action = (payload.get("target_action") or "").strip()
        target_payload = payload.get("target_payload") or {}
        if not target or not target_action:
            return {
                "qms": format_qms(
                    "Hermes_Dispatch", QMSStatus.EXCUSE_ME,
                    question="target_agent_or_action_missing",
                ),
                "message": "Both target_agent and target_action are required.",
            }
        signed = self.send_to_agent(target, target_action, target_payload)
        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Hermes dispatched ::{target_action}:: to @@{target}@@",
            actor=self.agent_name,
            details={"target_agent": target, "target_action": target_action},
        )
        return {
            "qms": format_qms(
                "Hermes_Dispatch", QMSStatus.THANK_YOU, target=target,
            ),
            "target_agent": target,
            "target_action": target_action,
            "signed_message_id": getattr(signed, "message_id", None),
        }

    # REM: -----------------------------------------------------------------------------------
    # REM: NON-BLOCKING DISPATCH (for the API operational surface)
    # REM: -----------------------------------------------------------------------------------
    # REM: handle_request()'s dispatch path BLOCKS on wait_for_decision — correct for
    # REM: programmatic/inter-agent use, wrong for an HTTP request that must not hang for
    # REM: hours awaiting a human. These two methods mirror the Foreman's propose/execute
    # REM: pattern: submit creates the HITL pause and returns immediately; complete verifies
    # REM: the human approved, then actually sends. The governance guarantee is preserved.

    def submit_dispatch(self, payload: Dict[str, Any], requester: str = "operator") -> Dict[str, Any]:
        """REM: Create the HITL approval for a dispatch and return immediately (non-blocking)."""
        from core.approval import approval_gate, ApprovalRule, ApprovalPriority
        target = (payload.get("target_agent") or "").strip()
        target_action = (payload.get("target_action") or "").strip()
        if not target or not target_action:
            return {
                "status": "error",
                "qms": format_qms("Hermes_Dispatch", QMSStatus.EXCUSE_ME,
                                  question="target_agent_or_action_missing"),
                "message": "Both target_agent and target_action are required.",
            }
        rule = approval_gate.check_requires_approval(
            agent_id=self.agent_name, action="dispatch", payload=payload
        ) or ApprovalRule(
            rule_id=f"rule-requires-approval-{self.agent_name}-dispatch",
            name=f"Required approval: {self.agent_name}.dispatch",
            description="Hermes cross-agent dispatch always requires human approval",
            agent_pattern=self.agent_name, action_pattern="dispatch",
            priority=ApprovalPriority.HIGH, timeout_seconds=3600,
        )
        req = approval_gate.create_request(
            agent_id=self.agent_name, action="dispatch",
            description=f"Hermes wants to dispatch ::{target_action}:: to @@{target}@@",
            payload=payload, rule=rule,
            risk_factors=["cross_agent_dispatch", f"target:{target}"],
        )
        audit.log(
            AuditEventType.AGENT_ACTION,
            f"Hermes dispatch PENDING approval ::{target_action}:: -> @@{target}@@",
            actor=self.agent_name,
            details={"target_agent": target, "target_action": target_action,
                     "approval_request_id": req.request_id, "requester": requester},
        )
        return {
            "status": "pending_approval",
            "qms": format_qms("Hermes_Dispatch", QMSStatus.PRETTY_PLEASE, target=target),
            "approval_request_id": req.request_id,
            "message": (f"Dispatch to '{target}' requires human approval. "
                        f"Request {req.request_id} created. Approve, then call execute."),
        }

    def complete_dispatch(self, approval_request_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: After a human approves, verify and actually send the signed dispatch."""
        from core.approval import approval_gate, ApprovalStatus
        if not approval_request_id:
            return {
                "status": "error",
                "qms": format_qms("Hermes_Dispatch", QMSStatus.THANK_YOU_BUT_NO,
                                  reason="no_approval_id"),
                "message": "A valid approved approval_request_id is required.",
            }
        info = approval_gate.get_approval_status(approval_request_id)
        if not info:
            return {"status": "error",
                    "qms": format_qms("Hermes_Dispatch", QMSStatus.THANK_YOU_BUT_NO,
                                      reason="approval_not_found"),
                    "message": f"Approval '{approval_request_id}' not found."}
        if info["status"] != ApprovalStatus.APPROVED.value:
            audit.log(
                AuditEventType.SECURITY_ALERT,
                f"Blocked Hermes dispatch without approval: status={info['status']}",
                actor=self.agent_name, details={"approval_id": approval_request_id},
            )
            return {"status": "error",
                    "qms": format_qms("Hermes_Dispatch", QMSStatus.THANK_YOU_BUT_NO,
                                      reason="not_approved"),
                    "message": f"Approval '{approval_request_id}' is not approved "
                               f"(status: {info['status']})."}
        return self._dispatch(payload)

    def _status(self) -> Dict[str, Any]:
        """REM: Report Hermes's own governance status. Read-only, always safe."""
        level = trust_manager.get_trust_level(self.agent_name)
        hb = self.heartbeat()
        return {
            "qms": format_qms("Hermes_Status", QMSStatus.THANK_YOU),
            "agent_name": self.agent_name,
            "trust_level": level.value,
            "capabilities_count": hb.get("capabilities_count", 0),
            "signing_key_registered": hb.get("signing_key_registered", False),
            "pending_approvals": len(self.get_pending_approvals()),
        }


# REM: Module-level singleton, mirroring the other agents.
_hermes: Optional[HermesAgent] = None


def get_hermes() -> HermesAgent:
    global _hermes
    if _hermes is None:
        _hermes = HermesAgent()
    return _hermes
