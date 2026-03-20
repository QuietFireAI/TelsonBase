# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_ollama_agent_depth.py
# REM: Depth coverage for agents/ollama_agent.py
# REM: Tests: execute routing, action implementations, error mapping, constants.

import pytest
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def agent_with_mock_service():
    """REM: OllamaAgent with _service mocked — bypasses __init__ to avoid Ollama connection."""
    from agents.ollama_agent import OllamaAgent
    agent = object.__new__(OllamaAgent)
    agent._service = MagicMock()
    return agent


def _request(action, **payload_kwargs):
    """REM: Build a minimal AgentRequest-like object."""
    req = MagicMock()
    req.action = action
    req.payload = dict(payload_kwargs)
    return req


# ═══════════════════════════════════════════════════════════════════════════════
# CLASS ATTRIBUTES
# ═══════════════════════════════════════════════════════════════════════════════

class TestOllamaAgentAttributes:
    def test_agent_name(self):
        from agents.ollama_agent import OllamaAgent
        assert OllamaAgent.AGENT_NAME == "ollama_agent"

    def test_skip_quarantine(self):
        from agents.ollama_agent import OllamaAgent
        assert OllamaAgent.SKIP_QUARANTINE is True

    def test_requires_approval_for(self):
        from agents.ollama_agent import OllamaAgent
        assert "pull_model" in OllamaAgent.REQUIRES_APPROVAL_FOR
        assert "delete_model" in OllamaAgent.REQUIRES_APPROVAL_FOR

    def test_supported_actions(self):
        from agents.ollama_agent import OllamaAgent
        expected = {"generate", "chat", "list_models", "model_info",
                    "pull_model", "delete_model", "health_check", "recommended", "set_default"}
        assert set(OllamaAgent.SUPPORTED_ACTIONS) == expected

    def test_capabilities_include_ollama_execute(self):
        from agents.ollama_agent import OllamaAgent
        assert "ollama.execute:*" in OllamaAgent.CAPABILITIES


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTE — ROUTING
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteRouting:
    def test_unknown_action_raises_value_error(self, agent_with_mock_service):
        with pytest.raises(ValueError, match="Unknown action"):
            agent_with_mock_service.execute(_request("fly_to_moon"))

    def test_routes_to_generate(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with patch.object(agent, "_generate", return_value={"ok": True}) as mock_gen:
            agent.execute(_request("generate", prompt="Hello"))
        mock_gen.assert_called_once()

    def test_routes_to_chat(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with patch.object(agent, "_chat", return_value={"ok": True}) as mock_chat:
            agent.execute(_request("chat", messages=[{"role": "user", "content": "Hi"}]))
        mock_chat.assert_called_once()

    def test_routes_to_list_models(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with patch.object(agent, "_list_models", return_value={"models": []}) as mock_lm:
            agent.execute(_request("list_models"))
        mock_lm.assert_called_once()

    def test_routes_to_model_info(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with patch.object(agent, "_model_info", return_value={"info": {}}) as mock_mi:
            agent.execute(_request("model_info", model="gemma2:9b"))
        mock_mi.assert_called_once()

    def test_routes_to_pull_model(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with patch.object(agent, "_pull_model", return_value={"status": "success"}) as mock_pm:
            agent.execute(_request("pull_model", model="llama3.2:3b"))
        mock_pm.assert_called_once()

    def test_routes_to_delete_model(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with patch.object(agent, "_delete_model", return_value={"status": "deleted"}) as mock_dm:
            agent.execute(_request("delete_model", model="old:model"))
        mock_dm.assert_called_once()

    def test_routes_to_health_check(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with patch.object(agent, "_health_check", return_value={"status": "healthy"}) as mock_hc:
            agent.execute(_request("health_check"))
        mock_hc.assert_called_once()

    def test_routes_to_recommended(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with patch.object(agent, "_recommended", return_value={"recommended_models": []}) as mock_r:
            agent.execute(_request("recommended"))
        mock_r.assert_called_once()

    def test_routes_to_set_default(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with patch.object(agent, "_set_default", return_value={"old_default": "x", "new_default": "y"}) as mock_sd:
            agent.execute(_request("set_default", model="phi3:mini"))
        mock_sd.assert_called_once()

    def test_action_case_insensitive(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with patch.object(agent, "_health_check", return_value={"status": "healthy"}) as mock_hc:
            agent.execute(_request("Health_Check"))
        mock_hc.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTE — ERROR MAPPING
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteErrorMapping:
    def test_ollama_connection_error_maps_to_runtime_error(self, agent_with_mock_service):
        from core.ollama_service import OllamaConnectionError
        agent = agent_with_mock_service
        with patch.object(agent, "_health_check", side_effect=OllamaConnectionError("refused")):
            with pytest.raises(RuntimeError, match="unreachable"):
                agent.execute(_request("health_check"))

    def test_ollama_model_error_maps_to_value_error(self, agent_with_mock_service):
        from core.ollama_service import OllamaModelError
        agent = agent_with_mock_service
        with patch.object(agent, "_model_info", side_effect=OllamaModelError("not found")):
            with pytest.raises(ValueError):
                agent.execute(_request("model_info", model="missing:model"))

    def test_ollama_service_error_maps_to_runtime_error(self, agent_with_mock_service):
        from core.ollama_service import OllamaServiceError
        agent = agent_with_mock_service
        with patch.object(agent, "_generate", side_effect=OllamaServiceError("generic fail")):
            with pytest.raises(RuntimeError):
                agent.execute(_request("generate", prompt="test"))


# ═══════════════════════════════════════════════════════════════════════════════
# _GENERATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerate:
    def test_missing_prompt_raises_value_error(self, agent_with_mock_service):
        agent = agent_with_mock_service
        with pytest.raises(ValueError, match="prompt"):
            agent._generate({})

    def test_calls_service_generate(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.generate.return_value = {
            "model": "gemma2:9b", "response": "Hello!", "tokens_per_second": 10.0
        }
        result = agent._generate({"prompt": "Say hello"})
        agent._service.generate.assert_called_once()
        assert result["response"] == "Hello!"

    def test_passes_optional_params(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.generate.return_value = {
            "model": "phi3:mini", "response": "Hi", "tokens_per_second": 15.0
        }
        agent._generate({
            "prompt": "test",
            "model": "phi3:mini",
            "system": "Be concise",
            "temperature": 0.3,
            "max_tokens": 50,
            "context": [1, 2, 3],
        })
        call_kwargs = agent._service.generate.call_args[1]
        assert call_kwargs["model"] == "phi3:mini"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 50


# ═══════════════════════════════════════════════════════════════════════════════
# _CHAT
# ═══════════════════════════════════════════════════════════════════════════════

class TestChat:
    def test_missing_messages_raises(self, agent_with_mock_service):
        with pytest.raises(ValueError, match="messages"):
            agent_with_mock_service._chat({})

    def test_messages_not_list_raises(self, agent_with_mock_service):
        with pytest.raises(ValueError):
            agent_with_mock_service._chat({"messages": "not a list"})

    def test_message_missing_role_raises(self, agent_with_mock_service):
        with pytest.raises(ValueError):
            agent_with_mock_service._chat({"messages": [{"content": "hi"}]})

    def test_message_missing_content_raises(self, agent_with_mock_service):
        with pytest.raises(ValueError):
            agent_with_mock_service._chat({"messages": [{"role": "user"}]})

    def test_invalid_role_raises(self, agent_with_mock_service):
        with pytest.raises(ValueError, match="role"):
            agent_with_mock_service._chat({
                "messages": [{"role": "robot", "content": "beep"}]
            })

    def test_valid_roles(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.chat.return_value = {
            "model": "gemma2:9b",
            "message": {"role": "assistant", "content": "Fine thanks"},
            "tokens_per_second": 8.0,
        }
        for role in ("user", "assistant", "system"):
            agent._generate = MagicMock()
            agent._service.chat.return_value = {
                "model": "gemma2:9b",
                "message": {"role": "assistant", "content": "ok"},
                "tokens_per_second": 5.0,
            }
            result = agent._chat({"messages": [{"role": role, "content": "test"}]})
            assert "message" in result

    def test_calls_service_chat(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.chat.return_value = {
            "model": "gemma2:9b",
            "message": {"role": "assistant", "content": "Greetings"},
            "tokens_per_second": 12.0,
        }
        result = agent._chat({
            "messages": [{"role": "user", "content": "Hello"}],
            "system": "Be helpful",
            "temperature": 0.5,
            "max_tokens": 100,
        })
        agent._service.chat.assert_called_once()
        assert result["message"]["content"] == "Greetings"


# ═══════════════════════════════════════════════════════════════════════════════
# _LIST_MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class TestListModels:
    def test_returns_count_and_models(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.list_models.return_value = [
            {"name": "gemma2:9b"}, {"name": "llama3.2:3b"}
        ]
        agent._service.default_model = "gemma2:9b"
        result = agent._list_models()
        assert result["count"] == 2
        assert result["default_model"] == "gemma2:9b"
        assert "models" in result

    def test_empty_list(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.list_models.return_value = []
        agent._service.default_model = "gemma2:9b"
        result = agent._list_models()
        assert result["count"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# _MODEL_INFO
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelInfo:
    def test_missing_model_raises(self, agent_with_mock_service):
        with pytest.raises(ValueError, match="model"):
            agent_with_mock_service._model_info({})

    def test_returns_info(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.model_info.return_value = {"family": "llama", "parameter_size": "3B"}
        result = agent._model_info({"model": "llama3.2:3b"})
        assert "info" in result
        assert result["info"]["family"] == "llama"


# ═══════════════════════════════════════════════════════════════════════════════
# _PULL_MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestPullModel:
    def test_missing_model_raises(self, agent_with_mock_service):
        with pytest.raises(ValueError):
            agent_with_mock_service._pull_model({})

    def test_calls_service_pull(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.pull_model.return_value = {"model": "llama3.2:3b", "status": "success"}
        result = agent._pull_model({"model": "llama3.2:3b"})
        agent._service.pull_model.assert_called_once_with("llama3.2:3b")
        assert result["status"] == "success"


# ═══════════════════════════════════════════════════════════════════════════════
# _DELETE_MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeleteModel:
    def test_missing_model_raises(self, agent_with_mock_service):
        with pytest.raises(ValueError):
            agent_with_mock_service._delete_model({})

    def test_calls_service_delete(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.delete_model.return_value = {"model": "old:model", "status": "deleted"}
        result = agent._delete_model({"model": "old:model"})
        agent._service.delete_model.assert_called_once_with("old:model")
        assert result["status"] == "deleted"


# ═══════════════════════════════════════════════════════════════════════════════
# _HEALTH_CHECK
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthCheck:
    def test_healthy_with_models(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.health_check.return_value = {"status": "healthy"}
        agent._service.list_models.return_value = [{"name": "gemma2:9b"}, {"name": "llama3.2:3b"}]
        result = agent._health_check()
        assert result["status"] == "healthy"
        assert result["models_available"] == 2

    def test_healthy_list_models_error_returns_minus_one(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.health_check.return_value = {"status": "healthy"}
        agent._service.list_models.side_effect = ConnectionError("no conn")
        result = agent._health_check()
        assert result["status"] == "healthy"
        assert result["models_available"] == -1

    def test_unhealthy_does_not_list_models(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.health_check.return_value = {"status": "unreachable"}
        result = agent._health_check()
        agent._service.list_models.assert_not_called()
        assert result["status"] == "unreachable"


# ═══════════════════════════════════════════════════════════════════════════════
# _RECOMMENDED
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecommended:
    def test_returns_list_and_count(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.get_recommended_models.return_value = [
            {"name": "gemma2:9b", "is_downloaded": True},
            {"name": "llama3.2:3b", "is_downloaded": False},
        ]
        agent._service.default_model = "gemma2:9b"
        result = agent._recommended()
        assert result["count"] == 2
        assert result["default_model"] == "gemma2:9b"
        assert "recommended_models" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _SET_DEFAULT
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetDefault:
    def test_missing_model_raises(self, agent_with_mock_service):
        with pytest.raises(ValueError):
            agent_with_mock_service._set_default({})

    def test_updates_service_default_and_returns_old_new(self, agent_with_mock_service):
        agent = agent_with_mock_service
        agent._service.default_model = "gemma2:9b"
        result = agent._set_default({"model": "llama3.2:3b"})
        assert result["old_default"] == "gemma2:9b"
        assert result["new_default"] == "llama3.2:3b"
        assert agent._service.default_model == "llama3.2:3b"
