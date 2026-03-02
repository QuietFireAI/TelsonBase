# TelsonBase — Project Overview

**A Zero-Trust AI Agent Security Platform**
**Built for Data Sovereignty. Designed for Local-First Deployment.**

**Architect:** ::Jeff Phillips:: — ::support@telsonbase.com::
**Organization:** Quietfire AI
**Version:** 9.0.0B (March 1, 2026)
**License:** MIT

---

## What This Is

TelsonBase is a self-hosted AI agent security platform. It provides the infrastructure for running, monitoring, securing, and federating AI agents on hardware you own. Every component runs inside Docker containers on a single machine. No cloud dependencies. No external API calls required. No vendor lock-in.

The platform is designed for industries where data cannot leave the premises — legal, healthcare, finance, manufacturing — but the architecture applies to any organization that wants AI capabilities without surrendering data to third parties.

---

## What Makes This Different

### 1. Zero-Trust Agent Security Model

Every AI agent operates under a cryptographic identity and behavioral enforcement system. This is not "API key authentication." It's a layered security model:

- **Agent Registration:** Each agent receives an RSA-2048 keypair at registration. The public key is stored; the private key is held by the agent. No shared secrets.
- **Signed Actions:** Every action an agent takes is cryptographically signed with its private key and verified by the platform before execution. Tampered or unsigned actions are rejected.
- **Capability Enforcement:** Agents declare what they can do at registration. The platform enforces those boundaries at runtime. An agent registered for "document analysis" cannot perform "file system access" even if it tries.
- **Behavioral Anomaly Detection:** The platform tracks each agent's action patterns (frequency, timing, types) and flags deviations from established baselines. An agent that suddenly makes 100x its normal request rate triggers an alert.
- **Approval Gates:** Sensitive operations (model deletion, config changes, external network access) require explicit human approval before execution. Requests queue in Redis and wait for sign-off.
- **Egress Gateway:** All outbound network requests from agents pass through a controlled gateway with domain whitelisting. Agents cannot phone home, exfiltrate data, or contact unauthorized endpoints.
- **Audit Trail with Hash Chain:** Every security event is logged with a cryptographic hash chain (each entry includes the hash of the previous entry). Tampered or deleted audit entries break the chain and are detectable.

### 2. Qualified Message Standard (QMS)

QMS is a communication protocol that embeds human semantics directly into machine-parseable messages. It's not just a naming convention — it's a formal specification (v2.1.6) with grammar rules, priority levels, and inline data tagging.

Core suffixes create an implicit state machine:
- `_Please` — Request for action
- `_Thank_You` — Successful completion
- `_Thank_You_But_No` — Failed with explanation
- `_Excuse_Me` — Need clarification
- `_Pretty_Please` — High priority (triggers retain flags, elevated routing)

Inline tagging with `::double_colons::` marks extractable data within messages. Extended markers (`$$financial$$`, `##policy_id##`, `@@agent_target@@`, `??uncertainty??`) enable type-aware routing.

The result: `Backup_Failed_::Volume_Ollama_Data_Corrupted::_Thank_You_But_No` is simultaneously human-readable in a log stream and machine-parseable by any downstream agent or workflow.

No other agent communication standard does this. LangChain, CrewAI, and AutoGen all use structured JSON — machine-readable but opaque to humans. QMS makes agent behavior immediately debuggable without tooling.

### 3. Multi-AI Collaborative Development

TelsonBase was developed using a deliberate methodology: the architect (Jeff Phillips) directed implementation across three AI platforms — ChatGPT, Google Gemini, and Claude — rotating between them to reduce drift, hallucination, and single-platform bias. Each platform's contributions are tracked via version suffixes (G, C, CC).

This is documented in the codebase and is part of the project's story. Gemini ran the first external test suite (Colab). Claude built the security core, observability, and MQTT bus. ChatGPT contributed early architectural scaffolding. The rotation methodology itself — using cross-platform validation to maintain coherence — is a reproducible pattern for AI-assisted software development.

### 4. Federation — Cross-Instance Encrypted Trust

TelsonBase instances can establish trust relationships with other TelsonBase instances for cross-organizational agent collaboration. The federation protocol uses RSA-OAEP encrypted session key exchange, and all cross-instance messages are encrypted end-to-end. Trust levels (Standard, Elevated, Full) control what actions federated agents can perform.

This enables scenarios like: a law firm's document analysis agent sends a contract to an external compliance agent at an accounting firm, with every message encrypted, signed, and auditable on both sides.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    EXTERNAL TRAFFIC                         │
│                   (HTTPS via Traefik)                       │
└──────────────────────┬─────────────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────────────┐
│                  FRONTEND NETWORK                           │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐  │
│  │ Traefik │  │ Open-    │  │  MCP/mcp  │  │ Grafana   │  │
│  │ (SSL)   │  │ WebUI    │  │ (Goose)   │  │(Dashboards│  │
│  └────┬────┘  └──────────┘  └───────────┘  └───────────┘  │
└───────┼────────────────────────────────────────────────────┘
        │
┌───────▼────────────────────────────────────────────────────┐
│                  BACKEND NETWORK                            │
│  ┌───────────────┐  ┌──────────┐  ┌──────────┐            │
│  │  MCP Server   │  │  Worker  │  │   Beat   │            │
│  │  (FastAPI)    │  │ (Celery) │  │(Scheduler│            │
│  │  - Auth       │  │ - Agents │  │          │            │
│  │  - Signing    │  │ - Tasks  │  └──────────┘            │
│  │  - Egress     │  │ - Backup │                           │
│  │  - Metrics    │  └──────────┘                           │
│  └───────────────┘                                         │
└────────────────────────────────────────────────────────────┘
        │                    │
┌───────▼────────────┐  ┌───▼────────────────────────────────┐
│   DATA NETWORK     │  │        AI NETWORK                   │
│   (internal only)  │  │       (internal only)               │
│  ┌───────┐         │  │  ┌──────────┐  ┌───────────┐       │
│  │ Redis │         │  │  │  Ollama  │  │  NLWeb    │       │
│  │(Queue,│         │  │  │ (Local   │  │ (NL Query)│       │
│  │ Cache,│         │  │  │  LLMs)   │  │           │       │
│  │ State)│         │  │  └──────────┘  └───────────┘       │
│  ├───────┤         │  └────────────────────────────────────┘
│  │Mosquit│         │
│  │(MQTT) │         │  ┌────────────────────────────────────┐
│  └───────┘         │  │      MONITORING NETWORK             │
└────────────────────┘  │  ┌────────────┐  ┌─────────────┐   │
                        │  │ Prometheus │  │  cAdvisor   │   │
                        │  │  (Metrics) │  │(Containers) │   │
                        │  ├────────────┤  ├─────────────┤   │
                        │  │Redis Export│  │Node Exporter│   │
                        │  └────────────┘  └─────────────┘   │
                        └────────────────────────────────────┘
```

### Network Segmentation (5 Isolated Networks)

| Network | Internal | Purpose | Services |
|---------|----------|---------|----------|
| `frontend` | No | Public-facing services | Traefik, Open-WebUI, MCP Server (incl. `/mcp` gateway), Grafana |
| `backend` | No | Application logic | MCP Server, Worker, Beat |
| `data` | **Yes** | Data stores (no external access) | Redis, Mosquitto |
| `ai` | **Yes** | AI inference (no external access) | Ollama, NLWeb |
| `monitoring` | **Yes** | Observability (no external access) | Prometheus, Grafana, cAdvisor, exporters |

Services only join networks they need. If Redis is compromised, the attacker has no path to the frontend. If Ollama is compromised, it cannot reach the internet.

---

## Codebase Metrics

| Category | Lines | Files |
|----------|-------|-------|
| Application Python | ~25,000 | ~50 files |
| Test Python | ~8,000 | 10 test modules |
| Documentation (MD) | ~8,000 | 25+ docs |
| Config / Infrastructure | ~1,200 | docker-compose, prometheus, grafana, requirements |
| Frontend | ~400 | Dashboard HTML |
| **Total** | **~42,000** | **~90 files** |

### Test Coverage

**509 tests across 10 modules. All passing.**

| Test Module | Tests | Scope |
|-------------|-------|-------|
| `test_api.py` | 19 | API endpoints, auth flow, federation surface |
| `test_capabilities.py` | 15 | Capability enforcement, permission boundaries |
| `test_signing.py` | 13 | Cryptographic signing, key management, verification |
| `test_security.py` | ~60 | Auth, rate limiting, anomaly detection, approval gates |
| `test_egress.py` | ~30 | Egress gateway, domain whitelisting, blocking |
| `test_behavioral.py` | ~50 | Behavioral baselines, anomaly scoring, drift detection |
| `test_metrics.py` | ~40 | Prometheus instrumentation, counter/histogram behavior |
| `test_mqtt_bus.py` | 26 | MQTT agent communication, topic routing, QMS events |
| `test_mqtt_stress.py` | 26 | Load testing, rapid publish, priority handling, isolation |
| `test_secrets.py` | 48 | Docker secrets resolution, validation, rotation |
| Integration scripts | 2 | Live security flow, federation handshake |

### Security Modules (core/)

| Module | Lines | Purpose |
|--------|-------|---------|
| `auth.py` | ~400 | JWT tokens, API key validation, permission enforcement |
| `signing.py` | ~350 | RSA-2048 keypairs, action signing, verification, revocation |
| `capabilities.py` | ~300 | Agent capability declarations, runtime enforcement |
| `approval.py` | ~350 | Human-in-the-loop approval gates, webhook callbacks |
| `behavioral.py` | ~400 | Action frequency tracking, anomaly scoring, baseline drift |
| `audit.py` | ~250 | Hash-chain audit logging, tamper detection |
| `encryption.py` | ~200 | AES-256-GCM at rest, PBKDF2 key derivation |
| `egress.py` | ~300 | Outbound request interception, domain whitelisting |
| `metrics.py` | ~250 | 12 Prometheus metric families, request/agent/security instrumentation |
| `mqtt_bus.py` | ~400 | Agent-to-agent MQTT communication, QMS event publishing |
| `secrets.py` | ~300 | Docker secrets resolution, SecretValue masking, validation |
| `rotation.py` | ~150 | Secret rotation scheduling, key lifecycle management |

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Server | FastAPI + Uvicorn | HTTP API, Swagger docs, async request handling |
| Task Queue | Celery + Redis | Background agent task execution |
| Scheduler | Celery Beat | Periodic tasks (backups, rotation) |
| Message Broker | Redis | Celery broker, state persistence, caching |
| MQTT Broker | Eclipse Mosquitto | Agent-to-agent real-time messaging |
| Local AI | Ollama | Local LLM inference (llama3, phi3, gemma2, etc.) |
| Reverse Proxy | Traefik v2.10 | SSL termination, Let's Encrypt automation |
| Monitoring | Prometheus + Grafana | Metrics collection, dashboards, alerting |
| Container Metrics | cAdvisor + Node Exporter | Docker and host-level metrics |
| AI Chat UI | Open-WebUI | Human-AI conversation interface |
| Agent Interface | MCP gateway (`/mcp`) | Goose / Claude Desktop integration — operator-authenticated, HITL-gated |
| Secrets | Docker Secrets + generate_secrets.sh | tmpfs-mounted secrets, never on disk |

All Python dependencies are version-pinned for reproducible builds.

---

## What a DevOps Engineer Needs to Know

### Deployment is One Command

```bash
# 1. Clone and enter directory
git clone <repo> && cd telsonbase

# 2. Generate secrets
chmod +x scripts/generate_secrets.sh
./scripts/generate_secrets.sh

# 3. Configure
cp .env.example .env
# Edit: TRAEFIK_ACME_EMAIL, TRAEFIK_DOMAIN, TELSONBASE_ENV

# 4. Launch
docker-compose up --build -d

# 5. Verify
docker-compose ps          # All services healthy
curl http://localhost:8000/ # API responds
```

### Secrets Management

No plaintext credentials in `.env` for production. All secrets are generated by `generate_secrets.sh`, stored in `./secrets/` (mode 600, directory mode 700), and mounted via Docker Secrets at `/run/secrets/` inside containers. The SecretsProvider resolves secrets in order: Docker secrets file → environment variable → hard error. Production mode (`TELSONBASE_ENV=production`) blocks startup if any required secret is missing or uses an insecure default.

### Backup Strategy

Three tiers, all automated:
- **Daily snapshots** via Celery Beat (every 24h)
- **Startup snapshots** on container restart (23h cooldown)
- **Deployment snapshots** triggered manually before code changes

Archives are `.tar.gz` files stored in `./backups/{type}/` on the host. Restore process documented in `RESTORE_RECOVERY_GUIDE.md` — tested procedure, not theory.

### Monitoring

Prometheus scrapes 5 targets: MCP Server application metrics, Redis (via exporter), Docker containers (via cAdvisor), host (via Node Exporter), and Prometheus itself. Grafana auto-provisions with a TelsonBase infrastructure dashboard on first boot. Application-level metrics include request latency histograms, active agent counts, security event counters, and Ollama inference timing.

---

## What a Security Engineer Needs to Know

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| Compromised agent attempts data exfiltration | Egress gateway with domain whitelist. Internal-only networks for data/AI tiers. |
| Agent escalates privileges beyond registration | Capability enforcement at request time. Signed capability manifests. |
| Unauthorized API access | JWT + API key dual auth. Rate limiting. Failed auth logged with hash chain. |
| Tampered audit logs | SHA-256 hash chain. Each entry includes previous entry's hash. Break = detectable. |
| Insider modifies secrets | Docker secrets on tmpfs. Never written to container disk. Generate_secrets.sh with mode 600. |
| Supply chain attack on dependencies | All dependencies version-pinned. No floating versions. |
| Lateral movement after container compromise | 5 isolated Docker networks. Data and AI networks marked internal (no external route). |
| Agent behavioral anomaly (hijacked or malfunctioning) | Baseline tracking, frequency analysis, anomaly scoring. Alerts via MQTT Pretty_Please. |

### Encryption

- **In transit:** TLS 1.2+ via Traefik / Let's Encrypt
- **At rest:** AES-256-GCM with PBKDF2-derived keys
- **Agent signing:** RSA-2048 with SHA-256 digest
- **Federation:** RSA-OAEP session key exchange, AES-256 message encryption
- **Secrets:** Docker tmpfs mount, never on disk, SecretValue wrapper prevents log leakage

---

## Development Methodology

### Multi-AI Collaborative Engineering

This project was built using a documented methodology of rotating between AI platforms to cross-validate architecture and implementation:

- **Claude (Anthropic):** Security core, observability stack, MQTT bus, secrets management, test suite expansion, production hardening. Primary implementation partner.
- **Gemini (Google):** External test validation (Colab environment), dependency conflict identification, independent bug discovery.
- **ChatGPT (OpenAI):** Early architectural scaffolding, initial QMS concept development.

The rotation serves as a form of cross-validation. Each platform reviews the others' output. Drift, hallucination, and single-platform bias are caught by submitting the same codebase to a different model for analysis. This methodology is itself a contribution — a reproducible pattern for AI-assisted software development.

### Version History

| Version | Platform | Key Changes |
|---------|----------|-------------|
| 1.0.0 | ChatGPT | Initial scaffolding, docker-compose, basic API |
| 3.0.0 | Claude | Security kernel, federation, agent framework |
| 3.0.1 | Claude | Gemini-identified bugs fixed (3 bugs, 3 files) |
| 4.0.1C | Claude | Behavioral testing, QMS viewer, sovereign score |
| 4.1.0CC | Claude Code | Redis persistence, key revocation, federation crypto |
| 4.8.0CC | Claude Code | Ollama integration, model management endpoints |
| 5.0.0CC | Claude Code | Prometheus/Grafana observability, metrics instrumentation |
| 5.1.0CC | Claude Code | Secrets management, MQTT bus, stress tests, outer wrapper fixes |

---

## What This Project Proves

1. A 42,000-line zero-trust AI agent platform can be built on consumer hardware.
2. Multi-AI collaborative development produces more robust output than single-platform development.
3. Data sovereignty is not a marketing term — it's an architecture with 509 passing tests.
4. AI-assisted development, directed by a human architect with clear vision, can produce production-grade infrastructure.
5. QMS makes agent behavior immediately debuggable without specialized tooling.
6. Local-first AI deployment is not just possible — it's preferable for any organization that takes data ownership seriously.

---

## Contact

**Jeff Phillips** — Architect
support@telsonbase.com

**Quietfire AI** — quietfireai.com
