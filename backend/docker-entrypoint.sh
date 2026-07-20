#!/bin/sh
# Migrations run in-VPC before the app starts: RDS only accepts connections
# from the service security group, so this is the schema's only owner.
set -e

if [ -n "${EVERPILOT_SSM_CONFIG:-}" ] || [ -n "${DATABASE_URL:-}" ]; then
  echo "Running database migrations..."
  alembic upgrade head
else
  echo "No database configured — skipping migrations (in-memory mode)"
fi

exec uvicorn everpilot.main:app --host 0.0.0.0 --port 8000
