# Getting Support - ClawCoat

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

TelsonBase manages autonomous AI agents through earned trust — every agent carries a live Manners compliance score, starts at QUARANTINE, and advances only when behavior and human authorization align.

---

## Before You Ask

Check these first - most common issues are already documented:

- **[Troubleshooting Guide](docs/Operation%20Documents/TROUBLESHOOTING.md)** - Docker issues, auth failures, Redis errors, port conflicts, SSL problems
- **[FAQ](docs/FAQ.md)** - Common questions about architecture, security, and integrations
- **[Installation Guide - Windows](docs/Operation%20Documents/INSTALLATION_GUIDE_WINDOWS.md)** - Fresh install walkthrough
- **[GitHub Issues](https://github.com/QuietFireAI/ClawCoat/issues)** - Search open and closed issues before opening a new one

---

## How to Get Help

### Bugs and Errors

Open a **[GitHub Issue](https://github.com/QuietFireAI/ClawCoat/issues/new/choose)** using the Bug Report template.

Include:
- TelsonBase version: `curl http://localhost:8000/health`
- Docker version: `docker --version`
- Operating system and version
- The exact error message or unexpected behavior
- Steps to reproduce
- Relevant logs: `docker compose logs mcp_server --tail=100`

### Feature Requests

Open a **[GitHub Issue](https://github.com/QuietFireAI/ClawCoat/issues/new/choose)** using the Feature Request template. Describe the use case, not just the feature - understanding what you are trying to accomplish helps evaluate the request in context.

### Security Issues

**Do not open a public issue for security vulnerabilities.**

Report privately following the process in [SECURITY.md](SECURITY.md). Security issues are prioritized above all other work.

### General Questions

- **GitHub Discussions:** [github.com/QuietFireAI/ClawCoat/discussions](https://github.com/QuietFireAI/ClawCoat/discussions)
- **Email:** support@clawcoat.com

---

## Response Times

TelsonBase is maintained by a small team. Response times are best-effort.

| Channel | Expected response |
|---|---|
| Security reports | 48 hours |
| Bug reports (GitHub Issues) | 3-5 business days |
| Feature requests | Reviewed on rolling basis |
| General questions (Discussions) | Best effort |

---

## Contributing a Fix

If you have identified a bug and have a fix, pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the process. A PR with a fix will typically be reviewed faster than a bug report waiting for maintainer triage.

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
