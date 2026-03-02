# TelsonBase/Dockerfile
# REM: =======================================================================================
# REM: PRODUCTION CONTAINER IMAGE FOR TELSONBASE — MULTI-STAGE BUILD
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 2026
# REM:
# REM: Mission Statement: A secure, minimal container image for running the MCP server,
# REM: Celery workers, and Celery beat scheduler. Built on Python slim for reduced
# REM: attack surface.
# REM:
# REM: v8.0.2 — Multi-stage build + curl removal to eliminate build tools and
# REM:          reduce the installed package footprint to the absolute minimum.
# REM:
# REM: CVE MITIGATIONS:
# REM:   CVE-2026-24049  (HIGH)   wheel upgraded to 0.46.2 (builder + runtime)
# REM:   CVE-2025-8869   (MED)    pip upgraded to 26.0.1 (builder + runtime)
# REM:   CVE-2026-1703   (MED)    pip upgraded to 26.0.1 (builder + runtime)
# REM:   CVE-2024-23342  (HIGH)   ecdsa uninstalled — python-jose uses cryptography backend (HS256)
# REM:
# REM:   binutils (50+ LOW CVEs) — multi-stage build; gcc/binutils exist only in
# REM:   the builder stage and are never copied to the runtime image:
# REM:   CVE-2025-1178, CVE-2025-11494, CVE-2025-11413, CVE-2025-66866, CVE-2025-66862,
# REM:   CVE-2025-11840, CVE-2025-1182, CVE-2024-53589, CVE-2024-57360, CVE-2025-1148,
# REM:   CVE-2025-1179, CVE-2025-5245, CVE-2018-20673, CVE-2025-1151, CVE-2025-11081,
# REM:   CVE-2025-1147, CVE-2025-5244, CVE-2025-1176, CVE-2025-11495, CVE-2025-7545,
# REM:   CVE-2025-11414, CVE-2025-8225, CVE-2025-1180, CVE-2025-7546, CVE-2025-11839,
# REM:   CVE-2025-1150, CVE-2025-8224, CVE-2025-1153, CVE-2018-20712, CVE-2018-9996,
# REM:   CVE-2025-66863, CVE-2025-66861, CVE-2017-13716, CVE-2025-11083, CVE-2025-11412,
# REM:   CVE-2025-3198, CVE-2025-11082, CVE-2021-32256, CVE-2025-66864, CVE-2025-0840,
# REM:   CVE-2025-1149, CVE-2023-1972, CVE-2025-1152, CVE-2025-66865, CVE-2025-1181
# REM:
# REM:   curl (6 LOW CVEs) — curl package removed; healthcheck uses Python stdlib
# REM:   (urllib.request). No curl binary = no libcurl4 = no libldap (openldap):
# REM:   CVE-2025-10966, CVE-2025-15079, CVE-2025-0725, CVE-2024-2379,
# REM:   CVE-2025-15224, CVE-2025-14017
# REM:
# REM:   openldap (5 LOW CVEs) — eliminated as transitive dep of curl (above):
# REM:   CVE-2026-22185, CVE-2015-3276, CVE-2017-17740, CVE-2020-15719, CVE-2017-14159
# REM:
# REM:   CVE-2025-14831  (MED)    apt-get upgrade applies available Debian patches (gnutls28)
# REM:   CVE-2025-9820   (MED)    apt-get upgrade applies available Debian patches (gnutls28)
# REM:   CVE-2025-45582  (MED)    apt-get upgrade applies available Debian patches (tar)
# REM:
# REM: ACCEPTED RESIDUAL RISK (no fix available):
# REM:   CVE-2011-3389  (gnutls28 BEAST): Traefik enforces TLS 1.2+ / no CBC ciphers
# REM:   CVE-2005-2541  (tar 2005): no exploit path; tar not exposed to untrusted input
# REM:   glibc CVEs (CVE-2019-9192 etc.): Debian formal "won't fix"; universal baseline
# REM: =======================================================================================

# ---- Stage 1: builder -------------------------------------------------------
# REM: Build tools (gcc, binutils) exist ONLY in this stage. Nothing here ships
# REM: to production. This stage compiles any C extensions required by pip packages.
FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# REM: Upgrade pip and wheel (CVE-2026-24049), then install all dependencies.
RUN pip install --no-cache-dir --upgrade pip==26.0.1 wheel==0.46.2 && \
    pip install --no-cache-dir -r requirements.txt

# REM: Remove ecdsa — transitive dependency of python-jose but is NOT used.
# REM: TelsonBase uses JWT_ALGORITHM=HS256 (HMAC). python-jose[cryptography] handles
# REM: this via the cryptography library backend. ecdsa is the unused fallback backend.
# REM: Removing it eliminates CVE-2024-23342 (timing side-channel, CVSS 7.4).
RUN pip uninstall -y ecdsa || true


# ---- Stage 2: runtime -------------------------------------------------------
# REM: Clean base image. No gcc. No binutils. No curl. No openldap. Minimal footprint.
FROM python:3.11-slim-bookworm

# REM: Apply all available Debian security patches (gnutls28, tar, etc.)
# REM: No additional packages installed — curl is intentionally excluded.
# REM: curl would pull in libcurl4 → libldap (openldap), adding ~20 CVEs for a
# REM: single healthcheck command. The healthcheck uses Python stdlib instead.
RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# REM: Upgrade pip and wheel in the runtime image.
# REM: COPY --from=builder overwrites site-packages but the base image retains
# REM: its own pip/wheel dist-info in the layer. This explicit upgrade ensures
# REM: pip-audit sees 26.0.1/0.46.2 in the runtime image, resolving:
# REM:   CVE-2025-8869, CVE-2026-1703 (pip 24.0), CVE-2026-24049 (wheel 0.45.1)
RUN pip install --no-cache-dir --upgrade "pip==26.0.1" "wheel==0.46.2"

# REM: Security: Don't run as root inside container.
RUN groupadd --gid 1000 aiagent && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home aiagent

# REM: Copy Python packages and CLI tools from builder.
# REM: site-packages carries all pip-installed libraries (including C extensions).
# REM: /usr/local/bin carries gunicorn, celery, uvicorn, alembic, etc.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# REM: Set working directory
WORKDIR /app

# REM: Copy application code
COPY --chown=aiagent:aiagent . .

# REM: Create necessary directories with correct permissions
RUN mkdir -p /app/backups /app/logs && \
    chown -R aiagent:aiagent /app

# REM: Switch to non-root user
USER aiagent

# REM: Expose the API port
EXPOSE 8000

# REM: Healthcheck uses Python stdlib (urllib.request) — no curl dependency needed.
# REM: urllib.request.urlopen raises an exception on HTTP error or connection failure,
# REM: causing Python to exit non-zero, which Docker treats as unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)"

# REM: Default command runs the FastAPI server via Gunicorn.
# REM: Workers default to 2. Override with WEB_CONCURRENCY env var (e.g. WEB_CONCURRENCY=4).
# REM: The audit chain is Redis-backed with WATCH/MULTI/EXEC optimistic locking — safe for
# REM: any number of workers. The previous -w 1 constraint predated that implementation.
# REM: Shell form is required here so ${WEB_CONCURRENCY:-2} expands at container start.
# REM: 'exec' replaces the sh process with gunicorn — Docker SIGTERM goes directly to
# REM: gunicorn (PID 1), not sh. Without exec, sh receives SIGTERM but doesn't forward
# REM: it, causing in-flight requests to be dropped on container stop.
CMD ["sh", "-c", "exec gunicorn main:app -w ${WEB_CONCURRENCY:-2} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --access-logfile - --error-logfile -"]
