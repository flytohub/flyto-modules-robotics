# A bottom-up Gazebo verifier, reconciled against the layer below it

Owner: claude
Branch: main
Date: 2026-08-09

## What changed

- `scripts/verify-lima-gazebo.sh` — new. Retests `flyto-robotics`' own accepted
  Gazebo verifier, then drives that runtime through *this* package's real code
  and reads the result from Gazebo's own world-pose topic.
- `tests/test_lima_gazebo_closed_loop_contract.py` — new. Static tests that
  protect the verifier's safety ordering and its exact lower-layer values. They
  run no robot and prove nothing about one.
- Project-memory scaffold updated: `README.md`, `PROJECT.md`, `ARCHITECTURE.md`,
  `STATE.md`, `ROADMAP.md`, `tasks.md`, `DECISIONS.md`, `CHANGELOG.md`,
  `docs/README.md`, `handoffs/_registry.md`.

## Why

Every test in this repository asserts that this package agrees with itself. A
fixture that agrees with the code it tests proves only that. The 2026-08-08
handoff is the record of what that costs: three argument names passed every
test here and were still wrong at the gateway, and `yaw_delta_rad` capping at
±3.0 rad meant any turn past about 172° was refused *after* the job had been
claimed.

So the verifier does not assert against fixtures. It runs the layer below,
believes only that layer's own fresh evidence, and then sends a plan built by
`steps.plan_for_step()` — today's, not a hand-authored copy — through
`plan.run_request()`, `gateway.start_plan()` and `gateway.await_session()`. If a
contract drifts again, it fails there.

## Reconciled against the accepted lower layer

An earlier partial draft of this script existed and every one of its
lower-layer assumptions was wrong. They are corrected, and each correction has
a test so it cannot drift back:

| The draft assumed | What is actually true |
|---|---|
| `--run-id <id>` flag | `FLYTO_GAZEBO_VERIFY_RUN_ID=<id>` in the environment; there is no flag |
| `results/lima-gazebo/<id>/` | `results/virtual-robot/<id>/` |
| `flyto.robotics.lima-gazebo-verify.v1` | `flyto.robotics.burger-gazebo-acceptance.v1` |
| `flyto.robotics.lima-gazebo-cleanup.v1` | `flyto.robotics.runtime-cleanup.v1` |
| cleanup carries `run_id` | it does not; freshness comes from the unique path plus SHA-256 |
| cleanup field `normal_gateway_restored` | `passed`, `restored_normal_gateway_runtime`, `normal_runtime_restoration_exit_code`, `zero_command_published`, `verification_status` |
| `scripts/lima-gazebo-restore.sh --safe-stop` then `--normal-gateway` | `scripts/run-lima-gazebo.sh`, no flags, once; it publishes the zero command itself before restarting the runtime |
| Lima instance `flyto-robotics` | `flyto-robot-gazebo` |
| `/etc/flyto-robotics/delivery-token`, read as a raw token | `$HOME/.local/share/flyto-robot-gazebo/runtime/gateway.env`, sourced in the guest — it holds `export` assignments |
| robot `flyto-tb3-gazebo-001` | `flyto-rover-sim-001` |

Two of those were not merely wrong but dangerous. A `--run-id` flag would have
been rejected or misread, so the report the script then went looking for would
never have existed. And `read().strip()` on the environment file would have sent
the literal text `export FLYTO_...=...` as a bearer token — a failure that
arrives *after* the run has started.

## What the verifier requires beyond the draft

- **A cold-start physics gate.** The lower verifier's cleanup restarts the
  managed runtime, so we arrive at a fresh cold start. The gate is stated in the
  simulator's clock, not the wall clock: ten seconds of world-pose simulation
  time must pass with the Burger drifting no more than 0.01 m, bounded at ninety
  wall seconds, before the start sample and before the mission. A paused world
  advances no simulation time and fails it, which is the right answer.
- **A tighter displacement window.** 0.30–0.50 m for a 0.40 m command, against
  the draft's 0.25–0.55. The physical TurtleBot3 measured 0.371–0.372 m on the
  same command, so a correct run lands near 0.37; the floor is thirty times the
  drift the physics gate tolerates, so settling can never read as driving.
- **A stopped pose that holds.** One sample after the mission cannot tell a stop
  from a slow coast. Three seconds of simulation time with no drift can.
- **A structural pose parser.** The draft matched `pose { ... }` with a
  non-greedy regex that stopped at the first line-initial `}` — the *inner*
  brace of the first nested block — so it read a truncated body and could miss
  the model it was looking for. Replaced with a brace-and-indent parser.
- **Freshness proved before the fact.** The chosen lower results directory must
  not already exist. Since the cleanup contract carries no `run_id`, that is the
  only thing that can bind its evidence to this run, together with the digests
  recorded in `lower-evidence.json`.
- **Contracts as constants.** The draft made every lower-layer name an
  environment override. A contract you can switch off from a shell is not a
  contract; only the checkout *location* stays overridable.

## Safety

One EXIT owner, installed before the first action that can leave a robot moving
or a runtime in a fault state. It calls `run-lima-gazebo.sh` exactly once on
every path — success, failure and signal — records its exact exit code,
distinguishes that from a timeout kill, preserves an existing failure, and fails
an otherwise-passing run whose restoration failed. INT and TERM exit rather than
clean up themselves, so there is one implementation and one invocation.

This package still never publishes a stop. `run-lima-gazebo.sh` publishes the
best-effort zero command itself; a second one from here would be this package
inventing a safety path, which AGENTS.md forbids.

## Verified — executed

All of the following was run, not reasoned about.

**Static gates.**

- `/Users/chester/flytohub/flyto-ai/.venv/bin/python -m pytest -o pythonpath=src tests/ -q`
  — **221 passed**.
- `ruff check src tests` — passed.
- Strict Flyto Indexer route verification — passed.

**Packaging.** An isolated build produced
`flyto_modules_robotics-0.1.1-py3-none-any.whl`, SHA-256
`0203f2e205684088c11c4d3851b446c5cc2eacbeb666460baa2e50a502d0db62`. Installed
into an isolated Python 3.11 venv, `flyto_modules_robotics.__version__` and
`importlib.metadata.version("flyto-modules-robotics")` both read `0.1.1`. The
version drift is fixed and guarded twice — in the unit suite and in the
built-wheel CI consumer check. The Pi runner venv was upgraded to that exact
wheel; the rollback tar has SHA-256
`333ea229cfbf353d0beb6726491a876f6774fcf6c5617040e4b9121b5e4b6fbb`, and
`flyto-job-runner` is active after the restart. Nothing was published to PyPI.

**The verifier itself — run `mrg-20260809T101631Z-79266`, passed.**

| What | Value |
|---|---|
| Report contract | `flyto.modules-robotics.gazebo-closed-loop.v1`, `passed: true` |
| Report SHA-256 | `a47186f33eb05a1c833185806cdbc5f6b0f522fb1b8691d011ed205be123e25d` |
| Cleanup contract | `flyto.modules-robotics.gazebo-cleanup.v1` |
| Cleanup SHA-256 | `5836e3ddf13dec8a718f6ba1a74ccdd994bd0879c5722802d11644e4ec7c79d0` |
| Lower-evidence SHA-256 | `689f6185c09f30f0751948378e40508d91c33b0538fa9c8897d2ef7315baca9d` |
| Lower `flyto-robotics` report | passed, SHA-256 `fa8b0159b0e5c4fdd81b1536d245c5f7309d795efd4354f8149f7b5d49a92f6b` |

Cleanup reported `restored normal gateway runtime: true`, `lower processes
quiesced: true`, `guest scratch removed: true` — the EXIT owner described under
**Safety** did what it was written to do.

The mission: a module-authored `robotics.move` plan requested 0.40 m at
0.12 m/s, its final step was `safe_stop`, and no host was found anywhere in the
plan. Gateway session `pln-cb5b7e6f3c3e` completed without timeout. Gazebo
world-pose displacement was 0.3716104562185889 m.

Three of the requirements argued for above were answered by measurement rather
than by assertion:

- The **cold-start physics gate** observed 10.358 simulation seconds with a
  maximum drift of 0.00003205322549027037 m — three hundred times inside its
  0.01 m tolerance, so settling could not have been read as driving.
- The **0.30–0.50 m window** did not need moving. 0.3716104562185889 m lands on
  top of the physical 0.371–0.372 m the window was derived from, which is the
  outcome the window was betting on and the one it could not assume.
- The **stopped pose held** 3.4490000000000016 simulation seconds with zero
  drift, so the mission ended in a stop rather than a slow coast.

## Physical truth is separate, and is not closed

A Gazebo pass does not renew the physical TurtleBot3 evidence and does not
replace it. The current physical position:

- An older **pre-fix** real 0.05 m run is what exposed the lower fixed-tolerance
  defect: session `pln-cba3e3c77abf` completed at around 0.022 m.
- The `flyto-robotics` tolerance fix is accepted and deployed, and its own
  Gazebo verifier passed — but **a new physical motion was not run**.
- The fresh 20-scan hardware preflight refused motion, correctly: front
  0.8190000057 m, left and closest 0.2039999962 m, rear 0.7710000277 m, right
  0.3129999936 m, against a required left ≥ 0.30 m and closest ≥ 0.25 m. No
  blind sectors; odometry drift 0 over 2.000918116 s.
- The robot remains stopped. Physical 0.05 m and 0.10 m revalidation stays
  pending until the area is safely cleared.

Do not label the Gazebo run as hardware evidence, and do not claim
exhibition-ready physical closure on it.

## Follow-ups

1. Run the physical 0.05 m and 0.10 m revalidation once the area is safely
   cleared, and record it in STATE.md as physical evidence, kept apart from the
   Gazebo block.
2. Load the builder canvas with this installed alongside a real `flyto-core` and
   confirm the three steps are visible and usable there.
3. Decide whether to publish to PyPI and under which account. The wheel above
   was built and installed in isolation, never uploaded.
4. If the lower layer renames a field or a contract, change the constant block
   at the top of the verifier and the test that pins it, in the same commit.
