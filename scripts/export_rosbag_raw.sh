#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAG="${1:?usage: export_rosbag_raw.sh BAG_DIR OUTPUT_DIR}"
OUTPUT="${2:?usage: export_rosbag_raw.sh BAG_DIR OUTPUT_DIR}"
set +u
source /home/unitree/unitree_ros2/setup.sh
source "$ROOT/.venv-jetson/bin/activate"
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

python -m x5_ros.export_pairs "$OUTPUT" >"${OUTPUT}.log" 2>&1 &
EXPORT_PID=$!
trap 'kill -INT "$EXPORT_PID" 2>/dev/null || true' EXIT INT TERM
sleep 1
ros2 bag play --rate "${PLAY_RATE:-0.2}" "$BAG"
wait "$EXPORT_PID"
trap - EXIT INT TERM
cat "${OUTPUT}.log"
