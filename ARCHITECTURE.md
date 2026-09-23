# Architecture

## Production path

```text
Flyto2 Cloud / War Room
        |
        | selects workflow host + commanded resource
        v
AI Space execution host
        |
        | flyto.capability-request.v1
        v
Generic ROS 2 Adapter
        |
        | standard ROS 2 / DDS / Zenoh / rosbridge
        v
robot resource
```

This repository owns only the authoring edge between the builder and the canonical capability request.

## Builder plugin

`modules.py` registers Move / Turn / Stop through the existing `flyto.modules` entry point. Each module has explicit `params_schema` metadata so the real builder can render and validate its inputs.

The module validates against the production capability contract, then emits one canonical request. It does not emit `requires_device`, choose an execution host, open a network connection, or import ROS.

`provides_capability` is intentionally unset. These classes are authoring nodes, not resource providers, and `robotics.move` can emit either `motion.advance` or `motion.retreat` depending on parameters. Resource admission follows the emitted request.

## Canonical bounds

The authoring contract is aligned with the Generic ROS 2 Adapter:
- distance: 0.05–2.0 m
- speed: 0.02–0.25 m/s forward
- speed: 0.02–0.20 m/s reverse
- rotation: 1–180 degrees
- stop: no legacy dwell argument

The builder exposes the conservative 0.20 m/s move maximum so the same authored Move node remains valid if the user switches it to reverse.

## Host dispatch

In ordinary builder/preview contexts the node is declaration-only. A selected execution host may inject an opaque trusted dispatcher. The package cannot construct that authority from workflow data.

## Removed legacy path

The old `flyto.robotics.plan.v1`, delivery capability catalog, robot-local HTTP gateway, and executable Gazebo runtime path are not part of the production package anymore. Historical files in handoffs/results remain evidence only.

## Safety invariants

- no `rclpy`, serial access, motor driver, or `cmd_vel` publication here;
- no host/address/token in capability requests;
- commanded equipment and execution host remain separate identities;
- execution success is not mission verification;
- physical acceptance remains outside software closure.
