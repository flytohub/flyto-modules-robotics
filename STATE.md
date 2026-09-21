# State

Date: 2026-09-21

## Current architecture

`flyto-modules-robotics` is an optional **authoring/capability plugin**. It does
not run on a robot and does not own robot transport.

The active path is:

```text
Flyto2 workflow / Space Task
  → capability + approval + permission + resource binding
  → bounded robotics plan declaration
  → external robotics adapter
  → simulator or physical runtime
  → telemetry / evidence / outcome
  → Flyto2 verification / recovery
```

The legacy robot-local execution architecture is retired from the active source:
there is no `gateway.py`, Pi job runner, localhost:8766 default, delivery token,
or repository-owned Gazebo lower-runtime verifier.

## Preserved software contracts

- Three named authoring modules: Move, Turn, Stop.
- One registry capability per module.
- Host-free `flyto.robotics.plan.v1` documents.
- Safe-stop termination on moving plans.
- Strict immutable capability-catalog parsing.
- `trusted_plan_for_step` fail-closed planning from adapter-supplied catalog
  data.
- Repeat-safe `flyto-core` plugin registration.

## Evidence status

Historical Gazebo and earlier gateway receipts remain under `results/` and
`handoffs/` for provenance. They are historical evidence only and do not
describe the current transport architecture.

No claim is made here about current TurtleBot3 hardware readiness or physical
motion. Hardware acceptance is intentionally outside this software cleanup.

## Current release gate

The cleanup is complete only when its branch CI is green and the change is
merged to `main`. After merge, any simulator acceptance must use the same
external adapter contract as a physical robot; no direct control side channel
may be reintroduced.
