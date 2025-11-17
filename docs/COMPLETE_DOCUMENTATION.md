# VoiceAgent SaaS - Complete Documentation

**Version:** 1.0.0  
**Last Updated:** October 10, 2025

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Quick Start](#quick-start)
4. [Installation & Setup](#installation--setup)
5. [Architecture](#architecture)
6. [Database](#database)
7. [Features Documentation](#features-documentation)
8. [API Reference](#api-reference)
9. [Deployment](#deployment)
10. [Configuration](#configuration)
11. [Troubleshooting](#troubleshooting)

---

## Overview

VoiceAgent SaaS is a comprehensive platform for creating and managing intelligent French-speaking voice agents powered by Google Gemini 2.5 Flash, LangChain, and LangGraph.

### Key Highlights

- **Ultra-Low Latency**: Real-time voice conversations with <300ms latency
- **Native French Support**: Optimized for French language with natural pronunciation
- **Advanced AI**: Powered by Google Gemini with LangChain/LangGraph integration
- **Complete Backoffice**: Review calls, transcripts, analytics, and summaries
- **CRM Integration**: Built-in webhooks for HubSpot, Salesforce, and custom systems
- **API-First**: RESTful API and WebSocket support
- **Multi-Tenant**: API key-based authentication with usage tracking
- **Comprehensive Billing**: Stripe integration with credit-based system
- **Usage Analytics**: Detailed charts and export capabilities
- **Security Features**: Domain/IP allowlists, security logs
- **Support System**: Complete ticketing system with email notifications

---

## Features

### Core Features

✅ **Voice Agents**
- Create unlimited voice agents
- Customizable system prompts
- Multiple language support (French, English)
- LangGraph integration for complex workflows
- Real-time audio streaming with native audio dialog

✅ **Call Management**
- Real-time call monitoring
- Automatic transcription
- Sentiment analysis
- AI-generated summaries
- Key points extraction
- Call recordings (optional)

✅ **Dashboard & Analytics**
- Modern, professional UI with dark mode
- Real-time statistics
- Usage charts (daily, monthly)
- Agent performance metrics
- Export to CSV

✅ **Billing & Payments**
- Credit-based system (no recurring subscriptions)
- Top-up any amount (minimum $5)
- Stripe integration
- Transaction history
- Invoice generation
- Automatic credit deduction

✅ **Security**
- Domain allowlist with public keys
- IP allowlist for API access control
- Security event logging
- JWT authentication
- API key management

✅ **Support System**
- Public contact form
- Authenticated ticket tracking
- Email notifications
- Multiple categories and priorities
- Staff responses
- Conversation threading

### Technical Features

- **Backend**: FastAPI, SQLAlchemy, Pydantic
- **Frontend**: React, TypeScript, Tailwind CSS, Zustand
- **Database**: PostgreSQL with optimized indexes
- **Real-time**: WebSocket for voice streaming
- **AI**: Google Gemini 2.5 Flash with native audio
- **Payments**: Stripe Payment Intents
- **Email**: SMTP integration for notifications
- **Charts**: Recharts for data visualization
- **UI**: Headless UI, Heroicons, dark mode support

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Google API Key ([Get one here](https://ai.google.dev/))

### 5-Minute Setup

```bash
# 1. Clone repository
git clone <your-repo-url>
cd germini_voice

# 2. Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure .env (already exists, just update values)
# Edit backend/.env:
# - SECRET_KEY: Generate with: python -c "import secrets; print(secrets.token_hex(32))"
# - GOOGLE_API_KEY: Your Google AI API key
# - DATABASE_URL: Your PostgreSQL connection string

# 4. Run backend
python -m uvicorn app.main:app --reload

# 5. Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

Visit:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Installation & Setup

### Option 1: Supabase (Recommended for Quick Setup)

#### Step 1: Create Supabase Project (2 minutes)

1. Go to [https://supabase.com](https://supabase.com)
2. Click "New Project"
3. Fill in project details and save database password
4. Wait for provisioning (~2 minutes)

#### Step 2: Run Database Schema (1 minute)

1. In Supabase dashboard, click "SQL Editor"
2. Create new query
3. Copy contents of `database/complete_schema.sql`
4. Paste and click "Run"

#### Step 3: Get Connection String (1 minute)

1. Go to Settings → Database
2. Copy URI connection string
3. Replace `[YOUR-PASSWORD]` with your actual password

```
postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```

#### Step 4: Configure Backend (1 minute)

Create/edit `backend/.env`:

```env
# Database
DATABASE_URL=postgresql://postgres:your-password@db.xxxxx.supabase.co:5432/postgres

# Google Gemini API
GOOGLE_API_KEY=your-google-api-key-here

# Security
SECRET_KEY=your-secret-key-here
DEBUG=True

# Optional: Stripe (for billing)
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Optional: SMTP (for support emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@voiceagent.ai
SUPPORT_EMAIL=support@voiceagent.ai
```

#### Step 5: Start Application

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

### Option 2: Local PostgreSQL

```bash
# 1. Create database
createdb voiceagent_db

# 2. Run schema
psql -d voiceagent_db -f database/complete_schema.sql

# 3. Update .env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/voiceagent_db

# 4. Start application (same as above)
```

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   React UI   │  │  WebSocket   │  │   HTTP API   │      │
│  │   (Vite)     │  │   Client     │  │   (Axios)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                       Backend Layer                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              FastAPI Application                       │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │   │
│  │  │  REST API  │  │ WebSocket  │  │   Auth     │     │   │
│  │  │  Endpoints │  │   Server   │  │  (JWT)     │     │   │
│  │  └────────────┘  └────────────┘  └────────────┘     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Service Layer                             │   │
│  │  ┌─────────────────┐  ┌──────────────────┐           │   │
│  │  │ Agent Service   │  │  CRM Service     │           │   │
│  │  │ - Voice Stream  │  │  - Webhooks      │           │   │
│  │  │ - LangChain     │  │  - Integrations  │           │   │
│  │  │ - LangGraph     │  │                  │           │   │
│  │  └─────────────────┘  └──────────────────┘           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
┌──────────────────┐ ┌────────────┐ ┌────────────────┐
│   PostgreSQL     │ │   Redis    │ │ Google Gemini  │
│   - Users        │ │   - Cache  │ │ - Voice AI     │
│   - Agents       │ │   - Queue  │ │ - Native Audio │
│   - Calls        │ │   - State  │ │ - Streaming    │
│   - Billing      │ │            │ │                │
└──────────────────┘ └────────────┘ └────────────────┘
```

### Technology Stack

**Backend:**
- FastAPI - High-performance async web framework
- SQLAlchemy - ORM for database operations
- Pydantic - Data validation
- Google Generative AI - Gemini integration
- LangChain/LangGraph - AI orchestration
- Stripe - Payment processing
- SMTP - Email notifications

**Frontend:**
- React 18 - UI framework
- TypeScript - Type safety
- Vite - Build tool
- Tailwind CSS - Styling
- Zustand - State management
- React Router - Navigation
- Recharts - Data visualization
- Headless UI - Accessible components

**Database:**
- PostgreSQL 15+ - Primary database
- Redis - Caching and real-time features

---

## Database

### Tables Overview

#### Core Tables

1. **users**
   - User accounts and authentication
   - Subscription tiers
   - Credit balance
   - Usage tracking

2. **api_keys**
   - API key management
   - Usage tracking
   - Expiration

3. **voice_agents**
   - Agent configurations
   - System prompts
   - Model settings
   - CRM integration

4. **calls**
   - Call history
   - Transcripts
   - Sentiment analysis
   - Cost tracking

5. **call_messages**
   - Individual messages within calls
   - Role (user/assistant)
   - Audio URLs

#### Billing Tables

6. **transactions**
   - Payment history
   - Stripe integration
   - Transaction status

7. **invoices**
   - Invoice generation
   - Billing periods
   - PDF downloads

8. **usage_records**
   - Detailed usage tracking
   - Per-call metrics
   - Monthly aggregation

#### Security Tables

9. **domain_allowlists**
   - Allowed domains
   - Public keys for ChatKit
   - Verification status

10. **ip_allowlists**
    - IP restrictions
    - CIDR notation support
    - Usage tracking

11. **security_logs**
    - Security events
    - Audit trail
    - Severity levels

#### Support Tables

12. **support_tickets**
    - User support requests
    - Ticket numbers
    - Categories and priorities
    - Status tracking

13. **ticket_responses**
    - Ticket conversation thread
    - User and staff responses
    - Timestamps

### Database Schema Location

All database tables are defined in: `database/complete_schema.sql`

To apply the schema:
```sql
-- For Supabase: Run in SQL Editor
-- For local PostgreSQL:
psql -d voiceagent_db -f database/complete_schema.sql
```

---

## Features Documentation

### 1. Billing System

#### Credit-Based Model

- No recurring subscriptions
- Top up any amount (minimum $5)
- Pay-as-you-go model
- Automatic credit deduction per call

#### Features

- View credit balance
- Top-up credits via Stripe
- Transaction history
- Invoice generation (optional)
- Export transaction data

#### API Endpoints

```
GET  /api/v1/billing/credit-balance
POST /api/v1/billing/top-up-credits
GET  /api/v1/billing/transactions
GET  /api/v1/billing/invoices
POST /api/v1/billing/create-payment-intent
```

#### Stripe Configuration

**⚠️ Important:** To enable credit top-ups and billing features, you MUST configure Stripe.

**Quick Setup:**
1. Get your Stripe API key from: https://dashboard.stripe.com/test/apikeys
2. Add to `backend/.env`:
   ```env
   STRIPE_API_KEY=sk_test_your_key_here
   STRIPE_WEBHOOK_SECRET=whsec_your_secret_here
   ```
3. For local development, run Stripe webhook forwarding:
   ```bash
   stripe listen --forward-to localhost:8000/api/v1/billing/webhook
   ```

**📖 Detailed Setup Guide:** See [STRIPE_SETUP_GUIDE.md](STRIPE_SETUP_GUIDE.md) for complete instructions.

Required environment variables:
```env
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

**Test Card Numbers:**
- Success: `4242 4242 4242 4242`
- Declined: `4000 0000 0000 0002`

### 2. Usage Tracking & Analytics

#### Features

- Real-time usage monitoring
- Daily and monthly charts
- Usage by agent breakdown
- Export to CSV
- Cost tracking

#### Metrics

- Total minutes used
- Total cost
- Number of calls
- Average call duration
- Peak usage times
- Agent performance

#### API Endpoints

```
GET /api/v1/usage/summary
GET /api/v1/usage/by-month?months=12
GET /api/v1/usage/by-day?days=30
GET /api/v1/usage/by-agent
GET /api/v1/usage/export
```

### 3. Security Features

#### Domain Allowlist

- Add trusted domains
- Generate public keys for ChatKit
- Domain verification
- Request tracking

#### IP Allowlist

- Restrict API access by IP
- CIDR notation support
- IPv4 and IPv6
- Automatic blocking

#### Security Logs

- All security events logged
- Severity levels (info, warning, critical)
- IP address tracking
- Audit trail

#### API Endpoints

```
# Domain Allowlist
GET  /api/v1/security/domains
POST /api/v1/security/domains
PUT  /api/v1/security/domains/{id}
DELETE /api/v1/security/domains/{id}
POST /api/v1/security/domains/{id}/regenerate-key

# IP Allowlist
GET  /api/v1/security/ips
POST /api/v1/security/ips
PUT  /api/v1/security/ips/{id}
DELETE /api/v1/security/ips/{id}

# Security Logs
GET /api/v1/security/logs
```

### 4. Support System

#### Features

- Public contact form (no authentication required)
- Authenticated ticket tracking
- Email notifications (user + support team)
- Multiple categories
- Priority levels
- Status tracking
- Conversation threading

#### Ticket Categories

- Technical Issue
- Billing Question
- General Inquiry
- Feature Request
- Bug Report

#### Ticket Priorities

- Low
- Medium
- High
- Urgent

#### Ticket Status

- Open
- In Progress
- Resolved
- Closed

#### API Endpoints

```
POST /api/v1/support/tickets
GET  /api/v1/support/tickets
GET  /api/v1/support/tickets/{ticket_number}
POST /api/v1/support/tickets/{ticket_number}/responses
GET  /api/v1/support/categories
```

#### Email Configuration

Required environment variables:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@voiceagent.ai
SMTP_FROM_NAME=VoiceAgent Support
SMTP_USE_TLS=true
SUPPORT_EMAIL=support@voiceagent.ai
```

**Note:** If SMTP is not configured, emails are logged to console (development mode).

### 5. Theme Switching

#### Features

- Light mode
- Dark mode
- System preference (auto)
- Persistent across sessions
- Smooth transitions
- FOUC prevention

#### Usage

Theme selector available in:
- Profile page
- Landing page header
- All authenticated pages

Theme is stored in localStorage and applied before React renders.

### 6. Profile Management

#### Features

- View/edit profile information
- Change password
- View account statistics
- Theme preferences
- Delete account (with confirmation)

#### API Endpoints

```
GET    /api/v1/profile/me
PUT    /api/v1/profile/me
POST   /api/v1/profile/change-password
GET    /api/v1/profile/stats
DELETE /api/v1/profile/me
```

---

## API Reference

### Authentication

All authenticated endpoints require a Bearer token:

```bash
Authorization: Bearer <jwt_token>
```

Or API key in header:

```bash
X-API-Key: <your_api_key>
```

### Core Endpoints

#### Auth

```
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/api-keys
GET  /api/v1/auth/api-keys
DELETE /api/v1/auth/api-keys/{id}
```

#### Agents

```
GET    /api/v1/agents
POST   /api/v1/agents
GET    /api/v1/agents/{id}
PUT    /api/v1/agents/{id}
DELETE /api/v1/agents/{id}
GET    /api/v1/agents/public/demo
```

#### Calls

```
GET    /api/v1/calls
GET    /api/v1/calls/{id}
GET    /api/v1/calls/{id}/transcript
POST   /api/v1/calls/{id}/generate-summary
DELETE /api/v1/calls/{id}
GET    /api/v1/calls/stats/overview
```

#### WebSocket

```
WS /api/v1/ws/voice/{agent_id}?token={jwt_token}
WS /api/v1/ws/voice/{agent_id}?api_key={api_key}
```

### Complete API Documentation

Full interactive API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Deployment

### Pre-Deployment Checklist

- [ ] Domain name registered and DNS configured
- [ ] SSL certificate obtained (Let's Encrypt recommended)
- [ ] Google Cloud API key with production quota
- [ ] PostgreSQL database provisioned
- [ ] Environment variables configured
- [ ] Backup strategy implemented
- [ ] Monitoring tools set up

### Production Environment Variables

```env
# Application
DEBUG=False
SECRET_KEY=<strong-secret-key>
ALLOWED_ORIGINS=https://yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Google Gemini
GOOGLE_API_KEY=<your-production-key>

# Stripe
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@yourdomain.com
SMTP_PASSWORD=<app-password>
SMTP_FROM_EMAIL=noreply@yourdomain.com
SUPPORT_EMAIL=support@yourdomain.com

# Monitoring (optional)
SENTRY_DSN=<your-sentry-dsn>
```

### Deployment Options

#### Option 1: Railway (Easiest)

1. Push code to GitHub
2. Connect Railway to your repo
3. Add PostgreSQL database
4. Configure environment variables
5. Deploy

#### Option 2: Vercel (Frontend) + Railway (Backend)

**Frontend (Vercel):**
```bash
cd frontend
npm run build
vercel deploy
```

**Backend (Railway):**
- Deploy from GitHub
- Add PostgreSQL
- Configure environment

#### Option 3: Docker Compose

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### Option 4: Manual VPS

```bash
# 1. Setup server (Ubuntu 22.04)
sudo apt update
sudo apt install python3.11 postgresql nginx certbot

# 2. Clone repository
git clone <repo-url>
cd germini_voice

# 3. Setup backend
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Setup systemd service
sudo cp deploy/voiceagent.service /etc/systemd/system/
sudo systemctl enable voiceagent
sudo systemctl start voiceagent

# 5. Setup Nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/voiceagent
sudo ln -s /etc/nginx/sites-available/voiceagent /etc/nginx/sites-enabled/
sudo systemctl restart nginx

# 6. SSL with Certbot
sudo certbot --nginx -d yourdomain.com
```

### Post-Deployment

1. Test all endpoints
2. Monitor logs for errors
3. Setup database backups
4. Configure monitoring (Sentry, DataDog, etc.)
5. Setup uptime monitoring
6. Load testing
7. Security audit

---

## Configuration

### Backend Configuration (backend/.env)

```env
# Required
SECRET_KEY=<generate-with-python-secrets>
DEBUG=True
DATABASE_URL=postgresql://...
GOOGLE_API_KEY=<your-key>

# Optional but recommended
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Optional
REDIS_URL=redis://localhost:6379
SENTRY_DSN=<your-sentry-dsn>
LOG_LEVEL=INFO

# SMTP (for support emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=<app-password>
SMTP_FROM_EMAIL=noreply@voiceagent.ai
SMTP_FROM_NAME=VoiceAgent Support
SMTP_USE_TLS=true
SUPPORT_EMAIL=support@voiceagent.ai

# CORS
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Frontend Configuration (frontend/.env)

```env
VITE_API_URL=http://localhost:8000
```

### Generate Secret Key

```python
import secrets
print(secrets.token_hex(32))
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Problem:** `could not connect to server`

**Solution:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -d voiceagent_db -U postgres

# Check connection string format
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

#### 2. Gemini API Errors

**Problem:** `API key not found` or `Quota exceeded`

**Solution:**
- Verify API key in .env
- Check quota at https://ai.google.dev/
- Ensure billing is enabled

#### 3. WebSocket Connection Failed

**Problem:** WebSocket fails to connect

**Solution:**
- Check CORS settings
- Verify WebSocket URL format
- Check firewall rules
- Test with: `wscat -c ws://localhost:8000/api/v1/ws/voice/1?token=...`

#### 4. Frontend Build Errors

**Problem:** `Module not found` or build fails

**Solution:**
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Vite cache
rm -rf .vite

# Rebuild
npm run build
```

#### 5. Stripe Webhook Issues

**Problem:** Webhooks not received

**Solution:**
- Use Stripe CLI for testing: `stripe listen --forward-to localhost:8000/webhooks/stripe`
- Verify webhook secret in .env
- Check endpoint configuration in Stripe dashboard

#### 6. Email Not Sending

**Problem:** Support emails not being sent

**Solution:**
- Check SMTP credentials
- For Gmail, use App Password (not regular password)
- Verify SMTP_USE_TLS is set correctly
- Check logs for SMTP errors
- In development, emails are logged to console

### Debug Mode

Enable detailed logging:

```env
DEBUG=True
LOG_LEVEL=DEBUG
```

View logs:
```bash
# Backend
tail -f backend/logs/app.log

# Frontend (browser console)
# Open DevTools → Console
```

### Performance Issues

#### Slow API Responses

1. Add database indexes (check `complete_schema.sql`)
2. Enable query logging to find slow queries
3. Add Redis caching
4. Scale database

#### High Memory Usage

1. Check for memory leaks in WebSocket connections
2. Limit concurrent connections
3. Add connection pooling
4. Monitor with: `htop` or `docker stats`

### Getting Help

1. **Documentation**: Check this file first
2. **API Docs**: http://localhost:8000/docs
3. **GitHub Issues**: Report bugs and feature requests
4. **Discord/Slack**: Community support (if available)
5. **Email**: support@voiceagent.ai

---

## Support & Contributing

### Report Issues

Please report issues with:
- Clear description
- Steps to reproduce
- Expected vs actual behavior
- System information
- Relevant logs

### Feature Requests

Submit feature requests via GitHub Issues with:
- Use case description
- Proposed solution
- Alternative solutions considered

### Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

---

## License

[Your License Here]

---

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/)
- [Google Gemini](https://ai.google.dev/)
- [LangChain](https://www.langchain.com/)
- [Stripe](https://stripe.com/)
- [Supabase](https://supabase.com/)
- [Tailwind CSS](https://tailwindcss.com/)

---

**Last Updated:** October 10, 2025  
**Documentation Version:** 1.0.0

