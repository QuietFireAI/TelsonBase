# TB-PROOF-035: OpenClaw Governance Pipeline

**Sheet ID:** TB-PROOF-035
**Claim Source:** clawcoat.com - OpenClaw Integration
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- test_openclaw.py -- 55 behavioral tests confirm full governance pipeline
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "Control Your Claw - TelsonBase acts as a governed MCP proxy for OpenClaw. Every action is evaluated against trust levels, approval gates, Manners compliance, anomaly detection, and egress control."

## Verdict

VERIFIED - `core/openclaw.py` implements a complete 8-step governance pipeline that evaluates every OpenClaw action before execution. Feature-flagged via `OPENCLAW_ENABLED`.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/openclaw.py` | Full file | OpenClawManager singleton with governance pipeline |
| `api/openclaw_routes.py` | Full file | 10 REST endpoints for claw management |
| `core/config.py` | Lines 262-271 | OPENCLAW_ENABLED feature flag + 5 settings |
| `core/audit.py` | Lines 159-167 | 8 OpenClaw audit event types |
| `core/approval.py` | Lines 193-211 | 3 OpenClaw-specific approval rules |
| `main.py` | Lines 216-221 | Startup initialization when enabled |

### The 8-Step Governance Pipeline
| Step | Check | On Fail |
|---|---|---|
| 1 | Instance registered? | Reject - unregistered claw |
| 2 | Kill switch (suspended)? | Reject - immediate |
| 3 | Nonce replay protection | Reject - replay detected |
| 4 | Tool on blocklist? | Reject - tool blocked |
| 5 | Classify action category | Map to READ/WRITE/DELETE/EXTERNAL/FINANCIAL/SYSTEM |
| 6 | Manners compliance score | Auto-demote to quarantine if < 0.50 |
| 7 | Trust level permission check | Allow / Gate / Block based on matrix |
| 8 | Anomaly detection | Flag behavioral deviations (even for Citizens) |

### Key Design Decisions
- Feature-flagged: `OPENCLAW_ENABLED=false` by default - zero impact on existing deployments
- Fail-closed: unregistered claws rejected, unknown tools classified as writes
- Kill switch checked before ANY other logic (Step 2)
- Manners auto-demotion happens before trust check (Step 6 before Step 7)
- Every decision logged to cryptographic audit chain
- Redis-backed state survives container restarts

## Verification Command

```bash
docker compose exec mcp_server python -m pytest \
  tests/test_openclaw.py -v --tb=short
```

## Expected Result

References to the governance pipeline, evaluate_action method, and OPENCLAW configuration.

---

*Sheet TB-PROOF-035 | ClawCoat v11.0.2 | March 19, 2026*
