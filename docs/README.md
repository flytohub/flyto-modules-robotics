# Docs

This package is small enough that the durable documentation lives in the
project-memory files at the repository root:

| File | What it answers |
|---|---|
| `PROJECT.md` | what this is for, and what it deliberately is not |
| `ARCHITECTURE.md` | builder → capability request → external ROS 2 adapter boundary |
| `STATE.md` | what is verified and what is not |
| `ROADMAP.md` | what is next, and what is out of scope |
| `DECISIONS.md` | the decisions that shaped it, and what each one rejected |
| `README.md` | installing and configuring it |

Production integrations should consume `capability_request_for_step`, which emits
`flyto.capability-request.v1` without a host, credential or robot-local runtime.
`plan_for_step` / `trusted_plan_for_step`, the delivery catalog and explicitly
named `legacy_gateway.py` are legacy preview/Gazebo compatibility only while old
consumers migrate. The package top level does not export that gateway client.
