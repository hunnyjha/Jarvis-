#!/usr/bin/env bash
set -e
echo "Running database migrations..."
docker compose run --rm backend alembic upgrade head
echo "✅ Migrations complete"
