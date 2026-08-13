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
from typing import Any, Mapping

from .plan import PlanBuildError, run_request
from .steps import MODULE_MOVE, MODULE_STOP, MODULE_TURN, preview_plan_for_step

# Re-exported for callers that used to read these here. The identifiers now
# live beside the mapping that gives them meaning, in steps.py.
__all__ = ["MODULE_MOVE", "MODULE_TURN", "MODULE_STOP", "build_modules"]

CATEGORY = "robotics"
ICON_COLOR = "#22D3EE"

# What each step asks a device to be able to do, named in the registry's own
# vocabulary and versioned so a device declaring an older contract is a
# mismatch the builder can see rather than a robot that moves unexpectedly.
# One capability per step, and no two steps share one: the mapping is how a
# device's declared abilities are matched to an authored step, so a duplicate
# would make two different motions indistinguishable at match time.
#
# These name the *contract*, not the plan's internal step names. The plan
# builders in plan.py emit the bare capability verbs ("move_relative",
# "safe_stop") into the plan the gateway executes; these identifiers are what
# the registry matches a device against. The two are deliberately separate --
# renaming a registry contract must not silently change the bytes a robot runs.
CAPABILITY_MOVE = "robotics.motion.move_relative@1"
CAPABILITY_TURN = "robotics.motion.turn_relative@1"
CAPABILITY_STOP = "robotics.safety.safe_stop@1"


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


def _robot_id(step: Any) -> str:
    """Which robot this step is for: the one it names, else the one it reached.

    A workflow that names no robot is the normal case and the useful one — the
    same authored steps then run on whichever device the job was dispatched to,
    which is what lets five identical robots share one workflow.
    """
    named = str(step.params.get("robot_id") or "").strip()
    return named or str(step.context.get("resource_id", ""))


def _plan_from_params(module_id: str, params: Mapping[str, Any], robot_id: str) -> dict[str, Any]:
    """The plan this step describes, built by the mapping in steps.py.

    Both halves of the product ask the same question of the same table: this
    module, to declare the motion, and the robot's own runner, to perform it.
    Spelling the builder call out here as well would be a second answer, free
    to drift from the first without anything failing until a robot moved
    differently from what the canvas said.
    """
    plan = preview_plan_for_step(module_id, params, robot_id=robot_id)
    if plan is None:  # pragma: no cover - the table and the classes are one file apart
        raise PlanBuildError(f"no plan is defined for {module_id}")
    return plan


# flyto-core awaits execute() (core/modules/base.py: `return await self.execute()`),
# so these must be coroutines. They were plain functions, and every one of the
# 36 tests passed anyway because the stand-in base class in test_registration.py
# calls .execute() synchronously — the engine's own contract was never in the
# room. Against a real installed flyto-core the step died with "object dict
# can't be used in 'await' expression", which is not a failure a workflow author
# can act on.
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
        provides_capability=CAPABILITY_MOVE,
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
            _plan_from_params(MODULE_MOVE, self.params, "validation-only")

        async def execute(self) -> dict[str, Any]:
            try:
                plan = _plan_from_params(MODULE_MOVE, self.params, _robot_id(self))
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
        provides_capability=CAPABILITY_TURN,
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
            _plan_from_params(MODULE_TURN, self.params, "validation-only")

        async def execute(self) -> dict[str, Any]:
            try:
                plan = _plan_from_params(MODULE_TURN, self.params, _robot_id(self))
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
        provides_capability=CAPABILITY_STOP,
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
            _plan_from_params(MODULE_STOP, self.params, "validation-only")

        async def execute(self) -> dict[str, Any]:
            try:
                plan = _plan_from_params(MODULE_STOP, self.params, _robot_id(self))
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
