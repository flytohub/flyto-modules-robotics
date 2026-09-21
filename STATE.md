# State

## External ROS 2 adapter convergence — 2026-09-21

Current production contract:

`workflow node -> flyto.capability-request.v1 -> external AI Space computer ->
Generic ROS 2 Adapter -> standard ROS 2 resource`.

Move/Turn/Stop no longer emit `requires_device` plus a
`flyto.robotics.plan.v1` job payload. They emit `commanded_resource` plus
canonical `motion.advance` / `motion.retreat` / `motion.rotate` /
`motion.halt` requests. The request contains no gateway URL, bearer token,
execution host, Pi runner identity or ROS implementation detail.

The production-facing `gateway.py` API has been removed. Historical Gazebo
reproduction uses explicitly named `legacy_gateway.py`, which is not exported
from the package top level and has no default address. The lower delivery catalog
and plan helpers remain legacy-only while downstream users migrate;
`127.0.0.1:8766` is not a production assumption.

Physical TurtleBot3 execution is owned by the external adapter architecture.
The Pi has been cleaned to native ROS 2 in the 2026-09-21 physical closure work
tracked in `flyto-cloud`. Historical Pi-runner statements below are evidence
of the superseded architecture, not current deployment guidance.


Date: 2026-08-28

## Where this stands today

Three things are true at once, and they must not be merged:

- **Registration and capability discovery against `flyto-core` 2.27: passed.**
  A built wheel of the current source was installed and consumed by the actual
  sibling `flyto-core` 2.27.0 through the public `flyto.modules` entry point.
  Recorded under "Capability metadata and the `flyto-core` 2.27 consumer proof"
  below. It is a *registration* result: no module was executed by it.
- **Gazebo closed-loop: passed.** The bottom-up verifier ran end to end and its
  report, cleanup and lower-layer evidence are all recorded below. That evidence
  is the 2026-08-09 run and was **not** rerun for the 2.27 proof.
- **Physical revalidation: blocked, safely.** The fresh hardware preflight
  refused motion because the area is not clear. The robot remains stopped and no
  new physical motion has been run since the `flyto-robotics` tolerance fix.

A registry pass says the steps and their capabilities arrive in `flyto-core`'s
registry. A Gazebo pass says the contract survives to a simulated chassis.
Neither is hardware evidence, neither renews the physical TurtleBot3
measurements, and neither may be presented as exhibition-ready physical closure.

## Safe-stop session cancellation — changed 2026-08-28

The client now exposes the lower gateway's existing
`POST /v1/deliveries/{session_id}/safe-stop` contract as
`gateway.safe_stop(...)`. This is materially different from starting a separate
stop plan: the lower gateway owns both the actuator stop and the transition of
the original session to `cancelled`, so an upstream caller can inspect that
state before claiming the work was withdrawn.

The package suite passed with **291 tests**, and strict Flyto Indexer
verification passed **18/18**. These tests cover the exact HTTP method, path,
reason payload, authentication path, and returned cancellation state. No
gateway, ROS process, simulator, or physical robot was contacted by this change;
the physical revalidation status above remains blocked on a safely cleared area.

## The registration boundary — changed 2026-08-11, accepted

`register_all` used to answer every `ImportError` the same way: log "could not
reach flyto-core" and return. It now suppresses exactly two cases — `flyto-core`
absent, and a `flyto-core` present without the API this package imports — and
re-raises the rest, so a dependency missing inside `flyto-core`, a broken
`modules` here, a raising decorator or a failing `build_modules` reach
`flyto-core`'s discovery boundary as the plugin failures they are. The
discriminator is where the error was raised, not what it names; see
ARCHITECTURE.md and the two 2026-08-11 entries in DECISIONS.md.

Registration is also now explicitly repeat-safe: rebuilt on every call,
remembered between none, so a cleared or hot-reloaded registry refills with the
same three ids in the same order, the same capability metadata, and whatever
plugin ownership the host is assigning at the time.

Read the evidence line here carefully, because it is narrower than the section
above it:

- **The repository gates ran and were accepted.** Job
  `job_46d0f9c1892d458eb4e2cd9c` checked the official repository at
  implementation revision
  `039d29ae50c5f6b6558ee599b7d8e4958c733b564d60c5b42d2fe75236861a12` and
  recorded **232 passed**, with strict route / Flyto Indexer verification
  accepted. The 232 figure is now an observed and accepted result, not a
  reported one; it is recorded under "Last verification" below.
- **What the gates cover is still the unit suite plus the repository gate.** The
  tests drive `register_all` against a `flyto-core`-shaped `sys.modules`
  stand-in and a registry stand-in keyed by module id. The 2.27 consumer proof
  recorded below was **not** re-run against this change, so the boundary change
  carries a repository result, not a fresh consumer, canvas, Gazebo or hardware
  result.

## Capability metadata and the `flyto-core` 2.27 consumer proof

Each step declares one capability through `register_module(provides_capability=…)`
in `modules.py`. The mapping is accepted:

| Module | `provides_capability` |
|---|---|
| `robotics.move` | `robotics.motion.move_relative@1` |
| `robotics.turn` | `robotics.motion.turn_relative@1` |
| `robotics.stop` | `robotics.safety.safe_stop@1` |

One capability per step and no two steps share one. These name the *registry
contract*, not the plan's internal step verbs — `plan.py` still emits the bare
`move_relative` and `safe_stop` into the plan the gateway executes, so renaming a
registry contract cannot silently change the bytes a robot runs.

That mapping was then proved against a real consumer, not a stand-in:

- An isolated copy of the current source built
  `flyto_modules_robotics-0.1.1-py3-none-any.whl`, SHA-256
  `868805c58bf2dd08b35b0bafd136527cbe0cdbe80facca7eb22b308adc3ffb0b`.
- That installed wheel was consumed by the **actual sibling `flyto-core`
  2.27.0**, through the public `flyto.modules` entry point
  `robotics -> flyto_modules_robotics:register_all`. No import path was
  monkey-patched and no stand-in base class was involved.
- `ModuleRegistry` stamped plugin owner `robotics` on all three modules, and
  `ModuleRegistry.capabilities()` returned exactly each canonical capability
  above mapped to its one module — no extra entry, no capability claimed by two
  modules.

What the proof did **not** do: no module was executed, and no network, ROS,
Gazebo, Lima or robot was contacted. It is registration and capability discovery
only.

Read that wheel digest carefully. It is **not** the same wheel as the 0.1.1 build
recorded under "Historical evidence" (SHA-256 `0203f2e2…`); the version string is
unchanged while the source gained the capability metadata above, so the two
digests differ by design. At the time of this historical proof, the Pi runner venv still carried the
older `0203f2e2…` wheel. That runner architecture was later removed from the
physical TurtleBot3; the `868805c5…` wheel was only built and installed in
isolation for this registration proof.

The build emitted a **setuptools license deprecation warning**. It is a packaging
follow-up, tracked in `tasks.md`; it is not a registration failure and the
registration above succeeded with it present.

## Gazebo exhibition stability — passed

`scripts/verify-lima-gazebo.sh` is a bottom-up closed-loop verifier: it retests
`flyto-robotics`' own accepted Gazebo verifier, then sends a plan built by this
package's `steps.plan_for_step()` through `gateway.start_plan()` to the runtime
that verifier just proved, and reads the outcome from Gazebo's world-pose topic
rather than from odometry.

Latest run — `mrg-20260809T101631Z-79266`:

| What | Value |
|---|---|
| Report contract | `flyto.modules-robotics.gazebo-closed-loop.v1`, `passed: true` |
| Report SHA-256 | `a47186f33eb05a1c833185806cdbc5f6b0f522fb1b8691d011ed205be123e25d` |
| Cleanup contract | `flyto.modules-robotics.gazebo-cleanup.v1` |
| Cleanup SHA-256 | `5836e3ddf13dec8a718f6ba1a74ccdd994bd0879c5722802d11644e4ec7c79d0` |
| Lower-evidence SHA-256 | `689f6185c09f30f0751948378e40508d91c33b0538fa9c8897d2ef7315baca9d` |
| Lower `flyto-robotics` report | passed, SHA-256 `fa8b0159b0e5c4fdd81b1536d245c5f7309d795efd4354f8149f7b5d49a92f6b` |

Cleanup reported `restored normal gateway runtime: true`, `lower processes
quiesced: true`, `guest scratch removed: true`.

The mission itself: a module-authored `robotics.move` plan requested 0.40 m at
0.12 m/s, its final step was `safe_stop`, and no host appeared anywhere in the
plan. Gateway session `pln-cb5b7e6f3c3e` completed without timeout. Gazebo
world-pose displacement was 0.3716104562185889 m — inside the 0.30–0.50 m
window and next to the physical 0.371–0.372 m measurements the window was
derived from. The cold-start physics gate observed 10.358 simulation seconds
with a maximum drift of 0.00003205322549027037 m, and the stopped pose held for
3.4490000000000016 simulation seconds with zero drift.

## Physical TurtleBot3 — revalidation pending safe clearance

An older, pre-fix real 0.05 m run is what exposed the lower fixed-tolerance
defect: session `pln-cba3e3c77abf` completed at around 0.022 m. The
`flyto-robotics` tolerance fix is accepted and deployed and its own Gazebo
verifier passed — but **no new physical motion has been run since**.

The fresh 20-scan hardware preflight refused motion, which is the correct
outcome:

| Sector | Measured | Required |
|---|---|---|
| Front | 0.8190000057 m | — |
| Left | 0.2039999962 m | ≥ 0.30 m |
| Rear | 0.7710000277 m | — |
| Right | 0.3129999936 m | — |
| Closest | 0.2039999962 m | ≥ 0.25 m |

No blind sectors; odometry drift 0 over 2.000918116 s. The robot remains
stopped. Physical 0.05 m and 0.10 m revalidation stays pending until the area is
safely cleared.

## Historical 2026-08 Pi-runner state — superseded

The remainder of this section is retained only as evidence of the architecture
that existed before the 2026-09-21 external-adapter decision. It is not current
deployment guidance. Current production truth is the section at the top of this
file.

At that time the package was not published, registration against `flyto-core`
2.27.0 had passed, Gazebo had closed on the 2026-08-09 run, and physical motion
revalidation was blocked.

The next bottom-up consumer layer now exists: the package can authenticate to
the accepted delivery gateway's `GET /v1/capabilities` endpoint and strictly
parse its content-addressed v1 execution catalog into immutable values. Tests
cover the GET/auth boundary, lower-shaped data, canonical hash recomputation,
determinism and adversarial rejection. Reading the catalog creates no plan or
session. The pure runner-facing `plan_for_step` now requires this trusted catalog
by default and derives named-node runtime arguments, bounds and defaults from
it. The move node preserves the lower declaration's `speed` argument name in
the emitted plan. Legacy constants remain only behind the explicitly named
`preview_plan_for_step` canvas-compatibility path; catalog failures do not fall
back to them.

- **Publishing is undecided, not merely pending.** Nothing has been uploaded to
  PyPI. The release workflow exists — a `v*` tag builds, tests the built wheel
  and would upload through Trusted Publishing — and its two jobs assert the two
  properties no unit test can: that the wheel imports and builds plans with no
  execution engine installed at all, and that a real `flyto-core` discovers it
  through the entry point and registers all three steps. Whether to publish, and
  under which account, is still an open decision.
- **Against `flyto-core` 2.27: registration and capability discovery are
  proved**, by the consumer proof recorded above against the actual sibling
  `flyto-core` 2.27.0. What remains unproved on 2.27 is the *builder canvas*:
  nobody has loaded the canvas with this installed and seen or used the three
  steps there. The `flyto-core==2.26.11` numbers under "Historical evidence"
  stay historical; do not read them as current.

- No test needs a robot or a `flyto-core`. The suite is 232 passed on the
  official repository check of the current implementation revision; see "Last
  verification" below for the job and revision.
- The version contract no longer drifts. An isolated build produced
  `flyto_modules_robotics-0.1.1-py3-none-any.whl` (SHA-256
  `0203f2e205684088c11c4d3851b446c5cc2eacbeb666460baa2e50a502d0db62`), and in an
  isolated Python 3.11 venv installed from that wheel
  `flyto_modules_robotics.__version__` and
  `importlib.metadata.version("flyto-modules-robotics")` both read `0.1.1`. The
  fix is guarded twice: in the unit suite and in the built-wheel CI consumer
  check.
- **Historical only:** the old Pi-runner environment was once upgraded to that
  wheel and `flyto-job-runner` was observed active. The 2026-09-21 physical
  cleanup removed that runtime from TurtleBot3; do not recreate it.
- `steps.py` holds the one mapping from a module identifier to the plan it
  means. Two readers share it: the modules registered into `flyto-core`, which
  read it to *declare* a motion, and the robot's own job runner, which reads it
  to *perform* one. A copy on either side would be free to drift, and the drift
  would only show as a robot moving differently from what the canvas said.
- The plan now uses the argument names and bounds the robot's own capability
  contract declares. Three did not match and every test passed anyway, because
  each asserted the name this package had chosen rather than the one the robot
  reads: `radians` is `yaw_delta_rad`; angular speed is 0.1-1.0, not 0.05-0.8;
  and `yaw_delta_rad` caps at ±3.0 rad, so the old 360° limit meant any turn
  past ~172° was refused by the gateway after the job had been claimed.
- **Historical only:** the three steps formerly returned `requires_device` plus
  a delivery plan for a Pi runner. They now emit `commanded_resource` plus a
  canonical capability request for an external adapter.
- **Historical only:** the old runner posted `POST /v1/plans`. That endpoint is
  not part of the current production robotics authority path.
- Each step declares one capability to the registry through
  `register_module(provides_capability=…)`; the accepted mapping and its 2.27
  consumer proof are above.

## Historical evidence — true when taken, not current

Nothing in this section has been re-run against today's robot, and only the
narrow registration-and-capability question has been re-answered on `flyto-core`
2.27 — by the separate consumer proof above, not by re-running anything here. It
is kept because it is what the design was proved on, not because it still stands.

- **2026-08-08, end to end on hardware.** A `robotics.turn` step authored on the
  canvas, dispatched as a Space task, was built into a plan by the robot's runner
  and carried out — `workflow.turn.left.90deg.v1`, reported succeeded with
  `arrival.pose` and `clearance.measurement`.
- **TurtleBot3 gateway runs.** Six live runs through `POST /v1/plans`, forward
  and backward, measured 0.371–0.372 m against a 0.400 m target, zero safety
  stops. This is the source of the 0.30–0.50 m Gazebo window.

### Registration against `flyto-core==2.26.11` (historical)

Installed together in a clean Python 3.12 venv, `discover_plugins(force=True)`
found this package and the three steps reached the registry with the metadata a
canvas needs:

| Module | ui_label | ui_icon | ui_color |
|---|---|---|---|
| `robotics.move` | Move Robot | MoveVertical | `#22D3EE` |
| `robotics.turn` | Turn Robot | RotateCw | `#22D3EE` |
| `robotics.stop` | Stop Robot | Square | `#F87171` |

431 modules were in that registry, three of them ours, and `ModuleRegistry.get`
returned the class. Both the count and the flyto-core version are from that run
and say nothing about 2.27; the `ui_*` metadata table above has not been
re-measured on 2.27, and the 2.27 proof above checked plugin ownership and
capabilities rather than these fields. Reproduce with:

```bash
python3.12 -m venv /tmp/plugintest
/tmp/plugintest/bin/pip install -e . -e ../flyto-core
/tmp/plugintest/bin/python -c "from core.modules.registry import ModuleRegistry; ModuleRegistry.discover_plugins(force=True); print(sorted(k for k in ModuleRegistry.get_all_metadata() if k.startswith('robotics.')))"
```

Note when reading that output: metadata canonicalises `label` to `ui_label` and
`icon` to `ui_icon`. Checking the former reports `None` and looks like missing
labels — flyto-core's own modules read the same way.

`discover_plugins` reports `module_count: 0` for every plugin including
flyto-core's own `community`. The counter is wrong; registration is not.

## Remaining risks

- **Physical motion after the tolerance fix.** Not run. The preflight refused,
  the robot is stopped, and the 0.05 m and 0.10 m revalidation waits on a safely
  cleared area. Gazebo does not stand in for it.
- **Appearing and being usable on the builder canvas.** Still open, and it is
  what the 2.27 proof deliberately does not answer: registration and capability
  discovery closed, but nobody has loaded the builder with this installed and
  seen the three steps, placed one, or run one from there.
- **Executing a module inside `flyto-core` 2.27.** The consumer proof registered
  and discovered; it executed nothing. Coroutine `execute()` on 2.27 is covered
  by the unit suite and by the built-wheel CI consumer check, not by that proof.
- **Bounds.** `plan.py` holds its own `MAX_DISTANCE_M` and `MAX_SPEED_MPS`
  constants while the robot's `CapabilityDefinition` already carries
  per-capability bounds. Two copies, only one authoritative. See ROADMAP.
- **Gazebo evidence is not fresh.** The run recorded above is 2026-08-09 and was
  not rerun for the capability or 2.27 work. It stands as of that run.
- **Packaging.** The isolated build emitted a setuptools license deprecation
  warning. It did not stop the build or the registration, and it is a packaging
  follow-up in `tasks.md` — not a registration failure.
- **Publishing.** Not on PyPI, and the account to publish under is still
  undecided. Both wheels above were built and installed in isolation, not
  uploaded.

## Last verification

The 2026-08-11 registration-boundary change now has a gate result of its own —
the last line of this group's first entry — and it supersedes the 2026-08-10
numbers above it for the suite count.

- 2026-08-11 registration boundary — **accepted.** Job
  `job_46d0f9c1892d458eb4e2cd9c`, official repository check at implementation
  revision
  `039d29ae50c5f6b6558ee599b7d8e4958c733b564d60c5b42d2fe75236861a12`:
  **232 passed**, and strict route / Flyto Indexer verification accepted. This
  is the observed result for that change; the earlier "reported 232" wording is
  retired.
- `/Users/chester/flytohub/flyto-ai/.venv/bin/python -m pytest -o pythonpath=src tests/ -q`
  — **222 passed in 0.23s**, on the tree as of 2026-08-10. Superseded by the
  232-passed check above.
- `ruff check src tests` — passed, on the tree as of 2026-08-10.
- Strict Flyto Indexer route verification — passed, on the tree as of
  2026-08-10, and accepted again in job `job_46d0f9c1892d458eb4e2cd9c` above.
- `flyto-core` 2.27.0 consumer proof — passed. Wheel
  `flyto_modules_robotics-0.1.1-py3-none-any.whl`, SHA-256
  `868805c58bf2dd08b35b0bafd136527cbe0cdbe80facca7eb22b308adc3ffb0b`; entry
  point `robotics -> flyto_modules_robotics:register_all`; plugin owner
  `robotics` on all three modules; `ModuleRegistry.capabilities()` exactly the
  three canonical capabilities, each mapped to its one module. No module
  executed; no network, ROS, Gazebo, Lima or robot contacted.
- `scripts/verify-lima-gazebo.sh` — passed on **2026-08-09**, run
  `mrg-20260809T101631Z-79266`; digests above. Not rerun since.
