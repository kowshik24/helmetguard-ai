#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

mkdir -p logs data/uploads data/artifacts data/reports
cp -n .env.example .env || true

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but not found in PATH."
  exit 1
fi

if [ ! -d "venv" ]; then
  uv venv venv
fi

source venv/bin/activate
uv pip install -e .

INSTALL_VISION="${INSTALL_VISION:-1}"
if [ "$INSTALL_VISION" = "1" ]; then
  echo "Installing vision dependencies (this can take a while)..."
  uv pip install -e '.[vision]'
fi

if ! redis-cli -p 6379 ping >/dev/null 2>&1; then
  echo "Starting Redis on port 6379..."
  redis-server --port 6379 --daemonize yes --pidfile "$ROOT_DIR/logs/redis.pid"
  sleep 1
fi

if ! redis-cli -p 6379 ping >/dev/null 2>&1; then
  echo "Redis failed to start."
  exit 1
fi

# Stop stale processes if present.
if [ -f logs/api.pid ] && ps -p "$(cat logs/api.pid)" >/dev/null 2>&1; then
  kill "$(cat logs/api.pid)" || true
fi
if [ -f logs/worker.pid ] && ps -p "$(cat logs/worker.pid)" >/dev/null 2>&1; then
  kill "$(cat logs/worker.pid)" || true
fi

nohup venv/bin/uvicorn api.app.main:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
echo $! > logs/api.pid

nohup venv/bin/python -m worker.app.main > logs/worker.log 2>&1 &
echo $! > logs/worker.pid

sleep 2

echo "Setup complete."
echo "API PID: $(cat logs/api.pid)"
echo "Worker PID: $(cat logs/worker.pid)"
echo "Health: $(curl -sS http://127.0.0.1:8000/api/v1/health || echo 'unavailable')"
