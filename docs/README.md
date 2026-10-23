# Docs

Durable project documentation lives in the repository root:

| File | Purpose |
|---|---|
| `docs/project/PROJECT.md` | product boundary |
| `ARCHITECTURE.md` | step → host dispatcher → flyto-robotics adapter |
| `docs/project/STATE.md` | verified state and remaining physical acceptance |
| `docs/project/ROADMAP.md` | completed software closure and future work |
| `docs/project/DECISIONS.md` | architecture decisions |
| `docs/project/tasks.md` | closure checklist |

The `fleet` entry point (`fleet_pack.py`) registers the Open-RMF steps; `recovery.py` turns the adapter's `recovery_context` into the planner-facing detour sectors.
`presentation.py` is the HMI declaration (entry point group `flyto2.resource_presentations`); see ARCHITECTURE.md, HMI presentation.

Each capability is one `@register_module` with `provides_capability` and a `flyto.capability-contract.v1` contract (`src/flyto_modules_robotics/capabilities.py`, `modules.py`). `capability_request_for_step` is the pure request API. The historical plan/catalog/gateway execution path has been retired; historical handoffs and results (docs/project/) remain evidence only.
