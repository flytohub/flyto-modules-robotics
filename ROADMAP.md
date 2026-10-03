# Roadmap

## Software closure

Completed:
1. Canonical `flyto.capability-request.v1` authoring contract.
2. Host-neutral execution handoff to the approved external adapter path.
3. Real `flyto-core` builder-registry acceptance.
4. Explicit builder parameter schemas.
5. Authoring bounds aligned with the Generic ROS 2 Adapter.
6. Removal of the retired plan/catalog/gateway authoring path.
7. One module per capability with a declared `flyto.capability-contract.v1` contract (1.0.0).

## Remaining product work

- Add a step only when the adapter declares the capability; named destinations would come from the adapter, not from here.
- Navigate declares no evidence yet: v1 measure ops compare phases, and arrival at an absolute coordinate is not one of them.
- Allow adapter-discovered schemas to enrich the authoring UI without making an offline canvas depend on live hardware.
- Decide separately whether this package should be published to PyPI.

## Physical acceptance

Physical TurtleBot3 movement, interruption, safe-stop, sensor/evidence verification, and recovery remain separate hardware acceptance work.
