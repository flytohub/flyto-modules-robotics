# Registry rows for merged work marked Merged

Owner: claude
Branch: claude/registry-merged-20261011
Date: 2026-10-11

## What changed

`handoffs/_registry.md` only:

- `2026-10-07-recovery-semantics.md`: Active -> Merged (#14, merge commit 4eb1555).
- `2026-10-04-evidence-recovery-fleet.md`: Active (PR open) -> Merged (#10, merge commit 0975534).

## Why

Both branches are on `origin/main`; an Active row tells the other agent the
work is still open on its branch.

## Verified

- `git log origin/main` shows both merge commits.

## Not verified

- Nothing in code changed; no tests were run for this record-only change.

## Follow-ups

None.
