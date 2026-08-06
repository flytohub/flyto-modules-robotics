# Decisions

## 2026-08-05 — Hardware arrives as an optional package, not as a flyto-core module

Decision: robot steps live in this separate, optionally installed package,
discovered through `flyto-core`'s existing `flyto.modules` entry point.

Reason: two constraints together force it. Hardware must not enter `flyto-core`,
which is the software execution engine; and commands must be authorable in the
builder, whose available steps come from `flyto-core`'s module registry. An
optional plugin is the only shape that satisfies both. `flyto-core` documents this
entry point for exactly this purpose and uses it for its own `community` modules.

## 2026-08-05 — A step posts a plan over loopback rather than calling a library

Decision: a step builds a plan and posts it to the robot's own gateway; it never
imports `flyto-robotics` or touches ROS.

Reason: `rclpy`'s init and shutdown are process-global, so a long-running
workflow executor cannot host them safely. More importantly, a caller that died
mid-mission would leave nothing to stop the robot, while the gateway is a service
with signal handling that sends the final zero-velocity stop. Running out of
process is the point of the hop.

## 2026-08-05 — The gateway address is configuration, not a parameter

Decision: `FLYTO_ROBOTICS_GATEWAY_URL`, defaulting to loopback. No step takes a
host.

Reason: the job was already dispatched to a device, so the step runs on the robot
it drives. A host in a workflow would bind it to one machine — the same
duplication the capability model exists to remove, wearing a URL instead of a
device id. A test asserts no plan ever contains one.

## 2026-08-06 — A step declares motion; the robot's runner performs it

Decision: `modules.py` never posts to a gateway. It builds a plan, names the
device that must carry it out, and returns that as the job payload.

Reason: these modules register into `flyto-core`, and `flyto-core` runs on the
worker and the desktop — not on the robot. The first version posted to
`127.0.0.1:8766`, which is correct only if the code runs on the Pi. On a worker
that address is the container's own loopback, so the request would either fail
or find something else listening. Thirty-six tests passed against that design
because every one of them assumed the module ran on the robot.

Reversal of the transport half of the 2026-08-05 entry above. The plan format,
the bounds and the address-is-configuration rule are unchanged; only who sends
it moved.
