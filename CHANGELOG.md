# Changelog

## 0.1.0 — 2026-08-05

Initial version. Not published.

- Three workflow steps: `robotics.move`, `robotics.turn`, `robotics.stop`,
  registered into `flyto-core` through its `flyto.modules` entry point.
- Plans are built locally with bounded parameters and always end in a safe stop.
- The gateway address is configuration, never a step parameter, so identical
  robots share one authored workflow.
- A missing `flyto-core` is logged rather than raised: discovery loads every
  plugin in one loop, and raising would take down the others.

## Unreleased

- `steps.py`: one table mapping a module identifier to the plan it means,
  shared by the modules registered into `flyto-core` and by the robot's own
  job runner. `modules.py` reads it too, so the builder call is written once.
- Argument names and bounds now mirror the robot's capability contract
  (`turn_relative` takes `yaw_delta_rad`, not `radians`; angular speed
  0.1-1.0; `yaw_delta_rad` caps at ±3.0 rad, from which the degree limit is
  derived rather than written as a rounded figure).
- How far and how much are the author's to state: `robotics.move` requires a
  distance and `robotics.turn` an angle. A default would be a robot moving an
  amount nobody chose. How fast and which way keep safe defaults.
