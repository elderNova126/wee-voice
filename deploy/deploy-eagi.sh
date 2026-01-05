#!/bin/bash

# =============================================================================
# WeeVoice EAGI Deployment Script
# =============================================================================
#
# This script deploys the WeeVoice AI Voice Agent using EAGI (Extended AGI)
# for Asterisk phone call handling.
#
# Prerequisites:
#   1. Asterisk 18+ installed
#   2. Python 3.9+ installed
#   3. GOOGLE_API_KEY configured
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
log_step "Step 1/6: Verifying Asterisk installation..."

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
log_step "Step 2/6: Installing Python dependencies..."

# Install system packages
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv > /dev/null

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

log_info "Python dependencies installed"

# =============================================================================
# Step 3: Configure environment
# =============================================================================
log_step "Step 3/6: Configuring environment..."

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

# Gemini model and voice settings
GEMINI_MODEL=gemini-2.5-flash-native-audio-preview-09-2025
GEMINI_VOICE=Aoede

# Agent configuration (can be overridden per-agent in database)
AGENT_SYSTEM_PROMPT=You are a helpful and professional phone assistant. Keep responses concise and natural.
AGENT_GREETING=Hello! How can I help you today?

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
log_step "Step 4/6: Installing EAGI scripts..."

# Create EAGI wrapper script that activates venv
cat > "$AGI_BIN/weevoice_eagi.py" << 'EAGI_WRAPPER'
#!/bin/bash
# WeeVoice EAGI Wrapper - Activates venv and runs EAGI script

# Load environment
export HOME="/opt/weevoice"
source /opt/weevoice/backend/.env 2>/dev/null

# Run EAGI with virtual environment Python
exec /opt/weevoice/backend/venv/bin/python3 /opt/weevoice/backend/eagi/weevoice_eagi_realtime.py "$@"
EAGI_WRAPPER

# Make executable
chmod +x "$AGI_BIN/weevoice_eagi.py"
chown asterisk:asterisk "$AGI_BIN/weevoice_eagi.py"

log_info "EAGI script installed: $AGI_BIN/weevoice_eagi.py"

# Also create a direct Python script for debugging
cat > "$AGI_BIN/weevoice_debug.py" << 'DEBUG_SCRIPT'
#!/opt/weevoice/backend/venv/bin/python3
# Direct EAGI script for debugging
import sys
sys.path.insert(0, '/opt/weevoice/backend')
from eagi.weevoice_eagi_realtime import main
main()
DEBUG_SCRIPT

chmod +x "$AGI_BIN/weevoice_debug.py"
chown asterisk:asterisk "$AGI_BIN/weevoice_debug.py"

# =============================================================================
# Step 5: Configure Asterisk dialplan
# =============================================================================
log_step "Step 5/6: Configuring Asterisk dialplan..."

# Backup existing extensions.conf
if [ -f "$ASTERISK_CONF/extensions.conf" ]; then
    cp "$ASTERISK_CONF/extensions.conf" "$ASTERISK_CONF/extensions.conf.backup.$(date +%Y%m%d)"
fi

# Copy EAGI dialplan
cp "$SCRIPT_DIR/asterisk/extensions_eagi.conf" "$ASTERISK_CONF/"
chown asterisk:asterisk "$ASTERISK_CONF/extensions_eagi.conf"

# Check if include exists in extensions.conf
if ! grep -q "extensions_eagi.conf" "$ASTERISK_CONF/extensions.conf" 2>/dev/null; then
    log_info "Adding EAGI dialplan include to extensions.conf..."
    
    # Add include at end of file
    echo "" >> "$ASTERISK_CONF/extensions.conf"
    echo "; WeeVoice EAGI AI Agent" >> "$ASTERISK_CONF/extensions.conf"
    echo '#include "extensions_eagi.conf"' >> "$ASTERISK_CONF/extensions.conf"
fi

# Reload dialplan
if pgrep -x asterisk > /dev/null; then
    asterisk -rx "dialplan reload" > /dev/null 2>&1 || true
    log_info "Asterisk dialplan reloaded"
else
    log_warn "Asterisk not running - dialplan will load on start"
fi

# =============================================================================
# Step 6: Set permissions and create directories
# =============================================================================
log_step "Step 6/6: Setting permissions..."

# Set ownership
chown -R asterisk:asterisk "$WEEVOICE_DIR"
chown -R asterisk:asterisk "$LOG_DIR"

# Create temp directories
mkdir -p /tmp/weevoice_fifos /tmp/weevoice_audio
chown asterisk:asterisk /tmp/weevoice_fifos /tmp/weevoice_audio
chmod 755 /tmp/weevoice_fifos /tmp/weevoice_audio

# Ensure asterisk user can read backend files
chmod -R 755 "$WEEVOICE_DIR/backend"
chmod 600 "$ENV_FILE"
chown asterisk:asterisk "$ENV_FILE"

# =============================================================================
# Verify Installation
# =============================================================================
echo ""
echo "============================================"
echo -e "  ${GREEN}EAGI Deployment Complete!${NC}"
echo "============================================"
echo ""

# Check EAGI script
if [ -x "$AGI_BIN/weevoice_eagi.py" ]; then
    log_info "✓ EAGI script installed: $AGI_BIN/weevoice_eagi.py"
else
    log_error "✗ EAGI script not executable"
fi

# Check dialplan
if grep -q "weevoice-ai-agent" "$ASTERISK_CONF/extensions_eagi.conf" 2>/dev/null; then
    log_info "✓ Asterisk dialplan configured"
else
    log_error "✗ Dialplan configuration missing"
fi

# Check API key
if grep -q "^GOOGLE_API_KEY=.\+" "$ENV_FILE" 2>/dev/null; then
    log_info "✓ GOOGLE_API_KEY configured"
else
    log_warn "⚠ GOOGLE_API_KEY not set - edit $ENV_FILE"
fi

echo ""
echo "Next steps:"
echo "  1. Edit $ENV_FILE and set GOOGLE_API_KEY"
echo "  2. Configure your SIP trunk to route to context [weevoice-ai-agent]"
echo "  3. Test with: asterisk -rx 'originate Local/s@weevoice-ai-agent application Wait 60'"
echo ""
echo "Dialplan contexts available:"
echo "  - weevoice-ai-agent    : Main AI agent context"
echo "  - from-zadarma         : For Zadarma SIP trunk"
echo "  - weevoice-test        : Test extensions (9999, 9998)"
echo ""
echo "Logs:"
echo "  - /var/log/weevoice/eagi_realtime.log"
echo "  - /var/log/asterisk/messages"
echo ""
echo "Debug:"
echo "  asterisk -rvvvv"
echo "  tail -f /var/log/weevoice/eagi_realtime.log"
echo ""

