# Unified Pipeline Implementation

- `pyproject.toml:1` selects the setuptools build backend; `setup.py:1` declares the installable `x5-360-pipeline` distribution, dependencies, and retained top-level stitcher module.
- `x5_360_pipeline/__init__.py:3` exports the two public API symbols.
- `x5_360_pipeline/pipeline.py:13` defines `CubemapFrame`, which carries BGR panorama, horizontal cubemap, named faces, and optional JPEG payloads.
- `x5_360_pipeline/pipeline.py:22` defines `X5CubemapPipeline`; its constructor creates the X5 factory stitcher, exposes dynamic-seam mode/cadence, and builds the one-time cached cubemap sampler.
- `x5_360_pipeline/pipeline.py:60` processes separate left/right BGR fisheyes.
- `x5_360_pipeline/pipeline.py:78` splits a BGR side-by-side frame and delegates to `process`.
- `x5_360_pipeline/pipeline.py:90` validates the fixed BGR fisheye frame contract before projection.

The wrapper deliberately uses py360convert's `EquirecSampler` rather than its `e2c()` convenience function so the cubemap coordinate table is cached for every frame. The returned horizontal cubemap has shape `(face_width, face_width * 6, 3)` and `faces` splits it in fixed `F/R/B/L/U/D` order.
