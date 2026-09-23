# flyto-modules-robotics

## Purpose

Optional Flyto2 builder plugin for authoring robot motion without making the robot a Flyto2 appliance.

The package owns three authoring nodes:
- `robotics.move`
- `robotics.turn`
- `robotics.stop`

Each node emits one bounded `flyto.capability-request.v1` request for commanded equipment. Execution placement, ROS 2 transport, hardware safety, and mission verification live outside this package.

## Production contract

- Move → `motion.advance` or `motion.retreat`
- Turn → `motion.rotate`
- Stop → `motion.halt`

The package contains no production `flyto.robotics.plan.v1`, capability-catalog parser, gateway client, ROS client, runtime daemon, or Pi-side executor.

## Users

- Workflow authors using the Flyto2 builder.
- AI Space / workflow hosts consuming canonical capability requests.
- Maintainers reading historical Gazebo receipts as audit evidence.

## Non-goals

- Driving hardware directly.
- Choosing the execution computer.
- Shipping credentials, hostnames, or adapter addresses in workflow data.
- Declaring a physical mission successful.
- Running Flyto2 Runtime or Core on the robot.
