#!/bin/sh
set -e

# 1. Fallback credentials for LOCAL docker development only
LOCAL_USER="postgres_user"
LOCAL_DB="marketplace_db"

echo "⏳ Checking database connection parameters..."

# 2. Dynamically determine how to check database readiness
if [ -n "$DATABASE_URL" ]; then
  echo "Detected Render environment. Checking connection via DATABASE_URL..."
  until pg_isready -d "$DATABASE_URL"; do
    echo "Database is not ready yet - sleeping 1 second"
    sleep 1
  done
else
  # Fallback logic for your local Docker Compose setup
  DB_HOST="${DB_HOST:-db}"
  POSTGRES_USER="${POSTGRES_USER:-$LOCAL_USER}"
  POSTGRES_DB="${POSTGRES_DB:-$LOCAL_DB}"
  
  echo "Detected local environment. Waiting for PostgreSQL at ${DB_HOST}..."
  until pg_isready -h "$DB_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
    sleep 1
  done
fi

echo "🚀 Applying database migrations..."
python manage.py migrate --noinput

if python manage.py help seed_marketplace >/dev/null 2>&1; then
  echo "🌱 Seeding development data..."
  python manage.py seed_marketplace
else
  echo "⏩ Skipping seed_marketplace (command not installed yet)."
fi

# 3. Handle server launch dynamically (Gunicorn for production Render, runserver for local dev)
if [ -n "$RENDER" ]; then
  echo "🏁 Starting production environment via Gunicorn..."
  # Hand execution back to Render's Dockerfile CMD (which runs Gunicorn)
  exec "$@"
else
  echo "💻 Starting local development server..."
  python manage.py runserver 0.0.0.0:8000
fi
