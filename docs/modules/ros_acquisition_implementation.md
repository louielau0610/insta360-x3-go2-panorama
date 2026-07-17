# ROS2 Raw-Fisheye Acquisition Implementation

- `native/x5_stream_recorder.cc:36` defines `RecordingDelegate`; stream index 0 is written both to the recoverable H.264 file and, when configured, to the live FIFO.
- `native/x5_stream_recorder.cc:112` parses `--stream0-fifo`, owns CameraSDK, and retains the existing discovery/live-view/metadata behavior.
- `x5_ros/common.py:10` validates/splits side-by-side BGR, converts ROS images without cv_bridge, and reads/writes exact timestamp-pair CSV files and lossless PNGs.
- `x5_ros/publisher.py:23` builds `sensor_msgs/Image` messages using `array.array` to avoid Foxy Python's per-byte debug validation.
- `x5_ros/publisher.py:44` defines the single `x5_dual_fisheye_publisher` node and its two reliable image publishers.
- `x5_ros/publisher.py:67` orchestrates CameraSDK/FIFO/GStreamer decoding, 10 Hz selection, paired publication, and optional direct bag writing.
- `x5_ros/bag_writer.py:26` implements the Foxy-compatible SQLite schema, direct CDR writes, 30-pair WAL commits, timestamp index, and version-4 rosbag metadata.
- `x5_ros/export_pairs.py:16` defines the exact-stamp two-topic exporter used during slowed bag playback.
- `x5_ros/postprocess_pairs.py:17` processes exported pairs into panorama, six cube faces, and three 100° perspective panels plus their 300° contact sheet.
- `scripts/record_rosbag_raw.sh:1` estimates raw storage, runs live capture/publication/bagging, validates rate/pair counts, calls `ros2 bag info`, and hashes the run.
- `scripts/export_rosbag_raw.sh:1` replays at 0.2x by default and drives the lossless exporter.
- `tests/test_acquisition.py:16` protects side-by-side ordering and exact pair CSV serialization in addition to the existing acquisition tests.
