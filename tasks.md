# Tasks

## Current external-adapter closure

- [x] Change Move / Turn / Stop runtime output from Pi delivery plans to
      `flyto.capability-request.v1`.
- [x] Separate commanded equipment from execution-host placement:
      `commanded_resource` is now the robot/resource, while AI Space / War Room
      selects the computer that executes the workflow.
- [x] Map authored nodes to canonical Space capabilities:
      `motion.advance`, `motion.retreat`, `motion.rotate`, `motion.halt`.
- [x] Ensure production capability requests contain no gateway URL, token,
      execution host, `robot_id` runtime placement or implicit loopback.
- [x] Remove the legacy gateway's implicit `127.0.0.1:8766` default; historical
      Gazebo use must opt in through explicit configuration.
- [x] Mark lower delivery catalog / plan / gateway APIs as legacy
      simulation/migration compatibility.
- [ ] Wire the AI Space/workflow runtime to consume
      `flyto.capability-request.v1` and call the approved Generic ROS 2 Adapter.
- [ ] Rework builder registration metadata once the host registry can represent
      a module that may emit more than one execution capability
      (`robotics.move` can advance or retreat).
- [ ] Load the real Flyto2 builder with this package installed and confirm the
      three authoring nodes are visible and emit the canonical request.
- [ ] Remove legacy `gateway.py`, lower delivery-catalog coupling and
      `flyto.robotics.plan.v1` after the final downstream/Gazebo consumer
      migrates.
- [ ] Decide whether to publish to PyPI and under which account.

## Physical acceptance

Physical TurtleBot3 acceptance belongs to the external-adapter / Cloud closure,
not to a Pi runner in this repository. A real bounded movement, interruption,
safe stop and independent evidence verification remain required before physical
closure can be claimed.

## Historical completed evidence

- 2026-08-09 Gazebo closed-loop run
  `mrg-20260809T101631Z-79266` passed and remains simulation evidence.
- `flyto-core` 2.27 registration/capability discovery was proved with the
  built 0.1.1 wheel; no physical execution was implied.
- The 2026-08 Pi-runner / delivery-gateway work is retained in historical
  handoffs only and is superseded for production by the 2026-09-21 architecture.
