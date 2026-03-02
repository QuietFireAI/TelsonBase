#!/bin/bash
# TelsonBase/scripts/generate_secrets.sh
# REM: =======================================================================================
# REM: SECRET GENERATION BOOTSTRAP — ONE COMMAND TO SECURE YOUR INSTANCE
# REM: =======================================================================================
# REM: Architect: ::Quietfire AI Project::
# REM: Date: February 23, 2026
#
# REM: v6.2.0CC: Docker secrets bootstrap script
# REM:   - Added --rotate flag for forced regeneration with confirmation
# REM:   - Added --check flag for verification-only mode
# REM:   - Added PostgreSQL, Redis, and MQTT password generation
#
# REM: Mission Statement: This script generates cryptographically secure values for
# REM: every secret TelsonBase requires and stores them as individual files in the
# REM: ./secrets/ directory. Docker Compose mounts these files at /run/secrets/ inside
# REM: containers — never baked into images, never written to container disk.
#
# REM: Usage:
# REM:   chmod +x scripts/generate_secrets.sh
# REM:   ./scripts/generate_secrets.sh            # Generate missing secrets
# REM:   ./scripts/generate_secrets.sh --rotate   # Force regeneration (with confirmation)
# REM:   ./scripts/generate_secrets.sh --check    # Verify existing secrets only
#
# REM: After running:
# REM:   - ./secrets/ directory contains one file per secret
# REM:   - docker-compose.yml reads these via the 'secrets' section
# REM:   - .env is still used for NON-SENSITIVE config (domains, log level, etc.)
#
# REM: NEVER commit the ./secrets/ directory to version control.
# REM: ALWAYS back up ./secrets/ to your Drobo NAS or AWS Snowball device.
# REM: =======================================================================================

set -euo pipefail

# REM: Color output for readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SECRETS_DIR="./secrets"

# REM: Parse command-line flags
MODE="generate"  # Default mode
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rotate)
            MODE="rotate"
            shift
            ;;
        --check)
            MODE="check"
            shift
            ;;
        *)
            echo -e "${RED}Unknown flag: $1${NC}"
            echo "Usage: $0 [--rotate | --check]"
            exit 1
            ;;
    esac
done

# REM: Full list of all secrets for verification
ALL_SECRETS=(
    telsonbase_mcp_api_key
    telsonbase_jwt_secret
    telsonbase_encryption_key
    telsonbase_encryption_salt
    telsonbase_webui_secret
    telsonbase_grafana_password
    telsonbase_postgres_password
    telsonbase_redis_password
    telsonbase_mqtt_password
)

echo -e "${CYAN}"
echo "=============================================================="
echo "           TelsonBase — Secret Generation Bootstrap           "
echo "                    by Quietfire AI                               "
echo "=============================================================="
echo -e "${NC}"

# REM: =====================================================
# REM: CHECK-ONLY MODE — verify existing secrets, no generation
# REM: =====================================================
if [ "$MODE" = "check" ]; then
    echo -e "${CYAN}Verification-only mode (--check). No secrets will be generated.${NC}"
    echo ""

    if [ ! -d "$SECRETS_DIR" ]; then
        echo -e "${RED}FAILED: ${SECRETS_DIR}/ directory does not exist.${NC}"
        echo "Run this script without --check to generate secrets."
        exit 1
    fi

    ERROR_COUNT=0
    for secret_file in "${ALL_SECRETS[@]}"; do
        filepath="${SECRETS_DIR}/${secret_file}"
        if [ ! -f "$filepath" ]; then
            echo -e "  ${RED}x${NC} ${secret_file} — MISSING"
            ERROR_COUNT=$((ERROR_COUNT + 1))
        else
            size=$(wc -c < "$filepath" | tr -d ' ')
            perms=$(stat -c '%a' "$filepath" 2>/dev/null || stat -f '%Lp' "$filepath" 2>/dev/null)
            if [ "$size" -lt 16 ]; then
                echo -e "  ${RED}x${NC} ${secret_file} — TOO SHORT (${size} bytes)"
                ERROR_COUNT=$((ERROR_COUNT + 1))
            elif [ "$perms" != "644" ]; then
                echo -e "  ${YELLOW}!${NC} ${secret_file} — OK but permissions are ${perms} (should be 644)"
            else
                echo -e "  ${GREEN}+${NC} ${secret_file} — OK (${size} bytes, mode ${perms})"
            fi
        fi
    done

    echo ""
    if [ $ERROR_COUNT -gt 0 ]; then
        echo -e "${RED}FAILED: ${ERROR_COUNT} secret(s) have issues.${NC}"
        exit 1
    else
        echo -e "${GREEN}All secrets verified successfully.${NC}"
        exit 0
    fi
fi

# REM: =====================================================
# REM: ROTATE MODE — forced regeneration with confirmation
# REM: =====================================================
if [ "$MODE" = "rotate" ]; then
    echo -e "${RED}WARNING: --rotate will regenerate ALL secrets.${NC}"
    echo -e "${RED}This will invalidate all existing sessions, tokens, and credentials.${NC}"
    echo -e "${RED}You MUST restart the entire stack after rotation.${NC}"
    echo ""
    read -p "Type 'ROTATE' to confirm forced regeneration: " confirmation
    if [ "$confirmation" != "ROTATE" ]; then
        echo "Aborted. No secrets were changed."
        exit 0
    fi
    echo -e "${YELLOW}Rotating all secrets...${NC}"
    OVERWRITE=true
elif [ -d "$SECRETS_DIR" ]; then
    # REM: Normal generate mode — secrets directory exists
    echo -e "${YELLOW}WARNING: ${SECRETS_DIR}/ already exists.${NC}"
    echo ""
    echo "Options:"
    echo "  1) Overwrite all secrets (DANGER: existing sessions/tokens will be invalidated)"
    echo "  2) Generate only missing secrets (safe)"
    echo "  3) Abort"
    echo ""
    read -p "Choose [1/2/3]: " choice
    case $choice in
        1)
            echo -e "${RED}Overwriting all secrets...${NC}"
            OVERWRITE=true
            ;;
        2)
            echo -e "${GREEN}Generating only missing secrets...${NC}"
            OVERWRITE=false
            ;;
        *)
            echo "Aborted."
            exit 0
            ;;
    esac
else
    OVERWRITE=true
fi

# REM: Create secrets directory with restricted permissions
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# REM: Function to generate a secret file
generate_secret() {
    local filename="$1"
    local description="$2"
    local length="${3:-32}"  # Default 32 bytes = 64 hex chars
    local filepath="${SECRETS_DIR}/${filename}"

    if [ "$OVERWRITE" = false ] && [ -f "$filepath" ]; then
        echo -e "  ${GREEN}+${NC} ${filename} — already exists (skipped)"
        return
    fi

    # REM: Generate cryptographically secure random value
    openssl rand -hex "$length" > "$filepath"
    chmod 644 "$filepath"

    echo -e "  ${GREEN}+${NC} ${filename} — ${description}"
}

# REM: Function to generate a password (alphanumeric, good for Grafana etc.)
generate_password() {
    local filename="$1"
    local description="$2"
    local length="${3:-24}"
    local filepath="${SECRETS_DIR}/${filename}"

    if [ "$OVERWRITE" = false ] && [ -f "$filepath" ]; then
        echo -e "  ${GREEN}+${NC} ${filename} — already exists (skipped)"
        return
    fi

    # REM: Generate password with mixed characters
    openssl rand -base64 "$length" | tr -d '\n/+=' | head -c "$length" > "$filepath"
    chmod 644 "$filepath"

    echo -e "  ${GREEN}+${NC} ${filename} — ${description}"
}

echo ""
echo -e "${CYAN}Generating secrets...${NC}"
echo ""

# REM: =====================================================
# REM: CORE SECURITY SECRETS
# REM: =====================================================
echo -e "${YELLOW}[Core Security]${NC}"
generate_secret "telsonbase_mcp_api_key"       "Master API key (64 hex chars)"          32
generate_secret "telsonbase_jwt_secret"         "JWT signing key (64 hex chars)"         32
generate_secret "telsonbase_encryption_key"     "AES-256-GCM master key (64 hex chars)"  32
generate_secret "telsonbase_encryption_salt"    "PBKDF2 salt (32 hex chars)"             16

echo ""

# REM: =====================================================
# REM: SERVICE SECRETS
# REM: =====================================================
echo -e "${YELLOW}[Service Secrets]${NC}"
generate_secret "telsonbase_webui_secret"       "Open-WebUI session secret"              32
generate_password "telsonbase_grafana_password"  "Grafana admin password"                 24

echo ""

# REM: =====================================================
# REM: INFRASTRUCTURE PASSWORDS
# REM: =====================================================
echo -e "${YELLOW}[Infrastructure Passwords]${NC}"
generate_password "telsonbase_postgres_password" "PostgreSQL database password"           32
generate_password "telsonbase_redis_password"    "Redis authentication password"          32
generate_password "telsonbase_mqtt_password"     "MQTT broker (Mosquitto) password"       24

echo ""

# REM: =====================================================
# REM: SYNC GENERATED VALUES INTO .env
# REM: =====================================================
# REM: Pydantic Settings reads env vars (from .env via env_file) with higher priority
# REM: than default_factory. We sync every secret value into .env so deployers
# REM: never need to manually copy keys, and CHANGE_ME placeholders are replaced
# REM: automatically on first run.
# REM: Docker secret files (600) remain as a backup/audit copy.

update_env_var() {
    local env_var="$1"
    local secret_file="$2"
    if [ ! -f ".env" ] || [ ! -f "$secret_file" ]; then return; fi
    local value
    value=$(cat "$secret_file")
    if grep -q "^${env_var}=" .env; then
        sed -i "s|^${env_var}=.*|${env_var}=${value}|" .env
        echo -e "  ${GREEN}+${NC} .env: ${env_var} synced"
    fi
}

if [ -f ".env" ]; then
    echo -e "${CYAN}Syncing generated secrets into .env...${NC}"
    echo ""
    update_env_var "MCP_API_KEY"        "${SECRETS_DIR}/telsonbase_mcp_api_key"
    update_env_var "JWT_SECRET_KEY"     "${SECRETS_DIR}/telsonbase_jwt_secret"
    update_env_var "POSTGRES_PASSWORD"  "${SECRETS_DIR}/telsonbase_postgres_password"
    update_env_var "REDIS_PASSWORD"     "${SECRETS_DIR}/telsonbase_redis_password"
    update_env_var "MOSQUITTO_PASSWORD" "${SECRETS_DIR}/telsonbase_mqtt_password"
    update_env_var "WEBUI_SECRET_KEY"   "${SECRETS_DIR}/telsonbase_webui_secret"

    # REM: DATABASE_URL embeds the postgres password inline — update it too
    if [ -f "${SECRETS_DIR}/telsonbase_postgres_password" ]; then
        PG_PASS=$(cat "${SECRETS_DIR}/telsonbase_postgres_password")
        sed -i "s|DATABASE_URL=postgresql://telsonbase:[^@]*@|DATABASE_URL=postgresql://telsonbase:${PG_PASS}@|" .env
        echo -e "  ${GREEN}+${NC} .env: DATABASE_URL password updated"
    fi
    echo ""
else
    echo -e "${YELLOW}No .env found — skipping env sync. Copy .env.example to .env and re-run.${NC}"
    echo ""
fi

# REM: =====================================================
# REM: MOSQUITTO PASSWORD FILE
# REM: =====================================================
# REM: The MQTT broker requires a password file generated by mosquitto_passwd.
# REM: We use Docker (already required for the stack) to run mosquitto_passwd
# REM: so the host does not need mosquitto installed separately.

if [ -f "${SECRETS_DIR}/telsonbase_mqtt_password" ]; then
    echo -e "${CYAN}Creating Mosquitto password file...${NC}"
    echo ""
    MQPASS=$(cat "${SECRETS_DIR}/telsonbase_mqtt_password")
    PWFILE="./monitoring/mosquitto/password_file"

    if command -v docker &>/dev/null; then
        # REM: Remove existing file first — mosquitto_passwd -c won't overwrite a file
        # REM: it doesn't own (tarball files are owned by build user, not root)
        rm -f "$PWFILE"
        docker run --rm \
            -v "$(pwd)/monitoring/mosquitto:/mosquitto/config" \
            eclipse-mosquitto:2 \
            mosquitto_passwd -c -b /mosquitto/config/password_file telsonbase "$MQPASS"
        chmod 644 "$PWFILE"
        echo -e "  ${GREEN}+${NC} monitoring/mosquitto/password_file — created"
    else
        echo -e "  ${YELLOW}!${NC} Docker not available yet — password file not created."
        echo -e "  ${YELLOW}!${NC} Re-run this script after Docker is installed."
    fi
    echo ""
fi

# REM: =====================================================
# REM: VERIFY
# REM: =====================================================
echo -e "${CYAN}Verifying secrets...${NC}"
echo ""

ERROR_COUNT=0
for secret_file in "${ALL_SECRETS[@]}"; do
    filepath="${SECRETS_DIR}/${secret_file}"
    if [ ! -f "$filepath" ]; then
        echo -e "  ${RED}x${NC} ${secret_file} — MISSING"
        ERROR_COUNT=$((ERROR_COUNT + 1))
    else
        size=$(wc -c < "$filepath" | tr -d ' ')
        perms=$(stat -c '%a' "$filepath" 2>/dev/null || stat -f '%Lp' "$filepath" 2>/dev/null)
        if [ "$size" -lt 16 ]; then
            echo -e "  ${RED}x${NC} ${secret_file} — TOO SHORT (${size} bytes)"
            ERROR_COUNT=$((ERROR_COUNT + 1))
        elif [ "$perms" != "644" ]; then
            echo -e "  ${YELLOW}!${NC} ${secret_file} — OK but permissions are ${perms} (fixing to 644)"
            chmod 644 "$filepath"
        else
            echo -e "  ${GREEN}+${NC} ${secret_file} — OK (${size} bytes, mode ${perms})"
        fi
    fi
done

echo ""

if [ $ERROR_COUNT -gt 0 ]; then
    echo -e "${RED}FAILED: ${ERROR_COUNT} secret(s) have issues. Fix before deploying.${NC}"
    exit 1
fi

echo -e "${GREEN}==============================================================${NC}"
echo -e "${GREEN}                    All secrets generated!                     ${NC}"
echo -e "${GREEN}==============================================================${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT — Next steps:${NC}"
echo ""
echo "  1. BACK UP the ./secrets/ directory to your Drobo NAS or Snowball device"
echo "  2. Verify ./secrets/ is in your .gitignore (it should be)"
echo "  3. Start with:  docker-compose up -d --build"
echo "  4. Set TELSONBASE_ENV=production in your .env for production mode"
echo ""
echo -e "${RED}NEVER commit ./secrets/ to git. NEVER share these files.${NC}"
echo -e "${RED}If compromised, re-run this script with --rotate to rotate all secrets.${NC}"
echo ""
