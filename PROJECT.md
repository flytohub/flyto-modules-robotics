# flyto-modules-robotics

## Purpose

Make bounded robotics intent authorable in Flyto2 without putting robot
transport or hardware control into `flyto-core` or into this plugin.

## Owned surfaces

- `robotics.move`, `robotics.turn`, `robotics.stop` module registration.
- Their one-to-one Flyto2 capability declarations.
- Pure bounded `flyto.robotics.plan.v1` construction.
- Strict immutable parsing of a robotics capability catalog supplied by an
  external adapter.
- Transport-neutral declarations returned to the Flyto2 runtime.

## Not owned

- Raspberry Pi services or runners.
- ROS 2 / Nav2 processes.
- Robot IP addresses, localhost gateways or SSH tunnels.
- Robot credentials.
- Dispatch authority, leases or operator approval.
- Physical safe-stop enforcement.
- Mission-completion verdicts.

Those belong to the selected external adapter and the Flyto2 Space Task runtime.

## Users

Workflow authors and adapter implementers. A robot itself does not need this
package installed.
