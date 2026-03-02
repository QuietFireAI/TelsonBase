# AI_NAS_OS/gateway/Dockerfile
# REM: =======================================================================================
# REM: EGRESS GATEWAY CONTAINER
# REM: =======================================================================================
# REM: Minimal container for the external API proxy. This container is the ONLY
# REM: one with external network access in the production configuration.
# REM:
# REM: v8.0.2 — Added pip/wheel upgrade and apt-get upgrade for CVE hardening.
# REM: CVE MITIGATIONS:
# REM:   CVE-2026-24049  (HIGH)   wheel upgraded to 0.46.2
# REM:   CVE-2025-14831  (MED)    apt-get upgrade applies available Debian patches (gnutls28)
# REM:   CVE-2025-9820   (MED)    apt-get upgrade applies available Debian patches (gnutls28)
# REM:   CVE-2025-45582  (MED)    apt-get upgrade applies available Debian patches (tar)
# REM: =======================================================================================

FROM python:3.11-slim-bookworm

# REM: Apply all available Debian security patches before anything else.
RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# REM: Create non-root user
RUN groupadd --gid 1000 gateway && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home gateway

WORKDIR /app

# REM: Install dependencies — upgrade pip and wheel first (CVE-2026-24049)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.0.1 wheel==0.46.2 && \
    pip install --no-cache-dir -r requirements.txt

# REM: Copy application code
COPY --chown=gateway:gateway egress_proxy.py .

USER gateway

EXPOSE 8080

CMD ["uvicorn", "egress_proxy:app", "--host", "0.0.0.0", "--port", "8080"]
