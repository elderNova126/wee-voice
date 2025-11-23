# SIP Bridge Deployment Guide

## Overview

This SIP bridge accepts incoming SIP calls from Zadarma and forwards audio to your Railway WebSocket backend.

## Architecture

```
[Caller] 
   ↓
[Zadarma Virtual Phone Number]
   ↓
[Zadarma PBX] - "External Server (SIP URI)"
   ↓ SIP INVITE
[Your VPS - FreeSWITCH/Asterisk]
   ↓ WebSocket
[Railway Backend - Your App]
   ↓
[Gemini API]
```

## Deployment Options

### Option 1: FreeSWITCH (Recommended)
**Best for**: Production use, feature-rich, reliable

```bash
# Run deployment script
chmod +x deploy_freeswitch.sh
./deploy_freeswitch.sh
```

**Requirements**:
- Ubuntu 22.04 LTS VPS
- 1 GB RAM minimum
- Public IP address
- Ports: 5060/UDP, 10000-20000/UDP

**Cost**: ~$5-10/month (DigitalOcean, Linode, Vultr)

### Option 2: Asterisk
**Best for**: Enterprise features, mature ecosystem

```bash
# Install Asterisk
sudo apt update
sudo apt install asterisk asterisk-modules

# Configure (see ASTERISK_CONFIG.md)
```

### Option 3: Managed SIP Service (Easiest)
**Best for**: Quick setup, no VPS management

Use a managed SIP service that forwards to WebSocket:

1. **Twilio Elastic SIP Trunking** ($1/month + usage)
   - Configure SIP trunk
   - Forward to TwiML app
   - TwiML app connects to your WebSocket

2. **SignalWire** (Similar to Twilio)
   - Full SIP stack
   - WebSocket forwarding
   - Good for scalability

3. **Bandwidth.com**
   - Enterprise-grade
   - SIP-to-WebSocket bridge
   - Great pricing

## Quick Start (FreeSWITCH)

### 1. Create VPS

**DigitalOcean**:
```bash
# Create droplet
- Ubuntu 22.04 LTS
- Basic ($6/month)
- Choose datacenter near you
```

**Linode**:
```bash
# Create Linode
- Ubuntu 22.04 LTS
- Nanode 1GB ($5/month)
```

### 2. Deploy

```bash
# SSH into your VPS
ssh root@your-vps-ip

# Create user (if root)
adduser sipbridge
usermod -aG sudo sipbridge
su - sipbridge

# Clone your repo or download scripts
wget https://your-repo/deploy_freeswitch.sh
chmod +x deploy_freeswitch.sh

# Run deployment
./deploy_freeswitch.sh
```

### 3. Configure

Edit `/opt/sip_bridge/.env`:

```env
BACKEND_WS_URL=wss://your-app.railway.app/api/v1/ws/voice
BACKEND_API_KEY=your_railway_api_key
SIP_USERNAME=agent
```

### 4. Start FreeSWITCH

```bash
sudo systemctl start freeswitch
sudo systemctl enable freeswitch
sudo systemctl status freeswitch
```

### 5. Test Connection

```bash
cd /opt/sip_bridge
source venv/bin/activate
python3 test_connection.py
```

Expected output:
```
✅ Successfully connected to Railway WebSocket
✅ Sent test audio
✅ Received response
```

### 6. Get Your SIP URI

```bash
# Your SIP URI is:
echo "agent@$(curl -s ifconfig.me):5060"
```

Example: `agent@123.45.67.89:5060`

### 7. Configure Zadarma

1. Go to Zadarma Dashboard → PBX
2. Select your PBX extension
3. Set "Call forwarding to" → "External server (SIP URI)"
4. Enter your SIP URI: `agent@YOUR_VPS_IP:5060`
5. Save

### 8. Test Call

1. Call your Zadarma virtual number
2. Check logs:
   ```bash
   # FreeSWITCH logs
   sudo tail -f /var/log/freeswitch/freeswitch.log
   
   # Bridge logs
   tail -f /opt/sip_bridge/bridge.log
   
   # Railway logs
   railway logs
   ```

## Firewall Configuration

### Required Ports

```bash
# SIP signaling
sudo ufw allow 5060/udp

# RTP media (audio)
sudo ufw allow 10000:20000/udp

# SSH (don't forget!)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

### Zadarma IP Whitelist

Add Zadarma IP ranges (get from Zadarma support):

```bash
# Example (replace with actual Zadarma IPs)
sudo ufw allow from 185.45.152.0/24 to any port 5060 proto udp
sudo ufw allow from 185.45.153.0/24 to any port 5060 proto udp
```

## Troubleshooting

### SIP Connection Issues

**Problem**: "Busy line" or "Not reachable"

**Solutions**:
```bash
# 1. Check FreeSWITCH is running
sudo systemctl status freeswitch

# 2. Check port is open
sudo netstat -tulpn | grep 5060

# 3. Check firewall
sudo ufw status

# 4. Test SIP registration
fs_cli -x "sofia status"
```

### Audio Issues

**Problem**: Call connects but no audio

**Solutions**:
```bash
# 1. Check RTP ports
sudo ufw allow 10000:20000/udp

# 2. Check Railway WebSocket connection
tail -f /opt/sip_bridge/bridge.log

# 3. Test Railway app
curl https://your-app.railway.app/health
```

### WebSocket Connection Issues

**Problem**: Bridge can't connect to Railway

**Solutions**:
```bash
# 1. Verify Railway URL
echo $BACKEND_WS_URL

# 2. Test WebSocket
python3 test_connection.py

# 3. Check Railway logs
railway logs
```

## Monitoring

### FreeSWITCH Status

```bash
# CLI
fs_cli

# Commands
> status
> sofia status
> show calls
> show channels
```

### Bridge Status

```bash
# Check bridge is running
ps aux | grep bridge

# View logs
tail -f /opt/sip_bridge/bridge.log

# Check WebSocket connection
python3 -c "from config import *; print(BACKEND_WS_URL)"
```

### Railway App

```bash
# View logs
railway logs -f

# Check WebSocket connections
railway logs | grep WebSocket
```

## Maintenance

### Update FreeSWITCH

```bash
sudo apt update
sudo apt upgrade freeswitch-meta-all
sudo systemctl restart freeswitch
```

### Update Bridge

```bash
cd /opt/sip_bridge
source venv/bin/activate
pip install --upgrade websockets
```

### Backup Configuration

```bash
# Backup FreeSWITCH config
sudo tar -czf freeswitch-backup-$(date +%Y%m%d).tar.gz /etc/freeswitch/

# Backup bridge config
tar -czf bridge-backup-$(date +%Y%m%d).tar.gz /opt/sip_bridge/.env
```

## Cost Breakdown

### VPS Hosting
- **DigitalOcean**: $6/month (Basic droplet)
- **Linode**: $5/month (Nanode 1GB)
- **Vultr**: $5/month (Regular Performance)

### Alternative: Managed SIP
- **Twilio**: $1/month + $0.0085/min
- **SignalWire**: $0.008/min
- **Bandwidth**: $0.005/min

### Total Monthly Cost
- **DIY (VPS)**: $5-10/month + electricity
- **Managed**: $10-50/month depending on call volume

## Security

### Recommendations

1. **Use strong SIP passwords**
   ```bash
   # Generate secure password
   openssl rand -base64 32
   ```

2. **Limit SIP access to Zadarma IPs only**
   ```bash
   sudo ufw deny 5060/udp
   sudo ufw allow from ZADARMA_IP to any port 5060 proto udp
   ```

3. **Enable fail2ban**
   ```bash
   sudo apt install fail2ban
   sudo systemctl enable fail2ban
   ```

4. **Use SSL/TLS for WebSocket**
   - Ensure Railway URL uses `wss://` (not `ws://`)

5. **Monitor logs for suspicious activity**
   ```bash
   sudo tail -f /var/log/freeswitch/freeswitch.log | grep INVITE
   ```

## Next Steps

1. ✅ Deploy FreeSWITCH on VPS
2. ✅ Configure connection to Railway
3. ✅ Test SIP connectivity
4. ✅ Configure Zadarma PBX
5. ✅ Make test call
6. ✅ Monitor and optimize

Need help? Check:
- FreeSWITCH Wiki: https://freeswitch.org/confluence/
- Zadarma API Docs: https://zadarma.com/support/api/
- Your Railway logs: `railway logs`

