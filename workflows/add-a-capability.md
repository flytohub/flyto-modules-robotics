# Adding support for a new robot capability

The robot already lists its own capabilities, so most of this is confirming
rather than authoring.

1. **Check whether you need a step at all.** If the capability is one the generic
   step can carry (see ROADMAP 2), nothing here changes.
2. **Read the robot's own definition.** `flyto-robotics`'s `CapabilityDefinition`
   carries the argument specs and bounds. Do not invent bounds that disagree with
   it — that is the duplication STATE.md already flags.
3. **Add a builder in `plan.py`.** Pure, bounded, ending in a safe stop. Assert
   the exact plan bytes in a test.
4. **Add the step class in `modules.py`.** `validate_params` builds the plan so a
   bad value fails on the canvas rather than at the wheels.
5. **Register it in `build_modules`** and give it a label, an icon and a colour —
   a step with no label cannot be found on the canvas.
6. **Run the suite.** No test may need a robot.
