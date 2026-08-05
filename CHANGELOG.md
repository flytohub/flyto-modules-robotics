# Changelog

## 0.1.0 — 2026-08-05

Initial version. Not published.

- Three workflow steps: `robotics.move`, `robotics.turn`, `robotics.stop`,
  registered into `flyto-core` through its `flyto.modules` entry point.
- Plans are built locally with bounded parameters and always end in a safe stop.
- The gateway address is configuration, never a step parameter, so identical
  robots share one authored workflow.
- A missing `flyto-core` is logged rather than raised: discovery loads every
  plugin in one loop, and raising would take down the others.
