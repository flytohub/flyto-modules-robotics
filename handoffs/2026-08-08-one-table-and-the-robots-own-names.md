# One table for what a step means, and the robot's own argument names

Date: 2026-08-08
Spans: `flyto-modules-robotics`, `flyto-robotics`, verified on a physical
TurtleBot3

## What this is

This package could describe a motion, and the robot could perform one, but a
step authored on the canvas never reached the robot as itself. Closing that
gap turned up three argument-level mismatches with the robot's own capability
contract — every one of them invisible to a suite that had never met a
gateway.

## The gap

`STATE.md` said it plainly: *written and tested; never installed alongside a
real flyto-core*. It had also never been sent to a real gateway. The Space
task path dispatches a template's authored steps to the device, and the
robot's job runner understood two shapes — an inline plan, and a plan file
already on the robot — so `robotics.turn` with `{degrees: 90}` was reported as
a job that device could not run.

## What was added

`steps.py`: the mapping from a module identifier to the plan it means, written
once. Two callers read it, and they could not be more different:

* the modules registered into `flyto-core`, running on a worker or a desktop,
  which read it to **declare** a motion;
* the robot's own job runner, running on a Pi with no execution engine at all,
  which reads it to **perform** one.

A copy on either side would have been free to drift, and the drift would only
have surfaced as a robot moving differently from what the canvas said.
`modules.py` reads it too, so the builder call is written once rather than
twice per step (validate and execute).

The package is pure Python with no dependencies, so the robot puts it on
`PYTHONPATH` rather than installing it — that machine has no pip, and its
deployment is an rsync of trees.

## The three mismatches, and why tests did not catch them

| this package sent | the robot declares |
|---|---|
| `radians` | `yaw_delta_rad` |
| angular speed 0.05 – 0.8 | 0.1 – 1.0 |
| turn up to 360° | `yaw_delta_rad` capped at ±3.0 rad ≈ 172° |

The gateway's answer to the first was exact and useful — *"turn_relative.
arguments contains unsupported fields: radians"* — but it arrived after the
job had been claimed, a long way from the author who typed the step.

Every test passed against all three, because each asserted the name **this
package had chosen** rather than the one the robot reads. A fixture that
agrees with the code it tests proves only that the code is self-consistent.
The bounds now cite `flyto-robotics/capabilities.py` in a comment, the degree
limit is derived from the radian one rather than written as a rounded figure
free to drift from it, and a test pins the argument names as the robot's.

## One default removed on purpose

`robotics.move` required no distance and `robotics.turn` no angle: they
defaulted to 0.4 m and 90°. A default speed is a reasonable assumption about
*how* to move; a default distance is a robot moving an amount nobody chose.
How far and how much are now the author's to state; how fast and which way
keep their defaults.

## Verified

54 tests, none needing a robot or `flyto-core`. Then on hardware: a
`robotics.turn` step authored on the canvas, dispatched as a Space task, built
into a plan by the robot's own runner and carried out —
`workflow.turn.left.90deg.v1`, reported succeeded with `arrival.pose` and
`clearance.measurement`.

One trap worth knowing: the runner imports this package lazily and caches it,
so an rsync of a corrected `plan.py` does nothing until the runner is
restarted. A stale in-memory copy produced the same 400 twice after the fix
was already on disk.
