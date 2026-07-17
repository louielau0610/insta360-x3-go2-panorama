#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DURATION="${1:-10}"
PUBLISH_FPS="${2:-10}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT/runs}"
RUN_DIR="$OUTPUT_ROOT/$(date +%Y%m%d_%H%M%S)_x5_rosbag_raw"
mkdir -p "$RUN_DIR"

set +u
source /home/unitree/unitree_ros2/setup.sh
source "$ROOT/.venv-jetson/bin/activate"
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

python - "$OUTPUT_ROOT" "$DURATION" "$PUBLISH_FPS" <<'PY'
import shutil, sys
root, duration, fps = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
expected = 1920 * 1920 * 3 * 2 * fps * duration
free = shutil.disk_usage(root).free
if free < expected * 1.5:
    raise SystemExit(f"insufficient disk: need 1.5x {expected / 1e9:.2f} GB, have {free / 1e9:.2f} GB")
print(f"Expected raw image payload: {expected / 1e9:.2f} GB")
PY

python -m x5_ros.publisher \
  --recorder "$ROOT/bin/x5-stream-recorder" \
  --capture-output "$RUN_DIR/x5" \
  --duration "$DURATION" \
  --publish-fps "$PUBLISH_FPS" \
  --bag-output "$RUN_DIR/bag" \
  | tee "$RUN_DIR/publisher.log"
ros2 bag info "$RUN_DIR/bag" | tee "$RUN_DIR/bag_info.txt"
python - "$RUN_DIR/bag/bag_0.db3" "$RUN_DIR/bag_validation.json" "$PUBLISH_FPS" <<'PY'
import json, sqlite3, sys
database, output, target_fps = sys.argv[1], sys.argv[2], float(sys.argv[3])
connection = sqlite3.connect(database)
rows = list(connection.execute(
    "SELECT topic_id, COUNT(*), MIN(timestamp), MAX(timestamp) "
    "FROM messages GROUP BY topic_id ORDER BY topic_id"
))
if len(rows) != 2 or rows[0][1] != rows[1][1] or rows[0][2:] != rows[1][2:]:
    raise SystemExit(f"unpaired raw image topics: {rows}")
count, first_stamp, last_stamp = rows[0][1:]
duration = max((last_stamp - first_stamp) / 1e9, 1e-9)
rate = count / duration
report = {"pairs": count, "duration_sec": duration, "pair_rate_hz": rate, "target_hz": target_fps}
open(output, "w", encoding="utf-8").write(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
if rate < target_fps * 0.8:
    raise SystemExit(f"raw bag rate {rate:.2f} Hz is below 80% of target {target_fps:.2f} Hz")
PY
go2-collect checksum "$RUN_DIR"
echo "ROS bag run complete: $RUN_DIR"
