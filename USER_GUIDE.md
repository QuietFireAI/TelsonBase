# TelsonBase User Guide

**Version:** 9.0.0B
**For:** Solopreneurs, small teams, and anyone running TelsonBase for the first time

---

## What Is TelsonBase?

TelsonBase is a self-hosted platform for running AI agents on your own hardware. Instead of sending your data to cloud APIs, TelsonBase keeps everything local — your models, your data, your agents, your rules.

It runs as a set of Docker containers on any machine with Docker installed. Agents do work (process documents, manage real estate transactions, run local LLMs, manage backups), and TelsonBase makes sure they only do what you've authorized them to do.

**Key features:**

- **Zero-trust agent governance** — every agent action is authenticated, authorized, and audited
- **Local LLM inference** — chat and generate text with Ollama models, no data leaves your machine
- **Human-in-the-loop approval gates** — high-risk actions require your explicit approval before execution
- **Three authentication methods** — API key, JWT tokens, and DID-based identity (via Identiclaw)
- **Real estate vertical** — transaction management, compliance monitoring, and document preparation agents
- **Manners compliance** — runtime enforcement of Anthropic's agent safety principles
- **Multi-tenancy** — client-matter isolation with per-tenant rate limiting
- **Immutable audit chain** — SHA-256 hash-linked logs for tamper evidence

**The short version:** It's a secure, governed workbench for AI agents with built-in guardrails.

---

## Quick Start (5 Minutes)

### Prerequisites

- Docker Desktop installed and running
- At least 8GB RAM (16GB recommended if running Ollama for local LLM)
- Git (for cloning the repository)

### Step 1: Clone and Configure

```bash
git clone https://github.com/quietfire/telsonbase.git
cd telsonbase
cp .env.example .env
```

### Step 2: Generate Secrets

```bash
# Linux/Mac:
bash scripts/generate_secrets.sh

# Windows PowerShell:
# Generate random keys manually:
$key = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 48 | ForEach-Object {[char]$_})
echo $key
# Copy the output into your .env file for MCP_API_KEY and JWT_SECRET_KEY
```

### Step 3: Start Everything

```bash
docker compose up -d
```

This starts 10 containers:

| Container | Purpose | Port |
|---|---|---|
| **traefik** | Reverse proxy, TLS termination, HTTPS redirect | 80, 443 |
| **mcp_server** | Main API server (FastAPI) | 8000 |
| **redis** | State storage, caching, pub/sub | 6379 |
| **postgres** | Primary database (users, tenants, identities) | 5432 |
| **worker** | Background task processing (Celery) | — |
| **beat** | Scheduled tasks (daily checks, deadline monitoring) | — |
| **mosquitto** | Agent-to-agent messaging (MQTT) | 1883 |
| **ollama** | Local LLM inference | 11434 |
| **prometheus** | Metrics collection | 9090 |
| **grafana** | Monitoring dashboards | 3000 |

### Step 4: Verify It's Running

```bash
# Health check:
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "9.0.0B", ...}
```

---

## The Dashboard

TelsonBase has two web interfaces:

### Admin Dashboard

Open **http://localhost:8000/dashboard** in your browser.

The admin dashboard has 7 tabs:

| Tab | What It Shows |
|---|---|
| **Overview** | System health, agent status, quick stats, sovereign score |
| **Agents** | All agents with trust levels, capabilities, and action buttons |
| **Identity** | DID-authenticated agents, trust progression, revocation controls |
| **Approvals** | Pending and completed approval requests (approve/reject from here) |
| **QMS** | Message log with hash-chain verification, message type filtering |
| **Anomalies** | Behavioral anomaly alerts with severity and response actions |
| **Chat** | LLM chat interface (Ollama) — all inference local |

Log in with your API key (from `.env` file). The dashboard updates every 30 seconds.

### User Console

Open **http://localhost:8000/console** in your browser.

The user console is a simplified 5-tab interface for day-to-day operators:

| Tab | What It Shows |
|---|---|
| **Home** | Welcome card, quick stats, quick actions, activity feed |
| **Chat** | Full LLM chat interface |
| **Agents** | Read-only agent cards with capability details |
| **My Approvals** | Approve/reject requests with notes |
| **Activity** | QMS log, anomaly alerts, audit entries (read-only) |

---

## Authentication

TelsonBase supports three authentication methods:

### 1. API Key (simplest)

Pass your API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: YOUR_MCP_API_KEY" http://localhost:8000/v1/agents
```

### 2. JWT Token (for sessions)

Register a user, log in, and use the Bearer token:

```bash
# Register (first user):
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "YourSecurePassword123!", "role": "admin"}' \
  http://localhost:8000/v1/auth/register

# Login:
curl -X POST -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=YourSecurePassword123!" \
  http://localhost:8000/v1/auth/token

# Use the token:
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8000/v1/agents
```

### 3. DID Identity (via Identiclaw)

For agent-to-agent authentication using decentralized identifiers. See the [Identiclaw Operations Guide](docs/IDENTICLAW_OPERATIONS.md) for setup.

### Multi-Factor Authentication (MFA)

Enable TOTP-based MFA for any user account:

```bash
# Enable MFA:
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/v1/auth/mfa/enable

# Returns a QR code / secret for your authenticator app
```

### User Roles

| Role | Permissions |
|---|---|
| **viewer** | Read-only access to agents, status, and logs |
| **operator** | Viewer + approve/reject requests, run agent tasks |
| **manager** | Operator + manage agents, tenants, and tools |
| **admin** | Manager + user management, security settings, system config |
| **security** | Admin + key revocation, kill switch, audit export |

---

## Your First API Call

Every API call needs authentication. Use the API key from your `.env` file:

```bash
# List all available agents:
curl -H "X-API-Key: YOUR_MCP_API_KEY" http://localhost:8000/v1/agents

# Check the toolroom status:
curl -H "X-API-Key: YOUR_MCP_API_KEY" http://localhost:8000/v1/toolroom/status

# Get system health with details:
curl -H "X-API-Key: YOUR_MCP_API_KEY" http://localhost:8000/v1/system/health
```

---

## Key Concepts

### Agents Do the Work

Agents are the workers. Each one has a specific job and lives on one of three floors:

**Ground Level — Core Platform Agents:**
| Agent | Role |
|---|---|
| **backup_agent** | Backs up data on schedule (Redis, Postgres, configs) |
| **document_agent** | Reads, summarizes, searches, and redacts documents |
| **ollama_agent** | Runs local LLM inference (chat, generation, model management) |
| **demo_agent** | Testing and demonstration of security features |
| **memory_agent** | Agent memory and context management |

**Mezzanine — Supervisor Agents:**
| Agent | Role |
|---|---|
| **foreman_agent** | Manages the Toolroom (tool checkout, updates, HITL gates) |
| **goose_session** | External operator agent registered via MCP gateway (Goose / Claude Desktop) |

**Third Floor — Real Estate Vertical:**
| Agent | Role |
|---|---|
| **transaction_agent** | Real estate transaction lifecycle management |
| **compliance_check_agent** | Ohio regulatory compliance monitoring (licenses, fair housing, CE) |
| **doc_prep_agent** | Document generation from templates (purchase agreements, disclosures) |

You don't talk to agents directly. You send requests to the API, and TelsonBase routes them to the right agent.

### Agent Trust Levels

Every agent has a trust level that determines what it can do:

```
QUARANTINE → PROBATION → RESIDENT → CITIZEN
```

| Level | What It Means |
|---|---|
| **Quarantine** | New/untrusted agent. Cannot execute any actions. Under review. |
| **Probation** | Limited permissions. Actions are logged with extra scrutiny. |
| **Resident** | Standard operating level. Can execute authorized actions. |
| **Citizen** | Highest trust. Can perform supervisor-level operations. |

New agents start at **Quarantine** and must be promoted by an admin. Trust levels can be revoked instantly via the kill switch.

### The Toolroom

Agents can't install software or download tools on their own. They request tools from the **Toolroom**, and the **Foreman** (a supervisor agent) handles the request. The Foreman checks:

1. Is the tool from an approved source? (GitHub repos you've whitelisted)
2. Does the agent have sufficient trust level?
3. Does the tool require external API access? (If so, you have to approve it first)

Think of it like a machine shop: workers sign tools out, use them, sign them back in. Everything is logged.

### QMS — How Agents Talk

QMS (Qualified Message Standard) is TelsonBase's internal messaging format. You'll see it in logs:

```
Tool_Checkout_Please ::backup_agent:: ::tool_pgcli::
Tool_Checkout_Thank_You ::CHKOUT-a3f2b1c9d4e5::
```

The suffixes tell you what happened:
- `_Please` — A request was made
- `_Thank_You` — It succeeded
- `_Thank_You_But_No` — It was denied (with a reason)
- `_Pretty_Please` — Urgent/escalated request
- `_Excuse_Me` — Need clarification

Priority levels: `::!URGENT!::`, `::!P1!::`, `::!P2!::`, `::!P3!::`

You don't need to write QMS — it's automatic. But understanding it makes logs readable.

### HITL — Human-in-the-Loop

Any operation that touches the outside world (downloading a tool, calling an external API, closing a transaction, deleting a model) requires your explicit approval. TelsonBase creates an **Approval Request** and waits for you to approve or reject it.

Check pending approvals:
```bash
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/approvals/pending
```

Approve one:
```bash
curl -X POST -H "X-API-Key: YOUR_KEY" \
  http://localhost:8000/v1/approvals/APPR-abc123/approve
```

Or approve/reject from the Dashboard (Approvals tab) or User Console (My Approvals tab).

### Manners Compliance

TelsonBase enforces Anthropic's published agent safety principles at runtime:

| Principle | What It Means |
|---|---|
| **MANNERS-1: Human Control** | High-risk actions require approval gates |
| **MANNERS-2: Transparency** | All actions logged to immutable audit chain |
| **MANNERS-3: Value Alignment** | Agents confined to their declared role |
| **MANNERS-4: Privacy** | Data stays in designated paths, tenant-isolated |
| **MANNERS-5: Security** | Input validated, outputs verified, rate-limited |

Every agent is scored against these five principles. An agent that accumulates three violations in 24 hours is automatically quarantined. An agent below 0.25 compliance score cannot execute any actions.

---

## Common Tasks

### Running a Local LLM Query

If Ollama is running with a model loaded:

```bash
# Check available models:
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/llm/models

# Pull a model (requires approval):
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2"}' \
  http://localhost:8000/v1/llm/pull

# Generate text:
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2", "prompt": "Explain zero-trust security in one paragraph"}' \
  http://localhost:8000/v1/llm/generate

# Chat:
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "What is TelsonBase?"}]
  }' \
  http://localhost:8000/v1/llm/chat
```

Or use the **Chat** tab in either dashboard — it's a full LLM interface with model selection.

### Managing Real Estate Transactions

```bash
# Create a transaction:
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "purchase",
    "address": "123 Main St, Bellevue, OH 44811",
    "price": 185000
  }' \
  http://localhost:8000/v1/transactions

# List all transactions:
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/transactions

# Check deadlines:
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/transactions/deadlines

# Run compliance check:
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/compliance/check-all
```

The transaction agent runs a daily deadline check at 7:00 AM UTC. The compliance agent runs a daily sweep at 7:30 AM UTC. Both will flag issues automatically.

### Adding a Tool to the Toolroom

1. **Add the GitHub repo to approved sources:**
```bash
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"repo": "dbcli/pgcli"}' \
  http://localhost:8000/v1/toolroom/sources
```
This creates an approval request. Approve it, then execute:

```bash
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"repo": "dbcli/pgcli"}' \
  http://localhost:8000/v1/toolroom/sources/execute-add
```

2. **Propose installing the tool:**
```bash
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "github_repo": "dbcli/pgcli",
    "tool_name": "pgcli",
    "description": "PostgreSQL CLI with auto-completion",
    "category": "database"
  }' \
  http://localhost:8000/v1/toolroom/install/propose
```

3. **Approve the installation** (check `/v1/approvals/pending` for the request ID)

4. **Execute the installation** with the approval ID.

### Checking What's in the Toolroom

```bash
# All tools:
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/toolroom/tools

# Active checkouts (who has what):
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/toolroom/checkouts

# Cage archive (compliance trail):
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/toolroom/cage

# Approved GitHub sources:
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/toolroom/sources
```

### Managing DID Identities (Identiclaw)

If `IDENTICLAW_ENABLED=true` in your `.env`:

```bash
# List all DID-authenticated agents:
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/identity/list

# Register a new DID agent (requires approval):
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"did": "did:key:z6MkExample...", "display_name": "External Agent"}' \
  http://localhost:8000/v1/identity/register

# Revoke a DID (kill switch — immediate):
curl -X POST -H "X-API-Key: YOUR_KEY" \
  http://localhost:8000/v1/identity/did:key:z6MkExample.../revoke

# Reinstate after review:
curl -X POST -H "X-API-Key: YOUR_KEY" \
  http://localhost:8000/v1/identity/did:key:z6MkExample.../reinstate
```

The kill switch is instant, Redis-persisted, and checked before any cryptographic verification. See the [Identiclaw Operations Guide](docs/IDENTICLAW_OPERATIONS.md) for the full setup walkthrough.

### Managing Users and Tenants

```bash
# List users:
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/auth/users

# Create a tenant:
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Realty", "tier": "professional"}' \
  http://localhost:8000/v1/tenants

# Assign user to tenant:
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-123", "tenant_id": "tenant-456"}' \
  http://localhost:8000/v1/tenants/assign
```

---

## Environment Variables That Matter

These are in your `.env` file. The critical ones:

| Variable | What It Does | Default |
|---|---|---|
| `MCP_API_KEY` | Your API authentication key | (must set) |
| `JWT_SECRET_KEY` | Signs authentication tokens | (must set, 32+ chars) |
| `REDIS_URL` | Where Redis is | `redis://redis:6379/0` |
| `DATABASE_URL` | PostgreSQL connection | `postgresql://...` |
| `OLLAMA_BASE_URL` | Where Ollama is | `http://ollama:11434` |
| `CORS_ORIGINS` | Who can call the API | `["*"]` (lock down in prod) |
| `TELSONBASE_ENV` | `development` or `production` | `development` |
| `IDENTICLAW_ENABLED` | Enable DID identity integration | `false` |
| `RATE_LIMIT_PER_MINUTE` | API rate limit | `60` |

See `docs/System Documents/ENV_CONFIGURATION.md` for the complete list.

---

## Monitoring

### Logs

```bash
# All container logs:
docker compose logs -f

# Just the API:
docker compose logs -f mcp_server

# Just the worker (background tasks):
docker compose logs -f worker
```

Look for `REM:` prefixed lines — these are TelsonBase's internal logging. QMS messages show agent activity.

### Grafana Dashboard

Prometheus and Grafana are included in docker-compose:
- Open **http://localhost:3000** in your browser
- Default login: `admin` / (your `GRAFANA_ADMIN_PASSWORD`)
- Pre-built dashboard shows: API traffic, auth failures, agent activity, QMS message rates

### Health Endpoints

```bash
# Overall health:
curl http://localhost:8000/health

# LLM engine health:
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/v1/llm/health
```

---

## Security — What You Should Know

1. **Change the default secrets.** The `.env.example` has placeholder values. Replace them. Use `scripts/generate_secrets.sh` or generate random 48-character hex strings with `openssl rand -hex 32`.

2. **Lock down CORS in production.** Change `CORS_ORIGINS=["*"]` to your actual domain.

3. **The Foreman is the only agent that touches the internet.** All other agents are network-isolated. If you see any other agent making external requests, that's an anomaly.

4. **Every action is logged.** Audit logs are SHA-256 hash-chained for tamper evidence. You can export them for compliance review via the API.

5. **HITL gates can't be bypassed.** There's no `--force` flag that skips human approval for external operations. This is by design.

6. **Three auth methods.** API key for scripts, JWT for sessions, DID for agent-to-agent identity. All three can coexist.

7. **Kill switch.** Any agent (including DID-authenticated ones) can be instantly revoked. The kill switch is checked before cryptographic verification — it's immediate.

8. **Network segmentation.** Docker networks are separated into 5 tiers: `frontend`, `backend`, `data`, `ai`, and `monitoring`. The `data` and `ai` networks are `internal: true` — no external access.

9. **Non-root containers.** All containers run as UID 1000 (non-root). Base images are slim variants.

10. **Encryption.** AES-256-GCM for data at rest, TLS for all network traffic, bcrypt (cost 12) for passwords, Ed25519 for DID signatures.

For the complete security architecture, see `docs/System Documents/SECURITY_ARCHITECTURE.md`. For production hardening, see the checklist in `SECURITY.md`.

---

## Stopping and Restarting

```bash
# Stop everything (preserves data):
docker compose down

# Stop and delete data volumes (fresh start):
docker compose down -v

# Restart just one service:
docker compose restart mcp_server

# Rebuild after code changes:
docker compose up -d --build
```

Your data persists in Docker volumes: PostgreSQL (users, tenants, identities), Redis (state, cache, agent data), and Ollama (downloaded models). As long as volumes persist, your state survives restarts.

---

## Project Structure

```
telsonbase/
├── main.py                  # FastAPI application entry point
├── core/                    # Core platform modules
│   ├── config.py            # Centralized configuration (Settings)
│   ├── auth.py              # Authentication (API key, JWT, DID)
│   ├── audit.py             # SHA-256 hash-chained audit logging
│   ├── approval.py          # Human-in-the-loop approval gates
│   ├── identiclaw.py        # DID/VC identity engine (Identiclaw)
│   ├── manners.py           # Manners compliance runtime
│   ├── models.py            # SQLAlchemy database models
│   └── ...                  # 30+ security and compliance modules
├── agents/                  # Agent implementations
│   ├── registry.yaml        # Agent HR registry (Manners mappings)
│   ├── backup_agent.py      # Backup and recovery
│   ├── document_agent.py    # Document processing
│   ├── ollama_agent.py      # Local LLM inference
│   ├── transaction_agent.py # Real estate transactions
│   ├── compliance_check_agent.py  # Regulatory compliance
│   └── doc_prep_agent.py    # Document generation
├── api/                     # API route modules
│   ├── auth_routes.py       # User auth, MFA, sessions
│   ├── identiclaw_routes.py # DID identity management
│   ├── tenancy_routes.py    # Multi-tenancy
│   └── ...
├── frontend/                # Web dashboards
│   ├── index.html           # Admin dashboard (React SPA)
│   └── user-console.html    # Operator console (React SPA)
├── toolroom/                # Agent tool management
├── federation/              # Cross-instance trust
├── gateway/                 # Egress proxy (domain whitelist)
├── monitoring/              # Prometheus, Grafana, Mosquitto configs
├── alembic/                 # Database migrations
├── tests/                   # 673+ test suite
├── docs/                    # Documentation
├── licenses/                # Third-party license texts
├── MANNERS.md                  # Agent safety principles
├── SECURITY.md              # Security policy and hardening checklist
└── docker-compose.yml       # Container orchestration
```

---

## Getting Help

- **Troubleshooting:** See `docs/Operation Documents/TROUBLESHOOTING.md`
- **API Reference:** See `docs/System Documents/API_REFERENCE.md`
- **Architecture:** See `docs/System Documents/SECURITY_ARCHITECTURE.md`
- **Environment:** See `docs/System Documents/ENV_CONFIGURATION.md`
- **Identiclaw:** See `docs/IDENTICLAW_OPERATIONS.md`
- **Developer Guide:** See `docs/Operation Documents/DEVELOPER_GUIDE.md`
- **Deployment:** See `docs/Operation Documents/DEPLOYMENT_GUIDE.md`

---

## Who Built This

TelsonBase was created by Jeff Phillips (Quietfire AI) and built through collaboration with three AI models: ChatGPT (initial structure), Gemini (testing/validation), and Claude Code (engineering, security hardening, and Identiclaw integration). The complete attribution and methodology is documented in the project README and `docs/Partner Comments/claude_code_comments.md`.

---

*Last updated: March 1, 2026 — v9.0.0B*
