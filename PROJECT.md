# flyto-modules-robotics

## Purpose

Make physical-motion intent authorable in Flyto2 workflows without turning a
robot into a Flyto2 appliance.

The package is an optional `flyto-core` builder plugin. It converts authored
Move / Turn / Stop nodes into canonical capability requests that an external
adapter can execute.

## Owned surfaces

- `robotics.move`, `robotics.turn`, `robotics.stop` authoring nodes.
- `flyto.capability-request.v1` projection for those nodes.
- Mapping from authored direction/angle to canonical Space capabilities:
  `motion.advance`, `motion.retreat`, `motion.rotate`, `motion.halt`.
- Pure legacy preview/plan helpers while old authoring consumers migrate.

## Users

- Workflow authors using the Flyto2 builder.
- AI Space / workflow runtimes consuming the emitted capability request.
- Maintainers reading retained historical Gazebo receipts as audit evidence.

## Non-goals

- Driving hardware or importing ROS 2.
- Running a Flyto2 daemon on the robot.
- Choosing the execution computer.
- Storing credentials or adapter addresses in workflow steps.
- Owning hardware safety or mission-verification truth.
- Defining a competing robot hardware protocol.

The physical robot is standard ROS 2 equipment. The execution adapter belongs on
an external computer.
