# Toolroom Trust Level Matrix
**Version:** v11.0.1 · **Maintainer:** Quietfire AI

This document defines how agent trust levels govern toolroom access. It is the authoritative reference for operators configuring tool designations and for agents understanding what is available at each tier.

For the general trust level system, see `core/trust_levels.py` and `proof_sheets/TB-PROOF-036_trust_level_matrix.md`.

---

## How Tool Access is Controlled

Every tool in the registry has three access control fields set at install time:

| Field | Type | Default | Purpose |
|---|---|---|---|
| `min_trust_level` | string | `"resident"` | Minimum agent tier required to check out this tool |
| `requires_api_access` | bool | `False` | If true, HITL gate triggers regardless of trust level |
| `allowed_agents` | list | `[]` (all) | Explicit allowlist; empty means any agent of sufficient trust level |

**Source:** `toolroom/registry.py` - `ToolMetadata` dataclass.

All three are evaluated in sequence by the Foreman during every checkout request (`toolroom/foreman.py` - `handle_checkout_request()`):

```
1. Does the tool exist?
2. Is the agent on the allowed_agents list? (if list is non-empty)
3. Is the agent's trust level >= tool.min_trust_level?
4. Does the tool require API access? → HITL gate regardless of tier
5. Proceed with checkout.
```

---

## The Promotion Ladder

Agents are promoted sequentially from QUARANTINE through to AGENT - the top tier. There are no skips on promotion. Every agent earns its way through the full ladder.

```
QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT
  (new/gated)  (limited)  (standard) (full)    (apex)
```

This matters for toolroom access: tool designations map directly to this ladder. A tool designated `min_trust_level = "agent"` is only accessible to agents that have earned the apex tier through the full promotion path. There is no shortcut to that designation.

---

## Checkout Eligibility by Tier

| Trust Tier | Index | Can check out tools with min_trust_level... | Notes |
|---|---|---|---|
| **QUARANTINE** | 0 | `quarantine` only | No standard tools. Read-only internal tools only if designated. |
| **PROBATION** | 1 | `quarantine`, `probation` | Parsing, utility tools reasonable here. No external. |
| **RESIDENT** | 2 | `quarantine`, `probation`, `resident` | Full access to standard tools. **Default minimum.** |
| **CITIZEN** | 3 | All tiers up to `citizen` | Full tool access. Can use API-access tools after HITL approval. |
| **AGENT** | 4 | All tiers including `agent` | Apex tier. Full tool access. Anomalies advisory, not gated. |

**The default `min_trust_level` is `"resident"`**, which means QUARANTINE and PROBATION agents cannot check out any standard tool without the operator explicitly lowering the designation.

Unknown trust levels (unregistered agents) are treated as QUARANTINE - the most restrictive fallback.

---

## API Access Gate

`requires_api_access = True` is a separate gate from trust level. It triggers a HITL approval request regardless of the agent's tier - even AGENT-level agents require human authorization before checking out an API-access tool.

This is intentional: external API access carries credential and egress risk that no tier designation removes.

```
Tool requires_api_access = True
  → Foreman creates ApprovalRequest (APPR-xxxxx)
  → Human operator reviews and approves/denies
  → Only after approval: checkout proceeds
```

**Source:** `toolroom/foreman.py` - `handle_checkout_request()` Step 4.

---

## Recommended Designations by Tool Category

These are operator guidelines, not enforced defaults. The Foreman does not assign `min_trust_level` automatically by category - the installing operator sets it at install time.

| Category | Recommended `min_trust_level` | `requires_api_access` | Rationale |
|---|---|---|---|
| `parsing` | `probation` | `False` | Read-only data transformation. Low risk. |
| `utility` | `probation` | `False` | General helpers. Low risk. |
| `crypto` | `resident` | `False` | Sensitive operations. Require established trust. |
| `filesystem` (read) | `probation` | `False` | Read-only filesystem. Probation-appropriate. |
| `filesystem` (write/delete) | `resident` | `False` | Destructive potential. Require RESIDENT. |
| `database` (read) | `resident` | `False` | Data access requires RESIDENT minimum. |
| `database` (write) | `citizen` | `False` | Data mutation requires elevated trust. |
| `analytics` | `resident` | `False` | Data processing. RESIDENT standard. |
| `network` (internal) | `resident` | `False` | Internal network access. RESIDENT minimum. |
| `network` (external) | `resident` | `True` | External calls always trigger HITL gate. |
| `integration` | `citizen` | `True` | External services. CITIZEN + HITL. |
| Highest-sensitivity tools | `agent` | `True` | Reserved for apex-tier agents only. Full promotion ladder required. |

`min_trust_level = "agent"` is the most restrictive designation. Only agents that have completed the full QUARANTINE → PROBATION → RESIDENT → CITIZEN → AGENT promotion path - meeting every behavioral threshold and receiving human approval at each step - can check out these tools. Use this designation for tools with destructive, irreversible, or system-level consequences where anything less than proven trust is unacceptable.

---

## Setting Tool Designations

Tool designations are set at install time. They can be updated by re-registering the tool.

### At Install (GitHub-sourced tool)

Pass `min_trust_level` and `requires_api_access` to the install task:

```bash
docker compose exec worker celery -A celery_app.worker call \
  foreman_agent.execute_tool_install \
  --args='["dbcli/pgcli", "pgcli", "PostgreSQL CLI", "database", "latest", false, "operator", "APPR-xxxxx"]'
```

The `false` parameter in position 6 is `requires_api_access`. `min_trust_level` defaults to `"resident"` unless passed explicitly.

### At Install (Function tool)

Set in the decorator:

```python
@register_function_tool(
    name="Hash Calculator",
    category="crypto",
    description="Compute SHA-256 hash of input text",
    min_trust_level="resident",
    requires_api_access=False,
)
def hash_text(text: str, algorithm: str = "sha256") -> dict:
    ...
```

### Post-Install Update

Re-register the tool with updated metadata. The registry carries forward version history on update. Only human operators can change tool designations - the Foreman cannot modify its own registry entries except during installs and updates.

---

## Locking a Tool to Specific Agents

Set `allowed_agents` to restrict a tool to named agents only:

```python
metadata = ToolMetadata(
    tool_id="restricted_tool",
    name="Restricted Tool",
    ...
    allowed_agents=["analytics_agent", "reporting_agent"],  # Only these two
    min_trust_level="resident",
)
```

An empty list (default) means any agent meeting the `min_trust_level` can check it out. A non-empty list is an allowlist - trust level still applies on top of it.

---

## Enforcement Source

| Check | Where Enforced |
|---|---|
| `min_trust_level` comparison | `toolroom/foreman.py` - `handle_checkout_request()` |
| `allowed_agents` check | `toolroom/foreman.py` - Step 2 |
| `requires_api_access` gate | `toolroom/foreman.py` - Step 4 |
| Trust hierarchy definition | `core/trust_levels.py` - `AgentTrustLevel` enum |
| Constraints per tier | `core/trust_levels.py` - `TRUST_LEVEL_CONSTRAINTS` |

---

## Trust Tier Constraints Summary

For the full capability constraint matrix per tier, see `core/trust_levels.py` (`TRUST_LEVEL_CONSTRAINTS`). The toolroom-specific summary:

| Tier | Rate Limit | External Access | Spawn Agents | Re-verification |
|---|---|---|---|---|
| QUARANTINE | 5/min | No | No | Not required |
| PROBATION | 30/min | No | No | Not required |
| RESIDENT | 60/min | Yes | No | Every 14 days |
| CITIZEN | 120/min | Yes | Yes | Every 7 days |
| AGENT | 300/min | Yes | Yes | Every 3 days (0 anomaly tolerance) |

AGENT tier re-verification is the strictest: 99.9% success rate required, 0 anomalies per period, minimum 50 actions per period to demonstrate activity.

---

## Related Documents

| Document | What It Covers |
|---|---|
| `toolroom/TOOLROOM.md` | Full toolroom operational guide |
| `proof_sheets/TB-PROOF-036_trust_level_matrix.md` | OpenClaw permission matrix verification |
| `proof_sheets/tb-proof-054_toolroom_suite.md` | Toolroom test suite class-level evidence |
| `core/trust_levels.py` | Trust level enum, constraints, promotion requirements |
| `toolroom/foreman.py` | Checkout enforcement implementation |
| `toolroom/registry.py` | ToolMetadata definition and storage |

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
