# Validation Principles

DNG decoding is deliberately outside the timed region because the GO2 runtime must receive already decoded BGR frames. The validator measures the same supported `X5CubemapPipeline` call used by live integration and does not maintain a second stitching implementation.

Repeated identical frames protect deterministic temporal behavior: the cached dynamic seam may update, but it must not drift by more than 1 px or materially change the panorama. Shape checks protect the `1280x640` panorama and six named `512x512` cubemap faces required by downstream perception.

The default 4.5 FPS floor represents the project's current “approximately 5 Hz” acceptance criterion and is intentionally configurable for RK3588S measurements. Desktop timing is diagnostic only. Visual inspection remains required for semantic artifacts such as duplicated objects because a numeric stability test cannot prove perceptual correctness.
