# 2026-09-23 software closure

## Scope

Software-only closure for Flyto2 robotics authoring and external-adapter handoff.

## Closed

- one production authoring contract: `flyto.capability-request.v1`;
- explicit Move / Turn / Stop builder schemas;
- canonical adapter-compatible motion bounds;
- host-neutral opaque execution dispatch;
- no robot-local Flyto2 runtime requirement;
- retired plan/catalog/gateway authoring path removed;
- real flyto-core registry/execute acceptance included in tests.

## Not claimed

No new TurtleBot3 movement was executed. Physical bounded motion, interruption, safe stop, evidence verification, and recovery remain pending hardware acceptance.
