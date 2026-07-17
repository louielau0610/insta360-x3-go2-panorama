from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage

from .common import compressed_message_to_bgr, write_lossless_png, write_pairs_csv


class PairExporter(Node):
    def __init__(self, output_dir, idle_timeout):
        super().__init__("x5_fisheye_bag_exporter")
        self.output_dir = Path(output_dir)
        self.left_dir = self.output_dir / "fisheye1"
        self.right_dir = self.output_dir / "fisheye2"
        self.left_dir.mkdir(parents=True, exist_ok=False)
        self.right_dir.mkdir(parents=True, exist_ok=False)
        self.idle_timeout = idle_timeout
        self.last_message_time = time.monotonic()
        self.pending = {}
        self.rows = []
        self.received = [0, 0]
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(
            CompressedImage, "/fisheye1/image_compressed", lambda msg: self._receive(0, msg), qos
        )
        self.create_subscription(
            CompressedImage, "/fisheye2/image_compressed", lambda msg: self._receive(1, msg), qos
        )

    def _receive(self, side, message):
        self.last_message_time = time.monotonic()
        self.received[side] += 1
        stamp = message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec
        pair = self.pending.setdefault(stamp, [None, None])
        pair[side] = message
        if pair[0] is None or pair[1] is None:
            return
        left_name = f"{stamp}.png"
        right_name = f"{stamp}.png"
        write_lossless_png(self.left_dir / left_name, compressed_message_to_bgr(pair[0]))
        write_lossless_png(self.right_dir / right_name, compressed_message_to_bgr(pair[1]))
        self.rows.append((stamp, f"fisheye1/{left_name}", f"fisheye2/{right_name}"))
        del self.pending[stamp]
        while len(self.pending) > 20:
            del self.pending[min(self.pending)]

    def idle(self):
        return bool(self.rows) and time.monotonic() - self.last_message_time >= self.idle_timeout

    def finish(self):
        self.rows.sort()
        write_pairs_csv(self.output_dir / "pairs.csv", self.rows)
        summary = {
            "fisheye1_received": self.received[0],
            "fisheye2_received": self.received[1],
            "pairs_exported": len(self.rows),
            "unmatched_stamps": len(self.pending),
        }
        (self.output_dir / "export_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Decode synchronized compressed fisheye pairs from rosbag")
    parser.add_argument("output", type=Path)
    parser.add_argument("--idle-timeout", type=float, default=3)
    args = parser.parse_args(argv)
    rclpy.init()
    node = PairExporter(args.output, args.idle_timeout)
    try:
        while rclpy.ok() and not node.idle():
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        summary = node.finish()
        node.destroy_node()
        rclpy.shutdown()
    print(json.dumps(summary, indent=2))
    return 0 if summary["pairs_exported"] and not summary["unmatched_stamps"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
