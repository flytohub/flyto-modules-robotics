# State

Date: 2026-08-05

## Status

Installed alongside a real `flyto-core`, verified against a real robot, and
ready to publish.

- Packaged for PyPI the way `flyto-core` is: a `v*` tag builds, tests the
  built wheel, and uploads through Trusted Publishing. The two jobs that
  matter assert the two properties no unit test can — that the wheel imports
  and builds plans with no execution engine installed at all, and that a real
  `flyto-core` from PyPI discovers it through the entry point and registers
  all three steps.
- Not yet on PyPI: a new project needs a pending publisher registered on
  pypi.org first (README, Releasing). Verified locally instead against
  `flyto-core==2.26.11` installed from PyPI, with this package installed from
  its own built wheel — both discovered, three steps registered.

- 54 tests pass, none needing a robot or `flyto-core`.
- `steps.py` holds the one mapping from a module identifier to the plan it
  means. Two readers share it: the modules registered into `flyto-core`, which
  read it to *declare* a motion, and the robot's own job runner, which reads it
  to *perform* one. A copy on either side would be free to drift, and the drift
  would only show as a robot moving differently from what the canvas said.
- The plan now uses the argument names and bounds the robot's own capability
  contract declares. Three did not match and every test passed anyway, because
  each asserted the name this package had chosen rather than the one the robot
  reads: `radians` is `yaw_delta_rad`; angular speed is 0.1-1.0, not 0.05-0.8;
  and `yaw_delta_rad` caps at ±3.0 rad, so the old 360° limit meant any turn
  past ~172° was refused by the gateway after the job had been claimed.
- Verified end to end on 2026-08-08: a `robotics.turn` step authored on the
  canvas, dispatched as a Space task, was built into a plan by the robot's
  runner and carried out — `workflow.turn.left.90deg.v1`, reported succeeded
  with `arrival.pose` and `clearance.measurement`.
- Three steps registered: `robotics.move`, `robotics.turn`, `robotics.stop`.
- `POST /v1/plans`, the gateway endpoint these post to, is on `flyto-robotics`
  `main` and verified on a TurtleBot3 (six live runs, forward and backward,
  measured 0.371-0.372 m against a 0.400 m target, zero safety stops).

## Verified against a real flyto-core

Installed together in a clean Python 3.12 venv, `discover_plugins(force=True)`
finds this package and the three steps reach the registry with the metadata a
canvas needs:

| Module | ui_label | ui_icon | ui_color |
|---|---|---|---|
| `robotics.move` | Move Robot | MoveVertical | `#22D3EE` |
| `robotics.turn` | Turn Robot | RotateCw | `#22D3EE` |
| `robotics.stop` | Stop Robot | Square | `#F87171` |

431 modules in the registry, three of them ours, and `ModuleRegistry.get`
returns the class. Reproduce with:

```bash
python3.12 -m venv /tmp/plugintest
/tmp/plugintest/bin/pip install -e . -e ../flyto-core
/tmp/plugintest/bin/python -c "from core.modules.registry import ModuleRegistry; ModuleRegistry.discover_plugins(force=True); print(sorted(k for k in ModuleRegistry.get_all_metadata() if k.startswith('robotics.')))"
```

Note when reading that output: metadata canonicalises `label` to `ui_label` and
`icon` to `ui_icon`. Checking the former reports `None` and looks like missing
labels — flyto-core's own modules read the same way.

`discover_plugins` reports `module_count: 0` for every plugin including
flyto-core's own `community`. The counter is wrong; registration is not.

## Not verified

- **Appearing on the builder canvas.** Registration is confirmed; nobody has
  yet loaded the builder with this installed and looked.
- **Bounds.** `plan.py` holds its own `MAX_DISTANCE_M` and `MAX_SPEED_MPS`
  constants while the robot's `CapabilityDefinition` already carries
  per-capability bounds. Two copies, only one authoritative. See ROADMAP.

## Last verification

`PYTHONPATH=src python3 -m pytest tests/ -q` — 36 passed.
