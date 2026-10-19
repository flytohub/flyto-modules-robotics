# Handoffs

New handoffs use `YYYY-MM-DD-topic.md`.

| Date | Topic | File | Status | Owner | Branch |
|---|---|---|---|---|---|
| 2026-10-19 | Screen roles: `surfaces` operator_console (default, request+approve <= 4, stop) / field_tablet (request <= 4, stop) / remote_view (read); schema re-vendored 9dce8cba...831615e; block sha256 2f07c993...64efc4e7 | `2026-10-19-robot-surface-roles.md` | Candidate — 1.7.0; 328 passed / 4 skipped; verify --strict 20/0/0; install only after Cloud with schema 9dce8cba is deployed | claude | `claude/hmi-surfaces-20261019` |
| 2026-10-18 | An idle robot's HMI offers a first request: `request_examples` (Proof #1 tasks), heading readout, localization state; schema re-vendored from Cloud f1e72d566 | `2026-10-18-hmi-first-request.md` | Candidate — 1.6.0; install only after Cloud with schema e8df2eae is deployed | claude | `claude/hmi-first-step-20261018` |
| 2026-10-12 | HMI presentation with live values: battery gauge, position2d, goal distance / progress, navigation state over flyto-robotics 0.8.0 channels; entry point `flyto2.resource_presentations` | `2026-10-12-hmi-live-values.md` | Candidate — 1.5.0; fakes and contract checks only, no live render | claude | `claude/hmi-values-20261012` |
| 2026-10-12 | HMI presentation declaration for the mobile robot (`flyto.resource-presentation.v1`) | `2026-10-12-presentation-v1.md` | Superseded — landed inside `claude/hmi-values-20261012` (2026-10-12 hmi-live-values) | claude | `claude/presentation-v1` |
| 2026-10-11 | Registry rows for merged work marked Merged | `2026-10-11-registry-merged.md` | Merged | claude | `claude/registry-merged-20261011` |
| 2026-10-07 | Recovery semantics (roles, fills) on the motion contracts | `2026-10-07-recovery-semantics.md` | Merged (#14, 4eb1555) — 1.4.0; equals Cloud FIRST_PARTY_REVIEWED; needs flyto-core 2.39.0 (feature-detected) | claude | `claude/recovery-declaration` |
| 2026-10-04 | Named places: `robotics.places`, `robotics.mark_place`, navigate by place with resolved target | `2026-10-04-robot-places.md` | Active — 1.3.0; needs flyto-robotics 0.3.0; hosts must judge against `resolved_arguments` | claude | `claude/robot-places` |
| 2026-10-04 | Navigation arrival is proven by the contract | `2026-10-04-navigate-arrival-evidence.md` | Done — 1.2.0; needs flyto-core 2.38.0 (feature-detected) | claude | `claude/navigate-arrival-evidence` |
| 2026-10-04 | Step output drops the legacy capture's bytes as well as the artifacts' | `2026-10-04-strip-legacy-capture-bytes.md` | Active | claude | `claude/strip-capture-bytes` |
| 2026-10-04 | Provider-declared artifacts, safe-stop role and detour recovery; Open-RMF `fleet` pack | `2026-10-04-evidence-recovery-fleet.md` | Merged (#10, 0975534); fakes only | claude | `claude/evidence-recovery-fleet` |
| 2026-10-04 | One module per capability, each with a declared capability contract | `2026-10-04-capability-contract.md` | Merged (#9); superseded in part by 2026-10-04 evidence-recovery-fleet | claude | `claude/capability-contract` |
| 2026-09-21 | External ROS 2 adapter architecture | `2026-09-21-external-ros2-adapter.md` | Merged (#3, squash fb0ab0d; branch tip c6914d5 is tree-identical to it); duplicate follow-up #5 closed; remote branch deleted 2026-10-07. Production modules emit canonical capability requests; Pi delivery path is legacy only | ChatGPT | `fix/external-ros2-adapter-architecture` |
| 2026-08-28 | Safe-stop client that cancels the original gateway session | `2026-08-28-safe-stop-session-cancellation.md` | Historical — superseded for production by the 2026-09-21 external ROS 2 adapter architecture | codex | main |
| 2026-08-13 | Trusted catalog plan wiring using the lower runtime argument names | `2026-08-13-trusted-catalog-plan-wiring.md` | Historical — lower delivery-plan compatibility only; Pi runner integration is no longer a production goal | flyto_coding | main |
| 2026-08-13 | Strict immutable consumer for the delivery capability catalog | `2026-08-13-strict-capability-catalog-consumer.md` | Historical compatibility evidence; production discovery belongs to the external adapter | flyto_coding | main |
| 2026-08-09 | A bottom-up Gazebo verifier, reconciled against the layer below it | `2026-08-09-gazebo-bottom-up-closed-loop.md` | Historical simulation evidence — passed run `mrg-20260809T101631Z-79266`; not the production transport | claude | main |
| 2026-08-08 | One table for what a step means, and the robot's own argument names | `2026-08-08-one-table-and-the-robots-own-names.md` | Active | codex | main |

The work that created this package is recorded in
`flyto-cloud/handoffs/2026-08-05-space-task-closed-loop.md`, because it spans
three repositories.
- [2026-09-23 software closure](2026-09-23-software-closure.md) — canonical authoring contract closed; only physical acceptance remains.
