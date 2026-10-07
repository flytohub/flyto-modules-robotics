# Architecture

## Production path

```text
Flyto2 Cloud / War Room
        |
        | approves the resource's capabilities, selects host + commanded resource
        v
AI Space execution host (Flyto2 Desktop + flyto-core + this package)
        |
        | step -> host dispatcher: {resource_id, capability_id, arguments}
        v
flyto-robotics Generic ROS 2 adapter (on the same host)
        |
        | standard ROS 2 / DDS / rosbridge
        v
robot resource (stock ROS 2, no Flyto2 software)
```

This repository owns only the capability declarations and the step that hands
one bounded request to the host's dispatcher.

## One module per capability

`capabilities.py` holds one row per capability: module id, capability id,
display, `params_schema` (bounds as `min`/`max`/`unit`), and a
`flyto.capability-contract.v1` contract. `modules.py` registers each row with
one `@register_module(..., provides_capability=..., contract=...)`. flyto-core
discovers them through the `flyto.modules` entry point.

| Step | Capability |
|---|---|
| `robotics.advance` | `motion.advance` |
| `robotics.retreat` | `motion.retreat` |
| `robotics.rotate` | `motion.rotate` |
| `robotics.halt` | `motion.halt` |
| `robotics.navigate` | `motion.navigate` |
| `robotics.observe` | `vision.observe` |
| `robotics.map` | `sensing.map` |
| `robotics.places` | `places.list` |
| `robotics.mark_place` | `places.mark` |

## Canonical bounds

Parameter names, bounds, units and speed defaults equal the flyto-robotics
adapter's `generic_ros2_adapter.ARGUMENTS`; `tests/test_capabilities.py` pins
them to a copy of that table. Out-of-range values are refused, never clamped.

## Contracts

Every contract satisfies the v1 rules in flyto-core
`docs/CAPABILITY_CONTRACT.md`. Evidence tolerances equal Cloud's
`motion_verification.py` constants (travel along the starting heading
within max(0.03 m, 0.3·d), signed, retreat as `scale: -1`; heading 0.15 rad;
signed rotation max(0.1 rad, 0.2·|yaw|); rotation drift 0.05 m; settle
0.02 m), measured from `before` to `settled`. Tests run flyto-core's `judge`
against a transcription of Cloud's check and require identical verdicts. Cloud reads the contract as data and judges the host's observations
against it; this package never judges its own outcome.

When the installed flyto-core predates `contract=` (before 2.35.0), the steps
register without contracts and one warning is logged; Cloud then falls back to
its built-in capability rows.

## Recovery and artifacts

Advance and retreat declare `recovery` (flyto-core 2.36.0): substitutes, the
`recovery_context` observation and guidance. The adapter reports the facts;
`recovery.py` turns its sweep into six nearest-return sectors, and a failed
step returns the result as `recovery`. Captures declare `artifacts`; the
adapter returns them in the contract's transport and a step's output keeps
only their digests.

The motion contracts' `recovery` blocks also carry recovery semantics
(flyto-core 2.39.0): `on` / `alternatives` / `preserves` / `resource_scope` on
advance and `fills` on all four motions. They are data for the host, which
matches roles across the resource's contracts; `recovery.py` ignores them and
returns no step `recovery` for a block without `capabilities`.
`modules._registrar` drops them where the installed core has no
`RECOVERY_FIELDS`.

## Fleet pack

`fleet_pack.register_fleet` (entry point `fleet`) registers `fleet.navigate`
(`motion.navigate_to_waypoint`), `fleet.dock`, `fleet.load`, `fleet.unload`
through the same `_capability_step` and dispatcher boundary. The resource is a
fleet (`fleet:<name>`), the adapter is flyto-robotics' `open_rmf.fleet`, and
Open-RMF picks the robot.

## Host dispatch

With no dispatcher in the step context the step only declares its request. An
AI Space host injects an opaque dispatcher under
`_flyto_runtime_external_capability_dispatcher`; its type must carry
`_flyto_runtime_opaque = True`, so workflow data cannot forge it. The step
passes exactly `{resource_id, capability_id, arguments}` and maps the adapter
outcome (`completed`, `refused`, `timeout`, `cancelled`, `failed`) to the step
result, keeping the execution record either way.

## Safety invariants

- no `rclpy`, serial access, motor driver, socket or `cmd_vel` here;
- no host, address or token in a request or a step parameter;
- commanded equipment and execution host remain separate identities;
- clearance, safety basis, deployment mode and safe stop are enforced by the
  adapter and the host dispatcher, not re-implemented here;
- execution success is not mission verification; Cloud judges evidence;
- physical acceptance remains outside software closure.

## Removed legacy path

`flyto.robotics.plan.v1`, the delivery capability catalog, the robot-local
HTTP gateway, the executable Gazebo runtime, and the Move / Turn / Stop
authoring nodes are gone. Historical files under `handoffs/` and `results/`
remain evidence only.
