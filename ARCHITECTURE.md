# VoiceAgent SaaS - Technical Architecture

## System Overview

VoiceAgent SaaS is a multi-tenant platform for creating and managing French-speaking voice agents with ultra-low latency. The system is built on modern web technologies with a focus on real-time performance and scalability.

## Architecture Diagram

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
│                        API Gateway / LB                       │
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
│   - Calls        │ │   - Locks  │ │                │
└──────────────────┘ └────────────┘ └────────────────┘
            │
            ▼
┌──────────────────────────────────────┐
│        External Integrations          │
│  ┌──────────┐  ┌──────────┐          │
│  │ HubSpot  │  │Salesforce│          │
│  │   CRM    │  │   CRM    │          │
│  └──────────┘  └──────────┘          │
└──────────────────────────────────────┘
```

## Technology Stack

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite 5
- **Styling**: TailwindCSS 3
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query)
- **Routing**: React Router v6
- **HTTP Client**: Axios
- **WebSocket**: Native WebSocket API
- **UI Components**: Headless UI, Hero Icons

### Backend
- **Framework**: FastAPI 0.115
- **Python**: 3.11+
- **ASGI Server**: Uvicorn
- **ORM**: SQLAlchemy 2.0
- **Authentication**: JWT (python-jose)
- **Password Hashing**: Passlib with bcrypt
- **AI/ML**:
  - Google Generative AI SDK
  - LangChain 0.3
  - LangGraph 0.2
- **Audio**: PyAudio, Google Cloud Speech/TTS

### Infrastructure
- **Database**: PostgreSQL 15
- **Cache/Queue**: Redis 7
- **Container**: Docker, Docker Compose
- **Web Server** (Production): Nginx
- **Monitoring**: Prometheus, Sentry (optional)

## Data Models

### Core Entities

```python
User
├── id: int
├── email: str (unique)
├── full_name: str
├── hashed_password: str
├── subscription_tier: enum (free, basic, pro, enterprise)
├── total_minutes_used: float
└── api_keys: List[APIKey]

VoiceAgent
├── id: int
├── user_id: int (FK)
├── name: str
├── description: text
├── language: str (default: fr-FR)
├── system_prompt: text
├── agent_config: json (LangGraph workflow)
├── tools_enabled: json (list of tool names)
├── crm_config: json
└── calls: List[Call]

Call
├── id: int
├── user_id: int (FK)
├── agent_id: int (FK)
├── session_id: str (unique)
├── status: enum (initiated, in_progress, completed, failed)
├── duration_minutes: float
├── cost: float
├── transcript: text
├── summary: text
├── sentiment: str
├── key_points: json
└── messages: List[CallMessage]

APIKey
├── id: int
├── user_id: int (FK)
├── key: str (unique, indexed)
├── name: str
├── is_active: bool
├── total_requests: int
└── last_used_at: datetime
```

## API Architecture

### RESTful Endpoints

```
Authentication
POST   /api/v1/auth/register      - Register new user
POST   /api/v1/auth/login         - Login (returns JWT)
GET    /api/v1/auth/me            - Get current user
POST   /api/v1/auth/api-keys      - Create API key
GET    /api/v1/auth/api-keys      - List API keys
DELETE /api/v1/auth/api-keys/{id} - Delete API key

Agents
GET    /api/v1/agents/            - List user's agents
POST   /api/v1/agents/            - Create agent
GET    /api/v1/agents/{id}        - Get agent details
PUT    /api/v1/agents/{id}        - Update agent
DELETE /api/v1/agents/{id}        - Delete agent
GET    /api/v1/agents/public/demo - Get public demo agent

Calls
GET    /api/v1/calls/                      - List calls (with filters)
GET    /api/v1/calls/{id}                  - Get call details
GET    /api/v1/calls/{id}/transcript       - Get transcript
POST   /api/v1/calls/{id}/generate-summary - Generate AI summary
GET    /api/v1/calls/stats/overview        - Get usage statistics
DELETE /api/v1/calls/{id}                  - Delete call
```

### WebSocket Protocol

```
Connection
WS /api/v1/ws/voice/{agent_id}?api_key={key}

Client → Server Messages:
- Binary: Audio chunks (PCM 16-bit, 16kHz)
- JSON: Control messages
  {
    "type": "end_session" | "interrupt"
  }

Server → Client Messages:
- Binary: Audio response (PCM 16-bit, 24kHz)
- JSON: Session events
  {
    "type": "session_started" | "transcript" | "error",
    "session_id": "uuid",
    "agent_name": "string",
    "language": "fr-FR",
    "role": "user" | "agent",
    "text": "string",
    "message": "string"
  }
```

## Voice Processing Flow

```
1. Client captures microphone audio
   ↓
2. Audio converted to PCM 16-bit, 16kHz
   ↓
3. WebSocket sends audio chunks (2048 bytes)
   ↓
4. Backend receives and buffers audio
   ↓
5. Audio sent to Google Gemini 2.5 Flash
   ↓
6. Gemini processes with LangChain/LangGraph
   ↓
7. AI generates response (text + audio)
   ↓
8. Audio streamed back to client (24kHz)
   ↓
9. Client plays audio in real-time
   ↓
10. Transcript saved to database
```

## LangChain/LangGraph Integration

### Agent Workflow

```python
# Simplified LangGraph workflow
from langgraph.graph import StateGraph

# Define agent state
class AgentState(TypedDict):
    messages: List[Message]
    context: Dict[str, Any]
    tools_used: List[str]

# Build workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("understand", understand_intent)
workflow.add_node("process", process_request)
workflow.add_node("execute_tool", execute_tool)
workflow.add_node("respond", generate_response)

# Add edges
workflow.add_edge("understand", "process")
workflow.add_conditional_edges(
    "process",
    should_use_tool,
    {
        True: "execute_tool",
        False: "respond"
    }
)
workflow.add_edge("execute_tool", "respond")

# Compile
agent = workflow.compile()
```

### Custom Tools

```python
# Example: Customer lookup tool
@tool
def get_customer_info(customer_id: str) -> dict:
    """Récupère les informations d'un client"""
    # Query database or CRM
    return {
        "name": "Jean Dupont",
        "email": "jean@example.com",
        "status": "Premium"
    }

# Example: Appointment booking
@tool
def book_appointment(date: str, time: str, reason: str) -> dict:
    """Réserve un rendez-vous"""
    # Create appointment in system
    return {
        "success": True,
        "appointment_id": "APT-123",
        "date": date,
        "time": time
    }
```

## Security Architecture

### Authentication Flow

```
1. User registers/logs in
   ↓
2. Server validates credentials
   ↓
3. Server generates JWT token
   {
     "sub": user_id,
     "exp": expiration_timestamp
   }
   ↓
4. Client stores token (localStorage)
   ↓
5. Client includes token in requests
   Authorization: Bearer <token>
   ↓
6. Server validates token on each request
   ↓
7. Token refresh on expiration
```

### API Key Authentication

```
1. User generates API key
   ↓
2. Key format: vak_<32-char-urlsafe-base64>
   ↓
3. Key stored hashed in database
   ↓
4. Client includes key in WebSocket URL
   ws://api/ws/voice/1?api_key=vak_...
   ↓
5. Server validates and tracks usage
```

## Performance Optimizations

### Frontend
- Code splitting by route
- Image lazy loading
- React Query caching (5min default)
- WebSocket connection pooling
- Audio buffer management

### Backend
- Async/await throughout
- Database connection pooling (20 connections)
- Redis caching for hot data
- Background tasks for heavy operations
- Streaming responses for large data

### Database
- Indexed columns:
  - Users: email
  - APIKeys: key
  - Calls: session_id, user_id, status
  - Agents: user_id, is_public
- Query optimization with SQLAlchemy
- Pagination for large result sets

## Scaling Strategy

### Horizontal Scaling
- Stateless backend (multiple instances)
- Load balancer (Nginx, ALB)
- Redis for shared state
- PostgreSQL read replicas

### Vertical Scaling
- Increase container resources
- Database optimization
- Connection pool tuning

### Microservices (Future)
```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  API Service │  │Voice Service │  │ CRM Service  │
└──────────────┘  └──────────────┘  └──────────────┘
       │                  │                  │
       └──────────────────┴──────────────────┘
                          │
                   Message Queue
                    (RabbitMQ)
```

## Monitoring & Observability

### Metrics to Track
- Request latency (p50, p95, p99)
- WebSocket connections (active, total)
- Voice call duration
- Error rates by endpoint
- Database query performance
- Cache hit rates
- API key usage

### Logging Strategy
- Structured logging (JSON)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Correlation IDs for request tracing
- Sensitive data masking

### Alerting
- High error rates (>5%)
- Slow response times (>2s)
- Database connection issues
- Redis unavailability
- High memory/CPU usage

## Disaster Recovery

### Backup Strategy
- Database: Daily automated backups
- Call recordings: S3 with versioning
- Configuration: Version control
- Recovery Time Objective (RTO): 4 hours
- Recovery Point Objective (RPO): 1 hour

### High Availability
- Multi-AZ database deployment
- Redis cluster mode
- Load balancer health checks
- Auto-scaling groups
- Circuit breakers for external APIs

## Future Enhancements

### Phase 2
- [ ] Real-time collaboration
- [ ] Advanced analytics dashboard
- [ ] Voice cloning
- [ ] Multi-language support
- [ ] Mobile SDKs

### Phase 3
- [ ] AI training on custom data
- [ ] Integration marketplace
- [ ] White-label solutions
- [ ] Advanced workflow builder
- [ ] Real-time translation

## Development Workflow

```
Development → Staging → Production

1. Local Development
   - Docker Compose
   - Hot reload
   - Debug mode

2. CI/CD Pipeline
   - Automated tests
   - Linting
   - Build images
   - Security scanning

3. Staging Deploy
   - Smoke tests
   - Integration tests
   - Performance tests

4. Production Deploy
   - Blue-green deployment
   - Canary releases
   - Rollback capability
```

## Conclusion

This architecture provides:
- ✅ Ultra-low latency (<300ms)
- ✅ High scalability
- ✅ Security & compliance
- ✅ Extensibility
- ✅ Monitoring & observability
- ✅ Easy maintenance

For questions or contributions, see README.md or contact the development team.

