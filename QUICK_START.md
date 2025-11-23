# 🚀 Quick Start Guide

## What You Need

1. **VPS** (Virtual Private Server)
   - Ubuntu 22.04 LTS
   - 1GB RAM minimum
   - Public IP address
   - Cost: $5-10/month
   - Providers: DigitalOcean, Linode, Vultr

2. **Zadarma Account**
   - Virtual phone number
   - PBX access
   - API credentials (optional)

3. **Railway App** (Your existing app)
   - Already deployed and working
   - WebSocket endpoint ready

## 5-Minute Setup

### 1. Create VPS

**DigitalOcean**:
```bash
# Go to: digitalocean.com
# Click: Create → Droplets
# Choose: Basic ($6/month)
# OS: Ubuntu 22.04 LTS
# Create Droplet
```

**Get your VPS IP**: `123.45.67.89` (example)

### 2. Deploy FreeSWITCH

```bash
# SSH into your VPS
ssh root@YOUR_VPS_IP

# Run one-command deployment
curl -sSL https://raw.githubusercontent.com/YOUR_REPO/main/sip_bridge/deploy_freeswitch.sh | bash
```

### 3. Configure

```bash
# Edit configuration
nano /opt/sip_bridge/.env

# Set your Railway URL and API key:
BACKEND_WS_URL=wss://your-app.railway.app/api/v1/ws/voice
BACKEND_API_KEY=your_api_key

# Save and exit (Ctrl+X, Y, Enter)
```

### 4. Test Connection

```bash
cd /opt/sip_bridge
source venv/bin/activate
python3 test_connection.py
```

Expected output:
```
✅ Connected successfully!
✅ Test audio sent
✅ Received response
🎉 CONNECTION TEST PASSED!
```

### 5. Get Your SIP URI

```bash
echo "agent@$(curl -s ifconfig.me):5060"
```

Copy this! Example: `agent@123.45.67.89:5060`

### 6. Configure Zadarma

1. Login: https://my.zadarma.com
2. Go to: **PBX** → **PBX Extensions**
3. Select extension (e.g., 100)
4. Set "Call forwarding to":
   - Type: **External server (SIP URI)**
   - Value: `agent@YOUR_VPS_IP:5060`
5. Save

6. Configure incoming calls:
   - Go to: **PBX** → **Incoming Calls and IVR**
   - Select your phone number
   - Forward to: Extension 100
   - Save

### 7. Add Number in Your App

1. Go to: your-app.railway.app/dashboard/phone-numbers
2. Click: **Add Existing Number**
3. Enter:
   - Phone: +3242833288
   - Country: BE
   - SIP URI: `agent@123.45.67.89:5060` (optional)
4. Click: **Add Phone Number**
5. Click: **Assign Agent** → Select your agent

### 8. Test!

Call your Zadarma number: `+3242833288`

You should hear your AI agent! 🎉

## Troubleshooting

### "Busy Line"

```bash
# Check FreeSWITCH is running
sudo systemctl status freeswitch

# Check SIP port
sudo netstat -tulpn | grep 5060

# If not running
sudo systemctl start freeswitch
```

### No Audio

```bash
# Open RTP ports
sudo ufw allow 10000:20000/udp

# Restart FreeSWITCH
sudo systemctl restart freeswitch
```

### WebSocket Error

```bash
# Check Railway is running
curl https://your-app.railway.app/health

# View logs
railway logs -f
```

## Next Steps

- ✅ Monitor calls in dashboard
- ✅ Check call logs
- ✅ Review transcripts
- ✅ Adjust agent prompts

## Need Help?

1. Check logs:
   ```bash
   # FreeSWITCH
   sudo tail -f /var/log/freeswitch/freeswitch.log
   
   # Railway
   railway logs -f
   ```

2. Read full docs: `IMPLEMENTATION_COMPLETE.md`

3. Test connection: `python3 test_connection.py`

---

**That's it!** Your SIP bridge is ready. 🎊

