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

Evidence (revised after flyto-core PR #122 added `along` and `expect.scale`),
chosen so verdicts equal Cloud's current `motion_verification.judge`; every item
lists phases `before`, `after`, `settled`:
- advance: `along` (x, y, heading_field yaw) expect `distance_m` scale 1,
  abs 0.03 / rel 0.3, settle 0.02; `heading.hold` abs_angle_delta yaw, value 0,
  abs 0.15.
- retreat: same with `scale: -1`.
- rotate: signed `angle_delta` yaw expect `yaw_radians`, abs 0.1 / rel 0.2;
  `position.drift` distance (x, y) value 0, abs 0.05, settle 0.02.
- navigate declares no evidence (v1 ops compare phases; arrival at an absolute
  coordinate is not expressible). halt/observe/map: none.
- Contracts carry `schema` and are already in Core's normalized form, so the
  registered metadata equals the spec row.
- Deviations from the original spec table: rotation uses signed `angle_delta`
  (not `abs_angle_delta`); advance/retreat use `along` (not `distance`) and add
  `heading.hold`. All three were then adopted in Core's reference section.
- `concurrent_safe=False` on all seven, including read-only (one adapter
  session per job).

## Verified

- ruff 0.15.15 `check src tests`: All checks passed.
- Python 3.11 venv with the flyto-core worktree `claude/capability-contract`
  at 0af4da8 (2.35.0) installed editable: `PYTHONPATH=src pytest tests -q
  -o addopts=""` → 152 passed, 0 skipped. This includes Core's own
  `validate_contract` on all 7 contracts (and equality with its normalized
  form), Core's `judge` on the Cloud cases (advance 0.10 asked, settled
  (0.119, 0, yaw 0.02) usable; retreat 0.2 asked, measured −0.19 usable; settle
  drift 0.03 unusable; rotate drift 0.06 unusable; plus wrong-direction,
  sideways-slide, heading and ±π cases), a 2,000-case seeded random comparison
  per motion of Core's `judge` against a transcription of Cloud's judge (all
  verdicts equal, both outcomes present), and the real registry run with
  `contract=` accepted (metadata contract equals the spec row).
- Python 3.11 venv with released flyto-core 2.33.0: 125 passed, 27 skipped
  (the Core-validator/judge tests); the real registry run exercised
  register-without-contract.
- Python 3.12 without flyto-core: 124 passed, 28 skipped.
- `flyto-index verify . --strict`: PASS, 20 pass / 0 warn / 0 fail.
- Pre-change: `flyto-index outline/context/impact` on this worktree; MCP
  `task(plan)` and both gates passed.

## Not verified

- MCP `task(action='validate')`: the MCP server is pinned to flyto-indexer's
  root, so it ran that repo's ruff and could not import this package; it
  reported fail. The equivalent ruff + pytest above were run directly.
- Against a released flyto-core 2.35.0 from PyPI (only the PR #122 worktree).
- Core's capability manifest `contracts` key for these modules.
- Cloud consuming the contracts; no robot, simulator or ROS graph contacted.
- The Cloud oracle in `tests/test_capabilities.py` is a transcription; if
  Cloud's `motion_verification.py` changes, it must be updated by hand.

## Follow-ups

- After flyto-core 2.35.0 is released: CI's `pip install flyto-core` picks it
  up and the Core-validator/judge tests run there too.
- Section 3 (flyto-cloud): re-pin this package for Desktop and port the
  evidence arithmetic (`contract_verification.py`) with identical verdicts.
- Publishing to PyPI remains a separate decision.
