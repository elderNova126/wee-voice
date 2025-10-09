#!/bin/bash

# VoiceAgent SaaS - Setup Script
# This script helps set up the development environment

set -e

echo "🚀 VoiceAgent SaaS - Setup Script"
echo "=================================="
echo ""

# Check for required tools
echo "📋 Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required but not installed. Aborting." >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js is required but not installed. Aborting." >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "⚠️  Docker is not installed. Docker is recommended for easy setup." >&2; }

echo "✅ Prerequisites check passed"
echo ""

# Generate secret key
echo "🔐 Generating secret key..."
SECRET_KEY=$(openssl rand -hex 32)
echo "Generated SECRET_KEY: $SECRET_KEY"
echo ""

# Setup backend
echo "🔧 Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

echo "Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating backend .env file..."
    cat > .env << EOF
SECRET_KEY=$SECRET_KEY
DEBUG=True
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/voiceagent_db
REDIS_URL=redis://localhost:6379/0
GOOGLE_API_KEY=your-google-api-key-here
EOF
    echo "✅ Backend .env created (please update GOOGLE_API_KEY)"
else
    echo "⚠️  Backend .env already exists, skipping..."
fi

cd ..
echo ""

# Setup frontend
echo "🎨 Setting up frontend..."
cd frontend

echo "Installing Node dependencies..."
npm install

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating frontend .env file..."
    echo "VITE_API_URL=http://localhost:8000" > .env
    echo "✅ Frontend .env created"
else
    echo "⚠️  Frontend .env already exists, skipping..."
fi

cd ..
echo ""

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/recordings data/transcripts
echo "✅ Data directories created"
echo ""

# Docker setup
if command -v docker >/dev/null 2>&1; then
    echo "🐳 Docker detected. Would you like to start services with Docker? (y/n)"
    read -r use_docker
    
    if [ "$use_docker" = "y" ]; then
        echo "Starting services with Docker Compose..."
        docker-compose up -d postgres redis
        echo "✅ PostgreSQL and Redis started"
        echo ""
        echo "⏳ Waiting for services to be ready..."
        sleep 5
    fi
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Update backend/.env with your GOOGLE_API_KEY"
echo "2. Start PostgreSQL and Redis (or use Docker Compose)"
echo "3. Start backend:"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   python -m uvicorn backend.app.main:app --reload"
echo ""
echo "4. Start frontend (in another terminal):"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "5. Visit http://localhost:3000"
echo ""
echo "📚 For more details, see SETUP_GUIDE.md"

