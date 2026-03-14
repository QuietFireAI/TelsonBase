# Third-Party Notices - ClawCoat v11.0.1

TelsonBase incorporates and depends on open-source software. This document
lists all third-party dependencies, their licenses, and the corresponding
license files in this directory.

---

## Python Packages (requirements.txt)

| Package | Version | License | File |
|---|---|---|---|
| FastAPI | 0.125.0 | MIT | [MIT.txt](MIT.txt) |
| Uvicorn | 0.27.1 | BSD-3-Clause | [BSD-3-Clause.txt](BSD-3-Clause.txt) |
| Gunicorn | 25.0.3 | MIT | [MIT.txt](MIT.txt) |
| Pydantic | 2.9.2 | MIT | [MIT.txt](MIT.txt) |
| pydantic-settings | 2.6.1 | MIT | [MIT.txt](MIT.txt) |
| Celery | 5.3.6 | BSD-3-Clause | [BSD-3-Clause.txt](BSD-3-Clause.txt) |
| redis (Python) | 5.0.1 | MIT | [MIT.txt](MIT.txt) |
| paho-mqtt | 1.6.1 | EPL-2.0 / EDL-1.0 | [EPL-2.0.txt](EPL-2.0.txt) |
| requests | 2.32.5 | Apache-2.0 | [Apache-2.0.txt](Apache-2.0.txt) |
| python-jose | 3.5.0 | MIT | [MIT.txt](MIT.txt) |
| passlib | 1.7.4 | BSD-2-Clause | [BSD-2-Clause.txt](BSD-2-Clause.txt) |
| pyotp | 2.9.0 | MIT | [MIT.txt](MIT.txt) |
| python-json-logger | 2.0.7 | BSD-2-Clause | [BSD-2-Clause.txt](BSD-2-Clause.txt) |
| prometheus-client | 0.20.0 | Apache-2.0 | [Apache-2.0.txt](Apache-2.0.txt) |
| httpx | 0.28.1 | BSD-3-Clause | [BSD-3-Clause.txt](BSD-3-Clause.txt) |
| starlette | >=0.47.2 | BSD-3-Clause | [BSD-3-Clause.txt](BSD-3-Clause.txt) |
| mcp | >=1.2.0 | MIT | [MIT.txt](MIT.txt) |
| cryptography | 46.0.5 | Apache-2.0 / BSD-3 | [Apache-2.0.txt](Apache-2.0.txt) |
| SQLAlchemy | 2.0.36 | MIT | [MIT.txt](MIT.txt) |
| psycopg2-binary | 2.9.10 | LGPL-3.0 | [LGPL-3.0.txt](LGPL-3.0.txt) |
| Alembic | 1.13.3 | MIT | [MIT.txt](MIT.txt) |

### Test Dependencies (not distributed)

| Package | Version | License | Notes |
|---|---|---|---|
| pytest | 7.4.4 | MIT | Development only |
| pytest-asyncio | 0.23.4 | Apache-2.0 | Development only |
| pytest-mock | 3.12.0 | MIT | Development only |

---

## Docker Images

| Image | Version | License | File | Notes |
|---|---|---|---|---|
| python | 3.11-slim-bookworm | PSF | [PSF.txt](PSF.txt) | Base image |
| redis | 7-alpine | BSD-3-Clause | [BSD-3-Clause.txt](BSD-3-Clause.txt) | Cache + pub/sub |
| postgres | 16-alpine | PostgreSQL | [PostgreSQL.txt](PostgreSQL.txt) | Primary database |
| ollama/ollama | latest | MIT | [MIT.txt](MIT.txt) | Local LLM inference |
| traefik | v2.10 | MIT | [MIT.txt](MIT.txt) | Reverse proxy |
| eclipse-mosquitto | 2 | EPL-2.0 / EDL-1.0 | [EPL-2.0.txt](EPL-2.0.txt) | MQTT broker |
| prom/prometheus | v2.49.1 | Apache-2.0 | [Apache-2.0.txt](Apache-2.0.txt) | Metrics collection |
| grafana/grafana | 10.3.1 | AGPL-3.0 | [AGPL-3.0.txt](AGPL-3.0.txt) | See usage notes |
| open-webui | main | MIT | [MIT.txt](MIT.txt) | LLM chat UI |

---

## Frontend Libraries (CDN / Inline)

| Library | Version | License | Notes |
|---|---|---|---|
| React | 18.x | MIT | Vendored locally (`frontend/vendor/react.production.min.js`) |
| ReactDOM | 18.x | MIT | Vendored locally (`frontend/vendor/react-dom.production.min.js`) |
| Babel Standalone | 7.x | MIT | Vendored locally (`frontend/vendor/babel.min.js`) |
| Tailwind CSS | 3.x | MIT | Loaded via CDN |

---

## License Files in This Directory

| File | License Type | Packages Covered |
|---|---|---|
| [MIT.txt](MIT.txt) | MIT License | FastAPI, Gunicorn, Pydantic, redis-py, python-jose, pyotp, SQLAlchemy, Alembic, Ollama, Traefik, Open WebUI, React, Tailwind |
| [BSD-3-Clause.txt](BSD-3-Clause.txt) | BSD 3-Clause | Uvicorn, Celery, httpx, Redis (server) |
| [BSD-2-Clause.txt](BSD-2-Clause.txt) | BSD 2-Clause | passlib, python-json-logger |
| [Apache-2.0.txt](Apache-2.0.txt) | Apache License 2.0 | requests, prometheus-client, cryptography, Prometheus |
| [PSF.txt](PSF.txt) | Python Software Foundation | Python 3.11 |
| [PostgreSQL.txt](PostgreSQL.txt) | PostgreSQL License | PostgreSQL 16 |
| [EPL-2.0.txt](EPL-2.0.txt) | Eclipse Public License 2.0 | Mosquitto, paho-mqtt |
| [AGPL-3.0.txt](AGPL-3.0.txt) | GNU AGPL 3.0 | Grafana (unmodified, separate service) |
| [LGPL-3.0.txt](LGPL-3.0.txt) | GNU LGPL 3.0 | psycopg2-binary (dynamically linked) |

---

## Optional External Integrations

These services are not bundled with TelsonBase. They are optional integrations enabled by operator configuration. No code from these services is distributed with TelsonBase.

| Service | Provider | License / Terms | Notes |
|---|---|---|---|
| OpenClaw | OpenClaw project | Provider terms | Autonomous AI agent. TelsonBase acts as a governed MCP proxy - OpenClaw is not modified. Optional integration. |
| Goose | Block, Inc. | Apache-2.0 | Open-source MCP agent operator. Optional integration. |
| Identiclaw | vouched.id | Provider terms | DID-based agent identity. Planned future integration. Runs on operator's own Cloudflare account. |

---

## Important Notes

1. **Grafana (AGPL-3.0)**: TelsonBase runs unmodified Grafana as a separate
   Docker container. No Grafana code is embedded in or distributed with
   TelsonBase. AGPL copyleft is not triggered for TelsonBase's source code.

2. **n8n**: Removed from the TelsonBase stack as of Feb 2026. Replaced by the native MCP gateway (`api/mcp_gateway.py`). License file removed.

3. **psycopg2 (LGPL-3.0)**: Used as a dynamically-linked Python library.
   This constitutes "use of the Library" under LGPL, not a derivative work.
   TelsonBase's own license is not affected.

4. **CDN Dependencies**: React, Babel, and Tailwind CSS are loaded from
   CDN in the dashboard HTML files. No source code is bundled. For
   air-gapped deployments, these can be self-hosted.
