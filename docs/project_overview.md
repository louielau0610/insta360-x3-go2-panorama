# X5 Dual-Fisheye Stitcher

This project is a calibration-aware Insta360 X5 stitching and cubemap pipeline for mobile-robot perception.

`x5_360_pipeline` is the supported runtime entry point. It composes the X5 calibration-aware stitcher with py360convert's cubemap sampler, returning both a 2:1 panorama and the complete six-face `F/R/B/L/U/D` cubemap from a single BGR side-by-side frame.

The calibrated path accepts two square fisheye frames, applies per-lens polynomial lookup tables with full rotations, and blends their spherical overlap. The test capture is an Insta360 X5 DNG decoded into two 2944x2944 circular fisheyes with native left/right ordering.

## Current limitations

- The fitted profile uses three indoor DNG/firmware-JPG pairs (003–005), not a multi-distance calibration target; it must be checked on held-out outdoor captures before deployment.
- The static model does not estimate a translation baseline or a depth-dependent warp.
- Static blending cannot correct parallax from near objects at the seam.
- The code has no durable quality tests.

## Current calibrated baseline

`CalibratedDualFisheyeStitcher.from_x5_factory()` creates a standard 2:1 equirectangular LUT from the X5 `p2` circle geometry plus fitted camera-to-panorama rotations and fifth-order radial curves. The fit uses firmware exports as spherical supervision while treating each capture's stabilization rotation as a nuisance variable.

On sample 003, the old overlap produced one reliable cross-lens feature with about 85 px displacement. The fitted profile produced 114 matches with 8.66 px median displacement; the remaining mismatch is concentrated in near objects and ambiguous texture. Official-supervised feature reprojection across 003–005 fell from 115.30 px median to 2.19 px median after robust fitting.

## Target pipeline

`X5 dual fisheye -> calibrated 2:1 equirectangular LUT -> seam/exposure balance -> py360 perspective views -> robot perception`

For all-direction perception, the pipeline emits a cubemap rather than only three perspective views: `X5 dual fisheye -> 2:1 panorama -> F/R/B/L/U/D cubemap -> robot perception`.

Runtime must use precomputed maps. Calibration and map generation are offline operations. Quality is assessed against the X5 firmware-exported JPEG and through forward-perspective samples relevant to robot navigation.

## Baseline verification

With the X5 factory preset at 960x960 input and 960x480 output, the desktop core averaged 10.36 ms per stitch (96.5 FPS, p95 11.13 ms; exposure balance disabled). It reduced near-black output pixels on sample 003 from 12.837% to 9.291% versus the previous approximate-centre baseline. These figures are not RK3588S measurements.

At the GO2-oriented `1280x640` panorama and six `512x512` faces, the fitted-geometry desktop in-memory chain averaged 26.87 ms (37.22 FPS, p95 31.91 ms). The API wrapper produced the expected panorama and fixed `F/R/B/L/U/D` face contract on 003.

With the fitted geometry at `1920x960`, the desktop stitch-only core averaged 45.19 ms (22.13 FPS, p95 54.60 ms). Radial and rotation corrections are absorbed into startup LUT generation and do not add a new per-frame optimization stage.
