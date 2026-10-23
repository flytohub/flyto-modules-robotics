# Named places: robotics.places, robotics.mark_place, navigate by place

Owner: claude
Branch: claude/robot-places
Date: 2026-10-04

## What changed

- `capabilities.py`: `robotics.places` -> `places.list` (read-only, no
  params, artifact `places` / `application/json` / 256 KiB);
  `robotics.mark_place` -> `places.mark` (`place` text 1..64 required;
  `actuates: false`, `controlled`, effect `places.written`, requires
  `map.localized`, no evidence). `robotics.navigate` gains `place` (text
  1..64) and `x`/`y` become not individually required; the arrival evidence
  is unchanged. Constants `MAX_PLACE_NAME_LENGTH`, `RESOLVED_ARGUMENTS`, ...
- `capability_request.py`: `navigate_target` — exactly one target (place, or
  x and y; yaw_radians only with x/y), the adapter's own rule. Text refuses
  every Unicode Cc/Zl/Zp character (was ASCII controls only).
- `modules.py`: nine robotics steps. Step output adds `places` (list),
  `place` (mark), `known_places` (refused navigate) and, for a navigation by
  place, `resolved_arguments` = authored arguments overlaid with the adapter's
  `evidence.resolved_arguments`, only when the adapter's `navigation_target`
  names the same place (case-insensitive, NFC) and x/y are finite; authored
  keys are never replaced. `modules.resolved_arguments()` is public.
- `tests/contract_rules.py`: a missing/non-finite target argument is an
  unusable verdict, as in flyto-core 2.38.0 (it raised KeyError).
- `tests/test_places.py` (new, 44 cases); table copies in
  `test_capabilities.py` follow flyto-robotics 0.3.0 `ARGUMENTS`.
- Version 1.3.0; CHANGELOG, README, ARCHITECTURE, PROJECT, STATE, DECISIONS,
  tasks.

## Why

Named places without Cloud storing a location list. The arrival evidence
reads its target from the call's arguments (core `judge`, Cloud
`contract_verification.judge_report` with the schedule step's stored
arguments). A call by place has no x/y, so it must be judged against what the
adapter resolved. Rejected: resolving in the step (second resolver, bypassed
by direct dispatch) and rewriting the request (hides what was asked). See
DECISIONS.md 2026-10-04.

## Verified

- pytest with flyto-core origin/main 50c4876 (2.38.0, exported source, not
  installed into any repo): 289 passed.
- pytest with flyto-core 2.35.0 (the flyto-core checkout's venv): 263 passed,
  26 skipped. Without flyto-core (flyto-robotics venv, py3.12): 228 passed,
  61 skipped.
- `ruff check src tests` with CI's pinned ruff 0.15.15: All checks passed.
- `flyto-index verify . --strict` (2.18.1): PASS, 20 pass / 0 warn / 0 fail.
- `flyto-index task validate`: pass (ruff pass, 287 passed) with
  `test_core_capability_host_runs_both_packs_end_to_end` deselected: that test
  strips PYTHONPATH for its subprocess, and the indexer's interpreter has no
  flyto-core installed. It passes in the 289-test run above.
- Core's real judge: by-place arrival usable at the resolved place, unusable
  0.4 m away (measured 0.4, allowed 0.3), heading judged against the place's
  yaw; judged against the authored `{place}` alone it is unusable.

## Not verified

- No live adapter, twin or robot; dispatch is faked.
- No host reads `resolved_arguments` yet (Cloud judges the schedule step's
  stored arguments), so a navigation by place is unprovable there today:
  fails closed, never a false arrival.
- Builder rendering of a string `place` field beside optional x/y not checked.

## Follow-ups

- Cloud / Desktop: judge a navigate by place against `resolved_arguments`.
- Planner: read `robotics.places` (and cite its `places` artifact) before
  naming a place.
