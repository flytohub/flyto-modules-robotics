"""Canonical robotics capability requests emitted by workflow authoring nodes.

This module is the complete production authoring contract.  It has no ROS,
gateway, robot-runtime, Flyto2 Runtime, or legacy delivery-plan dependency.
Bounds are the intersection needed by the standard Generic ROS 2 adapter so a
request accepted here is not knowingly outside that adapter contract.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .steps import MODULE_MOVE, MODULE_STOP, MODULE_TURN

CAPABILITY_REQUEST_VERSION = "flyto.capability-request.v1"

CAPABILITY_ADVANCE = "motion.advance"
CAPABILITY_RETREAT = "motion.retreat"
CAPABILITY_ROTATE = "motion.rotate"
CAPABILITY_HALT = "motion.halt"

MIN_DISTANCE_M = 0.05
MAX_DISTANCE_M = 2.0
MIN_SPEED_MPS = 0.02
MAX_ADVANCE_SPEED_MPS = 0.25
MAX_RETREAT_SPEED_MPS = 0.20
DEFAULT_SPEED_MPS = 0.12
MIN_TURN_DEGREES = 1.0
MAX_TURN_DEGREES = 180.0

_MOVE_FIELDS = frozenset({"distance_m", "speed", "reverse"})
_TURN_FIELDS = frozenset({"degrees", "clockwise"})
_STOP_FIELDS = frozenset()


class CapabilityRequestError(ValueError):
    """Authored robotics parameters cannot become a canonical capability request."""


# Kept as a source-compatible exception name for callers that used the old
# authoring validation exception.  The retired plan module itself is removed.
PlanBuildError = CapabilityRequestError


def _reject_unknown(params: Mapping[str, Any], allowed: frozenset[str]) -> None:
    unknown = sorted(str(key) for key in params if key not in allowed)
    if unknown:
        raise CapabilityRequestError(
            "unsupported robotics parameter(s): " + ", ".join(unknown)
        )


def _number(value: Any, name: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CapabilityRequestError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise CapabilityRequestError(f"{name} must be finite")
    if number < minimum or number > maximum:
        raise CapabilityRequestError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return number


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise CapabilityRequestError(f"{name} must be a boolean")
    return value


def _resource(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CapabilityRequestError("a commanded resource is required")
    resource_id = value.strip()
    if len(resource_id) > 128:
        raise CapabilityRequestError(
            "commanded resource must be 128 characters or fewer"
        )
    return resource_id


def _move_request(
    params: Mapping[str, Any],
    resource_id: str,
) -> dict[str, Any]:
    _reject_unknown(params, _MOVE_FIELDS)
    if "distance_m" not in params:
        raise CapabilityRequestError("distance_m is required")
    reverse = _boolean(params.get("reverse", False), "reverse")
    capability_id = CAPABILITY_RETREAT if reverse else CAPABILITY_ADVANCE
    distance = _number(
        params["distance_m"],
        "distance_m",
        minimum=MIN_DISTANCE_M,
        maximum=MAX_DISTANCE_M,
    )
    speed_max = MAX_RETREAT_SPEED_MPS if reverse else MAX_ADVANCE_SPEED_MPS
    speed = _number(
        params.get("speed", DEFAULT_SPEED_MPS),
        "speed",
        minimum=MIN_SPEED_MPS,
        maximum=speed_max,
    )
    direction = "backward" if reverse else "forward"
    return {
        "contract_version": CAPABILITY_REQUEST_VERSION,
        "resource_id": resource_id,
        "capability_id": capability_id,
        "arguments": {
            "distance_m": distance,
            "speed_mps": speed,
        },
        "goal": f"move {direction} {distance:.2f} m then stop safely",
    }


def _turn_request(
    params: Mapping[str, Any],
    resource_id: str,
) -> dict[str, Any]:
    _reject_unknown(params, _TURN_FIELDS)
    if "degrees" not in params:
        raise CapabilityRequestError("degrees is required")
    clockwise = _boolean(params.get("clockwise", False), "clockwise")
    degrees = _number(
        params["degrees"],
        "degrees",
        minimum=MIN_TURN_DEGREES,
        maximum=MAX_TURN_DEGREES,
    )
    radians = math.radians(degrees)
    yaw = -radians if clockwise else radians
    direction = "right" if clockwise else "left"
    return {
        "contract_version": CAPABILITY_REQUEST_VERSION,
        "resource_id": resource_id,
        "capability_id": CAPABILITY_ROTATE,
        "arguments": {"yaw_radians": yaw},
        "goal": f"turn {direction} {degrees:.0f} degrees then stop safely",
    }


def _halt_request(
    params: Mapping[str, Any],
    resource_id: str,
) -> dict[str, Any]:
    _reject_unknown(params, _STOP_FIELDS)
    return {
        "contract_version": CAPABILITY_REQUEST_VERSION,
        "resource_id": resource_id,
        "capability_id": CAPABILITY_HALT,
        "arguments": {},
        "goal": "halt robot motion safely",
    }


def capability_request_for_step(
    module_id: Any,
    params: Mapping[str, Any] | None = None,
    *,
    resource_id: str,
) -> dict[str, Any] | None:
    """Translate one authored robotics node into a bounded capability request.

    Unknown module identifiers are not claimed.  Known robotics nodes fail
    closed on missing, unsupported, non-finite, or out-of-contract parameters.
    The request names commanded equipment only; execution-host selection remains
    an AI Space / War Room responsibility.
    """

    normalized = str(module_id or "").strip()
    if normalized not in {MODULE_MOVE, MODULE_TURN, MODULE_STOP}:
        return None

    commanded_resource = _resource(resource_id)
    values = params or {}
    if not isinstance(values, Mapping):
        raise CapabilityRequestError("robotics parameters must be an object")

    if normalized == MODULE_MOVE:
        return _move_request(values, commanded_resource)
    if normalized == MODULE_TURN:
        return _turn_request(values, commanded_resource)
    return _halt_request(values, commanded_resource)
