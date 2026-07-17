#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DURATION="${1:-10}"
PUBLISH_FPS="${2:-10}"
JPEG_QUALITY="${JPEG_QUALITY:-85}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT/runs}"
RUN_DIR="$OUTPUT_ROOT/$(date +%Y%m%d_%H%M%S)_x5_dual_storage"
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
print(f"Expected direct-disk raw image payload: {expected / 1e9:.2f} GB")
PY

python -m x5_ros.publisher \
  --recorder "$ROOT/bin/x5-stream-recorder" \
  --capture-output "$RUN_DIR/x5" \
  --duration "$DURATION" \
  --publish-fps "$PUBLISH_FPS" \
  --jpeg-quality "$JPEG_QUALITY" \
  --raw-output "$RUN_DIR/raw" \
  --bag-output "$RUN_DIR/bag" \
  | tee "$RUN_DIR/publisher.log"
ros2 bag info "$RUN_DIR/bag" | tee "$RUN_DIR/bag_info.txt"
python - "$RUN_DIR/bag/bag_0.db3" "$RUN_DIR/raw/pairs.csv" "$RUN_DIR/bag_validation.json" "$PUBLISH_FPS" "$JPEG_QUALITY" <<'PY'
import csv, json, sqlite3, sys
from pathlib import Path
database, pairs_csv, output = sys.argv[1:4]
target_fps, jpeg_quality = float(sys.argv[4]), int(sys.argv[5])
connection = sqlite3.connect(database)
rows = list(connection.execute(
    "SELECT topics.name, topics.type, COUNT(*), MIN(timestamp), MAX(timestamp) "
    "FROM messages JOIN topics ON topics.id=messages.topic_id "
    "GROUP BY topics.id ORDER BY topics.id"
))
if len(rows) != 2 or rows[0][2] != rows[1][2] or rows[0][3:] != rows[1][3:]:
    raise SystemExit(f"unpaired compressed image topics: {rows}")
if any(row[1] != "sensor_msgs/msg/CompressedImage" for row in rows):
    raise SystemExit(f"unexpected bag topic types: {rows}")
count, first_stamp, last_stamp = rows[0][2:]
raw_rows = list(csv.DictReader(open(pairs_csv, newline="", encoding="utf-8")))
if len(raw_rows) != count:
    raise SystemExit(f"raw/bag pair mismatch: raw={len(raw_rows)}, bag={count}")
bag_stamps = [row[0] for row in connection.execute(
    "SELECT timestamp FROM messages WHERE topic_id=1 ORDER BY timestamp"
)]
raw_stamps = [int(row["timestamp_ns"]) for row in raw_rows]
if raw_stamps != bag_stamps:
    raise SystemExit("raw and compressed-bag timestamps do not match exactly")
duration = max((last_stamp - first_stamp) / 1e9, 1e-9)
rate = count / duration
run = Path(database).parents[1]
raw_bytes = sum(path.stat().st_size for path in (run / "raw").rglob("*.bmp"))
bag_bytes = Path(database).stat().st_size
report = {
    "pairs": count, "duration_sec": duration, "pair_rate_hz": rate,
    "target_hz": target_fps, "jpeg_quality": jpeg_quality,
    "raw_bytes": raw_bytes, "compressed_bag_bytes": bag_bytes,
}
open(output, "w", encoding="utf-8").write(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
if rate < target_fps * 0.8:
    raise SystemExit(f"compressed bag rate {rate:.2f} Hz is below 80% of target {target_fps:.2f} Hz")
PY
go2-collect checksum "$RUN_DIR"
echo "Dual raw-disk/compressed-bag run complete: $RUN_DIR"
