# X5 Dual-Fisheye Stitcher

This project is a calibration-aware Insta360 X5 stitching and cubemap pipeline for mobile-robot perception.

`x5_360_pipeline` is the supported runtime entry point. It composes the X5 calibration-aware stitcher with py360convert's cubemap sampler, returning both a 2:1 panorama and the complete six-face `F/R/B/L/U/D` cubemap from a single BGR side-by-side frame.

The calibrated path accepts two square fisheye frames, applies per-lens equidistant lookup tables, and blends their spherical overlap. The test capture is an Insta360 X5 DNG decoded into two 2944x2944 circular fisheyes with native left/right ordering.

## Current limitations

- The calibrated path uses the X5 factory circle centres, radii, and small pitch/yaw corrections, but it still assumes an equidistant radial model and does not fit lens distortion or a translation baseline.
- The last approximately-90-degree orientation number in the X5 `p2` record does not map directly to this equirectangular roll convention; applying it rotates the panorama incorrectly, so it is preserved as metadata rather than used at runtime.
- Static blending cannot correct parallax from near objects at the seam.
- The code has no durable quality tests.

## Current calibrated baseline

`CalibratedDualFisheyeStitcher.from_x5_factory()` creates a standard 2:1 equirectangular LUT from the X5 `p2` record embedded in the DNG. It scales the 10752x5376 factory canvas to the local lens frame, converts the right centre to local coordinates, applies the tested small pitch/yaw corrections, and estimates bounded exposure gains from the actual spherical overlap.

The available four indoor DNG/JPG pairs are adequate for a coarse orientation check but not final calibration: a one-image edge search preferred FOV 188 degrees while the four-image aggregate preferred 202 degrees. This instability shows that the scene does not constrain the lens model sufficiently; final intrinsics and pose must use a calibration target at multiple locations and orientations.

## Target pipeline

`X5 dual fisheye -> calibrated 2:1 equirectangular LUT -> seam/exposure balance -> py360 perspective views -> robot perception`

For all-direction perception, the pipeline emits a cubemap rather than only three perspective views: `X5 dual fisheye -> 2:1 panorama -> F/R/B/L/U/D cubemap -> robot perception`.

Runtime must use precomputed maps. Calibration and map generation are offline operations. Quality is assessed against the X5 firmware-exported JPEG and through forward-perspective samples relevant to robot navigation.

## Baseline verification

With the X5 factory preset at 960x960 input and 960x480 output, the desktop core averaged 10.36 ms per stitch (96.5 FPS, p95 11.13 ms; exposure balance disabled). It reduced near-black output pixels on sample 003 from 12.837% to 9.291% versus the previous approximate-centre baseline. These figures are not RK3588S measurements.

At the GO2-oriented `1280x640` panorama and six `512x512` faces, the desktop in-memory chain averaged 30.38 ms (32.92 FPS); JPEG encoding of all six faces raised it to 43.79 ms (22.83 FPS). The API wrapper was checked on 003 against direct component calls for exact panorama and cubemap equality.
