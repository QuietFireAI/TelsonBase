# ClawCoat - Proof Index

**Every claim is backed by evidence.**

**Last Verified:** March 8, 2026 &nbsp;|&nbsp; **Version:** v11.0.1 &nbsp;|&nbsp; **Tests Passing:** 746 &nbsp;|&nbsp; **Proof Documents:** 788

---

TelsonBase publishes evidence for every security and compliance claim in the project.
If a claim is in the README, there is a verifiable source behind it.
If the evidence doesn't hold up, the claim gets fixed - not hidden.

---

## What Is Here

| Tier | Count | Format | Purpose |
|---|---|---|---|
| **Claim-level sheets** | 52 | `TB-PROOF-NNN` | One sheet per logical capability claim. Source files, verification command, verdict. |
| **Test suite class sheets** | 15 | `tb-proof-NNN` | One sheet per test suite - all classes listed, test counts, what each proves. |
| **Individual test sheets** | 721 | `TB-TEST-[DOMAIN]-NNN` | One sheet per test function. Single-command verification. Cross-referenced to class sheet. |
| **Total** | **788** | | |

---

## Domains Covered

| Domain | Sheets | Tests |
|---|---|---|
| Security battery | 9 class sheets | 96 |
| QMS protocol | 1 class sheet | 115 |
| Tool governance | 1 class sheet | 129 |
| OpenClaw | 1 class sheet | 55 |
| End-to-end | 1 class sheet | 29 |
| Contracts | 1 class sheet | 7 |
| Core + 9 other domains | 1 class sheet each | 315 |

---

## Full Index

**[→ proof_sheets/INDEX.md](proof_sheets/INDEX.md)**

The master index lists all 52 claim-level sheets organized by category:
Test Suite · Compliance · Cryptography · Authentication · Agent Governance · Security Testing · Data Sovereignty · Infrastructure · OpenClaw · Integration

Each sheet includes:
- The exact claim being proved
- The source file and test file
- A single copy-paste verification command
- The verdict (VERIFIED / PARTIAL / PENDING)

---

## Sample Verification

```bash
# Check a specific claim
cat proof_sheets/TB-PROOF-001_tests_passing.md

# Run the verification command from inside that sheet
docker compose exec mcp_server python -m pytest tests/ -v --tb=short

# Check a specific test function
cat proof_sheets/individual/sec/TB-TEST-SEC-001_test_api_key_hash_uses_sha256.md

# Run that one test
docker compose exec mcp_server python -m pytest \
  tests/test_security_battery.py::TestAuthSecurity::test_api_key_hash_uses_sha256 \
  -v --tb=short
```

Question any claim. Run the command. That is the point.

---

*TelsonBase v11.0.1 · Quietfire AI · Apache 2.0*
