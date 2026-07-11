# Stitcher Implementation

- `dual_fisheye_stitcher.py:5` stores the X5 `p2` factory canvas and lens-circle records.
- `dual_fisheye_stitcher.py:11` stores the official-supervised full rotations and fifth-order radial profiles.
- `dual_fisheye_stitcher.py:25` scales factory circle geometry to an arbitrary local fisheye frame.
- `dual_fisheye_stitcher.py:50` defines `CalibratedDualFisheyeStitcher`, the standard 2:1 implementation.
- `dual_fisheye_stitcher.py:58` builds the X5 preset from factory circles plus fitted geometry.
- `dual_fisheye_stitcher.py:94` accepts fitted rotations/radial curves while retaining explicit equidistant fallback parameters.
- `dual_fisheye_stitcher.py:183` rotates each spherical ray, evaluates the selected radial model, and records its overlap weight.
- `dual_fisheye_stitcher.py:221` estimates bounded per-lens gains from valid spherical-overlap pixels.
- `dual_fisheye_stitcher.py:237` solves a smooth vertical minimum-cost path with an invalid-support penalty and centre bias.
- `dual_fisheye_stitcher.py:263` computes two quarter-resolution paths from local disagreement plus the selected regions' dark-obstruction cost, then applies temporal smoothing.
- `dual_fisheye_stitcher.py:307` caches the seam mask, constrains exclusive lens support, and rejects a selected near-black obstruction when the other lens is reliable.
- `dual_fisheye_stitcher.py:331` performs two bilinear remaps and selects either dynamic-seam pixels or the legacy calibrated weighted blend.
