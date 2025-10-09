# VoiceAgent SaaS - French Voice Agents with Ultra-Low Latency

A comprehensive SaaS platform for creating realistic French-speaking voice agents powered by Google Gemini 2.5 Flash, LangChain, and LangGraph.

## 🚀 Features

- **Ultra-Low Latency**: Real-time voice conversations with <300ms latency using Gemini 2.5 Flash
- **Native French Support**: Optimized for French language with natural pronunciation
- **Advanced AI**: Powered by Google Gemini, LangChain, and LangGraph for intelligent conversations
- **Backoffice Dashboard**: Comprehensive interface to review calls, transcripts, and summaries
- **CRM Integration**: Built-in webhooks for HubSpot, Salesforce, and custom CRM systems
- **API-First**: RESTful API and WebSocket support for easy integration
- **Multi-Tenant**: API key-based authentication with usage tracking and billing
- **Real-Time Analytics**: Call statistics, sentiment analysis, and detailed transcripts

## 📋 Requirements

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+
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

# Stripe (optional)
STRIPE_API_KEY=your-stripe-key
STRIPE_WEBHOOK_SECRET=your-webhook-secret
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
- `POST /api/v1/calls/{id}/generate-summary` - Generate AI summary

#### WebSocket
- `WS /api/v1/ws/voice/{agent_id}` - Real-time voice connection

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

- Use managed PostgreSQL (RDS, Cloud SQL)
- Redis cluster for session management
- Load balancer for multiple backend instances
- CDN for frontend assets
- Separate WebSocket servers for voice traffic

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines.

## 📧 Support

- Documentation: [docs.voiceagent.com](https://docs.voiceagent.com)
- Email: support@voiceagent.com
- Discord: [Join our community](https://discord.gg/voiceagent)

## 🎯 Roadmap

- [ ] Multi-language support (Spanish, German, Italian)
- [ ] Advanced analytics dashboard
- [ ] Call recording playback in browser
- [ ] Voice cloning capabilities
- [ ] Integration marketplace
- [ ] Mobile SDKs (iOS, Android)
- [ ] Custom voice training
- [ ] Real-time collaboration features

## 🙏 Acknowledgments

- Google Gemini Team for the amazing voice AI
- LangChain community
- FastAPI and React communities

---

Built with ❤️ for creating amazing voice experiences in French.

