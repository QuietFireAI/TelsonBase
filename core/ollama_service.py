# TelsonBase/core/ollama_service.py
# REM: =======================================================================================
# REM: SOVEREIGN AI ENGINE SERVICE — DIRECT OLLAMA REST API CLIENT
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
# REM:
# REM: Mission Statement: Direct HTTP communication with Ollama's REST API. No third-party
# REM: Python client. No dependency chain poison. Just httpx talking to localhost:11434,
# REM: the same way Open-WebUI does it. This is the engine room of TelsonBase — where
# REM: local LLM inference actually happens.
# REM:
# REM: Why not ollama==0.1.6? Because it forced httpx<0.26.0 which broke pytest-asyncio.
# REM: One stale dependency cascaded into the entire Gemini Colab test failure. Never again.
# REM: The Ollama REST API is stable, documented, and won't break our dependency chain.
# REM:
# REM: Ollama REST API reference: https://github.com/ollama/ollama/blob/main/docs/api.md
# REM: =======================================================================================

import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional
from enum import Enum

import httpx

from core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# REM: =======================================================================================
# REM: MODEL REGISTRY — Recommended models for consumer-grade hardware
# REM: =======================================================================================

class ModelTier(str, Enum):
    """REM: Model tiers by resource requirements."""
    LIGHTWEIGHT = "lightweight"   # < 4GB RAM — fast, basic tasks
    STANDARD = "standard"         # 4-8GB RAM — good quality, most tasks
    HEAVY = "heavy"               # 8GB+ RAM — best quality, slow on CPU


# REM: Curated model list. All open source. All run on consumer hardware.
# REM: User can pull anything Ollama supports, but these are the recommended defaults.
RECOMMENDED_MODELS = {
    "gemma2:9b": {
        "tier": ModelTier.STANDARD,
        "size_gb": 5.4,
        "ram_required_gb": 8,
        "description": "Google's open model. Best quality-to-size ratio. Strong reasoning.",
        "license": "Gemma License (permissive)",
        "recommended_for": ["general chat", "analysis", "summarization", "reasoning"],
        "default": True,
    },
    "llama3.2:3b": {
        "tier": ModelTier.LIGHTWEIGHT,
        "size_gb": 2.0,
        "ram_required_gb": 4,
        "description": "Meta's lightweight model. Fast responses. Good for simple tasks.",
        "license": "Llama 3.2 Community License",
        "recommended_for": ["quick answers", "summaries", "classification"],
        "default": False,
    },
    "qwen2.5:7b": {
        "tier": ModelTier.STANDARD,
        "size_gb": 4.7,
        "ram_required_gb": 7,
        "description": "Alibaba's open model. Excellent at structured output and code.",
        "license": "Apache 2.0",
        "recommended_for": ["code generation", "structured output", "analysis"],
        "default": False,
    },
    "phi3:mini": {
        "tier": ModelTier.LIGHTWEIGHT,
        "size_gb": 2.3,
        "ram_required_gb": 4,
        "description": "Microsoft's small model. Punches above its weight on reasoning.",
        "license": "MIT",
        "recommended_for": ["reasoning", "math", "concise answers"],
        "default": False,
    },
    "mistral:7b": {
        "tier": ModelTier.STANDARD,
        "size_gb": 4.1,
        "ram_required_gb": 6,
        "description": "Mistral AI's foundation model. Battle-tested, reliable general purpose.",
        "license": "Apache 2.0",
        "recommended_for": ["general chat", "writing", "analysis"],
        "default": False,
    },
}


class OllamaServiceError(Exception):
    """REM: Base exception for Ollama service failures."""
    pass


class OllamaConnectionError(OllamaServiceError):
    """REM: Cannot reach Ollama at configured URL."""
    pass


class OllamaModelError(OllamaServiceError):
    """REM: Model-specific error (not found, pull failed, etc.)."""
    pass


class OllamaService:
    """
    REM: Direct HTTP client for Ollama's REST API.
    REM: No third-party Python client. Just httpx → localhost:11434.
    
    REM: QMS Protocol:
    REM:   Health check: Ollama_Health_Check_Please → Ollama_Health_Check_Thank_You
    REM:   Generate:     Ollama_Generate_Please     → Ollama_Generate_Thank_You
    REM:   Chat:         Ollama_Chat_Please         → Ollama_Chat_Thank_You
    REM:   Pull model:   Ollama_Pull_Model_Please   → Ollama_Pull_Model_Thank_You
    """
    
    def __init__(self, base_url: Optional[str] = None, timeout: float = 300.0):
        """
        REM: Initialize with Ollama base URL from config or override.
        REM: Default timeout is 300s — gemma2:9b on CPU runs ~2 tok/s, chat can take minutes.
        """
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.timeout = timeout
        self._default_model = self._get_default_model()
        logger.info(f"REM: OllamaService initialized. Base URL: ::{self.base_url}:: Default model: ::{self._default_model}::")
    
    @property
    def default_model(self) -> str:
        return self._default_model
    
    @default_model.setter
    def default_model(self, model: str):
        self._default_model = model
        logger.info(f"REM: Default model changed to ::{model}::")
    
    def _get_default_model(self) -> str:
        """REM: Get the default model from RECOMMENDED_MODELS registry."""
        for name, info in RECOMMENDED_MODELS.items():
            if info.get("default"):
                return name
        return "gemma2:9b"  # Fallback
    
    def _client(self, stream_timeout: Optional[float] = None) -> httpx.Client:
        """REM: Create a fresh sync httpx client. Short-lived per request."""
        t = stream_timeout or self.timeout
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(t, connect=10.0),
        )

    def _async_client(self, stream_timeout: Optional[float] = None) -> httpx.AsyncClient:
        """REM: Create a fresh async httpx client for use in async endpoints."""
        t = stream_timeout or self.timeout
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(t, connect=10.0),
        )
    
    # REM: ==================================================================================
    # REM: HEALTH & STATUS
    # REM: ==================================================================================
    
    def health_check(self) -> Dict[str, Any]:
        """
        REM: Check if Ollama is reachable and get basic status.
        REM: QMS: Ollama_Health_Check_Please → Ollama_Health_Check_Thank_You
        """
        start = time.time()
        try:
            with self._client() as client:
                response = client.get("/")
                latency_ms = round((time.time() - start) * 1000, 1)
                
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "base_url": self.base_url,
                        "latency_ms": latency_ms,
                        "default_model": self._default_model,
                        "qms_status": "Ollama_Health_Check_Thank_You",
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "base_url": self.base_url,
                        "latency_ms": latency_ms,
                        "error": f"HTTP {response.status_code}",
                        "qms_status": "Ollama_Health_Check_Thank_You_But_No",
                    }
        except httpx.ConnectError:
            return {
                "status": "unreachable",
                "base_url": self.base_url,
                "error": "Connection refused — is Ollama running?",
                "qms_status": "Ollama_Health_Check_Thank_You_But_No",
            }
        except Exception as e:
            return {
                "status": "error",
                "base_url": self.base_url,
                "error": str(e),
                "qms_status": "Ollama_Health_Check_Thank_You_But_No",
            }
    
    def is_healthy(self) -> bool:
        """REM: Quick boolean health check."""
        return self.health_check().get("status") == "healthy"
    
    # REM: ==================================================================================
    # REM: MODEL MANAGEMENT
    # REM: ==================================================================================
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        REM: List all locally available models.
        REM: Ollama API: GET /api/tags
        REM: Returns model name, size, modification time, digest.
        """
        try:
            with self._client() as client:
                response = client.get("/api/tags")
                response.raise_for_status()
                data = response.json()
                
                models = []
                for model in data.get("models", []):
                    name = model.get("name", "")
                    recommended = RECOMMENDED_MODELS.get(name, {})
                    
                    models.append({
                        "name": name,
                        "size_bytes": model.get("size", 0),
                        "size_gb": round(model.get("size", 0) / (1024**3), 2),
                        "modified_at": model.get("modified_at", ""),
                        "digest": model.get("digest", "")[:16],
                        "is_recommended": name in RECOMMENDED_MODELS,
                        "is_default": name == self._default_model,
                        "tier": recommended.get("tier", "custom"),
                        "description": recommended.get("description", "Custom/user-pulled model"),
                    })
                
                return sorted(models, key=lambda m: (not m["is_default"], not m["is_recommended"], m["name"]))
                
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama — is the service running?")
        except Exception as e:
            raise OllamaServiceError(f"Failed to list models: {e}")
    
    def model_info(self, model: str) -> Dict[str, Any]:
        """
        REM: Get detailed info about a specific model.
        REM: Ollama API: POST /api/show
        """
        try:
            with self._client() as client:
                response = client.post("/api/show", json={"name": model})
                if response.status_code == 404:
                    raise OllamaModelError(f"Model '{model}' not found locally")
                response.raise_for_status()
                data = response.json()
                
                # REM: Extract useful fields from the verbose response
                details = data.get("details", {})
                return {
                    "name": model,
                    "family": details.get("family", "unknown"),
                    "parameter_size": details.get("parameter_size", "unknown"),
                    "quantization_level": details.get("quantization_level", "unknown"),
                    "format": details.get("format", "unknown"),
                    "template": data.get("template", "")[:200],
                    "system": data.get("system", "")[:200],
                    "is_recommended": model in RECOMMENDED_MODELS,
                }
                
        except OllamaModelError:
            raise
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama")
        except Exception as e:
            raise OllamaServiceError(f"Failed to get model info: {e}")
    
    def pull_model(self, model: str) -> Dict[str, Any]:
        """
        REM: Pull (download) a model from the Ollama registry.
        REM: Ollama API: POST /api/pull
        REM: QMS: Ollama_Pull_Model_Please ::model_name:: → Ollama_Pull_Model_Thank_You
        REM:
        REM: NOTE: This is a synchronous blocking call. For large models (5GB+),
        REM: this can take minutes or hours depending on bandwidth. In production,
        REM: this should be dispatched as a Celery background task.
        """
        logger.info(f"REM: Ollama_Pull_Model_Please ::{model}::")
        try:
            # REM: Use a very long timeout for downloads
            with self._client(stream_timeout=3600.0) as client:
                response = client.post(
                    "/api/pull",
                    json={"name": model, "stream": False},
                    timeout=httpx.Timeout(3600.0, connect=10.0),
                )
                response.raise_for_status()
                data = response.json()
                
                status = data.get("status", "unknown")
                logger.info(f"REM: Ollama_Pull_Model_Thank_You ::{model}:: Status: ::{status}::")
                
                return {
                    "model": model,
                    "status": status,
                    "qms_status": "Ollama_Pull_Model_Thank_You",
                }
                
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama")
        except Exception as e:
            logger.error(f"REM: Ollama_Pull_Model_Thank_You_But_No ::{model}:: Error: ::{e}::")
            raise OllamaServiceError(f"Failed to pull model '{model}': {e}")
    
    def delete_model(self, model: str) -> Dict[str, Any]:
        """
        REM: Delete a model from local storage.
        REM: Ollama API: DELETE /api/delete
        """
        logger.info(f"REM: Ollama_Delete_Model_Please ::{model}::")
        try:
            with self._client() as client:
                response = client.request("DELETE", "/api/delete", json={"name": model})
                if response.status_code == 404:
                    raise OllamaModelError(f"Model '{model}' not found")
                response.raise_for_status()
                
                logger.info(f"REM: Ollama_Delete_Model_Thank_You ::{model}::")
                return {
                    "model": model,
                    "status": "deleted",
                    "qms_status": "Ollama_Delete_Model_Thank_You",
                }
                
        except OllamaModelError:
            raise
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama")
        except Exception as e:
            raise OllamaServiceError(f"Failed to delete model '{model}': {e}")
    
    # REM: ==================================================================================
    # REM: INFERENCE — The actual AI brain
    # REM: ==================================================================================
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        context: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        REM: Single prompt → single response. Non-streaming.
        REM: Ollama API: POST /api/generate
        REM: QMS: Ollama_Generate_Please → Ollama_Generate_Thank_You
        
        REM: This is for one-shot tasks: summarize this, classify this, extract this.
        REM: For conversation, use chat().
        """
        model = model or self._default_model
        logger.info(f"REM: Ollama_Generate_Please ::{model}:: Prompt length: {len(prompt)}")
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if context:
            payload["context"] = context
        
        start = time.time()
        try:
            with self._client() as client:
                response = client.post("/api/generate", json=payload)
                
                if response.status_code == 404:
                    raise OllamaModelError(
                        f"Model '{model}' not found. Pull it first: POST /v1/llm/models/pull"
                    )
                response.raise_for_status()
                data = response.json()
                
                elapsed = round(time.time() - start, 2)
                result = {
                    "model": model,
                    "response": data.get("response", ""),
                    "done": data.get("done", False),
                    "context": data.get("context"),
                    "total_duration_ms": data.get("total_duration", 0) // 1_000_000,
                    "eval_count": data.get("eval_count", 0),
                    "eval_duration_ms": data.get("eval_duration", 0) // 1_000_000,
                    "tokens_per_second": self._calc_tokens_per_sec(data),
                    "elapsed_seconds": elapsed,
                    "qms_status": "Ollama_Generate_Thank_You",
                }
                
                logger.info(
                    f"REM: Ollama_Generate_Thank_You ::{model}:: "
                    f"Tokens: {result['eval_count']} | "
                    f"Speed: {result['tokens_per_second']} tok/s | "
                    f"Time: {elapsed}s"
                )
                return result
                
        except OllamaModelError:
            raise
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama — is the service running?")
        except httpx.ReadTimeout:
            raise OllamaServiceError(
                f"Ollama timed out after {self.timeout}s. "
                "Model may be too large for your hardware, or prompt is very long."
            )
        except Exception as e:
            logger.error(f"REM: Ollama_Generate_Thank_You_But_No ::{model}:: Error: ::{e}::")
            raise OllamaServiceError(f"Generate failed: {e}")
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        REM: Multi-turn conversation. Non-streaming.
        REM: Ollama API: POST /api/chat
        REM: QMS: Ollama_Chat_Please → Ollama_Chat_Thank_You
        
        REM: Messages format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        REM: This maintains conversation context natively — Ollama handles the KV cache.
        """
        model = model or self._default_model
        logger.info(f"REM: Ollama_Chat_Please ::{model}:: Messages: {len(messages)}")
        
        # REM: Inject system prompt as first message if provided
        full_messages = list(messages)
        if system:
            full_messages.insert(0, {"role": "system", "content": system})
        
        payload = {
            "model": model,
            "messages": full_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        start = time.time()
        try:
            with self._client() as client:
                response = client.post("/api/chat", json=payload)
                
                if response.status_code == 404:
                    raise OllamaModelError(
                        f"Model '{model}' not found. Pull it first: POST /v1/llm/models/pull"
                    )
                response.raise_for_status()
                data = response.json()
                
                elapsed = round(time.time() - start, 2)
                message = data.get("message", {})
                
                result = {
                    "model": model,
                    "message": {
                        "role": message.get("role", "assistant"),
                        "content": message.get("content", ""),
                    },
                    "done": data.get("done", False),
                    "total_duration_ms": data.get("total_duration", 0) // 1_000_000,
                    "eval_count": data.get("eval_count", 0),
                    "tokens_per_second": self._calc_tokens_per_sec(data),
                    "elapsed_seconds": elapsed,
                    "qms_status": "Ollama_Chat_Thank_You",
                }
                
                logger.info(
                    f"REM: Ollama_Chat_Thank_You ::{model}:: "
                    f"Tokens: {result['eval_count']} | "
                    f"Speed: {result['tokens_per_second']} tok/s | "
                    f"Time: {elapsed}s"
                )
                return result
                
        except OllamaModelError:
            raise
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama — is the service running?")
        except httpx.ReadTimeout:
            raise OllamaServiceError(f"Chat timed out after {self.timeout}s.")
        except Exception as e:
            logger.error(f"REM: Ollama_Chat_Thank_You_But_No ::{model}:: Error: ::{e}::")
            raise OllamaServiceError(f"Chat failed: {e}")
    
    # REM: ==================================================================================
    # REM: ASYNC INFERENCE — Non-blocking versions for async FastAPI endpoints
    # REM: ==================================================================================
    # REM: v5.2.1CC: These async methods use httpx.AsyncClient so they don't block
    # REM: the event loop when called from async def FastAPI endpoints.

    async def agenerate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        context: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """REM: Async version of generate(). Use from async FastAPI endpoints."""
        model = model or self._default_model
        logger.info(f"REM: Ollama_Generate_Please ::{model}:: Prompt length: {len(prompt)}")

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if context:
            payload["context"] = context

        start = time.time()
        try:
            async with self._async_client() as client:
                response = await client.post("/api/generate", json=payload)
                if response.status_code == 404:
                    raise OllamaModelError(
                        f"Model '{model}' not found. Pull it first: POST /v1/llm/models/pull"
                    )
                response.raise_for_status()
                data = response.json()

                elapsed = round(time.time() - start, 2)
                result = {
                    "model": model,
                    "response": data.get("response", ""),
                    "done": data.get("done", False),
                    "context": data.get("context"),
                    "total_duration_ms": data.get("total_duration", 0) // 1_000_000,
                    "eval_count": data.get("eval_count", 0),
                    "eval_duration_ms": data.get("eval_duration", 0) // 1_000_000,
                    "tokens_per_second": self._calc_tokens_per_sec(data),
                    "elapsed_seconds": elapsed,
                    "qms_status": "Ollama_Generate_Thank_You",
                }
                logger.info(
                    f"REM: Ollama_Generate_Thank_You ::{model}:: "
                    f"Tokens: {result['eval_count']} | Speed: {result['tokens_per_second']} tok/s | Time: {elapsed}s"
                )
                return result
        except OllamaModelError:
            raise
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama — is the service running?")
        except httpx.ReadTimeout:
            raise OllamaServiceError(
                f"Ollama timed out after {self.timeout}s. "
                "Model may be too large for your hardware, or prompt is very long."
            )
        except Exception as e:
            logger.error(f"REM: Ollama_Generate_Thank_You_But_No ::{model}:: Error: ::{e}::")
            raise OllamaServiceError(f"Generate failed: {e}")

    async def achat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """REM: Async version of chat(). Use from async FastAPI endpoints."""
        model = model or self._default_model
        logger.info(f"REM: Ollama_Chat_Please ::{model}:: Messages: {len(messages)}")

        full_messages = list(messages)
        if system:
            full_messages.insert(0, {"role": "system", "content": system})

        payload = {
            "model": model,
            "messages": full_messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        start = time.time()
        try:
            async with self._async_client() as client:
                response = await client.post("/api/chat", json=payload)
                if response.status_code == 404:
                    raise OllamaModelError(
                        f"Model '{model}' not found. Pull it first: POST /v1/llm/models/pull"
                    )
                response.raise_for_status()
                data = response.json()

                elapsed = round(time.time() - start, 2)
                message = data.get("message", {})
                result = {
                    "model": model,
                    "message": {
                        "role": message.get("role", "assistant"),
                        "content": message.get("content", ""),
                    },
                    "done": data.get("done", False),
                    "total_duration_ms": data.get("total_duration", 0) // 1_000_000,
                    "eval_count": data.get("eval_count", 0),
                    "tokens_per_second": self._calc_tokens_per_sec(data),
                    "elapsed_seconds": elapsed,
                    "qms_status": "Ollama_Chat_Thank_You",
                }
                logger.info(
                    f"REM: Ollama_Chat_Thank_You ::{model}:: "
                    f"Tokens: {result['eval_count']} | Speed: {result['tokens_per_second']} tok/s | Time: {elapsed}s"
                )
                return result
        except OllamaModelError:
            raise
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama — is the service running?")
        except httpx.ReadTimeout:
            raise OllamaServiceError(f"Chat timed out after {self.timeout}s.")
        except Exception as e:
            logger.error(f"REM: Ollama_Chat_Thank_You_But_No ::{model}:: Error: ::{e}::")
            raise OllamaServiceError(f"Chat failed: {e}")

    async def ahealth_check(self) -> Dict[str, Any]:
        """REM: Async version of health_check()."""
        start = time.time()
        try:
            async with self._async_client() as client:
                response = await client.get("/")
                latency_ms = round((time.time() - start) * 1000, 1)
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "base_url": self.base_url,
                        "latency_ms": latency_ms,
                        "default_model": self._default_model,
                        "qms_status": "Ollama_Health_Check_Thank_You",
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "base_url": self.base_url,
                        "latency_ms": latency_ms,
                        "error": f"HTTP {response.status_code}",
                        "qms_status": "Ollama_Health_Check_Thank_You_But_No",
                    }
        except httpx.ConnectError:
            return {
                "status": "unreachable",
                "base_url": self.base_url,
                "error": "Connection refused — is Ollama running?",
                "qms_status": "Ollama_Health_Check_Thank_You_But_No",
            }
        except Exception as e:
            return {
                "status": "error",
                "base_url": self.base_url,
                "error": str(e),
                "qms_status": "Ollama_Health_Check_Thank_You_But_No",
            }

    async def alist_models(self) -> List[Dict[str, Any]]:
        """REM: Async version of list_models()."""
        try:
            async with self._async_client() as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                data = response.json()
                models = []
                for model in data.get("models", []):
                    name = model.get("name", "")
                    recommended = RECOMMENDED_MODELS.get(name, {})
                    models.append({
                        "name": name,
                        "size_bytes": model.get("size", 0),
                        "size_gb": round(model.get("size", 0) / (1024**3), 2),
                        "modified_at": model.get("modified_at", ""),
                        "digest": model.get("digest", "")[:16],
                        "is_recommended": name in RECOMMENDED_MODELS,
                        "is_default": name == self._default_model,
                        "tier": recommended.get("tier", "custom"),
                        "description": recommended.get("description", "Custom/user-pulled model"),
                    })
                return sorted(models, key=lambda m: (not m["is_default"], not m["is_recommended"], m["name"]))
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama — is the service running?")
        except Exception as e:
            raise OllamaServiceError(f"Failed to list models: {e}")

    async def apull_model(self, model: str) -> Dict[str, Any]:
        """REM: Async version of pull_model()."""
        logger.info(f"REM: Ollama_Pull_Model_Please ::{model}::")
        try:
            async with self._async_client(stream_timeout=3600.0) as client:
                response = await client.post(
                    "/api/pull",
                    json={"name": model, "stream": False},
                    timeout=httpx.Timeout(3600.0, connect=10.0),
                )
                response.raise_for_status()
                data = response.json()
                status = data.get("status", "unknown")
                logger.info(f"REM: Ollama_Pull_Model_Thank_You ::{model}:: Status: ::{status}::")
                return {"model": model, "status": status, "qms_status": "Ollama_Pull_Model_Thank_You"}
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama")
        except Exception as e:
            logger.error(f"REM: Ollama_Pull_Model_Thank_You_But_No ::{model}:: Error: ::{e}::")
            raise OllamaServiceError(f"Failed to pull model '{model}': {e}")

    async def adelete_model(self, model: str) -> Dict[str, Any]:
        """REM: Async version of delete_model()."""
        logger.info(f"REM: Ollama_Delete_Model_Please ::{model}::")
        try:
            async with self._async_client() as client:
                response = await client.request("DELETE", "/api/delete", json={"name": model})
                if response.status_code == 404:
                    raise OllamaModelError(f"Model '{model}' not found")
                response.raise_for_status()
                logger.info(f"REM: Ollama_Delete_Model_Thank_You ::{model}::")
                return {"model": model, "status": "deleted", "qms_status": "Ollama_Delete_Model_Thank_You"}
        except OllamaModelError:
            raise
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama")
        except Exception as e:
            raise OllamaServiceError(f"Failed to delete model '{model}': {e}")

    async def aget_recommended_models(self) -> List[Dict[str, Any]]:
        """REM: Async version of get_recommended_models()."""
        try:
            local_models = {m["name"] for m in await self.alist_models()}
        except OllamaServiceError:
            local_models = set()
        result = []
        for name, info in RECOMMENDED_MODELS.items():
            result.append({
                "name": name,
                "tier": info["tier"],
                "size_gb": info["size_gb"],
                "ram_required_gb": info["ram_required_gb"],
                "description": info["description"],
                "license": info["license"],
                "recommended_for": info["recommended_for"],
                "is_default": info["default"],
                "is_downloaded": name in local_models,
            })
        return result

    async def amodel_info(self, model: str) -> Dict[str, Any]:
        """REM: Async version of model_info()."""
        try:
            async with self._async_client() as client:
                response = await client.post("/api/show", json={"name": model})
                if response.status_code == 404:
                    raise OllamaModelError(f"Model '{model}' not found locally")
                response.raise_for_status()
                data = response.json()
                details = data.get("details", {})
                return {
                    "name": model,
                    "family": details.get("family", "unknown"),
                    "parameter_size": details.get("parameter_size", "unknown"),
                    "quantization_level": details.get("quantization_level", "unknown"),
                    "format": details.get("format", "unknown"),
                    "template": data.get("template", "")[:200],
                    "system": data.get("system", "")[:200],
                    "is_recommended": model in RECOMMENDED_MODELS,
                }
        except OllamaModelError:
            raise
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot reach Ollama")
        except Exception as e:
            raise OllamaServiceError(f"Failed to get model info: {e}")

    # REM: ==================================================================================
    # REM: RECOMMENDED MODELS — Discovery for the dashboard
    # REM: ==================================================================================
    
    def get_recommended_models(self) -> List[Dict[str, Any]]:
        """
        REM: Return curated model list with local availability status.
        REM: Dashboard uses this to show what can be pulled and what's ready.
        """
        try:
            local_models = {m["name"] for m in self.list_models()}
        except OllamaServiceError:
            local_models = set()
        
        result = []
        for name, info in RECOMMENDED_MODELS.items():
            result.append({
                "name": name,
                "tier": info["tier"],
                "size_gb": info["size_gb"],
                "ram_required_gb": info["ram_required_gb"],
                "description": info["description"],
                "license": info["license"],
                "recommended_for": info["recommended_for"],
                "is_default": info["default"],
                "is_downloaded": name in local_models,
            })
        
        return result
    
    # REM: ==================================================================================
    # REM: INTERNAL HELPERS
    # REM: ==================================================================================
    
    def _calc_tokens_per_sec(self, data: Dict[str, Any]) -> float:
        """REM: Calculate tokens per second from Ollama response metadata."""
        eval_count = data.get("eval_count", 0)
        eval_duration = data.get("eval_duration", 0)
        if eval_duration > 0:
            return round(eval_count / (eval_duration / 1_000_000_000), 1)
        return 0.0


# REM: =======================================================================================
# REM: SINGLETON INSTANCE — Same pattern as audit, signing, etc.
# REM: =======================================================================================

_ollama_service: Optional[OllamaService] = None


def get_ollama_service() -> OllamaService:
    """REM: Get or create the singleton OllamaService instance."""
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
    return _ollama_service
