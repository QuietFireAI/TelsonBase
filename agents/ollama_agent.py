# TelsonBase/agents/ollama_agent.py
# REM: =======================================================================================
# REM: SOVEREIGN AI ENGINE AGENT FOR TELSONBASE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: This is the engine room agent. It wraps core/ollama_service.py
# REM: in the full TelsonBase security framework: signing, capabilities, anomaly detection,
# REM: and approval gates. Every LLM interaction flows through here, monitored and audited.
# REM:
# REM: This agent provides:
# REM:   - Model management (list, pull, delete, info)
# REM:   - Text generation (single prompt → response)
# REM:   - Conversational chat (multi-turn)
# REM:   - Health checking for the Ollama service
# REM:   - Model recommendation for the dashboard
# REM:
# REM: Why a full agent and not just API endpoints?
# REM:   Because in TelsonBase, the engine is monitored like any other tool. If an agent
# REM:   starts pulling models at 3am or running 500 inferences per minute, the anomaly
# REM:   detector catches it. If someone tries to delete a model, it needs approval.
# REM:   The engine isn't above the law — it IS the law, and it follows the law.
# REM:
# REM: QMS Protocol:
# REM:   Ollama_Generate_Please   → Ollama_Generate_Thank_You
# REM:   Ollama_Chat_Please       → Ollama_Chat_Thank_You
# REM:   Ollama_List_Models_Please → Ollama_List_Models_Thank_You
# REM:   Ollama_Pull_Model_Please → Ollama_Pull_Model_Thank_You (requires approval)
# REM:   Ollama_Delete_Model_Please → Ollama_Delete_Model_Thank_You (requires approval)
# REM:   Ollama_Health_Check_Please → Ollama_Health_Check_Thank_You
# REM: =======================================================================================

import logging
from typing import Any, Dict, List, Optional

from agents.base import AgentRequest, AgentResponse, SecureBaseAgent
from core.audit import AuditEventType, audit
from core.config import get_settings
from core.ollama_service import (RECOMMENDED_MODELS, OllamaConnectionError,
                                 OllamaModelError, OllamaService,
                                 OllamaServiceError, get_ollama_service)
from core.qms import QMSStatus, format_qms

settings = get_settings()
logger = logging.getLogger(__name__)


class OllamaAgent(SecureBaseAgent):
    """
    REM: Sovereign AI engine agent.
    REM: All LLM interactions flow through here — monitored, signed, and audited.
    """

    AGENT_NAME = "ollama_agent"

    CAPABILITIES = [
        "ollama.execute:*",                   # Can run any model
        "ollama.manage:list",                  # Can list models
        "ollama.manage:info",                  # Can get model details
        "ollama.manage:pull",                  # Can pull models (with approval)
        "ollama.manage:delete",                # Can delete models (with approval)
        "filesystem.read:/app/prompts/*",      # Can read prompt templates
        "filesystem.write:/app/responses/*",   # Can write response logs
        "external.none",                       # No external network — Ollama is local
    ]

    # REM: Pulling and deleting models are destructive — require human approval
    REQUIRES_APPROVAL_FOR = ["pull_model", "delete_model"]

    # REM: Built-in agent, skip quarantine
    SKIP_QUARANTINE = True

    SUPPORTED_ACTIONS = [
        "generate",          # Single prompt → response
        "chat",              # Multi-turn conversation
        "list_models",       # What's downloaded locally
        "model_info",        # Details about a specific model
        "pull_model",        # Download a new model (requires approval)
        "delete_model",      # Remove a model (requires approval)
        "health_check",      # Is Ollama alive?
        "recommended",       # Curated model list for dashboard
        "set_default",       # Change the default model
    ]

    def __init__(self):
        super().__init__()
        self._service: OllamaService = get_ollama_service()

    def execute(self, request: AgentRequest) -> Optional[Dict[str, Any]]:
        """
        REM: Route request to the appropriate Ollama action.
        REM: This is called by SecureBaseAgent.handle_request() AFTER all
        REM: security checks (signing, capabilities, approval) have passed.
        """
        action = request.action.lower()
        payload = request.payload

        if action not in self.SUPPORTED_ACTIONS:
            raise ValueError(
                f"Unknown action: ::{action}::. "
                f"Supported: {self.SUPPORTED_ACTIONS}"
            )

        try:
            if action == "generate":
                return self._generate(payload)
            elif action == "chat":
                return self._chat(payload)
            elif action == "list_models":
                return self._list_models()
            elif action == "model_info":
                return self._model_info(payload)
            elif action == "pull_model":
                return self._pull_model(payload)
            elif action == "delete_model":
                return self._delete_model(payload)
            elif action == "health_check":
                return self._health_check()
            elif action == "recommended":
                return self._recommended()
            elif action == "set_default":
                return self._set_default(payload)

        except OllamaConnectionError as e:
            logger.error(f"REM: Ollama unreachable: ::{e}::_Thank_You_But_No")
            raise RuntimeError(
                f"Ollama engine unreachable at {self._service.base_url}. "
                "Check that the Ollama container is running."
            )
        except OllamaModelError as e:
            logger.error(f"REM: Model error: ::{e}::_Thank_You_But_No")
            raise ValueError(str(e))
        except OllamaServiceError as e:
            logger.error(f"REM: Ollama service error: ::{e}::_Thank_You_But_No")
            raise RuntimeError(str(e))

    # REM: ==================================================================================
    # REM: INFERENCE ACTIONS
    # REM: ==================================================================================

    def _generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Single prompt → single response.
        REM: QMS: Ollama_Generate_Please with ::prompt:: ::model::
        """
        prompt = payload.get("prompt")
        if not prompt:
            raise ValueError("'prompt' is required for generate action")

        result = self._service.generate(
            prompt=prompt,
            model=payload.get("model"),
            system=payload.get("system"),
            temperature=payload.get("temperature", 0.7),
            max_tokens=payload.get("max_tokens"),
            context=payload.get("context"),
        )

        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms("Ollama_Generate", QMSStatus.THANK_YOU,
                       agent_id=self.AGENT_NAME,
                       request_id=None),
            actor=self.AGENT_NAME,
            details={
                "model": result["model"],
                "prompt_length": len(prompt),
                "response_length": len(result.get("response", "")),
                "tokens_per_second": result.get("tokens_per_second", 0),
            }
        )

        return result

    def _chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Multi-turn conversation.
        REM: QMS: Ollama_Chat_Please with ::messages:: ::model::
        REM:
        REM: Messages format:
        REM:   [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        messages = payload.get("messages")
        if not messages or not isinstance(messages, list):
            raise ValueError("'messages' list is required for chat action")

        # REM: Validate message format
        for msg in messages:
            if "role" not in msg or "content" not in msg:
                raise ValueError("Each message must have 'role' and 'content' fields")
            if msg["role"] not in ("user", "assistant", "system"):
                raise ValueError(f"Invalid role: {msg['role']}. Use user/assistant/system")

        result = self._service.chat(
            messages=messages,
            model=payload.get("model"),
            system=payload.get("system"),
            temperature=payload.get("temperature", 0.7),
            max_tokens=payload.get("max_tokens"),
        )

        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms("Ollama_Chat", QMSStatus.THANK_YOU,
                       agent_id=self.AGENT_NAME,
                       request_id=None),
            actor=self.AGENT_NAME,
            details={
                "model": result["model"],
                "message_count": len(messages),
                "response_length": len(result.get("message", {}).get("content", "")),
                "tokens_per_second": result.get("tokens_per_second", 0),
            }
        )

        return result

    # REM: ==================================================================================
    # REM: MODEL MANAGEMENT ACTIONS
    # REM: ==================================================================================

    def _list_models(self) -> Dict[str, Any]:
        """REM: List all locally available models."""
        models = self._service.list_models()
        return {
            "models": models,
            "count": len(models),
            "default_model": self._service.default_model,
            "qms_status": "Ollama_List_Models_Thank_You",
        }

    def _model_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Get details about a specific model."""
        model = payload.get("model")
        if not model:
            raise ValueError("'model' name is required")
        info = self._service.model_info(model)
        return {
            "info": info,
            "qms_status": "Ollama_Model_Info_Thank_You",
        }

    def _pull_model(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Download a model. Requires human approval.
        REM: QMS: Ollama_Pull_Model_Please ::model_name::
        """
        model = payload.get("model")
        if not model:
            raise ValueError("'model' name is required")

        logger.info(f"REM: Ollama_Pull_Model_Please ::{model}:: (approved)")
        result = self._service.pull_model(model)

        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms("Ollama_Pull_Model", QMSStatus.THANK_YOU,
                       agent_id=self.AGENT_NAME),
            actor=self.AGENT_NAME,
            details={"model": model, "status": result.get("status")}
        )

        return result

    def _delete_model(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        REM: Delete a model. Requires human approval.
        REM: QMS: Ollama_Delete_Model_Please ::model_name::
        """
        model = payload.get("model")
        if not model:
            raise ValueError("'model' name is required")

        logger.info(f"REM: Ollama_Delete_Model_Please ::{model}:: (approved)")
        result = self._service.delete_model(model)

        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms("Ollama_Delete_Model", QMSStatus.THANK_YOU,
                       agent_id=self.AGENT_NAME),
            actor=self.AGENT_NAME,
            details={"model": model}
        )

        return result

    # REM: ==================================================================================
    # REM: HEALTH & DISCOVERY ACTIONS
    # REM: ==================================================================================

    def _health_check(self) -> Dict[str, Any]:
        """REM: Check Ollama engine health."""
        health = self._service.health_check()

        # REM: Also try to list models if healthy for a complete picture
        if health["status"] == "healthy":
            try:
                models = self._service.list_models()
                health["models_available"] = len(models)
                health["model_names"] = [m["name"] for m in models]
            except (ConnectionError, TimeoutError, KeyError, TypeError) as e:
                logger.debug(f"REM: Could not list Ollama models: {e}")
                health["models_available"] = -1

        return health

    def _recommended(self) -> Dict[str, Any]:
        """REM: Return curated model recommendations with availability status."""
        models = self._service.get_recommended_models()
        return {
            "recommended_models": models,
            "count": len(models),
            "default_model": self._service.default_model,
            "qms_status": "Ollama_Recommended_Thank_You",
        }

    def _set_default(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REM: Change the default model."""
        model = payload.get("model")
        if not model:
            raise ValueError("'model' name is required")

        old_default = self._service.default_model
        self._service.default_model = model

        audit.log(
            AuditEventType.AGENT_ACTION,
            format_qms("Ollama_Set_Default", QMSStatus.THANK_YOU,
                       agent_id=self.AGENT_NAME),
            actor=self.AGENT_NAME,
            details={"old_default": old_default, "new_default": model}
        )

        return {
            "old_default": old_default,
            "new_default": model,
            "qms_status": "Ollama_Set_Default_Thank_You",
        }
