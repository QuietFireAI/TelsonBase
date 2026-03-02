# TB-PROOF-029: Local LLM Inference via Ollama

**Sheet ID:** TB-PROOF-029
**Claim Source:** telsonbase.com — The Promise Section
**Status:** VERIFIED
**Last Verified:** February 23, 2026
**Version:** 7.3.0CC

---

## Exact Claim

> "All AI processing runs via Ollama on your hardware. No OpenAI. No Google. No API calls to third-party inference services. The data physically cannot leave."

## Verdict

VERIFIED — `core/ollama_service.py` and `agents/ollama_agent.py` handle all LLM inference through a local Ollama Docker container on the `ai` network (internal only).

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/ollama_service.py` | Full file | Async Ollama client (httpx → local container) |
| `agents/ollama_agent.py` | Full file | Agent wrapper for LLM operations |
| `docker-compose.yml` | Lines 235-270 | Ollama service definition on `ai` network |
| `core/config.py` | OLLAMA_BASE_URL setting | Default: `http://ollama:11434` |

### Docker Configuration

```yaml
# docker-compose.yml
ollama:
  image: "ollama/ollama:latest"
  networks:
    - ai         # ai network is internal: true
  volumes:
    - ollama_data:/root/.ollama

ai:
  driver: bridge
  internal: true   # No external access
```

### LLM API Endpoints

All inference routes in `main.py`:
- `POST /v1/llm/generate` — text generation
- `POST /v1/llm/chat` — chat conversation
- `GET /v1/llm/models` — list available models
- `POST /v1/llm/pull` — download model (requires approval)
- `DELETE /v1/llm/models/{name}` — remove model (requires approval)
- `GET /v1/llm/health` — Ollama health check

Every endpoint routes through `core/ollama_service.py` which uses `httpx.AsyncClient` pointing to `OLLAMA_BASE_URL` (Docker-internal address).

### Code Evidence

```python
# core/ollama_service.py
self.base_url = settings.ollama_base_url  # http://ollama:11434
self.client = httpx.AsyncClient(base_url=self.base_url)
```

## Verification Command

```bash
grep -n "ollama_base_url\|OLLAMA_BASE_URL\|base_url" core/ollama_service.py core/config.py | head -10
```

## Expected Result

All references point to `http://ollama:11434` (Docker internal network address).

---

*Sheet TB-PROOF-029 | TelsonBase v7.3.0CC | February 23, 2026*
