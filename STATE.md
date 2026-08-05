# State

Date: 2026-08-05

## Status

Written and tested; never installed alongside a real `flyto-core`.

- 36 tests pass, none needing a robot or `flyto-core`.
- Three steps registered: `robotics.move`, `robotics.turn`, `robotics.stop`.
- `POST /v1/plans`, the gateway endpoint these post to, is on `flyto-robotics`
  `main` and verified on a TurtleBot3 (six live runs, forward and backward,
  measured 0.371-0.372 m against a 0.400 m target, zero safety stops).

## Not verified

- **Registration against a real `flyto-core`.** `register_all` is exercised
  against a stand-in base class and decorator, and the import path (`core.modules`)
  matches `flyto-core`'s own entry point declaration, but the two have never been
  installed together.
- **Appearing on the builder canvas.** Follows from registration, unobserved.
- **Bounds.** `plan.py` holds its own `MAX_DISTANCE_M` and `MAX_SPEED_MPS`
  constants while the robot's `CapabilityDefinition` already carries
  per-capability bounds. Two copies, only one authoritative. See ROADMAP.

## Last verification

`PYTHONPATH=src python3 -m pytest tests/ -q` — 36 passed.
