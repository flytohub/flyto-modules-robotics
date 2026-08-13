# Roadmap

## Near term

1. **Integrate the Pi runner with the trusted named-plan API.** The pure contract
   is available with fail-closed `require_trusted_catalog` semantics; the next
   repository can fetch the lower catalog and call it before posting locally.
2. **A generic escape hatch.** One `robotics.command` step whose capability list
   and parameter schema come from that catalog, so a robot that gains an arm or a
   lift works without a new release of this package.
3. **Confirm the steps on the builder canvas.** Installing alongside a real
   `flyto-core` is done: 2.27.0 discovers the package through the entry point,
   owns all three modules and reports their three capabilities. What is left is
   the canvas itself — load the builder with this installed and confirm the three
   steps are visible and usable there.

## Later

- Decide whether preview metadata should be refreshed from a cached catalog
  without making the canvas depend on an online robot.

## Explicitly out of scope

- **Collapsing the three named steps into the generic one.** Three nodes labelled
  Move / Turn / Stop read at a glance on a canvas; one generic node makes three
  identical boxes, turns static validation into a runtime fetch from a robot that
  may be offline while authoring, and cannot vary `icon` or `can_connect_to` per
  capability.
- **Driving hardware from this package.** See PROJECT.md.
