"""Canonical capability requests emitted by robotics workflow nodes.

This module is pure authoring/runtime contract code.  It never opens a socket,
imports ROS 2, names an execution computer, or knows how a robot is wired.

The execution host is selected by AI Space / War Room.  The resource named here
is only the commanded equipment.  A Generic ROS 2 Adapter running on that
external computer translates the capability request to standard ROS 2.
"""

from __future__ import annotations

from typing import Any, Mapping

from .plan import PlanBuildError
from .steps import MODULE_MOVE, MODULE_STOP, MODULE_TURN, preview_plan_for_step

CAPABILITY_REQUEST_VERSION = "flyto.capability-request.v1"

CAPABILITY_ADVANCE = "motion.advance"
CAPABILITY_RETREAT = "motion.retreat"
CAPABILITY_ROTATE = "motion.rotate"
CAPABILITY_HALT = "motion.halt"


def capability_request_for_step(
    module_id: Any,
    params: Mapping[str, Any] | None = None,
    *,
    resource_id: str,
) -> dict[str, Any] | None:
    """Translate one authored robotics node into a standard capability request.

    The legacy preview plan remains the single validation source for the
    existing Move/Turn/Stop canvas parameters.  None of its lower gateway
    vocabulary crosses this boundary.
    """

    normalized = str(module_id or "").strip()
    if normalized not in {MODULE_MOVE, MODULE_TURN, MODULE_STOP}:
        return None

    commanded_resource = str(resource_id or "").strip()
    if not commanded_resource:
        raise PlanBuildError("a commanded resource is required")

    preview = preview_plan_for_step(
        normalized,
        params or {},
        robot_id=commanded_resource,
    )
    if preview is None:  # pragma: no cover - guarded by the module-id set above
        return None

    if normalized == MODULE_MOVE:
        step = preview["steps"][0]
        distance = float(step["arguments"]["distance_m"])
        capability_id = CAPABILITY_RETREAT if distance < 0 else CAPABILITY_ADVANCE
        arguments = {
            "distance_m": abs(distance),
            "speed_mps": float(step["arguments"]["speed"]),
        }
    elif normalized == MODULE_TURN:
        step = preview["steps"][0]
        capability_id = CAPABILITY_ROTATE
        arguments = {
            "yaw_radians": float(step["arguments"]["yaw_delta_rad"]),
        }
    else:
        capability_id = CAPABILITY_HALT
        arguments = {}

    return {
        "contract_version": CAPABILITY_REQUEST_VERSION,
        "resource_id": commanded_resource,
        "capability_id": capability_id,
        "arguments": arguments,
        "goal": str(preview["goal"]),
    }
