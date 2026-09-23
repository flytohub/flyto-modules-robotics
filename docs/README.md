# Docs

Durable project documentation lives in the repository root:

| File | Purpose |
|---|---|
| `PROJECT.md` | product boundary |
| `ARCHITECTURE.md` | builder → capability request → external adapter |
| `STATE.md` | verified state and remaining physical acceptance |
| `ROADMAP.md` | completed software closure and future work |
| `DECISIONS.md` | architecture decisions |
| `tasks.md` | closure checklist |

Production integrations consume `capability_request_for_step`, which emits `flyto.capability-request.v1`. The historical plan/catalog/gateway execution path has been retired from the package; historical handoffs/results remain evidence only.
