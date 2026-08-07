# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""Which step means which plan — the one place that mapping lives.

Two very different callers need to answer the same question, "what does this
authored step actually ask the robot to do":

* the modules registered into ``flyto-core``, running on a worker or a
  desktop, which answer it to *declare* the motion;
* the robot's own job runner, running on a Pi with no execution engine at all,
  which answers it to *perform* the motion.

If each kept its own answer they would drift, and the drift would be silent
until a robot moved differently from what the canvas said. So the mapping
lives here, in a module that imports nothing but the plan builders beside it:
pure, no engine, no network, no clock. The Pi can import it; so can the
worker.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .plan import (
    DEFAULT_ANGULAR_SPEED,
    DEFAULT_SPEED_MPS,
    move_plan,
    stop_plan,
    turn_plan,
)

MODULE_MOVE = "robotics.move"
MODULE_TURN = "robotics.turn"
MODULE_STOP = "robotics.stop"

# The identifier a step carries when it is meant for a robot. Kept as a
# constant rather than spelled out at each call site, because "is this step
# ours" is a question three places ask.
NAMESPACE = "robotics."


# How far and how much are the author's to state; how fast and which way have
# safe defaults. A default distance or angle would be a robot moving an amount
# nobody chose, which is the one kind of default worth refusing to write.
def _move(params: Mapping[str, Any], robot_id: str) -> dict[str, Any]:
    return move_plan(
        robot_id=robot_id,
        distance_m=params.get("distance_m"),
        speed=params.get("speed", DEFAULT_SPEED_MPS),
        reverse=bool(params.get("reverse", False)),
    )


def _turn(params: Mapping[str, Any], robot_id: str) -> dict[str, Any]:
    return turn_plan(
        robot_id=robot_id,
        degrees=params.get("degrees"),
        angular_speed=params.get("angular_speed", DEFAULT_ANGULAR_SPEED),
        clockwise=bool(params.get("clockwise", False)),
    )


def _stop(params: Mapping[str, Any], robot_id: str) -> dict[str, Any]:
    return stop_plan(robot_id=robot_id, seconds=params.get("seconds", 0.0))


_BUILDERS: dict[str, Callable[[Mapping[str, Any], str], dict[str, Any]]] = {
    MODULE_MOVE: _move,
    MODULE_TURN: _turn,
    MODULE_STOP: _stop,
}

MODULE_IDS = tuple(_BUILDERS)


def is_robotics_step(module_id: Any) -> bool:
    """Whether this identifier is one of ours at all."""
    return str(module_id or "").strip() in _BUILDERS


def plan_for_step(
    module_id: Any,
    params: Mapping[str, Any] | None = None,
    *,
    robot_id: str,
) -> dict[str, Any] | None:
    """The plan an authored step describes, or None if the step is not ours.

    None rather than an exception for an unknown identifier: a caller sifting
    a job's steps for the ones it can carry out is asking a question, not
    making a mistake. A step that *is* ours but cannot be built — a distance
    out of bounds, a missing angle — still raises
    :class:`~flyto_modules_robotics.plan.PlanBuildError`, because that one is
    a fault in the workflow and silence would let it reach a robot.
    """
    builder = _BUILDERS.get(str(module_id or "").strip())
    if builder is None:
        return None
    return builder(params or {}, robot_id)


def step_module_id(step: Mapping[str, Any] | None) -> str:
    """The module a step names, under any of the keys a step may use.

    A step arrives spelled differently depending on who serialised it — the
    canvas, the plan contract, or a device job — and a reader that knew only
    one spelling would quietly treat the others as "not a robot step".
    """
    if not isinstance(step, Mapping):
        return ""
    for key in ("module", "module_id", "action", "type"):
        value = step.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
