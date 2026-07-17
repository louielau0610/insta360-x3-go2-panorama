# GO2 Field Acquisition Principles

## Responsibility and non-goals

The acquisition layer creates reproducible, recoverable camera and robot-state records. It does not command the GO2, choose a gait, synchronize clocks over a network, or hide source-format mismatches. Motion remains under the official remote/app or a separately reviewed controller.

## Safety boundary

`UnitreeTelemetry` imports only channel initialization and subscriber types. It subscribes to `rt/lowstate` and `rt/lf/sportmodestate`; it never imports or constructs `ChannelPublisher`, `SportClient`, `LowCmd`, or motion-switcher APIs. Failure to receive state is a preflight failure rather than permission to continue without telemetry.

## Time and data integrity

Every camera frame and DDS callback is stamped with both host Unix nanoseconds and host monotonic nanoseconds. Unix time supports cross-device correlation; monotonic time protects duration/order measurements against wall-clock adjustment. Unitree's message-native timestamp is retained inside the serialized message.

Camera and DDS callbacks are not assumed to share a hardware clock. The field procedure therefore requires an observable start event and preservation of raw streams. Any later clock-model correction must be recorded as a derived artifact, never applied destructively.

The recorder writes a manifest even after runtime failure. Video uses MJPEG AVI for recoverable generic capture; the X5 SDK path preserves elementary encoded streams without transcoding. `SHA256SUMS` is generated only after all writers close.

## Throughput and failure behavior

Raw camera frames are written at source rate. Online panorama generation is scheduled independently at 6 Hz by default. A processing shortfall marks the run failed but does not delete raw data. Camera read failure, wrong dimensions, insufficient disk, missing DDS state, unwritable video, or an empty SDK primary stream fails the run explicitly. CameraSDK stream index 0 is the required X5 preview; stream index 1 is retained when present but is optional.

After an X5 USB reconnect, Android-mode selection can cause another USB enumeration before CameraSDK becomes ready. The native recorder therefore retries discovery for at most 15 seconds. It does not retry after recording starts or conceal a mid-run disconnect.

## Extension rule

New camera adapters should produce decoded BGR frames for `ExperimentRecorder` or preserve encoded bytes plus callback timestamps like the native X5 adapter. New GO2 topics belong in `UnitreeTelemetry` and must remain subscriber-only. Protect changes with a synthetic run test and an actual-hardware preflight.
