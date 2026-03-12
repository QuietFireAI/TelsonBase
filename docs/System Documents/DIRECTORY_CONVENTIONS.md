# TelsonBase - Directory & Naming Conventions

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

---

## The Building Metaphor

TelsonBase is structured as a building. This release is **Ground Level** - the foundation that everything else sits on. Future development builds upward (new agent layers, UI, marketplace) and downward (deeper kernel security, hardware integration, firmware-level sovereignty).

---

## Naming Conventions Going Forward

### Project Root Directory

| Convention | Notes |
|------------|-------|
| `telsonbase/` | Canonical root directory name. Version lives in the archive filename. |
| `quietfire_mcp_server/` | Legacy name - retired. |

### Tarball / Archive Naming

Format: `telsonbase_v{MAJOR}.{MINOR}.{PATCH}{SUFFIX}.{ext}`

Examples:
- `telsonbase_v5.1.0CC.tar.gz`
- `telsonbase_v5.1.0CC.zip`
- `telsonbase_v6.0.0G.tar.gz` (Gemini-contributed release)

**Suffixes:**
- `G` - Gemini save / contribution
- `C` - Claude save / contribution
- `CC` - Claude Code contribution
- No suffix - Jeff's direct work

### Internal References

All Python files, configs, and documentation reference **TelsonBase** as the project name. All code uses `TelsonBase` (display) or `telsonbase` (identifier) exclusively.

```python
# Old:
# TelsonBase/core/auth.py

# New:
# TelsonBase/core/auth.py
```

### The Building Floors

| Floor | Description | Status |
|-------|-------------|--------|
| **Below Ground** | Hardware integration, firmware sovereignty, Snowball device protocols | Future |
| **Foundation** | Docker orchestration, network segmentation, secrets management | ✅ Built |
| **Ground Level** | Core security platform: auth, signing, capabilities, audit, encryption, approval gates, egress control, behavioral anomaly detection | ✅ Built |
| **Mezzanine** | Agent framework: MQTT bus, Celery workers, QMS protocol, Ollama integration | ✅ Built |
| **First Floor** | Observability: Prometheus metrics, Grafana dashboards, health endpoints | ✅ Built |
| **Second Floor** | Federation: cross-instance trust, encrypted messaging, session key exchange | ✅ Built |
| **Third Floor** | Specialized agents: legal, real estate, healthcare, financial | Future |
| **Fourth Floor** | Agent marketplace, plugin model, third-party sandboxed execution | Future |
| **Penthouse** | Multi-instance mesh, sovereign cloud federation, Quiet Fire SaaS offering | Future |

### Dashboard Navigation Note

Agent registration lives in the **Agents tab**, not the OpenClaw tab. The Agents tab covers all agent types (OpenClaw, Generic, DID). The OpenClaw tab is monitoring-only - trust levels, action counts, Manners scores. A "Register Agent" shortcut in the OpenClaw tab header links back to the same registration modal. See [DASHBOARD_agent_registration.md](../DASHBOARD_agent_registration.md) for the full click path.

### Package / Module Names

Internal Python packages keep their current names. No rename needed:

```
telsonbase/
├── core/          # Security kernel
├── agents/        # Agent implementations
├── federation/    # Cross-instance trust
├── toolroom/      # Tool management
├── api/           # Route definitions
├── gateway/       # Egress control
├── celery_app/    # Task queue
├── scripts/       # Bootstrap and test scripts
├── tests/         # Test suite
├── monitoring/    # Prometheus/Grafana configs
├── frontend/      # Dashboard HTML
├── secrets/       # Generated secrets (gitignored)
├── backups/       # Backup archives (gitignored)
└── logs/          # Runtime logs (gitignored)
```

### Environment Variable Prefix

Convention: `TELSONBASE_` (e.g., `TELSONBASE_ENCRYPTION_KEY`, `TELSONBASE_ENV`)

### Docker Compose Service Names

No change needed. Service names (`mcp_server`, `worker`, `beat`, `redis`, etc.) are functional descriptions, not project names. They're correct as-is.

### Docker Volume Prefix

Convention: `telsonbase_` (Docker auto-prefixes from the root directory name)

---

## Summary

The project is **TelsonBase**. The directory is `telsonbase/`. The version is in the archive filename. This is Ground Level. We build from here.
