# X5 Raw-Disk and Compressed-Rosbag Workflow

## Data contract

Each selected X5 preview frame becomes one timestamped pair:

- `raw/fisheye1/<timestamp>.bmp` and `raw/fisheye2/<timestamp>.bmp`: `1920x1920` lossless decoded BGR pixels.
- `raw/pairs.csv`: exact timestamp and relative path for every completed raw pair.
- `/fisheye1/image_compressed` and `/fisheye2/image_compressed`: synchronized JPEG `sensor_msgs/msg/CompressedImage` topics.
- `bag/`: Foxy-compatible rosbag2 SQLite containing the two compressed topics.
- `x5/`: the original X5 H.264 stream plus camera timestamps, gyro, and exposure sidecars.

JPEG quality defaults to 85 and only affects ROS/bag data. It never changes the raw BMP files.

## Storage budget

At 10 paired frames/s, direct-disk raw BGR requires about 13.3 GB/minute. Plan on 15 GB/minute with filesystem and run-metadata headroom. JPEG rosbag size varies with quality, motion, texture, and noise and must be measured on a representative run before planning long captures.

The recorder requires 1.5 times the estimated raw payload to be free before starting. Prefer short independent bags and retain sufficient capacity for clean shutdown and checksum verification.

## Record

```bash
ssh unitree@10.40.8.222
cd ~/ws_datacollection

# 10 seconds, 10 paired frames/s, JPEG quality 85.
bash scripts/record_rosbag_raw.sh 10 10

# Optional lower bag bitrate.
JPEG_QUALITY=75 bash scripts/record_rosbag_raw.sh 10 10
```

The output directory name ends in `_x5_dual_storage`. A successful run writes `bag_validation.json` with pair rate, raw bytes, compressed bag bytes, and JPEG quality.

## Canonical offline processing

Use the lossless raw directory directly:

```bash
source .venv-jetson/bin/activate
x5-ros-postprocess \
  runs/<run>/raw \
  runs/<run>_postprocess
```

This path does not introduce JPEG loss after the X5 H.264 preview decode.

## Rosbag replay/export

```bash
source ~/unitree_ros2/setup.sh
ros2 bag info runs/<run>/bag

PLAY_RATE=0.2 bash scripts/export_rosbag_raw.sh \
  runs/<run>/bag \
  runs/<run>_bag_export
```

The exporter decodes bag JPEG messages and creates paired PNG files for inspection. These files are not equivalent to the canonical BMP originals because JPEG is lossy.

## Completion rules

- Raw pair count equals both compressed topic counts.
- Every raw timestamp exactly equals its corresponding bag timestamp.
- Pair rate is at least 80% of target.
- `ros2 bag info` accepts the bag.
- `SHA256SUMS` verifies before the source data is moved or deleted.
- `CameraInfo` remains absent until verified per-lens ROS calibration exists.
- GO2 telemetry remains in the subscriber-only acquisition path; no motion commands are published.
