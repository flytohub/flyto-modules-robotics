# Navigation arrival is proven by the contract

Owner: claude
Branch: claude/navigate-arrival-evidence
Date: 2026-10-04

## What changed

- `capabilities.py`: `robotics.navigate` declares two evidence items
  (`_arrival_evidence`): `arrival` -- `distance_to` over `["x", "y"]`, frame
  `map`, observed as `map_pose`, phases `after`, `settled`, against the
  call's `x`/`y`, `tolerance.absolute` 0.30 m; `arrival.heading` --
  `angle_to` over `["yaw"]` against `yaw_radians` with `optional: true`,
  0.30 rad. Constants `NAV2_XY_GOAL_TOLERANCE_M` / `NAV2_YAW_GOAL_TOLERANCE_RAD`
  (0.25, turtlebot3_navigation2 `burger.yaml` goal checker, read from the
  twin's live params; repo lab config is 0.20 / 0.25) plus 0.05 margins.
- `modules.py`: `core_measure_ops()` feature-detects flyto-core 2.38.0's ops;
  `registrable_contract()` is the one reduction for an older core (drops the
  2.36.0 keys it lacks and evidence items using absolute ops it lacks), with
  one warning each. `build_modules` / `build_fleet_modules` take `measure_ops`.
- `tests/contract_rules.py` (vendored rules) understands the absolute ops,
  `measure.frame` and the optional target.
- Version 1.2.0.

## Why

Nav2 in the twin returned SUCCEEDED with the robot 0.63 m short of its goal
and Cloud read it as arrived: navigate declared no evidence, so nothing judged
the end pose. The tolerance never exceeds what Nav2 itself accepts plus 0.05 m
(map->odom correction jitter between Nav2's last check and the settled
observation).

## Verified

- Without flyto-core: 181 passed, 49 skipped. With flyto-core 2.37.x: 209
  passed, 21 skipped (navigate registers without the arrival evidence). With
  the 2.38.0 branch installed: 230 passed, 0 skipped, including the core judge
  on the 0.63 m case (unusable) and registration through the real registry.
- `ruff check src tests`; `flyto-index verify . --strict` exit 0.

## Not verified

- No live navigation in the twin or on the robot with this contract.

## Follow-ups

- flyto-cloud judges the arrival with the ported ops (branch
  `claude/navigate-arrival`).
- Desktop must bundle flyto-core >= 2.38.0 for the evidence to be declared.
