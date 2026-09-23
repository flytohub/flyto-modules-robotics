# flyto-modules-robotics

Optional robotics authoring modules for Flyto2 workflows.

Installing this package beside `flyto-core` adds Move / Turn / Stop nodes to the builder. The nodes emit bounded `flyto.capability-request.v1` requests for commanded equipment; they never choose an execution computer, import ROS, or talk directly to a robot.

## Architecture

Workflow / Space Task → AI Space execution host → `flyto.capability-request.v1` → Generic ROS 2 Adapter → robot resource.

The robot is equipment, not a Flyto2 execution host.

## Usage

Install the package beside `flyto-core`, then author Move / Turn / Stop nodes in the normal builder. The builder uses schemas shipped by this plugin; AI Space chooses execution placement independently.

| Step | Canonical capability |
|---|---|
| `robotics.move` forward | `motion.advance` |
| `robotics.move` reverse | `motion.retreat` |
| `robotics.turn` | `motion.rotate` |
| `robotics.stop` | `motion.halt` |

Move validates 0.05–2.0 m. The builder exposes 0.02–0.20 m/s so one authored Move remains valid in both directions; the pure request API accepts forward speeds up to 0.25 m/s. Turn validates 1–180 degrees. Stop has no retired dwell argument.

## API

The public production API is `capability_request_for_step`.

    from flyto_modules_robotics import capability_request_for_step

    request = capability_request_for_step(
        "robotics.move",
        {"distance_m": 0.4},
        resource_id="tb3-lab",
    )

The result contains the commanded resource, canonical capability, bounded arguments, and goal. It contains no gateway URL, token, execution host, Pi identity, or ROS implementation detail.

## Builder integration

The package is discovered through the existing `flyto.modules` entry point. The three nodes publish explicit `params_schema` metadata to the real `flyto-core` registry.

`provides_capability` is deliberately unset on the authoring classes because Move can produce two different execution capabilities. Resource admission follows the emitted canonical request.

## Host execution

Without host authority, execution is declaration-only. A selected AI Space host may inject one opaque trusted dispatcher; the module then forwards the exact canonical request and returns the execution record. The package cannot manufacture that dispatcher from workflow data.

## Configuration

There is no robot hostname, gateway URL, credential, or runtime address to configure in this package. The execution host and external adapter are selected elsewhere in Flyto2.

## Removed legacy path

The retired `flyto.robotics.plan.v1`, delivery capability catalog, robot-local HTTP gateway, and executable Gazebo runtime path are no longer production APIs in this package. Historical receipts remain in handoffs/results only.

## Installation

    pip install flyto-modules-robotics

The package is optional and is installed on the authoring/execution computer, not on the robot.

## Testing

    PYTHONPATH=src python3.11 -m pytest tests/ -q
    ruff check src tests
    flyto-index verify . --strict

Software verification requires no physical robot. Physical TurtleBot3 movement remains a separate acceptance step.

## Development

Keep the package pure: no ROS imports, no robot-local runtime, no gateway client, and no execution-host selection. Update project-memory files when changing contract boundaries.

## Release

The package is currently not published to PyPI. The repository contains a Trusted Publishing workflow for a future explicit release decision.

## License

Apache-2.0. See `LICENSE`.
