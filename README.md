# flyto-modules-robotics

Optional robot-control modules for Flyto2 workflows. Install this only on
installations that drive a robot:

```bash
pip install flyto-modules-robotics
```

Without it, Flyto2 is pure software automation. With it, the workflow builder
gains four steps — move, turn, stop, and read the range scan — so a command like
"advance three steps" is authored on the canvas like any other workflow.

## Why this is a separate package

`flyto-core` is the software execution engine and does not know what a robot is.
This package is discovered through `flyto-core`'s existing
`flyto.modules` entry point, so hardware arrives as an install decision rather
than as a dependency everybody carries.

## What a step actually does

A step builds a `flyto.robotics.plan.v1` and posts it to the robot's own gateway
over loopback. It never names a machine: the job was already dispatched to a
device, so the module is running on the robot it is driving. That is what lets
five identical robots share one authored workflow instead of five copies.

The gateway — not this package — owns safety. It validates the plan against a
frozen capability registry, refuses one that moves without ending in a safe
stop, runs one mission at a time, and still sends the final zero-velocity stop
if the caller dies mid-mission. Running out of process is the whole point.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `FLYTO_ROBOTICS_GATEWAY_URL` | `http://127.0.0.1:8766` | the local robot gateway |
| `FLYTO_ROBOTICS_DELIVERY_TOKEN` | — | bearer token, required |
| `FLYTO_ROBOTICS_ROBOT_ID` | — | must match the gateway's job |
