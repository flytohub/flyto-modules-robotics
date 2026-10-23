# External ROS 2 adapter architecture

Date: 2026-09-21
Owner: ChatGPT
Branch: `fix/external-ros2-adapter-architecture`

## Decision

TurtleBot3 is standard ROS 2 equipment. This package runs only on a Flyto2
execution computer as an optional workflow-authoring plugin.

Production path:

```text
Workflow / Space Task
  -> selected AI Space computer
  -> flyto.capability-request.v1
  -> approved Generic ROS 2 Adapter
  -> standard ROS 2
  -> commanded robot
```

The resource being commanded is not the machine executing the workflow.

## Source changes

- Added `capability_request_for_step`.
- Move maps to `motion.advance` or `motion.retreat`.
- Turn maps to `motion.rotate`.
- Stop maps to `motion.halt`.
- Module execution returns `commanded_resource` and `capability_request`;
  it no longer returns `requires_device` plus a Pi delivery plan.
- Module metadata no longer claims a gateway credential requirement.
- The old HTTP gateway has no implicit URL and is legacy/Gazebo-only.
- The Gazebo verifier requires an explicit legacy gateway URL.
- README/project memory now forbid Pi-side Flyto2 runtime as a production
  architecture.

## Compatibility

The old preview/trusted plan builders, delivery catalog and gateway client are
retained temporarily so historical simulation/downstream evidence remains
reproducible. They are not production authority.

The builder registry still exposes the historical
`robotics.motion.move_relative` / `turn_relative` / `safe_stop` capability
metadata because the current host registry assigns one capability per module
while Move can now emit two canonical execution capabilities. Removing that
metadata requires a host-registry migration; it must not be silently lied about
in this repository.

## Verification boundary

Unit and strict repository verification must pass before this branch is pushed.
Physical movement is not part of this repository's acceptance and must not be
claimed by source-only tests.
