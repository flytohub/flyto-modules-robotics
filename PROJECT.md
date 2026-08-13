# flyto-modules-robotics

## Purpose

Make robot motion authorable in the Flyto2 workflow builder, as an install
decision rather than a dependency everybody carries.

`flyto-core` is the software execution engine and does not know what a robot is.
This package is discovered through its existing `flyto.modules` entry point, so a
Flyto2 installation without it stays pure software automation, and one with it
gains motion steps on the canvas.

## Owned surfaces

- The `robotics.*` module identifiers registered into `flyto-core`'s registry.
- The capability each of those modules declares to that registry —
  `robotics.motion.move_relative@1`, `robotics.motion.turn_relative@1`,
  `robotics.safety.safe_stop@1` — one per step and none shared.
- The plan documents those modules build (`flyto.robotics.plan.v1`).
- The loopback client that hands a plan to the robot's own gateway.
- The pure Pi-runner API that derives named-node plans from a verified lower
  capability catalog and refuses implicit legacy-bound fallback.

## Users

An operator authoring a workflow in the Flyto2 builder, and the device-side
runner that executes one of its steps on a robot.

## Non-goals

- **Driving hardware.** No serial port, no ROS topic, no velocity. A step builds
  a plan and posts it; `flyto-robotics` owns the robot.
- **Owning safety.** The gateway validates against a frozen capability registry,
  runs one mission at a time, and sends the final stop if the caller dies. This
  package must never become the thing that guarantees a stop.
- **Naming a machine.** A workflow that carried a host would be bound to one
  robot, which is the duplication the capability model exists to remove.
- **Being required on a robot.** A machine that only runs robot missions needs
  `flyto-robotics` and a runner, not this package. This is for *mixed*
  workflows — crawl a page, then move, then report.
