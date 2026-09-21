# Tasks

- [x] Register `robotics.move`, `robotics.turn`, and `robotics.stop` through
      the public `flyto.modules` entry point.
- [x] Keep plan construction pure, bounded, host-free and safe-stop terminated.
- [x] Keep trusted catalog parsing immutable and fail-closed.
- [x] Remove the robot-local HTTP gateway client, Pi-runner assumptions,
      localhost:8766 configuration, delivery credentials and the old Gazebo
      lower-runtime verifier from the active software architecture.
- [x] Make the active documentation describe one execution authority path:
      Flyto2 → external adapter → machine/simulator → evidence → verification.
- [ ] Run the repository CI on the external-adapter cleanup and merge it to
      `main`.
- [ ] Confirm the three named steps render and remain usable on the real Flyto2
      builder canvas.
- [ ] Add a simulator-backed software acceptance adapter through the generic
      adapter contract; do not add simulator-specific authority to Cloud.
- [ ] Decide whether to add `robotics.command`.
- [ ] Clear the setuptools license metadata deprecation warning.
- [ ] Decide whether and when to publish the package to PyPI.

Physical TurtleBot3 validation is intentionally not tracked as a task in this
software package. It belongs to the separate hardware acceptance effort.
