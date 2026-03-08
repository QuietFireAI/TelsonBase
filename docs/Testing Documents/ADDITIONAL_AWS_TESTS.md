# TelsonBase - Additional AWS Tests & Pre-Handoff Strategy

**Date:** March 1, 2026
**Context:** Supplemental tests beyond the 10-phase AWS Testing Guide

---

## Strategy: Protect First, Share Second

**Sequence:**
1. AWS validation (you, solo)
2. IP filings March 1st (copyright $65, trademark $250-350)
3. NDA signed
4. Then outside eyes

No rush on external review. Your own test results, your own screenshots, your own AWS bill showing $3 spent - that's sufficient evidence without anyone else's stamp.

---

## Additional AWS Tests

### 1. Dependency Vulnerability Audit (2 minutes)

```bash
# Run inside the container - uses the exact same packages the running app uses
docker compose exec mcp_server sh -c "pip install pip-audit -q && pip-audit -r /app/requirements.txt"
```

This gives you a CVE report on every dependency. If it comes back clean, that's evidence. If it finds something, you fix it before anyone else sees the code.

### 2. Docker Image Vulnerability Scan

```bash
# Find the exact image name first, then scan
docker image ls | grep mcp_server
docker scout cves <image-name>:latest
```

Same idea - known vulnerabilities in your base images. Free, built into Docker.
Note: golang/stdlib CVEs in the output are from the Ollama vendor image, not TelsonBase.
Your Python CVE count should be 0. The multi-stage Dockerfile also eliminates 13 LOW binutils CVEs.

### 3. Secret Leak Scan - Verify No Secrets in Built Images

```bash
docker history mcp_server:latest --no-trunc | grep -i key
docker inspect mcp_server:latest | grep -i password
```

Should return nothing. If it does, you have a build problem.

### 4. Cold Start Timing

```bash
time docker compose up -d --build
# Then poll until all healthy
watch docker compose ps
```

Document the number. Investors and buyers ask "how fast does it deploy."

### 5. Kill Recovery - Resilience Test

```bash
docker kill telsonbase-mcp_server-1
# Wait 30 seconds (restart policy should bring it back)
docker compose ps
```

If it self-heals, that's resilience evidence. If it doesn't, you found something to fix.

---

## Complete Test Inventory

| # | Test | Source |
|---|------|--------|
| 1 | Does it breathe (service health) | AWS Testing Guide Phase 1 |
| 2 | Auth and security gates | AWS Testing Guide Phase 2 |
| 3 | Ollama live integration | AWS Testing Guide Phase 3 |
| 4 | Agent capability enforcement | AWS Testing Guide Phase 4 |
| 5 | Backup and restore fire drill | AWS Testing Guide Phase 5 |
| 6 | Observability validation | AWS Testing Guide Phase 6 |
| 7 | Endpoint stress test | AWS Testing Guide Phase 7 |
| 8 | Federation surface | AWS Testing Guide Phase 8 |
| 9 | Full test suite (701 passed, 1 skipped, + 26 MQTT stress) | AWS Testing Guide Phase 9 |
| 10 | Evidence collection | AWS Testing Guide Phase 10 |
| 11 | Dependency vulnerability audit | This document |
| 12 | Docker image CVE scan | This document |
| 13 | Secret leak scan | This document |
| 14 | Cold start timing | This document |
| 15 | Kill recovery / resilience | This document |

15 total validation steps. All executable solo. All producing documented evidence.

---

File the papers March 1st. Then you decide who's worth showing it to.

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
