# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""What an HMI shows for a ROS 2 mobile robot (``flyto.resource-presentation.v1``).

The pack declares WHAT is shown; Cloud passes the block through unchanged
(schema-validated, size-capped) and the App renders it through one generic
panel registry. Nothing here names a widget: panels are generic kinds
(``state``, ``alert``) over sources the robot resource really carries.

Only real sources are read. The resource manifest the flyto-robotics ROS 2
adapter publishes declares no telemetry channel of its own
(``telemetry_channels: []``), so there is no battery, pose, navigation-state
or distance-to-goal channel to show, and no panel claims one. What exists:

* the ``connection`` channel, declared on every adapter-backed manifest by
  the execution host (flyto-cloud ``local/resource_connection_telemetry.py``)
  with ``state`` in :data:`CONNECTION_STATES`;
* the resource's own ``presence.state`` and ``deployment_mode``;
* whether a capability of this pack is currently offered (``capability``).

The block is an optional manifest extension (:data:`PRESENTATION_EXTENSION`):
:func:`manifest_with_presentation` adds it only when the host asks, so a
manifest for an older Cloud is byte-for-byte unchanged.

The schema is vendored byte-identical from the App contract
(``flyto-app/docs/contracts/flyto.resource-presentation.v1.schema.json``, the
copy flyto-cloud validates with); its sha256 is pinned in the tests, and so is
the canonical sha256 of the block below.
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

# The state panels, one row each: (id, zh-TW, en, source, priority, options).
_STATE_PANELS = (
    ("presence", "機器人狀態", "Robot status", {"resource": "presence.state"}, "hero", _PRESENCE_OPTIONS),
    ("connection", "連線", "Link", _CONNECTION_STATE, "primary", _CONNECTION_OPTIONS),
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
    "panels": [*map(_alert_panel, _ALERT_PANELS), *map(_state_panel, _STATE_PANELS)],
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
    "CONNECTION_CHANNEL",
    "CONNECTION_STATES",
    "DEPLOYMENT_MODES",
    "MAX_CANONICAL_BYTES",
    "MOBILE_ROBOT_PRESENTATION",
    "PRESENCE_STATES",
    "PRESENTATION_EXTENSION",
    "PRESENTATION_SCHEMA",
    "canonical_bytes",
    "manifest_with_presentation",
    "presentation_block",
    "schema_text",
]
