"""The workflow steps this package adds to the builder.

A step here *declares* motion; it never performs it. These modules register into
flyto-core, and flyto-core runs on the worker and the desktop — not on the
robot. A step that drove hardware from here would be reaching for a gateway on
the wrong machine: the loopback address meaning "this robot" on a Pi means "this
container" on a worker, and the request would either fail or find something else
listening.

So a step builds a plan, names the device that must carry it out, and returns it
as the payload the robot's own runner reads from its job. Driving stays on the
robot, behind the gateway that owns the final stop.

flyto-core is imported inside :func:`build_modules`, never at module scope, so
``plan`` stays importable — and testable — where flyto-core is absent.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .plan import PlanBuildError, move_plan, run_request, stop_plan, turn_plan

MODULE_MOVE = "robotics.move"
MODULE_TURN = "robotics.turn"
MODULE_STOP = "robotics.stop"

CATEGORY = "robotics"
ICON_COLOR = "#22D3EE"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _declare(plan: dict[str, Any], *, resource_id: str) -> dict[str, Any]:
    """Say what this step wants done, without doing it.

    These modules register into flyto-core, and flyto-core runs on the worker
    and the desktop — not on the robot. A step that drove hardware from here
    would be reaching for a gateway on the wrong machine: the loopback address
    that means "this robot" on a Pi means "this container" on a worker, and the
    request would either fail or, worse, find something else listening.

    So the step declares. It builds the plan, names the device that must carry
    it out, and returns it as the job payload the robot's own runner reads. The
    driving stays where the robot is, behind the gateway that owns the final
    stop.
    """
    return {
        "dispatched": False,
        "requires_device": resource_id,
        "plan_id": plan["plan_id"],
        "goal": plan["goal"],
        "request": run_request(
            plan,
            request_id=f"wf-{uuid.uuid4().hex[:12]}",
            requested_at=_now_iso(),
        ),
    }


def _refuse(exc: Exception) -> dict[str, Any]:
    """A step that cannot even be described is a workflow fault, reported."""
    return {
        "dispatched": False,
        "requires_device": "",
        "error": str(exc)[:300],
    }


def build_modules(base_module, register_module) -> list[tuple[str, type]]:
    """Define the module classes against whatever flyto-core provides.

    The base class and decorator are passed in rather than imported so this
    function has no import-time dependency on flyto-core, and so a test can
    exercise the classes against a stand-in.
    """

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
                    robot_id=str(self.params.get("robot_id") or "").strip()
                    or self.context.get("resource_id", ""),
                    distance_m=self.params.get("distance_m", 0.4),
                    speed=self.params.get("speed", 0.12),
                    reverse=bool(self.params.get("reverse", False)),
                )
            except (PlanBuildError, ValueError) as exc:
                return _refuse(exc)
            return _declare(
                plan, resource_id=str(self.context.get("resource_id", "")),
            )


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
                    robot_id=str(self.params.get("robot_id") or "").strip()
                    or self.context.get("resource_id", ""),
                    degrees=self.params.get("degrees", 90),
                    angular_speed=self.params.get("angular_speed", 0.4),
                    clockwise=bool(self.params.get("clockwise", False)),
                )
            except (PlanBuildError, ValueError) as exc:
                return _refuse(exc)
            return _declare(
                plan, resource_id=str(self.context.get("resource_id", "")),
            )


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
                    robot_id=str(self.params.get("robot_id") or "").strip()
                    or self.context.get("resource_id", ""),
                    seconds=self.params.get("seconds", 0.0),
                )
            except (PlanBuildError, ValueError) as exc:
                return _refuse(exc)
            return _declare(
                plan, resource_id=str(self.context.get("resource_id", "")),
            )


    return [
        (MODULE_MOVE, RoboticsMove),
        (MODULE_TURN, RoboticsTurn),
        (MODULE_STOP, RoboticsStop),
    ]
