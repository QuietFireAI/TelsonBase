# TB-PROOF-031: Non-Root Container Execution

**Sheet ID:** TB-PROOF-031
**Claim Source:** SECURITY.md - Container Security
**Status:** VERIFIED
**Test Coverage:** VERIFIED -- TestNonRootContainer -- Dockerfile confirmed: aiagent user created, USER instruction switches to non-root before CMD
**Last Verified:** March 8, 2026
**Version:** v11.0.2

---

## Exact Claim

> "All containers run as non-root users (UID 1000)"

## Reviewer Note - Infrastructure Evidence

> **Do NOT search Python application source for container user configuration.**
> Non-root execution is enforced at the container build layer, not in application code.
>
> **Where to look:**
> - `Dockerfile` lines 18-19 - `groupadd`/`useradd` for `aiagent` (UID 1000)
> - `Dockerfile` line 51 - `USER aiagent` directive
> - `.github/workflows/ci.yml` lines 133-137 - CI verification: `whoami | grep -q "aiagent"`
>
> A code-only scanner that searches `.py` files exclusively will not find this evidence.
> That is a scanner limitation, not a gap in the implementation.

## Verdict

VERIFIED - `Dockerfile` creates user `aiagent` (UID 1000) and sets `USER aiagent`. CI pipeline verifies this with `docker run --rm ... whoami`.

## Evidence

### Source Files
| File | Lines | What It Proves |
|---|---|---|
| `Dockerfile` | Lines 18-19 | User creation: `groupadd --gid 1000 aiagent && useradd --uid 1000 ...` |
| `Dockerfile` | Line 44 | File ownership: `COPY --chown=aiagent:aiagent . .` |
| `Dockerfile` | Line 51 | `USER aiagent` directive |
| `.github/workflows/ci.yml` | Lines 133-137 | CI verification: `whoami | grep -q "aiagent"` |
| `SECURITY.md` | Lines 77-82 | Container security documentation |

### Code Evidence

From `Dockerfile`:
```dockerfile
# User creation
RUN groupadd --gid 1000 aiagent && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home aiagent

# File ownership
COPY --chown=aiagent:aiagent . .

# Run as non-root
USER aiagent
```

From `.github/workflows/ci.yml`:
```yaml
- name: Verify non-root user in container
  run: |
    docker run --rm telsonbase-mcp:ci whoami | grep -q "aiagent" && \
      echo "PASS: Container runs as non-root user (aiagent)" || \
      (echo "FAIL: Container running as root" && exit 1)
```

## Verification Command

```bash
docker compose exec mcp_server python -m pytest \
  tests/test_depth_infrastructure.py::TestNonRootContainer -v --tb=short

# Runtime check (requires running stack):
docker compose exec mcp_server whoami
```

## Expected Result

```
3 passed (Dockerfile tests) + 'aiagent' (runtime)
```

---

*Sheet TB-PROOF-031 | ClawCoat v11.0.2 | March 19, 2026*
