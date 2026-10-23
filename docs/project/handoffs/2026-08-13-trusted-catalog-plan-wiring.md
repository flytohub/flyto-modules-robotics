# Trusted catalog plan wiring

Status: Active
Owner: flyto_coding
Branch: main

Runner-facing `plan_for_step` now requires a validated lower capability catalog
by default. It derives runtime names, bounds, defaults and required safe-stop
support from that immutable catalog and fails closed when the catalog is absent
or incompatible. The legacy constant-backed behavior remains available only
through the explicitly named `preview_plan_for_step` compatibility path.

The move schema and emitted plan use the lower capability's actual argument
name, `speed`. The sibling `flyto-robotics` declarations were inspected
read-only: `robotics.motion.move_relative@1` declares `distance_m` and `speed`,
and its mission consumer reads `speed`. This wiring does not introduce the
unsupported `speed_mps` spelling.

Every moving catalog-derived plan still ends in `safe_stop`. No host is placed
in a plan, and this package gains no ROS, serial, velocity-command or other
hardware-driving authority. `robotics.command` and Pi-runner integration remain
outside this slice.

## Inherited implementation provenance

This handoff closes the plan-wiring portion inherited from governed route job
`job_16e69924d0794046bc5bd491`. That inherited tree was unaccepted work, not an
accepted baseline. Historical verification receipts in the catalog handoff and
project memory remain scoped to their recorded job and implementation revision;
they are not evidence for this reconciled tree.

## Not verified in this implementation round

The host owns source-controlled checks, exact-revision evidence and the final
independent audit. This implementation worker did not run Gazebo or hardware and
does not record a new passing receipt here. No deployment, publication or
credential access occurred.
