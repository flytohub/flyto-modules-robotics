# flyto-modules-robotics

## Purpose

The robot SDK face of Flyto2, and the proof that a robot needs no robot-specific platform code: every capability is one `@register_module` with `provides_capability` and a `flyto.capability-contract.v1` contract.

| Step | Capability |
|---|---|
| `robotics.advance` | `motion.advance` |
| `robotics.retreat` | `motion.retreat` |
| `robotics.rotate` | `motion.rotate` |
| `robotics.halt` | `motion.halt` |
| `robotics.navigate` | `motion.navigate` |
| `robotics.observe` | `vision.observe` |
| `robotics.map` | `sensing.map` |
| `robotics.places` | `places.list` |
| `robotics.mark_place` | `places.mark` |

Steps run on the AI Space host and hand `{resource_id, capability_id, arguments}` to the host's dispatcher, which calls the flyto-robotics ROS 2 adapter. Execution placement, ROS 2 transport, hardware safety, and mission verification live outside this package.

The package contains no `flyto.robotics.plan.v1`, capability-catalog parser, gateway client, ROS client, runtime daemon, or robot-side executor.

## Users

- Workflow authors using the Flyto2 builder.
- AI Space hosts executing steps through their dispatcher.
- Cloud, reading the declared contracts as data.
- Maintainers reading historical Gazebo receipts as audit evidence.

## Non-goals

- Driving hardware directly.
- Choosing the execution computer.
- Shipping credentials, hostnames, or adapter addresses in workflow data.
- Declaring a physical mission successful.
- Running Flyto2 Runtime or Core on the robot.
