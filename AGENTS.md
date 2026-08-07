# Agent rules

Read `PROJECT.md`, `ARCHITECTURE.md`, `STATE.md` and `DECISIONS.md` before
changing anything here.

## Constraints

- **Never drive hardware from this package.** No serial port, no ROS topic, no
  velocity, no `rclpy`. A step builds a plan and posts it. The reason is in
  DECISIONS.md and it is a safety property, not a preference.
- **Never put a host in a step parameter.** The gateway address is configuration.
  A test asserts no plan contains one; do not weaken it.
- **Every plan that moves must end in a safe stop.** The gateway refuses one that
  does not; the builders here append it so an author never meets that as an error.
- **`flyto-core` is imported inside `register_all`, never at module scope.** `plan`
  and `gateway` must stay importable and testable without it.
- **A missing `flyto-core` is logged, not raised.** Discovery loads every plugin in
  one loop; raising would take down the others.

## Verification

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
```

36 tests, none needing a robot or `flyto-core`. Any change to bounds, to the plan
shape, or to how the address is resolved needs a test that would fail without it.

## Repo notes

Merged from `CLAUDE.md` so Codex and Claude read one set of rules.

The constraints in this file are the point of this package, not style
preferences.

This repository is deliberately small and deliberately optional. The temptation
it invites is to make it do more: talk to ROS directly, take a host as a
parameter, collapse the three steps into one generic node, or grow its own safety
logic. Each of those has been considered and rejected with a stated reason in
`DECISIONS.md` and `ROADMAP.md`. Read those before proposing any of them again.

Keep the project-memory scaffold current in the same change: `PROJECT.md`,
`ARCHITECTURE.md`, `STATE.md`, `ROADMAP.md`, `tasks.md`, `DECISIONS.md`,
`CHANGELOG.md`, `docs/README.md`, `handoffs/_registry.md`.
