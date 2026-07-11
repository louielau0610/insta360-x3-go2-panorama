# Insta360 X5 360° Pipeline

> A calibration-aware dual-fisheye stitching pipeline that produces a 2:1 panorama and a full six-face cubemap from an Insta360 X5 frame.

This project provides a compact runtime path for future all-direction robot perception on Unitree GO2-class platforms. It combines an X5-specific calibrated stitcher, content-aware seam selection, and cubemap rendering behind one Python API. The package works entirely on in-memory BGR frames; JPEG encoding is optional and stays outside the real-time path.

## Highlights

- **Calibrated X5 stitcher** — precomputes per-lens polynomial lookup tables, circle geometry, and rotations at startup.
- **Two useful outputs** — returns a standard equirectangular panorama and a complete `F/R/B/L/U/D` cubemap in a single call.
- **Content-aware seams** — selects the lower-cost source through the overlap instead of averaging duplicated or obstructed content.
- **Runtime-oriented design** — caches maps and seams, keeps cubemap faces in memory, and separates offline DNG validation from live-frame processing.
- **Repeatable validation** — exercises known X5 samples, output shapes, seam stability, and a configurable throughput floor.

## Pipeline

```text
X5 side-by-side BGR frame
          │
          ▼
calibrated dual-fisheye LUT stitch
          │
          ├── 2:1 equirectangular panorama
          │
          └── py360convert ──> F / R / B / L / U / D cubemap faces
```

The cubemap provides complete `360° × 180°` coverage; it complements the panorama and does not infer metric depth.

## Install

```bash
pip install -e .
```

The package installs `numpy`, `opencv-python`, and `py360convert`.

## Quick start

```python
from x5_360_pipeline import X5CubemapPipeline

# X5 raw layout: two 2944 × 2944 fisheyes side by side.
pipeline = X5CubemapPipeline(2944, 2944)

result = pipeline.process_side_by_side(side_by_side_bgr)
panorama_bgr = result.panorama
front_bgr = result.faces["F"]
back_bgr = result.faces["B"]
```

For camera sources that provide separate images, call `pipeline.process(left_bgr, right_bgr)` instead. All inputs and outputs use BGR channel order.

## Output contract

With the default configuration, one side-by-side BGR input frame yields:

| Output | Default shape | Intended use |
| --- | --- | --- |
| Panorama | `1280 × 640` BGR | Recording, visualization, and panorama-based processing |
| Cubemap | Six `512 × 512` BGR faces | All-direction robot-perception consumers |
| JPEG payloads | Optional | Transmission or logging only |

Cubemap face order is always `F/R/B/L/U/D`.

## X5 calibration and seam model

The X5 preset scales the `p2` factory lens circles from a `10752 × 5376` source canvas, then combines independent lens centres and radii with full per-lens rotation matrices and fifth-order radial curves. The geometry was fitted against firmware-exported image pairs 003–005. Lookup tables are built once at startup.

In the spherical overlap, the preset evaluates a low-resolution minimum-cost path using local disagreement and dark-obstruction costs. The seam is temporally smoothed, updated every three frames by default, and reused between updates. This avoids overlap averaging and can suppress a near-black lens obstruction when the other lens contains reliable content.

## Performance envelope

Desktop measurements on sample 003 at a `1280 × 640` panorama plus six `512 × 512` faces, using the default dynamic seam and in-memory BGR frames:

| Workload | Average | Throughput | p95 |
| --- | ---: | ---: | ---: |
| Stitch only | 22.12 ms | 45.21 FPS | — |
| Panorama + cubemap | 32.92 ms | 30.38 FPS | 59.06 ms |

These are desktop measurements, not RK3588S or GO2 performance guarantees. On the target platform, retain faces in memory, cache all maps, pin the real-time process to appropriate CPU cores, and validate with real robot inputs. If CPU headroom is limited, `seam_update_interval=5` is a possible starting point—but moving-object seam lag must be checked first.

## Offline regression

After changing geometry, seam logic, or projection code, validate known X5 samples with the optional photo decoder:

```bash
pip install rawpy
python tools/validate_x5_samples.py /path/to/dngs /path/to/output
```

The validator checks panorama and cubemap shapes, repeated-frame seam drift, first-to-stable output change, and an approximately 5 Hz minimum throughput. DNG decode time is excluded. Keep generated JPEGs and `validation_report.json` outside the repository.

## Repository layout

| Path | Purpose |
| --- | --- |
| `x5_360_pipeline/` | Supported unified panorama-plus-cubemap API. |
| `dual_fisheye_stitcher.py` | X5 calibration-aware LUT stitcher and seam implementation. |
| `tools/validate_x5_samples.py` | Offline DNG quality and performance regression utility. |
| `docs/` | Implementation details, parameter assumptions, and robot-use constraints. |

## Scope and limitations

- The fitted static geometry aligns distant overlap content but cannot eliminate near-field parallax.
- Content-aware seam selection does not create a depth-correct view when a close object crosses the seam.
- The calibration profile is supervised by three indoor firmware exports, not a multi-distance calibration target; validate it on held-out outdoor scenes before deployment.
- Camera-to-robot extrinsics still require calibration for robot use.
- Local optical flow remains a later option only if held-out moving scenes demonstrate that its additional cost and distortion risk are justified.

See the [project overview](docs/project_overview.md) and module documents in [`docs/modules/`](docs/modules/) for implementation details and design constraints.
