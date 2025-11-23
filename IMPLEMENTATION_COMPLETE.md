# Zadarma SIP Bridge - Complete Implementation Guide

## 🎯 Final Architecture

```
┌──────────┐
│  Caller  │
└────┬─────┘
     │ Phone Call
     ↓
┌─────────────────────┐
│ Zadarma Phone Number│
│   +3242833288      │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  Zadarma PBX        │
│  Extension: 100     │
│  Forward to:        │
│  "External Server"  │
└──────────┬──────────┘
           │ SIP INVITE
           ↓
┌─────────────────────┐
│  Your VPS          │
│  IP: 123.45.67.89  │
│  FreeSWITCH         │
│  Port: 5060/UDP     │
└──────────┬──────────┘
           │ WebSocket (wss://)
           ↓
┌─────────────────────┐
│  Railway Backend    │
│  your-app.railway   │
│  WebSocket Handler  │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  Gemini API        │
│  Voice Agent        │
└─────────────────────┘
```

## ✅ What We've Built

### 1. SIP Bridge Components (`/sip_bridge/`)
- **sip_server.py**: Python SIP-to-WebSocket bridge
- **config.py**: Configuration management
- **requirements.txt**: Python dependencies
- **deploy_freeswitch.sh**: Auto-deployment script
- **README.md**: Comprehensive deployment guide

### 2. Backend Simplification
- ✅ Removed automatic PBX API configuration
- ✅ Simplified phone number model
- ✅ SIP URI stored for reference only
- ✅ Manual Zadarma dashboard setup

### 3. Frontend Updates (Needed)
- ✅ SIP URI field (optional, for reference)
- ✅ Clear instructions for manual setup

## 🚀 Deployment Steps

### Step 1: Deploy SIP Bridge (VPS)

**Quick Start**:
```bash
# On your VPS (Ubuntu 22.04)
wget https://your-repo/sip_bridge/deploy_freeswitch.sh
chmod +x deploy_freeswitch.sh
./deploy_freeswitch.sh
```

**Manual Steps**:
1. Create VPS (DigitalOcean, Linode, etc.)
2. Choose Ubuntu 22.04 LTS
3. Minimum: 1GB RAM, 1 CPU
4. Cost: $5-10/month

### Step 2: Configure SIP Bridge

Edit `/opt/sip_bridge/.env`:
```env
BACKEND_WS_URL=wss://your-app.railway.app/api/v1/ws/voice
BACKEND_API_KEY=your_railway_api_key
SIP_USERNAME=agent
SIP_PASSWORD=secure_password_here
```

### Step 3: Start Services

```bash
# Start FreeSWITCH
sudo systemctl start freeswitch
sudo systemctl enable freeswitch

# Verify it's running
sudo systemctl status freeswitch

# Check SIP port
sudo netstat -tulpn | grep 5060
```

### Step 4: Configure Firewall

```bash
# Allow SIP and RTP
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 5060/udp    # SIP
sudo ufw allow 10000:20000/udp  # RTP audio

# Enable firewall
sudo ufw enable
```

### Step 5: Get Your SIP URI

```bash
# Your SIP URI is:
echo "agent@$(curl -s ifconfig.me):5060"
```

Example output: `agent@123.45.67.89:5060`

### Step 6: Configure Zadarma Dashboard

1. **Login** to Zadarma: https://my.zadarma.com
2. Go to **PBX** → **PBX Extensions**
3. Select or create extension (e.g., extension 100)
4. In "Call forwarding to" section:
   - Select **"External server (SIP URI)"**
   - Enter: `agent@YOUR_VPS_IP:5060`
5. Click **Save**

6. **Configure your virtual number**:
   - Go to **PBX** → **Incoming Calls and IVR**
   - Select your phone number
   - Set routing to forward to your extension (100)
   - Save

### Step 7: Add Phone Number in Your App

1. Go to your WeeVoice dashboard
2. Click **"Add Existing Number"**
3. Fill in:
   - **Phone Number**: +3242833288
   - **Country Code**: BE
   - **SIP URI** (optional): `agent@123.45.67.89:5060`
   - **Business Name**: Your Company
4. Click **Add Phone Number**

5. **Assign to Agent**:
   - Click **"Assign Agent"**
   - Select your voice agent
   - Save

### Step 8: Test the Setup

1. **Test WebSocket Connection**:
   ```bash
   cd /opt/sip_bridge
   source venv/bin/activate
   python3 test_connection.py
   ```

2. **Make Test Call**:
   - Call your Zadarma number from your phone
   - You should hear your AI agent

3. **Check Logs**:
   ```bash
   # FreeSWITCH logs
   sudo tail -f /var/log/freeswitch/freeswitch.log
   
   # Railway logs
   railway logs -f
   ```

## 📊 Testing Checklist

- [ ] VPS is accessible via SSH
- [ ] FreeSWITCH is running (`systemctl status freeswitch`)
- [ ] Firewall allows UDP 5060 and 10000-20000
- [ ] WebSocket connection test passes
- [ ] Zadarma PBX extension configured
- [ ] Phone number added in your app
- [ ] Agent assigned to phone number
- [ ] Test call connects
- [ ] Audio flows both directions
- [ ] Call is logged in database
- [ ] Transcript is generated

## 🔧 Troubleshooting

### Problem: "Busy Line" when calling

**Causes**:
1. PBX extension not configured in Zadarma
2. Wrong SIP URI
3. FreeSWITCH not running
4. Firewall blocking port 5060

**Solution**:
```bash
# Check FreeSWITCH
sudo systemctl status freeswitch

# Check SIP port
sudo netstat -tulpn | grep 5060

# Check firewall
sudo ufw status

# Test SIP connectivity from Zadarma
# (Use Zadarma's test call feature)
```

### Problem: Call connects but no audio

**Causes**:
1. RTP ports blocked
2. WebSocket not connecting
3. Wrong audio codec

**Solution**:
```bash
# Open RTP ports
sudo ufw allow 10000:20000/udp

# Test WebSocket
cd /opt/sip_bridge
python3 test_connection.py

# Check FreeSWITCH codec
fs_cli
> sofia status profile internal
```

### Problem: WebSocket connection fails

**Causes**:
1. Wrong Railway URL
2. Invalid API key
3. Railway app not running

**Solution**:
```bash
# Verify Railway URL
curl https://your-app.railway.app/health

# Check .env file
cat /opt/sip_bridge/.env

# Test manually
wscat -c "wss://your-app.railway.app/api/v1/ws/voice/1?api_key=YOUR_KEY"
```

## 💰 Cost Breakdown

| Component | Provider | Cost/Month |
|-----------|----------|-----------|
| VPS | DigitalOcean | $6 |
| VPS | Linode | $5 |
| VPS | Vultr | $5 |
| Zadarma Number | Zadarma | €4.99 |
| **Total (VPS)** | | **~$10-11** |
|  |  |  |
| Alternative: Twilio SIP | Twilio | $1 + usage |
| Alternative: SignalWire | SignalWire | usage only |

## 🔐 Security Best Practices

1. **Use strong SIP password**:
   ```bash
   openssl rand -base64 32
   ```

2. **Whitelist Zadarma IPs only**:
   ```bash
   # Get IPs from Zadarma support
   sudo ufw allow from ZADARMA_IP to any port 5060 proto udp
   ```

3. **Enable fail2ban**:
   ```bash
   sudo apt install fail2ban
   sudo systemctl enable fail2ban
   ```

4. **Use TLS for WebSocket**:
   - Always use `wss://` (not `ws://`)
   - Verify Railway SSL certificate

5. **Regular updates**:
   ```bash
   sudo apt update && sudo apt upgrade
   sudo systemctl restart freeswitch
   ```

## 📚 Additional Resources

### FreeSWITCH
- Official Wiki: https://freeswitch.org/confluence/
- Community: https://freeswitch.org/confluence/display/FREESWITCH/Community
- Troubleshooting: https://freeswitch.org/confluence/display/FREESWITCH/Troubleshooting

### Zadarma
- API Docs: https://zadarma.com/support/api/
- PBX Guide: https://zadarma.com/support/api/pbx/
- Support: support@zadarma.com

### Your Railway App
- Logs: `railway logs -f`
- Environment: `railway vars`
- Deploy: `railway up`

## 🎉 Success Criteria

Your setup is working when:
1. ✅ You call the Zadarma number
2. ✅ FreeSWITCH accepts the SIP call
3. ✅ WebSocket connects to Railway
4. ✅ You hear your AI agent speaking
5. ✅ Your speech is transcribed
6. ✅ AI responds appropriately
7. ✅ Call is logged in database
8. ✅ Transcript is saved

## 🚨 Important Notes

1. **Railway cannot handle SIP directly** - That's why we need a VPS
2. **Manual Zadarma configuration required** - Cannot be done via API
3. **Test thoroughly** before going live
4. **Monitor costs** - VPS + Zadarma + call volume
5. **Backup configs** regularly

## 📞 Support

Need help?
1. Check logs: FreeSWITCH, Railway, Bridge
2. Test each component individually
3. Verify firewall rules
4. Contact Zadarma support for their side
5. Check Railway logs for WebSocket issues

---

**You're all set!** 🎊

Now you can receive calls on your Zadarma number and have them answered by your AI agent running on Railway.

