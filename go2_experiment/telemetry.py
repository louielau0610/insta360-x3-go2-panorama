import dataclasses
import json
import queue
import threading
import time
from pathlib import Path


def _jsonable(value):
    if dataclasses.is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "item"):
        return value.item()
    return str(value)


class JsonlWriter:
    """Write callback data outside the DDS callback thread."""

    def __init__(self, path, max_queue=10000):
        self.path = Path(path)
        self.queue = queue.Queue(maxsize=max_queue)
        self.dropped = 0
        self.written = 0
        self._stop = object()
        self._thread = threading.Thread(target=self._run, name=f"writer-{self.path.stem}")
        self._thread.start()

    def submit(self, record):
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self.dropped += 1

    def _run(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8", buffering=1) as output:
            while True:
                record = self.queue.get()
                if record is self._stop:
                    break
                output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                self.written += 1

    def close(self):
        self.queue.put(self._stop)
        self._thread.join()


class UnitreeTelemetry:
    """Subscribe to GO2 state topics without creating any command publisher."""

    def __init__(self, output_dir, interface, lowstate_hz=50, sportstate_hz=20):
        self.output_dir = Path(output_dir)
        self.interface = interface
        self.lowstate_interval_ns = int(1e9 / lowstate_hz) if lowstate_hz else 0
        self.sportstate_interval_ns = int(1e9 / sportstate_hz) if sportstate_hz else 0
        self.low_writer = JsonlWriter(self.output_dir / "go2_lowstate.jsonl")
        self.sport_writer = JsonlWriter(self.output_dir / "go2_sportmodestate.jsonl")
        self.last_low_ns = 0
        self.last_sport_ns = 0
        self.first_message = threading.Event()
        self._subscribers = []
        self.active = True

    def start(self):
        try:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
            from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, SportModeState_
        except ImportError as error:
            self.close()
            raise RuntimeError("unitree_sdk2py is not installed; run scripts/install_go2.sh") from error

        ChannelFactoryInitialize(0, self.interface)
        low_subscriber = ChannelSubscriber("rt/lowstate", LowState_)
        sport_subscriber = ChannelSubscriber("rt/lf/sportmodestate", SportModeState_)
        low_subscriber.Init(self._on_lowstate, 10)
        sport_subscriber.Init(self._on_sportstate, 10)
        self._subscribers = [low_subscriber, sport_subscriber]

    @staticmethod
    def _record(topic, message, host_mono_ns):
        return {
            "topic": topic,
            "host_unix_ns": time.time_ns(),
            "host_monotonic_ns": host_mono_ns,
            "message": _jsonable(message),
        }

    def _on_lowstate(self, message):
        if not self.active:
            return
        now = time.monotonic_ns()
        if self.lowstate_interval_ns and now - self.last_low_ns < self.lowstate_interval_ns:
            return
        self.last_low_ns = now
        self.low_writer.submit(self._record("rt/lowstate", message, now))
        self.first_message.set()

    def _on_sportstate(self, message):
        if not self.active:
            return
        now = time.monotonic_ns()
        if self.sportstate_interval_ns and now - self.last_sport_ns < self.sportstate_interval_ns:
            return
        self.last_sport_ns = now
        self.sport_writer.submit(self._record("rt/lf/sportmodestate", message, now))
        self.first_message.set()

    def wait_ready(self, timeout):
        return self.first_message.wait(timeout)

    def stats(self):
        return {
            "lowstate_written": self.low_writer.written,
            "lowstate_dropped": self.low_writer.dropped,
            "sportstate_written": self.sport_writer.written,
            "sportstate_dropped": self.sport_writer.dropped,
        }

    def close(self):
        self.active = False
        for writer in (self.low_writer, self.sport_writer):
            if writer._thread.is_alive():
                writer.close()
