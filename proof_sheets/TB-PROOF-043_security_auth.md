# TB-PROOF-043 - Security Battery: Authentication Security

**Sheet ID:** TB-PROOF-043
**Claim Source:** tests/test_security_battery.py::TestAuthSecurity
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- TestAuthSecurity -- 19 behavioral tests
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "96 dedicated security tests" - README, proof_sheets/INDEX.md

This sheet proves the **Authentication Security** category of the TelsonBase security battery. 19 tests covering API key hashing, JWT lifecycle, MFA enforcement, session management, and emergency access controls.

## Verdict

VERIFIED - All 19 tests pass. TelsonBase enforces SHA-256 key hashing, constant-time comparison, JWT expiration and revocation, TOTP multi-factor authentication with replay protection, single-use backup codes, role-based MFA requirements, and session timeout limits.

## Test Functions

| # | Function | Proves |
|---|---|---|
| 1 | `test_api_key_hash_uses_sha256` | API keys are hashed with SHA-256 before storage - raw key never stored |
| 2 | `test_api_key_hash_not_plaintext` | Hashed key is provably different from the original plaintext |
| 3 | `test_jwt_token_generation` | JWT generation produces a valid 3-part encoded string |
| 4 | `test_jwt_token_decode_roundtrip` | JWT round-trips correctly: subject and permissions claims survive encode/decode |
| 5 | `test_jwt_expiration_enforcement` | Expired JWTs are rejected by the decoder - no grace period |
| 6 | `test_jwt_revocation_check` | Revoked JWTs are rejected before natural expiration |
| 7 | `test_constant_time_comparison_used_in_auth` | API key comparison uses `hmac.compare_digest` - timing-attack resistant |
| 8 | `test_mfa_enrollment_generates_valid_totp_secret` | MFA enrollment generates a valid RFC 6238 TOTP secret |
| 9 | `test_mfa_verification_valid_token` | A valid TOTP token is accepted by the verifier |
| 10 | `test_mfa_verification_invalid_token` | An invalid TOTP token is rejected |
| 11 | `test_mfa_replay_attack_prevention` | The same TOTP token is rejected if presented twice (replay protection) |
| 12 | `test_mfa_backup_code_single_use` | MFA backup codes are consumed on first use - cannot be reused |
| 13 | `test_mfa_required_for_privileged_roles` | MFA enrollment is enforced for admin and security roles |
| 14 | `test_mfa_not_required_for_viewer` | MFA is not required for the viewer role |
| 15 | `test_api_key_rotation_invalidates_old_key` | Rotating an API key invalidates the previous key |
| 16 | `test_emergency_access_requires_approval` | Emergency (break-glass) access requires an approval gate before activation |
| 17 | `test_emergency_access_auto_expires` | Emergency access sessions auto-expire - no indefinite elevation |
| 18 | `test_session_auto_logoff_idle_timeout` | Idle sessions are terminated at the configured timeout |
| 19 | `test_session_max_duration_enforcement` | Sessions are forcibly closed at absolute max duration regardless of activity |

## Source Files Tested

- `tests/test_security_battery.py::TestAuthSecurity`
- `core/auth.py` - `_hash_key`, `create_access_token`, `decode_token`, `revoke_token`
- `core/mfa.py` - TOTP enrollment, verification, backup codes
- `core/session_management.py` - idle timeout, max duration
- `core/emergency_access.py` - break-glass flow

## Verification Command

```bash
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestAuthSecurity -v --tb=short
```

## Expected Result

```
19 passed
```

---

*Sheet TB-PROOF-043 | ClawCoat v11.0.2 | March 19, 2026*
