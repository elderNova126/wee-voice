#!/bin/bash

# WeeVoice Deployment Script
# Run this on your VPS to deploy all services

set -e

echo "============================================"
echo "  WeeVoice Deployment Script"
echo "============================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./deploy.sh)"
    exit 1
fi

# Get domain name
read -p "Enter your domain name (e.g., voice.example.com): " DOMAIN
read -p "Enter your Google API Key: " GOOGLE_API_KEY
read -p "Enter your OpenAI API Key (optional, press Enter to skip): " OPENAI_API_KEY

# Generate secret key
SECRET_KEY=$(openssl rand -hex 32)

echo ""
echo "Installing dependencies..."

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Install certbot for SSL
apt-get update
apt-get install -y certbot

echo ""
echo "Getting SSL certificate..."

# Get SSL certificate
certbot certonly --standalone -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || true

# Create .env file
cat > .env << EOF
DOMAIN=$DOMAIN
GOOGLE_API_KEY=$GOOGLE_API_KEY
OPENAI_API_KEY=$OPENAI_API_KEY
SECRET_KEY=$SECRET_KEY
EOF

# Update nginx.conf with domain
sed -i "s/YOUR_DOMAIN/$DOMAIN/g" nginx.conf

echo ""
echo "Building and starting services..."

# Build and start
docker-compose up -d --build

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
echo "Make sure your Asterisk extensions.conf uses:"
echo "  AudioSocket(\${CALL_UUID},127.0.0.1:9092)"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""

