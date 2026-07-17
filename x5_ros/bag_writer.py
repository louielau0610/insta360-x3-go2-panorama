from __future__ import annotations

import sqlite3
from pathlib import Path

from rclpy.serialization import serialize_message


QOS_YAML = """- history: 1
  depth: 10
  reliability: 1
  durability: 2
  deadline:
    sec: 9223372036
    nsec: 854775807
  lifespan:
    sec: 9223372036
    nsec: 854775807
  liveliness: 1
  liveliness_lease_duration:
    sec: 9223372036
    nsec: 854775807
  avoid_ros_namespace_conventions: false"""


class RawImageBagWriter:
    """Write paired ROS2 Image messages directly to a Foxy sqlite3 bag."""

    def __init__(self, output_dir, commit_pairs=30):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=False)
        self.database_path = self.output_dir / "bag_0.db3"
        self.connection = sqlite3.connect(str(self.database_path))
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute(
            "CREATE TABLE topics(id INTEGER PRIMARY KEY,name TEXT NOT NULL,type TEXT NOT NULL,"
            "serialization_format TEXT NOT NULL,offered_qos_profiles TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE messages(id INTEGER PRIMARY KEY,topic_id INTEGER NOT NULL,"
            "timestamp INTEGER NOT NULL,data BLOB NOT NULL)"
        )
        for topic_id, name in ((1, "/fisheye1/image_raw"), (2, "/fisheye2/image_raw")):
            self.connection.execute(
                "INSERT INTO topics VALUES(?,?,?,?,?)",
                (topic_id, name, "sensor_msgs/msg/Image", "cdr", QOS_YAML),
            )
        self.connection.commit()
        self.commit_pairs = commit_pairs
        self.pairs = 0
        self.first_timestamp = None
        self.last_timestamp = None

    def write_pair(self, left, right, timestamp_ns):
        self.connection.execute(
            "INSERT INTO messages(topic_id,timestamp,data) VALUES(?,?,?)",
            (1, timestamp_ns, sqlite3.Binary(serialize_message(left))),
        )
        self.connection.execute(
            "INSERT INTO messages(topic_id,timestamp,data) VALUES(?,?,?)",
            (2, timestamp_ns, sqlite3.Binary(serialize_message(right))),
        )
        self.first_timestamp = timestamp_ns if self.first_timestamp is None else self.first_timestamp
        self.last_timestamp = timestamp_ns
        self.pairs += 1
        if self.pairs % self.commit_pairs == 0:
            self.connection.commit()

    def close(self):
        self.connection.commit()
        self.connection.execute("CREATE INDEX timestamp_idx ON messages (timestamp ASC)")
        self.connection.commit()
        self.connection.close()
        duration = 0 if self.first_timestamp is None else self.last_timestamp - self.first_timestamp
        timestamp = 0 if self.first_timestamp is None else self.first_timestamp
        metadata = f"""rosbag2_bagfile_information:
  version: 4
  storage_identifier: sqlite3
  relative_file_paths:
    - bag_0.db3
  duration:
    nanoseconds: {duration}
  starting_time:
    nanoseconds_since_epoch: {timestamp}
  message_count: {self.pairs * 2}
  topics_with_message_count:
    - topic_metadata:
        name: /fisheye1/image_raw
        type: sensor_msgs/msg/Image
        serialization_format: cdr
        offered_qos_profiles: ""
      message_count: {self.pairs}
    - topic_metadata:
        name: /fisheye2/image_raw
        type: sensor_msgs/msg/Image
        serialization_format: cdr
        offered_qos_profiles: ""
      message_count: {self.pairs}
  compression_format: ""
  compression_mode: ""
"""
        (self.output_dir / "metadata.yaml").write_text(metadata, encoding="utf-8")
