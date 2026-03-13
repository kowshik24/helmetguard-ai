#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

mkdir -p logs data/uploads data/artifacts data/reports
if [ ! -f .env ]; then
  cp .env.example .env
fi

env_get() {
  local key="$1"
  local default_val="$2"
  if [ -f .env ]; then
    local line
    line="$(grep -E "^${key}=" .env | tail -n 1 || true)"
    if [ -n "$line" ]; then
      local value="${line#*=}"
      value="${value%$'\r'}"
      echo "$value"
      return
    fi
  fi
  echo "$default_val"
}

run_cmd() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

wait_for_health() {
  local url="$1"
  local timeout_sec="${2:-40}"
  local elapsed=0
  until curl -fsS "$url" >/dev/null 2>&1; do
    sleep 1
    elapsed=$((elapsed + 1))
    if [ "$elapsed" -ge "$timeout_sec" ]; then
      echo "Health check timeout: $url"
      return 1
    fi
  done
  return 0
}

setup_ufw() {
  local enable_ufw="$1"
  local ufw_ports="$2"
  local auto_enable="$3"

  if [ "$enable_ufw" != "1" ]; then
    return 0
  fi

  if ! command -v ufw >/dev/null 2>&1; then
    echo "UFW not installed; skipping firewall configuration."
    return 0
  fi

  IFS=',' read -r -a ports <<< "$ufw_ports"
  for port in "${ports[@]}"; do
    port="${port// /}"
    if [ -n "$port" ]; then
      run_cmd ufw allow "${port}/tcp" || true
    fi
  done

  if [ "$auto_enable" = "1" ]; then
    run_cmd ufw --force enable
  fi

  run_cmd ufw status || true
}

install_system_deps() {
  local install_flag="$1"
  local deps_csv="$2"
  if [ "$install_flag" != "1" ]; then
    return 0
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    echo "apt-get not found; skipping system dependency installation."
    return 0
  fi

  local deps_spaced
  deps_spaced="${deps_csv//,/ }"
  if [ -z "$deps_spaced" ]; then
    return 0
  fi

  echo "Installing system packages: $deps_spaced"
  run_cmd apt-get update -y
  run_cmd apt-get install -y $deps_spaced
}

stop_pid_file() {
  local file="$1"
  if [ -f "$file" ]; then
    local pid
    pid="$(cat "$file")"
    if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
      kill "$pid" || true
      sleep 1
      if ps -p "$pid" >/dev/null 2>&1; then
        kill -9 "$pid" || true
      fi
    fi
    rm -f "$file"
  fi
}

DEPLOY_MODE="${DEPLOY_MODE:-$(env_get DEPLOY_MODE process)}"
INSTALL_DEPS="${INSTALL_DEPS:-$(env_get INSTALL_DEPS 1)}"
INSTALL_VISION="${INSTALL_VISION:-$(env_get INSTALL_VISION 0)}"
INSTALL_SYSTEM_DEPS="${INSTALL_SYSTEM_DEPS:-$(env_get INSTALL_SYSTEM_DEPS 0)}"
SYSTEM_DEPS="${SYSTEM_DEPS:-$(env_get SYSTEM_DEPS ffmpeg,redis-server,curl)}"
ENABLE_UFW="${ENABLE_UFW:-$(env_get ENABLE_UFW 0)}"
UFW_ALLOW_PORTS="${UFW_ALLOW_PORTS:-$(env_get UFW_ALLOW_PORTS 22,8000)}"
UFW_AUTO_ENABLE="${UFW_AUTO_ENABLE:-$(env_get UFW_AUTO_ENABLE 0)}"
API_HOST="${API_HOST:-$(env_get API_HOST 0.0.0.0)}"
API_PORT="${API_PORT:-$(env_get API_PORT 8000)}"
REDIS_PORT="${REDIS_PORT:-$(env_get REDIS_PORT 6379)}"

setup_ufw "$ENABLE_UFW" "$UFW_ALLOW_PORTS" "$UFW_AUTO_ENABLE"
install_system_deps "$INSTALL_SYSTEM_DEPS" "$SYSTEM_DEPS"

if [ "$DEPLOY_MODE" = "docker" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not found. Install Docker or set DEPLOY_MODE=process"
    exit 1
  fi

  run_cmd docker compose --env-file .env -f infra/compose/docker-compose.yml up -d --build --remove-orphans
  wait_for_health "http://127.0.0.1:${API_PORT}/api/v1/health" 80

  echo "Setup complete (docker mode)."
  echo "API URL: http://127.0.0.1:${API_PORT}"
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but not found in PATH."
  exit 1
fi

if [ ! -d venv ]; then
  uv venv venv
fi

source venv/bin/activate

if [ "$INSTALL_DEPS" = "1" ]; then
  uv pip install -e .
fi
if [ "$INSTALL_VISION" = "1" ]; then
  echo "Installing vision dependencies (this can take a while)..."
  uv pip install -e '.[vision]'
fi

if command -v redis-cli >/dev/null 2>&1; then
  if ! redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1; then
    if ! command -v redis-server >/dev/null 2>&1; then
      echo "redis-server not found. Install Redis or use DEPLOY_MODE=docker"
      exit 1
    fi
    echo "Starting Redis on port ${REDIS_PORT}..."
    redis-server --port "$REDIS_PORT" --daemonize yes --pidfile "$ROOT_DIR/logs/redis.pid"
    sleep 1
  fi
  if ! redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1; then
    echo "Redis failed to start on port ${REDIS_PORT}."
    exit 1
  fi
fi

stop_pid_file "logs/api.pid"
stop_pid_file "logs/worker.pid"

nohup venv/bin/uvicorn api.app.main:app --host "$API_HOST" --port "$API_PORT" > logs/api.log 2>&1 &
echo $! > logs/api.pid

nohup venv/bin/python -m worker.app.main > logs/worker.log 2>&1 &
echo $! > logs/worker.pid

wait_for_health "http://127.0.0.1:${API_PORT}/api/v1/health" 60

echo "Setup complete (process mode)."
echo "API PID: $(cat logs/api.pid)"
echo "Worker PID: $(cat logs/worker.pid)"
echo "Health: $(curl -sS http://127.0.0.1:${API_PORT}/api/v1/health)"
