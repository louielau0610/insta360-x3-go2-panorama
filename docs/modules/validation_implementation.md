# Validation Implementation

- `tools/validate_x5_samples.py:14` decodes one DNG through the optional `rawpy` dependency and returns BGR data.
- `tools/validate_x5_samples.py:24` repeatedly runs the unified pipeline, validates fixed output shapes, measures timing and temporal stability, and writes inspection JPEGs.
- `tools/validate_x5_samples.py:74` parses sample IDs and acceptance settings, writes `validation_report.json`, and returns a failing exit status when any sample misses the contract.

The validator is a repository tool rather than an installed runtime module. Run it from an editable installation or with the repository on `PYTHONPATH`.
