# Stitcher Implementation

- `dual_fisheye_stitcher.py:5`--`dual_fisheye_stitcher.py:7` store the X5 `p2` factory canvas and the two lens records.
- `dual_fisheye_stitcher.py:10` scales those records to an arbitrary local fisheye frame and converts the right centre from full-canvas to local coordinates.
- `dual_fisheye_stitcher.py:35` defines `CalibratedDualFisheyeStitcher`, the standard 2:1 implementation.
- `dual_fisheye_stitcher.py:43` builds the X5 preset, using only the verified pitch/yaw micro-corrections from the factory orientation records.
- `dual_fisheye_stitcher.py:70` accepts independent centres, radii, FOVs, yaw, pitch, roll, and exposure-balance control.
- `dual_fisheye_stitcher.py:124` rotates each equirectangular ray into its lens frame, converts it using the equidistant radius/FOV model, and records an overlap weight.
- `dual_fisheye_stitcher.py:155` estimates bounded per-lens gains from valid pixels in the two-lens spherical overlap.
- `dual_fisheye_stitcher.py:170` performs two bilinear remaps, applies the optional gains, and blends only where both lens maps are valid.
