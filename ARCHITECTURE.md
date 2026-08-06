# Architecture

Three layers, only the thinnest of which needs `flyto-core`.

```
worker or desktop                        robot
------------------------------------     ---------------------------------
flyto-core registry                      flyto_job_runner
    |  register_all()                        |  claims the job
modules.py   <- declares, never drives       |
    |                                        v
plan.py      -----> job payload -----> flyto-robotics gateway
                     (device queue)        validates, executes,
                                           owns the final stop
                                               |
                                           ROS 2 / robot
```

The split across the two columns is the point. `flyto-core` runs on the worker
and the desktop; the robot has neither. A step that drove hardware from the
left column would be reaching for a gateway on the wrong machine — the loopback
address meaning "this robot" on a Pi means "this container" on a worker.

So `modules.py` declares: it builds a plan, names the device, and returns it as
the payload the robot's runner reads from its job. `gateway.py` is the client
that runner uses; nothing in `modules.py` touches it, and a test asserts that by
inspecting imports and calls rather than grepping for the word.

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
