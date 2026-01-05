#!/bin/bash
#===============================================================================
# WeeVoice EAGI Deployment Script
# Uses EXISTING web backend database (Neon) - no new DB needed
#===============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $1"; }

# Configuration
WEEVOICE_DIR="/opt/weevoice"
BACKEND_DIR="${WEEVOICE_DIR}/backend"
EAGI_DIR="${BACKEND_DIR}/eagi"
AGI_BIN="/var/lib/asterisk/agi-bin"
LOG_DIR="/var/log/weevoice"
VENV_DIR="${BACKEND_DIR}/venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"

echo "=============================================="
echo "  WeeVoice EAGI Deployment"
echo "  (Uses existing web backend database)"
echo "=============================================="
echo ""

#===============================================================================
# Step 1: Check prerequisites
#===============================================================================
log_step "1/7: Checking prerequisites..."

if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (sudo)"
    exit 1
fi

if ! command -v asterisk &> /dev/null; then
    log_error "Asterisk is not installed"
    exit 1
fi
log_info "✓ Asterisk found"

# Check for existing backend .env
if [ -f "${BACKEND_DIR}/.env" ]; then
    log_info "✓ Found existing backend .env"
elif [ -f "${SOURCE_DIR}/backend/.env" ]; then
    log_info "✓ Found source backend .env"
else
    log_warn "⚠ No .env found - you'll need to configure it"
fi

#===============================================================================
# Step 2: Create directories
#===============================================================================
log_step "2/7: Creating directories..."

mkdir -p "$WEEVOICE_DIR"
mkdir -p "$BACKEND_DIR"
mkdir -p "$EAGI_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$AGI_BIN"

chown -R asterisk:asterisk "$LOG_DIR"
chmod 755 "$LOG_DIR"

log_info "✓ Directories created"

#===============================================================================
# Step 3: Setup Python virtual environment
#===============================================================================
log_step "3/7: Setting up Python virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q

# Install dependencies (same as web backend)
pip install -q \
    google-genai \
    sqlalchemy \
    psycopg2-binary \
    httpx \
    pydantic \
    pydantic-settings \
    python-dotenv \
    langchain \
    langchain-google-genai \
    langchain-core

log_info "✓ Virtual environment ready"

#===============================================================================
# Step 4: Copy backend code
#===============================================================================
log_step "4/7: Copying backend application..."

# Copy entire backend (app, prompts, eagi)
if [ -d "${SOURCE_DIR}/backend/app" ]; then
    cp -r "${SOURCE_DIR}/backend/app" "${BACKEND_DIR}/"
    log_info "✓ Copied app module"
fi

if [ -d "${SOURCE_DIR}/backend/prompts" ]; then
    cp -r "${SOURCE_DIR}/backend/prompts" "${BACKEND_DIR}/"
    log_info "✓ Copied prompts"
fi

if [ -d "${SOURCE_DIR}/backend/eagi" ]; then
    cp -r "${SOURCE_DIR}/backend/eagi" "${BACKEND_DIR}/"
    log_info "✓ Copied EAGI scripts"
fi

# Copy .env if not exists (uses existing web backend config)
if [ ! -f "${BACKEND_DIR}/.env" ] && [ -f "${SOURCE_DIR}/backend/.env" ]; then
    cp "${SOURCE_DIR}/backend/.env" "${BACKEND_DIR}/.env"
    log_info "✓ Copied .env from source"
fi

#===============================================================================
# Step 5: Verify .env has required settings
#===============================================================================
log_step "5/7: Verifying environment configuration..."

ENV_FILE="${BACKEND_DIR}/.env"

if [ -f "$ENV_FILE" ]; then
    # Check for required variables
    if grep -q "^DATABASE_URL=" "$ENV_FILE"; then
        log_info "✓ DATABASE_URL configured (Neon)"
    else
        log_error "DATABASE_URL not found in .env!"
        log_error "Add your Neon database URL to ${ENV_FILE}"
    fi
    
    if grep -q "^GOOGLE_API_KEY=" "$ENV_FILE"; then
        log_info "✓ GOOGLE_API_KEY configured"
    else
        log_warn "⚠ GOOGLE_API_KEY not found - add it to ${ENV_FILE}"
    fi
    
    # Ensure BACKEND_CORS_ORIGINS exists (prevents pydantic error)
    if ! grep -q "^BACKEND_CORS_ORIGINS=" "$ENV_FILE"; then
        echo 'BACKEND_CORS_ORIGINS=["http://localhost:3000"]' >> "$ENV_FILE"
        log_info "✓ Added BACKEND_CORS_ORIGINS"
    fi
else
    log_error "No .env file found at ${ENV_FILE}"
    log_error "Copy your web backend .env file there"
    exit 1
fi

#===============================================================================
# Step 6: Create AGI wrapper script
#===============================================================================
log_step "6/7: Creating AGI wrapper script..."

cat > "${AGI_BIN}/weevoice_eagi_realtime.py" << 'WRAPPER_EOF'
#!/bin/bash
#===============================================================================
# WeeVoice EAGI Wrapper
# Loads environment from web backend and runs EAGI script
#===============================================================================

export HOME="/opt/weevoice"
export PYTHONPATH="/opt/weevoice/backend:$PYTHONPATH"

# Load .env (same as web backend - includes Neon DATABASE_URL)
ENV_FILE="/opt/weevoice/backend/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Run the EAGI script
exec /opt/weevoice/backend/venv/bin/python3 /opt/weevoice/backend/eagi/weevoice_eagi_full.py "$@"
WRAPPER_EOF

chmod +x "${AGI_BIN}/weevoice_eagi_realtime.py"
chown asterisk:asterisk "${AGI_BIN}/weevoice_eagi_realtime.py"

log_info "✓ Wrapper script created"

#===============================================================================
# Step 7: Deploy Asterisk dialplan & set permissions
#===============================================================================
log_step "7/7: Deploying Asterisk dialplan..."

if [ -f "/etc/asterisk/extensions.conf" ]; then
    cp "/etc/asterisk/extensions.conf" "/etc/asterisk/extensions.conf.backup.$(date +%Y%m%d%H%M%S)"
fi

if [ -f "${SOURCE_DIR}/deploy/asterisk/extensions.conf" ]; then
    cp "${SOURCE_DIR}/deploy/asterisk/extensions.conf" "/etc/asterisk/extensions.conf"
    chown asterisk:asterisk "/etc/asterisk/extensions.conf"
    log_info "✓ extensions.conf deployed"
fi

asterisk -rx "dialplan reload" > /dev/null 2>&1 || true
log_info "✓ Asterisk dialplan reloaded"

# Set permissions
chown -R asterisk:asterisk "$WEEVOICE_DIR"
chmod +x "${EAGI_DIR}"/*.py 2>/dev/null || true

#===============================================================================
# Summary
#===============================================================================
echo ""
echo "=============================================="
echo "  Deployment Complete!"
echo "=============================================="
echo ""
log_info "EAGI Script:  ${EAGI_DIR}/weevoice_eagi_full.py"
log_info "AGI Wrapper:  ${AGI_BIN}/weevoice_eagi_realtime.py"
log_info "Config File:  ${ENV_FILE}"
log_info "Log File:     ${LOG_DIR}/eagi.log"
echo ""
echo "The EAGI uses your EXISTING Neon database."
echo "Same agents and settings as your web UI."
echo ""
echo "To test:"
echo "  1. Call your phone number"
echo "  2. Watch logs: tail -f ${LOG_DIR}/eagi.log"
echo ""
