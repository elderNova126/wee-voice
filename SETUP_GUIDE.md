# VoiceAgent SaaS - Complete Setup Guide

This guide will walk you through setting up the VoiceAgent SaaS platform from scratch.

## Prerequisites

Before you begin, ensure you have:

1. **Google Cloud Account** with Gemini API access
   - Visit https://ai.google.dev/
   - Create a project and enable Gemini API
   - Generate an API key

2. **Development Environment**
   - Python 3.11 or higher
   - Node.js 20 or higher
   - PostgreSQL 15 or higher
   - Redis 7 or higher
   - Git

3. **Optional Services**
   - Stripe account (for payments)
   - Sentry account (for error tracking)
   - CRM account (HubSpot, Salesforce)

## Step 1: Clone and Setup Project

```bash
# Clone the repository
git clone https://github.com/yourusername/voiceagent-saas.git
cd voiceagent-saas

# Create data directories
mkdir -p data/recordings data/transcripts
```

## Step 2: Backend Setup

### 2.1 Install Python Dependencies

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2.2 Configure Environment

```bash
# Create .env file
cp .env.example .env
```

Edit `backend/.env` with your configuration:

```env
# Application
SECRET_KEY=generate-a-secure-random-key-here
DEBUG=True

# Database - Update with your PostgreSQL credentials
DATABASE_URL=postgresql://postgres:your-password@localhost:5432/voiceagent_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Google Cloud - REQUIRED
GOOGLE_API_KEY=your-google-api-key-here

# Optional: OpenAI (fallback)
OPENAI_API_KEY=your-openai-key

# Optional: Stripe
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Optional: Monitoring
SENTRY_DSN=https://...
```

### 2.3 Setup Database

```bash
# Create PostgreSQL database
createdb voiceagent_db

# Or using psql:
psql -U postgres
CREATE DATABASE voiceagent_db;
\q
```

### 2.4 Run Backend

```bash
# The database tables will be created automatically
python -m uvicorn backend.app.main:app --reload

# Backend will be available at: http://localhost:8000
# API docs at: http://localhost:8000/api/docs
```

## Step 3: Frontend Setup

### 3.1 Install Node Dependencies

```bash
cd ../frontend

# Install dependencies
npm install
```

### 3.2 Configure Environment

```bash
# Create .env file
echo "VITE_API_URL=http://localhost:8000" > .env
```

### 3.3 Run Frontend

```bash
npm run dev

# Frontend will be available at: http://localhost:3000
```

## Step 4: Create Your First User

### Option A: Using the UI

1. Open http://localhost:3000
2. Click "Créer un compte"
3. Fill in the registration form
4. Login with your credentials

### Option B: Using API

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecurePassword123",
    "full_name": "Admin User"
  }'
```

## Step 5: Create Your First Agent

1. Login to the dashboard
2. Navigate to "Agents"
3. Click "Nouvel Agent"
4. Configure your agent:

```json
{
  "name": "Assistant Français",
  "description": "Agent de démonstration en français",
  "language": "fr-FR",
  "voice_id": "fr-FR-Neural2-A",
  "system_prompt": "Tu es un assistant vocal intelligent et serviable. Tu réponds toujours en français de manière naturelle et amicale. Tu peux aider avec diverses tâches et questions.",
  "is_public": true
}
```

5. Save the agent

## Step 6: Test Voice Functionality

### Option A: Using the Demo Page

1. Navigate to http://localhost:3000/demo
2. Click "Démarrer la Conversation"
3. Allow microphone access
4. Speak in French!

### Option B: Using WebSocket Client

```javascript
// Example WebSocket client
const agentId = 1; // Your agent ID
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/voice/${agentId}`);

ws.onopen = () => {
  console.log('Connected!');
};

ws.onmessage = (event) => {
  if (event.data instanceof Blob) {
    // Audio response - play it
    console.log('Received audio');
  } else {
    const data = JSON.parse(event.data);
    console.log('Message:', data);
  }
};

// Send audio data
const audioChunk = new Int16Array(2048); // Your audio data
ws.send(audioChunk.buffer);
```

## Step 7: Generate API Keys

1. In the dashboard, navigate to "Clés API"
2. Click "Nouvelle Clé"
3. Give it a name (e.g., "Production")
4. Copy the generated key
5. Use it in your applications:

```javascript
const ws = new WebSocket(
  `ws://localhost:8000/api/v1/ws/voice/${agentId}?api_key=${apiKey}`
);
```

## Step 8: Configure CRM Integration (Optional)

### HubSpot Integration

1. Get your HubSpot API key
2. Edit your agent settings:

```json
{
  "crm_enabled": true,
  "crm_webhook_url": "https://api.hubspot.com/contacts/v1/contact",
  "crm_config": {
    "type": "hubspot",
    "api_key": "your-hubspot-key"
  }
}
```

### Salesforce Integration

```json
{
  "crm_enabled": true,
  "crm_webhook_url": "https://your-instance.salesforce.com/services/data/v52.0/sobjects/Task",
  "crm_config": {
    "type": "salesforce",
    "auth_header": {
      "Authorization": "Bearer your-salesforce-token"
    }
  }
}
```

### Custom CRM Webhook

```json
{
  "crm_enabled": true,
  "crm_webhook_url": "https://your-crm.com/api/calls",
  "crm_config": {
    "type": "custom",
    "api_key": "your-api-key",
    "custom_fields": {
      "company_id": "12345",
      "source": "voice_agent"
    }
  }
}
```

## Step 9: Docker Deployment (Production)

### 9.1 Prepare Environment

```bash
# Create .env file in project root
cat > .env << EOF
SECRET_KEY=$(openssl rand -hex 32)
GOOGLE_API_KEY=your-google-api-key
STRIPE_API_KEY=your-stripe-key
SENTRY_DSN=your-sentry-dsn
EOF
```

### 9.2 Build and Run

```bash
# Build all services
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 9.3 Access Services

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
pg_isready

# Check connection string
psql postgresql://postgres:password@localhost:5432/voiceagent_db

# Recreate database if needed
dropdb voiceagent_db
createdb voiceagent_db
```

### Redis Connection Issues

```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Start Redis if not running
redis-server
```

### Microphone Access Issues

1. Ensure you're using HTTPS or localhost
2. Check browser permissions
3. Try a different browser
4. Check system microphone settings

### WebSocket Connection Issues

1. Check firewall settings
2. Verify CORS configuration
3. Check WebSocket URL format
4. Enable debug logging

### Google API Errors

```bash
# Test your API key
curl -X POST https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: YOUR_API_KEY" \
  -d '{"contents":[{"parts":[{"text":"Hello"}]}]}'
```

## Performance Optimization

### Backend

1. **Enable caching**
   ```python
   # Redis caching for API responses
   CACHE_TTL = 300  # 5 minutes
   ```

2. **Connection pooling**
   ```python
   # In database.py
   engine = create_engine(
       DATABASE_URL,
       pool_size=20,
       max_overflow=0
   )
   ```

3. **Async operations**
   - All I/O operations use async/await
   - Background tasks for heavy operations

### Frontend

1. **Code splitting**
   ```javascript
   // Already configured in vite.config.ts
   ```

2. **Image optimization**
   - Use WebP format
   - Lazy loading

3. **API caching**
   - React Query handles caching
   - Adjust staleTime for your needs

## Security Checklist

- [ ] Change default SECRET_KEY
- [ ] Use strong passwords
- [ ] Enable HTTPS in production
- [ ] Configure CORS properly
- [ ] Set up rate limiting
- [ ] Enable API key expiration
- [ ] Regular security updates
- [ ] Monitor error logs
- [ ] Backup database regularly
- [ ] Use environment variables for secrets

## Next Steps

1. **Customize Your Agent**
   - Add custom tools and functions
   - Train on specific use cases
   - Configure voice preferences

2. **Set Up Monitoring**
   - Sentry for error tracking
   - Prometheus for metrics
   - Log aggregation

3. **Deploy to Production**
   - Choose cloud provider
   - Set up CI/CD
   - Configure auto-scaling

4. **Build Your SaaS**
   - Set up Stripe subscriptions
   - Create pricing tiers
   - Build marketing pages

## Getting Help

- **Documentation**: Check README.md for detailed features
- **Issues**: Open a GitHub issue
- **Community**: Join our Discord server
- **Email**: support@voiceagent.com

## Useful Commands

```bash
# Backend
python -m uvicorn backend.app.main:app --reload  # Dev server
python -m pytest                                  # Run tests
python -m alembic upgrade head                   # Database migrations

# Frontend
npm run dev          # Development server
npm run build        # Production build
npm run preview      # Preview production build
npm run lint         # Check code quality

# Docker
docker-compose up -d              # Start all services
docker-compose logs -f backend    # View backend logs
docker-compose restart backend    # Restart backend
docker-compose down -v            # Stop and remove volumes
```

## Success!

If everything is set up correctly, you should be able to:

✅ Access the frontend at http://localhost:3000
✅ Create and login to an account
✅ Create voice agents
✅ Test voice conversations in the demo
✅ View call history and transcripts
✅ Generate API keys
✅ Integrate with your applications

Happy building! 🚀

