# flyto-modules-robotics

Optional robotics **authoring** modules for Flyto2 workflows.

Installing this package adds human-readable Move / Turn / Stop nodes to
`flyto-core`. Those nodes do not drive a robot, do not choose an execution
computer and do not contact a Flyto2 gateway. They emit a canonical capability
request for commanded equipment.

## Production architecture

```text
Workflow / Space Task
        |
        v
AI Space computer selected by Flyto2
        |
        |  capability_request
        v
Generic ROS 2 Adapter
        |
        |  DDS / Zenoh / rosbridge / standard ROS 2
        v
TurtleBot3 or other ROS 2 resource
```

The robot is equipment, not a Flyto2 execution host.

A normal TurtleBot3 therefore needs only its upstream ROS 2 stack: TurtleBot3
packages, Nav2/SLAM as needed, LiDAR/camera drivers, odometry/TF and a standard
ROS transport. It does **not** need this package, `flyto-core`, a Flyto2
credential, job runner, scheduler or gateway.

## Installed workflow nodes

| Step ID | Author meaning | Runtime capability request |
|---|---|---|
| `robotics.move` | bounded straight-line movement | `motion.advance` or `motion.retreat` |
| `robotics.turn` | bounded in-place yaw | `motion.rotate` |
| `robotics.stop` | immediate safe stop | `motion.halt` |

Forward/reverse is decided from the authored Move parameters. A workflow node
does not carry an adapter URL or execution host.

Example result:

```json
{
  "dispatched": false,
  "commanded_resource": "tb3-lab",
  "goal": "move forward 0.40 m then stop safely",
  "capability_request": {
    "contract_version": "flyto.capability-request.v1",
    "resource_id": "tb3-lab",
    "capability_id": "motion.advance",
    "arguments": {
      "distance_m": 0.4,
      "speed_mps": 0.12
    }
  }
}
```

`resource_id` is the equipment being commanded. It is not the Mac/Laptop/
Steam Deck executing the workflow. AI Space / War Room owns execution placement.

## Usage

A workflow author places Move / Turn / Stop on the canvas. At runtime the node
returns a capability request; AI Space / War Room separately chooses which
computer runs the workflow and which approved adapter may command the resource.

No robot-local Flyto2 process participates in this handoff.

## Public authoring API

`flyto_modules_robotics.capability_request_for_step(...)` is the canonical
runtime-facing API for this package.

```python
from flyto_modules_robotics import capability_request_for_step

request = capability_request_for_step(
    "robotics.move",
    {"distance_m": 0.4},
    resource_id="tb3-lab",
)
```

The request contains no hostname, bearer token, Pi identity or ROS
implementation detail.

## Safety boundary

This package never:

- opens a serial device;
- imports `rclpy`;
- publishes `cmd_vel`;
- selects a Flyto2 runner;
- stores a robot credential;
- decides that a mission objective is complete.

The external adapter is responsible for translating an approved capability to a
standard ROS 2 interface. Flyto2 Cloud independently evaluates returned evidence
before declaring the task complete.

## Legacy authoring compatibility

The historical `flyto.robotics.plan.v1` and capability-catalog parser remain
only as pure authoring/preview compatibility while the builder migration
finishes. They perform no network I/O and are not an execution path.

The robot-local HTTP gateway client and Gazebo runtime harness have been
retired. Historical simulation receipts remain under handoffs/results as audit
evidence; new production integration must use
`capability_request_for_step(...)` and an external adapter.

## Installation

```bash
pip install flyto-modules-robotics
```

The package remains optional. It is not currently published to PyPI; build a
wheel locally when testing.

Installing it beside `flyto-core` makes the robotics authoring nodes visible
through the existing `flyto.modules` entry point.

## Testing

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
ruff check src tests
flyto-index verify . --strict
```

The unit suite is pure Python. No unit test needs ROS, a physical robot or
`flyto-core`.

Historical Gazebo receipts remain in the repository as simulation evidence.
There is no executable robot-local gateway/Gazebo runtime path in this package.

## Releasing

The project is not on PyPI. If publishing is approved, the existing Trusted
Publishing workflow is used; no long-lived PyPI token belongs in this
repository.

## License

Apache-2.0. See `LICENSE`.
