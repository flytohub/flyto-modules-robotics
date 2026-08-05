"""Building the plan a workflow step asks the robot to carry out.

This is where "advance three steps" becomes a document. It is deliberately pure:
no network, no environment, no clock — so the exact bytes a step will send can be
asserted in a test without a robot anywhere nearby.

Two rules shape it.

Bounds live here, at the point of authoring. A distance or a speed outside them
is refused before anything is sent, so a mistyped workflow fails on the canvas
rather than at the wheels. The gateway checks its own bounds again on arrival —
this is the near check, not the only one.

A plan that moves always ends in a safe stop. The gateway refuses one that does
not, and rather than let a caller discover that as an error, every builder here
appends it.
"""

from __future__ import annotations

from typing import Any

PLAN_CONTRACT_VERSION = "flyto.robotics.plan.v1"
PLAN_RUN_REQUEST_CONTRACT_VERSION = "flyto.cloud.plan-run-request.v1"

# Bounds a workflow author may not exceed. Chosen to sit inside what a TurtleBot3
# class platform will accept, so a step that validates here is not then refused
# by the robot for being out of range.
MIN_DISTANCE_M = 0.01
MAX_DISTANCE_M = 2.0
MIN_SPEED_MPS = 0.01
MAX_SPEED_MPS = 0.2
MAX_TURN_DEGREES = 360.0
MIN_TURN_DEGREES = 1.0
MIN_ANGULAR_SPEED = 0.05
MAX_ANGULAR_SPEED = 0.8
MAX_DWELL_SECONDS = 60.0

DEFAULT_SPEED_MPS = 0.12
DEFAULT_ANGULAR_SPEED = 0.4

SAFE_STOP_STEP = {
    "step_id": "stop.finish",
    "capability": "safe_stop",
    "arguments": {"seconds": 0.0},
    "timeout_seconds": 1.0,
    "on_failure": "abort",
}


class PlanBuildError(ValueError):
    """A step's parameters cannot become a plan."""


def _number(value: Any, name: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanBuildError(f"{name} must be a number")
    number = float(value)
    if not minimum <= number <= maximum:
        raise PlanBuildError(f"{name} must be between {minimum} and {maximum}")
    return number


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanBuildError(f"{name} is required")
    text = value.strip()
    if len(text) > 128:
        raise PlanBuildError(f"{name} must be 128 characters or fewer")
    return text


def _timeout_for(seconds: float) -> float:
    """A generous per-step ceiling, so a slow floor is not a failure."""
    return round(min(120.0, max(4.0, seconds * 3.0)), 3)


def _plan(
    *,
    plan_id: str,
    robot_id: str,
    goal: str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "contract_version": PLAN_CONTRACT_VERSION,
        "plan_id": plan_id,
        "robot_id": _identifier(robot_id, "robot_id"),
        "goal": goal,
        "generated_by": {
            "kind": "human",
            "provider": "flyto-cloud",
            "model": "workflow-card",
        },
        "steps": steps + [dict(SAFE_STOP_STEP)],
    }


def move_plan(
    *,
    robot_id: str,
    distance_m: Any,
    speed: Any = DEFAULT_SPEED_MPS,
    reverse: bool = False,
) -> dict[str, Any]:
    """Drive a signed distance in a straight line.

    ``reverse`` rather than a negative distance in the workflow: an author types
    a positive number and picks a direction, so a sign slip cannot silently turn
    "forward 40cm" into "backward 40cm".
    """
    distance = _number(
        distance_m, "distance_m", minimum=MIN_DISTANCE_M, maximum=MAX_DISTANCE_M
    )
    velocity = _number(speed, "speed", minimum=MIN_SPEED_MPS, maximum=MAX_SPEED_MPS)
    signed = -distance if reverse else distance
    direction = "backward" if reverse else "forward"
    return _plan(
        plan_id=f"workflow.move.{direction}.{int(round(distance * 100))}cm.v1",
        robot_id=robot_id,
        goal=f"move {direction} {distance:.2f} m then stop safely",
        steps=[
            {
                "step_id": f"move.{direction}",
                "capability": "move_relative",
                "arguments": {"distance_m": signed, "speed": velocity},
                "timeout_seconds": _timeout_for(distance / velocity),
                "on_failure": "abort",
            }
        ],
    )


def turn_plan(
    *,
    robot_id: str,
    degrees: Any,
    angular_speed: Any = DEFAULT_ANGULAR_SPEED,
    clockwise: bool = False,
) -> dict[str, Any]:
    """Turn in place by an angle, without translating."""
    angle = _number(
        degrees, "degrees", minimum=MIN_TURN_DEGREES, maximum=MAX_TURN_DEGREES
    )
    speed = _number(
        angular_speed,
        "angular_speed",
        minimum=MIN_ANGULAR_SPEED,
        maximum=MAX_ANGULAR_SPEED,
    )
    radians = angle * 3.141592653589793 / 180.0
    signed = -radians if clockwise else radians
    direction = "right" if clockwise else "left"
    return _plan(
        plan_id=f"workflow.turn.{direction}.{int(round(angle))}deg.v1",
        robot_id=robot_id,
        goal=f"turn {direction} {angle:.0f} degrees then stop safely",
        steps=[
            {
                "step_id": f"turn.{direction}",
                "capability": "turn_relative",
                "arguments": {"radians": signed, "angular_speed": speed},
                "timeout_seconds": _timeout_for(radians / speed),
                "on_failure": "abort",
            }
        ],
    )


def stop_plan(*, robot_id: str, seconds: Any = 0.0) -> dict[str, Any]:
    """Hold a stop. The one plan whose only step is the safe stop itself."""
    hold = _number(seconds, "seconds", minimum=0.0, maximum=MAX_DWELL_SECONDS)
    plan = _plan(
        plan_id="workflow.stop.v1",
        robot_id=robot_id,
        goal=f"hold a safe stop for {hold:.1f} s",
        steps=[],
    )
    plan["steps"][-1]["arguments"]["seconds"] = hold
    plan["steps"][-1]["timeout_seconds"] = _timeout_for(max(hold, 1.0))
    return plan


def run_request(plan: dict[str, Any], *, request_id: str, requested_at: str) -> dict[str, Any]:
    """Wrap a plan in the contract the gateway accepts."""
    return {
        "contract_version": PLAN_RUN_REQUEST_CONTRACT_VERSION,
        "request_id": _identifier(request_id, "request_id"),
        "plan": plan,
        "requested_at": _identifier(requested_at, "requested_at"),
    }
