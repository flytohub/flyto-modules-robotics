"""The workflow steps this package adds to the builder.

A step here declares desired motion; it never performs it. The module executes
on a normal Flyto2 computer and emits a standard capability request naming the
*commanded resource*. It does not choose the execution host and it never talks
to the robot.

AI Space / War Room owns placement of the execution computer. A Generic ROS 2
Adapter on that computer translates the request to standard ROS 2. The robot
therefore needs no Flyto2 package, credential, runner or gateway.

flyto-core is imported inside :func:`build_modules`, never at module scope, so
the pure authoring contract remains importable where flyto-core is absent.
"""

from __future__ import annotations

from typing import Any, Mapping

from .capability_request import capability_request_for_step
from .plan import PlanBuildError
from .steps import MODULE_MOVE, MODULE_STOP, MODULE_TURN, preview_plan_for_step

# Re-exported for callers that used to read these here. The identifiers now
# live beside the mapping that gives them meaning, in steps.py.
__all__ = ["MODULE_MOVE", "MODULE_TURN", "MODULE_STOP", "build_modules"]

CATEGORY = "robotics"
ICON_COLOR = "#22D3EE"

# What each step asks a device to be able to do, named in flyto-core's
# registry vocabulary. Registry identifiers deliberately omit the catalog's
# ``@1`` revision suffix: flyto-core accepts only its safe bounded identifier
# grammar here, while the execution catalog owns revisioned capability IDs.
# One capability per step, and no two steps share one: the mapping is how a
# device's declared abilities are matched to an authored step, so a duplicate
# would make two different motions indistinguishable at match time.
#
# These remain the builder-plugin registration identifiers for backward
# compatibility. They are not the physical execution vocabulary. Runtime
# requests emitted below use the canonical Space capability ids:
# motion.advance / motion.retreat / motion.rotate / motion.halt.
CAPABILITY_MOVE = "robotics.motion.move_relative"
CAPABILITY_TURN = "robotics.motion.turn_relative"
CAPABILITY_STOP = "robotics.safety.safe_stop"


def _declare(request: dict[str, Any]) -> dict[str, Any]:
    """Return desired work without selecting or contacting an execution host."""
    return {
        "dispatched": False,
        "commanded_resource": request["resource_id"],
        "goal": request["goal"],
        "capability_request": request,
    }


def _refuse(exc: Exception) -> dict[str, Any]:
    """A step that cannot even be described is a workflow fault, reported."""
    return {
        "dispatched": False,
        "commanded_resource": "",
        "error": str(exc)[:300],
    }


def _resource_id(step: Any) -> str:
    """The equipment being commanded, never the computer executing the workflow.

    `resource_id` is canonical. `robot_id` remains an input alias for
    already-authored workflows; neither value is an adapter address or an
    execution-host selector.
    """
    named = str(
        step.params.get("resource_id") or step.params.get("robot_id") or ""
    ).strip()
    return named or str(step.context.get("resource_id", "")).strip()


def _validate_params(module_id: str, params: Mapping[str, Any]) -> None:
    """Validate existing canvas parameters without producing executable work."""
    plan = preview_plan_for_step(module_id, params, robot_id="validation-only")
    if plan is None:  # pragma: no cover - classes and mapping are defined together
        raise PlanBuildError(f"no robotics capability request is defined for {module_id}")


def _request_from_step(step: Any, module_id: str) -> dict[str, Any]:
    request = capability_request_for_step(
        module_id,
        step.params,
        resource_id=_resource_id(step),
    )
    if request is None:  # pragma: no cover - classes and mapping are defined together
        raise PlanBuildError(f"no robotics capability request is defined for {module_id}")
    return request


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
        requires_credentials=False,
        handles_sensitive_data=False,
    )
    class RoboticsMove(base_module):
        module_id = MODULE_MOVE
        module_name = "Move Robot"
        module_description = "Drive a fixed distance, then stop safely"

        def validate_params(self) -> None:
            _validate_params(MODULE_MOVE, self.params)

        async def execute(self) -> dict[str, Any]:
            try:
                request = _request_from_step(self, MODULE_MOVE)
            except (PlanBuildError, ValueError) as exc:
                return _refuse(exc)
            return _declare(request)


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
        requires_credentials=False,
        handles_sensitive_data=False,
    )
    class RoboticsTurn(base_module):
        module_id = MODULE_TURN
        module_name = "Turn Robot"
        module_description = "Turn in place, then stop safely"

        def validate_params(self) -> None:
            _validate_params(MODULE_TURN, self.params)

        async def execute(self) -> dict[str, Any]:
            try:
                request = _request_from_step(self, MODULE_TURN)
            except (PlanBuildError, ValueError) as exc:
                return _refuse(exc)
            return _declare(request)


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
        requires_credentials=False,
        handles_sensitive_data=False,
    )
    class RoboticsStop(base_module):
        module_id = MODULE_STOP
        module_name = "Stop Robot"
        module_description = "Safe stop, held for a bounded time"

        def validate_params(self) -> None:
            _validate_params(MODULE_STOP, self.params)

        async def execute(self) -> dict[str, Any]:
            try:
                request = _request_from_step(self, MODULE_STOP)
            except (PlanBuildError, ValueError) as exc:
                return _refuse(exc)
            return _declare(request)


    return [
        (MODULE_MOVE, RoboticsMove),
        (MODULE_TURN, RoboticsTurn),
        (MODULE_STOP, RoboticsStop),
    ]
