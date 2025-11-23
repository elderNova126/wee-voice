#!/bin/bash
# Simple Deployment Script for DigitalOcean/Linode
# Creates a basic SIP bridge server

set -e

echo "🚀 Simple SIP Bridge Deployment"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "⚠️  Please don't run as root. Run as regular user with sudo access."
    exit 1
fi

# Get configuration
read -p "Enter your Railway app URL (e.g., your-app.railway.app): " RAILWAY_URL
read -p "Enter your Railway API key: " API_KEY
read -p "Enter SIP username (default: agent): " SIP_USER
SIP_USER=${SIP_USER:-agent}

# Update system
echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
echo "📦 Installing Python..."
sudo apt install -y python3 python3-pip python3-venv git ufw

# Create working directory
echo "📁 Creating working directory..."
mkdir -p ~/sip_bridge
cd ~/sip_bridge

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install ESL (Event Socket Library) for FreeSWITCH
pip install --upgrade pip
pip install websockets python-dotenv colorlog requests

# Create configuration
cat > .env << EOF
BACKEND_WS_URL=wss://${RAILWAY_URL}/api/v1/ws/voice
BACKEND_API_KEY=${API_KEY}
SIP_USERNAME=${SIP_USER}
SIP_HOST=0.0.0.0
SIP_PORT=5060
LOG_LEVEL=INFO
EOF

# Configure firewall
echo "🔥 Configuring firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 5060/udp
sudo ufw allow 10000:20000/udp

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

echo ""
echo "✅ Basic setup complete!"
echo ""
echo "📋 Your Configuration:"
echo "   SIP URI: ${SIP_USER}@${SERVER_IP}:5060"
echo "   Backend: wss://${RAILWAY_URL}/api/v1/ws/voice"
echo ""
echo "⚠️  IMPORTANT: You still need to install FreeSWITCH or Asterisk"
echo ""
echo "Choose your SIP server:"
echo "  A) FreeSWITCH (Recommended): ./deploy_freeswitch.sh"
echo "  B) Asterisk: ./deploy_asterisk.sh"
echo ""
echo "Or use a managed service:"
echo "  - Twilio Elastic SIP Trunking"
echo "  - SignalWire"
echo "  - Bandwidth.com"

