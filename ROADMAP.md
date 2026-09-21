# Roadmap

## Near term

1. **External adapter consumer integration.**
   Have the AI Space/workflow runtime consume `flyto.capability-request.v1`
   directly and route it to the approved external Generic ROS 2 Adapter.
2. **Canonical capability metadata.**
   Move builder registration metadata away from the historical
   `robotics.motion.*` authoring identifiers once the host registry supports a
   module that may emit more than one execution capability (Move can advance or
   retreat).
3. **Builder acceptance.**
   Load a real Flyto2 builder with this package installed and verify Move /
   Turn / Stop authoring plus the emitted capability request.
4. **Finish legacy simulation extraction.**
   The production-facing `gateway.py` API is gone; the historical HTTP client is
   explicitly `legacy_gateway.py` and not top-level exported. Remove that client,
   lower delivery-catalog coupling and `flyto.robotics.plan.v1` after the last
   simulation/downstream consumer migrates.

## Later

- Add higher-level authoring nodes only when they map to a stable Flyto2
  capability (for example named navigation), not to a robot vendor API.
- Allow adapter-discovered capability schemas to improve authoring UI without
  making an offline canvas depend on a live robot.

## Explicitly out of scope

- ROS, serial, motor or `cmd_vel` access in this package.
- Pi-side Flyto2 runners/gateways.
- A second scheduler or execution authority.
- Making action completion equal task completion.
