# Stitcher Implementation

- `dual_fisheye_stitcher.py:5` stores the X5 `p2` factory canvas and lens-circle records.
- `dual_fisheye_stitcher.py:11` stores the official-supervised full rotations and fifth-order radial profiles.
- `dual_fisheye_stitcher.py:25` scales factory circle geometry to an arbitrary local fisheye frame.
- `dual_fisheye_stitcher.py:50` defines `CalibratedDualFisheyeStitcher`, the standard 2:1 implementation.
- `dual_fisheye_stitcher.py:58` builds the X5 preset from factory circles plus fitted geometry.
- `dual_fisheye_stitcher.py:88` accepts fitted rotations/radial curves while retaining explicit equidistant fallback parameters.
- `dual_fisheye_stitcher.py:152` rotates each spherical ray, evaluates the selected radial model, and records its overlap weight.
- `dual_fisheye_stitcher.py:190` estimates bounded per-lens gains from valid spherical-overlap pixels.
- `dual_fisheye_stitcher.py:205` performs two bilinear remaps, applies optional gains, and blends by calibrated support weights.
