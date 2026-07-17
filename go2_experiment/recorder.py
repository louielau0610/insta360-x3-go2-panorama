import csv
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from x5_360_pipeline import X5CubemapPipeline

from .telemetry import UnitreeTelemetry


def load_config(path):
    path = Path(path)
    config = json.loads(path.read_text(encoding="utf-8"))
    for section in ("experiment", "camera", "go2", "recording"):
        if section not in config:
            raise ValueError(f"missing config section: {section}")
    return config


def _git_revision():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _source_value(value):
    return int(value) if isinstance(value, str) and value.isdecimal() else value


class SyntheticCapture:
    def __init__(self, width, height, fps=12):
        self.width = width
        self.height = height
        self.fps = fps
        self.index = 0
        self.next_frame_time = time.monotonic()

    def isOpened(self):
        return True

    def read(self):
        delay = self.next_frame_time - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self.next_frame_time = max(self.next_frame_time + 1 / self.fps, time.monotonic())
        image = np.zeros((self.height, self.width, 3), np.uint8)
        image[..., 1] = 50
        x = (self.index * 17) % self.width
        cv2.circle(image, (x, self.height // 2), max(10, self.height // 12), (0, 180, 255), -1)
        cv2.putText(image, str(self.index), (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        self.index += 1
        return True, image

    def get(self, prop):
        if prop == cv2.CAP_PROP_FPS:
            return self.fps
        return 0

    def release(self):
        pass


class ExperimentRecorder:
    """Record a camera stream and read-only GO2 telemetry into one run directory."""

    def __init__(self, config, run_dir=None, capture=None, telemetry_factory=UnitreeTelemetry):
        self.config = config
        self.camera_config = config["camera"]
        self.recording_config = config["recording"]
        self.run_dir = Path(run_dir) if run_dir else self._new_run_dir()
        self.capture = capture
        self.telemetry_factory = telemetry_factory
        self.telemetry = None
        self.stop_requested = False
        self.counts = {"source_frames": 0, "raw_frames": 0, "processed_frames": 0, "read_failures": 0}
        self.processing_ms = []
        self.recording_elapsed_sec = None

    def _new_run_dir(self):
        root = Path(self.recording_config["output_root"]).expanduser()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = self.config["experiment"].get("label", "run").replace(" ", "_")
        return root / f"{timestamp}_{label}"

    def _open_capture(self):
        if self.capture is not None:
            return self.capture
        if self.camera_config.get("source_type") == "synthetic":
            return SyntheticCapture(
                self.camera_config["expected_width"], self.camera_config["expected_height"]
            )
        capture = cv2.VideoCapture(_source_value(str(self.camera_config["source"])))
        if not capture.isOpened():
            raise RuntimeError(f"cannot open camera source: {self.camera_config['source']}")
        if self.camera_config.get("source_type") == "v4l2":
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_config["expected_width"])
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_config["expected_height"])
            capture.set(cv2.CAP_PROP_FPS, self.camera_config.get("fps_hint", 30))
        return capture

    def _check_disk(self):
        target = Path(self.recording_config["output_root"]).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        free_gb = shutil.disk_usage(target).free / 1024**3
        required = float(self.recording_config.get("min_free_gb", 20))
        if free_gb < required:
            raise RuntimeError(f"only {free_gb:.1f} GiB free; require {required:.1f} GiB")
        return free_gb

    def _validate_frame(self, frame):
        expected = (self.camera_config["expected_height"], self.camera_config["expected_width"])
        if frame is None or frame.ndim != 3 or frame.shape[:2] != expected or frame.shape[2] != 3:
            shape = None if frame is None else frame.shape
            raise RuntimeError(f"camera frame shape {shape}, expected {expected + (3,)}")

    def _start_telemetry(self):
        go2 = self.config["go2"]
        if not go2.get("enabled", True):
            return
        self.telemetry = self.telemetry_factory(
            self.run_dir / "telemetry",
            go2["interface"],
            go2.get("lowstate_hz", 50),
            go2.get("sportstate_hz", 20),
        )
        self.telemetry.start()
        if not self.telemetry.wait_ready(float(go2.get("ready_timeout_sec", 8))):
            raise RuntimeError("no GO2 DDS state received; check interface, cable, IP and sport service")

    def preflight(self):
        free_gb = self._check_disk()
        capture = self._open_capture()
        try:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("camera opened but returned no frame")
            self._validate_frame(frame)
            output_root = Path(self.recording_config["output_root"]).expanduser()
            with tempfile.TemporaryDirectory(prefix=".preflight_", dir=output_root) as temporary:
                self.run_dir = Path(temporary)
                self._start_telemetry()
                go2_ready = self.telemetry is not None
                if self.telemetry:
                    self.telemetry.close()
                    self.telemetry = None
                return {
                    "camera_shape": list(frame.shape),
                    "free_gb": free_gb,
                    "go2_ready": go2_ready,
                }
        finally:
            capture.release()
            if self.telemetry:
                self.telemetry.close()

    @staticmethod
    def _video_writer(path, fps, size):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
        if not writer.isOpened():
            raise RuntimeError(f"cannot create video: {path}")
        return writer

    def _manifest(self, status, started_unix_ns, error=None):
        total_elapsed = max((time.time_ns() - started_unix_ns) / 1e9, 1e-9)
        elapsed = self.recording_elapsed_sec or total_elapsed
        manifest = {
            "status": status,
            "error": error,
            "started_unix_ns": started_unix_ns,
            "finished_unix_ns": time.time_ns(),
            "elapsed_sec": total_elapsed,
            "recording_elapsed_sec": self.recording_elapsed_sec,
            "git_revision": _git_revision(),
            "host": {"platform": platform.platform(), "python": platform.python_version()},
            "config": self.config,
            "counts": self.counts,
            "rates": {
                "source_fps": self.counts["source_frames"] / elapsed,
                "processed_fps": self.counts["processed_frames"] / elapsed,
            },
            "processing_ms": {
                "mean": float(np.mean(self.processing_ms)) if self.processing_ms else None,
                "p95": float(np.percentile(self.processing_ms, 95)) if self.processing_ms else None,
            },
            "telemetry": self.telemetry.stats() if self.telemetry else None,
        }
        path = self.run_dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return manifest

    def record(self, duration_sec=None):
        free_gb = self._check_disk()
        self.run_dir.mkdir(parents=True, exist_ok=False)
        (self.run_dir / "config.json").write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        capture = self._open_capture()
        raw_writer = panorama_writer = timestamp_file = None
        started_unix_ns = time.time_ns()
        status, error = "complete", None
        previous_handlers = {}
        try:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("camera opened but returned no first frame")
            self._validate_frame(frame)
            self._start_telemetry()
            source_fps = capture.get(cv2.CAP_PROP_FPS) or self.camera_config.get("fps_hint", 30)
            source_fps = source_fps if 0 < source_fps <= 240 else self.camera_config.get("fps_hint", 30)
            raw_writer = self._video_writer(
                self.run_dir / "camera_raw.avi", source_fps, (frame.shape[1], frame.shape[0])
            )
            layout = self.camera_config.get("layout", "dual_fisheye_sbs")
            pipeline = None
            target_hz = float(self.camera_config.get("process_hz", 6))
            if self.camera_config.get("process", True) and layout == "dual_fisheye_sbs":
                pipeline = X5CubemapPipeline(
                    frame.shape[1] // 2,
                    frame.shape[0],
                    panorama_width=self.camera_config.get("panorama_width", 1280),
                    cube_face_width=self.camera_config.get("cube_face_width", 512),
                    seam_update_interval=self.camera_config.get("seam_update_interval", 3),
                )
                panorama_writer = self._video_writer(
                    self.run_dir / "panorama.avi",
                    target_hz,
                    (pipeline.panorama_width, pipeline.panorama_height),
                )
            timestamp_file = (self.run_dir / "camera_timestamps.csv").open("w", newline="", encoding="utf-8")
            timestamps = csv.writer(timestamp_file)
            timestamps.writerow(["frame_index", "host_unix_ns", "host_monotonic_ns", "processed"])
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[sig] = signal.signal(sig, lambda *_: setattr(self, "stop_requested", True))
            start_mono = time.monotonic()
            next_process = start_mono
            current = frame
            while not self.stop_requested:
                now_mono = time.monotonic()
                if duration_sec is not None and now_mono - start_mono >= duration_sec:
                    break
                unix_ns, mono_ns = time.time_ns(), time.monotonic_ns()
                raw_writer.write(current)
                self.counts["source_frames"] += 1
                self.counts["raw_frames"] += 1
                processed = False
                if pipeline is not None and now_mono >= next_process:
                    processing_start = time.perf_counter()
                    result = pipeline.process_side_by_side(current)
                    panorama_writer.write(result.panorama)
                    self.processing_ms.append((time.perf_counter() - processing_start) * 1000)
                    self.counts["processed_frames"] += 1
                    processed = True
                    next_process = max(next_process + 1 / target_hz, now_mono)
                timestamps.writerow([self.counts["source_frames"] - 1, unix_ns, mono_ns, int(processed)])
                ok, current = capture.read()
                if not ok:
                    self.counts["read_failures"] += 1
                    if self.camera_config.get("source_type") == "file":
                        break
                    raise RuntimeError("camera frame read failed")
            self.recording_elapsed_sec = time.monotonic() - start_mono
        except Exception as exc:
            status, error = "failed", str(exc)
            if "start_mono" in locals():
                self.recording_elapsed_sec = time.monotonic() - start_mono
        finally:
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
            capture.release()
            for handle in (raw_writer, panorama_writer, timestamp_file):
                if handle is not None:
                    handle.release() if hasattr(handle, "release") else handle.close()
            if self.telemetry:
                self.telemetry.close()
            manifest = self._manifest(status, started_unix_ns, error)
        minimum_hz = float(self.recording_config.get("minimum_processed_hz", 6))
        processing_required = (
            self.camera_config.get("process", True)
            and self.camera_config.get("layout", "dual_fisheye_sbs") == "dual_fisheye_sbs"
        )
        if status == "complete" and processing_required:
            if manifest["rates"]["processed_fps"] < minimum_hz * 0.9:
                manifest["status"] = "failed"
                manifest["error"] = f"processed rate below {minimum_hz} Hz"
                (self.run_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
                )
        return manifest


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_checksums(run_dir):
    run_dir = Path(run_dir)
    lines = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(f"{sha256_file(path)}  {path.relative_to(run_dir).as_posix()}")
    (run_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
