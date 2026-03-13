#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

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

if [ "$DEPLOY_MODE" = "docker" ]; then
  if command -v docker >/dev/null 2>&1; then
    run_cmd docker compose --env-file .env -f infra/compose/docker-compose.yml down --remove-orphans || true
  fi
  echo "Stopped docker services."
  exit 0
fi

stop_pid_file "logs/api.pid"
stop_pid_file "logs/worker.pid"
stop_pid_file "logs/redis.pid"

echo "Stopped process-mode services (API/worker/managed Redis)."
