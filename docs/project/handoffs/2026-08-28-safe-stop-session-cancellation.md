# Safe-stop client for session cancellation

Owner: codex
Branch: main
Date: 2026-08-28

## What changed

`src/flyto_modules_robotics/gateway.py` now exposes `safe_stop(session_id,
reason=...)`, which posts to the lower delivery gateway's existing
`/v1/deliveries/{session_id}/safe-stop` endpoint and returns its session
payload. `tests/test_gateway.py` fixes the method, path, payload and returned
`cancelled` state as a regression contract.

## Why

The lower `flyto-robotics` gateway already stops the actuator and transitions
the active session to `cancelled`, but this client had no way to call it. Cloud
therefore refused every cancellation and incorrectly documented the endpoint as
absent. A separate stop plan was rejected because it cannot prove that the
original session was withdrawn.

## Verified

- Full package suite: **291 passed** using the sibling `flyto-ai` Python 3.12
  environment with `PYTHONPATH=src`.
- Changed-file Ruff check: passed.
- `flyto-index verify . --strict`: **18 passed, 0 warnings, 0 failures**.
- `git diff --check`: passed.

## Not verified

No network request reached a live gateway, and no ROS, Gazebo, Lima or physical
robot process ran. This is client-contract proof, not renewed physical evidence.

## Follow-ups

Wire the Cloud robotics conformance adapter to this method and accept
`cancelled` only when the returned session state says so. Re-run physical motion
conformance only after the robot is reachable and its area is confirmed clear.
