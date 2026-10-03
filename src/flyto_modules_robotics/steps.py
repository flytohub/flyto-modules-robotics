# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""Stable step identifiers for the robotics plugin.

One step per capability; the identifiers and what they provide are defined in
:mod:`flyto_modules_robotics.capabilities`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .capabilities import FLEET_SPECS, SPECS

MODULE_IDS = tuple(spec.module_id for spec in SPECS)
# The ``fleet`` pack's steps (Open-RMF); not robotics steps.
FLEET_MODULE_IDS = tuple(spec.module_id for spec in FLEET_SPECS)
NAMESPACE = "robotics."


def is_robotics_step(module_id: Any) -> bool:
    """Whether an identifier names one of this package's robotics steps."""

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
