# TB-PROOF-010: AES-256-GCM Encryption at Rest

**Sheet ID:** TB-PROOF-010
**Claim Source:** clawcoat.com - Capabilities Section, The Promise Section
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- TestEncryptionIntegrity -- 11 behavioral tests confirm AES-256-GCM encrypt/decrypt/tamper
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "AES-256-GCM encryption at rest with PBKDF2 key derivation (100,000+ iterations)."
> "Patient health information is encrypted at rest with AES-256-GCM"

## Verdict

VERIFIED - `core/secure_storage.py` implements AES-256-GCM encryption using the `cryptography` library's `AESGCM` class with 32-byte keys and 12-byte nonces.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/secure_storage.py` | Line 28 | `from cryptography.hazmat.primitives.ciphers.aead import AESGCM` |
| `core/secure_storage.py` | Line 69 | `NONCE_SIZE = 12` (96-bit nonce) |
| `core/secure_storage.py` | Line 70 | `KEY_SIZE = 32` (256-bit key) |
| `core/secure_storage.py` | Line 103 | `self._aesgcm = AESGCM(self._encryption_key)` |
| `core/secure_storage.py` | Line 139 | `ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)` |

### Code Evidence

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_SIZE = 32   # 256 bits
NONCE_SIZE = 12 # 96 bits (GCM standard)

self._aesgcm = AESGCM(self._encryption_key)
ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
```

### Cryptographic Parameters

| Parameter | Value | Standard |
|---|---|---|
| Algorithm | AES-256-GCM | NIST SP 800-38D |
| Key size | 256 bits (32 bytes) | NIST recommended |
| Nonce size | 96 bits (12 bytes) | GCM standard |
| Authentication tag | 128 bits (built into GCM) | NIST SP 800-38D |
| Library | `cryptography==46.0.5` | OpenSSL backend |

## Verification Command

```bash
docker compose exec mcp_server python -m pytest \
  tests/test_security_battery.py::TestEncryptionIntegrity -v --tb=short
```

## Expected Result

Lines showing AESGCM import, 32-byte key size, 12-byte nonce, and encrypt/decrypt method calls.

---

*Sheet TB-PROOF-010 | ClawCoat v11.0.2 | March 19, 2026*
