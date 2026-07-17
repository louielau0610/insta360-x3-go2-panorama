# ROS2 Dual-Storage Acquisition Principles

## Responsibility and boundary

The ROS adapter preserves decoded X5 lens pixels on disk and exposes synchronized compressed ROS2 image topics. It does not control the GO2, invent camera intrinsics, or stitch online.

CameraSDK has one owner. `x5_dual_fisheye_publisher` receives the single `3840x1920` H.264 preview through a FIFO, decodes BGR, assigns the left square to `fisheye1` and the right square to `fisheye2`, and assigns both one ROS timestamp. Two processes must never open the X5 independently.

## Dual-storage contract

For every selected 10 Hz frame, the adapter first preserves two `1920x1920` BGR images as uncompressed BMP files under `raw/fisheye1` and `raw/fisheye2`. `raw/pairs.csv` is flushed after both files succeed and is the authoritative exact-timestamp index. BMP is chosen over PNG to avoid spending the Jetson CPU budget on lossless compression during acquisition.

The same pixels are JPEG-encoded at configurable quality 1–100 (default 85), published as `sensor_msgs/msg/CompressedImage` on `/fisheye1/image_compressed` and `/fisheye2/image_compressed`, and CDR-serialized into rosbag2. Compression changes image values and is intended for ROS transport/replay, not as the canonical post-processing source.

The X5 live-preview input was already H.264 before decoding, so “raw” here means the first decoded BGR pixels without another lossy encode; it does not mean sensor-native DNG. No `CameraInfo` is published until trustworthy per-lens ROS calibration exists.

## Throughput and recoverability

Two uncompressed BMP images at 10 Hz require approximately 221 MB/s or 13.3 GB/minute. Every run estimates this raw requirement and requires 1.5 times the expected capacity. The compressed bag size is variable with JPEG quality and scene detail.

The SQLite writer uses WAL, normal synchronization, and 30-pair commits. An interruption can lose the current bag transaction, while each already indexed raw BMP pair remains independently readable. A completed run must have equal compressed-topic counts, exact timestamp equality with `raw/pairs.csv`, at least 80% of target rate, valid `ros2 bag info`, and verified SHA-256 files.

## Offline contract

Canonical post-processing reads `raw/pairs.csv` and BMP files directly. Bag playback remains available for ROS consumers; its exporter decodes `CompressedImage` messages to paired PNG files using exact ROS nanoseconds and fails on missing pairs. Both paths feed the same panorama, `F/R/B/L/U/D` cubemap, and 300° view processor, but only the raw BMP path avoids the additional JPEG loss.
