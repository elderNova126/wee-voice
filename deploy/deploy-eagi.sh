#!/bin/bash

# =============================================================================
# WeeVoice EAGI Deployment Script
# =============================================================================
#
# This script deploys the WeeVoice AI Voice Agent using EAGI (Extended AGI)
# for Asterisk phone call handling with Zadarma SIP trunk.
#
# Prerequisites:
#   1. Asterisk 18+ installed with PJSIP
#   2. Python 3.9+ installed
#   3. GOOGLE_API_KEY configured
#   4. Zadarma SIP trunk configured in pjsip.conf
#
# Usage:
#   sudo ./deploy-eagi.sh
#
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

echo ""
echo "============================================"
echo "  WeeVoice EAGI Deployment"
echo "============================================"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root: sudo ./deploy-eagi.sh"
    exit 1
fi

# Directories
WEEVOICE_DIR="/opt/weevoice"
AGI_BIN="/var/lib/asterisk/agi-bin"
ASTERISK_CONF="/etc/asterisk"
LOG_DIR="/var/log/weevoice"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/../backend"

# =============================================================================
# Step 1: Verify Asterisk
# =============================================================================
log_step "Step 1/7: Verifying Asterisk installation..."

if ! command -v asterisk &> /dev/null; then
    log_error "Asterisk not found. Please install Asterisk first."
    exit 1
fi

ASTERISK_VERSION=$(asterisk -V 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)
log_info "Asterisk version: $ASTERISK_VERSION"

# Verify Asterisk directories exist
if [ ! -d "$AGI_BIN" ]; then
    log_info "Creating AGI directory: $AGI_BIN"
    mkdir -p "$AGI_BIN"
    chown asterisk:asterisk "$AGI_BIN"
fi

# =============================================================================
# Step 2: Install Python dependencies
# =============================================================================
log_step "Step 2/7: Installing Python dependencies..."

# Install system packages
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv python3-dotenv > /dev/null 2>&1 || true

# Create WeeVoice directory structure
mkdir -p "$WEEVOICE_DIR"/{backend,config,data}
mkdir -p "$LOG_DIR"

# Copy backend files
log_info "Copying backend files..."
cp -r "$BACKEND_DIR"/* "$WEEVOICE_DIR/backend/"

# Create virtual environment
log_info "Setting up Python virtual environment..."
cd "$WEEVOICE_DIR/backend"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Install dependencies
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
./venv/bin/pip install python-dotenv -q

log_info "Python dependencies installed"

# =============================================================================
# Step 3: Configure environment
# =============================================================================
log_step "Step 3/7: Configuring environment..."

# Check for existing .env
ENV_FILE="$WEEVOICE_DIR/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
    # Look for template or create minimal
    if [ -f "$SCRIPT_DIR/env-templates/backend.env" ]; then
        cp "$SCRIPT_DIR/env-templates/backend.env" "$ENV_FILE"
        log_info "Copied env template"
    elif [ -f "$BACKEND_DIR/.env" ]; then
        cp "$BACKEND_DIR/.env" "$ENV_FILE"
        log_info "Copied existing .env"
    else
        # Create minimal .env
        cat > "$ENV_FILE" << 'EOF'
# WeeVoice EAGI Configuration
DEBUG=false

# Google Gemini API (REQUIRED)
GOOGLE_API_KEY=

# Gemini model settings
GEMINI_MODEL=gemini-2.5-flash-native-audio-preview-09-2025

# High quality audio mode (16kHz instead of 8kHz)
WEEVOICE_HIGH_QUALITY=true

# Database (SQLite default)
DATABASE_URL=sqlite:////opt/weevoice/data/voiceagent.db

# Optional: OpenAI for summaries
OPENAI_API_KEY=
EOF
        log_warn "Created minimal .env - Please configure GOOGLE_API_KEY!"
    fi
fi

# Verify GOOGLE_API_KEY
if grep -q "^GOOGLE_API_KEY=$" "$ENV_FILE" || ! grep -q "^GOOGLE_API_KEY=" "$ENV_FILE"; then
    log_warn "GOOGLE_API_KEY not set in $ENV_FILE"
    log_warn "Please add your Google API key to continue"
fi

# =============================================================================
# Step 4: Install EAGI scripts
# =============================================================================
log_step "Step 4/7: Installing EAGI scripts..."

# Create EAGI wrapper script that activates venv and loads env
cat > "$AGI_BIN/weevoice_eagi_realtime.py" << 'EAGI_WRAPPER'
#!/bin/bash
# WeeVoice EAGI Wrapper - Activates venv and runs EAGI script

# Set environment
export HOME="/opt/weevoice"
export WEEVOICE_HIGH_QUALITY="true"

# Load .env file
if [ -f /opt/weevoice/backend/.env ]; then
    set -a
    source /opt/weevoice/backend/.env
    set +a
fi

# Run EAGI with virtual environment Python
exec /opt/weevoice/backend/venv/bin/python3 /opt/weevoice/backend/eagi/weevoice_eagi_realtime.py "$@"
EAGI_WRAPPER

# Make executable
chmod +x "$AGI_BIN/weevoice_eagi_realtime.py"
chown asterisk:asterisk "$AGI_BIN/weevoice_eagi_realtime.py"

log_info "EAGI script installed: $AGI_BIN/weevoice_eagi_realtime.py"

# Also create symlink for backward compatibility
ln -sf "$AGI_BIN/weevoice_eagi_realtime.py" "$AGI_BIN/weevoice_eagi.py" 2>/dev/null || true
chown -h asterisk:asterisk "$AGI_BIN/weevoice_eagi.py" 2>/dev/null || true

# =============================================================================
# Step 5: Configure Asterisk dialplan (extensions.conf)
# =============================================================================
log_step "Step 5/7: Configuring Asterisk dialplan..."

# Backup existing extensions.conf
if [ -f "$ASTERISK_CONF/extensions.conf" ]; then
    BACKUP_FILE="$ASTERISK_CONF/extensions.conf.backup.$(date +%Y%m%d%H%M%S)"
    cp "$ASTERISK_CONF/extensions.conf" "$BACKUP_FILE"
    log_info "Backed up extensions.conf to $BACKUP_FILE"
fi

# Copy our extensions.conf (contains [zadarma] context for incoming calls)
if [ -f "$SCRIPT_DIR/asterisk/extensions.conf" ]; then
    cp "$SCRIPT_DIR/asterisk/extensions.conf" "$ASTERISK_CONF/extensions.conf"
    chown asterisk:asterisk "$ASTERISK_CONF/extensions.conf"
    log_info "Installed extensions.conf with [zadarma] context"
else
    log_error "extensions.conf not found in $SCRIPT_DIR/asterisk/"
    exit 1
fi

# =============================================================================
# Step 6: Set permissions and create directories
# =============================================================================
log_step "Step 6/7: Setting permissions..."

# Set ownership
chown -R asterisk:asterisk "$WEEVOICE_DIR"
chown -R asterisk:asterisk "$LOG_DIR"

# Create temp directories for audio
mkdir -p /tmp/weevoice_audio
chown asterisk:asterisk /tmp/weevoice_audio
chmod 755 /tmp/weevoice_audio

# Ensure asterisk user can read backend files
chmod -R 755 "$WEEVOICE_DIR/backend"
chmod 600 "$ENV_FILE"
chown asterisk:asterisk "$ENV_FILE"

# =============================================================================
# Step 7: Reload Asterisk
# =============================================================================
log_step "Step 7/7: Reloading Asterisk..."

if pgrep -x asterisk > /dev/null; then
    asterisk -rx "dialplan reload" > /dev/null 2>&1 || true
    log_info "Asterisk dialplan reloaded"
else
    log_warn "Asterisk not running - start with: systemctl start asterisk"
fi

# =============================================================================
# Verify Installation
# =============================================================================
echo ""
echo "============================================"
echo -e "  ${GREEN}EAGI Deployment Complete!${NC}"
echo "============================================"
echo ""

# Check EAGI script
if [ -x "$AGI_BIN/weevoice_eagi_realtime.py" ]; then
    log_info "✓ EAGI script: $AGI_BIN/weevoice_eagi_realtime.py"
else
    log_error "✗ EAGI script not executable"
fi

# Check extensions.conf has zadarma context
if grep -q "\[zadarma\]" "$ASTERISK_CONF/extensions.conf" 2>/dev/null; then
    log_info "✓ Dialplan [zadarma] context configured"
else
    log_error "✗ Dialplan [zadarma] context missing"
fi

# Check API key
if grep -q "^GOOGLE_API_KEY=.\+" "$ENV_FILE" 2>/dev/null; then
    log_info "✓ GOOGLE_API_KEY configured"
else
    log_warn "⚠ GOOGLE_API_KEY not set - edit $ENV_FILE"
fi

# Show dialplan
echo ""
log_info "Dialplan contexts:"
asterisk -rx "dialplan show zadarma" 2>/dev/null | head -10 || echo "  (Asterisk not running)"

echo ""
echo "============================================"
echo "  Configuration Summary"
echo "============================================"
echo ""
echo "EAGI Script:"
echo "  $AGI_BIN/weevoice_eagi_realtime.py"
echo ""
echo "Dialplan Contexts:"
echo "  [zadarma]     - Incoming calls from Zadarma → AI Agent"
echo "  [webrtc]      - Outbound calls from AI/WebRTC"
echo "  [internal]    - Internal extension calls"
echo ""
echo "Call Flow:"
echo "  +32480206645 called → Zadarma → pjsip [zadarma] → EAGI AI Agent"
echo ""
echo "Next Steps:"
echo "  1. Verify GOOGLE_API_KEY in $ENV_FILE"
echo "  2. Ensure pjsip.conf has: context=zadarma for zadarma-endpoint"
echo "  3. Test: Call +32480206645"
echo ""
echo "Logs:"
echo "  tail -f /var/log/weevoice/eagi.log"
echo "  asterisk -rvvvv"
echo ""
