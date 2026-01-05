#!/bin/bash
#===============================================================================
# WeeVoice EAGI Quick Update Script
# Use this to update EAGI files without full redeployment
#===============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
WEEVOICE_DIR="/opt/weevoice"
BACKEND_DIR="${WEEVOICE_DIR}/backend"
AGI_BIN="/var/lib/asterisk/agi-bin"
LOG_DIR="/var/log/weevoice"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"

echo "=============================================="
echo "  WeeVoice EAGI Quick Update"
echo "=============================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (sudo)"
    exit 1
fi

# Check prerequisites
if [ ! -d "$BACKEND_DIR" ]; then
    log_error "WeeVoice not installed at $WEEVOICE_DIR"
    log_error "Run deploy-no-docker.sh first for full installation"
    exit 1
fi

#===============================================================================
# Update EAGI Scripts
#===============================================================================
log_info "Updating EAGI scripts..."

# Copy EAGI scripts
if [ -d "${SOURCE_DIR}/backend/eagi" ]; then
    cp -r "${SOURCE_DIR}/backend/eagi" "${BACKEND_DIR}/"
    chmod +x "${BACKEND_DIR}/eagi"/*.py 2>/dev/null || true
    log_info "✓ EAGI scripts updated"
fi

# Update API endpoint
if [ -f "${SOURCE_DIR}/backend/app/api/eagi.py" ]; then
    cp "${SOURCE_DIR}/backend/app/api/eagi.py" "${BACKEND_DIR}/app/api/"
    log_info "✓ EAGI API endpoint updated"
fi

#===============================================================================
# Update AGI Wrapper
#===============================================================================
log_info "Updating AGI wrapper..."

cat > "${AGI_BIN}/weevoice_eagi_realtime.py" << 'WRAPPER_EOF'
#!/bin/bash
#===============================================================================
# WeeVoice EAGI Wrapper
# Connects to backend WebSocket API for AI voice streaming
#===============================================================================

export HOME="/opt/weevoice"
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"

exec /opt/weevoice/backend/venv/bin/python3 /opt/weevoice/backend/eagi/weevoice_eagi_full.py "$@"
WRAPPER_EOF

chmod +x "${AGI_BIN}/weevoice_eagi_realtime.py"
chown asterisk:asterisk "${AGI_BIN}/weevoice_eagi_realtime.py" 2>/dev/null || true

#===============================================================================
# Update Dialplan
#===============================================================================
log_info "Updating Asterisk dialplan..."

if [ -f "${SOURCE_DIR}/deploy/asterisk/extensions.conf" ]; then
    cp "${SOURCE_DIR}/deploy/asterisk/extensions.conf" "/etc/asterisk/extensions.conf"
    chown asterisk:asterisk "/etc/asterisk/extensions.conf" 2>/dev/null || true
    asterisk -rx "dialplan reload" > /dev/null 2>&1 || true
    log_info "✓ Dialplan updated and reloaded"
fi

#===============================================================================
# Restart Backend
#===============================================================================
log_info "Restarting backend..."

if command -v supervisorctl &> /dev/null; then
    supervisorctl restart weevoice-backend 2>/dev/null || true
    sleep 3
fi

# Clear EAGI log
truncate -s 0 "${LOG_DIR}/eagi.log" 2>/dev/null || true

#===============================================================================
# Verify
#===============================================================================
echo ""
log_info "Verifying..."

if curl -s "http://127.0.0.1:8000/api/v1/eagi/config" > /dev/null 2>&1; then
    log_info "✓ EAGI API is responding"
else
    log_warn "⚠ EAGI API not responding - check backend logs"
fi

echo ""
echo "=============================================="
echo -e "  ${GREEN}EAGI Update Complete!${NC}"
echo "=============================================="
echo ""
echo "Test: Call your phone number and watch:"
echo "  tail -f /var/log/weevoice/eagi.log"
echo ""
