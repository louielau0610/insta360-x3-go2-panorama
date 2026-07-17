# GO2 + X5 Field Guide — 2026-07-18

## Tonight: build the deployment package

From Windows PowerShell in the repository:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package_deployment.ps1
```

Copy `go2_x5_deployment.zip` to the Ubuntu 22.04 acquisition computer and extract it. The package includes the project and available x86_64/ARM64 Insta360 CameraSDK archive. Do not wait until the field session to download dependencies; run installation tonight while internet is available.

```bash
cd go2_x5_deployment
bash scripts/install_go2.sh
python -m unittest discover -s tests -v
```

Copy `config/go2_x5_v4l2.json` to `config/tomorrow.json` and edit only:

- `experiment.operator`, `scene`, `notes`, and `label`;
- `go2.interface` from `ip -brief link`;
- `camera.source` and actual decoded frame dimensions if using V4L2/RTSP;
- `recording.output_root` to the dedicated data disk.

## Direct GO2 connection

1. Power the GO2 normally and retain its official remote control.
2. Connect the acquisition computer to the GO2 Ethernet port.
3. List interfaces with `ip -brief link` and identify the newly connected interface.
4. Configure and test it:

```bash
bash scripts/configure_go2_network.sh enp2s0
```

The defaults set the host to `192.168.123.99/24` and ping `192.168.123.161`. If your GO2 uses another documented address, pass host and robot IP as the second and third arguments. Do not start a run until DDS state is received.

## Choose exactly one camera path

### A. Decoded V4L2/RTSP source

Use this when OpenCV can read the live left/right side-by-side frame directly.

```bash
v4l2-ctl --list-devices
bash scripts/preflight.sh config/tomorrow.json
bash scripts/record.sh config/tomorrow.json 60
```

The configured dimensions must match exactly. For the calibrated full-resolution path this is normally `5888x2944`, but the preflight result—not an assumption—is authoritative.

### B. Official X5 CameraSDK

Use this when the X5 is connected by USB but does not appear as a decoded video source.

For X4/X5, select **Android mode** on the camera after connecting USB. The Linux account must have read/write access to the `2e1a:*` USB device; use a `plugdev` udev rule rather than hard-coding the dynamic bus/device number.

The recorder allows up to 15 seconds for CameraSDK discovery because the camera can enumerate a second time while entering Android mode. A timeout still fails the run explicitly.

```bash
bash scripts/build_x5_sdk_recorder.sh
bash scripts/record_x5_sdk_go2.sh config/tomorrow.json 60
```

This records the primary elementary encoded dual-fisheye stream, an optional secondary stream when CameraSDK supplies one, byte offsets, camera/host timestamps, gyro and exposure. It does not perform online custom stitching. On the verified X5 `3840x1920` preview, CameraSDK supplied stream index 0 only; an empty index 1 is valid.

## Mandatory one-minute pilot

Keep the robot lying down or supported and run exactly 60 seconds. A valid pilot has:

- command exit status zero;
- non-empty camera stream/video and GO2 telemetry files;
- `manifest.json` status `complete` for the generic path, or nonzero X5 chunk count for the SDK path;
- timestamps increasing and no telemetry queue drops;
- at least 6 Hz processed output when custom online stitching is enabled;
- sufficient remaining data-disk capacity for the planned session;
- a generated `SHA256SUMS` file.

Open one raw frame/stream and one panorama before movement. Confirm left/right order, upright orientation, exposure, seam location and that the camera mount is fixed.

## Formal run procedure

1. Announce the run label aloud and show a phone clock or LED flash to the camera for a visible synchronization event.
2. Start acquisition while the GO2 is stationary; wait 10 seconds.
3. Use the official remote to execute the planned motion. The acquisition software never moves the robot.
4. End with another 10 stationary seconds.
5. Stop with `Ctrl+C` once. Wait for writers and checksums to finish; do not power off immediately.
6. Inspect completion status, counts, file sizes and the first/last timestamp.
7. Make the run directory read-only or copy it to a second disk before the next condition.

Use at least three independent repetitions per condition. Never reuse a run directory or edit its saved `config.json`.

## First controlled-motion pilot

Only proceed after the 60-second stationary pilot passes. Clear the test area, keep an operator on the official remote and emergency stop, and ensure no person is within the robot's motion envelope. The acquisition process remains read-only.

For the first 90-second run, keep the GO2 stationary for at least the first 10 seconds. The onsite operator may then perform only low-speed, short-distance motion judged safe for the available space. End all motion by 70 seconds and keep the robot stationary for the final 20 seconds. Stop immediately for camera/DDS interruption, mount movement, unexpected gait, loss of remote control, or a person entering the test area.

```bash
bash scripts/record_x5_sdk_go2.sh config/jetson_go2_x5_motion_pilot.json 90
```

Passing requires both process exit statuses to be zero, zero telemetry queue drops, a decodable primary X5 stream, successful SHA-256 verification, and visual inspection of a frame from the moving interval.

## Immediate stop / invalid-run conditions

Stop motion with the official remote and terminate acquisition if the camera disconnects, DDS telemetry stops, the mount moves, disk becomes full, the computer thermally shuts down, people enter the safety area, or the robot behaves unexpectedly. Retain the run directory but mark it invalid in the experiment log; never silently combine it with a later run.
