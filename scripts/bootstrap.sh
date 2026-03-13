#!/usr/bin/env bash
set -euo pipefail

mkdir -p data/uploads data/artifacts data/reports
cp -n .env.example .env || true

echo "Bootstrap complete."
