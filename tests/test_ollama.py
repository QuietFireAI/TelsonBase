# TelsonBase/tests/test_ollama.py
# REM: =======================================================================================
# REM: TEST SUITE — OLLAMA SERVICE & LLM ENGINE ENDPOINTS
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Tests the three layers:
# REM:   1. core/ollama_service.py — Direct HTTP to Ollama REST API
# REM:   2. agents/ollama_agent.py — SecureAgent wrapper
# REM:   3. main.py /v1/llm/* endpoints — API surface
# REM:
# REM: All tests mock httpx responses — no live Ollama required.
# REM: =======================================================================================

import pytest
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
from datetime import datetime, timezone

# REM: =====================================================================
# REM: LAYER 1: OllamaService unit tests
# REM: =====================================================================


class TestOllamaServiceInit:
    """REM: Test service initialization and configuration."""
    
    def test_service_creates_with_default_url(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        assert svc.base_url == "http://test:11434"
    
    def test_service_strips_trailing_slash(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434/")
        assert svc.base_url == "http://test:11434"
    
    def test_default_model_is_gemma2(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        assert svc.default_model == "gemma2:9b"
    
    def test_default_model_can_be_changed(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        svc.default_model = "llama3.2:3b"
        assert svc.default_model == "llama3.2:3b"


class TestOllamaServiceHealthCheck:
    """REM: Test health check against Ollama REST API."""
    
    def test_healthy_when_ollama_responds_200(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            result = svc.health_check()
            assert result["status"] == "healthy"
            assert "latency_ms" in result
            assert result["qms_status"] == "Ollama_Health_Check_Thank_You"
    
    def test_unhealthy_when_ollama_returns_error(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            result = svc.health_check()
            assert result["status"] == "unhealthy"
    
    def test_unreachable_when_connection_refused(self):
        import httpx
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            result = svc.health_check()
            assert result["status"] == "unreachable"
            assert "Connection refused" in result["error"]
    
    def test_is_healthy_returns_boolean(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            assert svc.is_healthy() is True


class TestOllamaServiceModels:
    """REM: Test model management operations."""
    
    def test_list_models_returns_sorted(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "mistral:7b", "size": 4400000000, "modified_at": "2024-01-01", "digest": "abc123def456"},
                {"name": "gemma2:9b", "size": 5800000000, "modified_at": "2024-01-02", "digest": "def456abc123"},
            ]
        }
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            models = svc.list_models()
            assert len(models) == 2
            # Default model should sort first
            assert models[0]["name"] == "gemma2:9b"
            assert models[0]["is_default"] is True
            assert models[0]["is_recommended"] is True
    
    def test_list_models_shows_custom_models(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "my-custom-model:latest", "size": 1000000, "modified_at": "2024-01-01", "digest": "custom123"},
            ]
        }
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            models = svc.list_models()
            assert models[0]["is_recommended"] is False
            assert models[0]["tier"] == "custom"
    
    def test_model_info_returns_details(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "details": {
                "family": "gemma2",
                "parameter_size": "9B",
                "quantization_level": "Q4_K_M",
                "format": "gguf",
            },
            "template": "{{ .System }}\n{{ .Prompt }}",
            "system": "You are a helpful assistant.",
        }
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            info = svc.model_info("gemma2:9b")
            assert info["family"] == "gemma2"
            assert info["parameter_size"] == "9B"
    
    def test_model_info_404_raises(self):
        from core.ollama_service import OllamaService, OllamaModelError
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            with pytest.raises(OllamaModelError):
                svc.model_info("nonexistent:model")
    
    def test_pull_model_success(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            result = svc.pull_model("gemma2:9b")
            assert result["model"] == "gemma2:9b"
            assert result["qms_status"] == "Ollama_Pull_Model_Thank_You"
    
    def test_delete_model_success(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            result = svc.delete_model("old-model:latest")
            assert result["status"] == "deleted"
    
    def test_delete_model_404_raises(self):
        from core.ollama_service import OllamaService, OllamaModelError
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            with pytest.raises(OllamaModelError):
                svc.delete_model("nonexistent:model")


class TestOllamaServiceGenerate:
    """REM: Test text generation."""
    
    def test_generate_returns_response(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": "The capital of France is Paris.",
            "done": True,
            "context": [1, 2, 3],
            "total_duration": 500000000,
            "eval_count": 8,
            "eval_duration": 200000000,
        }
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            result = svc.generate("What is the capital of France?")
            assert result["response"] == "The capital of France is Paris."
            assert result["done"] is True
            assert result["model"] == "gemma2:9b"  # default
            assert result["tokens_per_second"] > 0
            assert result["qms_status"] == "Ollama_Generate_Thank_You"
    
    def test_generate_with_custom_model(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": "Paris", "done": True,
            "total_duration": 100000000, "eval_count": 1, "eval_duration": 50000000,
        }
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            result = svc.generate("Capital of France?", model="llama3.2:3b")
            assert result["model"] == "llama3.2:3b"
            # Verify the payload sent to httpx
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["model"] == "llama3.2:3b"
    
    def test_generate_model_not_found_raises(self):
        from core.ollama_service import OllamaService, OllamaModelError
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            with pytest.raises(OllamaModelError):
                svc.generate("test", model="nonexistent:model")
    
    def test_generate_connection_refused_raises(self):
        import httpx
        from core.ollama_service import OllamaService, OllamaConnectionError
        svc = OllamaService(base_url="http://test:11434")
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            with pytest.raises(OllamaConnectionError):
                svc.generate("test")
    
    def test_generate_includes_system_prompt(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": "test", "done": True,
            "total_duration": 100000000, "eval_count": 1, "eval_duration": 50000000,
        }
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            svc.generate("test", system="You are a pirate.")
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["system"] == "You are a pirate."


class TestOllamaServiceChat:
    """REM: Test multi-turn chat."""
    
    def test_chat_returns_message(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Hello! How can I help?"},
            "done": True,
            "total_duration": 300000000,
            "eval_count": 6,
            "eval_duration": 150000000,
        }
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            result = svc.chat([{"role": "user", "content": "Hi"}])
            assert result["message"]["role"] == "assistant"
            assert result["message"]["content"] == "Hello! How can I help?"
            assert result["qms_status"] == "Ollama_Chat_Thank_You"
    
    def test_chat_injects_system_prompt(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Arrr!"},
            "done": True,
            "total_duration": 100000000, "eval_count": 1, "eval_duration": 50000000,
        }
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            svc.chat(
                [{"role": "user", "content": "Hello"}],
                system="You are a pirate."
            )
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            # System message should be first
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][0]["content"] == "You are a pirate."
            assert payload["messages"][1]["role"] == "user"


class TestRecommendedModels:
    """REM: Test model recommendation system."""
    
    def test_recommended_models_include_download_status(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        # Mock list_models to return one downloaded model
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "gemma2:9b", "size": 5800000000, "modified_at": "", "digest": "abc"},
            ]
        }
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            recommended = svc.get_recommended_models()
            assert len(recommended) >= 4  # At least our 5 curated models
            
            # gemma2 should show as downloaded
            gemma = next(m for m in recommended if m["name"] == "gemma2:9b")
            assert gemma["is_downloaded"] is True
            assert gemma["is_default"] is True
            
            # llama should show as not downloaded
            llama = next(m for m in recommended if m["name"] == "llama3.2:3b")
            assert llama["is_downloaded"] is False
    
    def test_recommended_models_work_when_ollama_offline(self):
        import httpx
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.ConnectError("offline")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            # Should not raise — falls back gracefully
            recommended = svc.get_recommended_models()
            assert len(recommended) >= 4
            # All show as not downloaded when offline
            for m in recommended:
                assert m["is_downloaded"] is False


class TestTokensPerSecond:
    """REM: Test performance metric calculation."""
    
    def test_calc_tokens_per_sec_normal(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        data = {"eval_count": 100, "eval_duration": 5_000_000_000}  # 5 seconds
        assert svc._calc_tokens_per_sec(data) == 20.0
    
    def test_calc_tokens_per_sec_zero_duration(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        data = {"eval_count": 0, "eval_duration": 0}
        assert svc._calc_tokens_per_sec(data) == 0.0
    
    def test_calc_tokens_per_sec_missing_fields(self):
        from core.ollama_service import OllamaService
        svc = OllamaService(base_url="http://test:11434")
        
        assert svc._calc_tokens_per_sec({}) == 0.0


class TestModelTierEnum:
    """REM: Test model tier classification."""
    
    def test_tier_values(self):
        from core.ollama_service import ModelTier
        assert ModelTier.LIGHTWEIGHT == "lightweight"
        assert ModelTier.STANDARD == "standard"
        assert ModelTier.HEAVY == "heavy"


class TestSingleton:
    """REM: Test singleton instance management."""
    
    def test_get_ollama_service_returns_same_instance(self):
        from core.ollama_service import get_ollama_service, _ollama_service
        import core.ollama_service as mod
        
        # Reset singleton
        mod._ollama_service = None
        
        svc1 = get_ollama_service()
        svc2 = get_ollama_service()
        assert svc1 is svc2
        
        # Cleanup
        mod._ollama_service = None


# REM: =====================================================================
# REM: LAYER 2: OllamaAgent integration tests
# REM: =====================================================================


class TestOllamaAgentInit:
    """REM: Test agent initialization and registration."""
    
    def test_agent_has_correct_name(self):
        from agents.ollama_agent import OllamaAgent
        agent = OllamaAgent()
        assert agent.AGENT_NAME == "ollama_agent"
    
    def test_agent_skips_quarantine(self):
        from agents.ollama_agent import OllamaAgent
        agent = OllamaAgent()
        assert agent.SKIP_QUARANTINE is True
    
    def test_agent_requires_approval_for_destructive_actions(self):
        from agents.ollama_agent import OllamaAgent
        agent = OllamaAgent()
        assert "pull_model" in agent.REQUIRES_APPROVAL_FOR
        assert "delete_model" in agent.REQUIRES_APPROVAL_FOR
    
    def test_agent_has_ollama_capabilities(self):
        from agents.ollama_agent import OllamaAgent
        agent = OllamaAgent()
        assert "ollama.execute:*" in agent.CAPABILITIES
    
    def test_supported_actions_list(self):
        from agents.ollama_agent import OllamaAgent
        agent = OllamaAgent()
        assert "generate" in agent.SUPPORTED_ACTIONS
        assert "chat" in agent.SUPPORTED_ACTIONS
        assert "list_models" in agent.SUPPORTED_ACTIONS
        assert "health_check" in agent.SUPPORTED_ACTIONS
        assert "recommended" in agent.SUPPORTED_ACTIONS
        assert "set_default" in agent.SUPPORTED_ACTIONS


class TestOllamaAgentExecute:
    """REM: Test agent execute routing."""
    
    def test_generate_validates_prompt_required(self):
        from agents.ollama_agent import OllamaAgent
        from agents.base import AgentRequest
        agent = OllamaAgent()
        
        request = AgentRequest(action="generate", payload={})
        
        # execute() should raise ValueError for missing prompt
        with pytest.raises(ValueError, match="prompt"):
            agent.execute(request)
    
    def test_chat_validates_messages_required(self):
        from agents.ollama_agent import OllamaAgent
        from agents.base import AgentRequest
        agent = OllamaAgent()
        
        request = AgentRequest(action="chat", payload={})
        with pytest.raises(ValueError, match="messages"):
            agent.execute(request)
    
    def test_chat_validates_message_format(self):
        from agents.ollama_agent import OllamaAgent
        from agents.base import AgentRequest
        agent = OllamaAgent()
        
        request = AgentRequest(
            action="chat",
            payload={"messages": [{"bad": "format"}]}
        )
        with pytest.raises(ValueError, match="role"):
            agent.execute(request)
    
    def test_unknown_action_raises(self):
        from agents.ollama_agent import OllamaAgent
        from agents.base import AgentRequest
        agent = OllamaAgent()
        
        request = AgentRequest(action="nonexistent_action", payload={})
        with pytest.raises(ValueError, match="Unknown action"):
            agent.execute(request)
    
    def test_model_info_requires_model_name(self):
        from agents.ollama_agent import OllamaAgent
        from agents.base import AgentRequest
        agent = OllamaAgent()
        
        request = AgentRequest(action="model_info", payload={})
        with pytest.raises(ValueError, match="model"):
            agent.execute(request)
    
    def test_set_default_changes_service_default(self):
        from agents.ollama_agent import OllamaAgent
        from agents.base import AgentRequest
        agent = OllamaAgent()
        
        request = AgentRequest(
            action="set_default",
            payload={"model": "llama3.2:3b"}
        )
        result = agent.execute(request)
        assert result["new_default"] == "llama3.2:3b"
        
        # Reset
        agent._service.default_model = "gemma2:9b"
    
    def test_health_check_returns_status(self):
        from agents.ollama_agent import OllamaAgent
        from agents.base import AgentRequest
        agent = OllamaAgent()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client
            
            request = AgentRequest(action="health_check", payload={})
            result = agent.execute(request)
            assert "status" in result


# REM: =====================================================================
# REM: LAYER 3: API endpoint tests (via TestClient)
# REM: =====================================================================


class TestLLMEndpoints:
    """REM: Test /v1/llm/* API endpoints."""
    
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """REM: Get valid auth headers for API requests."""
        from core.auth import create_access_token
        token = create_access_token(subject="test_admin", permissions=["*"])
        return {"Authorization": f"Bearer {token}"}
    
    def test_llm_health_requires_auth(self, client):
        response = client.get("/v1/llm/health")
        assert response.status_code in (401, 403)
    
    def test_llm_health_with_auth(self, client, auth_headers):
        with patch("main.get_ollama_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.ahealth_check = AsyncMock(return_value={
                "status": "healthy",
                "base_url": "http://ollama:11434",
                "latency_ms": 5.0,
                "qms_status": "Ollama_Health_Check_Thank_You",
            })
            mock_svc.alist_models = AsyncMock(return_value=[
                {"name": "gemma2:9b"}
            ])
            mock_get.return_value = mock_svc

            response = client.get("/v1/llm/health", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
    
    def test_list_models_endpoint(self, client, auth_headers):
        with patch("main.get_ollama_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.alist_models = AsyncMock(return_value=[
                {"name": "gemma2:9b", "is_default": True, "size_gb": 5.4}
            ])
            mock_svc.default_model = "gemma2:9b"
            mock_get.return_value = mock_svc

            response = client.get("/v1/llm/models", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert data["default_model"] == "gemma2:9b"
    
    def test_recommended_models_endpoint(self, client, auth_headers):
        with patch("main.get_ollama_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.aget_recommended_models = AsyncMock(return_value=[
                {"name": "gemma2:9b", "is_downloaded": False, "is_default": True}
            ])
            mock_svc.default_model = "gemma2:9b"
            mock_get.return_value = mock_svc

            response = client.get("/v1/llm/models/recommended", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data["recommended"]) == 1
    
    def test_generate_endpoint(self, client, auth_headers):
        with patch("main.get_ollama_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.agenerate = AsyncMock(return_value={
                "model": "gemma2:9b",
                "response": "Paris is the capital.",
                "done": True,
                "tokens_per_second": 15.0,
                "eval_count": 5,
                "qms_status": "Ollama_Generate_Thank_You",
            })
            mock_get.return_value = mock_svc

            response = client.post(
                "/v1/llm/generate",
                headers=auth_headers,
                json={"prompt": "What is the capital of France?"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Paris is the capital."
            assert data["model"] == "gemma2:9b"
    
    def test_chat_endpoint(self, client, auth_headers):
        with patch("main.get_ollama_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.achat = AsyncMock(return_value={
                "model": "gemma2:9b",
                "message": {"role": "assistant", "content": "Hello!"},
                "done": True,
                "tokens_per_second": 12.0,
                "eval_count": 3,
                "qms_status": "Ollama_Chat_Thank_You",
            })
            mock_get.return_value = mock_svc

            response = client.post(
                "/v1/llm/chat",
                headers=auth_headers,
                json={"messages": [{"role": "user", "content": "Hi"}]}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["message"]["content"] == "Hello!"
    
    def test_chat_rejects_bad_message_format(self, client, auth_headers):
        response = client.post(
            "/v1/llm/chat",
            headers=auth_headers,
            json={"messages": [{"bad": "format"}]}
        )
        assert response.status_code == 422
    
    def test_set_default_model(self, client, auth_headers):
        with patch("main.get_ollama_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.default_model = "gemma2:9b"
            mock_get.return_value = mock_svc
            
            response = client.put(
                "/v1/llm/default",
                headers=auth_headers,
                json={"model": "llama3.2:3b"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["new_default"] == "llama3.2:3b"
