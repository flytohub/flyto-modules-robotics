# Docs

This package is small enough that the durable documentation lives in the
project-memory files at the repository root:

| File | What it answers |
|---|---|
| `PROJECT.md` | what this is for, and what it deliberately is not |
| `ARCHITECTURE.md` | the three layers, and why there is an HTTP hop |
| `STATE.md` | what is verified and what is not |
| `ROADMAP.md` | what is next, and what is out of scope |
| `DECISIONS.md` | the decisions that shaped it, and what each one rejected |
| `README.md` | installing and configuring it |

Runner integrations should use the public `plan_for_step` API with the immutable
catalog returned by `capability_catalog`; `preview_plan_for_step` is canvas-only
compatibility and is not lower-authority execution validation.
