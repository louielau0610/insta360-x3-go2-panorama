# Stitcher Principles

The project must emit a standard 2:1 equirectangular panorama before calling `py360convert`. A non-2:1 panorama changes the longitude-to-pixel relationship and invalidates downstream perspective projections.

Each lens needs independent intrinsic parameters (centre, effective focal length and, when needed, radial distortion) plus a relative rotation into one spherical coordinate frame. These parameters belong in offline LUT generation; per-frame code must only remap and blend.

The X5 preset uses its embedded 10752x5376 `p2` record for each lens circle centre and radius, then scales them to the actual local frame. It also uses the two small orientation values as pitch/yaw corrections. The final approximately-90-degree value is not applied as roll: the controlled 003 comparison showed that interpretation rotates the panorama by about 90 degrees. It remains available in the returned factory metadata until its vendor coordinate convention is decoded.

The radial model remains deliberately simple: radius divided by half-FOV defines an equidistant focal length. Future calibration should fit the radial curve and relative translation against a multi-distance target capture, rather than changing the factory constants to hide parallax.

Exposure gain is measured only where both projected lenses are valid. The gains are limited to `[0.8, 1.25]`; if there are too few valid pixels, the image is left unchanged. This prevents a dark border or a nearby object in one lens from globally brightening or darkening a robot perception frame.

The overlap is a quality boundary, not a reason to geometrically concatenate two local projections. Exposure gains must be estimated conservatively and blending must not hide a geometric misalignment. Parallax from objects near the camera cannot be solved by a static LUT and must be reported rather than silently distorted.

For robot use, the success criteria are: straight structural edges remain stable in forward views, seam artifacts stay outside the forward navigation view where possible, and the end-to-end stream sustains at least 10 Hz on the target RK3588S hardware.
