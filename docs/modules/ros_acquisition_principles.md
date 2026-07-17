# ROS2 Raw-Fisheye Acquisition Principles

## Responsibility and boundary

The ROS adapter exposes the X5 lenses as synchronized ROS2 image topics and stores the same uncompressed messages in rosbag2. It does not control the GO2, alter lens pixels, invent camera intrinsics, or perform online stitching.

CameraSDK has one owner. `x5_dual_fisheye_publisher` receives the single `3840x1920` H.264 preview through a FIFO, decodes BGR, assigns the left square to `fisheye1` and the right square to `fisheye2`, and publishes both with one ROS timestamp. Two processes must never open the X5 independently.

## Original-pixel contract

Each topic is `sensor_msgs/msg/Image`, `1920x1920`, `bgr8`, with `step=5760`. Rosbag stores CDR-serialized uncompressed messages. The input was already encoded by the X5 live-preview H.264 path, but the ROS layer applies no JPEG or other additional lossy compression.

No `CameraInfo` is published until a trustworthy per-lens ROS calibration is available. The existing X5 factory profile remains internal to the stitcher and must not be misrepresented as a pinhole matrix.

## Throughput and recoverability

Two raw images at 10 Hz produce approximately 221 MB/s of payload, about 13 GB/minute. Every run performs a disk-space estimate and requires 1.5 times the expected payload. The SQLite writer uses WAL, normal synchronization, and commits every 30 pairs; an interrupted run can lose the current transaction but previously committed data remains recoverable.

The node publishes the topics for ROS visibility but writes rosbag2 in-process. Foxy cross-process DDS/rosbag testing dropped large messages and produced unequal topic counts; direct CDR writing produced equal counts near 10 Hz. Every completed bag must have equal topic counts, identical first/last timestamps, at least 80% of target rate, a valid `ros2 bag info`, and verified SHA-256 files.

## Offline contract

Bag playback is slowed to 0.2x by default so lossless PNG export does not drop messages. Pairing uses exact ROS nanoseconds, never nearest-neighbor substitution. Missing or unmatched stamps fail export. Post-processing consumes paired PNG files and produces panorama, six `F/R/B/L/U/D` faces, and left/front/right 100° panels covering the forward 300° sector.
