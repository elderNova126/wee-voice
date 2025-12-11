#!/bin/bash

# WeeVoice Deployment Script (No Docker)
# Deploys Backend, Frontend, and configures Nginx on the same VPS as Asterisk

set -e

echo "============================================"
echo "  WeeVoice Deployment (No Docker)"
echo "============================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./deploy-no-docker.sh)"
    exit 1
fi

# Get configuration
read -p "Enter your domain name (e.g., voice.example.com): " DOMAIN
read -p "Enter your Google API Key: " GOOGLE_API_KEY
read -p "Enter your OpenAI API Key (optional, press Enter to skip): " OPENAI_API_KEY

# Generate secret key
SECRET_KEY=$(openssl rand -hex 32)

echo ""
echo "Step 1: Installing system dependencies..."

# Update system
apt-get update
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nodejs \
    npm \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    supervisor

# Install Node.js 18 if not present
if ! node -v | grep -q "v18"; then
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
fi

echo ""
echo "Step 2: Setting up directory structure..."

# Create directories
mkdir -p /opt/weevoice
mkdir -p /opt/weevoice/backend
mkdir -p /opt/weevoice/frontend
mkdir -p /opt/weevoice/data
mkdir -p /opt/weevoice/uploads
mkdir -p /var/log/weevoice

# Copy files (assuming we're in the deploy directory)
cp -r ../backend/* /opt/weevoice/backend/
cp -r ../frontend/* /opt/weevoice/frontend/

echo ""
echo "Step 3: Setting up Backend..."

cd /opt/weevoice/backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
cat > /opt/weevoice/backend/.env << EOF
# App Settings
DEBUG=false
SECRET_KEY=$SECRET_KEY
BASE_URL=https://$DOMAIN

# API Keys
GOOGLE_API_KEY=$GOOGLE_API_KEY
OPENAI_API_KEY=$OPENAI_API_KEY

# Database
DATABASE_URL=sqlite:////opt/weevoice/data/voiceagent.db

# URLs
FRONTEND_URL=https://$DOMAIN
BACKEND_URL=https://$DOMAIN/api

# Storage
UPLOAD_DIR=/opt/weevoice/uploads
CALL_RECORDINGS_PATH=/opt/weevoice/data/recordings
TRANSCRIPTS_PATH=/opt/weevoice/data/transcripts

# SIP (disabled, using AudioSocket)
SIP_ENABLED=false
EOF

deactivate

echo ""
echo "Step 4: Setting up Frontend..."

cd /opt/weevoice/frontend

# Create .env file for frontend
cat > .env.local << EOF
NEXT_PUBLIC_API_URL=https://$DOMAIN/api
EOF

# Install dependencies and build
npm ci
npm run build

echo ""
echo "Step 5: Configuring Supervisor (process manager)..."

# Create supervisor config for backend
cat > /etc/supervisor/conf.d/weevoice-backend.conf << EOF
[program:weevoice-backend]
command=/opt/weevoice/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
directory=/opt/weevoice/backend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/weevoice/backend.err.log
stdout_logfile=/var/log/weevoice/backend.out.log
environment=PATH="/opt/weevoice/backend/venv/bin"
EOF

# Create supervisor config for frontend
cat > /etc/supervisor/conf.d/weevoice-frontend.conf << EOF
[program:weevoice-frontend]
command=/usr/bin/npm start
directory=/opt/weevoice/frontend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/weevoice/frontend.err.log
stdout_logfile=/var/log/weevoice/frontend.out.log
environment=NODE_ENV="production",PORT="3000"
EOF

# Set permissions
chown -R www-data:www-data /opt/weevoice
chown -R www-data:www-data /var/log/weevoice

# Reload supervisor
supervisorctl reread
supervisorctl update

echo ""
echo "Step 6: Configuring Nginx..."

# Create nginx config
cat > /etc/nginx/sites-available/weevoice << EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    # SSL will be configured by certbot
    # ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # API routes -> Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
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

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/weevoice /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx config
nginx -t

echo ""
echo "Step 7: Getting SSL certificate..."

# Get SSL certificate
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
    echo "SSL certificate failed. You can run this manually later:"
    echo "  certbot --nginx -d $DOMAIN"
}

# Restart nginx
systemctl restart nginx

echo ""
echo "Step 8: Starting services..."

supervisorctl start weevoice-backend
supervisorctl start weevoice-frontend

echo ""
echo "Step 9: Configuring firewall..."

# Configure firewall
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 5060/udp   # SIP
ufw allow 8089/tcp   # WebSocket SIP
ufw allow 10000:20000/udp  # RTP

echo ""
echo "============================================"
echo "  Deployment Complete!"
echo "============================================"
echo ""
echo "Your WeeVoice is now running at:"
echo "  Frontend: https://$DOMAIN"
echo "  API:      https://$DOMAIN/api"
echo ""
echo "AudioSocket is listening on:"
echo "  127.0.0.1:9092 (localhost only)"
echo ""
echo "Service management:"
echo "  supervisorctl status"
echo "  supervisorctl restart weevoice-backend"
echo "  supervisorctl restart weevoice-frontend"
echo ""
echo "Logs:"
echo "  tail -f /var/log/weevoice/backend.out.log"
echo "  tail -f /var/log/weevoice/frontend.out.log"
echo ""
echo "Make sure your Asterisk extensions.conf uses:"
echo "  AudioSocket(\${CALL_UUID},127.0.0.1:9092)"
echo ""

