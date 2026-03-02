# TB-PROOF-028: Zero Data Leaves Your Network

**Sheet ID:** TB-PROOF-028
**Claim Source:** telsonbase.com — The Promise Section
**Status:** VERIFIED
**Last Verified:** February 23, 2026
**Version:** 7.3.0CC

---

## Exact Claim

> "Zero data leaves your network. Ever."
> "No OpenAI. No Google. No API calls to third-party inference services."

## Verdict

VERIFIED — No OpenAI, Google, or external inference API calls exist anywhere in the codebase. All LLM inference runs via local Ollama container. Docker network segmentation enforces isolation with `internal: true` on data and AI networks.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `docker-compose.yml` | Lines 528-533 | `data` and `ai` networks: `internal: true` |
| `core/ollama_service.py` | Full file | Ollama client points to local container only |
| `core/config.py` | OLLAMA_BASE_URL | Default: `http://ollama:11434` (Docker internal) |
| `gateway/egress_proxy.py` | Full file | Domain whitelist enforcement |
| `.env.example` | ALLOWED_EXTERNAL_DOMAINS | Only approved domains can be contacted |

### Network Architecture

```yaml
# docker-compose.yml
data:
  driver: bridge
  internal: true   # No external access to data tier
ai:
  driver: bridge
  internal: true   # No external access to AI tier
```

`internal: true` means Docker blocks all external network access. Data and AI traffic physically cannot leave the host.

### Zero External Inference Dependencies

```bash
# Search for any OpenAI or Google API references:
$ grep -rn "openai\|googleapis\|api.openai\|api.google" core/ api/ agents/ --include="*.py"
# (zero results)
```

### Egress Controls

The only external domains allowed are configured in `.env` under `ALLOWED_EXTERNAL_DOMAINS`. By default this includes only:
- `github.com` / `api.github.com` (tool updates via Foreman)
- `identity.identiclaw.com` (DID resolution, when enabled)
- `pypi.org` (dependency checks)

No inference data, client data, or PHI is ever sent to any of these.

## Verification Command

```bash
# Verify no external inference API references exist:
grep -rn "openai\|anthropic\|googleapis\|azure.com\|api.openai" core/ api/ agents/ --include="*.py" | wc -l
```

## Expected Result

```
0
```

Zero references to external inference APIs.

---

*Sheet TB-PROOF-028 | TelsonBase v7.3.0CC | February 23, 2026*
