# HMI presentation with live values (battery, position, navigation)

Owner: claude
Branch: claude/hmi-values-20261012 (includes the unpushed `claude/presentation-v1` commit 380b34b)
Date: 2026-10-12
Paired change: flyto-robotics 0.8.0, same branch name (`2026-10-12-hmi-live-values.md` there)

## What changed

- `presentation.py` (1.5.0): the robot's `flyto.resource-presentation.v1`
  block gains live value panels over the channels flyto-robotics 0.8.0
  declares and samples once a second:
  - `goal_distance` readout, hero while `nav.goal.state` is `navigating`
    (`nav.goal.distance_m`, m, 2 decimals);
  - `goal_progress` progress (`nav.goal.progress_pct`, 0-100 %), while navigating;
  - `battery` gauge (`power.battery.percent`, 0-100 %; refused tone < 10,
    attention < 20);
  - `position` position2d (`pose.planar` x / y / heading_deg, goal_x /
    goal_y, plane bounds from `view_x_min` .. `view_y_max`);
  - `voltage` readout (`power.battery.voltage_v`, V);
  - `navigation_state` state panel (idle, navigating, arrived, blocked,
    cancelled, failed).
  The link-lost alert and presence / link / navigate / camera / mode state
  panels are kept. 12 panels, 5158 canonical bytes.
- `ROBOT_CHANNEL_FIELDS` / `NAVIGATION_STATES` mirror flyto-robotics
  `live_telemetry`; both repos pin the same table in tests.
- Schema re-vendored from Cloud `origin/main`
  (`services/device/schemas`, sha256 `cede95aa…5a5736`, adds optional
  `refusal_codes`). Block sha256 `36d57fe2…04da22`.
- `pyproject.toml`: entry point group `flyto2.resource_presentations`,
  `robotics = flyto_modules_robotics.presentation:presentation_block`. The
  runtime finds the block there; neither package imports the other.

## Verified

- `tests/test_presentation.py` written failing first (missing panels,
  missing table, missing entry point), then green.
- flyto-core venv (`flyto-core/.venv/bin/python -B -m pytest -o pythonpath=src tests/`):
  323 passed, 5 skipped (jsonschema not in that venv).
- flyto-indexer venv (has jsonschema, no flyto-core): 259 passed, 69 skipped;
  the schema-validation test ran there.
- Cloud's own `validate_presentation` (from `origin/main`, loaded from a
  temp copy): block accepted. flyto-app `origin/main` schema (`029dcc19…`)
  also accepts it.
- With Cloud's `ResourceManifestDTO`, `with_connection_channel` and the
  telemetry pump's `envelope` (Cloud main checkout imported read-only, `-B`):
  the flyto-robotics manifest with this block validates and each sample
  envelopes.
- `flyto-index verify . --strict`: PASS, 20 pass, 0 warn, 0 fail.
- ruff 0.16.4 (not CI's pinned 0.15.15): the changed files are clean; the 6
  findings in `__init__.py`, `contract_rules.py`, `test_capabilities.py`,
  `test_places.py`, `test_recovery_semantics.py` predate this branch.

## Not verified

- No live values seen: nothing ran against the twin or the physical robot,
  and no App screen rendered this block from Cloud.
- Nothing is deployed to the demo host; its installed pack is unchanged.

## For other repos

- flyto-cloud: no change needed. `MANIFEST_EXTENSIONS` already asks for
  `presentation`; the telemetry pump already runs `telemetry_sampler`.
- flyto-app: no change needed; only registry kinds are used. The App
  fixture `mobile_robot.json` uses `power.battery.value` and
  `nav.goal.distance`; the real fields are `percent` and `distance_m`.
