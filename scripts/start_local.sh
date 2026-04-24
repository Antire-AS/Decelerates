#!/usr/bin/env bash
# Start local dev environment (API + ensures Postgres is running in WSL)
# Usage: bash scripts/start_local.sh

set -e

# Start PostgreSQL in WSL if not running
echo "Starting PostgreSQL in WSL..."
wsl -d Ubuntu -- bash -c "sudo service postgresql start > /dev/null 2>&1 || true"
sleep 2

# Get WSL IP
WSL_IP=$(wsl -d Ubuntu -- bash -c "hostname -I | awk '{print \$1}'")
echo "WSL IP: $WSL_IP"

# Test connection
if ! DATABASE_URL="postgresql://tharusan@${WSL_IP}:5432/brokerdb" uv run python -c \
  "from sqlalchemy import create_engine, text; e=create_engine('postgresql://tharusan@${WSL_IP}:5432/brokerdb'); e.connect().execute(text('SELECT 1'))" 2>/dev/null; then
  echo "ERROR: Cannot connect to PostgreSQL at $WSL_IP:5432"
  echo "Check that Postgres is running: wsl -d Ubuntu -- sudo service postgresql start"
  exit 1
fi
echo "PostgreSQL OK"

# Start API
export DATABASE_URL="postgresql://tharusan@${WSL_IP}:5432/brokerdb"
echo "Starting API on http://localhost:8000 ..."
uv run --env-file .env uvicorn api.main:app --reload --port 8000
