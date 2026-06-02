#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  JARVIS — one-command startup
#  Usage:  ./start.sh
# ──────────────────────────────────────────────────────────────
set -e

echo ""
echo "🤖  Starting JARVIS — your personal Reddit assistant"
echo "───────────────────────────────────────────────────"

# 1. Make sure a .env exists
if [ ! -f .env ]; then
  echo "📝  No .env found — creating one from the template..."
  cp .env.example .env
  echo ""
  echo "⚠️   STOP: open the file called  .env  and paste in your keys:"
  echo "        • ANTHROPIC_API_KEY   (console.anthropic.com)"
  echo "        • OPENAI_API_KEY      (platform.openai.com)"
  echo "        • REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (reddit.com/prefs/apps)"
  echo ""
  echo "    Then run  ./start.sh  again."
  exit 0
fi

# 2. Start all the services
echo "🐳  Starting services (this can take a few minutes the first time)..."
docker compose up --build -d

# 3. Wait for the backend to be ready
echo "⏳  Waiting for the backend to wake up..."
until docker compose exec -T backend python -c "print('ok')" >/dev/null 2>&1; do
  sleep 3
done

# 4. Set up the database
echo "🗄️   Setting up the database..."
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend python -m app.db.seed

# 5. Done!
echo ""
echo "✅  JARVIS is running!"
echo "───────────────────────────────────────────────────"
echo "   Open:      http://localhost:3000"
echo "   Login:     admin@jarvis.local"
echo "   Password:  JarvisAdmin2024!"
echo ""
echo "   To stop later:  docker compose down"
echo "───────────────────────────────────────────────────"
