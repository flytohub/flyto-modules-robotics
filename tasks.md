# Tasks

## Software closure

- [x] Emit `flyto.capability-request.v1` from every step.
- [x] Separate commanded equipment from workflow execution host.
- [x] Route canonical requests through opaque host authority when supplied.
- [x] Map to `motion.advance`, `motion.retreat`, `motion.rotate`, `motion.halt`.
- [x] Align authoring validation with Generic ROS 2 Adapter bounds.
- [x] Add explicit builder `params_schema` metadata.
- [x] Verify the real `flyto-core` registry exposes every step and executes a declaration-only canonical request.
- [x] One module per capability (advance, retreat, rotate, halt, navigate, observe, map), each with `provides_capability` and a `flyto.capability-contract.v1` contract.
- [x] Register without contracts, with one warning, on a flyto-core older than 2.35.0.
- [x] Declare `role`, `artifacts` and `recovery` (flyto-core 2.36.0); drop them with one warning on an older core.
- [x] Return the declared detour recovery (Cloud's sectors) from a failed advance/retreat step.
- [x] `fleet` pack: navigate-to-waypoint, dock, load, unload through the Open-RMF adapter.
- [ ] Cloud: read a step's `recovery` instead of `services/space_tasks/detour.py`, and adapter `artifacts` instead of rendering the map.
- [x] Remove the retired `flyto.robotics.plan.v1`, capability catalog, gateway, and executable Gazebo authoring/runtime path.
- [x] Keep workflow data free of gateway URLs, credentials, execution-host identities, and Pi-runner assumptions.
- [ ] Decide separately whether to publish to PyPI.

## Physical acceptance

- [ ] Run bounded physical movement only after the area meets the safety clearance floor.
- [ ] Verify interruption and safe stop.
- [ ] Verify independent physical evidence and mission outcome.
- [ ] Verify recovery/reconnect behavior.

Historical Gazebo and earlier TurtleBot3 evidence remains audit history and does not substitute for the pending physical acceptance above.
