#!/bin/bash

# VoiceAgent SaaS - Production Deployment Script

set -e

echo "🚀 VoiceAgent SaaS - Production Deployment"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please create .env file with production credentials"
    echo "Example:"
    echo "  SECRET_KEY=your-secret-key"
    echo "  GOOGLE_API_KEY=your-api-key"
    echo "  POSTGRES_PASSWORD=your-db-password"
    echo "  REDIS_PASSWORD=your-redis-password"
    exit 1
fi

# Load environment variables
source .env

# Validate required variables
required_vars=("SECRET_KEY" "GOOGLE_API_KEY" "POSTGRES_PASSWORD")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Required environment variable $var is not set"
        exit 1
    fi
done

echo "✅ Environment variables validated"
echo ""

# Build images
echo "🔨 Building Docker images..."
docker-compose -f docker-compose.prod.yml build --no-cache
echo "✅ Images built successfully"
echo ""

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down
echo ""

# Start services
echo "🚀 Starting services..."
docker-compose -f docker-compose.prod.yml up -d
echo ""

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🏥 Checking service health..."
services=("postgres" "redis" "backend" "frontend" "nginx")
all_healthy=true

for service in "${services[@]}"; do
    if docker-compose -f docker-compose.prod.yml ps | grep -q "$service.*Up"; then
        echo "✅ $service is running"
    else
        echo "❌ $service is not running"
        all_healthy=false
    fi
done

echo ""

if [ "$all_healthy" = true ]; then
    echo "✅ All services are running!"
    echo ""
    echo "🌐 Your application is now available at:"
    echo "   Frontend: http://localhost"
    echo "   Backend API: http://localhost/api"
    echo "   API Docs: http://localhost/api/docs"
    echo ""
    echo "📊 View logs with:"
    echo "   docker-compose -f docker-compose.prod.yml logs -f"
else
    echo "❌ Some services failed to start"
    echo "Check logs with:"
    echo "   docker-compose -f docker-compose.prod.yml logs"
    exit 1
fi

echo ""
echo "🎉 Deployment complete!"

