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
4. **Finish pure authoring-contract migration.**
   The robot-local HTTP gateway and executable Gazebo runtime are gone. Remove
   the remaining lower delivery-catalog / `flyto.robotics.plan.v1` authoring
   compatibility once the builder no longer reuses it for parameter validation.

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
