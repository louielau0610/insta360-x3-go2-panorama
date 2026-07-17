# X5 Dual-Fisheye Stitcher

This project is a calibration-aware Insta360 X5 stitching and cubemap pipeline for mobile-robot perception.

It now also provides a field acquisition boundary. `go2_experiment` records camera frames with host wall/monotonic timestamps and subscribes to GO2 state through Unitree SDK2. The native X5 CameraSDK recorder preserves the primary encoded dual-fisheye stream, any optional secondary stream, and camera timestamps when a decoded V4L2/RTSP source is unavailable. It permits a bounded 15-second discovery window for the X5 Android-mode USB re-enumeration. Neither path publishes robot commands.

Stationary and controlled-motion runs use separate saved configurations and labels. Motion is always performed by an onsite operator with the official remote; the software only records state and camera data.

`x5_ros` is the ROS2 Foxy adapter. One node owns CameraSDK, decodes and splits the X5 preview, publishes synchronized `/fisheye1/image_raw` and `/fisheye2/image_raw` `bgr8` messages, and writes those exact messages into rosbag2 without a second DDS transfer. Offline tools replay/export lossless timestamp-paired PNG files and generate panorama, six-face cubemap, and 300° left/front/right products. The bag contains original decoded pixels, not JPEG-compressed topics.

`x5_360_pipeline` is the supported runtime entry point. It composes the X5 calibration-aware stitcher with py360convert's cubemap sampler, returning both a 2:1 panorama and the complete six-face `F/R/B/L/U/D` cubemap from a single BGR side-by-side frame.

The calibrated path accepts two square fisheye frames, applies per-lens polynomial lookup tables with full rotations, and blends their spherical overlap. The test capture is an Insta360 X5 DNG decoded into two 2944x2944 circular fisheyes with native left/right ordering.

## Current limitations

- The fitted profile uses three indoor DNG/firmware-JPG pairs (003–005), not a multi-distance calibration target; it must be checked on held-out outdoor captures before deployment.
- The static model does not estimate a translation baseline or a depth-dependent warp.
- Dynamic seam selection cannot correct depth-dependent parallax when a near object crosses the selected path.
- The code has no durable quality tests.

## Current calibrated baseline

`CalibratedDualFisheyeStitcher.from_x5_factory()` creates a standard 2:1 equirectangular LUT from the X5 `p2` circle geometry plus fitted camera-to-panorama rotations and fifth-order radial curves. The fit uses firmware exports as spherical supervision while treating each capture's stabilization rotation as a nuisance variable.

On sample 003, the old overlap produced one reliable cross-lens feature with about 85 px displacement. The fitted profile produced 114 matches with 8.66 px median displacement; the remaining mismatch is concentrated in near objects and ambiguous texture. Official-supervised feature reprojection across 003–005 fell from 115.30 px median to 2.19 px median after robust fitting.

The second stage replaces overlap averaging in the X5 preset with two content-aware minimum-cost paths. Its cost includes both local disagreement and the dark-obstruction cost of the regions that each candidate path would select. Seam search runs at quarter resolution, is temporally smoothed, and refreshes every three frames by default. A conservative near-black fallback selects the other lens only when it contains clearly brighter valid content; this removes the visible lens/selfie-stick obstruction on sample 003 without cropping the panorama.

## Target pipeline

`X5 dual fisheye -> calibrated 2:1 equirectangular LUT -> seam/exposure balance -> py360 perspective views -> robot perception`

For all-direction perception, the pipeline emits a cubemap rather than only three perspective views: `X5 dual fisheye -> 2:1 panorama -> F/R/B/L/U/D cubemap -> robot perception`.

Field data flow is `X5 raw/encoded stream + host timestamps + GO2 LowState/SportModeState -> one immutable run directory -> SHA-256 manifest`. Raw camera data remains available even if online stitching cannot meet its target frequency.

The ROS raw-image flow is `X5 H.264 -> one CameraSDK owner -> BGR decode -> synchronized left/right ROS Image messages -> direct rosbag2 SQLite + ROS topics -> lossless PNG pairs -> offline multi-view processing`. Direct bag writing avoids Foxy DDS dropping large 11 MB image messages between separate processes; topics remain published for diagnostics and optional consumers.

The supported on-robot deployment root is `~/ws_datacollection` on the GO2-mounted Jetson. `scripts/install_jetson.sh` creates an isolated Python 3.8 environment while retaining JetPack's system OpenCV; it does not replace CUDA, JetPack, ROS 2, or robot services.
The Jetson environment pins the final Python 3.8-compatible NumPy/SciPy/Pillow releases and applies postponed annotation evaluation to py360convert 1.0.4, whose package metadata otherwise excludes Python 3.8.

Runtime must use precomputed maps. Calibration and map generation are offline operations. Quality is assessed against the X5 firmware-exported JPEG and through forward-perspective samples relevant to robot navigation.

## Field safety and integrity

- Acquisition is read-only: the code creates Unitree subscribers and no command publisher.
- `scripts/preflight.sh` must pass before a run, including reception of at least one GO2 state message.
- Every formal run has an unedited config, frame/chunk timestamps, completion status, counts, and `SHA256SUMS`.
- A failed manifest, empty X5 stream, timestamp gaps, or operator emergency stop makes the run invalid; raw files are retained for diagnosis.
- Network interface, X5 source layout and output storage are explicit configuration, never inferred during a formal run.

## Baseline verification

With the X5 factory preset at 960x960 input and 960x480 output, the desktop core averaged 10.36 ms per stitch (96.5 FPS, p95 11.13 ms; exposure balance disabled). It reduced near-black output pixels on sample 003 from 12.837% to 9.291% versus the previous approximate-centre baseline. These figures are not RK3588S measurements.

At the GO2-oriented `1280x640` panorama and six `512x512` faces, the fitted-geometry desktop in-memory chain averaged 26.87 ms (37.22 FPS, p95 31.91 ms). The API wrapper produced the expected panorama and fixed `F/R/B/L/U/D` face contract on 003.

With the stage-two dynamic seam enabled, the same output contract averaged 32.92 ms (30.38 FPS, p95 59.06 ms). Stitch-only processing averaged 22.12 ms (45.21 FPS). The refresh frame creates the p95 spike; cached frames reuse the previous seam. These are desktop CPU measurements, not RK3588S measurements.

With the fitted geometry at `1920x960`, the desktop stitch-only core averaged 45.19 ms (22.13 FPS, p95 54.60 ms). Radial and rotation corrections are absorbed into startup LUT generation and do not add a new per-frame optimization stage.

## Verification workflow

`tools/validate_x5_samples.py` is the offline regression entry point for known X5 DNG captures. It excludes photo decoding from timing, exercises the supported panorama-plus-cubemap API repeatedly, verifies the fixed output shapes, and fails when repeated-frame seam drift exceeds 1 px, first-to-stable MAE exceeds 0.1, or throughput falls below the configurable acceptance floor (4.5 FPS by default). Field configuration raises the processed output requirement to 6 Hz. Validator outputs belong in an external test directory, not the source tree.

Run `python -m unittest discover -s tests -v` for acquisition contract tests, then `go2-collect preflight --config <config>` on the actual hardware.

On the GO2-mounted Jetson, run `bash scripts/install_jetson.sh` and complete the synthetic smoke test before enabling GO2 telemetry or attaching the X5. Bind DDS to the internal robot interface, not the external Wi-Fi interface.

The verified 2026-07-17 on-robot environment, commands, measurements, artifacts, and remaining live-X5 blocker are recorded in `docs/jetson_deployment_report.md`.
