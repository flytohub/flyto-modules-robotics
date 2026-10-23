# The mobile robot declares three screen roles (operator console, field tablet, remote view)

Owner: claude
Branch: claude/hmi-surfaces-20261019 (local, on claude/hmi-first-step-20261018 7406081)
Date: 2026-10-19

## What changed

- `src/flyto_modules_robotics/presentation.py`: `_SURFACES` added to the
  block as `surfaces`. `operator_console` landscape_16_9, `default`,
  `request`/`approve` `max_level` 4, `stop`; `field_tablet` portrait,
  `request` `max_level` 4, `stop`; `remote_view` landscape_16_9, read only.
  `required_panels` `link_lost` + `presence` on every role.
- Schema re-vendored byte-identical from flyto-cloud
  `src/ui/web/backend/services/device/schemas/flyto.resource-presentation.v1.schema.json`
  (sha256 `9dce8cba2082faa83257ac026872df674d44b47ae5375572831b43e95831615e`).
- Block canonical sha256 `72b3b5cd...198fc` ->
  `2f07c993673d9e017aecd4174c8b4f7a9015618cf6d80774435fadda64efc4e7`
  (7,745 bytes); pins in `tests/test_presentation.py`, plus two tests (the
  three roles and their grants; every role names only this pack's panels and
  never hides the link). Version 1.6.0 -> 1.7.0.

## Why

Owner direction 2026-10-19: screen roles and customizable layouts must not be
car-specific. This is the non-car declaration through the same shape (Cloud
`handoffs/2026-10-19-hmi-surface-roles.md`).

## Verified

- `PYTHONPATH=src <flyto-cloud .venv>/bin/python -m pytest tests -q`:
  328 passed, 4 skipped (python3 on this Mac is 3.9 and lacks `tomllib`).
- Cloud's validators on this block: `presentation_problem` None,
  `surfaces_problem` None.
- `ruff check src tests`: 6 findings, all pre-existing (none in the files
  changed here).
- `flyto-index verify . --strict`: 20 pass / 0 warn / 0 fail.

## Not verified

- No App render, no twin or real TurtleBot3 run.
- Install order: only after the Cloud with schema 9dce8cba is deployed.

## Follow-ups

- A robot-arm or leader/follower pack declaring `teach_pendant` /
  `safety_watch` / `leader_station`: Cloud's tests already validate such a
  declaration (`tests/unit/test_hmi_surfaces.py`); no arm pack exists locally.
