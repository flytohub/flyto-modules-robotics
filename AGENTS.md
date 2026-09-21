# Agent rules

Read `PROJECT.md`, `ARCHITECTURE.md`, `STATE.md` and `DECISIONS.md` before
changing anything here.

## Constraints

- **Never drive hardware from this package.** No serial port, no ROS topic, no
  velocity, no `rclpy`. A production step emits a canonical capability request
  for commanded equipment; an external adapter executes it. The reason is in
  DECISIONS.md and it is a safety property, not a preference.
- **Never put an execution host, gateway URL or credential in a step parameter.**
  AI Space / War Room chooses the execution computer. The request names only the
  commanded resource. Tests assert the production request contains no host,
  gateway, token or Pi-runner assumption.
- **Canonical production output is `flyto.capability-request.v1`.** Historical
  `flyto.robotics.plan.v1` builders remain only as pure authoring/preview
  compatibility until they are removed.
- **`flyto-core` is imported inside `register_all`, never at module scope.** Pure
  authoring/preview helpers stay importable without it. No robot-local gateway
  client or execution transport belongs in this package.
- **A missing `flyto-core` is logged, not raised.** Discovery loads every plugin in
  one loop; raising would take down the others.

## Before you edit: search and impact

Explore with the `flyto-indexer` tools before changing code, not with a blind
grep. The constraints above are easy to break from one file away, and the index
is what shows the other file.

- `search` — find the symbol and the places that already answer the question.
- `impact(target='<symbol>')` — the references and blast radius of the symbol you
  are about to change, before you change it. `impact(mode='unstaged')` for what
  you have already touched.

`plan_for_step` and the bounds in `plan.py` have callers outside this package;
`impact` is how you see them.

## Verification

Every change is verified bottom-up: the tests first, then the repository gate.

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
```

Tests, none needing a robot or `flyto-core`. Any change to bounds or request
shape needs a test that would fail without it.

`search` and `impact` are the pre-change gate; the strict verifier below is the
mandatory post-change gate. Run it after the edit, and hand nothing off until it passes:

```bash
flyto-index verify . --strict
```

It checks index integrity, secrets, documentation coverage, agent-instruction
hygiene and that the generated index is ignored. `--strict` promotes warnings to
failures, which is what CI runs. If `search` or `impact` looked stale, run
`flyto-index scan .` first and verify again.

## Repo notes

Merged from `CLAUDE.md` so Codex and Claude read one set of rules.

The constraints in this file are the point of this package, not style
preferences.

This repository is deliberately small and deliberately optional. The temptation
it invites is to make it do more: talk to ROS directly, choose an execution
host, put a Flyto runtime on the robot, or grow its own safety/verification
logic. Each of those has been considered and rejected with a stated reason in
`DECISIONS.md` and `ROADMAP.md`. Read those before proposing any of them again.

Keep the project-memory scaffold current in the same change: `PROJECT.md`,
`ARCHITECTURE.md`, `STATE.md`, `ROADMAP.md`, `tasks.md`, `DECISIONS.md`,
`CHANGELOG.md`, `docs/README.md`, `handoffs/_registry.md`.
