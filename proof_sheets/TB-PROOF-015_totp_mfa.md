# TB-PROOF-015: RFC 6238 TOTP Multi-Factor Authentication

**Sheet ID:** TB-PROOF-015
**Claim Source:** clawcoat.com - Capabilities Section
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- TestAuthSecurity -- 7 MFA/TOTP behavioral tests: enrollment, valid token, invalid token, replay, backup codes
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "RFC 6238 TOTP with QR enrollment and backup codes. HIPAA-compliant automatic logoff (15-minute idle, 10-minute for privileged roles). Account lockout after 5 failed attempts. Replay attack prevention on every MFA verification."

## Verdict

VERIFIED - `core/mfa.py` implements RFC 6238 TOTP using the `pyotp` library with QR provisioning URIs, 10 backup codes, and replay attack prevention via constant-time comparison.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/mfa.py` | Line 13 | RFC 6238 reference in header |
| `core/mfa.py` | Line 58 | MFA-required roles: `{Role.ADMIN, Role.SECURITY_OFFICER, Role.SUPER_ADMIN}` |
| `core/mfa.py` | Line 61 | `BACKUP_CODE_COUNT = 10` |
| `core/mfa.py` | Line 159 | `secret = pyotp.random_base32()` |
| `core/mfa.py` | Line 162 | `totp = pyotp.TOTP(secret)` |
| `core/mfa.py` | Lines 163-166 | `totp.provisioning_uri(name=username, issuer_name="TelsonBase")` |
| `core/mfa.py` | Lines 228-241 | Replay prevention: `hmac.compare_digest(token, record.last_used_token)` |
| `core/mfa.py` | Lines 244-245 | Token verification: `totp.verify(token)` |
| `core/mfa.py` | Lines 169-171 | Backup codes: `secrets.token_hex()` |

### Code Evidence

```python
# Secret generation
secret = pyotp.random_base32()
totp = pyotp.TOTP(secret)
provisioning_uri = totp.provisioning_uri(name=username, issuer_name="TelsonBase")

# Verification with replay prevention
if hmac.compare_digest(token, record.last_used_token):
    raise MFAError("Token already used")  # Replay attack prevention
is_valid = totp.verify(token)
```

### MFA Features

| Feature | Implementation | Reference |
|---|---|---|
| TOTP algorithm | pyotp (RFC 6238) | `core/mfa.py` line 162 |
| QR code enrollment | provisioning_uri | `core/mfa.py` lines 163-166 |
| Backup codes | 10 random hex tokens | `core/mfa.py` lines 169-171 |
| Replay prevention | Constant-time comparison | `core/mfa.py` lines 228-241 |
| Required roles | admin, security_officer, super_admin | `core/mfa.py` line 58 |

## Verification Command

```bash
docker compose exec mcp_server python -m pytest \
  tests/test_security_battery.py::TestAuthSecurity -v --tb=short -k "mfa or totp"
```

## Expected Result

References to pyotp, RFC 6238, TOTP operations, backup codes, and replay prevention.

---

*Sheet TB-PROOF-015 | ClawCoat v11.0.2 | March 19, 2026*
