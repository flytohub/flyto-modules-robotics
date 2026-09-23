# Tasks

## Software closure

- [x] Emit `flyto.capability-request.v1` from Move / Turn / Stop.
- [x] Separate commanded equipment from workflow execution host.
- [x] Route canonical requests through opaque host authority when supplied.
- [x] Map to `motion.advance`, `motion.retreat`, `motion.rotate`, `motion.halt`.
- [x] Align authoring validation with Generic ROS 2 Adapter bounds.
- [x] Add explicit builder `params_schema` metadata.
- [x] Verify the real `flyto-core` registry exposes all three nodes and executes a declaration-only canonical request.
- [x] Remove misleading singular `provides_capability` metadata from multi-capability authoring nodes.
- [x] Remove the retired `flyto.robotics.plan.v1`, capability catalog, gateway, and executable Gazebo authoring/runtime path.
- [x] Keep workflow data free of gateway URLs, credentials, execution-host identities, and Pi-runner assumptions.
- [ ] Decide separately whether to publish to PyPI.

## Physical acceptance

- [ ] Run bounded physical movement only after the area meets the safety clearance floor.
- [ ] Verify interruption and safe stop.
- [ ] Verify independent physical evidence and mission outcome.
- [ ] Verify recovery/reconnect behavior.

Historical Gazebo and earlier TurtleBot3 evidence remains audit history and does not substitute for the pending physical acceptance above.
