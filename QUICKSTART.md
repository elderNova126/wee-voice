# 🚀 Quick Start Guide

Get VoiceAgent SaaS running in 5 minutes!

## Prerequisites

- Python 3.11+ installed
- Node.js 20+ installed
- PostgreSQL 15+ running
- Google API Key ([Get one here](https://ai.google.dev/))

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd germini_voice

# Create data directories
mkdir -p data/recordings data/transcripts
```

## Step 2: Backend Setup (5 minutes)

```bash
# Navigate to backend
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

### Configure Environment

The `.env` file is already created. Just update these values:

```bash
# Open backend/.env and update:
# 1. SECRET_KEY - Generate with: python -c "import secrets; print(secrets.token_hex(32))"
# 2. GOOGLE_API_KEY - Your Google AI API key
# 3. DATABASE_URL - Your PostgreSQL connection string
```

**Quick example:**

```env
SECRET_KEY=abc123...your-generated-key
GOOGLE_API_KEY=AIzaSy...your-google-key
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/voiceagent_db
```

### Create Database

```bash
# Using psql
psql -U postgres
CREATE DATABASE voiceagent_db;
\q

# Or using createdb command
createdb voiceagent_db
```

### Start Backend

```bash
# Make sure you're in backend/ with venv activated
python -m uvicorn backend.app.main:app --reload
```

✅ Backend running at: http://localhost:8000
📚 API Docs at: http://localhost:8000/api/docs

## Step 3: Frontend Setup (2 minutes)

Open a **new terminal** (keep backend running):

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# The .env file is already configured for local development
# Start development server
npm run dev
```

✅ Frontend running at: http://localhost:3000

## Step 4: Test the Application

1. **Open your browser**: http://localhost:3000
2. **Create an account**: Click "Créer un compte"
3. **Create your first agent**:
   - Go to Dashboard → Agents
   - Click "Nouvel Agent"
   - Fill in:
     - Name: "Assistant Test"
     - Language: French (fr-FR)
     - System Prompt: "Tu es un assistant vocal serviable."
   - Save

4. **Try the Demo**:
   - Go to http://localhost:3000/demo
   - Click "Démarrer la Conversation"
   - Allow microphone access
   - **Speak in French!** 🎙️

## Quick Configuration Reference

### Backend (.env)
```env
# Required
GOOGLE_API_KEY=your-key-here
DATABASE_URL=postgresql://user:pass@localhost:5432/voiceagent_db
SECRET_KEY=your-secret-key

# Optional
DEBUG=True
```

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000
```

## Troubleshooting

### Backend won't start?
```bash
# Check PostgreSQL is running
pg_isready

# Check your .env file
cat backend/.env

# Regenerate secret key
python -c "import secrets; print(secrets.token_hex(32))"
```

### Frontend won't connect?
```bash
# Verify backend is running
curl http://localhost:8000/health

# Check frontend .env
cat frontend/.env
```

### Database connection error?
```bash
# Test PostgreSQL connection
psql -U postgres -d voiceagent_db

# Update DATABASE_URL in backend/.env with correct credentials
```

### Google API error?
- Verify your API key at: https://ai.google.dev/
- Make sure Gemini API is enabled
- Check quota limits

## What's Next?

- 📖 Read the full [README.md](README.md)
- 🔧 Check [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup
- 🏗️ See [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- 🚢 Review [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment

## Using Docker (Alternative)

If you prefer Docker:

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Common Commands

```bash
# Backend
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python -m uvicorn backend.app.main:app --reload

# Frontend
cd frontend
npm run dev

# Database
psql -U postgres -d voiceagent_db
\dt  # List tables
\q   # Quit

# Generate Secret Key
python -c "import secrets; print(secrets.token_hex(32))"
```

## Need Help?

- Check the [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions
- Review error logs in the terminal
- Ensure all prerequisites are installed
- Verify .env files are configured correctly

Happy building! 🎉🇫🇷

