from __future__ import annotations

import array
import argparse
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

from .bag_writer import RawImageBagWriter
from .common import split_side_by_side


def _image_message(image, stamp, frame_id):
    message = Image()
    message.header.stamp = stamp
    message.header.frame_id = frame_id
    message.height, message.width = image.shape[:2]
    message.encoding = "bgr8"
    message.is_bigendian = False
    message.step = message.width * 3
    payload = array.array("B")
    payload.frombytes(image.data)
    message.data = payload
    return message


def _gstreamer_source(path):
    return (
        f"filesrc location={path} ! h264parse ! avdec_h264 ! videoconvert ! "
        "video/x-raw,format=BGR ! appsink drop=true max-buffers=2 sync=false"
    )


class DualFisheyePublisher(Node):
    def __init__(self):
        super().__init__("x5_dual_fisheye_publisher")
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.fisheye1 = self.create_publisher(Image, "/fisheye1/image_raw", qos)
        self.fisheye2 = self.create_publisher(Image, "/fisheye2/image_raw", qos)

    def publish_pair(self, frame):
        left, right = split_side_by_side(frame)
        stamp = self.get_clock().now().to_msg()
        left_message = _image_message(left, stamp, "x5_fisheye1_optical_frame")
        right_message = _image_message(right, stamp, "x5_fisheye2_optical_frame")
        self.fisheye1.publish(left_message)
        self.fisheye2.publish(right_message)
        timestamp_ns = stamp.sec * 1_000_000_000 + stamp.nanosec
        return timestamp_ns, left_message, right_message


def run(args):
    recorder = None
    anchor_fd = None
    temporary = None
    if args.input_h264:
        source = Path(args.input_h264)
    else:
        if not args.capture_output:
            raise ValueError("--capture-output is required for a live camera")
        temporary = tempfile.TemporaryDirectory(prefix="x5_ros_fifo_")
        source = Path(temporary.name) / "stream0.h264"
        os.mkfifo(source)
        anchor_fd = os.open(source, os.O_RDWR | os.O_NONBLOCK)
        recorder = subprocess.Popen([
            str(args.recorder), "--output", str(args.capture_output),
            "--duration", str(args.duration), "--stream0-fifo", str(source),
        ])

    capture = cv2.VideoCapture(_gstreamer_source(source), cv2.CAP_GSTREAMER)
    if anchor_fd is not None:
        os.close(anchor_fd)
        anchor_fd = None
    if not capture.isOpened():
        raise RuntimeError(f"cannot decode X5 stream: {source}")

    rclpy.init()
    node = DualFisheyePublisher()
    bag = RawImageBagWriter(args.bag_output) if args.bag_output else None
    started = time.monotonic()
    next_publish = started
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    next_input = started
    decoded = published = failures = 0
    first_stamp = last_stamp = None
    try:
        while rclpy.ok():
            if args.duration > 0 and time.monotonic() - started >= args.duration:
                break
            if recorder is None:
                delay = next_input - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                next_input = max(next_input + 1.0 / source_fps, time.monotonic())
            ok, frame = capture.read()
            if not ok:
                failures += 1
                if recorder is None or recorder.poll() is not None:
                    break
                continue
            decoded += 1
            now = time.monotonic()
            if now < next_publish:
                continue
            stamp, left_message, right_message = node.publish_pair(frame)
            if bag is not None:
                bag.write_pair(left_message, right_message, stamp)
            first_stamp = stamp if first_stamp is None else first_stamp
            last_stamp = stamp
            published += 1
            next_publish = max(next_publish + 1.0 / args.publish_fps, now)
            if published == 1 and args.ready_file:
                Path(args.ready_file).write_text(str(stamp), encoding="utf-8")
            rclpy.spin_once(node, timeout_sec=0)
    finally:
        if recorder is not None and recorder.poll() is None:
            recorder.send_signal(signal.SIGINT)
            recorder.wait(timeout=15)
        if bag is not None:
            bag.close()
        capture.release()
        node.destroy_node()
        rclpy.shutdown()
        if temporary is not None:
            temporary.cleanup()
    result = {
        "decoded_frames": decoded,
        "published_pairs": published,
        "read_failures": failures,
        "first_stamp_ns": first_stamp,
        "last_stamp_ns": last_stamp,
        "publish_fps_target": args.publish_fps,
    }
    print(json.dumps(result, indent=2))
    if published == 0:
        return 2
    if recorder is not None and recorder.returncode != 0:
        return recorder.returncode
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Publish synchronized X5 fisheye ROS2 images")
    parser.add_argument("--input-h264", type=Path)
    parser.add_argument("--recorder", type=Path, default=Path("bin/x5-stream-recorder"))
    parser.add_argument("--capture-output", type=Path)
    parser.add_argument("--duration", type=float, default=0)
    parser.add_argument("--publish-fps", type=float, default=10)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--bag-output", type=Path)
    args = parser.parse_args(argv)
    if args.publish_fps <= 0:
        parser.error("--publish-fps must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
