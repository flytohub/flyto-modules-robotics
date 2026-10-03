# Docs

Durable project documentation lives in the repository root:

| File | Purpose |
|---|---|
| `PROJECT.md` | product boundary |
| `ARCHITECTURE.md` | step → host dispatcher → flyto-robotics adapter |
| `STATE.md` | verified state and remaining physical acceptance |
| `ROADMAP.md` | completed software closure and future work |
| `DECISIONS.md` | architecture decisions |
| `tasks.md` | closure checklist |

Each capability is one `@register_module` with `provides_capability` and a `flyto.capability-contract.v1` contract (`src/flyto_modules_robotics/capabilities.py`, `modules.py`). `capability_request_for_step` is the pure request API. The historical plan/catalog/gateway execution path has been retired; historical handoffs/results remain evidence only.
