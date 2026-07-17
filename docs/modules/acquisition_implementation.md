# GO2 Field Acquisition Implementation

- `go2_experiment/recorder.py:22` loads and validates the four-section JSON configuration.
- `go2_experiment/recorder.py:44` provides the hardware-free synthetic source used by tests and rehearsal.
- `go2_experiment/recorder.py:77` defines `ExperimentRecorder`, which checks storage/source shape, gates on GO2 readiness, records MJPEG and timestamps, schedules 6 Hz panorama generation, and always closes with a manifest.
- `go2_experiment/recorder.py:144` runs the non-recording camera/GO2/storage preflight.
- `go2_experiment/recorder.py:205` executes a bounded or signal-terminated camera run.
- `go2_experiment/recorder.py:305` and `:313` hash closed artifacts and write `SHA256SUMS`.
- `go2_experiment/telemetry.py:21` implements a bounded asynchronous JSONL writer so DDS callbacks do not perform disk I/O.
- `go2_experiment/telemetry.py:54` initializes Unitree SDK2 on the configured interface and subscribes to GO2 low/high-frequency state.
- `go2_experiment/cli.py:12` exposes `preflight`, `record`, `telemetry`, and `checksum` commands.
- `native/x5_stream_recorder.cc:36` implements the CameraSDK delegate that saves the primary and optional secondary encoded streams, chunk offsets/timestamps, gyro, and exposure.
- `native/x5_stream_recorder.cc:112` allows 15 seconds for X5 USB discovery, configures live view, records until duration/signal, and requires non-empty stream index 0 output.
- `scripts/install_go2.sh:1` creates the Python environment and installs the official Unitree SDK2 Python source at pinned commit `e4cd91f`.
- `scripts/install_jetson.sh:1` creates the Python 3.8-compatible on-robot environment, preserves JetPack OpenCV, and installs the same pinned Unitree SDK2 source.
- `scripts/configure_go2_network.sh:1` applies the direct-Ethernet host address and verifies the robot is reachable.
- `scripts/build_x5_sdk_recorder.sh:1` selects a bundled SDK, the GO2 Jetson SDK, or `X5_SDK_ARCHIVE`, then builds the native recorder.
- `scripts/preflight.sh:1`, `scripts/record.sh:1`, and `scripts/record_x5_sdk_go2.sh:1` are the field operator entry points.
- `tests/test_acquisition.py:16` verifies telemetry serialization, configuration rejection, synthetic acquisition artifacts, manifest completion, checksums, and ROS image-pair helpers.

The generic decoded-source path is the only path that performs online custom stitching. The CameraSDK path prioritizes lossless acquisition of the encoded preview streams and records enough timing metadata for offline decoding/stitching.
