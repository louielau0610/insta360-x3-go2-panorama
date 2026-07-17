# Validation Implementation

- `tools/validate_x5_samples.py:14` decodes one DNG through the optional `rawpy` dependency and returns BGR data.
- `tools/validate_x5_samples.py:24` repeatedly runs the unified pipeline, validates fixed output shapes, measures timing and temporal stability, and writes inspection JPEGs.
- `tools/validate_x5_samples.py:74` parses sample IDs and acceptance settings, writes `validation_report.json`, and returns a failing exit status when any sample misses the contract.
- `tools/run_x5_frame.py:16` runs one already-decoded side-by-side frame repeatedly, writes the panorama and six cubemap faces, and records deployed-host timing in `frame_report.json`.
- `tools/run_x5_frame.py:54` exposes that single-frame deployment check as a command-line tool without adding DNG decoding to runtime code.

The validator is a repository tool rather than an installed runtime module. Run it from an editable installation or with the repository on `PYTHONPATH`.
