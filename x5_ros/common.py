from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np


def split_side_by_side(frame):
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("expected a BGR image")
    height, width = frame.shape[:2]
    if width != height * 2:
        raise ValueError(f"expected two square fisheyes, got {width}x{height}")
    return np.ascontiguousarray(frame[:, :height]), np.ascontiguousarray(frame[:, height:])


def encode_jpeg(image, quality):
    if not 1 <= quality <= 100:
        raise ValueError("JPEG quality must be between 1 and 100")
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("cannot encode JPEG image")
    return encoded


def compressed_message_to_bgr(message):
    image = cv2.imdecode(np.frombuffer(message.data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("cannot decode compressed image")
    return image


def write_pairs_csv(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["timestamp_ns", "fisheye1_path", "fisheye2_path"])
        writer.writerows(rows)


def read_pairs_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def write_lossless_png(path, image):
    if not cv2.imwrite(str(path), image, [cv2.IMWRITE_PNG_COMPRESSION, 1]):
        raise RuntimeError(f"cannot write image: {path}")


class RawPairWriter:
    """Write synchronized decoded pixels as uncompressed BMP pairs."""

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.left_dir = self.output_dir / "fisheye1"
        self.right_dir = self.output_dir / "fisheye2"
        self.left_dir.mkdir(parents=True, exist_ok=False)
        self.right_dir.mkdir(parents=True, exist_ok=False)
        self.index = (self.output_dir / "pairs.csv").open("w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.index)
        self.writer.writerow(["timestamp_ns", "fisheye1_path", "fisheye2_path"])
        self.pairs = 0

    def write_pair(self, left, right, timestamp_ns):
        left_relative = f"fisheye1/{timestamp_ns}.bmp"
        right_relative = f"fisheye2/{timestamp_ns}.bmp"
        if not cv2.imwrite(str(self.output_dir / left_relative), left):
            raise RuntimeError(f"cannot write raw image: {left_relative}")
        if not cv2.imwrite(str(self.output_dir / right_relative), right):
            raise RuntimeError(f"cannot write raw image: {right_relative}")
        self.writer.writerow([timestamp_ns, left_relative, right_relative])
        self.index.flush()
        self.pairs += 1

    def close(self):
        self.index.close()
