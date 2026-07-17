#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-$ROOT/config/go2_x5_v4l2.json}"
DURATION="${2:-}"
source "${VENV:-$ROOT/.venv-go2}/bin/activate"

set +e
if [[ -n "$DURATION" ]]; then
  go2-collect record --config "$CONFIG" --duration "$DURATION"
else
  go2-collect record --config "$CONFIG"
fi
STATUS=$?
set -e

LATEST="$(find "$(python3 -c "import json; print(json.load(open('$CONFIG'))['recording']['output_root'])")" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
go2-collect checksum "$LATEST"
echo "Run complete: $LATEST"
exit "$STATUS"
