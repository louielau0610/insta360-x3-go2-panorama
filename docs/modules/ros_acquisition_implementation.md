# ROS2 Dual-Storage Acquisition Implementation

- `native/x5_stream_recorder.cc:36` defines `RecordingDelegate`; stream index 0 is written both to the recoverable H.264 file and, when configured, to the live FIFO.
- `native/x5_stream_recorder.cc:112` parses `--stream0-fifo`, owns CameraSDK, and retains the existing discovery/live-view/metadata behavior.
- `x5_ros/common.py:10` validates and splits side-by-side BGR frames.
- `x5_ros/common.py:19` and `:28` JPEG-encode images and decode ROS compressed payloads without `cv_bridge`.
- `x5_ros/common.py:52` implements `RawPairWriter`, which writes lossless BMP pairs and flushes their exact timestamp CSV index.
- `x5_ros/publisher.py:23` builds `sensor_msgs/CompressedImage` messages using `array.array` to avoid Foxy Python's per-byte debug validation.
- `x5_ros/publisher.py:42` defines the single `x5_dual_fisheye_publisher` node and its two reliable compressed-image publishers.
- `x5_ros/publisher.py:72` orchestrates CameraSDK/FIFO/GStreamer decoding, 10 Hz selection, raw BMP writing, JPEG publication, and direct compressed bag writing.
- `x5_ros/bag_writer.py:26` implements the Foxy-compatible compressed-image SQLite schema, direct CDR writes, 30-pair WAL commits, timestamp index, and version-4 metadata.
- `x5_ros/export_pairs.py:16` defines the exact-stamp two-topic JPEG bag exporter used during slowed playback.
- `x5_ros/postprocess_pairs.py:17` accepts either canonical raw BMP pairs or decoded bag-export PNG pairs and produces panorama, six cube faces, and the 300° view.
- `scripts/record_rosbag_raw.sh:1` estimates raw-disk capacity, runs capture, validates exact raw/bag timestamps and rates, calls `ros2 bag info`, and hashes the run.
- `scripts/export_rosbag_raw.sh:1` replays the compressed bag at 0.2x by default and drives the decoder/exporter.
- `tests/test_acquisition.py:25` protects raw BMP equality, JPEG decoding, side-by-side ordering, timestamp CSV serialization, and existing field-acquisition contracts.
