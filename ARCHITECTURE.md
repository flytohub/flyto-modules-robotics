# Architecture

Three layers, only the thinnest of which needs `flyto-core`.

```
worker or desktop                        robot
------------------------------------     ---------------------------------
flyto-core registry                      flyto_job_runner
    |  register_all()                        |  claims the job
modules.py   <- declares, never drives       |
    |                                        v
plan.py      -----> job payload -----> flyto-robotics gateway
                     (device queue)        validates, executes,
                                           owns the final stop
                                               |
                                           ROS 2 / robot
```

The split across the two columns is the point. `flyto-core` runs on the worker
and the desktop; the robot has neither. A step that drove hardware from the
left column would be reaching for a gateway on the wrong machine — the loopback
address meaning "this robot" on a Pi means "this container" on a worker.

So `modules.py` declares: it builds a plan, names the device, and returns it as
the payload the robot's runner reads from its job. `gateway.py` is the client
that runner uses; nothing in `modules.py` touches it, and a test asserts that by
inspecting imports and calls rather than grepping for the word.

`gateway.capability_catalog()` is the read-only path in the opposite direction.
It performs authenticated `GET /v1/capabilities` and hands the response to
`catalog.py`, which accepts only the exact content-addressed
`flyto.robotics.capability-catalog.v1` projection. The result is recursively
immutable. Discovery neither builds nor posts a plan, and catalog failures have
one content-free error so credentials and untrusted response bodies cannot cross
the boundary. `steps.plan_for_step` is the execution-facing pure API: it requires
that trusted value by default and derives runtime names, bounds and defaults from
it. `preview_plan_for_step` alone retains legacy constants for offline canvas
compatibility; a catalog failure never crosses into that path implicitly.

## Two vocabularies, deliberately not one

A step names its capability twice, in two different vocabularies, and they must
not be collapsed.

| Where | `robotics.move` | `robotics.turn` | `robotics.stop` |
|---|---|---|---|
| Registry contract, `modules.py` | `robotics.motion.move_relative@1` | `robotics.motion.turn_relative@1` | `robotics.safety.safe_stop@1` |
| Plan step verb, `plan.py` | `move_relative` | `turn_relative` | `safe_stop` |

The first is what `flyto-core`'s registry matches a device's declared abilities
against, versioned so a device on an older contract is a mismatch the builder can
show rather than a robot that moves unexpectedly. The second is the byte the
gateway reads and executes. Keeping them separate means renaming a registry
contract cannot silently change what a robot does. One capability per step, and
no two steps share one, or two different motions would be indistinguishable at
match time.

## Why the split

`flyto-core` is imported inside `register_all`, never at module scope. So `plan`
and `gateway` import — and are tested — on a machine with no `flyto-core`, which
is most machines.

## What `register_all` is allowed to swallow

That lazy import is also the plugin's error boundary, and it has to separate two
failures that arrive wearing the same exception type.

| What happened | What `register_all` does |
|---|---|
| No `flyto-core` here | warn, return — the ordinary case on most machines |
| `flyto-core` here, without the API this package imports | warn, return |
| `flyto-core` here and broken on its own import | re-raise |
| This package's `modules`, the decorator or `build_modules` failing | re-raise |

The first two must not raise: `flyto-core` loads every plugin in one loop, so
raising would take module discovery down for every other plugin as well. The
last two must raise, because they are *this plugin* failing and only
`flyto-core`'s discovery boundary can report which plugin failed. Swallowed,
they became a warning saying `flyto-core` was missing on a machine that had it,
while three robot steps went quietly absent from the canvas.

Which row an `ImportError` falls into is decided by where it was raised, not by
what it is called. A `flyto-core` failing on its own
`from core.modules.registry import …` names a module this package also imports,
so a name test would put row three in row two. The traceback is walked instead:
anything in it that is neither this file nor the import machinery means the
import reached code behind the boundary and failed there.

Registration itself is repeated on every call and remembered between none of
them, so a registry that was cleared and rediscovered fills again. See
DECISIONS.md for why a process-global flag is the wrong shape.

`plan.py` is pure: no network, no environment, no clock. The exact bytes a step
will send are assertable in a test with no robot present.

## Why an HTTP hop rather than a library call

Importing `flyto-robotics` and calling its runner in-process would be simpler and
is wrong. `rclpy`'s init and shutdown are process-global, so a long-running
workflow executor cannot host them safely; and a caller that died mid-mission
would leave nothing to stop the robot. The gateway is a service with signal
handling that sends the final zero-velocity stop. The hop is isolation, not
overhead.

## Where the address comes from

Configuration, not a step parameter. The job was already dispatched to a device,
so the module is running on the robot it drives and the gateway is on loopback.
That is what lets five identical robots share one authored workflow.

| Variable | Default | Meaning |
|---|---|---|
| `FLYTO_ROBOTICS_GATEWAY_URL` | `http://127.0.0.1:8766` | the local robot gateway |
| `FLYTO_ROBOTICS_DELIVERY_TOKEN` | — | bearer token, required |
| `FLYTO_ROBOTICS_ROBOT_ID` | — | must match the gateway's job |
