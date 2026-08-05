# Roadmap

## Near term

1. **Read bounds from the robot, not from constants.** `flyto-robotics` already
   exposes `robot.capabilities.list` over MCP, carrying per-capability argument
   specs, `compatible_robots` and `safety_class`. Expose the same catalog on the
   HTTP gateway and read bounds from it. Today's constants are a worse duplicate
   that will drift, because a large AMR and a TurtleBot have different limits.
2. **A generic escape hatch.** One `robotics.command` step whose capability list
   and parameter schema come from that catalog, so a robot that gains an arm or a
   lift works without a new release of this package.
3. **Install alongside a real `flyto-core`** and confirm the steps appear on the
   canvas.

## Later

- Publish to PyPI once the catalog work lands, so the bounds a user gets are the
  robot's rather than this package's.

## Explicitly out of scope

- **Collapsing the three named steps into the generic one.** Three nodes labelled
  Move / Turn / Stop read at a glance on a canvas; one generic node makes three
  identical boxes, turns static validation into a runtime fetch from a robot that
  may be offline while authoring, and cannot vary `icon` or `can_connect_to` per
  capability.
- **Driving hardware from this package.** See PROJECT.md.
