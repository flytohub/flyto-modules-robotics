# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""What each robotics capability is, as data: parameters, bounds and contract.

One row per capability.  ``modules.py`` hands each row to flyto-core's
``@register_module``; nothing else in Flyto2 needs to know these rows exist.

Two sources of truth are mirrored here, and tests pin both:

* Parameters and bounds equal the flyto-robotics Generic ROS 2 adapter's
  ``generic_ros2_adapter.ARGUMENTS`` exactly.  A value outside them is refused,
  never clamped, so a step the builder accepts is never one the adapter is
  already known to reject.
* Evidence tolerances equal the constants Cloud has judged motion with since
  2026-10-02 (``services/space_tasks/motion_verification.py``), so moving them
  into a declared contract changes no verdict.

The contract shape is ``flyto.capability-contract.v1``; see flyto-core
``docs/CAPABILITY_CONTRACT.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

CONTRACT_SCHEMA = "flyto.capability-contract.v1"

MODULE_ADVANCE = "robotics.advance"
MODULE_RETREAT = "robotics.retreat"
MODULE_ROTATE = "robotics.rotate"
MODULE_HALT = "robotics.halt"
MODULE_NAVIGATE = "robotics.navigate"
MODULE_OBSERVE = "robotics.observe"
MODULE_MAP = "robotics.map"

CAPABILITY_ADVANCE = "motion.advance"
CAPABILITY_RETREAT = "motion.retreat"
CAPABILITY_ROTATE = "motion.rotate"
CAPABILITY_HALT = "motion.halt"
CAPABILITY_NAVIGATE = "motion.navigate"
CAPABILITY_OBSERVE = "vision.observe"
CAPABILITY_MAP = "sensing.map"

# Generic ROS 2 adapter bounds (flyto-robotics generic_ros2_adapter.ARGUMENTS).
MIN_DISTANCE_M = 0.05
MAX_DISTANCE_M = 2.0
MIN_SPEED_MPS = 0.02
MAX_ADVANCE_SPEED_MPS = 0.25
MAX_RETREAT_SPEED_MPS = 0.20
# The adapter's own defaults when speed_mps is omitted.
DEFAULT_ADVANCE_SPEED_MPS = 0.12
DEFAULT_RETREAT_SPEED_MPS = 0.10
MAX_YAW_RADIANS = math.pi
MAX_COORDINATE_M = 1000.0

# Cloud motion_verification.py constants, now declared by the provider.
DISTANCE_TOLERANCE_MIN_M = 0.03
DISTANCE_TOLERANCE_FRACTION = 0.3
HEADING_TOLERANCE_RAD = 0.15
ROTATION_TOLERANCE_MIN_RAD = 0.1
ROTATION_TOLERANCE_FRACTION = 0.2
ROTATION_POSITION_TOLERANCE_M = 0.05
SETTLE_TOLERANCE_M = 0.02


def _number(
    label: str,
    description: str,
    *,
    minimum: float,
    maximum: float,
    unit: str,
    required: bool,
    default: float | None = None,
) -> dict[str, Any]:
    field: dict[str, Any] = {
        "type": "number",
        "label": label,
        "description": description,
        "min": minimum,
        "max": maximum,
        "unit": unit,
        "required": required,
    }
    if default is not None:
        field["default"] = default
    return field


def _distance() -> dict[str, Any]:
    return _number(
        "Distance (m)",
        "Relative travel distance",
        minimum=MIN_DISTANCE_M,
        maximum=MAX_DISTANCE_M,
        unit="m",
        required=True,
    )


def _speed(maximum: float, default: float) -> dict[str, Any]:
    return _number(
        "Speed (m/s)",
        "Travel speed",
        minimum=MIN_SPEED_MPS,
        maximum=maximum,
        unit="m/s",
        required=False,
        default=default,
    )


def _yaw(required: bool, description: str) -> dict[str, Any]:
    return _number(
        "Yaw (rad)",
        description,
        minimum=-MAX_YAW_RADIANS,
        maximum=MAX_YAW_RADIANS,
        unit="rad",
        required=required,
    )


def _coordinate(axis: str) -> dict[str, Any]:
    return _number(
        f"{axis.upper()} (m)",
        f"Destination {axis} in the map frame",
        minimum=-MAX_COORDINATE_M,
        maximum=MAX_COORDINATE_M,
        unit="m",
        required=True,
    )


# Evidence the execution host reports as odometry poses at three phases.
_PHASES = ["before", "after", "settled"]


def _displacement_evidence(scale: int) -> list[dict[str, Any]]:
    return [
        {
            # Signed travel along the starting heading equals the commanded
            # distance (negative for a retreat), and the equipment stopped
            # moving once it was told to.  A sideways slide is not progress.
            "kind": "displacement",
            "observe": "pose",
            "phases": list(_PHASES),
            "measure": {"op": "along", "fields": ["x", "y"], "heading_field": "yaw"},
            "expect": {"argument": "distance_m", "scale": scale},
            "tolerance": {
                "absolute": DISTANCE_TOLERANCE_MIN_M,
                "relative": DISTANCE_TOLERANCE_FRACTION,
            },
            "settle": {"max_drift": SETTLE_TOLERANCE_M},
        },
        {
            # A straight move keeps its heading.
            "kind": "heading.hold",
            "observe": "pose",
            "phases": list(_PHASES),
            "measure": {"op": "abs_angle_delta", "fields": ["yaw"]},
            "expect": {"value": 0.0},
            "tolerance": {"absolute": HEADING_TOLERANCE_RAD, "relative": 0.0},
        },
    ]


def _rotation_evidence() -> list[dict[str, Any]]:
    return [
        {
            # Signed and wrapped: turning the wrong way is not a pass.
            "kind": "rotation",
            "observe": "pose",
            "phases": list(_PHASES),
            "measure": {"op": "angle_delta", "fields": ["yaw"]},
            "expect": {"argument": "yaw_radians", "scale": 1},
            "tolerance": {
                "absolute": ROTATION_TOLERANCE_MIN_RAD,
                "relative": ROTATION_TOLERANCE_FRACTION,
            },
        },
        {
            # Rotating in place does not travel, and it stops when told to.
            "kind": "position.drift",
            "observe": "pose",
            "phases": list(_PHASES),
            "measure": {"op": "distance", "fields": ["x", "y"]},
            "expect": {"value": 0.0},
            "tolerance": {"absolute": ROTATION_POSITION_TOLERANCE_M, "relative": 0.0},
            "settle": {"max_drift": SETTLE_TOLERANCE_M},
        },
    ]


def _contract(
    *,
    actuates: bool,
    safety_class: str,
    requires_safe_stop: bool,
    cancellable: bool,
    effects: list[str],
    requires: list[str],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": CONTRACT_SCHEMA,
        "actuates": actuates,
        "safety_class": safety_class,
        "requires_safe_stop": requires_safe_stop,
        "cancellable": cancellable,
        # The adapter keeps each call's result by call id, so a retry of the
        # same call returns the first result instead of moving again.
        "idempotent": True,
        "effects": effects,
        "requires": requires,
        "evidence": evidence,
    }


def _motion(evidence: list[dict[str, Any]], *, requires: list[str]) -> dict[str, Any]:
    return _contract(
        actuates=True,
        safety_class="movement",
        requires_safe_stop=True,
        cancellable=True,
        effects=["position.changed"],
        requires=requires,
        evidence=evidence,
    )


def _read_only() -> dict[str, Any]:
    return _contract(
        actuates=False,
        safety_class="read_only",
        requires_safe_stop=False,
        cancellable=False,
        effects=[],
        requires=[],
        evidence=[],
    )


# Preconditions the adapter checks before any motion: fresh odometry, and the
# robot's declared safety basis (LiDAR clearance, or a present operator).
_MOTION_REQUIRES = ["observation.fresh", "safety-basis.met"]


@dataclass(frozen=True)
class CapabilitySpec:
    """One capability, as registered: identity, display, parameters, contract."""

    module_id: str
    capability_id: str
    label: str
    description: str
    icon: str
    color: str
    tags: tuple[str, ...]
    params_schema: Mapping[str, Mapping[str, Any]]
    contract: Mapping[str, Any]
    timeout_ms: int
    retryable: bool

    @property
    def actuates(self) -> bool:
        return bool(self.contract["actuates"])


_MOTION_COLOR = "#22D3EE"
_STOP_COLOR = "#F87171"
_SENSE_COLOR = "#A78BFA"

SPECS: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        module_id=MODULE_ADVANCE,
        capability_id=CAPABILITY_ADVANCE,
        label="Advance",
        description="Move forward a bounded distance, then stop",
        icon="ArrowUp",
        color=_MOTION_COLOR,
        tags=("robot", "motion", "advance", "forward"),
        params_schema={
            "distance_m": _distance(),
            "speed_mps": _speed(MAX_ADVANCE_SPEED_MPS, DEFAULT_ADVANCE_SPEED_MPS),
        },
        contract=_motion(_displacement_evidence(1), requires=_MOTION_REQUIRES),
        timeout_ms=180000,
        retryable=False,
    ),
    CapabilitySpec(
        module_id=MODULE_RETREAT,
        capability_id=CAPABILITY_RETREAT,
        label="Retreat",
        description="Move backward a bounded distance, then stop",
        icon="ArrowDown",
        color=_MOTION_COLOR,
        tags=("robot", "motion", "retreat", "backward"),
        params_schema={
            "distance_m": _distance(),
            "speed_mps": _speed(MAX_RETREAT_SPEED_MPS, DEFAULT_RETREAT_SPEED_MPS),
        },
        contract=_motion(_displacement_evidence(-1), requires=_MOTION_REQUIRES),
        timeout_ms=180000,
        retryable=False,
    ),
    CapabilitySpec(
        module_id=MODULE_ROTATE,
        capability_id=CAPABILITY_ROTATE,
        label="Rotate",
        description="Rotate in place by a bounded angle, then stop",
        icon="RotateCw",
        color=_MOTION_COLOR,
        tags=("robot", "motion", "rotate", "turn"),
        params_schema={
            "yaw_radians": _yaw(True, "Signed rotation; positive turns left"),
        },
        contract=_motion(_rotation_evidence(), requires=_MOTION_REQUIRES),
        timeout_ms=180000,
        retryable=False,
    ),
    CapabilitySpec(
        module_id=MODULE_HALT,
        capability_id=CAPABILITY_HALT,
        label="Halt",
        description="Stop motion immediately",
        icon="Square",
        color=_STOP_COLOR,
        tags=("robot", "motion", "halt", "stop", "safety"),
        params_schema={},
        # Halt is the stop itself: it needs no safe stop and is not cancelled.
        contract=_contract(
            actuates=True,
            safety_class="controlled",
            requires_safe_stop=False,
            cancellable=False,
            effects=["motion.stopped"],
            requires=[],
            evidence=[],
        ),
        timeout_ms=90000,
        retryable=True,
    ),
    CapabilitySpec(
        module_id=MODULE_NAVIGATE,
        capability_id=CAPABILITY_NAVIGATE,
        label="Navigate",
        description="Travel to a map coordinate and arrive there",
        icon="Navigation",
        color=_MOTION_COLOR,
        tags=("robot", "motion", "navigate", "map"),
        params_schema={
            "x": _coordinate("x"),
            "y": _coordinate("y"),
            "yaw_radians": _yaw(False, "Heading to face on arrival"),
        },
        # Nav2 plans the path; the adapter requires LiDAR clearance and a
        # localised map for it, and refuses navigation on operator_present.
        contract=_motion(
            [], requires=["observation.fresh", "clearance.verified", "map.localized"]
        ),
        timeout_ms=360000,
        retryable=False,
    ),
    CapabilitySpec(
        module_id=MODULE_OBSERVE,
        capability_id=CAPABILITY_OBSERVE,
        label="Observe",
        description="Take one photo from the camera",
        icon="Camera",
        color=_SENSE_COLOR,
        tags=("robot", "vision", "camera", "photo"),
        params_schema={},
        contract=_read_only(),
        timeout_ms=90000,
        retryable=True,
    ),
    CapabilitySpec(
        module_id=MODULE_MAP,
        capability_id=CAPABILITY_MAP,
        label="Capture Map",
        description="Take the map built so far",
        icon="Map",
        color=_SENSE_COLOR,
        tags=("robot", "sensing", "map"),
        params_schema={},
        contract=_read_only(),
        timeout_ms=90000,
        retryable=True,
    ),
)

SPECS_BY_MODULE: Mapping[str, CapabilitySpec] = MappingProxyType(
    {spec.module_id: spec for spec in SPECS}
)
SPECS_BY_CAPABILITY: Mapping[str, CapabilitySpec] = MappingProxyType(
    {spec.capability_id: spec for spec in SPECS}
)
