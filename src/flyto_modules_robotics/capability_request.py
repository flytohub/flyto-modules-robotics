# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""Turn one authored step into a bounded ``flyto.capability-request.v1``.

Pure: no ROS, no network, no flyto-core.  Every parameter is checked against
the capability's ``params_schema`` (which equals the adapter's declared
arguments).  Unknown, missing, non-finite and out-of-range values are refused;
nothing is clamped.  Text (a fleet waypoint) is trimmed and must fit its
declared length; control characters are refused.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .capabilities import ALL_SPECS_BY_MODULE, CapabilitySpec

CAPABILITY_REQUEST_VERSION = "flyto.capability-request.v1"

# Routing, not an argument: which commanded resource the step addresses.
RESOURCE_PARAM = "resource_id"
MAX_RESOURCE_ID_LENGTH = 128


class CapabilityRequestError(ValueError):
    """Authored parameters cannot become a bounded capability request."""


def _resource(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CapabilityRequestError("a commanded resource is required")
    resource_id = value.strip()
    if len(resource_id) > MAX_RESOURCE_ID_LENGTH:
        raise CapabilityRequestError(
            f"commanded resource must be {MAX_RESOURCE_ID_LENGTH} characters or fewer"
        )
    return resource_id


def _bounded_number(name: str, value: Any, field: Mapping[str, Any]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CapabilityRequestError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise CapabilityRequestError(f"{name} must be finite")
    minimum, maximum = field["min"], field["max"]
    if number < minimum or number > maximum:
        unit = field.get("unit", "")
        raise CapabilityRequestError(
            f"{name} must be between {minimum:g} and {maximum:g} {unit}".rstrip()
        )
    return number


def _bounded_text(name: str, value: Any, field: Mapping[str, Any]) -> str:
    if not isinstance(value, str):
        raise CapabilityRequestError(f"{name} must be text")
    text = value.strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in text):
        raise CapabilityRequestError(f"{name} must not contain control characters")
    low, high = int(field.get("minLength", 0)), int(field["maxLength"])
    if not low <= len(text) <= high:
        raise CapabilityRequestError(f"{name} must be {low} to {high} characters")
    return text


def _argument(name: str, value: Any, field: Mapping[str, Any]) -> Any:
    if field.get("type") == "string":
        return _bounded_text(name, value, field)
    return _bounded_number(name, value, field)


def arguments_for(spec: CapabilitySpec, params: Mapping[str, Any]) -> dict[str, Any]:
    """Validated adapter arguments for one capability, defaults made explicit."""

    if not isinstance(params, Mapping):
        raise CapabilityRequestError("parameters must be an object")
    schema = spec.params_schema
    unknown = sorted(
        str(key) for key in params if key not in schema and key != RESOURCE_PARAM
    )
    if unknown:
        raise CapabilityRequestError(
            f"{spec.module_id} does not take: " + ", ".join(unknown)
        )
    arguments: dict[str, Any] = {}
    for name, field in schema.items():
        if name in params and params[name] is not None:
            arguments[name] = _argument(name, params[name], field)
        elif "default" in field:
            arguments[name] = float(field["default"])
        elif field.get("required"):
            raise CapabilityRequestError(f"{name} is required")
    return arguments


def capability_request_for_step(
    module_id: Any,
    params: Mapping[str, Any] | None = None,
    *,
    resource_id: str,
) -> dict[str, Any] | None:
    """The bounded request one robotics step makes, or None if not ours.

    The request names the commanded resource and the capability only.  Which
    computer executes it is chosen by the control plane, never here.
    """

    spec = ALL_SPECS_BY_MODULE.get(str(module_id or "").strip())
    if spec is None:
        return None
    return {
        "contract_version": CAPABILITY_REQUEST_VERSION,
        "resource_id": _resource(resource_id),
        "capability_id": spec.capability_id,
        "arguments": arguments_for(spec, params or {}),
    }
