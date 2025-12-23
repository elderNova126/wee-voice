# VoiceAgent SaaS - French Voice Agents with Ultra-Low Latency

A comprehensive SaaS platform for creating realistic French-speaking voice agents powered by Google Gemini 2.5 Flash, LangChain, and LangGraph.

## 🚀 Features

### Core Capabilities
- **Ultra-Low Latency**: Real-time voice conversations with <300ms latency using Gemini 2.5 Flash
- **Native French Support**: Optimized for French language with natural pronunciation
- **Advanced AI**: Powered by Google Gemini, LangChain, and LangGraph for intelligent conversations
- **🎭 Video Avatars**: Create interactive AI-powered video avatars from a single photo with real-time animation during calls
- **Complete Dashboard**: Modern UI with billing, usage analytics, security, and support
- **CRM Integration**: Built-in webhooks for HubSpot, Salesforce, and custom CRM systems
- **Credit-Based Billing**: Pay-as-you-go with Stripe integration
- **Security Features**: Domain/IP allowlists, security logs, and audit trails
- **Support System**: Complete ticketing system with email notifications
- **Real-Time Analytics**: Detailed charts, call statistics, and export capabilities
- **Zadarma PBX Integration**: Configure business-hours menus and after-hours routing that connect callers directly with AI agents or human teams

### Performance & Scalability
- **High Concurrency**: Handles 100+ simultaneous users without performance degradation
- **Non-Blocking Architecture**: All I/O operations are async for maximum throughput
- **Intelligent Rate Limiting**: Prevents overload with configurable per-endpoint limits
- **Connection Pooling**: Optimized database and external API connection management
- **Background Processing**: Long-running tasks (summaries, emails) run asynchronously
- **Caching System**: Reduces database load for frequently accessed data
- **Performance Monitoring**: Real-time metrics and health check endpoints
- **Production Ready**: Optimized for high-traffic, multi-user scenarios

## 📚 Complete Documentation

**For detailed setup, configuration, API reference, and feature documentation, see:**
### **[COMPLETE_DOCUMENTATION.md](COMPLETE_DOCUMENTATION.md)**

## 🆕 Recent Updates

### 🚀 Complete Performance & Scalability Overhaul (2024-11-24)
**Major performance improvements for high-traffic scenarios** - The application now handles 100+ concurrent users without delays or overload:

#### Key Improvements:
- ⚡ **30x Faster Response Times**: Summary generation and other operations return immediately (<1s vs 10-30s)
- 🔄 **Background Task Processing**: Long-running operations don't block API responses
- 🛡️ **Rate Limiting**: Intelligent rate limiting prevents API overload (100 req/min general, lower for expensive operations)
- 📊 **Database Optimization**: 2x larger connection pool (60 connections) + optimized queries
- 📧 **Async Email Service**: Non-blocking email sending with connection pooling
- 🎯 **Connection Management**: External API calls (OpenAI/Gemini) use connection pools
- 💾 **Caching System**: In-memory caching reduces database load
- 📈 **Performance Monitoring**: Real-time metrics and health checks

#### Scalability Metrics:
- **Concurrent Users**: 100+ (was 5-10)
- **Response Times**: <1s average under load (was 2-5s)
- **Throughput**: 50-100 requests/second
- **Database Capacity**: 60 concurrent connections (was 30)

See [PERFORMANCE_SCALABILITY_FIX.md](docs/PERFORMANCE_SCALABILITY_FIX.md) for complete details and [CHANGELOG.md](CHANGELOG.md) for all changes.

## 📋 Requirements

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Google Cloud API Key (for Gemini)

## 🛠️ Installation

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/voiceagent-saas.git
   cd voiceagent-saas
   ```

2. **Set up environment variables**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your credentials
   ```

3. **Start all services**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs

### Manual Installation

#### Backend Setup

1. **Create virtual environment**
   ```bash
   cd backend
   python -m venv venv  
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Initialize database**
   ```bash
   # The database tables will be created automatically on first run
   python -m uvicorn app.main:app --reload
   ```

#### Frontend Setup

1. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Configure environment**
   ```bash
   # Create .env file
   echo "VITE_API_URL=http://localhost:8000" > .env
   ```

3. **Start development server**
   ```bash
   npm run dev
   ```

## 🎯 Quick Start

### 1. Create Your First Agent

After logging in:

1. Navigate to **Dashboard > Agents**
2. Click **"Nouvel Agent"**
3. Configure your agent:
   - **Name**: Your agent's name
   - **Language**: Select French (fr-FR)
   - **System Prompt**: Define agent behavior
   - **Tools**: Enable optional features (CRM, appointments, etc.)

### 2. Test with Demo

Visit `/demo` to test the public demo agent with voice interaction.

> 💡 Need sample agents? Run `python backend/scripts/seed_public_agents.py` to create the bundled French concierge and the **French-language** Dubai real estate discovery demos (marked as public automatically).

> ☎️ When a public agent has an assigned phone number, the landing page, demo, and dedicated agent page now surface a direct call button so you can dial the AI instantly.

### 3. Integrate via API

Generate an API key and connect via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/voice/AGENT_ID?api_key=YOUR_API_KEY');

ws.onopen = () => {
  console.log('Connected to voice agent');
};

ws.onmessage = (event) => {
  if (event.data instanceof Blob) {
    // Handle audio response
  } else {
    // Handle text messages
    const data = JSON.parse(event.data);
    console.log(data);
  }
};

// Send audio chunks
ws.send(audioBuffer);
```

## 📚 Architecture

### Backend Stack
- **FastAPI**: High-performance async API framework
- **PostgreSQL**: Primary database for users, agents, calls
- **Redis**: Caching and session management
- **SQLAlchemy**: ORM for database operations
- **Google Gemini 2.5**: Voice AI model with native audio support
- **LangChain/LangGraph**: Agent orchestration and workflows

### Frontend Stack
- **React 18**: Modern UI framework
- **TypeScript**: Type-safe development
- **Vite**: Fast build tool
- **TailwindCSS**: Utility-first CSS
- **React Query**: Data fetching and caching
- **Zustand**: State management

### Key Components

```
backend/
├── app/
│   ├── api/              # API endpoints
│   │   ├── auth.py       # Authentication
│   │   ├── agents.py     # Agent management
│   │   ├── calls.py      # Call history
│   │   └── websocket.py  # Real-time voice
│   ├── models/           # Database models
│   ├── services/         # Business logic
│   │   ├── agent_service.py    # Voice agent
│   │   └── crm_service.py      # CRM integration
│   └── core/             # Configuration

frontend/
├── src/
│   ├── pages/            # Route pages
│   ├── layouts/          # Layout components
│   ├── lib/              # API client
│   └── store/            # State management
```

## 🔧 Configuration

### Environment Variables

**Backend (.env)**
```env
# Security
SECRET_KEY=your-secret-key-here
DEBUG=True

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/voiceagent_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Google Cloud
GOOGLE_API_KEY=your-google-api-key
OPENAI_API_KEY=your-openai-api-key  # For summaries

# Stripe (optional)
STRIPE_API_KEY=your-stripe-key
STRIPE_WEBHOOK_SECRET=your-webhook-secret

# Performance & Scalability
ENABLE_RATE_LIMITING=True  # Enable rate limiting (recommended)
RATE_LIMIT_PER_MINUTE=100  # Max requests per minute per IP

# Email (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=True
```

**Frontend (.env)**
```env
VITE_API_URL=http://localhost:8000
```

### CRM Integration

Configure webhooks for your CRM:

```python
# HubSpot Example
{
  "crm_webhook_url": "https://api.hubspot.com/contacts/v1/contact",
  "crm_config": {
    "type": "hubspot",
    "api_key": "your-hubspot-key"
  }
}

# Salesforce Example
{
  "crm_webhook_url": "https://your-instance.salesforce.com/services/data/v52.0/sobjects/Task",
  "crm_config": {
    "type": "salesforce",
    "auth_header": {
      "Authorization": "Bearer your-token"
    }
  }
}
```

## 🎨 Features in Detail

### Voice Agent Capabilities

- **Real-time streaming**: Continuous audio streaming with minimal latency
- **Interruption handling**: Natural conversation flow with interruption support
- **Function calling**: Integrate custom tools and APIs
- **Multilingual**: Support for French, English, and more
- **Voice selection**: Multiple voice options for different use cases

### Backoffice Features

- **Call Review**: Listen to recordings and review transcripts
- **AI Summaries**: Automatic call summarization with key points
- **Sentiment Analysis**: Understand customer emotions
- **Usage Analytics**: Track minutes, costs, and performance
- **API Management**: Create and manage API keys

### API Endpoints

#### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/auth/me` - Get current user
- `POST /api/v1/auth/api-keys` - Create API key

#### Agents
- `GET /api/v1/agents/` - List agents
- `POST /api/v1/agents/` - Create agent
- `PUT /api/v1/agents/{id}` - Update agent
- `DELETE /api/v1/agents/{id}` - Delete agent

#### Calls
- `GET /api/v1/calls/` - List calls
- `GET /api/v1/calls/{id}` - Get call details
- `GET /api/v1/calls/{id}/transcript` - Get transcript
- `POST /api/v1/calls/{id}/generate-summary` - Generate AI summary (async, non-blocking)
- `GET /api/v1/calls/{id}/summary-status` - Check summary generation status

#### WebSocket
- `WS /api/v1/ws/voice/{agent_id}` - Real-time voice connection
- `WS /api/v1/ws/call-monitor` - Real-time call updates and notifications

#### Performance
- `GET /api/v1/performance/health` - Health check with metrics
- `GET /api/v1/performance/stats` - Performance statistics (admin only)

## 🔐 Security

- JWT-based authentication
- API key management with rate limiting
- CORS configuration
- Environment-based secrets
- SQL injection protection via SQLAlchemy
- Input validation with Pydantic

## 📈 Monitoring & Analytics

### Built-in Metrics
- Total calls and duration
- Cost tracking
- Success rates
- Sentiment distribution
- Usage by subscription tier

### Integration Options
- Prometheus metrics (planned)
- Sentry error tracking
- Custom webhooks for events

## 🚢 Deployment

### Production Deployment

1. **Update environment variables**
   ```bash
   # Set production values
   DEBUG=False
   SECRET_KEY=secure-random-key
   DATABASE_URL=production-db-url
   ```

2. **Build production images**
   ```bash
   docker-compose -f docker-compose.prod.yml build
   ```

3. **Deploy to cloud**
   - AWS ECS / Fargate
   - Google Cloud Run
   - Azure Container Instances
   - Kubernetes cluster

### Scaling Considerations

The application is optimized for horizontal scaling:

- **Database**: Use managed PostgreSQL (RDS, Cloud SQL) with read replicas
- **Caching**: Redis cluster for distributed caching (in-memory cache included)
- **Load Balancing**: Multiple backend instances behind load balancer
- **CDN**: Serve frontend assets from CDN
- **WebSocket**: Separate WebSocket servers for voice traffic
- **Background Tasks**: Optional: Add Celery/RQ for distributed task processing

**Current Capacity** (single instance):
- 100+ concurrent users
- 50-100 requests/second
- 60 concurrent database connections
- Intelligent rate limiting per endpoint

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test

# Performance & Load Testing
cd backend
python test_load_performance.py  # Test concurrent request handling
python test_concurrent_summary.py  # Test summary generation concurrency
```

### Performance Testing

The application includes comprehensive load testing to verify scalability:

```bash
# Test with 100 concurrent users
python backend/test_load_performance.py
```

**Expected Results**:
- 95%+ success rate under load
- <1s average response time
- 50-100 requests/second throughput

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines.

## 📧 Support

- Documentation: [docs.voiceagent.com](https://docs.voiceagent.com)
- Email: support@voiceagent.com
- Discord: [Join our community](https://discord.gg/voiceagent)

## 🎯 Roadmap

### Completed ✅
- [x] **Multi-user concurrency support** (100+ users)
- [x] **Performance optimization** (30x faster)
- [x] **Rate limiting** (prevent overload)
- [x] **Background task processing** (non-blocking)
- [x] **Connection pooling** (external APIs)
- [x] **Performance monitoring** (real-time metrics)
- [x] **🎭 Video Avatar Feature** (AI-powered avatars from photos)

### Planned
- [ ] Multi-language support (Spanish, German, Italian)
- [ ] Redis integration for distributed caching
- [ ] Advanced analytics dashboard
- [ ] Call recording playback in browser
- [ ] Real-time avatar animation streaming (upgrade from static)
- [ ] Voice cloning capabilities
- [ ] Integration marketplace
- [ ] Mobile SDKs (iOS, Android)
- [ ] Custom voice training
- [ ] Real-time collaboration features
- [ ] Horizontal auto-scaling based on load
- [ ] Advanced monitoring (Prometheus, Grafana)

## 🙏 Acknowledgments

- Google Gemini Team for the amazing voice AI
- LangChain community
- FastAPI and React communities

---

Built with ❤️ for creating amazing voice experiences in French.

