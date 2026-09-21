# Changelog

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
