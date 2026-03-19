# TB-PROOF-013: Cryptographic Message Signing Between Agents

**Sheet ID:** TB-PROOF-013
**Claim Source:** clawcoat.com - AI Safety Section
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- test_signing.py -- 13 behavioral tests confirm sign, verify, tamper detection, replay prevention
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "Zero-trust architecture with cryptographic message signing between all agents."

## Verdict

VERIFIED - `core/signing.py` implements HMAC-based message signing for inter-agent communication, with key management persisted in Redis.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `core/signing.py` | Full file | Message signing with HMAC keys |
| `core/persistence.py` | signing_store | Redis-persisted signing keys |
| `federation/trust.py` | Full file | RSA-4096 + PSS padding for federation signing |
| `core/identiclaw.py` | Full file | Ed25519 signature verification for DID agents |

### Three Signing Layers

| Layer | Algorithm | Purpose | File |
|---|---|---|---|
| Internal agents | HMAC-SHA256 | Agent-to-agent message authentication | `core/signing.py` |
| Federation | RSA-4096 + PSS | Cross-instance trust verification | `federation/trust.py` |
| DID Identity | Ed25519 | External agent identity verification | `core/identiclaw.py` |

### How It Works

1. Each agent has a signing key registered in Redis
2. Messages include a signature computed with the sender's key
3. Recipients verify the signature before processing
4. Messages without valid signatures are logged as security anomalies
5. Key revocation immediately blocks an agent's ability to sign

## Verification Command

```bash
docker compose exec mcp_server python -m pytest \
  tests/test_signing.py -v --tb=short
```

## Expected Result

HMAC-based signing implementation with key management.

---

*Sheet TB-PROOF-013 | ClawCoat v11.0.2 | March 19, 2026*
