# Docs

The durable current documentation lives in the repository root:

| File | What it answers |
|---|---|
| `PROJECT.md` | purpose and ownership boundaries |
| `ARCHITECTURE.md` | canonical external-adapter execution model |
| `STATE.md` | current verified software state |
| `ROADMAP.md` | next software work |
| `DECISIONS.md` | architectural decisions and superseded choices |
| `README.md` | package usage and testing |

Adapter integrations may use `trusted_plan_for_step` with an immutable catalog
that the adapter obtained and validated through its own transport. This package
does not fetch robot state or execute plans itself.
