#!/usr/bin/env bash
set -e

echo "🤖 JARVIS Setup Script"
echo "======================"

# Check dependencies
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required"; exit 1; }
command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || { echo "❌ Docker Compose is required"; exit 1; }

# Create .env if missing
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "✅ Created .env from .env.example — please edit it with your API keys"
fi

# Start services
echo "🚀 Starting JARVIS services..."
docker compose up -d postgres redis chromadb

echo "⏳ Waiting for PostgreSQL to be ready..."
until docker compose exec postgres pg_isready -U jarvis -d jarvis_db >/dev/null 2>&1; do
  sleep 1
done

echo "📦 Running database migrations..."
docker compose run --rm backend alembic upgrade head

echo "🏗️  Starting all services..."
docker compose up -d

echo ""
echo "✅ JARVIS is running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
