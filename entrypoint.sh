#!/bin/sh
set -e

echo "⏳ Waiting for Postgres @ ${POSTGRES_HOST}:${POSTGRES_PORT}…"
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" >/dev/null 2>&1; do
  sleep 2
done
echo "✅ Postgres is up – running migrations"
uv run alembic upgrade head

echo "🚀 Starting bot"
exec "$@"
