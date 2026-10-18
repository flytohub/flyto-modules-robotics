# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""What an HMI shows for a ROS 2 mobile robot (``flyto.resource-presentation.v1``).

The pack declares WHAT is shown; Cloud passes the block through unchanged
(schema-validated, size-capped) and the App renders it through one generic
panel registry. Nothing here names a widget: panels are generic kinds
(``gauge``, ``readout``, ``progress``, ``position2d``, ``state``, ``alert``)
over sources the robot resource really carries:

* the live channels the flyto-robotics ROS 2 runtime (0.8.0,
  ``live_telemetry``) declares on its manifest and samples once a second --
  ``power.battery``, ``pose.planar`` and ``nav.goal`` with the fields in
  :data:`ROBOT_CHANNEL_FIELDS` (both repos pin that table in their tests);
* the ``connection`` channel, declared on every adapter-backed manifest by
  the execution host (flyto-cloud ``local/resource_connection_telemetry.py``)
  with ``state`` in :data:`CONNECTION_STATES`;
* the resource's own ``presence.state`` and ``deployment_mode``;
* whether a capability of this pack is currently offered (``capability``).

The block is an optional manifest extension (:data:`PRESENTATION_EXTENSION`).
The runtime builds the manifest, so it finds this block through the entry
point ``robotics`` in group ``flyto2.resource_presentations`` and adds it only
when the host asks; neither package imports the other.
:func:`manifest_with_presentation` is the same rule for any other caller.

The schema is vendored byte-identical from the copy flyto-cloud validates
with (``services/device/schemas``); its sha256 is pinned in the tests, and so
is the canonical sha256 of the block below.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Mapping
from importlib import resources
from types import MappingProxyType
from typing import Any

from .capabilities import CAPABILITY_NAVIGATE, CAPABILITY_OBSERVE

PRESENTATION_SCHEMA = "flyto.resource-presentation.v1"
PRESENTATION_EXTENSION = "presentation"
SCHEMA_RESOURCE = "schemas/flyto.resource-presentation.v1.schema.json"
MAX_CANONICAL_BYTES = 16_384

#: The host-declared link channel and its ``state`` vocabulary (flyto-cloud
#: ``CONNECTION_CHANNEL_DECLARATION``). Mirrored here; the tests pin it.
CONNECTION_CHANNEL = "connection"
CONNECTION_STATES = ("connected", "reconnecting", "failed", "stopped")

#: Equipment presence as Cloud derives it (``services.device.equipment_presence``).
PRESENCE_STATES = ("online", "unreachable", "unreported", "offline", "dormant", "never_connected")

#: The manifest's ``deployment_mode`` values (flyto-robotics ``adapter_provider``).
DEPLOYMENT_MODES = ("real", "simulation")

#: The robot runtime's live channels and the payload fields each one fills
#: (flyto-robotics ``live_telemetry.CHANNELS``). Mirrored; the tests pin it.
BATTERY_CHANNEL = "power.battery"
POSE_CHANNEL = "pose.planar"
NAVIGATION_CHANNEL = "nav.goal"
ROBOT_CHANNEL_FIELDS = MappingProxyType({
    BATTERY_CHANNEL: frozenset({"percent", "voltage_v"}),
    POSE_CHANNEL: frozenset({
        "x", "y", "heading_deg", "frame", "goal_x", "goal_y",
        "view_x_min", "view_x_max", "view_y_min", "view_y_max",
    }),
    NAVIGATION_CHANNEL: frozenset({"state", "distance_m", "progress_pct", "goal_x", "goal_y", "reason"}),
})
NAVIGATION_STATES = ("idle", "navigating", "arrived", "blocked", "cancelled", "failed")


def _label(zh: str, en: str) -> dict[str, str]:
    return {"zh-TW": zh, "en": en}


_CONNECTION_STATE = {"channel": CONNECTION_CHANNEL, "field": "state"}

# Each option: (value, zh-TW, en, icon, tone). Icons are names the App's
# generic icon table knows (flyto-app ``resource_visuals.dart``).
_PRESENCE_OPTIONS = (
    ("online", "在線", "Online", "active", "live"),
    ("unreachable", "無法連線", "Unreachable", "warning", "attention"),
    ("unreported", "未回報", "Not reported", "warning", "attention"),
    ("offline", "離線", "Offline", "stopped", "neutral"),
    ("dormant", "休眠", "Dormant", "idle", "neutral"),
    ("never_connected", "尚未連線", "Never connected", "idle", "neutral"),
)
_CONNECTION_OPTIONS = (
    ("connected", "已連線", "Connected", "done", "verified"),
    ("reconnecting", "重新連線中", "Reconnecting", "warning", "attention"),
    ("failed", "連線失敗", "Link failed", "error", "refused"),
    ("stopped", "已停止", "Stopped", "stopped", "neutral"),
)
_MODE_OPTIONS = (
    ("real", "實機", "Hardware", "power", "live"),
    ("simulation", "模擬", "Simulation", "idle", "neutral"),
)
_NAVIGATE_OPTIONS = (
    (True, "可導航", "Available", "moving", "verified"),
    (False, "無法導航", "Unavailable", "stopped", "neutral"),
)
_CAMERA_OPTIONS = (
    (True, "可拍照", "Available", "done", "verified"),
    (False, "無法拍照", "Unavailable", "stopped", "neutral"),
)
_NAVIGATION_STATE_OPTIONS = (
    ("idle", "待命", "Idle", "idle", "neutral"),
    ("navigating", "導航中", "Navigating", "moving", "running"),
    ("arrived", "已抵達", "Arrived", "done", "verified"),
    ("blocked", "路徑受阻", "Blocked", "warning", "attention"),
    ("cancelled", "已取消", "Cancelled", "stopped", "neutral"),
    ("failed", "未完成", "Did not finish", "error", "refused"),
)
#: ``pose.planar.frame``: ``map`` while localization's transform is fresh,
#: else ``odom`` (dead reckoning only, so a map goal is not trustworthy).
POSE_FRAMES = ("map", "odom")
_FRAME_OPTIONS = (
    ("map", "已定位（地圖）", "Localized (map)", "location", "verified"),
    ("odom", "僅里程計", "Odometry only", "warning", "attention"),
)

#: What the robot can be asked to do first, in the person's words. The App
#: shows them as chips that only fill the request field (Cloud schema
#: ``request_examples``, at most 4, 64 characters each); nothing is sent until
#: the person sends it. They are the Proof #1 tasks: move, stop if blocked,
#: photograph; then report.
REQUEST_EXAMPLES = (
    ("前進 1 公尺，遇到障礙就停下，然後拍照", "Drive 1 m forward, stop if blocked, then take a photo"),
    ("拍一張前方的照片", "Take a photo of what is ahead"),
    ("回報目前的電量和位置", "Report the battery and position"),
    ("停下來", "Stop now"),
)


def _field(channel: str, name: str) -> dict[str, str]:
    return {"channel": channel, "field": name}


_NAVIGATING = {"source": _field(NAVIGATION_CHANNEL, "state"), "in": ["navigating"]}

# The live value panels, one complete row each (they differ by kind, so each
# row is the panel itself). Order is layout order: the hero first.
_VALUE_PANELS: tuple[dict[str, Any], ...] = (
    {
        "id": "goal_distance", "kind": "readout", "label": _label("距離目標", "Distance to goal"),
        "source": _field(NAVIGATION_CHANNEL, "distance_m"), "unit": "m", "precision": 2,
        "priority": "hero", "when": _NAVIGATING,
    },
    {
        "id": "goal_progress", "kind": "progress", "label": _label("導航進度", "Progress"),
        "source": _field(NAVIGATION_CHANNEL, "progress_pct"), "unit": "%", "precision": 0,
        "range": {"min": 0, "max": 100}, "priority": "primary", "when": _NAVIGATING,
    },
    {
        "id": "battery", "kind": "gauge", "label": _label("電量", "Battery"),
        "source": _field(BATTERY_CHANNEL, "percent"), "unit": "%", "precision": 0,
        "range": {"min": 0, "max": 100}, "priority": "primary",
        "severity_map": [{"when": {"lt": 10}, "tone": "refused"}, {"when": {"lt": 20}, "tone": "attention"}],
    },
    {
        "id": "position", "kind": "position2d", "label": _label("位置", "Position"),
        "unit": "m", "precision": 2, "priority": "primary",
        "x": _field(POSE_CHANNEL, "x"), "y": _field(POSE_CHANNEL, "y"),
        "heading": _field(POSE_CHANNEL, "heading_deg"),
        "goal_x": _field(POSE_CHANNEL, "goal_x"), "goal_y": _field(POSE_CHANNEL, "goal_y"),
        "plane": {
            "x": {"min": _field(POSE_CHANNEL, "view_x_min"), "max": _field(POSE_CHANNEL, "view_x_max")},
            "y": {"min": _field(POSE_CHANNEL, "view_y_min"), "max": _field(POSE_CHANNEL, "view_y_max")},
        },
    },
    {
        "id": "heading", "kind": "readout", "label": _label("車頭方向", "Heading"),
        "source": _field(POSE_CHANNEL, "heading_deg"), "unit": "°", "precision": 0,
        "priority": "secondary",
    },
    {
        "id": "voltage", "kind": "readout", "label": _label("電池電壓", "Battery voltage"),
        "source": _field(BATTERY_CHANNEL, "voltage_v"), "unit": "V", "precision": 1,
        "priority": "secondary",
    },
)

# The state panels, one row each: (id, zh-TW, en, source, priority, options).
_STATE_PANELS = (
    ("presence", "機器人狀態", "Robot status", {"resource": "presence.state"}, "hero", _PRESENCE_OPTIONS),
    (
        "navigation_state", "導航狀態", "Navigation status",
        _field(NAVIGATION_CHANNEL, "state"), "primary", _NAVIGATION_STATE_OPTIONS,
    ),
    ("connection", "連線", "Link", _CONNECTION_STATE, "primary", _CONNECTION_OPTIONS),
    ("localization", "定位", "Localization", _field(POSE_CHANNEL, "frame"), "primary", _FRAME_OPTIONS),
    ("navigate", "導航", "Navigation", {"capability": CAPABILITY_NAVIGATE}, "primary", _NAVIGATE_OPTIONS),
    ("camera", "相機", "Camera", {"capability": CAPABILITY_OBSERVE}, "secondary", _CAMERA_OPTIONS),
    ("mode", "運行模式", "Mode", {"resource": "deployment_mode"}, "secondary", _MODE_OPTIONS),
)

# The alert panels, one row each: (id, zh-TW, en, condition, priority).
_ALERT_PANELS = (
    (
        "link_lost", "與機器人的連線中斷", "Link to the robot lost",
        {"source": _CONNECTION_STATE, "in": ["reconnecting", "failed"]}, "hero",
    ),
)


def _state_panel(row: tuple[Any, ...]) -> dict[str, Any]:
    panel_id, zh, en, source, priority, options = row
    return {
        "id": panel_id, "kind": "state", "label": _label(zh, en),
        "source": dict(source), "priority": priority,
        "states": [
            {"value": value, "label": _label(o_zh, o_en), "icon": icon, "tone": tone}
            for value, o_zh, o_en, icon, tone in options
        ],
    }


def _alert_panel(row: tuple[Any, ...]) -> dict[str, Any]:
    panel_id, zh, en, condition, priority = row
    return {"id": panel_id, "kind": "alert", "label": _label(zh, en),
            "when": copy.deepcopy(condition), "priority": priority}


_BLOCK: dict[str, Any] = {
    "schema": PRESENTATION_SCHEMA,
    "subject": {"label": _label("移動機器人", "Mobile robot")},
    "panels": [
        *map(_alert_panel, _ALERT_PANELS),
        *copy.deepcopy(_VALUE_PANELS),
        *map(_state_panel, _STATE_PANELS),
    ],
    "request_examples": [_label(zh, en) for zh, en in REQUEST_EXAMPLES],
}

#: Read-only view of the declaration; :func:`presentation_block` returns a copy.
MOBILE_ROBOT_PRESENTATION = MappingProxyType(_BLOCK)


def presentation_block() -> dict[str, Any]:
    """A fresh copy of the mobile robot's declaration, safe to put in a manifest."""
    return copy.deepcopy(_BLOCK)


def _requested(manifest_extensions: Iterable[str] | None) -> bool:
    if manifest_extensions is None or isinstance(manifest_extensions, (str, bytes)):
        return False
    try:
        return PRESENTATION_EXTENSION in {str(name) for name in manifest_extensions}
    except TypeError:
        return False


def manifest_with_presentation(
    manifest: Mapping[str, Any], manifest_extensions: Iterable[str] | None = None
) -> dict[str, Any]:
    """``manifest``, plus the block only when the host named the extension.

    Released hosts validate the manifest with ``extra="forbid"``; without the
    extension the result equals ``manifest`` key for key, so its contract
    hash is unchanged.
    """
    result = dict(manifest)
    if _requested(manifest_extensions):
        result[PRESENTATION_EXTENSION] = presentation_block()
    return result


def canonical_bytes(value: Any) -> bytes:
    """Sorted keys, compact separators, UTF-8: the form the size cap and hashes use."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def schema_text() -> str:
    """The vendored JSON Schema, as shipped in the package."""
    return resources.files("flyto_modules_robotics").joinpath(SCHEMA_RESOURCE).read_text("utf-8")


__all__ = [
    "BATTERY_CHANNEL",
    "CONNECTION_CHANNEL",
    "CONNECTION_STATES",
    "DEPLOYMENT_MODES",
    "MAX_CANONICAL_BYTES",
    "MOBILE_ROBOT_PRESENTATION",
    "NAVIGATION_CHANNEL",
    "NAVIGATION_STATES",
    "POSE_CHANNEL",
    "POSE_FRAMES",
    "PRESENCE_STATES",
    "PRESENTATION_EXTENSION",
    "PRESENTATION_SCHEMA",
    "REQUEST_EXAMPLES",
    "ROBOT_CHANNEL_FIELDS",
    "canonical_bytes",
    "manifest_with_presentation",
    "presentation_block",
    "schema_text",
]
