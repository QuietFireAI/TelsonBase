# TB-PROOF-047 - Security Battery: Network Security

**Sheet ID:** TB-PROOF-047
**Claim Source:** tests/test_security_battery.py::TestNetworkSecurity
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- TestNetworkSecurity -- 9 behavioral tests
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "TLS 1.2+, HSTS, CORS, MQTT authentication, production mode strict validation" - Security Architecture

This sheet proves the **Network Security** category of the TelsonBase security battery. 9 tests covering CORS wildcard prevention, Redis password enforcement, health endpoint data leakage, production mode validation, session timeouts, MQTT authentication, JWT algorithm configuration, and egress domain whitelisting.

## Verdict

VERIFIED - All 9 tests pass. CORS defaults do not allow wildcard origins. The health endpoint does not leak internal details. Production mode blocks insecure default credentials. Session timeouts are within HIPAA-compliant limits (15 min standard, 10 min for privileged roles). MQTT requires authentication. JWT uses a configured non-default algorithm. The egress domain whitelist is restrictive.

## Test Functions

| # | Function | Proves |
|---|---|---|
| 1 | `test_cors_no_wildcard_default` | Default CORS configuration does not permit wildcard (`*`) origins |
| 2 | `test_redis_url_contains_password_when_configured` | Redis connection URL includes authentication when a password is set |
| 3 | `test_health_endpoint_does_not_leak_details` | The `/health` endpoint returns status only - no internal version, config, or stack info |
| 4 | `test_production_mode_blocks_insecure_defaults` | `TELSONBASE_ENV=production` rejects default/weak credentials at startup |
| 5 | `test_default_session_timeout_15_minutes_or_less` | Standard session idle timeout is ≤15 minutes (HIPAA requirement) |
| 6 | `test_privileged_role_session_timeout_10_minutes` | Admin and security role sessions timeout at ≤10 minutes |
| 7 | `test_mqtt_auth_required` | MQTT broker configuration enforces authentication - anonymous connections rejected |
| 8 | `test_jwt_algorithm_configured` | JWT signing algorithm is explicitly configured (not defaulted to "none") |
| 9 | `test_external_domain_whitelist_restrictive` | `ALLOWED_EXTERNAL_DOMAINS` is set and does not permit unrestricted external calls |

## Source Files Tested

- `tests/test_security_battery.py::TestNetworkSecurity`
- `core/config.py` - CORS origins, JWT algorithm, session timeouts
- `core/middleware.py` - CORS enforcement
- `core/session_management.py` - Timeout configuration
- `monitoring/mosquitto/mosquitto.conf` - MQTT authentication config
- `core/capabilities.py` - Egress domain whitelist

## Verification Command

```bash
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestNetworkSecurity -v --tb=short
```

## Expected Result

```
9 passed
```

---

*Sheet TB-PROOF-047 | ClawCoat v11.0.2 | March 19, 2026*
