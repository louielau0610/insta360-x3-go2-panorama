"""Run one decoded X5 side-by-side frame through the deployed pipeline."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from x5_360_pipeline import X5CubemapPipeline


def run_frame(input_path, output_dir, repeat):
    frame = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError(f"cannot read image: {input_path}")
    height, width = frame.shape[:2]
    if width % 2:
        raise ValueError(f"side-by-side width must be even: {width}")

    pipeline = X5CubemapPipeline(width // 2, height)
    timings = []
    result = None
    for _ in range(repeat):
        started = time.perf_counter()
        result = pipeline.process_side_by_side(frame)
        timings.append((time.perf_counter() - started) * 1000)

    output_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_dir / "panorama.jpg"), result.panorama)
    for name, face in result.faces.items():
        cv2.imwrite(str(output_dir / f"cube_{name}.jpg"), face)

    mean_ms = float(np.mean(timings))
    report = {
        "input": str(input_path),
        "input_shape": list(frame.shape),
        "panorama_shape": list(result.panorama.shape),
        "face_shapes": {name: list(face.shape) for name, face in result.faces.items()},
        "repeat": repeat,
        "mean_ms": mean_ms,
        "p95_ms": float(np.percentile(timings, 95)),
        "fps": 1000.0 / mean_ms,
    }
    (output_dir / "frame_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repeat", type=int, default=6)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    print(json.dumps(run_frame(args.input, args.output, args.repeat), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
