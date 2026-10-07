# Changelog

## 1.4.0 — recovery semantics on the motion contracts (2026-10-07)

- `motion.advance`, `motion.retreat`, `motion.rotate` and `motion.navigate`
  declare recovery semantics in their contract's `recovery` block (flyto-core
  2.39.0): advance answers `obstruction` with the roles `reorient`,
  `reposition`, `travel_to` (in that order), preserves its `destination`, on
  the `same_resource`, and fills `reposition`; retreat fills `reposition`,
  rotate `reorient`, navigate `travel_to`. These equal Flyto2 Cloud's
  platform-reviewed first-party semantics exactly (definition hashes pinned in
  `tests/test_recovery_semantics.py`), so Cloud builds the way round from the
  contract instead of its legacy `RECOVERY_SUBSTITUTES` table.
- Advance's and retreat's host report (`capabilities`, `observe`, `guidance`)
  is unchanged. Rotate and navigate gain a `recovery` block holding only
  `fills`; a failed step of theirs still returns no `recovery` output.
- On a flyto-core without `RECOVERY_FIELDS` (before 2.39.0) the semantic keys
  are left out, and a block with nothing else is left out whole, with one
  warning: the registered contracts equal 1.3.0's, and Cloud keeps its legacy
  floor.

## 1.3.0 — named places (2026-10-04)

- `robotics.places` (`places.list`): read-only; returns the named places on
  the robot's map as `places` (`[{name, frame, x, y, yaw}]`) and declares an
  artifact of kind `places` (`application/json`, ≤ 256 KiB) a host can cite.
- `robotics.mark_place` (`places.mark`): saves the current map pose under a
  name; does not actuate, `controlled`, effect `places.written`, requires
  `map.localized`.
- `robotics.navigate` takes `place` (text, 1–64) as an alternative to
  `x`/`y`; exactly one target, and `yaw_radians` only with `x`/`y`. `x` and
  `y` are no longer individually required in `params_schema`.
- A navigation by place reports `resolved_arguments` (the authored arguments
  overlaid with the adapter's resolved `x`, `y`, `yaw_radians`, only when the
  adapter reports finite coordinates for that same place), the arguments its
  arrival evidence is judged against; a refused one reports `known_places`.
- Text arguments refuse every Unicode control character and line/paragraph
  separator (was: ASCII controls only).
- Needs flyto-robotics 0.3.0; an older adapter refuses `place` and the places
  capabilities without moving. An older flyto-core (< 2.36.0) registers
  `robotics.places` without its artifact declaration, as before.

## 1.2.0 — navigation arrival is proven, not reported (2026-10-04)

- `robotics.navigate` declares its arrival as evidence: `distance_to` over
  `["x", "y"]` in frame `map`, observed as the adapter's `map_pose`
  (flyto-robotics 03be416) after and once settled, against the call's own
  `x`/`y`, within 0.30 m; and `angle_to` over `["yaw"]` against an optional
  `yaw_radians`, within 0.30 rad. Both are Nav2's goal checker (burger.yaml
  `xy_goal_tolerance` / `yaw_goal_tolerance` 0.25, run unchanged on robot and
  twin) plus 0.05. A Nav2 SUCCEEDED that left the robot 0.63 m short is not an
  arrival.
- The absolute ops need flyto-core 2.38.0; they are feature-detected
  (`"distance_to" in core.capability_contract.MEASURE_OPS`) and an older core
  registers navigate without that evidence, with one warning.
  `modules.registrable_contract` is the one place that reduction is made.

## 1.1.0 — provider evidence, declared recovery, Open-RMF fleet pack (2026-10-04)

- flyto-core 2.36.0 optional contract keys, feature-detected
  (`core.capability_contract.OPTIONAL_FIELDS`) and dropped with one warning on
  an older core: `robotics.halt` declares `role: safe_stop`;
  `robotics.observe` and `robotics.map` declare the `artifacts` the adapter
  returns (photo JPEG; map JPEG or PNG); `robotics.advance` and
  `robotics.retreat` declare `recovery` (rotate / advance / retreat, observe
  `recovery_context`, planner guidance).
- `recovery.py`: Cloud's obstacle-detour sectors, moved into the pack. A failed
  or timed-out step whose capability declares recovery returns `recovery`
  (declared capabilities and guidance, the adapter's distances and the
  nearest return per sector). Sectors equal Cloud's on 300 seeded random
  sweeps.
- A step's output reduces returned artifacts to kind, media type, size and
  SHA-256; the host keeps the bytes.
- New `fleet` entry point (`fleet_pack.register_fleet`): `fleet.navigate`
  (`motion.navigate_to_waypoint`), `fleet.dock` (`motion.dock`), `fleet.load`
  (`transport.load`), `fleet.unload` (`transport.unload`), each with a
  waypoint parameter and a contract, driven through flyto-robotics'
  `open_rmf.fleet` adapter. Text parameters are trimmed and length-bounded.
- `PACK_DESCRIPTION` for both packs.

## 1.0.0 — capability contract (2026-10-04)

Breaking: Move / Turn / Stop are replaced by one step per capability, with the
adapter's own parameter names.

- Register `robotics.advance`, `.retreat`, `.rotate`, `.halt`, `.navigate`,
  `.observe` and `.map`, each with `provides_capability` and a
  `flyto.capability-contract.v1` contract (actuation, safety class, safe stop,
  cancellation, idempotency, effects, preconditions, evidence).
- Parameters and bounds equal the flyto-robotics adapter's `ARGUMENTS`
  (`distance_m`, `speed_mps`, `yaw_radians`, `x`, `y`); out-of-range values are
  refused, never clamped. Speed defaults equal the adapter's (0.12 / 0.10 m/s).
- Evidence reproduces Cloud's current motion verdicts: `along` the starting
  heading for advance/retreat (retreat `scale: -1`), signed `angle_delta` for
  rotate, heading hold, rotation drift and settle; verified with flyto-core's
  `judge` against a transcription of Cloud's check.
- The host dispatcher now receives exactly `{resource_id, capability_id,
  arguments}`; adapter outcomes map to `EXTERNAL_CAPABILITY_REFUSED`,
  `_TIMEOUT`, `_CANCELLED` or `_FAILED`, keeping the execution record.
- Dispatcher trust is checked on the dispatcher's type, as flyto-core does.
- A flyto-core without `contract=` gets the steps without contracts and one
  warning. New optional extra `core = ["flyto-core>=2.35.0"]`.

## 0.2.0 — software closure (2026-09-23)

- Make `flyto.capability-request.v1` the sole production authoring contract.
- Align Move/Turn validation with the Generic ROS 2 Adapter contract.
- Add explicit builder parameter schemas and real flyto-core registry acceptance.
- Remove misleading singular resource capability metadata from robotics authoring nodes.
- Remove retired plan/catalog authoring APIs and their executable release smoke path.
- Keep physical TurtleBot3 acceptance explicitly separate.


## Historical record

## Unreleased — external ROS 2 adapter architecture (2026-09-21)

- Change Move/Turn/Stop runtime output to `flyto.capability-request.v1` with a
  commanded resource and canonical Space motion capability.
- Separate execution-host placement from commanded equipment; the module result
  no longer returns `requires_device` for the robot.
- Remove module credential requirements: workflow authoring no longer talks to a
  robot-local Flyto2 gateway.
- Remove the production-facing `gateway.py`, then retire the final
  `legacy_gateway.py` HTTP client and executable Lima/Gazebo runtime harness
  after organization-wide search found no remaining production consumer.
- Document TurtleBot3 as standard ROS 2 equipment controlled by an external
  Generic ROS 2 Adapter.


Nothing in this project has been uploaded to PyPI. Every version below is a
local build only; the dates are when the work landed, not a release date.

## 0.1.1 — unreleased (local build, 2026-08-08)

- Added `gateway.safe_stop(session_id, reason=...)`, a client for the lower
  delivery gateway's existing safe-stop endpoint. It returns the original
  session's resulting state so Cloud can report cancellation only after the
  gateway says that session is `cancelled`, rather than confusing a separate
  stop command with withdrawal of the active work.
- Added a pure catalog-derived `plan_for_step` API for the next Pi runner. It
  requires a verified lower catalog by default, fails closed on missing or
  drifted contracts, retains safe-stop endings, and keeps legacy canvas behavior
  behind the explicitly named `preview_plan_for_step` path. Catalog-derived
  move plans preserve the lower runtime contract's `speed` argument name.

- `register_all` no longer reports every `ImportError` as a missing
  `flyto-core`. It suppresses and logs exactly two cases — `flyto-core` not
  installed, and a `flyto-core` that does not offer the API this package
  imports — and re-raises everything else, including a dependency missing
  inside `flyto-core`, a broken import in this package's own `modules`, a
  `register_module` decorator that raises and a failing `build_modules`. Those
  are this plugin failing, and only `flyto-core`'s discovery boundary can report
  which plugin failed; the old blanket `except ImportError` turned them into a
  warning naming the wrong cause while three robot steps went silently missing
  from the canvas. Which case an error is depends on where it was raised rather
  than on what it names, because a `flyto-core` breaking on its own
  `from core.modules.registry import …` names a module this package imports too.
- Registration is now explicitly repeatable rather than incidentally so: it is
  redone on every call and remembered between none of them, so a registry a host
  cleared and rediscovered fills again with the same three ids, in the same
  order, under the same capability metadata and the ownership the host assigns.
  No process-global "already registered" flag — that is precisely what would
  leave a hot-reloaded registry permanently empty with nothing raised.
- `test_registration.py` gained the regression tests for both, driven through a
  `flyto-core`-shaped `sys.modules` stand-in and a registry stand-in keyed by
  module id. The pre-existing missing-`flyto-core` test was rewritten off
  `builtins.__import__` patching: that fake raised from its own frame, which is
  not where an absent `flyto-core` raises from, so it could no longer tell the
  case it was written for apart from the ones that must now propagate.
- Each step now declares one capability to the registry through
  `register_module(provides_capability=…)`: `robotics.move` provides
  `robotics.motion.move_relative@1`, `robotics.turn` provides
  `robotics.motion.turn_relative@1`, and `robotics.stop` provides
  `robotics.safety.safe_stop@1`. One capability per step, none shared, so a
  device's declared abilities match exactly one authored step. These identifiers
  name the registry contract and are deliberately separate from the bare
  capability verbs `plan.py` emits into the executed plan.
- That mapping is proved against a real consumer. A wheel built from an isolated
  copy of the current source — `flyto_modules_robotics-0.1.1-py3-none-any.whl`,
  SHA-256 `868805c58bf2dd08b35b0bafd136527cbe0cdbe80facca7eb22b308adc3ffb0b` —
  was installed and consumed by the actual sibling `flyto-core` 2.27.0 through
  the public `flyto.modules` entry point
  `robotics -> flyto_modules_robotics:register_all`. `ModuleRegistry` stamped
  plugin owner `robotics` on all three modules and `ModuleRegistry.capabilities()`
  returned exactly the three capabilities above, each mapped to its one module.
  Registration and discovery only: no module was executed and no network, ROS,
  Gazebo, Lima or robot was contacted. The wheel was built and installed in
  isolation and uploaded nowhere; its digest differs from the earlier 0.1.1 build
  below because the source gained this metadata while the version did not change.
  The build emitted a setuptools license deprecation warning, tracked as a
  packaging follow-up in `tasks.md`.
- `execute` is now a coroutine on all three steps. flyto-core runs a module
  with `return await self.execute()`, so against a real engine 0.1.0 raised
  `object dict can't be used in 'await' expression` and no step could run at
  all. Thirty-six tests passed over it: the stand-in base class in
  `test_registration.py` calls `.execute()` directly, so the engine's own
  contract was never in the room. A test now asserts each one is a coroutine.
- The version contract no longer drifts: `flyto_modules_robotics.__version__`
  and the installed distribution metadata now agree. An isolated build of
  `flyto_modules_robotics-0.1.1-py3-none-any.whl`, installed into an isolated
  Python 3.11 venv, reports `0.1.1` from both. The agreement is guarded in the
  unit suite and again in the built-wheel CI consumer check, so a future bump
  that touches only one of the two fails before release. The wheel was built and
  installed in isolation; it was not uploaded anywhere.
- `scripts/verify-lima-gazebo.sh`, the bottom-up closed-loop verifier, has now
  been executed and passed: a module-authored `robotics.move` plan drove a
  Gazebo Burger through this package's real code and Gazebo's own world pose
  read the result. Simulation evidence only — it is not physical closure, and
  physical revalidation after the `flyto-robotics` tolerance fix is still
  pending.
- Entries below landed as part of 0.1.0.

## 0.1.0 — unreleased (local build, 2026-08-05)

Not on PyPI. Whether to publish, and under which account, is still open.

- Three workflow steps: `robotics.move`, `robotics.turn`, `robotics.stop`,
  registered into `flyto-core` through its `flyto.modules` entry point.
- Plans are built locally with bounded parameters and always end in a safe stop.
- The gateway address is configuration, never a step parameter, so identical
  robots share one authored workflow.
- A missing `flyto-core` is logged rather than raised: discovery loads every
  plugin in one loop, and raising would take down the others.

### Also in 0.1.0

- `steps.py`: one table mapping a module identifier to the plan it means,
  shared by the modules registered into `flyto-core` and by the robot's own
  job runner. `modules.py` reads it too, so the builder call is written once.
- Argument names and bounds now mirror the robot's capability contract
  (`turn_relative` takes `yaw_delta_rad`, not `radians`; angular speed
  0.1-1.0; `yaw_delta_rad` caps at ±3.0 rad, from which the degree limit is
  derived rather than written as a rounded figure).
- How far and how much are the author's to state: `robotics.move` requires a
  distance and `robotics.turn` an angle. A default would be a robot moving an
  amount nobody chose. How fast and which way keep safe defaults.
