# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""Stable authoring-node identifiers for the robotics plugin.

Production execution uses :mod:`flyto_modules_robotics.capability_request`.
There is deliberately no robot-local plan, gateway or capability-catalog
translation in this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

MODULE_MOVE = "robotics.move"
MODULE_TURN = "robotics.turn"
MODULE_STOP = "robotics.stop"

MODULE_IDS = (MODULE_MOVE, MODULE_TURN, MODULE_STOP)
NAMESPACE = "robotics."


def is_robotics_step(module_id: Any) -> bool:
    """Whether an identifier names one of the three robotics authoring nodes."""

    return str(module_id or "").strip() in MODULE_IDS


def step_module_id(step: Mapping[str, Any] | None) -> str:
    """Read the module identifier from any supported serialized step spelling."""

    if not isinstance(step, Mapping):
        return ""
    for key in ("module", "module_id", "action", "type"):
        value = step.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
