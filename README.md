# flyto-modules-robotics

Optional robotics **authoring** modules for Flyto2.

This package adds bounded robot-motion steps to the Flyto2 workflow registry. It
does **not** run on a robot, open ROS topics, connect to a robot-local gateway,
own credentials for a robot, or provide a second execution control plane.

## What it provides

When installed beside `flyto-core`, plugin discovery registers:

| Step | Registry capability | Meaning |
|---|---|---|
| `robotics.move` | `robotics.motion.move_relative` | bounded linear motion request |
| `robotics.turn` | `robotics.motion.turn_relative` | bounded yaw request |
| `robotics.stop` | `robotics.safety.safe_stop` | bounded safe-stop request |

Each step builds a `flyto.robotics.plan.v1` document and returns a declaration
with `dispatched: false` and `requires_device`. The workflow step therefore
states **what should happen** and which resource is required; it never performs
the physical action itself.

## Canonical execution path

```text
Flyto2 Space Task / Workflow
        ↓
capability + permission + resource assignment
        ↓
flyto-modules-robotics plan declaration
        ↓
external robotics adapter
        ↓
ROS 2 / Nav2 / Open-RMF / simulator / vendor runtime
        ↓
telemetry + evidence + result
        ↓
Flyto2 independent verification
```

The external adapter owns transport. It may target a simulator or a physical
machine, but no host, IP address, localhost port, ROS graph, or robot credential
is encoded into an authored workflow.

## Public APIs

- `flyto_modules_robotics.plan` — pure bounded plan builders.
- `flyto_modules_robotics.steps.plan_for_step` — offline/authoring plan mapping.
- `flyto_modules_robotics.steps.trusted_plan_for_step` — plan derivation from an
  already validated immutable capability catalog.
- `flyto_modules_robotics.catalog` — strict immutable parser for the robotics
  capability-catalog contract.
- `flyto_modules_robotics.register_all` — the `flyto.modules` plugin entry
  point consumed by `flyto-core`.

There is intentionally no public robot gateway client.

## Safety boundary

This package does not grant authority. Device capability claims, operator
approval, Space permissions, leases, cancellation, safe-stop enforcement,
execution evidence and mission completion belong to the surrounding Flyto2
runtime and the selected external adapter.

A successful ROS/Nav2 action is execution evidence; it is not by itself a Flyto2
mission-completion verdict.

## Testing

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
ruff check src tests
flyto-index verify . --strict
```

The repository unit suite is software-only. Historical Gazebo receipts under
`results/` and `handoffs/` are retained as historical evidence; they do not
represent the current execution architecture and are not physical acceptance.

## Release

The package has not been published to PyPI. Release mechanics remain documented
in the repository workflow and project metadata.

## License

Apache-2.0. See `LICENSE`.
