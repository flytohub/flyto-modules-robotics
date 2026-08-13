# flyto-modules-robotics

Optional robot-control modules for Flyto2 workflows. Install this only on
installations that drive a robot.

Without it, Flyto2 is pure software automation. With it, the workflow builder
gains three steps — move, turn and stop — so a command like "advance forty
centimetres" is authored on the canvas like any other workflow.

## Installation

```bash
pip install flyto-modules-robotics
```

Not yet on PyPI, so that command does not work today — install from a locally
built wheel instead (see Releasing for what publishing would take).

The package installs on a device that has no execution engine at all: a
Raspberry Pi can install it for the plan builders alone, with no `flyto-core`
present. `plan` and `gateway` import without it, and the CI job that tests the
built wheel asserts exactly that property before anything is published.

## Why this is a separate package

`flyto-core` is the software execution engine and does not know what a robot is.
This package is discovered through `flyto-core`'s existing `flyto.modules`
entry point, so hardware arrives as an install decision rather than as a
dependency everybody carries. `flyto-core` is imported inside `register_all`,
never at module scope, and a missing `flyto-core` is logged rather than raised
so that plugin discovery does not take down the other plugins in the loop.

## Usage

Once installed alongside `flyto-core`, discovery registers three step IDs:

| Step ID | What it authors | Capability it provides |
|---|---|---|
| `robotics.move` | a bounded linear translation | `robotics.motion.move_relative@1` |
| `robotics.turn` | a bounded yaw change, in degrees at the step boundary | `robotics.motion.turn_relative@1` |
| `robotics.stop` | an immediate safe stop | `robotics.safety.safe_stop@1` |

Each step declares its capability through `register_module(provides_capability=…)`,
one per step and none shared, so a device's declared abilities match exactly one
authored step. Those identifiers name the *registry contract*; they are not the
bare capability verbs the built plan carries to the gateway, and the two are kept
separate so renaming a contract cannot change the bytes a robot runs.

An author places one of these on the canvas like any other step. A step
**declares** motion; it does not perform it, and it does not post anything.
`flyto-core` runs on the worker and the desktop, not on the robot, so a step
executing there returns a declaration:

```json
{"dispatched": false, "requires_device": "<resource id>", "plan_id": "...", "goal": "...", "request": {...}}
```

The robot's own job runner — a Raspberry Pi running `flyto-job-runner`, with
this package installed — is what reads that payload and posts the plan to the
gateway on its own loopback. Driving stays on the robot.

An authored step normally need not hard-code a device: the declaration carries
`requires_device` and the plan's `robot_id` from the dispatch context, unless
`params.robot_id` explicitly selects one. No plan carries a host. That is what
lets five identical robots share one authored workflow instead of five copies
of it.

## API Reference

The surface a caller uses is small and is stable across the three steps.

- `flyto_modules_robotics.steps.plan_for_step(step_id, arguments, robot_id=...)`
  — builds a `flyto.robotics.plan.v1` for one authored step and returns it as a
  plain dictionary. Every plan that moves ends in a `safe_stop` capability, so
  an author never meets the gateway's refusal as an error.
- `flyto_modules_robotics.plan` — plan construction and the argument bounds.
  Arguments are normalised here: a `robotics.turn` of 90 degrees becomes a
  positive `yaw_delta_rad` in the built plan.
- `flyto_modules_robotics.gateway` — posting a plan and awaiting the session.
  Used on the robot, by the job runner and by the Gazebo verifier. The Core-side
  steps do not call it.
- `flyto_modules_robotics.register_all` — the `flyto.modules` entry point.

`plan_for_step` and the bounds in `plan.py` have callers outside this package.

## Architecture

There are two sides, and they are not the same process:

- **On the worker or desktop**, inside `flyto-core`, a step builds a plan and
  returns it as a declaration with `dispatched: false` and `requires_device`.
  It posts nothing. Loopback there means "this container", not "this robot",
  so posting from here would reach the wrong machine or, worse, something else
  listening.
- **On the robot**, the job runner reads that declaration and posts the plan to
  the gateway on its own loopback, using this package's `gateway` module.

Either way this package never drives hardware: no serial port, no ROS topic, no
velocity command, no `rclpy`. The boundary is deliberate and it is a safety
property rather than a layering preference.

The gateway — not this package — owns safety. It validates the plan against a
frozen capability registry, refuses one that moves without ending in a safe
stop, runs one mission at a time, and still sends the final zero-velocity stop
if the caller dies mid-mission. Running out of process is the whole point: a
crashed authoring process cannot leave a robot moving.

## Configuration

The gateway address is configuration, never a step parameter. It is resolved
from the environment on the device:

| Variable | Default | Meaning |
|---|---|---|
| `FLYTO_ROBOTICS_GATEWAY_URL` | `http://127.0.0.1:8766` | the local robot gateway |
| `FLYTO_ROBOTICS_DELIVERY_TOKEN` | — | bearer token, required |
| `FLYTO_ROBOTICS_ROBOT_ID` | — | must match the gateway's job |

A test asserts that no built plan contains a host. Any change to how the address
is resolved needs a test that would fail without it.

## Testing

The unit suite is pure: no test needs a robot, a simulator or `flyto-core`.

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
```

Last verified run: **222 passed in 0.23s**, via
`/Users/chester/flytohub/flyto-ai/.venv/bin/python -m pytest -o pythonpath=src tests/ -q`.
`ruff check src tests` passed alongside it.

Any change to the bounds, to the plan shape, or to how the address is resolved
needs a test that would fail without it.

A unit suite can only show that this package is self-consistent, so a separate
bottom-up closed-loop verifier drives Gazebo through this repository's real
code — `plan_for_step`, `run_request`, `gateway.start_plan` — rather than
against hand-authored fixtures:

```bash
bash scripts/verify-lima-gazebo.sh
```

It requires a running Lima guest with the robot runtime available. It exits
non-zero when any lower-layer evidence or cleanup contract fails, so only a
zero exit is a passing result. Each run writes run-scoped evidence artifacts,
so separate attempts are not confused with one another.

Latest verified run: **`mrg-20260809T101631Z-79266`, passed on 2026-08-09** and
not rerun since. Report contract
`flyto.modules-robotics.gazebo-closed-loop.v1`, SHA-256
`a47186f33eb05a1c833185806cdbc5f6b0f522fb1b8691d011ed205be123e25d`; cleanup
contract `flyto.modules-robotics.gazebo-cleanup.v1`, SHA-256
`5836e3ddf13dec8a718f6ba1a74ccdd994bd0879c5722802d11644e4ec7c79d0`. A
module-authored `robotics.move` plan requested 0.40 m at 0.12 m/s and Gazebo's
world pose measured 0.3716104562185889 m. Read that run's own evidence
artifacts rather than this summary; `STATE.md` carries the full digest set.

This is simulation evidence and nothing more. It is not hardware evidence, and
physical revalidation after the `flyto-robotics` tolerance fix is still pending
— see `STATE.md`.

Separately, a built wheel of the current source has been installed and consumed
by the actual sibling `flyto-core` 2.27.0 through the public `flyto.modules`
entry point. `ModuleRegistry` stamped plugin owner `robotics` on all three
modules and `ModuleRegistry.capabilities()` returned exactly the three
capabilities in the table above, each mapped to its one module. That proof
registers and discovers; it executes no module and contacts no network, ROS,
Gazebo, Lima or robot. Seeing and using the steps on the builder canvas is still
unproved. `STATE.md` carries the wheel digest and the full result.

## Development

Read `PROJECT.md`, `ARCHITECTURE.md`, `STATE.md` and `DECISIONS.md` before
changing anything, and read `AGENTS.md` for the constraints this package exists
to hold. Explore with the `flyto-indexer` tools before editing — `search` for
the symbol, `impact` for its blast radius — then verify bottom-up: the tests
first, then the repository gate.

```bash
ruff check src tests
flyto-index verify . --strict
```

The strict verify is the post-change gate and CI runs the same command. It
checks index integrity, secrets, documentation coverage, agent-instruction
hygiene and that the generated index stays untracked.

## Releasing

Published the way `flyto-core` is: push a `v*` tag and the workflow lints,
verifies, builds, tests the built wheel, and uploads through PyPI Trusted
Publishing. No token lives in this repository.

```bash
git tag v0.1.0 && git push origin v0.1.0
```

The first release needs a **pending publisher** on PyPI, because Trusted
Publishing has nothing to trust until then. The project is not created by
hand: a pending publisher is what creates it, on the first successful upload.

The form lives under the **account** sidebar rather than a project's, since
the project does not exist yet — <https://pypi.org/manage/account/publishing/>,
"Add a new pending publisher":

| Field | Value |
|---|---|
| PyPI project name | `flyto-modules-robotics` |
| Owner | `flytohub` |
| Repository name | `flyto-modules-robotics` |
| Workflow name | `publish-pypi.yml` |
| Environment name | `pypi` |

`workflow_dispatch` publishes to TestPyPI instead, which needs the same entry
on test.pypi.org.

A pending publisher does not reserve the name — it only becomes a project on
the first upload that uses it.

## License

Apache-2.0. See `LICENSE`.
