# X5 ROS2 Raw Bag Workflow

## Verified environment and result

The GO2 Jetson uses ROS2 Foxy, `rclpy`, `sensor_msgs`, CycloneDDS, GStreamer 1.16, JetPack OpenCV 4.2, and rosbag2 SQLite. The final rate/validation run is:

`/home/unitree/ws_datacollection/runs/20260717_141039_x5_rosbag_raw`

- Camera: Insta360 X5 `v1.11.6`, serial `IAHEA26067UB3R`.
- Duration represented in bag: 1.981 s.
- `/fisheye1/image_raw`: 20 messages.
- `/fisheye2/image_raw`: 20 messages.
- Pair rate: 10.10 Hz against a 10 Hz target.
- Image contract: `1920x1920`, `bgr8`, uncompressed CDR.
- Bag size: 422.4 MiB; approximately 13 GB/minute at this rate.
- X5 encoded stream and gyro/exposure sidecars were retained beside the bag.
- All run files passed `sha256sum -c SHA256SUMS`.
- The separate end-to-end run `20260717_140725_x5_rosbag_raw` replayed and exported 29/29 exact pairs with zero unmatched timestamps.
- Two of those exported pairs completed panorama, six-face cubemap, and 300° post-processing.

## Record

```bash
ssh unitree@10.40.8.222
cd ~/ws_datacollection

# 10 seconds at a target 10 paired frames/s: expect about 2.2 GB raw payload.
bash scripts/record_rosbag_raw.sh 10 10
```

At the measured rate, budget approximately 13 GB/minute. With 337 GB free, the mathematical maximum is roughly 25 minutes, but field runs should keep substantial free-space headroom and use shorter independent bags.

## Inspect and export

```bash
source ~/unitree_ros2/setup.sh
ros2 bag info runs/<run>/bag

PLAY_RATE=0.2 bash scripts/export_rosbag_raw.sh \
  runs/<run>/bag \
  runs/<run>_export
```

The export contains `fisheye1/*.png`, `fisheye2/*.png`, `pairs.csv`, and `export_report.json`. PNG is lossless and is used only after bag capture; bag image messages remain uncompressed BGR.

## Offline post-process

```bash
source .venv-jetson/bin/activate
x5-ros-postprocess \
  runs/<run>_export \
  runs/<run>_postprocess
```

Each timestamp directory contains `panorama.jpg`, `cube_F/R/B/L/U/D.jpg`, `view_left/front/right_100.jpg`, and `view_300_contact.jpg`.

## Known constraints

- The live X5 preview is H.264 before ROS decoding; “original” means no additional ROS-layer lossy compression.
- `CameraInfo` is intentionally absent until a verified ROS calibration is produced.
- GO2 telemetry remains in the existing subscriber-only JSONL path; this first raw bag contains the two image topics.
- The direct SQLite writer matches Foxy rosbag2 schema and was verified by `ros2 bag info` and `ros2 bag play`. Always stop normally and verify checksums before power-off.
