#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

./stop.sh
INSTALL_VISION="${INSTALL_VISION:-0}" ./setup.sh
