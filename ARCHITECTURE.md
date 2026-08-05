# Architecture

Three layers, only the thinnest of which needs `flyto-core`.

```
flyto-core registry            <- register_all(), via the flyto.modules entry point
    |
modules.py                     <- the three step classes; the only flyto-core coupling
    |
plan.py        gateway.py      <- pure: builds plans / posts them over loopback
    |
flyto-robotics gateway         <- validates, executes, owns the final stop
    |
ROS 2 / robot
```

## Why the split

`flyto-core` is imported inside `register_all`, never at module scope. So `plan`
and `gateway` import — and are tested — on a machine with no `flyto-core`, which
is most machines.

`plan.py` is pure: no network, no environment, no clock. The exact bytes a step
will send are assertable in a test with no robot present.

## Why an HTTP hop rather than a library call

Importing `flyto-robotics` and calling its runner in-process would be simpler and
is wrong. `rclpy`'s init and shutdown are process-global, so a long-running
workflow executor cannot host them safely; and a caller that died mid-mission
would leave nothing to stop the robot. The gateway is a service with signal
handling that sends the final zero-velocity stop. The hop is isolation, not
overhead.

## Where the address comes from

Configuration, not a step parameter. The job was already dispatched to a device,
so the module is running on the robot it drives and the gateway is on loopback.
That is what lets five identical robots share one authored workflow.

| Variable | Default | Meaning |
|---|---|---|
| `FLYTO_ROBOTICS_GATEWAY_URL` | `http://127.0.0.1:8766` | the local robot gateway |
| `FLYTO_ROBOTICS_DELIVERY_TOKEN` | — | bearer token, required |
| `FLYTO_ROBOTICS_ROBOT_ID` | — | must match the gateway's job |
