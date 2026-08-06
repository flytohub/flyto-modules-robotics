# State

Date: 2026-08-05

## Status

Written and tested; never installed alongside a real `flyto-core`.

- 36 tests pass, none needing a robot or `flyto-core`.
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
