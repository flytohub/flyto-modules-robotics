# HMI presentation declaration for the mobile robot (flyto.resource-presentation.v1)

Owner: claude
Branch: claude/presentation-v1
Date: 2026-10-12

## What changed

- `src/flyto_modules_robotics/presentation.py` — the mobile robot's
  `flyto.resource-presentation.v1` block, built from declarative rows (one
  row per state panel, one per alert panel; no if/elif), plus
  `manifest_with_presentation(manifest, manifest_extensions)`, which adds the
  block only when the host names the `presentation` extension.
- `src/flyto_modules_robotics/schemas/flyto.resource-presentation.v1.schema.json`
  — vendored byte-identical, sha256 `1c600a65996ed336b18986e6e7d71e6e75698e912f877c7a946d441286193c80`
  (the copy flyto-cloud `origin/main` validates with; flyto-app commit
  `f6dd4f3c`). Shipped as package data.
- `tests/test_presentation.py` — schema and block hashes pinned (block
  canonical sha256 `1e1b6563e9d58ae2275736f77e53f1795a3e3dfb7ce313c63d0fac863221e8df`,
  2719 bytes), schema validation, 16 KiB cap, every source is real, state
  options equal each source's vocabulary, manifest unchanged without the
  extension.
- `pyproject.toml` — `jsonschema` in the `dev` extra; schema as package data.
- `CHANGELOG.md`, `STATE.md`.

Panels: `link_lost` (alert, hero, `connection.state` in reconnecting/failed),
`presence` (state, hero, `presence.state`), `connection` (state,
`connection.state`), `navigate` (state, capability `motion.navigate`),
`camera` (state, capability `vision.observe`), `mode` (state,
`deployment_mode`).

## Why

Cloud (patch 0004) and the App render a pack-declared HMI. The robot needed
one, but only over sources it really has. The flyto-robotics ROS 2 manifest
declares `telemetry_channels: []` and has no telemetry sampler, so battery
(the robot does publish `/battery_state` on ROS, but not as a Flyto channel),
pose / `position2d`, navigation state and distance-to-goal panels are
omitted rather than declared over channels that never arrive. The only
channel used is `connection`, which Cloud's execution host declares on every
adapter-backed manifest (`local/resource_connection_telemetry.py`).

## Verified

- Schema hash: `git show origin/main:...` in flyto-cloud and `f6dd4f3c` in
  flyto-app both hash to `1c600a65…193c80`; the vendored file matches.
- `flyto-indexer/.venv/bin/python -I -m pytest -p no:cacheprovider -o pythonpath=src tests/ -q`
  in the worktree: 255 passed, 69 skipped (the skips are the existing
  flyto-core-dependent tests; that interpreter has no flyto-core and no
  installed copy of this pack, so the worktree source was the one tested).
  The new file alone: 14 passed.
- `flyto-index verify . --strict` in the worktree: PASS, 20 pass, 0 warn, 0 fail.
- `ruff check` (flyto-ai venv's ruff): the two new files are clean; 6
  pre-existing findings in `__init__.py` and older tests on `origin/main`
  (import order, `__all__` order, UP035) were left alone.

## Not verified

- No manifest emits the block yet, so nothing end to end: no Cloud upload, no
  App render. Not validated through Cloud's `validate_presentation` itself,
  only through the same schema file with `jsonschema` Draft 2020-12.
- flyto-app `origin/main` has since moved its schema to sha256 `cede95aa…`
  (adds `refusal_codes`). This pack pins the Cloud copy on purpose: Cloud
  rejects unknown panel keys, so `refusal_codes` must not be used until
  Cloud re-vendors.
- No live demo was touched; nothing was installed.

## Follow-ups

- flyto-robotics `adapter_provider`: add `"presentation"` to
  `MANIFEST_EXTENSIONS` and emit the block when requested (importing this
  module optionally, or receiving it from the pack). That repo is not a
  dependency of this pack, nor this pack of it; decide the direction there.
  Do it after the 10/14 demo.
- When the robot publishes real channels (battery, planar pose, Nav2 goal
  state), add rows for `gauge` / `position2d` / `readout` panels over them.
