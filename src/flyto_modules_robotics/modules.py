"""The four workflow steps this package adds to the builder.

flyto-core is imported inside :func:`build_modules`, never at module scope. That
keeps ``plan`` and ``gateway`` importable — and testable — on a machine with no
flyto-core installed, which is most machines: this package is only installed
where a robot is.

Each step does the same three things: turn its parameters into a plan, hand the
plan to the local gateway, and report what came back. No step opens a serial
port, publishes a velocity, or holds a ROS context. The gateway owns the robot,
so a step that dies leaves the robot's own safe stop in charge.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .gateway import GatewayError, GatewayRefused, await_session, robot_id, start_plan
from .plan import PlanBuildError, move_plan, run_request, stop_plan, turn_plan

MODULE_MOVE = "robotics.move"
MODULE_TURN = "robotics.turn"
MODULE_STOP = "robotics.stop"

CATEGORY = "robotics"
ICON_COLOR = "#22D3EE"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _dispatch(plan: dict[str, Any], *, wait: bool, timeout_seconds: float) -> dict[str, Any]:
    """Send one plan and describe the outcome in workflow terms."""
    request = run_request(
        plan,
        request_id=f"wf-{uuid.uuid4().hex[:12]}",
        requested_at=_now_iso(),
    )
    session = start_plan(request)
    session_id = str(session.get("session_id") or "")
    if wait and session_id:
        session = await_session(session_id, timeout_seconds=timeout_seconds)

    state = str(session.get("state") or session.get("status") or "unknown")
    return {
        "session_id": session_id,
        "state": state,
        "succeeded": state.lower() == "succeeded",
        "timed_out": bool(session.get("timed_out")),
        "plan_id": plan["plan_id"],
        "goal": plan["goal"],
        "pose": session.get("final_pose") or session.get("pose"),
        "minimum_range": session.get("minimum_range"),
    }


def build_modules(base_module, register_module) -> list[tuple[str, type]]:
    """Define the module classes against whatever flyto-core provides.

    The base class and decorator are passed in rather than imported so this
    function has no import-time dependency on flyto-core, and so a test can
    exercise the classes against a stand-in.
    """

    def _fail(exc: Exception) -> dict[str, Any]:
        # A refusal and an unreachable robot are different facts and a workflow
        # author needs to tell them apart: one is a bad step, the other is a
        # robot that is not there.
        return {
            "session_id": "",
            "state": "refused" if isinstance(exc, GatewayRefused) else "unavailable",
            "succeeded": False,
            "timed_out": False,
            "error": str(exc)[:300],
        }

    @register_module(
        module_id=MODULE_MOVE,
        version="1.0.0",
        category=CATEGORY,
        subcategory="motion",
        tags=["robot", "motion", "move", "drive"],
        label="Move Robot",
        label_key="modules.robotics.move.label",
        description="Drive the robot a fixed distance in a straight line, then stop",
        description_key="modules.robotics.move.description",
        icon="MoveVertical",
        color=ICON_COLOR,
        input_types=["*"],
        output_types=["object"],
        can_receive_from=["*"],
        can_connect_to=["*"],
        timeout_ms=180000,
        retryable=False,
        concurrent_safe=False,
        requires_credentials=True,
        handles_sensitive_data=False,
    )
    class RoboticsMove(base_module):
        module_id = MODULE_MOVE
        module_name = "Move Robot"
        module_description = "Drive a fixed distance, then stop safely"

        def validate_params(self) -> None:
            # Build the plan now so a bad distance fails on the canvas rather
            # than after something has started moving.
            move_plan(
                robot_id="validation-only",
                distance_m=self.params.get("distance_m", 0.4),
                speed=self.params.get("speed", 0.12),
                reverse=bool(self.params.get("reverse", False)),
            )

        def execute(self) -> dict[str, Any]:
            try:
                plan = move_plan(
                    robot_id=robot_id(),
                    distance_m=self.params.get("distance_m", 0.4),
                    speed=self.params.get("speed", 0.12),
                    reverse=bool(self.params.get("reverse", False)),
                )
                return _dispatch(
                    plan,
                    wait=bool(self.params.get("wait", True)),
                    timeout_seconds=float(self.params.get("timeout_seconds", 120.0)),
                )
            except (GatewayError, PlanBuildError) as exc:
                return _fail(exc)

    @register_module(
        module_id=MODULE_TURN,
        version="1.0.0",
        category=CATEGORY,
        subcategory="motion",
        tags=["robot", "motion", "turn", "rotate"],
        label="Turn Robot",
        label_key="modules.robotics.turn.label",
        description="Turn the robot in place by an angle, then stop",
        description_key="modules.robotics.turn.description",
        icon="RotateCw",
        color=ICON_COLOR,
        input_types=["*"],
        output_types=["object"],
        can_receive_from=["*"],
        can_connect_to=["*"],
        timeout_ms=180000,
        retryable=False,
        concurrent_safe=False,
        requires_credentials=True,
        handles_sensitive_data=False,
    )
    class RoboticsTurn(base_module):
        module_id = MODULE_TURN
        module_name = "Turn Robot"
        module_description = "Turn in place, then stop safely"

        def validate_params(self) -> None:
            turn_plan(
                robot_id="validation-only",
                degrees=self.params.get("degrees", 90),
                angular_speed=self.params.get("angular_speed", 0.4),
                clockwise=bool(self.params.get("clockwise", False)),
            )

        def execute(self) -> dict[str, Any]:
            try:
                plan = turn_plan(
                    robot_id=robot_id(),
                    degrees=self.params.get("degrees", 90),
                    angular_speed=self.params.get("angular_speed", 0.4),
                    clockwise=bool(self.params.get("clockwise", False)),
                )
                return _dispatch(
                    plan,
                    wait=bool(self.params.get("wait", True)),
                    timeout_seconds=float(self.params.get("timeout_seconds", 120.0)),
                )
            except (GatewayError, PlanBuildError) as exc:
                return _fail(exc)

    @register_module(
        module_id=MODULE_STOP,
        version="1.0.0",
        category=CATEGORY,
        subcategory="motion",
        tags=["robot", "motion", "stop", "safety"],
        label="Stop Robot",
        label_key="modules.robotics.stop.label",
        description="Bring the robot to a safe stop and hold it",
        description_key="modules.robotics.stop.description",
        icon="Square",
        color="#F87171",
        input_types=["*"],
        output_types=["object"],
        can_receive_from=["*"],
        can_connect_to=["*"],
        timeout_ms=90000,
        retryable=True,
        concurrent_safe=False,
        requires_credentials=True,
        handles_sensitive_data=False,
    )
    class RoboticsStop(base_module):
        module_id = MODULE_STOP
        module_name = "Stop Robot"
        module_description = "Safe stop, held for a bounded time"

        def validate_params(self) -> None:
            stop_plan(robot_id="validation-only", seconds=self.params.get("seconds", 0.0))

        def execute(self) -> dict[str, Any]:
            try:
                plan = stop_plan(
                    robot_id=robot_id(), seconds=self.params.get("seconds", 0.0)
                )
                # A stop is always waited for. Reporting "sent" while a robot is
                # still moving is the one result nobody can act on.
                return _dispatch(plan, wait=True, timeout_seconds=90.0)
            except (GatewayError, PlanBuildError) as exc:
                return _fail(exc)

    return [
        (MODULE_MOVE, RoboticsMove),
        (MODULE_TURN, RoboticsTurn),
        (MODULE_STOP, RoboticsStop),
    ]
