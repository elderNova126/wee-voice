# WeeVoice VPS Deployment Guide

Deploy Asterisk, Backend, and Frontend on a single VPS.

## Prerequisites

- Ubuntu 20.04/22.04 VPS with at least 4GB RAM, 2 vCPU
- Domain name pointing to your VPS IP
- Asterisk already installed (or will be installed)

## Quick Start

### 1. Clone the repository

```bash
cd /opt
git clone https://github.com/your-repo/wee-voice.git
cd wee-voice/deploy
```

### 2. Run the deployment script

```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

### 3. Configure Asterisk

Update `/etc/asterisk/extensions.conf`:

```ini
[zadarma]
exten => _.,1,NoOp(Incoming call: ${CALLERID(num)} -> ${EXTEN})
same => n,Answer()
same => n,Wait(1)
same => n,Set(CALL_UUID=${SHELL(cat /proc/sys/kernel/random/uuid | tr -d '\n')})
same => n,AudioSocket(${CALL_UUID},127.0.0.1:9092)
same => n,Hangup()

exten => h,1,NoOp(Call ended)
```

Reload dialplan:
```bash
asterisk -rx "dialplan reload"
```

## Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                        VPS                               │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐  │
│  │  Nginx   │───►│ Frontend │    │    Asterisk      │  │
│  │  :80/443 │    │  :3000   │    │  :4783 (SIP)     │  │
│  └────┬─────┘    └──────────┘    │  :8089 (WSS)     │  │
│       │                          └────────┬─────────┘  │
│       ▼                                   │            │
│  ┌──────────┐                             │            │
│  │ Backend  │◄────────────────────────────┘            │
│  │  :8000   │     AudioSocket :9092                    │
│  └────┬─────┘                                          │
│       │                                                │
│       ▼                                                │
│  ┌──────────┐                                          │
│  │ Gemini   │ (External API)                           │
│  │   AI     │                                          │
│  └──────────┘                                          │
└─────────────────────────────────────────────────────────┘
```

## Ports

| Service | Port | Public |
|---------|------|--------|
| Nginx HTTP | 80 | Yes |
| Nginx HTTPS | 443 | Yes |
| Backend API | 8000 | No (via Nginx) |
| Frontend | 3000 | No (via Nginx) |
| Asterisk SIP | 4783 | Yes |
| Asterisk WSS | 8089 | Yes |
| AudioSocket | 9092 | No (localhost) |

## Firewall Rules

```bash
# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Allow SIP
ufw allow 4783/udp

# Allow WebSocket SIP
ufw allow 8089/tcp

# Allow RTP (for WebRTC clients)
ufw allow 10000:20000/udp
```

## Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# Asterisk logs
tail -f /var/log/asterisk/messages
```

## Troubleshooting

### AudioSocket connection failed

1. Check if backend is running:
   ```bash
   docker-compose ps
   ```

2. Check if port 9092 is listening:
   ```bash
   netstat -tlnp | grep 9092
   ```

3. Check backend logs:
   ```bash
   docker-compose logs backend | grep AudioSocket
   ```

### Calls not connecting

1. Check Asterisk dialplan:
   ```bash
   asterisk -rx "dialplan show zadarma"
   ```

2. Check PJSIP endpoints:
   ```bash
   asterisk -rx "pjsip show endpoints"
   ```

### SSL certificate issues

Renew certificate:
```bash
certbot renew
docker-compose restart nginx
```

## Deployment without Docker

Use the `deploy-no-docker.sh` script for a traditional deployment:

```bash
chmod +x deploy-no-docker.sh
sudo ./deploy-no-docker.sh
```

This will:
1. Install Python 3.11, Node.js 18, Nginx
2. Set up the backend with virtualenv
3. Build the frontend
4. Configure Supervisor to manage processes
5. Set up Nginx as reverse proxy
6. Get SSL certificate via Let's Encrypt

### Service Management (No Docker)

```bash
# Check status
supervisorctl status

# Restart services
supervisorctl restart weevoice-backend
supervisorctl restart weevoice-frontend

# View logs
tail -f /var/log/weevoice/backend.out.log
tail -f /var/log/weevoice/frontend.out.log
```

### Manual Setup (Step by Step)

#### Backend

```bash
cd /opt/weevoice/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file with your settings
# Then run:
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

#### Frontend

```bash
cd /opt/weevoice/frontend
npm ci
npm run build
npm start
```

#### Nginx Config

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
    }
}
```

