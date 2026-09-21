# Handoffs

New handoffs use `YYYY-MM-DD-topic.md`.

| Date | Topic | File | Status | Owner | Branch |
|---|---|---|---|---|---|
| 2026-09-21 | External ROS 2 adapter architecture | `2026-09-21-external-ros2-adapter.md` | Active — production modules emit canonical capability requests; Pi delivery path is legacy only | ChatGPT | `fix/external-ros2-adapter-architecture` |
| 2026-08-28 | Safe-stop client that cancels the original gateway session | `2026-08-28-safe-stop-session-cancellation.md` | Historical — superseded for production by the 2026-09-21 external ROS 2 adapter architecture | codex | main |
| 2026-08-13 | Trusted catalog plan wiring using the lower runtime argument names | `2026-08-13-trusted-catalog-plan-wiring.md` | Historical — lower delivery-plan compatibility only; Pi runner integration is no longer a production goal | flyto_coding | main |
| 2026-08-13 | Strict immutable consumer for the delivery capability catalog | `2026-08-13-strict-capability-catalog-consumer.md` | Historical compatibility evidence; production discovery belongs to the external adapter | flyto_coding | main |
| 2026-08-09 | A bottom-up Gazebo verifier, reconciled against the layer below it | `2026-08-09-gazebo-bottom-up-closed-loop.md` | Historical simulation evidence — passed run `mrg-20260809T101631Z-79266`; not the production transport | claude | main |
| 2026-08-08 | One table for what a step means, and the robot's own argument names | `2026-08-08-one-table-and-the-robots-own-names.md` | Active | codex | main |

The work that created this package is recorded in
`flyto-cloud/handoffs/2026-08-05-space-task-closed-loop.md`, because it spans
three repositories.
