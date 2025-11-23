#!/bin/bash
# Quick Setup Script for .env file
# Run this on your VPS after deployment

echo "🔧 SIP Bridge Configuration Setup"
echo "=================================="
echo ""

# Check if .env already exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists!"
    read -p "Do you want to overwrite it? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Aborted."
        exit 0
    fi
    mv .env .env.backup
    echo "✅ Backed up existing .env to .env.backup"
fi

# Get Railway configuration
echo ""
echo "📋 Railway Backend Configuration"
echo "---------------------------------"
read -p "Enter your Railway app URL (e.g., myapp.railway.app): " RAILWAY_APP
read -p "Enter your Railway API key: " RAILWAY_API_KEY

# Get SIP configuration
echo ""
echo "📋 SIP Configuration"
echo "--------------------"
read -p "Enter SIP username [default: agent]: " SIP_USER
SIP_USER=${SIP_USER:-agent}

read -p "Enter SIP password [leave empty for none]: " SIP_PASS

# Get VPS IP
VPS_IP=$(curl -s ifconfig.me)
echo ""
echo "🌐 Detected VPS IP: $VPS_IP"
read -p "Is this correct? (Y/n): " ip_confirm
if [ "$ip_confirm" = "n" ] || [ "$ip_confirm" = "N" ]; then
    read -p "Enter your VPS IP: " VPS_IP
fi

# Optional: Zadarma IPs
echo ""
echo "🔒 Security (Optional)"
echo "---------------------"
read -p "Enter Zadarma IP ranges (comma-separated, or leave empty): " ZADARMA_IPS

# Create .env file
cat > .env << EOF
# ============================================
# SIP Bridge Configuration
# Generated: $(date)
# ============================================

# Railway Backend
BACKEND_WS_URL=wss://${RAILWAY_APP}/api/v1/ws/voice
BACKEND_API_KEY=${RAILWAY_API_KEY}

# SIP Server
SIP_HOST=0.0.0.0
SIP_PORT=5060
SIP_USERNAME=${SIP_USER}
SIP_PASSWORD=${SIP_PASS}
SIP_DOMAIN=${VPS_IP}

# RTP (Audio)
RTP_PORT_MIN=10000
RTP_PORT_MAX=20000

# Audio Configuration
INPUT_SAMPLE_RATE=16000
OUTPUT_SAMPLE_RATE=24000

# Logging
LOG_LEVEL=INFO

# Security
ZADARMA_ALLOWED_IPS=${ZADARMA_IPS}
EOF

echo ""
echo "✅ Configuration file created: .env"
echo ""
echo "📋 Your Configuration Summary"
echo "=============================="
echo "SIP URI: ${SIP_USER}@${VPS_IP}:5060"
echo "Backend: wss://${RAILWAY_APP}/api/v1/ws/voice"
echo ""
echo "🎯 Next Steps:"
echo "1. Test connection: python3 test_connection.py"
echo "2. Start FreeSWITCH: sudo systemctl start freeswitch"
echo "3. Configure Zadarma with SIP URI: ${SIP_USER}@${VPS_IP}:5060"
echo "4. Make a test call!"
echo ""

