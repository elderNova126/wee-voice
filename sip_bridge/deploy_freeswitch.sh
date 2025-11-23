#!/bin/bash
# FreeSWITCH SIP Bridge Deployment Script
# Deploys FreeSWITCH on Ubuntu 22.04 LTS

set -e

echo "🚀 Deploying FreeSWITCH SIP Bridge..."

# Update system
echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt install -y \
    wget \
    gnupg2 \
    software-properties-common \
    python3 \
    python3-pip \
    python3-venv \
    git \
    ufw

# Install FreeSWITCH
echo "📦 Installing FreeSWITCH..."
wget --http-user=signalwire --http-password=pat_f9Z9PkDznjsqNBxW5Q5e6nYQ \
    -O /usr/share/keyrings/signalwire-freeswitch-repo.gpg \
    https://freeswitch.signalwire.com/repo/deb/debian-release/signalwire-freeswitch-repo.gpg

echo "machine freeswitch.signalwire.com login signalwire password pat_f9Z9PkDznjsqNBxW5Q5e6nYQ" > /etc/apt/auth.conf
chmod 600 /etc/apt/auth.conf

echo "deb [signed-by=/usr/share/keyrings/signalwire-freeswitch-repo.gpg] https://freeswitch.signalwire.com/repo/deb/debian-release/ `lsb_release -sc` main" > /etc/apt/sources.list.d/freeswitch.list

sudo apt update
sudo apt install -y freeswitch-meta-all

# Configure firewall
echo "🔥 Configuring firewall..."
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 5060/udp    # SIP
sudo ufw allow 5080/udp    # SIP alternate
sudo ufw allow 10000:20000/udp  # RTP

# Don't enable UFW automatically in case of SSH lockout
echo "⚠️  Firewall rules configured but not enabled"
echo "⚠️  Run 'sudo ufw enable' after verifying SSH access"

# Create Python virtual environment
echo "🐍 Setting up Python environment..."
cd /opt
sudo mkdir -p sip_bridge
sudo chown $(whoami):$(whoami) sip_bridge
cd sip_bridge

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Install Python dependencies
cat > requirements.txt << 'EOF'
websockets==12.0
python-dotenv==1.0.0
aiofiles==23.2.1
colorlog==6.8.0
numpy==1.24.3
requests==2.31.0
EOF

pip install -r requirements.txt

# Create configuration file
echo "⚙️  Creating configuration..."
cat > .env << 'EOF'
# SIP Bridge Configuration

# FreeSWITCH Configuration
SIP_HOST=0.0.0.0
SIP_PORT=5060
SIP_USERNAME=agent
SIP_PASSWORD=

# Railway Backend
BACKEND_WS_URL=wss://your-app.railway.app/api/v1/ws/voice
BACKEND_API_KEY=your_api_key_here

# Logging
LOG_LEVEL=INFO
EOF

echo "✅ FreeSWITCH SIP Bridge deployed!"
echo ""
echo "📝 Next steps:"
echo "1. Edit /opt/sip_bridge/.env with your Railway app URL and API key"
echo "2. Configure FreeSWITCH (see FREESWITCH_CONFIG.md)"
echo "3. Enable firewall: sudo ufw enable"
echo "4. Start FreeSWITCH: sudo systemctl start freeswitch"
echo "5. Test connection: python3 test_connection.py"
echo ""
echo "🌐 Your SIP URI will be: agent@YOUR_VPS_IP:5060"

