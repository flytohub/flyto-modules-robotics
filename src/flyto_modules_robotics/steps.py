# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""Legacy preview/trusted-plan mapping for the three authoring nodes.

Production module execution now translates Move / Turn / Stop to canonical
Flyto2 capability requests in `capability_request.py`. The plan mapping remains
the validation/preview source and preserves historical Gazebo/downstream
compatibility while that old delivery path is retired.

If each kept its own answer they would drift, and the drift would be silent
until a robot moved differently from what the canvas said. So the mapping
lives here, in a module that imports nothing but the plan builders beside it:
pure, no engine, no network, no clock. The Pi can import it; so can the
worker.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

from .catalog import Capability, CapabilityCatalog
from .plan import (
    DEFAULT_ANGULAR_SPEED,
    DEFAULT_SPEED_MPS,
    PlanBuildError,
    _plan,
    _timeout_for,
    move_plan,
    stop_plan,
    turn_plan,
)

MODULE_MOVE = "robotics.move"
MODULE_TURN = "robotics.turn"
MODULE_STOP = "robotics.stop"

_CATALOG_CAPABILITIES = {
    MODULE_MOVE: "robotics.motion.move_relative@1",
    MODULE_TURN: "robotics.motion.turn_relative@1",
    MODULE_STOP: "robotics.safety.safe_stop@1",
}
_CATALOG_RUNTIMES = {
    MODULE_MOVE: "move_relative",
    MODULE_TURN: "turn_relative",
    MODULE_STOP: "safe_stop",
}

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
        reverse=params.get("reverse", False),
    )


def _turn(params: Mapping[str, Any], robot_id: str) -> dict[str, Any]:
    return turn_plan(
        robot_id=robot_id,
        degrees=params.get("degrees"),
        angular_speed=params.get("angular_speed", DEFAULT_ANGULAR_SPEED),
        clockwise=params.get("clockwise", False),
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
    """Build the legacy offline preview plan for an authored step.

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


def _catalog_capability(catalog: CapabilityCatalog, module_id: str) -> Capability:
    wanted = _CATALOG_CAPABILITIES[module_id]
    capability = catalog.capability(wanted)
    if capability is None:
        raise PlanBuildError(f"trusted catalog does not provide {wanted}")
    runtime = _CATALOG_RUNTIMES[module_id]
    if capability.runtime_name != runtime or catalog.runtime(runtime) is not capability:
        raise PlanBuildError(f"trusted catalog runtime is incompatible with {module_id}")
    return capability


def _require_known_arguments(
    capability: Capability, known: set[str]
) -> None:
    unknown_required = {
        str(schema["name"])
        for schema in capability.arguments
        if schema["name"] not in known and schema["required"]
    }
    if unknown_required:
        raise PlanBuildError("trusted catalog has unsupported required arguments")


def _catalog_safe_stop(catalog: CapabilityCatalog, seconds: Any) -> dict[str, Any]:
    stop = _catalog_capability(catalog, MODULE_STOP)
    if stop.requires_safe_stop:
        raise PlanBuildError("trusted safe_stop catalog is incompatible")
    _require_known_arguments(stop, {"seconds"})
    schema = _number_schema(
        stop, "seconds", required=False, require_default=seconds is _MISSING
    )
    hold = schema["default"] if seconds is _MISSING else seconds
    hold = _catalog_number(schema, "seconds", hold)
    return {
        "step_id": "stop.finish",
        "capability": stop.runtime_name,
        "arguments": {"seconds": hold},
        "timeout_seconds": _timeout_for(max(hold, 1.0)),
        "on_failure": "abort",
    }


def _number_schema(
    capability: Capability,
    name: str,
    *,
    required: bool,
    require_default: bool = False,
) -> Mapping[str, Any]:
    schema = capability.argument(name)
    if (
        schema is None
        or schema.get("type") != "number"
        or "minimum" not in schema
        or "maximum" not in schema
        or schema.get("required") is not required
        or (require_default and "default" not in schema)
        or (required and "default" in schema)
    ):
        raise PlanBuildError(f"trusted catalog argument {name} is incompatible")
    return schema


def _catalog_number(
    schema: Mapping[str, Any], name: str, value: Any
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanBuildError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise PlanBuildError(f"{name} must be finite")
    minimum = float(schema["minimum"])
    maximum = float(schema["maximum"])
    if number < minimum:
        raise PlanBuildError(f"{name} is below the trusted catalog minimum")
    if number > maximum:
        raise PlanBuildError(f"{name} is above the trusted catalog maximum")
    return number


def _parameter(params: Mapping[str, Any], name: str, schema: Mapping[str, Any]) -> Any:
    if name in params:
        return params[name]
    if "default" not in schema:
        raise PlanBuildError(f"{name} is required by the trusted catalog")
    return schema["default"]


def _boolean_parameter(params: Mapping[str, Any], name: str) -> bool:
    value = params.get(name, False)
    if not isinstance(value, bool):
        raise PlanBuildError(f"{name} must be a boolean")
    return value


_MISSING = object()
_MAPPING_PROXY = type(MappingProxyType({}))


def _is_immutable_catalog(catalog: object) -> bool:
    """Whether a catalog has the recursively frozen parser projection."""
    if type(catalog) is not CapabilityCatalog or type(catalog.capabilities) is not tuple:
        return False
    for capability in catalog.capabilities:
        if type(capability) is not Capability:
            return False
        if any(
            type(values) is not tuple
            for values in (
                capability.required_observations,
                capability.required_resources,
                capability.required_permissions,
                capability.arguments,
            )
        ):
            return False
        for argument in capability.arguments:
            if type(argument) is not _MAPPING_PROXY:
                return False
            condition = argument.get("required_when")
            if condition is not None and type(condition) is not _MAPPING_PROXY:
                return False
    return True


def _trusted_plan(
    module_id: str,
    params: Mapping[str, Any],
    robot_id: str,
    catalog: CapabilityCatalog,
) -> dict[str, Any]:
    capability = _catalog_capability(catalog, module_id)
    if module_id == MODULE_MOVE:
        if not capability.requires_safe_stop:
            raise PlanBuildError("trusted move catalog must require a safe stop")
        stop = _catalog_safe_stop(catalog, 0.0)
        _require_known_arguments(capability, {"distance_m", "speed"})
        distance_schema = _number_schema(capability, "distance_m", required=True)
        speed_schema = _number_schema(
            capability, "speed", required=False, require_default=True
        )
        distance = _parameter(params, "distance_m", distance_schema)
        if isinstance(distance, bool) or not isinstance(distance, (int, float)):
            raise PlanBuildError("distance_m must be a number")
        distance = float(distance)
        if not math.isfinite(distance):
            raise PlanBuildError("distance_m must be finite")
        if distance <= 0:
            raise PlanBuildError("distance_m must be greater than zero")
        reverse = _boolean_parameter(params, "reverse")
        signed_distance = -distance if reverse else distance
        _catalog_number(distance_schema, "distance_m", signed_distance)
        speed = _catalog_number(
            speed_schema, "speed", _parameter(params, "speed", speed_schema)
        )
        if speed <= 0:
            raise PlanBuildError("speed must be greater than zero")
        direction = "backward" if reverse else "forward"
        plan = _plan(
            plan_id=f"workflow.move.{direction}.{round(distance * 100)}cm.v1",
            robot_id=robot_id,
            goal=f"move {direction} {distance:.2f} m then stop safely",
            steps=[{
                "step_id": f"move.{direction}",
                "capability": capability.runtime_name,
                "arguments": {"distance_m": signed_distance, "speed": speed},
                "timeout_seconds": _timeout_for(distance / speed),
                "on_failure": "abort",
            }], safe_stop_step=stop,
        )
        return plan

    if module_id == MODULE_TURN:
        if not capability.requires_safe_stop:
            raise PlanBuildError("trusted turn catalog must require a safe stop")
        stop = _catalog_safe_stop(catalog, 0.0)
        _require_known_arguments(capability, {"yaw_delta_rad", "angular_speed"})
        yaw_schema = _number_schema(capability, "yaw_delta_rad", required=True)
        speed_schema = _number_schema(
            capability, "angular_speed", required=False, require_default=True
        )
        degrees = params.get("degrees")
        if isinstance(degrees, bool) or not isinstance(degrees, (int, float)):
            raise PlanBuildError("degrees must be a number")
        degrees = float(degrees)
        if not math.isfinite(degrees):
            raise PlanBuildError("degrees must be finite")
        if degrees <= 0:
            raise PlanBuildError("degrees must be greater than zero")
        clockwise = _boolean_parameter(params, "clockwise")
        radians = degrees * math.pi / 180.0
        yaw = -radians if clockwise else radians
        _catalog_number(yaw_schema, "yaw_delta_rad", yaw)
        speed = _catalog_number(
            speed_schema,
            "angular_speed", _parameter(params, "angular_speed", speed_schema),
        )
        if speed <= 0:
            raise PlanBuildError("angular_speed must be greater than zero")
        direction = "right" if clockwise else "left"
        plan = _plan(
            plan_id=f"workflow.turn.{direction}.{round(degrees)}deg.v1",
            robot_id=robot_id,
            goal=f"turn {direction} {degrees:.0f} degrees then stop safely",
            steps=[{
                "step_id": f"turn.{direction}",
                "capability": capability.runtime_name,
                "arguments": {"yaw_delta_rad": yaw, "angular_speed": speed},
                "timeout_seconds": _timeout_for(radians / speed),
                "on_failure": "abort",
            }], safe_stop_step=stop,
        )
        return plan

    stop = _catalog_safe_stop(
        catalog, params.get("seconds", _MISSING)
    )
    seconds = stop["arguments"]["seconds"]
    plan = _plan(
        plan_id="workflow.stop.v1",
        robot_id=robot_id,
        goal=f"hold a safe stop for {seconds:.1f} s",
        steps=[], safe_stop_step=stop,
    )
    plan["steps"][-1]["arguments"]["seconds"] = seconds
    plan["steps"][-1]["timeout_seconds"] = _timeout_for(max(seconds, 1.0))
    return plan


def trusted_plan_for_step(
    module_id: Any,
    params: Mapping[str, Any] | None = None,
    *,
    robot_id: str,
    catalog: CapabilityCatalog | None = None,
) -> dict[str, Any] | None:
    """Build the legacy catalog-derived delivery plan.

    This is retained for simulation/downstream compatibility while production
    workflow modules emit `flyto.capability-request.v1` for an external adapter.
    All legacy runtime names, bounds, defaults and the appended stop remain
    derived from the validated immutable lower catalog.
    """
    normalized = str(module_id or "").strip()
    if normalized not in _BUILDERS:
        return None
    if not _is_immutable_catalog(catalog):
        raise PlanBuildError("a trusted capability catalog is required")
    return _trusted_plan(normalized, params or {}, robot_id, catalog)


preview_plan_for_step = plan_for_step


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
