# TB-PROOF-019: Human-in-the-Loop Approval Gates

**Sheet ID:** TB-PROOF-019
**Claim Source:** clawcoat.com - AI Safety Section
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- test_openclaw.py -- HITL gates tested: quarantine holds READ, probation gates EXTERNAL, resident gates destructive
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "Agents operate autonomously within defined boundaries. Destructive, irreversible, or trust-crossing actions require explicit human approval before execution."

## Verdict

VERIFIED - `core/approval.py` implements 7 predefined approval rules. Every agent in `agents/registry.yaml` declares which actions require approval. No bypass mechanism exists.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/approval.py` | Lines 129-191 | 7 DEFAULT_APPROVAL_RULES |
| `agents/registry.yaml` | Every agent | `requires_approval` lists per agent |

### The 7 Approval Rules

| Rule ID | Trigger | Priority | Timeout |
|---|---|---|---|
| `rule-external-new-domain` | First-time external domain contact | HIGH | 2 hours |
| `rule-filesystem-delete` | Any `filesystem.delete*` action | HIGH | 1 hour |
| `rule-anomaly-flagged` | Agent flagged by anomaly detection | URGENT | 30 min |
| `rule-new-agent-first-action` | First action by newly registered agent | NORMAL | 24 hours |
| `rule-high-value-transaction` | Value above $1000 threshold | URGENT | 1 hour |
| `rule-did-first-registration` | New DID agent registers | HIGH | 24 hours |
| `rule-did-scope-change` | Expanded scopes on credential update | HIGH | 2 hours |

### Per-Agent Approval Requirements (from registry.yaml)

| Agent | Actions Requiring Approval |
|---|---|
| backup_agent | `restore` |
| document_agent | `redact`, `delete` |
| ollama_agent | `pull_model`, `delete_model` |
| foreman_agent | `install_tool`, `update_tool`, `enable_api_access`, `quarantine_tool`, `delete_tool` |
| transaction_agent | `close_transaction`, `cancel_transaction`, `remove_party`, `override_deadline` |
| compliance_check_agent | `override_violation`, `waive_disclosure`, `suspend_license` |
| doc_prep_agent | `finalize_document`, `delete_document` |

## Verification Command

```bash
docker compose exec mcp_server python -m pytest \
  tests/test_openclaw.py -v --tb=short -k "gate or approval or quarantine or probation"
```

## Expected Result

8 agent entries with `requires_approval` declarations.

---

*Sheet TB-PROOF-019 | ClawCoat v11.0.2 | March 19, 2026*
