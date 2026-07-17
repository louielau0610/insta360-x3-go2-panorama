from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import py360convert

from x5_360_pipeline import X5CubemapPipeline

from .common import read_pairs_csv


def main(argv=None):
    parser = argparse.ArgumentParser(description="Post-process exported ROS2 fisheye pairs")
    parser.add_argument("export_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args(argv)
    rows = read_pairs_csv(args.export_dir / "pairs.csv")
    if args.max_frames is not None:
        rows = rows[: args.max_frames]
    if not rows:
        raise ValueError("pairs.csv contains no image pairs")
    first = cv2.imread(str(args.export_dir / rows[0]["fisheye1_path"]))
    if first is None:
        raise ValueError("cannot read first fisheye image")
    pipeline = X5CubemapPipeline(first.shape[1], first.shape[0])
    args.output_dir.mkdir(parents=True, exist_ok=False)
    timings = []
    for row in rows:
        left = cv2.imread(str(args.export_dir / row["fisheye1_path"]))
        right = cv2.imread(str(args.export_dir / row["fisheye2_path"]))
        if left is None or right is None:
            raise ValueError(f"cannot read pair {row['timestamp_ns']}")
        started = time.perf_counter()
        result = pipeline.process(left, right)
        views = {
            "left": py360convert.e2p(result.panorama, (100, 100), -100, 0, (512, 512)),
            "front": py360convert.e2p(result.panorama, (100, 100), 0, 0, (512, 512)),
            "right": py360convert.e2p(result.panorama, (100, 100), 100, 0, (512, 512)),
        }
        timings.append((time.perf_counter() - started) * 1000)
        frame_dir = args.output_dir / row["timestamp_ns"]
        frame_dir.mkdir()
        cv2.imwrite(str(frame_dir / "panorama.jpg"), result.panorama)
        for name, image in result.faces.items():
            cv2.imwrite(str(frame_dir / f"cube_{name}.jpg"), image)
        for name, image in views.items():
            cv2.imwrite(str(frame_dir / f"view_{name}_100.jpg"), image)
        cv2.imwrite(str(frame_dir / "view_300_contact.jpg"), np.concatenate(list(views.values()), axis=1))
    report = {
        "pairs_processed": len(rows),
        "mean_compute_ms": float(np.mean(timings)),
        "p95_compute_ms": float(np.percentile(timings, 95)),
    }
    (args.output_dir / "postprocess_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
