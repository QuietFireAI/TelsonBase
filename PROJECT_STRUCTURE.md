# TelsonBase Project Structure

```
telsonbase/
├── main.py                 # FastAPI application entry point
├── version.py              # Version identifier (SemVer)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build instructions
├── docker-compose.yml      # Full stack orchestration
├── docker-compose.federation-test.yml  # Multi-instance test setup
├── pytest.ini              # Test configuration
├── .env.example            # Environment template (copy to .env)
│
├── core/                   # Security & infrastructure
│   ├── config.py           # Centralized settings (pydantic)
│   ├── auth.py             # JWT authentication
│   ├── signing.py          # HMAC-SHA256 message signing
│   ├── capabilities.py     # Permission enforcement
│   ├── anomaly.py          # Behavioral detection
│   ├── approval.py         # Human-in-the-loop gates
│   ├── audit.py            # Security event logging
│   ├── middleware.py       # Rate limiting, circuit breaker
│   ├── persistence.py      # State management
│   └── qms.py              # Qualified Message Standard
│
├── agents/                 # Agent implementations
│   ├── base.py             # Base agent class
│   ├── backup_agent.py     # Automated backup agent
│   ├── demo_agent.py       # Example/template agent
│   ├── document_agent.py   # Document processing agent
│   └── alien_adapter.py    # Quarantine adapter for external frameworks
│
├── api/                    # API extensions
│   ├── mcp_gateway.py      # MCP server — Goose / Claude Desktop integration (13 tools, HITL-gated)
│   └── n8n_integration.py  # Legacy n8n endpoints (disabled — superseded by MCP gateway)
│
├── federation/             # Cross-instance trust
│   └── trust.py            # Federation manager, trust protocols
│
├── gateway/                # Network security
│   ├── egress_proxy.py     # Outbound traffic control
│   ├── Dockerfile          # Gateway container
│   └── requirements.txt    # Gateway dependencies
│
├── frontend/               # Dashboard UI
│   ├── Dashboard.jsx       # React dashboard component
│   ├── index.html          # Entry HTML
│   └── package.json        # Frontend dependencies
│
├── celery_app/             # Background task processing
│   └── worker.py           # Celery worker configuration
│
├── persistence/            # Data storage modules
│   └── (Redis/file adapters)
│
├── scripts/                # Utilities & examples
│   ├── test_security_flow.py    # API integration test
│   ├── test_federation.py       # Federation test
│   ├── seed_demo_data.py        # Demo data setup
│   ├── n8n_workflow_document_processing.json  # Legacy n8n workflow (reference only)
│   └── goose.yaml (→ project root)            # Goose MCP connection config for operators
│
├── tests/                  # Test suite
│   ├── conftest.py         # Pytest fixtures
│   ├── test_api.py         # API endpoint tests
│   ├── test_signing.py     # Cryptographic tests
│   └── test_capabilities.py # Permission tests
│
├── docs/                   # Technical documentation
│   ├── API_REFERENCE.md    # Endpoint documentation + Python client examples
│   ├── DEVELOPER_GUIDE.md  # Development guide + local setup
│   ├── SECURITY_ARCHITECTURE.md  # Security model
│   ├── INCIDENT_RESPONSE.md      # Incident response procedures
│   ├── DISASTER_RECOVERY.md      # Backup and recovery guide
│   ├── TROUBLESHOOTING.md        # Common issues and solutions
│   ├── ENV_CONFIGURATION.md      # Environment variable reference
│   ├── claude_code_comments.md   # AI collaborator commentary
│   └── gemini_comments.md        # AI collaborator commentary
│
├── LICENSE                 # Apache License 2.0 — open source, free for any use
├── README.md               # Project overview
├── CHANGELOG.md            # Version history
├── CONTRIBUTING.md         # Contribution guide
├── CODE_OF_CONDUCT.md      # Community standards
├── SECURITY.md             # Vulnerability reporting
├── GLOSSARY.md             # Term definitions
├── INSTALLATION_GUIDE_WINDOWS.md  # Windows-specific setup guide
├── TESTING.md              # Test procedures
└── Restore_and_Recover_Guide.md  # Backup/restore guide
```

---

## Key Files by Function

### Security Chain
```
main.py → core/auth.py → core/signing.py → core/capabilities.py → core/anomaly.py → core/approval.py
```

### Agent Execution
```
main.py → agents/base.py → agents/*_agent.py → core/capabilities.py → gateway/egress_proxy.py
```

### Federation Flow
```
main.py → federation/trust.py → core/signing.py → (remote instance)
```

---

## Environment Files

| File | Purpose | Git |
|------|---------|-----|
| `.env.example` | Template with all variables | ✓ Tracked |
| `.env` | Actual secrets | ✗ Ignored |
| `.dockerignore` | Build exclusions | ✓ Tracked |

---

## Docker Services (docker-compose.yml)

| Service | Port | Purpose |
|---------|------|---------|
| `mcp_server` | 8000 | Main API |
| `worker` | — | Celery background tasks |
| `beat` | — | Scheduled tasks |
| `redis` | 6379 | Message broker & cache |
| `ollama` | 11434 | Local LLM |
| `open-webui` | 3000 | Chat interface |
| `/mcp` endpoint | — | MCP gateway (Goose / Claude Desktop) — served at port 8000 |
| `mosquitto` | 1883 | MQTT broker |
| `traefik` | 80/443 | Reverse proxy & SSL |

---

*For setup instructions, see `README.md`. For API details, see `docs/API_REFERENCE.md`.*
