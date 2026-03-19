# TB-PROOF-050 - Security Battery: Cryptographic Standards

**Sheet ID:** TB-PROOF-050
**Claim Source:** tests/test_security_battery.py::TestCryptographicStandards
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- TestCryptographicStandards -- 8 behavioral tests
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "AES-256-GCM · SHA-256 · PBKDF2 · Ed25519 · bcrypt cost 12 · TOTP RFC 6238" - SECURITY.md cryptographic primitives table

This sheet proves the **Cryptographic Standards** category of the TelsonBase security battery. 8 tests confirming that every cryptographic primitive meets its declared specification - not just that it functions, but that it uses the exact algorithm and key size claimed.

## Verdict

VERIFIED - All 8 tests pass. Signing keys are at minimum 256 bits. The audit chain uses SHA-256 - not MD5, not SHA-1. TOTP implements RFC 6238. Backup codes are generated with a CSPRNG. Key derivation runs at minimum 100,000 PBKDF2 iterations. AES key size is exactly 256 bits. GCM nonce size is 96 bits. Encryption key derivation uses SHA-256 as the PRF.

## Test Functions

| # | Function | Proves |
|---|---|---|
| 1 | `test_signing_key_length_minimum_256_bits` | Signing keys are at least 256 bits - no short keys |
| 2 | `test_hash_chain_uses_sha256_not_md5` | The audit chain hash function is SHA-256, not a weaker algorithm |
| 3 | `test_totp_uses_rfc6238_standard` | TOTP implementation is compatible with RFC 6238 - industry-standard authenticator apps work |
| 4 | `test_backup_codes_use_cryptographic_randomness` | MFA backup codes are generated with `secrets` (CSPRNG), not `random` |
| 5 | `test_key_derivation_uses_minimum_iterations` | PBKDF2 runs at minimum 100,000 iterations - brute-force resistant |
| 6 | `test_aes_key_size_is_256_bits` | AES key size is exactly 256 bits - not 128, not 192 |
| 7 | `test_gcm_nonce_size_is_96_bits` | GCM nonce size is 96 bits - NIST-recommended for AES-GCM |
| 8 | `test_encryption_key_derivation_uses_sha256` | Encryption key derivation uses SHA-256 as the PRF |

## Source Files Tested

- `tests/test_security_battery.py::TestCryptographicStandards`
- `core/signing.py` - Key generation, minimum length enforcement
- `core/audit.py` - Hash algorithm verification
- `core/mfa.py` - TOTP RFC 6238 implementation, backup code CSPRNG
- `core/secure_storage.py` - AES key size, GCM nonce size, PBKDF2 iteration count

## Verification Command

```bash
docker compose exec mcp_server python -m pytest tests/test_security_battery.py::TestCryptographicStandards -v --tb=short
```

## Expected Result

```
8 passed
```

---

*Sheet TB-PROOF-050 | ClawCoat v11.0.2 | March 19, 2026*
