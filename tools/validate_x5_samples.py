"""Validate X5 DNG samples without putting photo decoding in the runtime API."""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from x5_360_pipeline import X5CubemapPipeline


def decode_dng(path):
    try:
        import rawpy
    except ImportError as error:
        raise SystemExit("Install the optional validator dependency with: pip install rawpy") from error
    with rawpy.imread(str(path)) as raw:
        rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def validate_sample(path, output_dir, repeat, min_fps):
    frame = decode_dng(path)
    height, canvas_width = frame.shape[:2]
    if canvas_width % 2:
        raise ValueError(f"{path.name}: side-by-side width must be even")
    pipeline = X5CubemapPipeline(canvas_width // 2, height)
    timings = []
    seams = []
    first_panorama = None
    result = None
    for index in range(repeat):
        start = time.perf_counter()
        result = pipeline.process_side_by_side(frame)
        timings.append((time.perf_counter() - start) * 1000)
        seams.append(pipeline.stitcher.last_seams.copy())
        if index == 0:
            first_panorama = result.panorama.copy()

    expected_faces = set("FRBLUD")
    shapes_valid = (
        result.panorama.shape == (640, 1280, 3)
        and set(result.faces) == expected_faces
        and all(face.shape == (512, 512, 3) for face in result.faces.values())
    )
    seam_delta = float(np.max(np.abs(np.diff(np.stack(seams), axis=0)))) if repeat > 1 else 0.0
    panorama_mae = float(np.mean(np.abs(first_panorama.astype(np.int16) - result.panorama.astype(np.int16))))
    dark_percent = float(np.mean(cv2.cvtColor(result.panorama, cv2.COLOR_BGR2GRAY) < 12) * 100)
    mean_ms = float(np.mean(timings))
    fps = 1000 / mean_ms
    passed = shapes_valid and seam_delta <= 1 and panorama_mae <= 0.1 and fps >= min_fps

    sample_id = path.stem.rsplit("_", 1)[-1]
    sample_dir = output_dir / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(sample_dir / f"{sample_id}_panorama_1280x640.jpg"), result.panorama)
    for name, face in result.faces.items():
        cv2.imwrite(str(sample_dir / f"{sample_id}_cube_{name}_512.jpg"), face)
    return {
        "sample": sample_id,
        "passed": passed,
        "mean_ms": mean_ms,
        "p95_ms": float(np.percentile(timings, 95)),
        "fps": fps,
        "max_seam_delta_px": seam_delta,
        "first_to_stable_mae": panorama_mae,
        "near_black_percent": dark_percent,
        "shapes_valid": shapes_valid,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--samples", nargs="+", default=["003", "004", "005"])
    parser.add_argument("--repeat", type=int, default=12)
    parser.add_argument("--min-fps", type=float, default=4.5, help="Approximately 5 Hz acceptance floor")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for sample in args.samples:
        matches = sorted(args.input_dir.glob(f"*_00_{sample}.dng"))
        if len(matches) != 1:
            parser.error(f"expected one DNG matching sample {sample}, found {len(matches)}")
        report = validate_sample(matches[0], args.output_dir, args.repeat, args.min_fps)
        reports.append(report)
        print(json.dumps(report, ensure_ascii=False))
    (args.output_dir / "validation_report.json").write_text(
        json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    raise SystemExit(0 if all(report["passed"] for report in reports) else 1)


if __name__ == "__main__":
    main()
