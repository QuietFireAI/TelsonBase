# TB-PROOF-020: Behavioral Anomaly Detection

**Sheet ID:** TB-PROOF-020
**Claim Source:** clawcoat.com - Capabilities Section
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- pytest -k anomal -- behavioral anomaly detection tests
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "Continuous monitoring of AI agent behavior against established baselines. Rate spikes, enumeration patterns, unusual timing, and capability probes are flagged automatically. Automated threat response with quarantine recommendations."

## Verdict

VERIFIED - `core/anomaly.py` implements 7 anomaly detection types with statistical baselines and exponential moving average.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/anomaly.py` | Lines 51-59 | 7 anomaly detection types |
| `core/anomaly.py` | Lines 100-131 | `AgentBaseline` model with statistical parameters |
| `core/anomaly.py` | Lines 308-502 | Detection logic for all 7 types |
| `core/anomaly.py` | Line 128 | Maturity threshold: 100 observations |
| `core/anomaly.py` | Line 519 | EMA alpha=0.1 for adaptive baselines |

### The 7 Anomaly Detection Types

| Type | Trigger | Threshold |
|---|---|---|
| `RATE_SPIKE` | Activity rate > 3.0 std deviations above mean | Statistical |
| `NEW_RESOURCE` | Agent accesses resource not in its baseline | First-time |
| `NEW_ACTION` | Agent performs action not in its baseline | First-time |
| `UNUSUAL_TIMING` | Activity at hour with <1% historical activity | Statistical |
| `SEQUENTIAL_ACCESS` | 10+ sequential accesses in 60 seconds | Count-based |
| `ERROR_SPIKE` | Error rate exceeds 2x baseline | Ratio-based |
| `CAPABILITY_PROBE` | 5+ permission denials in 5 minutes | Count-based |

### Baseline Model

```python
class AgentBaseline:
    avg_actions_per_minute: float
    std_actions_per_minute: float
    max_observed_rate: float
    known_resources: Set[str]
    known_actions: Set[str]
    hourly_distribution: Dict[int, int]
    avg_error_rate: float
    # Maturity threshold: 100 observations
    # EMA alpha: 0.1 for adaptive updates
```

## Verification Command

```bash
docker compose exec mcp_server python -m pytest tests/ -v -k "anomal" --tb=short -q
```

## Expected Result

All anomaly detection tests pass, validating all 7 detection types.

---

*Sheet TB-PROOF-020 | ClawCoat v11.0.2 | March 19, 2026*
