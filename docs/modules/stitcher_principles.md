# Stitcher Principles

The project must emit a standard 2:1 equirectangular panorama before calling `py360convert`. A non-2:1 panorama changes the longitude-to-pixel relationship and invalidates downstream perspective projections.

Each lens needs independent intrinsic parameters (centre, effective focal length and, when needed, radial distortion) plus a relative rotation into one spherical coordinate frame. These parameters belong in offline LUT generation; per-frame code must only remap and blend.

The X5 preset uses its embedded 10752x5376 `p2` record for each lens circle centre and radius, then scales them to the actual local frame. Full camera-to-panorama rotation matrices and radial curves are fitted against paired DNG and firmware-exported JPG captures. Per-capture stabilization is solved as a nuisance rotation so it cannot be absorbed into shared lens geometry.

The fitted radial model is `rho/radius = a1*theta + a3*theta^3 + a5*theta^5`. It is evaluated only while the normalized radius stays in `[0, 1]`. The profile is a static far-scene alignment, not a substitute for relative translation, scene depth, or a multi-distance target calibration.

Exposure gain is measured only where both projected lenses are valid. The gains are limited to `[0.8, 1.25]`; if there are too few valid pixels, the image is left unchanged. This prevents a dark border or a nearby object in one lens from globally brightening or darkening a robot perception frame.

The overlap is a quality boundary, not a reason to geometrically concatenate two local projections. Exposure gains must be estimated conservatively and blending must not hide a geometric misalignment. Parallax from objects near the camera cannot be solved by a static LUT and must be reported rather than silently distorted.

For robot use, the success criteria are: straight structural edges remain stable in forward views, seam artifacts stay outside the forward navigation view where possible, and the end-to-end stream sustains at least 10 Hz on the target RK3588S hardware.
