#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-$ROOT/config/go2_x5_v4l2.json}"
DURATION="${2:-600}"
OUTPUT_ROOT="$(python3 -c "import json; print(json.load(open('$CONFIG'))['recording']['output_root'])")"
LABEL="$(python3 -c "import json; print(json.load(open('$CONFIG'))['experiment']['label'])")"
RUN_DIR="$OUTPUT_ROOT/$(date +%Y%m%d_%H%M%S)_${LABEL}"
mkdir -p "$RUN_DIR"
cp "$CONFIG" "$RUN_DIR/config.json"
if [[ -n "${VENV:-}" ]]; then
  DEPLOY_VENV="$VENV"
elif [[ -x "$ROOT/.venv-jetson/bin/python" ]]; then
  DEPLOY_VENV="$ROOT/.venv-jetson"
else
  DEPLOY_VENV="$ROOT/.venv-go2"
fi
source "$DEPLOY_VENV/bin/activate"
START_NS="$(date +%s%N)"

cleanup() {
  [[ -n "${TELEMETRY_PID:-}" ]] && kill -TERM "$TELEMETRY_PID" 2>/dev/null || true
  wait "${TELEMETRY_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

go2-collect telemetry --config "$CONFIG" --run-dir "$RUN_DIR" --duration "$DURATION" &
TELEMETRY_PID=$!
set +e
X5_ARGS=(--output "$RUN_DIR/x5" --duration "$DURATION")
if python -c "import json; raise SystemExit(not json.load(open('$CONFIG'))['camera'].get('in_camera_stitching', False))"; then
  X5_ARGS+=(--stitched)
fi
"$ROOT/bin/x5-stream-recorder" "${X5_ARGS[@]}"
X5_STATUS=$?
wait "$TELEMETRY_PID"
TELEMETRY_STATUS=$?
set -e
TELEMETRY_PID=""
python - "$RUN_DIR" "$CONFIG" "$X5_STATUS" "$TELEMETRY_STATUS" "$START_NS" <<'PY'
import json
import subprocess
import sys
import time
from pathlib import Path

run_dir, config_path = Path(sys.argv[1]), Path(sys.argv[2])
x5_status, telemetry_status, started_ns = map(int, sys.argv[3:6])
try:
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, cwd=config_path.resolve().parent.parent
    ).strip()
except Exception:
    revision = None
x5_device = run_dir / "x5" / "x5_device.json"
manifest = {
    "status": "complete" if x5_status == telemetry_status == 0 else "failed",
    "started_unix_ns": started_ns,
    "finished_unix_ns": time.time_ns(),
    "git_revision": revision,
    "config": json.loads(config_path.read_text(encoding="utf-8")),
    "x5_exit_status": x5_status,
    "telemetry_exit_status": telemetry_status,
    "x5_device": json.loads(x5_device.read_text()) if x5_device.exists() else None,
}
(run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
PY
go2-collect checksum "$RUN_DIR"
echo "Run complete: $RUN_DIR"
if [[ "$X5_STATUS" -ne 0 || "$TELEMETRY_STATUS" -ne 0 ]]; then
  exit 1
fi
