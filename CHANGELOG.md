# Changelog

## 0.1.1 — 2026-08-08

- `execute` is now a coroutine on all three steps. flyto-core runs a module
  with `return await self.execute()`, so against a real engine 0.1.0 raised
  `object dict can't be used in 'await' expression` and no step could run at
  all. Thirty-six tests passed over it: the stand-in base class in
  `test_registration.py` calls `.execute()` directly, so the engine's own
  contract was never in the room. A test now asserts each one is a coroutine.
- Unreleased entries below were published as part of 0.1.0.

## 0.1.0 — 2026-08-05

First release on PyPI, published 2026-08-08.

- Three workflow steps: `robotics.move`, `robotics.turn`, `robotics.stop`,
  registered into `flyto-core` through its `flyto.modules` entry point.
- Plans are built locally with bounded parameters and always end in a safe stop.
- The gateway address is configuration, never a step parameter, so identical
  robots share one authored workflow.
- A missing `flyto-core` is logged rather than raised: discovery loads every
  plugin in one loop, and raising would take down the others.

### Also in 0.1.0

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
