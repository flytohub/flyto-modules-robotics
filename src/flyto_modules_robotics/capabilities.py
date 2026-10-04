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
* Navigation arrival tolerances follow the robot's own Nav2 goal checker
  (see ``NAVIGATE_POSITION_TOLERANCE_M``): a contract never accepts an end
  pose Nav2 itself would not have accepted, plus a small margin.

The contract shape is ``flyto.capability-contract.v1``; see flyto-core
``docs/CAPABILITY_CONTRACT.md``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

CONTRACT_SCHEMA = "flyto.capability-contract.v1"

MODULE_ADVANCE = "robotics.advance"
MODULE_RETREAT = "robotics.retreat"
MODULE_ROTATE = "robotics.rotate"
MODULE_HALT = "robotics.halt"
MODULE_NAVIGATE = "robotics.navigate"
MODULE_OBSERVE = "robotics.observe"
MODULE_MAP = "robotics.map"
MODULE_PLACES = "robotics.places"
MODULE_MARK_PLACE = "robotics.mark_place"

CAPABILITY_ADVANCE = "motion.advance"
CAPABILITY_RETREAT = "motion.retreat"
CAPABILITY_ROTATE = "motion.rotate"
CAPABILITY_HALT = "motion.halt"
CAPABILITY_NAVIGATE = "motion.navigate"
CAPABILITY_OBSERVE = "vision.observe"
CAPABILITY_MAP = "sensing.map"
CAPABILITY_PLACES = "places.list"
CAPABILITY_MARK_PLACE = "places.mark"

# The fleet pack: the same contract, driven through flyto-robotics'
# Open-RMF adapter (``open_rmf.fleet``). The commanded resource is a fleet.
MODULE_FLEET_NAVIGATE = "fleet.navigate"
MODULE_FLEET_DOCK = "fleet.dock"
MODULE_FLEET_LOAD = "fleet.load"
MODULE_FLEET_UNLOAD = "fleet.unload"

# Not ``motion.navigate``: a single robot's navigate takes a map coordinate and
# needs a localised map and LiDAR; a fleet's takes a waypoint and has no stop
# of its own. Two contracts under one capability id are ambiguous to a
# contract host (flyto-core fails closed on them), so the fleet's has its own.
CAPABILITY_NAVIGATE_TO_WAYPOINT = "motion.navigate_to_waypoint"
CAPABILITY_DOCK = "motion.dock"
CAPABILITY_LOAD = "transport.load"
CAPABILITY_UNLOAD = "transport.unload"

# Keys flyto-core 2.36.0 added to the contract. An older core's closed schema
# rejects them, so ``modules.py`` registers without them there.
OPTIONAL_CONTRACT_KEYS = frozenset(("role", "artifacts", "recovery", "expected_duration_ms"))
# Measure ops flyto-core 2.38.0 added (with ``measure.frame``). An older core
# rejects an evidence item using them, so ``modules.py`` registers without
# that item there.
ABSOLUTE_MEASURE_OPS = frozenset(("distance_to", "angle_to"))

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

# What a capture returns (flyto-robotics adapter MAX_PHOTO_BYTES; the map is
# drawn from at most 4,000,000 cells).
MAX_PHOTO_BYTES = 2_000_000
MAX_MAP_PICTURE_BYTES = 8 * 1024 * 1024
# A waypoint on an Open-RMF fleet's shared map.
MAX_WAYPOINT_LENGTH = 128
# An Open-RMF task's deadline: a fleet robot may queue behind others first.
FLEET_TASK_MS = 600_000

# Cloud motion_verification.py constants, now declared by the provider.
DISTANCE_TOLERANCE_MIN_M = 0.03
DISTANCE_TOLERANCE_FRACTION = 0.3
HEADING_TOLERANCE_RAD = 0.15
ROTATION_TOLERANCE_MIN_RAD = 0.1
ROTATION_TOLERANCE_FRACTION = 0.2
ROTATION_POSITION_TOLERANCE_M = 0.05
SETTLE_TOLERANCE_M = 0.02

# Navigation arrival, judged in the map frame the goal is given in.
#
# Nav2's goal checker decides SUCCEEDED from the same map pose: the robot and
# its twin run turtlebot3_navigation2's burger.yaml unchanged
# (``goal_checker: xy_goal_tolerance 0.25, yaw_goal_tolerance 0.25``; read
# from the twin's live parameters 2026-10-04), and this repository's lab
# config (flyto-robotics ``config/nav2_params.yaml``) is tighter, 0.20 / 0.25.
# The contract allows the loosest of those plus 0.05: the map pose is
# odometry composed with localization's map->odom correction, which moves by
# a few centimetres between Nav2's last check and the settled observation.
# Nothing Nav2 itself would refuse is accepted; a SUCCEEDED that left the
# robot 0.63 m short (twin, 2026-10-04) is not an arrival.
NAV2_XY_GOAL_TOLERANCE_M = 0.25
NAV2_YAW_GOAL_TOLERANCE_RAD = 0.25
ARRIVAL_MARGIN_M = 0.05
ARRIVAL_MARGIN_RAD = 0.05
NAVIGATE_POSITION_TOLERANCE_M = NAV2_XY_GOAL_TOLERANCE_M + ARRIVAL_MARGIN_M
NAVIGATE_HEADING_TOLERANCE_RAD = NAV2_YAW_GOAL_TOLERANCE_RAD + ARRIVAL_MARGIN_RAD
# The adapter reports the pose in the map frame as ``map_pose``
# (``{"frame": "map", "x", "y", "yaw"}``, flyto-robotics 03be416), only while
# localization's transform is fresh; odometry stays ``pose``.
MAP_POSE_OBSERVATION = "map_pose"
MAP_FRAME = "map"

# Named places (flyto-robotics 0.3.0 ``places.py``): kept on the execution
# host beside the adapter, never on the robot and never in Cloud. A name is
# free text of at most this many characters.
MAX_PLACE_NAME_LENGTH = 64
# What ``places.list`` returns as a contract artifact: the list as JSON. The
# adapter keeps at most 200 places per map, well inside this.
PLACES_ARTIFACT_KIND = "places"
PLACES_MEDIA_TYPE = "application/json"
MAX_PLACES_BYTES = 256 * 1024
# A navigation by place reports, from the adapter, the x, y and yaw_radians the
# place resolved to. They are the call's arguments for its arrival evidence:
# a host judges ``arrival`` against the authored arguments overlaid with these.
RESOLVED_ARGUMENTS = "resolved_arguments"
PLACE_EFFECT = "places.written"


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
    # Not required on its own: a navigation names x and y, or a place.
    return _number(
        f"{axis.upper()} (m)",
        f"Destination {axis} in the map frame (with the other coordinate, instead of a place)",
        minimum=-MAX_COORDINATE_M,
        maximum=MAX_COORDINATE_M,
        unit="m",
        required=False,
    )


def _place(description: str, *, required: bool) -> dict[str, Any]:
    return {
        "type": "string",
        "label": "Place",
        "description": description,
        "minLength": 1,
        "maxLength": MAX_PLACE_NAME_LENGTH,
        "required": required,
    }


def _waypoint() -> dict[str, Any]:
    return {
        "type": "string",
        "label": "Waypoint",
        "description": "A named waypoint on the fleet's shared map",
        "minLength": 1,
        "maxLength": MAX_WAYPOINT_LENGTH,
        "required": True,
    }


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


def _arrival_evidence() -> list[dict[str, Any]]:
    """Where a navigation ended, against where it was sent, in the map frame.

    Measured once the robot settled; the start is not read. A Nav2 SUCCEEDED
    is the adapter's word, not this proof.
    """
    return [
        {
            "kind": "arrival",
            "observe": MAP_POSE_OBSERVATION,
            "phases": ["after", "settled"],
            "measure": {"op": "distance_to", "fields": ["x", "y"], "frame": MAP_FRAME},
            "expect": {"arguments": {"x": "x", "y": "y"}},
            "tolerance": {"absolute": NAVIGATE_POSITION_TOLERANCE_M, "relative": 0.0},
        },
        {
            # Facing the asked heading, when one was asked.
            "kind": "arrival.heading",
            "observe": MAP_POSE_OBSERVATION,
            "phases": ["after", "settled"],
            "measure": {"op": "angle_to", "fields": ["yaw"], "frame": MAP_FRAME},
            "expect": {"argument": "yaw_radians", "optional": True},
            "tolerance": {"absolute": NAVIGATE_HEADING_TOLERANCE_RAD, "relative": 0.0},
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
    **optional: Any,
) -> dict[str, Any]:
    contract = {
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
    unknown = set(optional) - OPTIONAL_CONTRACT_KEYS
    if unknown:  # pragma: no cover - a typo in this table
        raise ValueError(f"unknown contract keys: {sorted(unknown)}")
    contract.update(optional)
    return contract


def _motion(
    evidence: list[dict[str, Any]], *, requires: list[str], **optional: Any
) -> dict[str, Any]:
    return _contract(
        actuates=True,
        safety_class="movement",
        requires_safe_stop=True,
        cancellable=True,
        effects=["position.changed"],
        requires=requires,
        evidence=evidence,
        **optional,
    )


def _read_only(**optional: Any) -> dict[str, Any]:
    return _contract(
        actuates=False,
        safety_class="read_only",
        requires_safe_stop=False,
        cancellable=False,
        effects=[],
        requires=[],
        evidence=[],
        **optional,
    )


def _fleet_task(effects: list[str]) -> dict[str, Any]:
    """An Open-RMF task: the fleet's dispatcher picks the robot.

    ``requires_safe_stop`` is false because it cannot be honoured: Open-RMF has
    no fleet-wide stop, and the adapter refuses ``safe_stop`` rather than claim
    every machine is at rest. A machine is stopped on its own path
    (``robotics.halt``). Cancelling withdraws the task by the id RMF gave it.
    The call waits for RMF's terminal task state, so the deadline is long.
    """
    return _contract(
        actuates=True,
        safety_class="movement",
        requires_safe_stop=False,
        cancellable=True,
        effects=effects,
        requires=["fleet.dispatcher-reachable"],
        evidence=[],
        expected_duration_ms=FLEET_TASK_MS,
    )


# Preconditions the adapter checks before any motion: fresh odometry, and the
# robot's declared safety basis (LiDAR clearance, or a present operator).
_MOTION_REQUIRES = ["observation.fresh", "safety-basis.met"]

# What a planner may use instead after a straight motion stops short, and how.
# The adapter reports ``recovery_context`` (flyto-robotics 0.2.0): why it
# stopped, how far it went, and the LiDAR sweep at the stop; ``recovery.py``
# turns that into nearest-return sectors for the planner.
DETOUR_CAPABILITIES = [CAPABILITY_ROTATE, CAPABILITY_ADVANCE, CAPABILITY_RETREAT]
RECOVERY_OBSERVATION = "recovery_context"
DETOUR_GUIDANCE = (
    "If it stopped because something was in the way (reason obstacle_blocked), go "
    "round on the side whose sector shows more room: turn 90 degrees "
    "(yaw_radians 1.5708 left, -1.5708 right), go far enough to clear it, turn "
    "back, go past it, return to the original line and go the remaining distance. "
    "Keep every move at least 0.35 m short of anything in its way or the robot "
    "refuses it. At most 8 moves. If no side has room, stop and say why."
)


def _detour() -> dict[str, Any]:
    return {
        "capabilities": list(DETOUR_CAPABILITIES),
        "observe": RECOVERY_OBSERVATION,
        "guidance": DETOUR_GUIDANCE,
    }


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
        contract=_motion(
            _displacement_evidence(1), requires=_MOTION_REQUIRES, recovery=_detour()
        ),
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
        contract=_motion(
            _displacement_evidence(-1), requires=_MOTION_REQUIRES, recovery=_detour()
        ),
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
        # Halt is the stop itself: it needs no safe stop and is not cancelled,
        # and a host runs it at once, with no approval queue.
        contract=_contract(
            actuates=True,
            safety_class="controlled",
            requires_safe_stop=False,
            cancellable=False,
            effects=["motion.stopped"],
            requires=[],
            evidence=[],
            role="safe_stop",
        ),
        timeout_ms=90000,
        retryable=True,
    ),
    CapabilitySpec(
        module_id=MODULE_NAVIGATE,
        capability_id=CAPABILITY_NAVIGATE,
        label="Navigate",
        description="Travel to a map coordinate or a named place and arrive there",
        icon="Navigation",
        color=_MOTION_COLOR,
        tags=("robot", "motion", "navigate", "map", "place"),
        # Exactly one target: x and y (heading optional), or a place, which
        # carries its own heading (``capability_request.navigate_target``).
        params_schema={
            "x": _coordinate("x"),
            "y": _coordinate("y"),
            "yaw_radians": _yaw(False, "Heading to face on arrival (with x and y only)"),
            "place": _place(
                "A named place saved on this robot's map, instead of x and y",
                required=False,
            ),
        },
        # Nav2 plans the path; the adapter requires LiDAR clearance and a
        # localised map for it, and refuses navigation on operator_present.
        # A place is resolved by the adapter before anything moves; the
        # arrival is judged against the coordinates it resolved to
        # (``RESOLVED_ARGUMENTS``).
        contract=_motion(
            _arrival_evidence(),
            requires=["observation.fresh", "clearance.verified", "map.localized"],
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
        contract=_read_only(
            artifacts=[
                {"kind": "photo", "media_types": ["image/jpeg"], "max_bytes": MAX_PHOTO_BYTES}
            ]
        ),
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
        # Drawn by the adapter: JPEG where Pillow is installed, PNG otherwise.
        contract=_read_only(
            artifacts=[
                {
                    "kind": "map",
                    "media_types": ["image/jpeg", "image/png"],
                    "max_bytes": MAX_MAP_PICTURE_BYTES,
                }
            ]
        ),
        timeout_ms=90000,
        retryable=True,
    ),
    CapabilitySpec(
        module_id=MODULE_PLACES,
        capability_id=CAPABILITY_PLACES,
        label="Places",
        description="List the named places saved on this robot's map",
        icon="MapPin",
        color=_SENSE_COLOR,
        tags=("robot", "map", "place", "places"),
        params_schema={},
        # The list comes back as an artifact of kind "places", which a host
        # keeps and can cite when a plan names a place.
        contract=_read_only(
            artifacts=[
                {
                    "kind": PLACES_ARTIFACT_KIND,
                    "media_types": [PLACES_MEDIA_TYPE],
                    "max_bytes": MAX_PLACES_BYTES,
                }
            ]
        ),
        timeout_ms=30000,
        retryable=True,
    ),
    CapabilitySpec(
        module_id=MODULE_MARK_PLACE,
        capability_id=CAPABILITY_MARK_PLACE,
        label="Mark Place",
        description="Save the robot's current map position under a name",
        icon="MapPinPlus",
        color=_SENSE_COLOR,
        tags=("robot", "map", "place", "mark"),
        params_schema={"place": _place("The name to save the current position under", required=True)},
        # Writes the host's places file; nothing moves. The adapter keeps the
        # result by call id, so a retry does not save wherever the robot is now.
        contract=_contract(
            actuates=False,
            safety_class="controlled",
            requires_safe_stop=False,
            cancellable=False,
            effects=[PLACE_EFFECT],
            requires=["map.localized"],
            evidence=[],
        ),
        timeout_ms=30000,
        retryable=True,
    ),
)

_FLEET_COLOR = "#34D399"


def _fleet_spec(
    module_id: str, capability_id: str, label: str, description: str, icon: str,
    tags: tuple[str, ...], effects: list[str],
) -> CapabilitySpec:
    return CapabilitySpec(
        module_id=module_id,
        capability_id=capability_id,
        label=label,
        description=description,
        icon=icon,
        color=_FLEET_COLOR,
        tags=("fleet", "open-rmf", *tags),
        params_schema={"waypoint": _waypoint()},
        contract=_fleet_task(effects),
        timeout_ms=FLEET_TASK_MS,
        retryable=False,
    )


# The fleet pack (entry point ``fleet``): Open-RMF plans between named places,
# so every step takes a waypoint, never a distance or a robot.
FLEET_SPECS: tuple[CapabilitySpec, ...] = (
    _fleet_spec(
        MODULE_FLEET_NAVIGATE, CAPABILITY_NAVIGATE_TO_WAYPOINT, "Fleet Navigate",
        "Send a fleet robot, picked by the fleet, to a named waypoint",
        "Navigation", ("motion", "navigate"), ["position.changed"],
    ),
    _fleet_spec(
        MODULE_FLEET_DOCK, CAPABILITY_DOCK, "Fleet Dock",
        "Send a fleet robot to a docking waypoint",
        "BatteryCharging", ("motion", "dock"), ["position.changed"],
    ),
    _fleet_spec(
        MODULE_FLEET_LOAD, CAPABILITY_LOAD, "Fleet Load",
        "Have a fleet robot collect a payload at a named waypoint",
        "PackagePlus", ("transport", "load"), ["position.changed", "payload.loaded"],
    ),
    _fleet_spec(
        MODULE_FLEET_UNLOAD, CAPABILITY_UNLOAD, "Fleet Unload",
        "Have a fleet robot deliver a payload at a named waypoint",
        "PackageCheck", ("transport", "unload"), ["position.changed", "payload.unloaded"],
    ),
)

SPECS_BY_MODULE: Mapping[str, CapabilitySpec] = MappingProxyType(
    {spec.module_id: spec for spec in SPECS}
)
SPECS_BY_CAPABILITY: Mapping[str, CapabilitySpec] = MappingProxyType(
    {spec.capability_id: spec for spec in SPECS}
)
FLEET_SPECS_BY_MODULE: Mapping[str, CapabilitySpec] = MappingProxyType(
    {spec.module_id: spec for spec in FLEET_SPECS}
)
# Every step either pack registers, by module id.
ALL_SPECS_BY_MODULE: Mapping[str, CapabilitySpec] = MappingProxyType(
    {**SPECS_BY_MODULE, **FLEET_SPECS_BY_MODULE}
)
