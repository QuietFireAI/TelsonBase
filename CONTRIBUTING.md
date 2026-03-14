# Contributing to ClawCoat

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

Welcome. TelsonBase is a platform for managing autonomous AI agents through earned trust — agents earn autonomy through demonstrated behavior and explicit human authorization, tracked by a live Manners compliance score across five trust tiers. Contributions that strengthen earned-autonomy controls, data sovereignty, and compliance are valued.

See also: [Ambassador Program](docs/AMBASSADORS.md) for non-code contributions.

---

## Quick Start

```bash
# Clone
git clone https://github.com/QuietFireAI/ClawCoat.git
cd TelsonBase

# Copy environment, then generate all secrets (run in Git Bash on Windows)
cp .env.example .env
bash scripts/generate_secrets.sh

# Start services
docker compose up --build -d

# Run migration (required on first start)
docker compose exec mcp_server alembic upgrade head

# Run tests (720 tests, all must pass)
docker compose exec mcp_server python -m pytest tests/ -v --tb=short
```

---

## Code Standards

### 1. REM Comments

TelsonBase uses `REM:` prefix for architectural documentation comments. This is intentional-it distinguishes design rationale from implementation notes.

```python
# REM: This function validates QMS message format before cryptographic signing.
# REM: The order matters: format validation MUST precede signing to prevent
# REM: malformed messages from receiving valid signatures.
def validate_and_sign(message: str) -> SignedMessage:
    ...
```

Use REM comments to explain:
- **Why** a design decision was made
- **Security implications** of the code
- **Dependencies** between components

### 2. QMS™ (Qualified Message Standard)

All agent-to-agent communication uses QMS suffixes:

| Suffix | Meaning | Example |
|--------|---------|---------|
| `_Please` | Request | `Backup_Data_Please` |
| `_Thank_You` | Success | `Backup_Complete_Thank_You` |
| `_Thank_You_But_No` | Failure | `Backup_Failed_::Disk_Full::_Thank_You_But_No` |
| `_Excuse_Me` | Need clarification | `Target_Path_Missing_Excuse_Me` |
| `_Pretty_Please` | High priority | `Security_Alert_Pretty_Please` |

Field markers use double colons: `::important_value::`

```python
# Good
logger.info("Agent_Registration_::agent_001::_Thank_You")

# Bad
logger.info("Agent registered successfully")
```

### 3. Capability Declarations

Every agent must declare capabilities explicitly:

```python
AGENT_CAPABILITIES = {
    "agent_id": "document_processor",
    "capabilities": [
        "document:read",
        "document:summarize",
        "document:extract",
        # NOT "document:*" - explicit only
    ],
    "max_tokens_per_request": 10000,
    "allowed_external_domains": []  # Empty = no external access
}
```

### 4. Python Style

- PEP 8 compliance
- Type hints required for public functions
- Pydantic models for all API request/response schemas
- `async def` for I/O operations

---

## Testing Requirements

### Before Submitting PR

```bash
# All tests must pass (run inside the container)
docker compose exec mcp_server python -m pytest tests/ -v

# Specific test files
docker compose exec mcp_server python -m pytest tests/test_api.py -v
docker compose exec mcp_server python -m pytest tests/test_signing.py -v
docker compose exec mcp_server python -m pytest tests/test_capabilities.py -v
```

### Test Categories

1. **Unit Tests** (`tests/test_*.py`)
  - Test individual functions
  - Mock external dependencies
  - Fast execution

2. **Security Flow Tests** (`scripts/test_security_flow.py`)
  - Requires running Docker stack
  - Tests full authentication chain
  - Tests capability enforcement

3. **Federation Tests** (`docker-compose.federation-test.yml`)
  - Multi-instance trust establishment
  - Cross-instance message signing
  - Trust revocation

### Writing New Tests

```python
# tests/test_my_feature.py

import pytest
from core.signing import SigningService

def test_signature_verification():
    """
    REM: Verify that tampered messages fail signature check.
    """
    signer = SigningService()
    message = "Test_Message_Please"
    signed = signer.sign(message)
    
    # Tamper with message
    signed.message = "Tampered_Message_Please"
    
    assert not signer.verify(signed), "Tampered message should fail verification"
```

---

## Pull Request Process

### 1. Branch Naming

```
feature/add-agent-capability
fix/signing-verification-edge-case
docs/update-api-reference
security/patch-egress-bypass
```

### 2. Commit Messages

```
[AREA] Brief description

- Detail 1
- Detail 2

Fixes #123
```

Areas: `[API]`, `[SECURITY]`, `[AGENTS]`, `[FEDERATION]`, `[DOCS]`, `[TESTS]`

### 3. PR Checklist

- [ ] Tests pass (`docker compose exec mcp_server python -m pytest tests/ -v`)
- [ ] New code has REM comments explaining design decisions
- [ ] QMS conventions followed for agent messages
- [ ] Capabilities explicitly declared (no wildcards)
- [ ] Security implications documented
- [ ] CHANGELOG entry added (if user-facing)

### 4. Review Process

1. Automated tests run
2. Code review by maintainer
3. Security review for security-sensitive changes
4. Merge after approval

---

## Security Contributions

For security vulnerabilities, **DO NOT** open a public issue.

See `SECURITY.md` for responsible disclosure process.

---

## Areas Needing Contribution

### High Priority
- Industry-specific compliance validation (healthcare, legal, insurance, accounting)
- OpenClaw governance integration testing with real agent workflows
- Trust level UX feedback (is the Quarantine → Citizen path intuitive?)
- Security auditing and penetration testing
- Dashboard UI improvements (`frontend/`)

### Medium Priority
- Deployment guides for specific environments (NAS, rack server, cloud VM)
- Agent skill development with governance integration
- Prometheus/Grafana dashboard templates
- CI/CD pipeline setup
- Performance benchmarks

### Documentation
- Industry deployment case studies
- API usage examples
- Video tutorials
- Compliance framework deep-dives

---

## Good First Issues

New to TelsonBase? These areas are great starting points:

### Documentation Improvements
- Add deployment guides for specific cloud providers (AWS, Azure, GCP)
- Expand troubleshooting sections with edge cases
- Add more API client examples (JavaScript, Go, Rust)
- Improve inline code comments for complex security logic

### Test Coverage Expansion
- Add edge case tests for capability matching
- Test federation scenarios with network partitions
- Add stress tests for anomaly detection
- Test recovery scenarios after Redis restart

### Dashboard UI Enhancements
- Add dark mode toggle
- Improve mobile responsiveness
- Add keyboard shortcuts for common actions
- Add anomaly visualization charts

### Agent Templates
- Create a basic "starter agent" template
- Document the minimal agent implementation
- Add specialized agent examples (logging, metrics, notifications)
- Create agent testing utilities

---

## Code of Conduct

See `CODE_OF_CONDUCT.md`. Summary: Be respectful, be constructive, focus on the work.

---

## Questions?

- GitHub Discussions (preferred)
- Email: support@clawcoat.com

---

*"The industry gives AI agents the keys to everything and forgot to build the locks. We built the locks."*

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
