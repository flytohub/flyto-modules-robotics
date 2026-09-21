# Architecture

## Product boundary

This repository owns **workflow authoring**, not robot execution.

```text
                 Flyto2 Cloud / War Room
                        |
                 selects policy/resource
                        |
                        v
               AI Space computer
               (execution host)
                        |
              workflow module emits
           flyto.capability-request.v1
                        |
                        v
              Generic ROS 2 Adapter
                        |
          standard ROS 2 / DDS / Zenoh
                        |
                        v
                  robot resource
              (commanded equipment)
```

The execution host and commanded resource are different concepts. A TurtleBot3
resource id never means "put the Flyto2 job runner on this Pi".

## Layer 1 — builder plugin

`modules.py` registers Move / Turn / Stop with `flyto-core` through the
existing `flyto.modules` entry point.

The module:

1. validates existing canvas parameters;
2. resolves the commanded equipment id from `resource_id` (with
   `robot_id` accepted only as a backward-compatible authoring alias);
3. emits one canonical capability request;
4. performs no network or ROS operation.

The result deliberately has no `requires_device` execution-placement field.
It carries `commanded_resource` instead.

## Layer 2 — capability request

`capability_request.py` is the production contract of this package.

| Authored node | Capability |
|---|---|
| Move forward | `motion.advance` |
| Move reverse | `motion.retreat` |
| Turn | `motion.rotate` |
| Stop | `motion.halt` |

The request contains:

- contract version;
- commanded resource id;
- capability id;
- bounded arguments;
- human-readable goal.

It contains no host, gateway, token, execution-computer identity or ROS node
name.

The current Move/Turn/Stop parameter validation reuses the existing pure preview
plan builders so authored bounds have one implementation while migration is in
progress. The lower gateway plan never crosses the production request boundary.

## Layer 3 — external adapter

This repository does not implement the Generic ROS 2 Adapter. That adapter runs
on the selected AI Space computer and maps approved capabilities to standard ROS
2, for example Nav2 actions and `/cmd_vel`.

The adapter returns execution observations/evidence; it does not decide the
mission verdict. Cloud verification remains authoritative.

## Legacy compatibility

`plan.py`, `catalog.py` and explicitly named `legacy_gateway.py` preserve
historical `flyto.robotics.plan.v1` / Gazebo evidence while downstream consumers
migrate. `legacy_gateway` is not re-exported from the package top level.

They are explicitly outside the production authority path.

The legacy HTTP client:

- is never imported or called by `modules.py`;
- has no default URL;
- requires explicit `FLYTO_ROBOTICS_GATEWAY_URL`;
- exists for reproduction/compatibility, not deployment on a robot.

## flyto-core import boundary

`flyto-core` is imported only inside `register_all`. An absent or
incompatible registration API is logged and skipped; failures inside a present
plugin continue to raise so discovery does not silently lose robotics nodes.

## Safety invariants

- No hardware access in this package.
- No `rclpy`, serial, velocity or device driver.
- No host/address in workflow parameters.
- No robot-side Flyto2 runtime assumption.
- No implicit legacy gateway address.
- Capability discovery/authoring never grants execution authority.
- Robot execution success never equals mission completion.
