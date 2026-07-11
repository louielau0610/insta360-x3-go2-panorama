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

The calibrated stitcher scales the X5 `p2` factory lens circles from a `10752x5376` source canvas. It applies independent circle centres/radii and the tested pitch/yaw micro-corrections. Its lookup tables are built once at startup; frame processing performs only remapping, blending, and optional cubemap projection.

## Performance envelope

Desktop measurements on sample 003 at `1280x640` panorama plus six `512x512` faces:

- in-memory panorama plus cubemap: `30.38 ms` / `32.92 FPS`;
- with six JPEG encodes: `43.79 ms` / `22.83 FPS`.

On RK3588S, treat this as a starting point rather than a guarantee: keep cubemap faces in memory, pin the real-time process to Cortex-A76 cores, cache all maps, and validate on the actual GO2. DNG decoding is photo-only and must not be in the live stream path.

## Repository layout

- `x5_360_pipeline/`: supported unified API.
- `dual_fisheye_stitcher.py`: X5 factory-calibrated LUT stitcher.
- `docs/`: implementation details, parameter assumptions, and robot-use constraints.

## Limitations

The current lens model is equidistant and cannot remove near-field parallax. The approximately-90-degree orientation number in X5 factory metadata is retained but not applied as a roll, because that interpretation rotates the panorama incorrectly in this coordinate convention. Final deployment should still validate radial distortion, relative pose, and camera-to-robot extrinsics with calibration targets.
