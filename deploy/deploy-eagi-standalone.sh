#!/bin/bash
#===============================================================================
# WeeVoice EAGI Deployment Script
# Deploys EAGI that uses backend WebSocket API for voice streaming
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
echo "  (Uses backend WebSocket API)"
echo "=============================================="
echo ""

#===============================================================================
# Step 1: Check prerequisites
#===============================================================================
log_step "1/8: Checking prerequisites..."

if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (sudo)"
    exit 1
fi

if ! command -v asterisk &> /dev/null; then
    log_error "Asterisk is not installed"
    exit 1
fi
log_info "✓ Asterisk found"

#===============================================================================
# Step 2: Create directories
#===============================================================================
log_step "2/8: Creating directories..."

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
log_step "3/8: Setting up Python virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q

# Install ONLY websockets (EAGI uses backend API for everything)
pip install -q websockets

log_info "✓ Virtual environment ready"

#===============================================================================
# Step 4: Copy EAGI scripts
#===============================================================================
log_step "4/8: Copying EAGI scripts..."

# Remove old app directory if it exists (causes pydantic issues)
if [ -d "${BACKEND_DIR}/app" ]; then
    rm -rf "${BACKEND_DIR}/app"
    log_info "✓ Removed old app directory"
fi

# Clear Python cache
find "${BACKEND_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${BACKEND_DIR}" -name "*.pyc" -delete 2>/dev/null || true
log_info "✓ Cleared Python cache"

# Copy EAGI scripts
if [ -d "${SOURCE_DIR}/backend/eagi" ]; then
    cp -r "${SOURCE_DIR}/backend/eagi" "${BACKEND_DIR}/"
    log_info "✓ Copied EAGI scripts"
fi

#===============================================================================
# Step 5: Copy API endpoint to running backend
#===============================================================================
log_step "5/8: Installing EAGI API endpoint..."

# Copy eagi.py to the running backend's API directory
if [ -f "${SOURCE_DIR}/backend/app/api/eagi.py" ]; then
    if [ -d "${BACKEND_DIR}/app/api" ]; then
        cp "${SOURCE_DIR}/backend/app/api/eagi.py" "${BACKEND_DIR}/app/api/"
        log_info "✓ Copied eagi.py to backend"
    else
        log_warn "Backend app/api directory not found - API may need manual setup"
    fi
fi

# Check if main.py needs eagi import
if [ -f "${BACKEND_DIR}/app/main.py" ]; then
    if ! grep -q "eagi" "${BACKEND_DIR}/app/main.py"; then
        log_warn "⚠ main.py doesn't have eagi import - adding it..."
        
        # Add eagi to imports
        sed -i 's/phone_debug, performance$/phone_debug, performance, eagi/' "${BACKEND_DIR}/app/main.py"
        
        # Add router (only if not already there)
        if ! grep -q "eagi.router" "${BACKEND_DIR}/app/main.py"; then
            sed -i '/performance.router/a app.include_router(eagi.router, prefix=f"{settings.API_V1_STR}/eagi", tags=["EAGI"])' "${BACKEND_DIR}/app/main.py"
        fi
        
        log_info "✓ Added eagi to main.py"
    else
        log_info "✓ eagi already in main.py"
    fi
fi

#===============================================================================
# Step 6: Create AGI wrapper script
#===============================================================================
log_step "6/8: Creating AGI wrapper script..."

cat > "${AGI_BIN}/weevoice_eagi_realtime.py" << 'WRAPPER_EOF'
#!/bin/bash
#===============================================================================
# WeeVoice EAGI Wrapper
# Connects to backend WebSocket API for AI voice streaming
#===============================================================================

export HOME="/opt/weevoice"

# Backend API URL (same server)
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"

# Run EAGI script
exec /opt/weevoice/backend/venv/bin/python3 /opt/weevoice/backend/eagi/weevoice_eagi_full.py "$@"
WRAPPER_EOF

chmod +x "${AGI_BIN}/weevoice_eagi_realtime.py"
chown asterisk:asterisk "${AGI_BIN}/weevoice_eagi_realtime.py"

log_info "✓ Wrapper script created"

#===============================================================================
# Step 7: Deploy Asterisk dialplan
#===============================================================================
log_step "7/8: Deploying Asterisk dialplan..."

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

#===============================================================================
# Step 8: Set permissions and restart services
#===============================================================================
log_step "8/8: Finalizing..."

# Set permissions
chown -R asterisk:asterisk "$WEEVOICE_DIR"
chmod +x "${EAGI_DIR}"/*.py 2>/dev/null || true

# Clear log for fresh start
truncate -s 0 "${LOG_DIR}/eagi.log" 2>/dev/null || true

# Restart backend if using supervisor
if command -v supervisorctl &> /dev/null; then
    if supervisorctl status weevoice-backend &> /dev/null; then
        log_info "Restarting backend via supervisor..."
        supervisorctl restart weevoice-backend
        sleep 3
    fi
fi

#===============================================================================
# Verify
#===============================================================================
echo ""
echo "=============================================="
echo "  Deployment Complete!"
echo "=============================================="
echo ""

# Check backend
if curl -s "http://127.0.0.1:8000/api/v1/eagi/config" > /dev/null 2>&1; then
    log_info "✓ Backend API is responding"
else
    log_warn "⚠ Backend API not responding - make sure it's running"
    log_warn "  Try: sudo supervisorctl restart weevoice-backend"
fi

echo ""
log_info "EAGI Script:  ${EAGI_DIR}/weevoice_eagi_full.py"
log_info "AGI Wrapper:  ${AGI_BIN}/weevoice_eagi_realtime.py"
log_info "Log File:     ${LOG_DIR}/eagi.log"
echo ""
echo "To test:"
echo "  1. Make sure backend is running: curl http://127.0.0.1:8000/api/v1/eagi/config"
echo "  2. Call your phone number"
echo "  3. Watch logs: tail -f ${LOG_DIR}/eagi.log"
echo ""
