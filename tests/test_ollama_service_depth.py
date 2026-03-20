# SPDX-FileCopyrightText: 2026 Quietfire AI / Jeff Phillips
# SPDX-License-Identifier: Apache-2.0
# tests/test_ollama_service_depth.py
# REM: Depth coverage for core/ollama_service.py
# REM: Tests: OllamaService sync/async methods, error handling, singleton, helpers.

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _make_service(base_url="http://localhost:11434"):
    from core.ollama_service import OllamaService
    return OllamaService(base_url=base_url)


def _sync_ctx(response):
    """REM: Build a mock sync context manager that returns response."""
    m = MagicMock()
    m.__enter__ = lambda s: m
    m.__exit__ = lambda s, *a: None
    m.get = MagicMock(return_value=response)
    m.post = MagicMock(return_value=response)
    m.request = MagicMock(return_value=response)
    return m


def _async_ctx(response):
    """REM: Build a mock async context manager that returns response."""
    m = AsyncMock()
    m.__aenter__ = AsyncMock(return_value=m)
    m.__aexit__ = AsyncMock(return_value=False)
    m.get = AsyncMock(return_value=response)
    m.post = AsyncMock(return_value=response)
    m.request = AsyncMock(return_value=response)
    return m


def _resp(status=200, json_data=None):
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=json_data or {})
    r.raise_for_status = MagicMock()
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestModuleConstants:
    def test_recommended_models_not_empty(self):
        from core.ollama_service import RECOMMENDED_MODELS
        assert len(RECOMMENDED_MODELS) > 0

    def test_recommended_models_have_required_keys(self):
        from core.ollama_service import RECOMMENDED_MODELS
        for name, info in RECOMMENDED_MODELS.items():
            assert "tier" in info, f"{name} missing tier"
            assert "size_gb" in info, f"{name} missing size_gb"
            assert "default" in info, f"{name} missing default"

    def test_exactly_one_default_model(self):
        from core.ollama_service import RECOMMENDED_MODELS
        defaults = [n for n, i in RECOMMENDED_MODELS.items() if i.get("default")]
        assert len(defaults) == 1

    def test_model_tier_enum_values(self):
        from core.ollama_service import ModelTier
        assert ModelTier.LIGHTWEIGHT == "lightweight"
        assert ModelTier.STANDARD == "standard"
        assert ModelTier.HEAVY == "heavy"


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTION CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class TestExceptions:
    def test_service_error_is_exception(self):
        from core.ollama_service import OllamaServiceError
        e = OllamaServiceError("boom")
        assert isinstance(e, Exception)

    def test_connection_error_is_service_error(self):
        from core.ollama_service import OllamaConnectionError, OllamaServiceError
        e = OllamaConnectionError("no conn")
        assert isinstance(e, OllamaServiceError)

    def test_model_error_is_service_error(self):
        from core.ollama_service import OllamaModelError, OllamaServiceError
        e = OllamaModelError("no model")
        assert isinstance(e, OllamaServiceError)


# ═══════════════════════════════════════════════════════════════════════════════
# OllamaService INIT AND PROPERTIES
# ═══════════════════════════════════════════════════════════════════════════════

class TestOllamaServiceInit:
    def test_base_url_stripped(self):
        svc = _make_service("http://localhost:11434/")
        assert not svc.base_url.endswith("/")

    def test_default_model_is_set(self):
        svc = _make_service()
        assert svc.default_model  # non-empty string

    def test_default_model_property_getter(self):
        svc = _make_service()
        assert svc.default_model == svc._default_model

    def test_default_model_property_setter(self):
        svc = _make_service()
        svc.default_model = "llama3.2:3b"
        assert svc.default_model == "llama3.2:3b"
        assert svc._default_model == "llama3.2:3b"

    def test_get_default_model_returns_default_from_registry(self):
        from core.ollama_service import RECOMMENDED_MODELS
        svc = _make_service()
        expected = next(n for n, i in RECOMMENDED_MODELS.items() if i.get("default"))
        assert svc._get_default_model() == expected

    def test_timeout_stored(self):
        svc = _make_service()
        assert svc.timeout == 300.0


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK (sync)
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthCheck:
    def test_healthy_200(self):
        svc = _make_service()
        ctx = _sync_ctx(_resp(200))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.health_check()
        assert r["status"] == "healthy"
        assert "latency_ms" in r

    def test_unhealthy_non_200(self):
        svc = _make_service()
        ctx = _sync_ctx(_resp(503))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.health_check()
        assert r["status"] == "unhealthy"
        assert "error" in r

    def test_unreachable_connect_error(self):
        import httpx
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.get = MagicMock(side_effect=httpx.ConnectError("refused"))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.health_check()
        assert r["status"] == "unreachable"

    def test_health_check_generic_exception(self):
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.get = MagicMock(side_effect=RuntimeError("unexpected"))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.health_check()
        assert r["status"] == "error"
        assert "unexpected" in r["error"]

    def test_is_healthy_true(self):
        svc = _make_service()
        with patch.object(svc, "health_check", return_value={"status": "healthy"}):
            assert svc.is_healthy() is True

    def test_is_healthy_false(self):
        svc = _make_service()
        with patch.object(svc, "health_check", return_value={"status": "unreachable"}):
            assert svc.is_healthy() is False


# ═══════════════════════════════════════════════════════════════════════════════
# LIST MODELS (sync)
# ═══════════════════════════════════════════════════════════════════════════════

class TestListModels:
    def _make_tag_response(self, names):
        models = [{"name": n, "size": 4_000_000_000, "modified_at": "2026-01-01", "digest": "abc123"} for n in names]
        return _resp(200, {"models": models})

    def test_returns_sorted_list(self):
        svc = _make_service()
        ctx = _sync_ctx(self._make_tag_response(["llama3.2:3b", "gemma2:9b"]))
        with patch.object(svc, "_client", return_value=ctx):
            result = svc.list_models()
        assert isinstance(result, list)
        # default model (gemma2:9b) should come first
        assert result[0]["is_default"] is True

    def test_recommended_flag_set(self):
        svc = _make_service()
        ctx = _sync_ctx(self._make_tag_response(["gemma2:9b", "unknown:model"]))
        with patch.object(svc, "_client", return_value=ctx):
            result = svc.list_models()
        by_name = {m["name"]: m for m in result}
        assert by_name["gemma2:9b"]["is_recommended"] is True
        assert by_name["unknown:model"]["is_recommended"] is False

    def test_connect_error_raises(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.get = MagicMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                svc.list_models()

    def test_generic_exception_raises_service_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.get = MagicMock(side_effect=ValueError("bad"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                svc.list_models()


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL INFO (sync)
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelInfo:
    def test_returns_info_dict(self):
        svc = _make_service()
        data = {"details": {"family": "llama", "parameter_size": "7B", "quantization_level": "Q4_0", "format": "gguf"},
                "template": "{{ prompt }}", "system": ""}
        ctx = _sync_ctx(_resp(200, data))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.model_info("llama3.2:3b")
        assert r["family"] == "llama"
        assert r["is_recommended"] is True

    def test_404_raises_model_error(self):
        from core.ollama_service import OllamaModelError
        svc = _make_service()
        ctx = _sync_ctx(_resp(404, {}))
        ctx.post = MagicMock(return_value=_resp(404, {}))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaModelError):
                svc.model_info("nonexistent:model")

    def test_connect_error_raises(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                svc.model_info("gemma2:9b")

    def test_generic_error_raises_service_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(side_effect=RuntimeError("ugh"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                svc.model_info("gemma2:9b")


# ═══════════════════════════════════════════════════════════════════════════════
# PULL MODEL (sync)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPullModel:
    def test_success(self):
        svc = _make_service()
        ctx = _sync_ctx(_resp(200, {"status": "success"}))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.pull_model("llama3.2:3b")
        assert r["model"] == "llama3.2:3b"
        assert r["status"] == "success"

    def test_connect_error_raises(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                svc.pull_model("foo:bar")

    def test_generic_error_raises_service_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(side_effect=RuntimeError("network down"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                svc.pull_model("foo:bar")


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE MODEL (sync)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeleteModel:
    def test_success(self):
        svc = _make_service()
        ctx = _sync_ctx(_resp(200, {}))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.delete_model("llama3.2:3b")
        assert r["status"] == "deleted"

    def test_404_raises_model_error(self):
        from core.ollama_service import OllamaModelError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        not_found = MagicMock()
        not_found.status_code = 404
        ctx.request = MagicMock(return_value=not_found)
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaModelError):
                svc.delete_model("missing:model")

    def test_connect_error_raises(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.request = MagicMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                svc.delete_model("foo:bar")

    def test_generic_error_raises_service_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.request = MagicMock(side_effect=RuntimeError("bad"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                svc.delete_model("foo:bar")


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATE (sync)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerate:
    _GENERATE_RESP = {
        "response": "Hello world",
        "done": True,
        "context": [1, 2, 3],
        "total_duration": 5_000_000_000,
        "eval_count": 10,
        "eval_duration": 2_000_000_000,
    }

    def test_basic_generate(self):
        svc = _make_service()
        ctx = _sync_ctx(_resp(200, self._GENERATE_RESP))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.generate(prompt="Say hi")
        assert r["response"] == "Hello world"
        assert r["tokens_per_second"] > 0

    def test_with_system_and_max_tokens(self):
        svc = _make_service()
        ctx = _sync_ctx(_resp(200, self._GENERATE_RESP))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.generate(prompt="test", system="You are helpful", max_tokens=100, context=[1, 2])
        assert r["response"] == "Hello world"

    def test_explicit_model_overrides_default(self):
        svc = _make_service()
        ctx = _sync_ctx(_resp(200, self._GENERATE_RESP))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.generate(prompt="test", model="phi3:mini")
        assert r["model"] == "phi3:mini"

    def test_404_raises_model_error(self):
        from core.ollama_service import OllamaModelError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(return_value=_resp(404, {}))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaModelError):
                svc.generate(prompt="test")

    def test_connect_error_raises(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                svc.generate(prompt="test")

    def test_read_timeout_raises_service_error(self):
        import httpx
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(side_effect=httpx.ReadTimeout("timed out"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                svc.generate(prompt="test")

    def test_generic_error_raises_service_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(side_effect=RuntimeError("oops"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                svc.generate(prompt="test")


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT (sync)
# ═══════════════════════════════════════════════════════════════════════════════

class TestChat:
    _CHAT_RESP = {
        "message": {"role": "assistant", "content": "I'm fine, thanks!"},
        "done": True,
        "total_duration": 3_000_000_000,
        "eval_count": 8,
        "eval_duration": 1_000_000_000,
    }
    _MSGS = [{"role": "user", "content": "Hello"}]

    def test_basic_chat(self):
        svc = _make_service()
        ctx = _sync_ctx(_resp(200, self._CHAT_RESP))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.chat(messages=self._MSGS)
        assert r["message"]["content"] == "I'm fine, thanks!"

    def test_with_system_prompt(self):
        svc = _make_service()
        ctx = _sync_ctx(_resp(200, self._CHAT_RESP))
        with patch.object(svc, "_client", return_value=ctx):
            r = svc.chat(messages=self._MSGS, system="You are helpful", max_tokens=50)
        assert r["message"]["role"] == "assistant"

    def test_404_raises_model_error(self):
        from core.ollama_service import OllamaModelError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(return_value=_resp(404, {}))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaModelError):
                svc.chat(messages=self._MSGS)

    def test_connect_error_raises(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                svc.chat(messages=self._MSGS)

    def test_read_timeout_raises_service_error(self):
        import httpx
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(side_effect=httpx.ReadTimeout("timeout"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                svc.chat(messages=self._MSGS)

    def test_generic_error_raises_service_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = MagicMock()
        ctx.__enter__ = lambda s: ctx
        ctx.__exit__ = lambda s, *a: None
        ctx.post = MagicMock(side_effect=RuntimeError("fail"))
        with patch.object(svc, "_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                svc.chat(messages=self._MSGS)


# ═══════════════════════════════════════════════════════════════════════════════
# GET RECOMMENDED MODELS (sync)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetRecommendedModels:
    def test_returns_all_recommended(self):
        from core.ollama_service import RECOMMENDED_MODELS
        svc = _make_service()
        with patch.object(svc, "list_models", return_value=[{"name": "gemma2:9b"}]):
            r = svc.get_recommended_models()
        assert len(r) == len(RECOMMENDED_MODELS)

    def test_is_downloaded_true_when_present(self):
        svc = _make_service()
        with patch.object(svc, "list_models", return_value=[{"name": "gemma2:9b"}]):
            r = svc.get_recommended_models()
        by_name = {m["name"]: m for m in r}
        assert by_name["gemma2:9b"]["is_downloaded"] is True

    def test_is_downloaded_false_when_absent(self):
        svc = _make_service()
        with patch.object(svc, "list_models", return_value=[]):
            r = svc.get_recommended_models()
        for m in r:
            assert m["is_downloaded"] is False

    def test_list_models_error_falls_back_to_empty(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        with patch.object(svc, "list_models", side_effect=OllamaServiceError("down")):
            r = svc.get_recommended_models()
        for m in r:
            assert m["is_downloaded"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — _calc_tokens_per_sec
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcTokensPerSec:
    def test_normal_calculation(self):
        svc = _make_service()
        data = {"eval_count": 100, "eval_duration": 5_000_000_000}  # 5 seconds
        result = svc._calc_tokens_per_sec(data)
        assert result == pytest.approx(20.0, rel=0.01)

    def test_zero_duration_returns_zero(self):
        svc = _make_service()
        data = {"eval_count": 50, "eval_duration": 0}
        assert svc._calc_tokens_per_sec(data) == 0.0

    def test_missing_keys_returns_zero(self):
        svc = _make_service()
        assert svc._calc_tokens_per_sec({}) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetOllamaService:
    def test_returns_ollama_service_instance(self):
        from core.ollama_service import OllamaService, get_ollama_service
        import core.ollama_service as _mod
        _mod._ollama_service = None  # REM: reset singleton for clean test
        svc = get_ollama_service()
        assert isinstance(svc, OllamaService)

    def test_returns_same_instance_on_repeated_calls(self):
        from core.ollama_service import get_ollama_service
        a = get_ollama_service()
        b = get_ollama_service()
        assert a is b


# ═══════════════════════════════════════════════════════════════════════════════
# ASYNC METHODS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAsyncHealthCheck:
    def test_healthy(self):
        svc = _make_service()
        resp = _resp(200)
        ctx = _async_ctx(resp)
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(svc.ahealth_check())
        assert r["status"] == "healthy"

    def test_unhealthy_non_200(self):
        svc = _make_service()
        resp = _resp(503)
        ctx = _async_ctx(resp)
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(svc.ahealth_check())
        assert r["status"] == "unhealthy"

    def test_connect_error(self):
        import httpx
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(svc.ahealth_check())
        assert r["status"] == "unreachable"

    def test_generic_error(self):
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.get = AsyncMock(side_effect=RuntimeError("broken"))
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(svc.ahealth_check())
        assert r["status"] == "error"


class TestAsyncListModels:
    def test_returns_models(self):
        svc = _make_service()
        resp = _resp(200, {"models": [{"name": "gemma2:9b", "size": 5_000_000_000,
                                       "modified_at": "2026-01-01", "digest": "abc123"}]})
        ctx = _async_ctx(resp)
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(svc.alist_models())
        assert len(r) == 1
        assert r[0]["name"] == "gemma2:9b"

    def test_connect_error_raises(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.get = AsyncMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                asyncio.get_event_loop().run_until_complete(svc.alist_models())


class TestAsyncGenerate:
    _RESP_DATA = {"response": "async hi", "done": True, "context": None,
                  "total_duration": 2_000_000_000, "eval_count": 5, "eval_duration": 1_000_000_000}

    def test_basic(self):
        svc = _make_service()
        ctx = _async_ctx(_resp(200, self._RESP_DATA))
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(svc.agenerate(prompt="Hello async"))
        assert r["response"] == "async hi"

    def test_with_system_and_max_tokens_and_context(self):
        svc = _make_service()
        ctx = _async_ctx(_resp(200, self._RESP_DATA))
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(
                svc.agenerate(prompt="test", system="sys", max_tokens=10, context=[1, 2])
            )
        assert r["response"] == "async hi"

    def test_404_model_error(self):
        from core.ollama_service import OllamaModelError
        svc = _make_service()
        ctx = _async_ctx(_resp(404, {}))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaModelError):
                asyncio.get_event_loop().run_until_complete(svc.agenerate(prompt="test"))

    def test_connect_error(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                asyncio.get_event_loop().run_until_complete(svc.agenerate(prompt="test"))

    def test_timeout_raises_service_error(self):
        import httpx
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                asyncio.get_event_loop().run_until_complete(svc.agenerate(prompt="test"))

    def test_generic_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=RuntimeError("fail"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                asyncio.get_event_loop().run_until_complete(svc.agenerate(prompt="test"))


class TestAsyncChat:
    _RESP_DATA = {"message": {"role": "assistant", "content": "async chat"},
                  "done": True, "total_duration": 1_000_000_000, "eval_count": 4, "eval_duration": 500_000_000}
    _MSGS = [{"role": "user", "content": "Hi"}]

    def test_basic(self):
        svc = _make_service()
        ctx = _async_ctx(_resp(200, self._RESP_DATA))
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(svc.achat(messages=self._MSGS))
        assert r["message"]["content"] == "async chat"

    def test_with_system_and_max_tokens(self):
        svc = _make_service()
        ctx = _async_ctx(_resp(200, self._RESP_DATA))
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(
                svc.achat(messages=self._MSGS, system="helpful", max_tokens=20)
            )
        assert r["message"]["role"] == "assistant"

    def test_404_model_error(self):
        from core.ollama_service import OllamaModelError
        svc = _make_service()
        ctx = _async_ctx(_resp(404, {}))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaModelError):
                asyncio.get_event_loop().run_until_complete(svc.achat(messages=self._MSGS))

    def test_connect_error(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                asyncio.get_event_loop().run_until_complete(svc.achat(messages=self._MSGS))

    def test_timeout_raises_service_error(self):
        import httpx
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                asyncio.get_event_loop().run_until_complete(svc.achat(messages=self._MSGS))

    def test_generic_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=RuntimeError("fail"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                asyncio.get_event_loop().run_until_complete(svc.achat(messages=self._MSGS))


class TestAsyncPullModel:
    def test_success(self):
        svc = _make_service()
        ctx = _async_ctx(_resp(200, {"status": "success"}))
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(svc.apull_model("llama3.2:3b"))
        assert r["model"] == "llama3.2:3b"

    def test_connect_error(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                asyncio.get_event_loop().run_until_complete(svc.apull_model("x:y"))

    def test_generic_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=RuntimeError("fail"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                asyncio.get_event_loop().run_until_complete(svc.apull_model("x:y"))


class TestAsyncDeleteModel:
    def test_success(self):
        svc = _make_service()
        ctx = _async_ctx(_resp(200, {}))
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(svc.adelete_model("llama3.2:3b"))
        assert r["status"] == "deleted"

    def test_404_raises_model_error(self):
        from core.ollama_service import OllamaModelError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        not_found = MagicMock()
        not_found.status_code = 404
        ctx.request = AsyncMock(return_value=not_found)
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaModelError):
                asyncio.get_event_loop().run_until_complete(svc.adelete_model("gone:model"))

    def test_connect_error(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.request = AsyncMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                asyncio.get_event_loop().run_until_complete(svc.adelete_model("x:y"))

    def test_generic_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.request = AsyncMock(side_effect=RuntimeError("fail"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                asyncio.get_event_loop().run_until_complete(svc.adelete_model("x:y"))


class TestAsyncGetRecommendedModels:
    def test_returns_all_recommended(self):
        from core.ollama_service import RECOMMENDED_MODELS
        svc = _make_service()
        with patch.object(svc, "alist_models", return_value=[{"name": "gemma2:9b"}]):
            r = asyncio.get_event_loop().run_until_complete(svc.aget_recommended_models())
        assert len(r) == len(RECOMMENDED_MODELS)

    def test_is_downloaded_flag(self):
        svc = _make_service()
        with patch.object(svc, "alist_models", return_value=[{"name": "gemma2:9b"}]):
            r = asyncio.get_event_loop().run_until_complete(svc.aget_recommended_models())
        by_name = {m["name"]: m for m in r}
        assert by_name["gemma2:9b"]["is_downloaded"] is True

    def test_list_models_error_falls_back_to_empty(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        with patch.object(svc, "alist_models", side_effect=OllamaServiceError("down")):
            r = asyncio.get_event_loop().run_until_complete(svc.aget_recommended_models())
        for m in r:
            assert m["is_downloaded"] is False


class TestAsyncModelInfo:
    _INFO_DATA = {"details": {"family": "gemma", "parameter_size": "9B",
                              "quantization_level": "Q4_K_M", "format": "gguf"},
                  "template": "{{prompt}}", "system": ""}

    def test_success(self):
        svc = _make_service()
        ctx = _async_ctx(_resp(200, self._INFO_DATA))
        with patch.object(svc, "_async_client", return_value=ctx):
            r = asyncio.get_event_loop().run_until_complete(svc.amodel_info("gemma2:9b"))
        assert r["family"] == "gemma"
        assert r["is_recommended"] is True

    def test_404_raises_model_error(self):
        from core.ollama_service import OllamaModelError
        svc = _make_service()
        ctx = _async_ctx(_resp(404, {}))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaModelError):
                asyncio.get_event_loop().run_until_complete(svc.amodel_info("not:here"))

    def test_connect_error(self):
        import httpx
        from core.ollama_service import OllamaConnectionError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=httpx.ConnectError("no"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaConnectionError):
                asyncio.get_event_loop().run_until_complete(svc.amodel_info("x:y"))

    def test_generic_error(self):
        from core.ollama_service import OllamaServiceError
        svc = _make_service()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=RuntimeError("fail"))
        with patch.object(svc, "_async_client", return_value=ctx):
            with pytest.raises(OllamaServiceError):
                asyncio.get_event_loop().run_until_complete(svc.amodel_info("x:y"))
