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


def image_message_to_bgr(message):
    if message.encoding != "bgr8":
        raise ValueError(f"unsupported image encoding: {message.encoding}")
    row_bytes = message.width * 3
    if message.step < row_bytes:
        raise ValueError(f"invalid image step: {message.step}")
    data = np.frombuffer(message.data, dtype=np.uint8).reshape(message.height, message.step)
    return np.ascontiguousarray(data[:, :row_bytes].reshape(message.height, message.width, 3))


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
