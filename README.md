# flyto-modules-robotics

Optional robot-control modules for Flyto2 workflows. Install this only on
installations that drive a robot:

```bash
pip install flyto-modules-robotics
```

Without it, Flyto2 is pure software automation. With it, the workflow builder
gains three steps — move, turn and stop — so a command like "advance forty
centimetres" is authored on the canvas like any other workflow.

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

## Releasing

Published the way `flyto-core` is: push a `v*` tag and the workflow builds,
tests the built wheel, and uploads through PyPI Trusted Publishing. No token
lives in this repository.

```bash
git tag v0.1.0 && git push origin v0.1.0
```

The first release needs a **pending publisher** on PyPI, because Trusted
Publishing has nothing to trust until then. The project is not created by
hand: a pending publisher is what creates it, on the first successful upload.

The form lives under the **account** sidebar rather than a project's, since
the project does not exist yet — <https://pypi.org/manage/account/publishing/>,
"Add a new pending publisher":

| Field | Value |
|---|---|
| PyPI project name | `flyto-modules-robotics` |
| Owner | `flytohub` |
| Repository name | `flyto-modules-robotics` |
| Workflow name | `publish-pypi.yml` |
| Environment name | `pypi` |

`workflow_dispatch` publishes to TestPyPI instead, which needs the same entry
on test.pypi.org.

A pending publisher does not reserve the name — it only becomes a project on
the first upload that uses it.
