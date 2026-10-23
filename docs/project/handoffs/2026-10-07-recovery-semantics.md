# Recovery semantics on the motion contracts (1.4.0)

Owner: claude
Branch: claude/recovery-declaration
Date: 2026-10-07

## What changed

- `capabilities.py`: the `recovery` blocks of `motion.advance`, `motion.retreat`,
  `motion.rotate` and `motion.navigate` declare recovery semantics.
  - advance: `on [obstruction]`, `alternatives [reorient, reposition, travel_to]`,
    `preserves [destination]`, `resource_scope same_resource`, `fills [reposition]`.
  - retreat: `fills [reposition]`. rotate: `fills [reorient]`.
    navigate: `fills [travel_to]`.
  - Advance's and retreat's host report (`capabilities` / `observe` /
    `guidance`) is unchanged. These equal Flyto2 Cloud's
    `recovery_semantics.FIRST_PARTY_REVIEWED` (Cloud branch
    `claude/recovery-semantics`, 711b7bba3).
- `modules.py`: `core_recovery_fields()` feature-detects
  `core.capability_contract.RECOVERY_FIELDS` (flyto-core 2.39.0).
  `registrable_contract(..., recovery_fields)` drops the semantic keys there,
  and drops the whole block when nothing a pre-2.39 core requires
  (`capabilities`) is left. It warns once. `build_modules` and
  `build_fleet_modules` take `recovery_fields=`.
- `recovery.py`: a block without `capabilities` produces no step `recovery`.
- `tests/test_recovery_semantics.py`:
  - Pins Cloud's definition hashes.
  - Checks old-core reduction, the warning, real-core admission (2.39) and
    real-core refusal of the unreduced block (2.36-2.38).
- `tests/contract_rules.py` vendors the 2.39 recovery rules. The tests that
  validate against an installed core use what that core registers.
- Version 1.4.0.

## Compatibility

The pack feature-detects the core instead of raising its floor (DECISIONS
2026-10-07).
- On core 2.39.0 or later, the contracts carry the semantics.
- On core 2.36-2.38, they equal 1.3.0's contracts. Cloud then sees no
  declaration and uses its legacy floor, so behaviour is unchanged.
- On core before 2.36, `recovery` is dropped with the other optional keys,
  as before.

## Verified

- Pack suite against four interpreters (Python 3.11 venvs, in the order no
  core / PyPI 2.33.0 / 2.38.0 at `50c4876` / the 2.39.0 branch):
  241 passed / 69 skipped, 242 / 68, 293 / 17 and 306 / 4. The four skips
  on 2.39 are the refusal tests that only apply to 2.36-2.38 cores. This
  includes the real-registry subprocess test on each core.
- Cloud's own `recovery_semantics.reviewed`, run on these contracts as a
  2.39 core normalizes them, returns `reviewed` for all four. The hashes
  equal `FIRST_PARTY_REVIEWED`.
- Cloud's `step_recovery.recovery_for(motion.advance)` gives
  `(motion.rotate, motion.advance, motion.retreat, motion.navigate)` with
  `RECOVERY_SUBSTITUTES` made to raise on access. With 2.38-registered
  contracts all four are `undeclared` and the legacy floor answers.
- `ruff check src tests` passes (ruff 0.15.15). `flyto-index verify . --strict`: 20 pass.

## Not verified

- A live adapter, the twin and a robot.
- Cloud's full suite with these pins (Cloud not edited).
