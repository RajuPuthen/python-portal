#!/bin/sh
set -e

DB_HOST="${DB_HOST:-db}"
POSTGRES_USER="${POSTGRES_USER:-postgres_user}"
POSTGRES_DB="${POSTGRES_DB:-marketplace_db}"

echo "Waiting for PostgreSQL at ${DB_HOST}..."
until pg_isready -h "$DB_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
  sleep 1
done

echo "Applying database migrations..."
python manage.py migrate --noinput

if python manage.py help seed_marketplace >/dev/null 2>&1; then
  echo "Seeding development data..."
  python manage.py seed_marketplace
else
  echo "Skipping seed_marketplace (command not installed yet)."
fi

echo "Starting development server..."
python manage.py runserver 0.0.0.0:8000
