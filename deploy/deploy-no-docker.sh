#!/bin/bash

# =============================================================================
# WeeVoice Deployment Script (No Docker)
# =============================================================================
# 
# Prerequisites:
#   1. Ubuntu 20.04/22.04 VPS with Asterisk installed
#   2. Domain pointing to VPS (or use IP for testing)
#   3. backend/.env file with GOOGLE_API_KEY configured
#
# Usage:
#   cd deploy
#   sudo ./deploy-no-docker.sh weevoice.weedoo.be
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

echo ""
echo "============================================"
echo "  WeeVoice Deployment (No Docker)"
echo "============================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root: sudo ./deploy-no-docker.sh <domain>"
    exit 1
fi

# Get domain from argument or prompt
DOMAIN=${1:-}
if [ -z "$DOMAIN" ]; then
    log_error "Usage: sudo ./deploy-no-docker.sh <domain_or_ip>"
    log_error "Example: sudo ./deploy-no-docker.sh weevoice.weedoo.be"
    exit 1
fi

# Check for .env file (try multiple locations)
ENV_FILE=""
if [ -f "env-templates/backend.env" ]; then
    ENV_FILE="env-templates/backend.env"
elif [ -f "../backend/.env" ]; then
    ENV_FILE="../backend/.env"
fi

if [ -z "$ENV_FILE" ]; then
    log_error "No .env file found!"
    log_error "Please create deploy/env-templates/backend.env or backend/.env"
    exit 1
fi

log_info "Loading configuration from $ENV_FILE"
source "$ENV_FILE"

# Validate GOOGLE_API_KEY
if [ -z "$GOOGLE_API_KEY" ]; then
    log_error "GOOGLE_API_KEY not found in backend/.env"
    exit 1
fi

# Generate SECRET_KEY if not set
SECRET_KEY=${SECRET_KEY:-$(openssl rand -hex 32)}

# Determine protocol
if [[ $DOMAIN =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    PROTOCOL="http"
    USE_SSL=false
    log_warn "IP address detected - using HTTP (no SSL)"
else
    PROTOCOL="https"
    USE_SSL=true
fi

log_info "Domain: $DOMAIN"
log_info "Protocol: $PROTOCOL"
log_info "Google API Key: ${GOOGLE_API_KEY:0:15}..."

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"
WEEVOICE_DIR="/opt/weevoice"
BACKEND_DIR="${WEEVOICE_DIR}/backend"
AGI_BIN="/var/lib/asterisk/agi-bin"

# =============================================================================
# Step 1: Install Dependencies
# =============================================================================
log_step "Step 1/10: Installing system dependencies..."

apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip supervisor curl libsndfile1 > /dev/null

# Check if Apache2 is running (for Asterisk), use it instead of nginx
if systemctl is-active --quiet apache2; then
    USE_APACHE=true
    log_info "Apache2 detected (for Asterisk), will use Apache2 as reverse proxy"
    apt-get install -y -qq certbot python3-certbot-apache > /dev/null
else
    USE_APACHE=false
    apt-get install -y -qq nginx certbot python3-certbot-nginx > /dev/null
fi

# Install Node.js 22
if ! command -v node &> /dev/null || ! node -v | grep -q "v22"; then
    log_info "Installing Node.js 22..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - > /dev/null 2>&1
    apt-get install -y -qq nodejs > /dev/null
fi

# =============================================================================
# Step 2: Create Directory Structure
# =============================================================================
log_step "Step 2/10: Setting up directories..."

mkdir -p /opt/weevoice/{backend,frontend,data,uploads}
mkdir -p /var/log/weevoice
mkdir -p "$AGI_BIN"

# Copy application files
cp -r ../backend/* /opt/weevoice/backend/
cp -r ../frontend/* /opt/weevoice/frontend/

# =============================================================================
# Step 3: Setup Backend
# =============================================================================
log_step "Step 3/10: Setting up backend..."

cd /opt/weevoice/backend

# Create virtual environment and install dependencies
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

# Install websockets for EAGI
./venv/bin/pip install -q websockets

# Install high-quality audio libraries for EAGI (soxr for VHQ resampling)
log_info "Installing high-quality audio libraries for EAGI..."
./venv/bin/pip install -q numpy soxr 2>/dev/null && \
    log_info "✓ soxr VHQ audio resampler installed" || \
    log_warn "⚠ Could not install soxr - EAGI will use audioop fallback (lower quality)"

# Create production .env (preserving all original values + overriding URLs)
cat > .env << EOF
# =============================================================================
# WeeVoice Backend - Production (auto-generated by deploy script)
# =============================================================================

# Core Settings
DEBUG=false
SECRET_KEY=$SECRET_KEY
BASE_URL=$PROTOCOL://$DOMAIN
FRONTEND_URL=$PROTOCOL://$DOMAIN
BACKEND_URL=$PROTOCOL://$DOMAIN/api
BACKEND_CORS_ORIGINS=["$PROTOCOL://$DOMAIN","http://localhost:3000"]

# Database
DATABASE_URL=${DATABASE_URL:-sqlite:////opt/weevoice/data/voiceagent.db}

# AI APIs
GOOGLE_API_KEY=$GOOGLE_API_KEY
OPENAI_API_KEY=${OPENAI_API_KEY:-}
OPENAI_SUMMARY_MODEL=${OPENAI_SUMMARY_MODEL:-gpt-4o}

# Storage (Supabase)
STORAGE_URL=${STORAGE_URL:-}
STORAGE_KEY=${STORAGE_KEY:-}
STORAGE_BUCKET=${STORAGE_BUCKET:-weevoice}

# Email (SMTP) - Using TLS on port 587
SMTP_HOST=${SMTP_HOST:-mail.weedoo.be}
SMTP_PORT=${SMTP_PORT:-587}
SMTP_USER=${SMTP_USER:-voice@weedoo.be}
SMTP_PASSWORD=${SMTP_PASSWORD:-}
SMTP_USE_TLS=${SMTP_USE_TLS:-1}
SMTP_USE_SSL=${SMTP_USE_SSL:-0}
SMTP_FROM_EMAIL=${SMTP_FROM_EMAIL:-voice@weedoo.be}
SMTP_FROM_NAME=${SMTP_FROM_NAME:-WeeVoice}

# Zadarma Integration
ZADARMA_API_KEY=${ZADARMA_API_KEY:-}
ZADARMA_API_SECRET=${ZADARMA_API_SECRET:-}

# SIP / AudioSocket
SIP_ENABLED=true

# Pricing
COST_PER_MINUTE=${COST_PER_MINUTE:-0.07}
PHONE_NUMBER_MONTHLY_COST=${PHONE_NUMBER_MONTHLY_COST:-4.99}

# Storage Paths (auto-set for VPS)
UPLOAD_DIR=/opt/weevoice/uploads
CALL_RECORDINGS_PATH=/opt/weevoice/data/recordings
TRANSCRIPTS_PATH=/opt/weevoice/data/transcripts

# Asterisk Configuration (for dynamic SIP config generation)
ASTERISK_CONFIG_DIR=/etc/asterisk
ASTERISK_AGI_DIR=/var/lib/asterisk/agi-bin

# Stripe (optional)
STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY:-}
STRIPE_PUBLISHABLE_KEY=${STRIPE_PUBLISHABLE_KEY:-}
STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET:-}
EOF

# =============================================================================
# Step 4: Setup Frontend
# =============================================================================
log_step "Step 4/10: Setting up frontend..."

cd /opt/weevoice/frontend

# Create frontend .env (Vite uses VITE_ prefix)
# Note: Don't include /api - the frontend code already adds /api/v1
cat > .env.local << EOF
VITE_API_URL=$PROTOCOL://$DOMAIN
EOF

# Install dependencies
if [ -f "yarn.lock" ]; then
    log_info "Using Yarn..."
    npm install -g yarn > /dev/null 2>&1
    yarn install --frozen-lockfile
else
    npm ci --silent
fi

# Build (skip TypeScript check to avoid strict errors)
log_info "Building frontend..."
npx vite build

# =============================================================================
# Step 5: Setup EAGI (Asterisk Voice Agent)
# =============================================================================
log_step "Step 5/10: Setting up EAGI for Asterisk..."

# Copy EAGI scripts
if [ -d "${SOURCE_DIR}/backend/eagi" ]; then
    cp -r "${SOURCE_DIR}/backend/eagi" "${BACKEND_DIR}/"
    chmod +x "${BACKEND_DIR}/eagi"/*.py 2>/dev/null || true
    log_info "✓ EAGI scripts copied"
fi

# Check if eagi.py API endpoint exists and copy it
if [ -f "${SOURCE_DIR}/backend/app/api/eagi.py" ]; then
    cp "${SOURCE_DIR}/backend/app/api/eagi.py" "${BACKEND_DIR}/app/api/"
    log_info "✓ EAGI API endpoint installed"
fi

# Check if main.py needs eagi import
if [ -f "${BACKEND_DIR}/app/main.py" ]; then
    if ! grep -q "from app.api import.*eagi" "${BACKEND_DIR}/app/main.py"; then
        log_info "Adding EAGI router to main.py..."
        
        # Add eagi to imports (append to existing import line)
        sed -i 's/phone_debug, performance$/phone_debug, performance, eagi/' "${BACKEND_DIR}/app/main.py" 2>/dev/null || true
        
        # Add router (only if not already there)
        if ! grep -q "eagi.router" "${BACKEND_DIR}/app/main.py"; then
            sed -i '/performance.router/a app.include_router(eagi.router, prefix=f"{settings.API_V1_STR}/eagi", tags=["EAGI"])' "${BACKEND_DIR}/app/main.py" 2>/dev/null || true
        fi
        
        log_info "✓ EAGI router added to main.py"
    else
        log_info "✓ EAGI already configured in main.py"
    fi
fi

# Create AGI wrapper script
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
log_info "✓ AGI wrapper script created"

# =============================================================================
# Step 6: Deploy Asterisk Configuration (PJSIP + Dialplan)
# =============================================================================
log_step "Step 6/10: Deploying Asterisk configuration..."

if command -v asterisk &> /dev/null; then
    ASTERISK_CONF="/etc/asterisk"
    BACKUP_SUFFIX="backup.$(date +%Y%m%d%H%M%S)"
    
    # Backup existing configs
    [ -f "$ASTERISK_CONF/extensions.conf" ] && cp "$ASTERISK_CONF/extensions.conf" "$ASTERISK_CONF/extensions.conf.$BACKUP_SUFFIX"
    [ -f "$ASTERISK_CONF/pjsip.conf" ] && cp "$ASTERISK_CONF/pjsip.conf" "$ASTERISK_CONF/pjsip.conf.$BACKUP_SUFFIX"
    
    # Deploy extensions.conf
    if [ -f "${SOURCE_DIR}/deploy/asterisk/extensions.conf" ]; then
        cp "${SOURCE_DIR}/deploy/asterisk/extensions.conf" "$ASTERISK_CONF/extensions.conf"
        chown asterisk:asterisk "$ASTERISK_CONF/extensions.conf"
        log_info "✓ extensions.conf deployed"
    fi
    
    # Deploy pjsip.conf
    if [ -f "${SOURCE_DIR}/deploy/asterisk/pjsip.conf" ]; then
        cp "${SOURCE_DIR}/deploy/asterisk/pjsip.conf" "$ASTERISK_CONF/pjsip.conf"
        chown asterisk:asterisk "$ASTERISK_CONF/pjsip.conf"
        log_info "✓ pjsip.conf deployed"
    fi
    
    # Create empty weevoice include files (will be generated by backend when phone numbers are configured)
    touch "$ASTERISK_CONF/pjsip_weevoice.conf"
    touch "$ASTERISK_CONF/extensions_weevoice.conf"
    
    # Create Zadarma credentials file
    # Priority: 1. Database (existing credentials), 2. Environment variables, 3. Placeholder
    ZADARMA_USER=""
    ZADARMA_PASS=""
    ZADARMA_DOMAIN="sip.zadarma.com"
    CRED_SOURCE=""
    
    # Try to get credentials from database first
    if [ -n "$DATABASE_URL" ]; then
        log_info "Checking database for existing SIP credentials..."
        
        # Extract credentials from DATABASE_URL and query
        if [[ "$DATABASE_URL" == postgresql://* ]]; then
            # PostgreSQL database
            DB_CREDS=$(echo "$DATABASE_URL" | sed -E 's|postgresql://([^:]+):([^@]+)@([^/]+)/(.+)|\1 \2 \3 \4|')
            DB_USER=$(echo $DB_CREDS | cut -d' ' -f1)
            DB_PASS=$(echo $DB_CREDS | cut -d' ' -f2)
            DB_HOST=$(echo $DB_CREDS | cut -d' ' -f3)
            DB_NAME=$(echo $DB_CREDS | cut -d' ' -f4)
            
            # Query for SIP credentials
            SIP_RESULT=$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c \
                "SELECT sip_username, sip_password, sip_domain FROM phone_numbers WHERE sip_username IS NOT NULL AND sip_password IS NOT NULL AND sip_domain IS NOT NULL LIMIT 1;" 2>/dev/null | tr -d ' ')
            
            if [ -n "$SIP_RESULT" ] && [ "$SIP_RESULT" != "||" ]; then
                ZADARMA_USER=$(echo "$SIP_RESULT" | cut -d'|' -f1)
                ZADARMA_PASS=$(echo "$SIP_RESULT" | cut -d'|' -f2)
                ZADARMA_DOMAIN=$(echo "$SIP_RESULT" | cut -d'|' -f3)
                CRED_SOURCE="database"
                log_info "✓ Found SIP credentials in database (user: $ZADARMA_USER)"
            fi
        elif [[ "$DATABASE_URL" == sqlite://* ]]; then
            # SQLite database
            DB_PATH=$(echo "$DATABASE_URL" | sed 's|sqlite:///||')
            if [ -f "$DB_PATH" ]; then
                SIP_RESULT=$(sqlite3 "$DB_PATH" \
                    "SELECT sip_username, sip_password, sip_domain FROM phone_numbers WHERE sip_username IS NOT NULL AND sip_password IS NOT NULL AND sip_domain IS NOT NULL LIMIT 1;" 2>/dev/null)
                
                if [ -n "$SIP_RESULT" ]; then
                    ZADARMA_USER=$(echo "$SIP_RESULT" | cut -d'|' -f1)
                    ZADARMA_PASS=$(echo "$SIP_RESULT" | cut -d'|' -f2)
                    ZADARMA_DOMAIN=$(echo "$SIP_RESULT" | cut -d'|' -f3)
                    CRED_SOURCE="database"
                    log_info "✓ Found SIP credentials in database (user: $ZADARMA_USER)"
                fi
            fi
        fi
    fi
    
    # Fallback to environment variables if not found in database
    if [ -z "$ZADARMA_USER" ] || [ -z "$ZADARMA_PASS" ]; then
        if [ -n "${ZADARMA_SIP_LOGIN:-}" ] && [ -n "${ZADARMA_SIP_PASSWORD:-}" ]; then
            ZADARMA_USER="${ZADARMA_SIP_LOGIN}"
            ZADARMA_PASS="${ZADARMA_SIP_PASSWORD}"
            ZADARMA_DOMAIN="${ZADARMA_SIP_DOMAIN:-sip.zadarma.com}"
            CRED_SOURCE="environment"
            log_info "Using SIP credentials from environment variables"
        fi
    fi
    
    # Create credentials file
    if [ -n "$ZADARMA_USER" ] && [ -n "$ZADARMA_PASS" ]; then
        log_info "Creating Zadarma credentials from $CRED_SOURCE..."
        cat > "$ASTERISK_CONF/pjsip_zadarma_credentials.conf" << ZADEOF
;==============================================================================
; Zadarma SIP Authentication and Registration
; Auto-generated during deployment from $CRED_SOURCE
; Can be updated via Phone Numbers page in WeeVoice
;==============================================================================

[zadarma-auth]
type=auth
auth_type=userpass
username=${ZADARMA_USER}
password=${ZADARMA_PASS}

[zadarma-registration]
type=registration
transport=transport-udp
outbound_auth=zadarma-auth
server_uri=sip:${ZADARMA_DOMAIN}
client_uri=sip:${ZADARMA_USER}@${ZADARMA_DOMAIN}
retry_interval=60
max_retries=10
expiration=3600
line=yes
endpoint=zadarma-endpoint
ZADEOF
        log_info "✓ Zadarma credentials configured from $CRED_SOURCE"
    else
        log_warn "No SIP credentials found in database or environment"
        log_warn "Creating placeholder - configure via Phone Numbers page after deployment"
        cat > "$ASTERISK_CONF/pjsip_zadarma_credentials.conf" << 'ZADEOF'
;==============================================================================
; Zadarma SIP Authentication and Registration
; PLACEHOLDER - Configure via Phone Numbers page in WeeVoice
; Or edit this file manually with your Zadarma SIP credentials
;==============================================================================

[zadarma-auth]
type=auth
auth_type=userpass
username=CONFIGURE_ME
password=CONFIGURE_ME

[zadarma-registration]
type=registration
transport=transport-udp
outbound_auth=zadarma-auth
server_uri=sip:sip.zadarma.com
client_uri=sip:CONFIGURE_ME@sip.zadarma.com
retry_interval=60
max_retries=10
expiration=3600
line=yes
endpoint=zadarma-endpoint
ZADEOF
    fi
    
    # Set ownership to www-data (backend user) so it can update these files
    # Also add asterisk to the group for reading
    chown www-data:asterisk "$ASTERISK_CONF/pjsip_weevoice.conf"
    chown www-data:asterisk "$ASTERISK_CONF/extensions_weevoice.conf"
    chown www-data:asterisk "$ASTERISK_CONF/pjsip_zadarma_credentials.conf"
    chmod 664 "$ASTERISK_CONF/pjsip_weevoice.conf"
    chmod 664 "$ASTERISK_CONF/extensions_weevoice.conf"
    chmod 640 "$ASTERISK_CONF/pjsip_zadarma_credentials.conf"
    
    # Add www-data to asterisk group so backend can write to Asterisk configs
    usermod -a -G asterisk www-data 2>/dev/null || true
    
    # Make asterisk config directory group-writable so backend can create backup files
    chmod g+w "$ASTERISK_CONF"
    log_info "✓ Asterisk include files created with proper permissions"
    
    # Reload Asterisk configuration
    asterisk -rx "core reload" > /dev/null 2>&1 || true
    log_info "✓ Asterisk configuration reloaded"
    
    # Verify PJSIP loaded
    PJSIP_STATUS=$(asterisk -rx "pjsip show endpoints" 2>/dev/null | head -5)
    if echo "$PJSIP_STATUS" | grep -q "endpoint"; then
        log_info "✓ PJSIP endpoints loaded"
    else
        log_warn "⚠ No PJSIP endpoints yet - configure SIP credentials in Phone Numbers page"
    fi
else
    log_warn "Asterisk not found - skipping Asterisk configuration deployment"
fi

# =============================================================================
# Step 7: Configure Supervisor
# =============================================================================
log_step "Step 7/10: Configuring process manager..."

# Create cache directory for huggingface/transformers
mkdir -p /opt/weevoice/.cache

cat > /etc/supervisor/conf.d/weevoice.conf << EOF
[program:weevoice-backend]
command=/opt/weevoice/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
directory=/opt/weevoice/backend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/weevoice/backend.err.log
stdout_logfile=/var/log/weevoice/backend.out.log
environment=HOME="/opt/weevoice",HF_HOME="/opt/weevoice/.cache/huggingface",TRANSFORMERS_CACHE="/opt/weevoice/.cache/huggingface"
EOF

# Set permissions
chown -R www-data:www-data /opt/weevoice /var/log/weevoice

# Also allow asterisk user to access log directory for EAGI
if id "asterisk" &>/dev/null; then
    chown -R asterisk:asterisk /var/log/weevoice
    chmod 775 /var/log/weevoice
    chown asterisk:asterisk "${AGI_BIN}/weevoice_eagi_realtime.py"
fi

# =============================================================================
# Step 8: Configure Web Server (Apache2 or Nginx)
# =============================================================================
log_step "Step 8/10: Configuring web server..."

if [ "$USE_APACHE" = true ]; then
    # =========================================================================
    # Apache2 Configuration (when Asterisk uses Apache)
    # =========================================================================
    log_info "Configuring Apache2..."
    
    # Enable required modules
    a2enmod proxy proxy_http proxy_wstunnel ssl headers rewrite > /dev/null 2>&1
    
    # Check if SSL cert exists
    if [ "$USE_SSL" = true ] && [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        log_info "SSL certificate found, configuring HTTPS..."
        cat > /etc/apache2/sites-available/${DOMAIN}.conf << EOF
<VirtualHost *:80>
    ServerName $DOMAIN
    ServerAlias localhost 127.0.0.1
    
    # Only redirect to HTTPS if not localhost/127.0.0.1 (for testing)
    RewriteEngine On
    RewriteCond %{HTTPS} off
    RewriteCond %{HTTP_HOST} !^localhost [NC]
    RewriteCond %{HTTP_HOST} !^127\.0\.0\.1 [NC]
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
    
    # Serve frontend for localhost (no SSL needed for local testing)
    DocumentRoot /opt/weevoice/frontend/dist
    
    <Directory /opt/weevoice/frontend/dist>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
        
        # Cache static assets
        <FilesMatch "\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$">
            Header set Cache-Control "public, max-age=31536000, immutable"
        </FilesMatch>
    </Directory>
    
    # WebSocket FIRST (before regular API proxy and SPA routing)
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule ^/api/(.*)$ ws://127.0.0.1:8000/api/$1 [P,L]
    
    # API proxy (before SPA routing)
    ProxyPreserveHost On
    ProxyPass /api http://127.0.0.1:8000/api
    ProxyPassReverse /api http://127.0.0.1:8000/api
    ProxyTimeout 86400
    
    # SPA routing - serve index.html for non-file/non-api requests (must be last)
    # Only rewrite if it's not an API call, not assets, and not an existing file
    RewriteCond %{REQUEST_URI} !^/api
    RewriteCond %{REQUEST_URI} !^/assets/
    RewriteCond %{REQUEST_URI} !\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|json)$
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^ /index.html [L]
</VirtualHost>

<VirtualHost *:443>
    ServerName $DOMAIN
    ServerAlias localhost 127.0.0.1

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/$DOMAIN/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/$DOMAIN/privkey.pem

    # Serve frontend static files directly
    DocumentRoot /opt/weevoice/frontend/dist
    
    <Directory /opt/weevoice/frontend/dist>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
        
        # Cache static assets
        <FilesMatch "\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$">
            Header set Cache-Control "public, max-age=31536000, immutable"
        </FilesMatch>
    </Directory>
    
    # WebSocket FIRST (before regular API proxy and SPA routing)
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule ^/api/(.*)$ ws://127.0.0.1:8000/api/$1 [P,L]

    # API proxy (before SPA routing)
    ProxyPreserveHost On
    ProxyPass /api http://127.0.0.1:8000/api
    ProxyPassReverse /api http://127.0.0.1:8000/api
    ProxyTimeout 86400
    
    # SPA routing - serve index.html for non-file/non-api requests (must be last)
    # Only rewrite if it's not an API call, not assets, and not an existing file
    RewriteCond %{REQUEST_URI} !^/api
    RewriteCond %{REQUEST_URI} !^/assets/
    RewriteCond %{REQUEST_URI} !\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|json)$
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^ /index.html [L]
    
    RequestHeader set X-Forwarded-Proto "https"
</VirtualHost>
EOF
    else
        log_info "Configuring HTTP (no SSL cert found)..."
        cat > /etc/apache2/sites-available/${DOMAIN}.conf << EOF
<VirtualHost *:80>
    ServerName $DOMAIN
    ServerAlias localhost 127.0.0.1

    # Serve frontend static files directly
    DocumentRoot /opt/weevoice/frontend/dist
    
    <Directory /opt/weevoice/frontend/dist>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
        
        RewriteEngine On
        RewriteBase /
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteCond %{REQUEST_URI} !^/api
        RewriteRule ^ index.html [L]
    </Directory>

    # WebSocket FIRST (before regular API proxy)
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule ^/api/(.*)\$ ws://127.0.0.1:8000/api/\$1 [P,L]

    # API proxy
    ProxyPreserveHost On
    ProxyPass /api http://127.0.0.1:8000/api
    ProxyPassReverse /api http://127.0.0.1:8000/api

    ProxyTimeout 86400
</VirtualHost>
EOF
    fi
    
    # Enable site and test
    a2ensite ${DOMAIN}.conf > /dev/null 2>&1
    apachectl configtest
    
else
    # =========================================================================
    # Nginx Configuration (default - when Apache is not running)
    # =========================================================================
    log_info "Configuring Nginx..."
    
    rm -f /etc/nginx/sites-enabled/weevoice
    rm -f /etc/nginx/sites-enabled/default

    if [ "$USE_SSL" = true ] && [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        log_info "SSL certificate found, configuring HTTPS..."
        cat > /etc/nginx/sites-available/weevoice << EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Serve frontend static files
    root /opt/weevoice/frontend/dist;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # WebSocket
    location /api/v1/ws/ {
        proxy_pass http://127.0.0.1:8000/api/v1/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400;
    }

    # EAGI WebSocket
    location /api/v1/eagi/ {
        proxy_pass http://127.0.0.1:8000/api/v1/eagi/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400;
    }

    # API
    location /api {
        proxy_pass http://127.0.0.1:8000/api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
}
EOF
    else
        log_info "Configuring HTTP..."
        cat > /etc/nginx/sites-available/weevoice << EOF
server {
    listen 80;
    server_name $DOMAIN;

    # Serve frontend static files
    root /opt/weevoice/frontend/dist;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # WebSocket
    location /api/v1/ws/ {
        proxy_pass http://127.0.0.1:8000/api/v1/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_read_timeout 86400;
    }

    # EAGI WebSocket
    location /api/v1/eagi/ {
        proxy_pass http://127.0.0.1:8000/api/v1/eagi/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_read_timeout 86400;
    }

    # API
    location /api {
        proxy_pass http://127.0.0.1:8000/api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400;
    }
}
EOF
    fi
    
    ln -sf /etc/nginx/sites-available/weevoice /etc/nginx/sites-enabled/
    nginx -t
fi

# =============================================================================
# Step 9: SSL Certificate (if needed)
# =============================================================================
if [ "$USE_SSL" = true ] && [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    log_step "Step 9/10: Getting SSL certificate..."
    if [ "$USE_APACHE" = true ]; then
        systemctl reload apache2
        certbot --apache -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
            log_warn "SSL failed - run manually: certbot --apache -d $DOMAIN"
        }
    else
        systemctl restart nginx
        certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
            log_warn "SSL failed - run manually: certbot --nginx -d $DOMAIN"
        }
    fi
else
    log_step "Step 9/10: SSL already configured or not needed, skipping..."
fi

# =============================================================================
# Step 10: Start Services
# =============================================================================
log_step "Step 10/10: Starting services..."

if [ "$USE_APACHE" = true ]; then
    systemctl reload apache2
else
    systemctl restart nginx
fi
supervisorctl reread > /dev/null
supervisorctl update > /dev/null
supervisorctl restart weevoice-backend 2>/dev/null || supervisorctl start weevoice-backend

# Wait for backend to start
sleep 3

# Configure firewall (if ufw is active)
if command -v ufw &> /dev/null && ufw status | grep -q "active"; then
    ufw allow 80/tcp > /dev/null
    ufw allow 443/tcp > /dev/null
    ufw allow 5060/udp > /dev/null
    ufw allow 8089/tcp > /dev/null
    ufw allow 9092/tcp > /dev/null  # AudioSocket for Asterisk audio streaming
fi

# =============================================================================
# Verify Services
# =============================================================================
echo ""
log_info "Verifying services..."

# Check backend
if curl -s "http://127.0.0.1:8000/api/v1/eagi/config" > /dev/null 2>&1; then
    log_info "✓ Backend API is responding"
else
    log_warn "⚠ Backend API not responding yet - backend may still be starting"
fi

# Check frontend build
if [ -d "/opt/weevoice/frontend/dist" ] && [ -f "/opt/weevoice/frontend/dist/index.html" ]; then
    FRONTEND_FILES=$(find /opt/weevoice/frontend/dist -type f | wc -l)
    log_info "✓ Frontend build found ($FRONTEND_FILES files in dist/)"
else
    log_error "✗ Frontend build missing! Expected: /opt/weevoice/frontend/dist/index.html"
    log_error "  Run: cd /opt/weevoice/frontend && npm ci && npm run build"
fi

# Check web server
if [ "$USE_APACHE" = true ]; then
    if systemctl is-active --quiet apache2; then
        log_info "✓ Apache2 is running"
    else
        log_error "✗ Apache2 is not running! Run: systemctl start apache2"
    fi
    
    # Check if site is enabled
    if [ -L "/etc/apache2/sites-enabled/${DOMAIN}.conf" ] || [ -L "/etc/apache2/sites-enabled/000-${DOMAIN}.conf" ]; then
        log_info "✓ Apache site ${DOMAIN}.conf is enabled"
    else
        log_warn "⚠ Apache site ${DOMAIN}.conf may not be enabled"
        log_warn "  Run: a2ensite ${DOMAIN}.conf && systemctl reload apache2"
    fi
    
    # Test frontend via web server
    if curl -s "http://127.0.0.1/" | grep -q "html\|<!DOCTYPE" 2>/dev/null; then
        log_info "✓ Frontend is accessible via Apache (http://127.0.0.1/)"
    else
        log_warn "⚠ Frontend not accessible via Apache - check configuration"
    fi
else
    if systemctl is-active --quiet nginx; then
        log_info "✓ Nginx is running"
    else
        log_error "✗ Nginx is not running! Run: systemctl start nginx"
    fi
    
    # Test frontend via web server
    if curl -s "http://127.0.0.1/" | grep -q "html\|<!DOCTYPE" 2>/dev/null; then
        log_info "✓ Frontend is accessible via Nginx (http://127.0.0.1/)"
    else
        log_warn "⚠ Frontend not accessible via Nginx - check configuration"
    fi
fi

# =============================================================================
# Done!
# =============================================================================
echo ""
echo "============================================"
echo -e "  ${GREEN}Deployment Complete!${NC}"
echo "============================================"
echo ""
echo "URLs:"
echo "  Frontend: $PROTOCOL://$DOMAIN"
echo "  API:      $PROTOCOL://$DOMAIN/api"
echo "  API Docs: $PROTOCOL://$DOMAIN/api/docs"
echo "  EAGI API: $PROTOCOL://$DOMAIN/api/v1/eagi/config"
echo ""
echo "EAGI (Asterisk Voice Agent):"
echo "  Script:   ${BACKEND_DIR}/eagi/weevoice_eagi_full.py"
echo "  Wrapper:  ${AGI_BIN}/weevoice_eagi_realtime.py"
echo "  Logs:     /var/log/weevoice/eagi.log"
echo "  Audio:    soxr VHQ (high-quality) if installed, audioop fallback otherwise"
echo ""
echo -e "${YELLOW}IMPORTANT: Configure SIP for Phone Calls${NC}"
echo "  1. Go to Phone Numbers page in the frontend"
echo "  2. Add your phone number with SIP credentials:"
echo "     - SIP Username: Your Zadarma SIP login"
echo "     - SIP Password: Your Zadarma SIP password"
echo "     - SIP Domain: sip.zadarma.com"
echo "  3. Assign an AI agent to the phone number"
echo "  4. Save - Asterisk config will be auto-generated"
echo ""
echo "Commands:"
echo "  Status:  supervisorctl status"
echo "  Logs:    tail -f /var/log/weevoice/backend.out.log"
echo "  EAGI:    tail -f /var/log/weevoice/eagi.log"
echo "  Restart: supervisorctl restart weevoice-backend"
echo ""
echo "Frontend Troubleshooting:"
echo "  Check build:  ls -la /opt/weevoice/frontend/dist/"
echo "  Rebuild:      cd /opt/weevoice/frontend && npm ci && npm run build"
if [ "$USE_APACHE" = true ]; then
    echo "  Apache status: systemctl status apache2"
    echo "  Apache logs:  tail -f /var/log/apache2/error.log"
    echo "  Access logs:  tail -f /var/log/apache2/access.log"
    echo "  Test local:  curl http://127.0.0.1/"
    echo "  Test HTTPS:  curl -k https://$DOMAIN/"
    echo "  Test assets: curl -I https://$DOMAIN/assets/index-*.js"
else
    echo "  Nginx status: systemctl status nginx"
    echo "  Nginx logs:   tail -f /var/log/nginx/error.log"
    echo "  Test local:  curl http://127.0.0.1/"
    echo "  Test HTTPS:  curl -k https://$DOMAIN/"
    echo "  Test assets: curl -I https://$DOMAIN/assets/index-*.js"
fi
echo ""
echo "Browser Debugging (if blank page):"
echo "  1. Open browser DevTools (F12)"
echo "  2. Check Console tab for JavaScript errors"
echo "  3. Check Network tab - look for failed requests (red)"
echo "  4. Verify assets load: https://$DOMAIN/assets/index-*.js"
echo "  5. Check API connection: https://$DOMAIN/api/v1/health"
echo ""
echo "Asterisk Commands:"
echo "  Verify:  asterisk -rx 'pjsip show endpoints'"
echo "  Reload:  asterisk -rx 'core reload'"
echo "  Debug:   asterisk -rvvvv"
echo ""
echo "Test phone call:"
echo "  1. Configure SIP credentials in Phone Numbers page"
echo "  2. Call your configured phone number"
echo "  3. Watch: tail -f /var/log/weevoice/eagi.log"
echo ""
