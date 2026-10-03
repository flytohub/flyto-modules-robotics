# One module per capability, each with a declared capability contract

Owner: claude
Branch: claude/capability-contract
Date: 2026-10-04

## What changed

Section 2 of the shared Capability Contract v1 spec (Core `contract=` keyword,
built in parallel on flyto-core branch `claude/capability-contract`).

- `src/flyto_modules_robotics/capabilities.py` (new): one row per capability —
  module id, capability id, `params_schema` (bounds as `min`/`max`/`unit`),
  `flyto.capability-contract.v1` contract, timeout, retry.
- `modules.py`: seven explicit `@register_module(..., provides_capability=...,
  contract=...)` steps: `robotics.advance`, `.retreat`, `.rotate`, `.halt`,
  `.navigate`, `.observe`, `.map`. Move / Turn / Stop removed. The dispatcher
  receives exactly `{resource_id, capability_id, arguments}`; outcomes map to
  `EXTERNAL_CAPABILITY_{REFUSED,TIMEOUT,CANCELLED,FAILED}` with the execution
  record kept. Dispatcher trust is checked on its type. `supports_contract()`
  inspects `register_module`'s signature; without `contract=` the steps
  register without contracts and one warning is logged per registration pass.
- `capability_request.py`: validation generated from `params_schema`; unknown,
  missing, non-finite, bool and out-of-range values are refused, never clamped;
  adapter speed defaults (0.12 / 0.10) are made explicit in the request.
- `pyproject.toml`: 1.0.0; optional extra `core = ["flyto-core>=2.35.0"]`;
  `dependencies` stays empty.
- Tests: `tests/contract_rules.py` (vendored v1 validator + judge arithmetic),
  `tests/test_capabilities.py` (new), rewritten request/registration/steps tests.
- Docs: README (judge-facing), ARCHITECTURE, AGENTS, PROJECT, STATE, DECISIONS,
  ROADMAP, tasks, CHANGELOG, docs/src/tests READMEs, `workflows/add-a-capability.md`
  (was still describing `plan.py`).

## Why

The declaration is the whole integration: Cloud can read actuation, safety
class, safe stop, cancellation, bounds and evidence tolerances as data instead
of a robot-specific table.

Deviations from the spec table, deliberate:
- Rotation evidence uses signed `angle_delta`, not `abs_angle_delta`, because
  Cloud's current verdict is signed (wrong-direction turn fails); abs would
  change verdicts. `abs_angle_delta` is used for advance/retreat heading hold.
- Advance/retreat carry a second evidence item `heading.hold` (abs_angle_delta
  yaw, expect 0, abs 0.15) so Cloud's heading constant is declared too.
- Rotation's 0.02 m settle sits on the `position.drift` evidence (a distance),
  not on the rotation evidence (an angle), matching Cloud.
- Navigate declares no evidence: v1 measure ops compare phases; arrival at an
  absolute coordinate is not expressible.
- Linear displacement is euclidean `distance(x,y)` per spec; Cloud today
  projects onto the starting heading. Equal for straight motion; Cloud's
  `contract_verification.py` port must decide whether that difference matters.
- `concurrent_safe=False` on all seven, including read-only (one adapter
  session per job).

## Verified

Python 3.11 venv with released flyto-core 2.33.0 (no `contract=`):
- `ruff check src tests` (ruff 0.15.15): All checks passed.
- `PYTHONPATH=src python -m pytest tests -q -o addopts=""`: 114 passed,
  7 skipped (the 7 skips are `core.capability_contract` not installed). This
  includes the real flyto-core registry subprocess test, which exercised the
  register-without-contract path and `ModuleRegistry.capabilities()` mapping
  each of the 7 capabilities to exactly one step.
Python 3.12 venv without flyto-core: 113 passed, 8 skipped.
- `flyto-index verify . --strict`: PASS, 20 pass / 0 warn / 0 fail.
- Pre-change: `flyto-index outline/context/impact` on this worktree; MCP
  `task(plan)` and both gates passed.

## Not verified

- Registration against a flyto-core that accepts `contract=` (2.35.0 not yet
  available; its `core.capability_contract` did not exist when this was built).
  The 7 parametrized core-validator tests will run once it is installed.
- MCP `task(action='validate')`: the MCP server is pinned to flyto-indexer's
  root, so it ran that repo's ruff and could not import this package; it
  reported fail. The equivalent ruff + pytest above were run directly.
- Cloud consuming the contracts; no robot, simulator or ROS graph contacted.

## Follow-ups

- After flyto-core 2.35.0: install it, rerun the suite (expect 0 skips for the
  core validator), and confirm `get_all_metadata()["robotics.advance"]["contract"]`.
- Section 3 (flyto-cloud): re-pin this package for Desktop, port the evidence
  arithmetic, decide on the euclidean vs along-heading point above.
- Publishing to PyPI remains a separate decision.
