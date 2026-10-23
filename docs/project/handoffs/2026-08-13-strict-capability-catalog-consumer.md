# Strict capability catalog consumer

This bottom-up slice consumes the accepted `flyto-robotics` delivery gateway
endpoint without adding execution authority. `gateway.capability_catalog()`
sends an authenticated, body-free `GET /v1/capabilities`; it never starts a plan
or delivery. `catalog.py` accepts only the exact
`flyto.robotics.capability-catalog.v1` projection and returns frozen records,
tuples and read-only mappings.

Validation is fail-closed: exact top-level, entry and argument fields; revision
1; safe unique capability/runtime identities; approved flyto-robotics executor
entries; strict booleans and finite numbers; bounded argument payloads; and
lower-compatible canonical JSON recomputation for every schema hash and the
overall capabilities hash. Missing, unknown, duplicated, unsafe, oversized,
deep or mismatched input receives only `capability catalog invalid`, with no raw
response or bearer token included.

Plan construction from this read model is recorded separately in
`2026-08-13-trusted-catalog-plan-wiring.md`. Keeping the handoffs distinct makes
the catalog validation boundary independently reviewable and preserves this
receipt's exact scope.

No flyto-core, ROS or third-party import is introduced. No Gazebo, hardware,
deployment, publication or credential access belongs to this handoff.

## Pre-rework verification receipt

Governed route job `job_f0844bad058144f2b0514148` produced pre-rework
implementation revision
`f1d44e75420bd4f1503a9433ce20ec77cbf962749593121082402a01bf0ccaf0`.
The route-required verification passed. Codex independently ran the full
repository suite (`255 passed in 0.21s`) and the diff check was clean. This is
exact evidence for that pre-rework revision, not audit acceptance of this
current rework revision.

Neither that receipt nor this rework involved hardware, Gazebo, deployment,
publication or credentials. Those boundaries remain unchanged.
