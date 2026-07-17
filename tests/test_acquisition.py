from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from go2_experiment.recorder import ExperimentRecorder, SyntheticCapture, load_config, write_checksums
from go2_experiment.telemetry import JsonlWriter, _jsonable
from x5_ros.common import read_pairs_csv, split_side_by_side, write_pairs_csv


class AcquisitionTest(unittest.TestCase):
    def test_ros_pair_helpers(self):
        frame = np.zeros((12, 24, 3), np.uint8)
        frame[:, :12] = 17
        frame[:, 12:] = 31
        left, right = split_side_by_side(frame)
        self.assertEqual(left.shape, (12, 12, 3))
        self.assertTrue(np.all(left == 17))
        self.assertTrue(np.all(right == 31))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "pairs.csv"
            write_pairs_csv(path, [(123, "fisheye1/123.png", "fisheye2/123.png")])
            self.assertEqual(read_pairs_csv(path)[0]["timestamp_ns"], "123")

    def test_telemetry_serialization_and_writer(self):
        @dataclass
        class Message:
            tick: int
            vector: list[float]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.jsonl"
            writer = JsonlWriter(path)
            writer.submit({"message": _jsonable(Message(7, [1.0, 2.0]))})
            writer.close()
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["message"], {"tick": 7, "vector": [1.0, 2.0]})

    def test_config_requires_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing config section"):
                load_config(path)

    def test_dry_run_writes_recoverable_run(self):
        root = Path(__file__).parents[1]
        config = load_config(root / "config" / "dry_run.json")
        with tempfile.TemporaryDirectory() as directory:
            config["recording"]["output_root"] = directory
            config["recording"]["min_free_gb"] = 0
            config["recording"]["minimum_processed_hz"] = 1
            run_dir = Path(directory) / "run"
            capture = SyntheticCapture(640, 320, fps=12)
            result = ExperimentRecorder(config, run_dir, capture=capture).record(duration_sec=1.2)
            self.assertEqual(result["status"], "complete")
            self.assertGreater(result["counts"]["raw_frames"], 0)
            self.assertGreater(result["counts"]["processed_frames"], 0)
            self.assertTrue((run_dir / "camera_raw.avi").stat().st_size > 0)
            self.assertTrue((run_dir / "panorama.avi").stat().st_size > 0)
            self.assertTrue((run_dir / "camera_timestamps.csv").stat().st_size > 0)
            self.assertEqual(json.loads((run_dir / "manifest.json").read_text())["status"], "complete")
            write_checksums(run_dir)
            self.assertIn("manifest.json", (run_dir / "SHA256SUMS").read_text())


if __name__ == "__main__":
    unittest.main()
