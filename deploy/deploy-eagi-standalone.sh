#!/bin/bash
#===============================================================================
# WeeVoice EAGI Full Deployment Script
# Deploys the EAGI script with FULL agent features (database, prompts, tools)
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
echo "  WeeVoice EAGI Full Deployment"
echo "=============================================="
echo ""

#===============================================================================
# Step 1: Check prerequisites
#===============================================================================
log_step "1/9: Checking prerequisites..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (sudo)"
    exit 1
fi

# Check Asterisk
if ! command -v asterisk &> /dev/null; then
    log_error "Asterisk is not installed"
    exit 1
fi
log_info "✓ Asterisk found"

# Check Python
if ! command -v python3 &> /dev/null; then
    log_error "Python3 is not installed"
    exit 1
fi
log_info "✓ Python3 found: $(python3 --version)"

#===============================================================================
# Step 2: Create directories
#===============================================================================
log_step "2/9: Creating directories..."

mkdir -p "$WEEVOICE_DIR"
mkdir -p "$BACKEND_DIR"
mkdir -p "$EAGI_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$AGI_BIN"
mkdir -p "${WEEVOICE_DIR}/data"

chown -R asterisk:asterisk "$LOG_DIR"
chmod 755 "$LOG_DIR"

log_info "✓ Directories created"

#===============================================================================
# Step 3: Create Python virtual environment
#===============================================================================
log_step "3/9: Setting up Python virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate and install dependencies
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q

# Install required packages
pip install -q \
    google-genai \
    sqlalchemy \
    httpx \
    pydantic \
    pydantic-settings \
    python-dotenv

log_info "✓ Virtual environment ready"

#===============================================================================
# Step 4: Copy backend app code
#===============================================================================
log_step "4/9: Copying backend application..."

# Copy app module for database models and services
if [ -d "${SOURCE_DIR}/backend/app" ]; then
    cp -r "${SOURCE_DIR}/backend/app" "${BACKEND_DIR}/"
    log_info "✓ Copied app module"
fi

# Copy prompts
if [ -d "${SOURCE_DIR}/backend/prompts" ]; then
    cp -r "${SOURCE_DIR}/backend/prompts" "${BACKEND_DIR}/"
    log_info "✓ Copied prompts"
fi

# Copy EAGI scripts
if [ -d "${SOURCE_DIR}/backend/eagi" ]; then
    cp -r "${SOURCE_DIR}/backend/eagi" "${BACKEND_DIR}/"
    log_info "✓ Copied EAGI scripts"
fi

#===============================================================================
# Step 5: Create/update .env file with REQUIRED settings
#===============================================================================
log_step "5/9: Configuring environment..."

ENV_FILE="${BACKEND_DIR}/.env"

# Create .env if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    log_info "Creating .env file..."
    cat > "$ENV_FILE" << 'ENV_EOF'
# WeeVoice Backend Configuration
# ==============================

# REQUIRED: Google API Key for Gemini
GOOGLE_API_KEY=your-google-api-key-here

# Gemini Model
GEMINI_MODEL=gemini-2.5-flash-preview-native-audio-dialog

# Database (SQLite)
DATABASE_URL=sqlite:////opt/weevoice/data/weevoice.db

# Backend settings (required for pydantic-settings)
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
SECRET_KEY=your-secret-key-change-me-in-production

# Optional: High quality audio mode (for SIP/WebRTC, not PSTN)
WEEVOICE_HIGH_QUALITY=false
ENV_EOF
    log_warn "⚠ Created .env - you must set GOOGLE_API_KEY!"
fi

# Ensure BACKEND_CORS_ORIGINS exists (fixes pydantic error)
if ! grep -q "^BACKEND_CORS_ORIGINS=" "$ENV_FILE"; then
    echo 'BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]' >> "$ENV_FILE"
    log_info "✓ Added BACKEND_CORS_ORIGINS to .env"
fi

# Ensure DATABASE_URL exists
if ! grep -q "^DATABASE_URL=" "$ENV_FILE"; then
    echo 'DATABASE_URL=sqlite:////opt/weevoice/data/weevoice.db' >> "$ENV_FILE"
    log_info "✓ Added DATABASE_URL to .env"
fi

# Ensure SECRET_KEY exists
if ! grep -q "^SECRET_KEY=" "$ENV_FILE"; then
    SECRET=$(openssl rand -hex 32 2>/dev/null || echo "change-me-in-production")
    echo "SECRET_KEY=$SECRET" >> "$ENV_FILE"
    log_info "✓ Added SECRET_KEY to .env"
fi

chmod 600 "$ENV_FILE"

#===============================================================================
# Step 6: Create AGI wrapper script
#===============================================================================
log_step "6/9: Creating AGI wrapper script..."

cat > "${AGI_BIN}/weevoice_eagi_realtime.py" << 'WRAPPER_EOF'
#!/bin/bash
#===============================================================================
# WeeVoice EAGI Wrapper Script
# Loads environment and executes the Python EAGI handler
#===============================================================================

export HOME="/opt/weevoice"
export PYTHONPATH="/opt/weevoice/backend:$PYTHONPATH"

# Load .env file
ENV_FILE="/opt/weevoice/backend/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Execute the Python EAGI script
exec /opt/weevoice/backend/venv/bin/python3 /opt/weevoice/backend/eagi/weevoice_eagi_full.py "$@"
WRAPPER_EOF

chmod +x "${AGI_BIN}/weevoice_eagi_realtime.py"
chown asterisk:asterisk "${AGI_BIN}/weevoice_eagi_realtime.py"

log_info "✓ Wrapper script created"

#===============================================================================
# Step 7: Initialize database if needed
#===============================================================================
log_step "7/9: Checking database..."

DB_FILE="${WEEVOICE_DIR}/data/weevoice.db"

if [ ! -f "$DB_FILE" ]; then
    log_warn "Database not found - creating default agent..."
    
    # Create a simple Python script to initialize DB
    cat > /tmp/init_db.py << 'INITDB_EOF'
import os
import sys
sys.path.insert(0, '/opt/weevoice/backend')

# Set env vars before importing
os.environ.setdefault('DATABASE_URL', 'sqlite:////opt/weevoice/data/weevoice.db')
os.environ.setdefault('BACKEND_CORS_ORIGINS', '["http://localhost"]')
os.environ.setdefault('SECRET_KEY', 'init-key')
os.environ.setdefault('GOOGLE_API_KEY', 'placeholder')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create engine directly
engine = create_engine('sqlite:////opt/weevoice/data/weevoice.db')

# Import models to create tables
try:
    from app.models.database import Base
    from app.models import VoiceAgent, PhoneNumber, User
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    print("Tables created")
    
    # Create session
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Check if agent exists
    agent = db.query(VoiceAgent).first()
    if not agent:
        # Create default user first
        from datetime import datetime
        user = User(
            email="admin@weevoice.local",
            hashed_password="placeholder",
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created user: {user.id}")
        
        # Create default agent
        agent = VoiceAgent(
            user_id=user.id,
            name="WeeVoice Assistant",
            system_prompt="You are a helpful and professional phone assistant. Be friendly and concise.",
            greeting="Hello! How can I help you today?",
            language="en-US",
            voice_id="Aoede",
            model_name="gemini-2.5-flash-preview-native-audio-dialog",
            temperature=0.7,
            rag_enabled=False,
            tools_enabled=[],
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        print(f"Created agent: {agent.name} (ID: {agent.id})")
        
        # Create phone number config
        phone = PhoneNumber(
            user_id=user.id,
            phone_number="+32480206645",
            agent_id=agent.id,
            sip_username="409481",
            sip_password="placeholder",
            sip_server="sip.zadarma.com",
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(phone)
        db.commit()
        print(f"Created phone number: {phone.phone_number}")
    else:
        print(f"Agent already exists: {agent.name}")
    
    db.close()
    print("Database initialized successfully")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
INITDB_EOF

    source "$VENV_DIR/bin/activate"
    cd "$BACKEND_DIR"
    python3 /tmp/init_db.py || log_warn "Database init had issues - may need manual setup"
    rm -f /tmp/init_db.py
fi

if [ -f "$DB_FILE" ]; then
    chown asterisk:asterisk "$DB_FILE"
    chmod 664 "$DB_FILE"
    log_info "✓ Database ready: $DB_FILE"
else
    log_warn "⚠ Database not created - configure via web UI"
fi

#===============================================================================
# Step 8: Deploy Asterisk dialplan
#===============================================================================
log_step "8/9: Deploying Asterisk dialplan..."

# Backup existing extensions.conf
if [ -f "/etc/asterisk/extensions.conf" ]; then
    cp "/etc/asterisk/extensions.conf" "/etc/asterisk/extensions.conf.backup.$(date +%Y%m%d%H%M%S)"
fi

# Copy new extensions.conf
if [ -f "${SOURCE_DIR}/deploy/asterisk/extensions.conf" ]; then
    cp "${SOURCE_DIR}/deploy/asterisk/extensions.conf" "/etc/asterisk/extensions.conf"
    chown asterisk:asterisk "/etc/asterisk/extensions.conf"
    log_info "✓ extensions.conf deployed"
else
    log_warn "extensions.conf not found in source, skipping..."
fi

# Reload Asterisk dialplan
asterisk -rx "dialplan reload" > /dev/null 2>&1 || true
log_info "✓ Asterisk dialplan reloaded"

#===============================================================================
# Step 9: Set permissions
#===============================================================================
log_step "9/9: Setting permissions..."

chown -R asterisk:asterisk "$WEEVOICE_DIR"
chmod +x "${EAGI_DIR}"/*.py 2>/dev/null || true

log_info "✓ Permissions set"

#===============================================================================
# Summary
#===============================================================================
echo ""
echo "=============================================="
echo "  Deployment Complete!"
echo "=============================================="
echo ""
log_info "EAGI Script: ${EAGI_DIR}/weevoice_eagi_full.py"
log_info "AGI Wrapper: ${AGI_BIN}/weevoice_eagi_realtime.py"
log_info "Config File: ${ENV_FILE}"
log_info "Database:    ${DB_FILE}"
log_info "Log File:    ${LOG_DIR}/eagi.log"
echo ""

# Check if API key is configured
if grep -q "^GOOGLE_API_KEY=your-google-api-key-here" "$ENV_FILE" 2>/dev/null; then
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ACTION REQUIRED: Set your Google API Key                    ║${NC}"
    echo -e "${YELLOW}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${YELLOW}║  Edit: ${ENV_FILE}${NC}"
    echo -e "${YELLOW}║  Set:  GOOGLE_API_KEY=your-actual-key                        ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
else
    log_info "✓ GOOGLE_API_KEY is configured"
fi

echo "To test:"
echo "  1. Ensure GOOGLE_API_KEY is set in ${ENV_FILE}"
echo "  2. Call your phone number"
echo "  3. Watch logs: tail -f ${LOG_DIR}/eagi.log"
echo ""
echo "To customize the agent:"
echo "  - Edit database via web UI, or"
echo "  - Modify directly in SQLite: ${DB_FILE}"
echo ""
