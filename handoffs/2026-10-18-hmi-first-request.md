# An idle robot's HMI offers a first request

Owner: claude
Branch: claude/hmi-first-step-20261018
Date: 2026-10-18

Converged P0 step: 2 (Proof #1, TurtleBot3). The operator starts task A from
the phone HMI.

## What changed

- `src/flyto_modules_robotics/presentation.py`: `REQUEST_EXAMPLES` (four
  zh-TW/en chips) emitted as the block's `request_examples`; a `heading`
  readout over `pose.planar.heading_deg`; a `localization` state panel over
  `pose.planar.frame` (`POSE_FRAMES`, mirrored from flyto-robotics
  `live_telemetry.CHANNELS`).
- `schemas/flyto.resource-presentation.v1.schema.json`: re-vendored from
  flyto-cloud origin/main (f1e72d566, #579), sha256 `e8df2eae...`.
- `tests/test_presentation.py`: new schema and block pins; tests for the
  examples, heading and localization; the "no field Cloud does not validate"
  test now checks the block's keys against the vendored schema.
- Version 1.6.0 (`pyproject.toml`, `__init__.py`, `modules.py`).

## Why

The owner ran the HMI on 2026-10-17 without creating a task. The cockpit
showed the robot's readings, the "no tasks" card and an empty request field.
The App already renders `request_examples` as chips, but this pack never
declared any, so nothing told the operator what the robot could be asked.

## Verified

- `PYTHONPATH=src python3.12 -m pytest tests -q` (scratch venv with pytest +
  jsonschema): 261 passed, 69 skipped. The jsonschema validation test ran.
- `ruff check src tests`: 6 findings, all pre-existing on main (none in the
  files changed here).

## Not verified

- No App render of the 1.6.0 block on a phone, and no run on the twin or the
  robot.
- Production Cloud is 8f737a101, whose schema (`cede95aa...`) has
  `additionalProperties: false` and no `request_examples`. Installing 1.6.0
  there would make Cloud refuse the whole presentation block. It must wait
  for a deploy that includes f1e72d566 (converged P0 step 1).

## Follow-ups

- After the Cloud deploy, install 1.6.0 on the robot host and check the chips
  render in the phone HMI.
- The phone HMI does not draw the robot's camera or LiDAR live channels
  (`flyto.live-channels.v1`: `camera` ws-jpeg, `scan`, `pose`); only the web
  live view does. That is App work, recorded separately.
