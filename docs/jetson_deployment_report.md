# GO2 Jetson Deployment Report

Date: 2026-07-17

## Outcome

The `ws_datacollection` project is deployed at `/home/unitree/ws_datacollection` on the GO2-mounted Jetson and runs under its native Ubuntu 20.04/Python 3.8 environment. Live X5 CameraSDK capture, camera IMU/exposure metadata, real GO2 read-only telemetry, custom stitching, cubemap generation, manifests, and checksums were all verified on the robot computer.

The 60-second stationary deployment pilot is complete. No robot motion was commanded or tested; the acquisition code remains subscriber-only. Normal field safety checks are still required before a formal moving run.

## Target environment

- Host: GO2-mounted NVIDIA Jetson/Tegra, `aarch64`.
- Kernel: `5.10.104-tegra`.
- OS: Ubuntu 20.04.5 LTS.
- Python: 3.8.10.
- Storage: 469 GB root filesystem, 338 GB free during deployment.
- Internal GO2 interface: `eth0`, `192.168.123.18/24`.
- Motion controller: `192.168.123.161`, approximately 0.2 ms ping during deployment.
- External management interface: `wlan0`, `10.40.8.222/18`.

## Installed layout

```text
~/ws_datacollection/
├── .venv-jetson/              Python 3.8 deployment environment
├── .vendor/unitree_sdk2_python/
├── bin/x5-stream-recorder     ARM64 CameraSDK recorder
├── config/jetson_go2_smoke.json
├── config/jetson_go2_x5_sdk.json
├── runs/                      Verification and future acquisition runs
├── testdata/                  Deployment-only decoded X5 smoke input
└── docs/                      Design and deployment documentation
```

`scripts/install_jetson.sh` uses JetPack's system OpenCV, pins Python 3.8-compatible numerical packages, builds CycloneDDS Python bindings against the robot's existing CycloneDDS 0.10.2 installation, and installs Unitree SDK2 Python at commit `e4cd91f`.

## Verification results

### Package and contract tests

`python -m unittest discover -s tests -v` passed all 3 tests on the Jetson.

### Offline real X5 frame

The deployment input was decoded from sample 003 DNG outside the live timing path and transferred as a quality-95 BGR JPEG.

- Input: `5888x2944x3` side-by-side dual fisheye.
- Panorama: `1280x640x3`.
- Cubemap: six `512x512x3` faces in `F/R/B/L/U/D` order.
- Repetitions: 6.
- Mean: 63.83 ms.
- p95: 106.61 ms.
- Throughput: 15.67 FPS.
- Report: `runs/x5_frame_smoke_01/frame_report.json`.

This is a deployment/performance smoke test, not a substitute for live-camera visual inspection or held-out calibration validation.

### GO2 telemetry-only run

A 10-second read-only DDS run on `eth0` produced:

- 477 LowState records, 0 queue drops.
- 124 SportModeState records, 0 queue drops.
- Output: `runs/go2_telemetry_smoke_01/telemetry/`.

### Combined algorithm and GO2 run

A 5-second synthetic-camera plus real-GO2 telemetry run completed successfully:

- Source frames: 62 at 12.22 FPS.
- Processed panorama/cubemap frames: 30 at 5.91 FPS.
- Processing mean: 51.65 ms; p95: 123.42 ms.
- LowState: 244 written, 0 dropped.
- SportModeState: 69 written, 0 dropped.
- Camera read failures: 0.
- Manifest status: `complete`.
- `sha256sum -c SHA256SUMS`: all 7 artifacts passed.
- Output: `runs/jetson_combined_01/`.

### Live X5 and GO2 joint run

The X5 was connected directly over USB, placed in Android mode, and discovered by CameraSDK 2.1.1.

- Camera: Insta360 X5, serial `IAHEA26067UB3R`, firmware `v1.11.6`.
- USB link reported by Linux: 480 Mb/s (USB 2.0 High-Speed).
- Capture mode: non-stitched `3840x1920` dual-fisheye preview at approximately 29.97 FPS.
- Duration: 15 seconds.
- Primary camera chunks: 449; primary stream size: 14,680,013 bytes.
- Secondary stream chunks: 0. CameraSDK stream index 1 is optional for this X5 preview mode.
- GO2 telemetry: 714 LowState and 195 SportModeState records, with zero queue drops.
- X5 gyro CSV: 842,244 bytes; exposure CSV: 23,410 bytes.
- Recorder and telemetry exit status: both 0; manifest status: `complete`.
- All 19 final artifacts passed `sha256sum -c SHA256SUMS` after live-frame processing.
- Output: `runs/20260717_124312_jetson_go2_x5_sdk/`.

### Algorithm on a live X5 frame

The first decoded frame from the joint run was processed on the Jetson by the deployed custom pipeline:

- Input: `3840x1920x3` side-by-side dual fisheye.
- Panorama: `1280x640x3`.
- Cubemap: six `512x512x3` faces in `F/R/B/L/U/D` order.
- Repetitions: 6.
- Mean: 61.50 ms; p95: 107.36 ms; throughput: 16.26 FPS.
- The generated panorama was opened and visually confirmed to contain the full room scene.
- Report: `runs/20260717_124312_jetson_go2_x5_sdk/algorithm_smoke/frame_report.json`.

### Mandatory 60-second stationary pilot

The post-reconnect pilot completed successfully at `runs/20260717_125057_jetson_go2_x5_sdk/`:

- Manifest status: `complete`; X5 and telemetry exit status: both 0.
- X5 primary chunks: 1,797; primary stream: 62,703,634 bytes.
- LowState: 2,850 records; SportModeState: 751 records; queue drops: 0.
- Gyro CSV: 30,512 data rows; exposure CSV: 1,797 data rows.
- A decoded `3840x1920` live frame produced a `1280x640` panorama and all six `512x512` cubemap faces.
- Algorithm mean: 61.53 ms; p95: 107.94 ms; throughput: 16.25 FPS across six repetitions.
- The panorama was opened and visually confirmed to contain the complete stationary room scene.
- All 19 final artifacts passed `sha256sum -c SHA256SUMS`.

Immediately after the USB reconnect, one attempt at `runs/20260717_124816_jetson_go2_x5_sdk/` started before CameraSDK finished its second enumeration. It was correctly retained with manifest status `failed`, X5 exit status 3, and successful GO2 telemetry. A three-second retry then succeeded. The native recorder now retries discovery every 500 ms for at most 15 seconds, while still failing explicitly if the camera never becomes ready.

### First controlled-motion pilot

The first 90-second operator-controlled run was retained at `runs/20260717_125935_jetson_go2_x5_motion_pilot/`:

The exported metrics and representative images are collected in `docs/motion_pilot_data_report.md`.

- Manifest status: `complete`; X5 and telemetry exit status: both 0.
- X5 primary chunks: 2,699; primary stream: 94,299,036 bytes.
- LowState: 4,274 records; SportModeState: 1,130 records; queue drops: 0.
- Gyro CSV: 45,320 data rows; exposure CSV: 2,699 data rows.
- Telemetry detected motion from approximately 30.1 to 88.1 seconds. Maximum reported planar speed was 1.74 m/s and maximum absolute yaw speed was 2.51 rad/s.
- A sequentially decoded frame at 45 seconds produced a `1280x640` panorama and all six `512x512` cubemap faces.
- Algorithm mean: 62.05 ms; p95: 108.15 ms; throughput: 16.12 FPS across six repetitions.
- The raw dual-fisheye frame and panorama were opened and visually confirmed in the motion test area.
- The original 19 retained artifacts passed `sha256sum -c SHA256SUMS`; the later six-face/300° evaluation expanded the run to 32 verified artifacts.
- Final battery state of charge was 62%; maximum final motor temperature was 56°C.

This run proves that camera, robot telemetry, storage, and custom frame processing remain functional during real robot motion. It does **not** pass the documented first-motion procedure because telemetry did not show the required final 20-second stationary segment, and the reported peak speed exceeded the intended low-speed envelope. The raw run remains valid evidence and must not be relabeled; repeat the controlled-motion pilot with an earlier stop before treating the field procedure as complete.

The follow-up multi-view benchmark generated the panorama, all six cube faces, and three 100° left/front/right panels covering a continuous 300° forward sector. The direct H.264-to-11-JPEG full path averaged 159.83 ms (p95 238.17 ms, 6.26 complete output sets/s); detailed timing boundaries and images are in `docs/motion_pilot_data_report.md`.

## Operating commands

```bash
ssh unitree@10.40.8.222
cd ~/ws_datacollection
source .venv-jetson/bin/activate

# Repeat contract tests.
python -m unittest discover -s tests -v

# Read GO2 state only.
go2-collect telemetry \
  --config config/jetson_go2_smoke.json \
  --run-dir runs/go2_telemetry_check \
  --duration 10

# Repeat the decoded X5 frame check.
python tools/run_x5_frame.py \
  testdata/003_dual_fisheye_sbs.jpg \
  runs/x5_frame_check

# Build the Jetson CameraSDK recorder.
bash scripts/build_x5_sdk_recorder.sh

# Joint X5 + read-only GO2 capture.
bash scripts/record_x5_sdk_go2.sh config/jetson_go2_x5_sdk.json 60
```

## USB permission persistence

The persistent udev rule was installed and verified after unplug/replug and Android-mode selection:

```console
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="2e1a", MODE="0660", GROUP="plugdev"' \
  | sudo tee /etc/udev/rules.d/99-insta360.rules
sudo udevadm control --reload-rules
```

The camera enumerated as vendor/product `2e1a:0002`. It changed from device number `010` to `014` during Android-mode initialization, and the final node automatically retained mode `0660`, owner `root`, and group `plugdev`. Dynamic bus/device numbers must not be hard-coded.

## ROS2 raw-fisheye bag deployment

The later ROS2 Foxy adapter was verified with the same live X5. One node owns CameraSDK, splits each decoded `3840x1920` frame into synchronized `1920x1920` `bgr8` `/fisheye1/image_raw` and `/fisheye2/image_raw` messages, and writes those exact uncompressed messages into a standard rosbag2 SQLite bag.

The three-second live run at `runs/20260717_140725_x5_rosbag_raw/` produced 29 messages on each topic over 2.956 seconds (9.81 paired Hz), a 612.4 MiB bag, equal timestamps/counts, and successful SHA-256 verification. `ros2 bag info` and `ros2 bag play` both accepted the bag. Playback exported 29 exact lossless PNG pairs with zero unmatched timestamps, and two pairs completed panorama, six-face cubemap, and 300° post-processing. Full commands, storage budgeting, architecture, and limitations are documented in `docs/rosbag_raw_pipeline.md`.

After automatic pair/rate validation was added, `runs/20260717_141039_x5_rosbag_raw/` produced 20/20 paired messages over 1.981 seconds at 10.10 Hz and passed the configured 80%-of-target floor. Its bag size was 422.4 MiB.

## Raw-disk/compressed-bag revision

The later storage revision moves canonical decoded pixels out of rosbag: each 10 Hz timestamp writes two uncompressed `1920x1920` BMP files and one flushed `raw/pairs.csv` row, while JPEG quality 85 `sensor_msgs/msg/CompressedImage` messages are published and written to rosbag2. The X5 H.264 source and camera metadata remain separate sidecars.

An on-robot replay of the retained X5 H.264 sample produced 19 raw pairs over 1.942 seconds (`9.78 Hz`). The BMP files occupied 420,251,652 bytes and the compressed bag occupied 14,237,696 bytes. `ros2 bag info` reported 19 messages on each compressed topic with equal timestamp bounds. Slowed playback decoded and exported 19/19 pairs with zero unmatched stamps, and direct BMP post-processing completed panorama, cubemap, and 300° output for the tested pair.

The subsequent live-camera attempt did not start because USB enumeration contained no Insta360 vendor `2e1a`; CameraSDK correctly timed out after 15 seconds. The empty 8 KB attempt and replay-test outputs were removed. A three-second live confirmation remains required after reconnecting the X5 in Android USB mode.

## Safety and provenance

- The deployed telemetry code creates DDS subscribers only and does not publish robot motion commands.
- Robot motion must remain under the official remote during acquisition.
- The verified deployment was copied without `.git`, so manifests report `git_revision: null`. Commit/tag the source and deploy provenance metadata before formal data collection.
- Formal runs must retain their copied config, manifest, timestamps, telemetry, camera artifacts, and verified SHA-256 file.

## WSL finding

WSL 2 mirrored networking reached the Jetson over TCP/IP but did not receive GO2 DDS discovery/data over the external WLAN, even with a temporary diagnostic inbound allow window. Running on the Jetson and binding Unitree SDK2 to internal `eth0` resolved DDS immediately. The diagnostic broad firewall allowance was removed; only GO2-scoped rules remain on Windows.
