"""Robotics authoring nodes for Flyto2 workflows.

These nodes produce bounded `flyto.capability-request.v1` requests for
commanded equipment.  They never import ROS, choose an execution host, or
construct an adapter.  If a trusted AI Space host injects an opaque capability
dispatcher, the same canonical request can be executed at the original workflow
step; otherwise the node remains declaration-only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .capability_request import (
    DEFAULT_SPEED_MPS,
    MAX_DISTANCE_M,
    MAX_RETREAT_SPEED_MPS,
    MAX_TURN_DEGREES,
    MIN_DISTANCE_M,
    MIN_SPEED_MPS,
    MIN_TURN_DEGREES,
    CapabilityRequestError,
    capability_request_for_step,
)
from .steps import MODULE_MOVE, MODULE_STOP, MODULE_TURN

__all__ = ["MODULE_MOVE", "MODULE_STOP", "MODULE_TURN", "build_modules"]

CATEGORY = "robotics"
ICON_COLOR = "#22D3EE"

# Internal Core ABI for an opaque host-created authority.  The spelling predates
# the host-neutral architecture; Flyto2 Runtime is not required.
HOST_DISPATCHER_CONTEXT_KEY = "_flyto_runtime_external_capability_dispatcher"

MOVE_PARAMS_SCHEMA = {
    "distance_m": {
        "type": "number",
        "label": "Distance (m)",
        "description": "Bounded travel distance",
        "min": MIN_DISTANCE_M,
        "max": MAX_DISTANCE_M,
        "required": True,
    },
    "speed": {
        "type": "number",
        "label": "Speed (m/s)",
        "description": "Conservative speed valid for forward and reverse motion",
        "default": DEFAULT_SPEED_MPS,
        "min": MIN_SPEED_MPS,
        "max": MAX_RETREAT_SPEED_MPS,
        "required": False,
    },
    "reverse": {
        "type": "boolean",
        "label": "Reverse",
        "description": "Move backward instead of forward",
        "default": False,
        "required": False,
    },
}

TURN_PARAMS_SCHEMA = {
    "degrees": {
        "type": "number",
        "label": "Angle (degrees)",
        "description": "Bounded in-place rotation angle",
        "min": MIN_TURN_DEGREES,
        "max": MAX_TURN_DEGREES,
        "required": True,
    },
    "clockwise": {
        "type": "boolean",
        "label": "Clockwise",
        "description": "Rotate right instead of left",
        "default": False,
        "required": False,
    },
}

STOP_PARAMS_SCHEMA: dict[str, Any] = {}


def _declare(request: dict[str, Any]) -> dict[str, Any]:
    """Return desired work without selecting or contacting an execution host."""

    return {
        "dispatched": False,
        "commanded_resource": request["resource_id"],
        "goal": request["goal"],
        "capability_request": request,
    }


def _refuse(exc: Exception) -> dict[str, Any]:
    """Return a bounded authoring failure instead of raising through a workflow."""

    return {
        "dispatched": False,
        "commanded_resource": "",
        "error": str(exc)[:300],
    }


async def _dispatch_or_declare(step: Any, request: dict[str, Any]) -> dict[str, Any]:
    """Execute only through opaque authority supplied by the selected host."""

    dispatcher = step.context.get(HOST_DISPATCHER_CONTEXT_KEY)
    if dispatcher is None:
        return _declare(request)
    if (
        getattr(dispatcher, "_flyto_runtime_opaque", False) is not True
        or not callable(getattr(dispatcher, "invoke", None))
    ):
        raise RuntimeError("untrusted external capability dispatcher")

    record = await dispatcher.invoke(request)
    outcome = str(record.get("outcome") or "") if isinstance(record, Mapping) else ""
    if outcome != "completed":
        detail = str(
            record.get("detail") or outcome or "external capability failed"
        )[:300]
        return {
            "ok": False,
            "error": detail,
            "error_code": "EXTERNAL_CAPABILITY_FAILED",
            "dispatched": True,
            "commanded_resource": request["resource_id"],
        }
    return {
        "ok": True,
        "dispatched": True,
        "commanded_resource": request["resource_id"],
        "goal": request["goal"],
        "capability_request": request,
        "execution": dict(record),
    }


def _resource_id(step: Any) -> str:
    """Resolve commanded equipment, never the computer executing the workflow."""

    named = str(
        step.params.get("resource_id") or step.params.get("robot_id") or ""
    ).strip()
    return named or str(step.context.get("resource_id", "")).strip()


def _request_for(
    module_id: str,
    params: Mapping[str, Any],
    resource_id: str,
) -> dict[str, Any]:
    request = capability_request_for_step(
        module_id,
        params,
        resource_id=resource_id,
    )
    if request is None:  # pragma: no cover - declarations and ids are co-owned
        raise CapabilityRequestError(
            f"no robotics capability request is defined for {module_id}"
        )
    return request


def _validate_params(module_id: str, params: Mapping[str, Any]) -> None:
    """Validate canvas parameters against the production request contract."""

    _request_for(module_id, params, "validation-only")


def _request_from_step(step: Any, module_id: str) -> dict[str, Any]:
    return _request_for(module_id, step.params, _resource_id(step))


def build_modules(base_module, register_module) -> list[tuple[str, type]]:
    """Define the three optional builder modules against flyto-core's API.

    `provides_capability` is intentionally unset.  These are authoring nodes,
    not resource providers, and Move may request either `motion.advance` or
    `motion.retreat` depending on its parameters.  Resource admission therefore
    follows the emitted canonical request, not misleading singular registry
    metadata.
    """

    @register_module(
        module_id=MODULE_MOVE,
        version="2.0.0",
        category=CATEGORY,
        subcategory="motion",
        tags=["robot", "motion", "move", "drive"],
        label="Move Robot",
        label_key="modules.robotics.move.label",
        description="Move commanded equipment a bounded distance, then stop",
        description_key="modules.robotics.move.description",
        icon="MoveVertical",
        color=ICON_COLOR,
        input_types=["*"],
        output_types=["object"],
        can_receive_from=["*"],
        can_connect_to=["*"],
        params_schema=MOVE_PARAMS_SCHEMA,
        timeout_ms=180000,
        retryable=False,
        concurrent_safe=False,
        requires_credentials=False,
        handles_sensitive_data=False,
    )
    class RoboticsMove(base_module):
        module_id = MODULE_MOVE
        module_name = "Move Robot"
        module_description = "Move a bounded distance, then stop safely"

        def validate_params(self) -> None:
            _validate_params(MODULE_MOVE, self.params)

        async def execute(self) -> dict[str, Any]:
            try:
                request = _request_from_step(self, MODULE_MOVE)
            except (CapabilityRequestError, ValueError) as exc:
                return _refuse(exc)
            return await _dispatch_or_declare(self, request)

    @register_module(
        module_id=MODULE_TURN,
        version="2.0.0",
        category=CATEGORY,
        subcategory="motion",
        tags=["robot", "motion", "turn", "rotate"],
        label="Turn Robot",
        label_key="modules.robotics.turn.label",
        description="Rotate commanded equipment in place by a bounded angle",
        description_key="modules.robotics.turn.description",
        icon="RotateCw",
        color=ICON_COLOR,
        input_types=["*"],
        output_types=["object"],
        can_receive_from=["*"],
        can_connect_to=["*"],
        params_schema=TURN_PARAMS_SCHEMA,
        timeout_ms=180000,
        retryable=False,
        concurrent_safe=False,
        requires_credentials=False,
        handles_sensitive_data=False,
    )
    class RoboticsTurn(base_module):
        module_id = MODULE_TURN
        module_name = "Turn Robot"
        module_description = "Rotate in place by a bounded angle"

        def validate_params(self) -> None:
            _validate_params(MODULE_TURN, self.params)

        async def execute(self) -> dict[str, Any]:
            try:
                request = _request_from_step(self, MODULE_TURN)
            except (CapabilityRequestError, ValueError) as exc:
                return _refuse(exc)
            return await _dispatch_or_declare(self, request)

    @register_module(
        module_id=MODULE_STOP,
        version="2.0.0",
        category=CATEGORY,
        subcategory="motion",
        tags=["robot", "motion", "stop", "safety"],
        label="Stop Robot",
        label_key="modules.robotics.stop.label",
        description="Command equipment to halt motion safely",
        description_key="modules.robotics.stop.description",
        icon="Square",
        color="#F87171",
        input_types=["*"],
        output_types=["object"],
        can_receive_from=["*"],
        can_connect_to=["*"],
        params_schema=STOP_PARAMS_SCHEMA,
        timeout_ms=90000,
        retryable=True,
        concurrent_safe=False,
        requires_credentials=False,
        handles_sensitive_data=False,
    )
    class RoboticsStop(base_module):
        module_id = MODULE_STOP
        module_name = "Stop Robot"
        module_description = "Halt motion safely"

        def validate_params(self) -> None:
            _validate_params(MODULE_STOP, self.params)

        async def execute(self) -> dict[str, Any]:
            try:
                request = _request_from_step(self, MODULE_STOP)
            except (CapabilityRequestError, ValueError) as exc:
                return _refuse(exc)
            return await _dispatch_or_declare(self, request)

    return [
        (MODULE_MOVE, RoboticsMove),
        (MODULE_TURN, RoboticsTurn),
        (MODULE_STOP, RoboticsStop),
    ]
