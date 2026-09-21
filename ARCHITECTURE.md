# Architecture

## One authority path

```text
workflow authoring
      ↓
flyto-core registry
      ↓
flyto-modules-robotics
  - declares capability
  - builds bounded plan
  - never dispatches
      ↓
Flyto2 Space Task authority
  - approval
  - permission
  - resource binding
  - policy / lease
      ↓
external robotics adapter
      ↓
ROS 2 / Nav2 / Open-RMF / simulator / vendor runtime
      ↓
evidence / telemetry / outcome
      ↓
Flyto2 verification and recovery
```

The package deliberately stops before transport. It contains no robot-local
HTTP client, no Raspberry Pi runner, no ROS client, no WebSocket control plane
and no device credential handling.

## Why transport is external

A workflow is portable only if it does not contain a machine address. The same
authored `robotics.move` should be usable with a TurtleBot3 simulator, a
physical ROS 2 robot, or a fleet adapter without cloning the workflow for each
endpoint.

The external adapter is selected by capability/resource assignment. If the
selected adapter cannot map, cancel, or safe-stop the requested capability, it
must refuse. There is no fallback to a direct robot-control channel.

## Plan and capability contracts

Three boundaries remain intentionally distinct:

1. **Flyto2 registry capability** — what the workflow requires.
2. **Plan document** — the bounded physical intent to execute.
3. **Adapter/runtime capability** — what the selected external executor can
   actually provide.

The immutable catalog parser and `trusted_plan_for_step` allow an adapter to
supply lower-owned bounds without letting a device approve itself. Catalog
parsing is pure data validation; this package no longer fetches a catalog over
the network.

## Completion

This package never decides that a mission is complete. Adapter success is
execution evidence. Flyto2 binds that evidence to the task, goal and execution
receipt before independent verification may mark the task complete.
