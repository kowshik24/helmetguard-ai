#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

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

stop_pid_file "logs/api.pid"
stop_pid_file "logs/worker.pid"

if [ -f "logs/redis.pid" ]; then
  stop_pid_file "logs/redis.pid"
fi

echo "Stopped API/worker (and Redis if started by setup script)."
