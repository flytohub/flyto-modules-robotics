# Provider-declared artifacts and recovery; the Open-RMF fleet pack

Owner: claude
Branch: claude/evidence-recovery-fleet
Date: 2026-10-04

## What changed

- `capabilities.py`: flyto-core 2.36.0 optional keys in the spec rows —
  `robotics.halt` `role: safe_stop`; `robotics.observe` artifacts
  (`photo`, `image/jpeg`, 2,000,000 B); `robotics.map` artifacts (`map`,
  `image/jpeg` | `image/png`, 8 MiB); `robotics.advance` / `.retreat`
  `recovery` (`motion.rotate`, `motion.advance`, `motion.retreat`; observe
  `recovery_context`; guidance ≤ 500 chars). `FLEET_SPECS`: `fleet.navigate`
  (`motion.navigate_to_waypoint`), `fleet.dock` (`motion.dock`), `fleet.load`
  (`transport.load`), `fleet.unload` (`transport.unload`), each with a
  `waypoint` text parameter and an actuating movement contract with
  `requires_safe_stop: false`, `cancellable: true`,
  `expected_duration_ms: 600000`.
- `recovery.py` (new): Cloud's `services/space_tasks/detour.py` sectors and a
  `recovery_for(spec, record)` that a failed/timed-out step returns as
  `recovery` (declared capabilities + guidance + adapter facts + sectors);
  falls back to `motion_outcome` from an adapter older than flyto-robotics 0.2.0.
- `modules.py`: optional keys feature-detected via
  `core.capability_contract.OPTIONAL_FIELDS` and dropped with one warning on an
  older core; step outputs reduce `adapter_evidence.artifacts` to kind / media
  type / bytes / sha256; `build_fleet_modules`; shared `_capability_step`.
- `capability_request.py`: bounded text parameters (`minLength`/`maxLength`,
  trimmed, control characters refused).
- `fleet_pack.py` (new) + entry point `fleet`; `PACK_DESCRIPTION` on both packs;
  1.1.0. README ("OpenRMF through the same contract"), CHANGELOG, ARCHITECTURE,
  DECISIONS, STATE, ROADMAP, tasks, docs/README.
- Tests: `tests/test_evidence_recovery_fleet.py` (new); vendored
  `contract_rules.py` extended to the 2.36 keys; core-version-aware
  expectations in `test_capabilities.py` / `test_registration.py`.

## Why

The provider says what a host used to know: which step is the stop, which
return a picture, and what to try after a blocked straight move. A host passes
`recovery` to its planner and keeps no robot geometry. Fleets are a second
entry point so a site shows only the pack it uses.

`motion.navigate_to_waypoint` instead of `motion.navigate`: two different
contracts under one capability id make flyto-core's capability host report
`ambiguous` (fail closed, default 60 s deadline, no verdicts) and the manifest
entry go to `fleet.navigate`. Seen in a run before the rename
(`deadline_seconds: 60.0`); after it 600.0 and `contract_status: declared`.

## Verified

- `ruff 0.15.15 check src tests` (the CI pin): All checks passed.
- `PYTHONPATH=src pytest tests -q -o addopts=""`:
  - flyto-core main 279cbb3 (2.36.0), Python 3.11: 207 passed — incl. Core's
    `validate_contract` normalized form for all 11 contracts, and an end-to-end
    run through Core's `ModuleRegistry` + `CapabilityHost` with fake adapters
    (fleet navigate declared, 600 s deadline; un-allowed fleet load refused by
    the host; photo artifact kept by the host and stripped from the step
    output; blocked advance safe-stopped by the host with `recovery` returned;
    halt allowed by its `safe_stop` role).
  - flyto-core 2.35.0 (0af4da8): 195 passed, 12 skipped (optional keys dropped).
  - released flyto-core 2.33.0: 168 passed, 39 skipped.
  - no flyto-core, Python 3.12: 167 passed, 40 skipped.
- Sectors equal Cloud's transcription on 300 seeded random sweeps.
- Built wheel 1.1.0 installed beside flyto-core main: `discover_plugins` finds
  `robotics` (7 modules) and `fleet` (4) with their descriptions.
- `flyto-index verify . --strict`: 20 pass, 0 warn, 0 fail;
  `verify-workspace` with the flyto-robotics worktree: PASS.
- Cross-repo with flyto-robotics `claude/provider-evidence` (real adapters,
  fake transports) through Core's host: see that handoff.

## Not verified

- No robot, simulator or Open-RMF deployment contacted.
- MCP `task(action='validate')`: the MCP server is pinned to another root.
- Cloud reading a step's `recovery` (it still runs its own `detour.py`) and
  the new capability id `motion.navigate_to_waypoint` in Cloud's vocabulary.
- `.github/workflows/publish.yml` still checks the 0.x step ids
  (`robotics.turn`); it runs only on tags, which were not pushed.

## Follow-ups

- Cloud: use the step's `recovery` for the detour prompt; accept
  `motion.navigate_to_waypoint`.
- Update `publish.yml`'s wheel smoke test before any release.
