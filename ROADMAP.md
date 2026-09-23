# Roadmap

## Software closure

Completed:
1. Canonical `flyto.capability-request.v1` authoring contract.
2. Host-neutral execution handoff to the approved external adapter path.
3. Real `flyto-core` builder-registry acceptance for Move / Turn / Stop.
4. Explicit builder parameter schemas.
5. Authoring bounds aligned with the Generic ROS 2 Adapter.
6. Removal of the retired plan/catalog/gateway authoring path.

## Remaining product work

- Add higher-level nodes only when backed by stable Flyto2 capabilities, such as named navigation.
- Allow adapter-discovered schemas to enrich the authoring UI without making an offline canvas depend on live hardware.
- Decide separately whether this package should be published to PyPI.

## Physical acceptance

Physical TurtleBot3 movement, interruption, safe-stop, sensor/evidence verification, and recovery remain separate hardware acceptance work.
