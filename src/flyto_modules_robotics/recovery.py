# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""What a planner is told when a straight motion stops short.

The advance and retreat contracts declare ``recovery``: the capabilities a
planner may use instead (rotate, advance, retreat), the observation that
explains the failure (``recovery_context``), and guidance text. The adapter
reports the facts in ``recovery_context`` (flyto-robotics 0.2.0): why the
motion ended, how far it was asked to go and went, and the LiDAR sweep at the
stop. This module turns them into what the planner reads: the nearest return
in each sector of the robot's own view.

This is the detour logic Flyto2 Cloud ran itself until now
(``services/space_tasks/detour.py``), moved to the pack that owns the
capabilities, so a host passes the step's ``recovery`` to its planner and
contains no robot geometry. Pure: no ROS, no network, no flyto-core.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .capabilities import CAPABILITY_RETREAT, CapabilitySpec

RECOVERY_SCHEMA = "flyto.robotics.recovery.v1"

# Sectors of the robot's own view, degrees from straight ahead, left positive.
SECTORS: tuple[tuple[str, float, float], ...] = (
    ("ahead", -20.0, 20.0),
    ("ahead-left", 20.0, 70.0),
    ("left", 70.0, 110.0),
    ("ahead-right", -70.0, -20.0),
    ("right", -110.0, -70.0),
    ("behind", 160.0, 200.0),
)

# Outcomes after which a planner may try the declared recovery. A refusal never
# moved and a cancellation was somebody's decision.
RECOVERABLE_OUTCOMES = frozenset({"failed", "timeout"})


def sector_clearance(sweep: Any) -> dict[str, float | None]:
    """Nearest return per sector of a robot-frame sweep, or None when unseen."""
    nearest: dict[str, float | None] = {name: None for name, _, _ in SECTORS}
    if not isinstance(sweep, Mapping):
        return nearest
    try:
        start = float(sweep["angle_min_rad"])
        step = float(sweep["angle_increment_rad"])
        ranges = list(sweep["ranges_m"])
    except (KeyError, TypeError, ValueError):
        return nearest
    for index, distance in enumerate(ranges):
        if not isinstance(distance, (int, float)) or isinstance(distance, bool):
            continue
        if not math.isfinite(distance):
            continue
        angle = start + index * step
        degrees = math.degrees(math.atan2(math.sin(angle), math.cos(angle)))
        for name, low, high in SECTORS:
            shifted = degrees + 360.0 if high > 180.0 and degrees < 0 else degrees
            if low <= shifted <= high and (nearest[name] is None or distance < nearest[name]):
                nearest[name] = round(float(distance), 2)
    return nearest


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _along(start: Any, end: Any) -> float | None:
    if not isinstance(start, Mapping) or not isinstance(end, Mapping):
        return None
    values = [_number(start.get(key)) for key in ("x", "y", "yaw")]
    values += [_number(end.get(key)) for key in ("x", "y")]
    if None in values:
        return None
    x0, y0, yaw, x1, y1 = values
    return (x1 - x0) * math.cos(yaw) + (y1 - y0) * math.sin(yaw)


def _facts(capability_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    """The adapter's ``recovery_context``, or the same facts from an older one.

    An adapter before flyto-robotics 0.2.0 reports ``motion_outcome`` only:
    the distances are recovered from it, and the sectors stay unseen.
    """
    reported = evidence.get("recovery_context")
    if isinstance(reported, Mapping):
        return dict(reported)
    outcome = evidence.get("motion_outcome")
    if not isinstance(outcome, Mapping):
        return {}
    requested = _number(outcome.get("requested_distance_m"))
    along = _along(outcome.get("start_pose"), outcome.get("final_pose"))
    travelled = None
    if along is not None:
        travelled = round(max(0.0, -along if capability_id == CAPABILITY_RETREAT else along), 4)
    return {
        "reason": outcome.get("reason"),
        "requested_distance_m": requested,
        "travelled_m": travelled,
        "remaining_m": (
            round(max(0.0, requested - travelled), 4)
            if requested is not None and travelled is not None
            else None
        ),
        "minimum_range_at_stop_m": outcome.get("minimum_range_at_stop_m"),
        "clearance_floor_m": outcome.get("clearance_floor_m"),
    }


def recovery_for(spec: CapabilitySpec, record: Mapping[str, Any]) -> dict[str, Any] | None:
    """What the planner may do next after this step's call stopped short.

    None when the capability declares no recovery or the call did not fail
    or time out. The declared capabilities and guidance come from the
    contract; the measurements come from the adapter's own report.
    """
    declared = spec.contract.get("recovery")
    if not isinstance(declared, Mapping):
        return None
    if str(record.get("outcome") or "") not in RECOVERABLE_OUTCOMES:
        return None
    evidence = record.get("adapter_evidence")
    facts = _facts(spec.capability_id, evidence if isinstance(evidence, Mapping) else {})
    return {
        "schema": RECOVERY_SCHEMA,
        "capability_id": spec.capability_id,
        "capabilities": list(declared["capabilities"]),
        "guidance": declared.get("guidance", ""),
        "observe": declared.get("observe", ""),
        "context": {
            "reason": str(facts.get("reason") or ""),
            "requested_distance_m": facts.get("requested_distance_m"),
            "travelled_m": facts.get("travelled_m"),
            "remaining_m": facts.get("remaining_m"),
            "minimum_range_at_stop_m": facts.get("minimum_range_at_stop_m"),
            "clearance_floor_m": facts.get("clearance_floor_m"),
            # Where the robot was going, in the sectors below.
            "travel_sector": "behind" if spec.capability_id == CAPABILITY_RETREAT else "ahead",
            # Nearest return by direction from where the robot now faces
            # (metres; None means nothing seen in that sector).
            "sectors": sector_clearance(facts.get("sweep")),
        },
    }


__all__ = [
    "RECOVERABLE_OUTCOMES",
    "RECOVERY_SCHEMA",
    "SECTORS",
    "recovery_for",
    "sector_clearance",
]
