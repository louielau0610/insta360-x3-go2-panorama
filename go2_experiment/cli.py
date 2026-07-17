import argparse
import json
import signal
import sys
import time
from pathlib import Path

from .recorder import ExperimentRecorder, load_config, write_checksums
from .telemetry import UnitreeTelemetry


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only GO2 + X5 experiment acquisition")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "record"):
        command = subparsers.add_parser(name)
        command.add_argument("--config", required=True)
        command.add_argument("--run-dir")
        if name == "record":
            command.add_argument("--duration", type=float)
    checksum = subparsers.add_parser("checksum")
    checksum.add_argument("run_dir")
    telemetry = subparsers.add_parser("telemetry")
    telemetry.add_argument("--config", required=True)
    telemetry.add_argument("--run-dir", required=True)
    telemetry.add_argument("--duration", type=float, default=0)
    args = parser.parse_args(argv)

    if args.command == "checksum":
        write_checksums(args.run_dir)
        return 0
    if args.command == "telemetry":
        config = load_config(args.config)
        go2 = config["go2"]
        output = Path(args.run_dir)
        output.mkdir(parents=True, exist_ok=True)
        collector = UnitreeTelemetry(
            output / "telemetry", go2["interface"], go2.get("lowstate_hz", 50), go2.get("sportstate_hz", 20)
        )
        stop = False
        def request_stop(*_):
            nonlocal stop
            stop = True
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, request_stop)
        collector.start()
        if not collector.wait_ready(go2.get("ready_timeout_sec", 8)):
            collector.close()
            print("ERROR: no GO2 DDS state received", file=sys.stderr)
            return 2
        started = time.monotonic()
        while not stop and (args.duration <= 0 or time.monotonic() - started < args.duration):
            time.sleep(0.1)
        collector.close()
        print(json.dumps(collector.stats(), indent=2))
        return 0
    try:
        recorder = ExperimentRecorder(load_config(args.config), args.run_dir)
        result = recorder.preflight() if args.command == "preflight" else recorder.record(args.duration)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("status", "complete") == "complete" else 1
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
