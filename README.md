# Insta360 X5 360 Pipeline

An X5 factory-calibrated dual-fisheye runtime pipeline for full-sphere robot perception. One API produces both a standard 2:1 panorama and a complete six-face cubemap for Unitree GO2-class platforms.

## Output

Given one BGR side-by-side frame containing two square fisheyes, the default configuration produces:

- a `1280x640` BGR equirectangular panorama for recording and visualization;
- six `512x512` BGR cubemap faces in `F/R/B/L/U/D` order for all-direction perception;
- optional JPEG payloads only when transmission or logging requires them.

The cubemap is complete `360°x180°` coverage. It does not replace the panorama, and it does not infer metric depth.

## Install

```bash
pip install -e .
```

The package installs `numpy`, `opencv-python`, and `py360convert`.

## Usage

```python
from x5_360_pipeline import X5CubemapPipeline

# For the X5 raw 5888x2944 side-by-side layout.
pipeline = X5CubemapPipeline(2944, 2944)

result = pipeline.process_side_by_side(side_by_side_bgr)
panorama_bgr = result.panorama
front_bgr = result.faces["F"]
back_bgr = result.faces["B"]
```

If the camera source already supplies separate frames, call `pipeline.process(left_bgr, right_bgr)` instead. Inputs and outputs use BGR channel order.

## X5 factory profile

The calibrated stitcher scales the X5 `p2` factory lens circles from a `10752x5376` source canvas. It combines the independent circle centres/radii with full per-lens rotation matrices and fifth-order radial curves fitted against firmware-exported 003–005 image pairs. Its lookup tables are built once at startup. The X5 preset then uses a low-resolution, temporally smoothed minimum-cost seam to select one lens in the overlap instead of averaging duplicated objects. The seam is refreshed every three frames by default and reused between updates.

## Performance envelope

Desktop measurements on sample 003 at `1280x640` panorama plus six `512x512` faces, using the default dynamic seam and in-memory BGR frames:

- stitch only: `22.12 ms` / `45.21 FPS` average;
- panorama plus cubemap: `32.92 ms` / `30.38 FPS` average, `59.06 ms` p95.

On RK3588S, treat this as a starting point rather than a guarantee: keep cubemap faces in memory, pin the real-time process to Cortex-A76 cores, cache all maps, and validate on the actual GO2. DNG decoding is photo-only and must not be in the live stream path. Use `seam_update_interval=5` if the target needs more CPU headroom, after checking moving-object seam lag on the robot.

## Repository layout

- `x5_360_pipeline/`: supported unified API.
- `dual_fisheye_stitcher.py`: X5 factory-calibrated LUT stitcher.
- `docs/`: implementation details, parameter assumptions, and robot-use constraints.

## Limitations

The fitted static geometry aligns distant overlap content but cannot remove near-field parallax. The dynamic seam prevents overlap averaging and suppresses a near-black lens obstruction when the other lens has reliable content, but it does not synthesize a depth-correct view. Because the profile is supervised by three indoor firmware exports rather than a calibration target, final deployment should validate it with held-out outdoor scenes and then calibrate camera-to-robot extrinsics. Local optical flow remains an optional later step only if held-out moving scenes justify its cost and distortion risk.
