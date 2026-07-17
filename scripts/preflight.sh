#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-$ROOT/config/go2_x5_v4l2.json}"
source "${VENV:-$ROOT/.venv-go2}/bin/activate"

echo "=== network ==="
ip -brief address
echo "=== camera devices ==="
v4l2-ctl --list-devices || true
echo "=== storage ==="
df -h
echo "=== acquisition preflight ==="
go2-collect preflight --config "$CONFIG"
