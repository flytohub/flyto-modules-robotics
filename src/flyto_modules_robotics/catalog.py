"""Legacy immutable consumer for the superseded delivery capability catalog.

Production workflow execution uses canonical capability requests and an external
Generic ROS 2 Adapter. This parser remains for historical Gazebo/downstream
compatibility until the old delivery-plan path is fully removed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

CATALOG_CONTRACT_VERSION = "flyto.robotics.capability-catalog.v1"
CATALOG_ERROR = "capability catalog invalid"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,191}$")
_SAFE_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_TOP_FIELDS = {"contract_version", "registry_revision", "capabilities", "contract_hash"}
_ENTRY_FIELDS = {
    "capability_id", "runtime_name", "version", "executor_kind",
    "approval_status", "safety_class", "requires_safe_stop",
    "required_observations", "required_resources", "required_permissions",
    "arguments", "schema_hash",
}
_ARG_REQUIRED = {"name", "type", "required", "description"}
_ARG_OPTIONAL = {"minimum", "maximum", "choices", "default", "required_when"}
_VALUE_TYPES = {"number", "boolean", "string", "text"}
_MAX_CAPABILITIES = 256
_MAX_ARGUMENTS = 128
_MAX_ARGUMENT_BYTES = 65_536


class CapabilityCatalogError(ValueError):
    """A catalog did not exactly match the trusted consumer contract."""

    def __init__(self) -> None:
        super().__init__(CATALOG_ERROR)


@dataclass(frozen=True)
class Capability:
    capability_id: str
    runtime_name: str
    version: str
    executor_kind: str
    approval_status: str
    safety_class: str
    requires_safe_stop: bool
    required_observations: tuple[str, ...]
    required_resources: tuple[str, ...]
    required_permissions: tuple[str, ...]
    arguments: tuple[Mapping[str, Any], ...]
    schema_hash: str

    def argument(self, name: str) -> Mapping[str, Any] | None:
        """Return an immutable argument schema by its exact lower-owned name."""
        return next((item for item in self.arguments if item["name"] == name), None)

    argument_by_name = argument


@dataclass(frozen=True)
class CapabilityCatalog:
    contract_version: str
    registry_revision: int
    capabilities: tuple[Capability, ...]
    contract_hash: str

    def capability(self, capability_id: str) -> Capability | None:
        """Return an immutable capability by its exact versioned identity."""
        return next(
            (item for item in self.capabilities if item.capability_id == capability_id),
            None,
        )

    capability_by_id = capability

    def runtime(self, runtime_name: str) -> Capability | None:
        """Return an immutable capability by its exact lower runtime name."""
        return next(
            (item for item in self.capabilities if item.runtime_name == runtime_name),
            None,
        )

    capability_by_runtime_name = runtime


def _reject() -> None:
    raise CapabilityCatalogError()


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        _reject()


def _safe(value: object, pattern: re.Pattern[str] = _SAFE_TEXT) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _reject()
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 128:
        _reject()
    result = tuple(_safe(item) for item in value)
    if len(set(result)) != len(result):
        _reject()
    return result


def _finite_number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject()
    if not math.isfinite(float(value)):
        _reject()
    return value


def _argument(raw: object) -> Mapping[str, Any]:
    if not isinstance(raw, dict) or not _ARG_REQUIRED <= set(raw):
        _reject()
    if set(raw) - _ARG_REQUIRED - _ARG_OPTIONAL:
        _reject()
    name = _safe(raw["name"])
    value_type = raw["type"]
    if value_type not in _VALUE_TYPES or not isinstance(raw["required"], bool):
        _reject()
    description = raw["description"]
    if (
        not isinstance(description, str)
        or len(description) > 1024
        or any(ord(character) < 32 for character in description)
    ):
        _reject()
    normalized: dict[str, Any] = {
        "name": name,
        "type": value_type,
        "required": raw["required"],
        "description": description,
    }
    for bound in ("minimum", "maximum"):
        if bound in raw:
            if value_type != "number":
                _reject()
            normalized[bound] = _finite_number(raw[bound])
    if (
        "minimum" in normalized
        and "maximum" in normalized
        and normalized["minimum"] > normalized["maximum"]
    ):
        _reject()
    if "choices" in raw:
        if value_type != "string":
            _reject()
        normalized["choices"] = _string_list(raw["choices"])
    if "default" in raw:
        default = raw["default"]
        if value_type == "number":
            default = _finite_number(default)
            if "minimum" in normalized and default < normalized["minimum"]:
                _reject()
            if "maximum" in normalized and default > normalized["maximum"]:
                _reject()
        elif value_type == "boolean":
            if not isinstance(default, bool):
                _reject()
        elif not isinstance(default, str):
            _reject()
        elif value_type == "string":
            default = _safe(default)
        elif len(default) > 128 or any(ord(char) < 32 for char in default):
            _reject()
        if "choices" in normalized and default not in normalized["choices"]:
            _reject()
        normalized["default"] = default
    if "required_when" in raw:
        condition = raw["required_when"]
        if not isinstance(condition, dict) or set(condition) != {"argument", "equals"}:
            _reject()
        argument = _safe(condition["argument"])
        equals = condition["equals"]
        if not isinstance(equals, (str, bool, int, float)) or (
            isinstance(equals, float) and not math.isfinite(equals)
        ):
            _reject()
        normalized["required_when"] = MappingProxyType(
            {"argument": argument, "equals": equals}
        )
    return MappingProxyType(normalized)


def _entry(raw: object) -> Capability:
    if not isinstance(raw, dict) or set(raw) != _ENTRY_FIELDS:
        _reject()
    arguments_raw = raw["arguments"]
    if not isinstance(arguments_raw, list) or len(arguments_raw) > _MAX_ARGUMENTS:
        _reject()
    if len(_canonical(arguments_raw)) > _MAX_ARGUMENT_BYTES:
        _reject()
    arguments = tuple(_argument(item) for item in arguments_raw)
    names = tuple(item["name"] for item in arguments)
    if len(set(names)) != len(names):
        _reject()
    schema_hash = raw["schema_hash"]
    if not isinstance(schema_hash, str) or _HASH.fullmatch(schema_hash) is None:
        _reject()
    if hashlib.sha256(_canonical(arguments_raw)).hexdigest() != schema_hash:
        _reject()
    if raw["executor_kind"] != "flyto-robotics" or raw["approval_status"] != "APPROVED":
        _reject()
    if not isinstance(raw["requires_safe_stop"], bool):
        _reject()
    return Capability(
        capability_id=_safe(raw["capability_id"], _SAFE_ID),
        runtime_name=_safe(raw["runtime_name"]),
        version=_safe(raw["version"]),
        executor_kind="flyto-robotics",
        approval_status="APPROVED",
        safety_class=_safe(raw["safety_class"]),
        requires_safe_stop=raw["requires_safe_stop"],
        required_observations=_string_list(raw["required_observations"]),
        required_resources=_string_list(raw["required_resources"]),
        required_permissions=_string_list(raw["required_permissions"]),
        arguments=arguments,
        schema_hash=schema_hash,
    )


def parse_capability_catalog(value: object) -> CapabilityCatalog:
    """Validate the complete lower contract and return an immutable projection."""
    try:
        if not isinstance(value, dict) or set(value) != _TOP_FIELDS:
            _reject()
        if value["contract_version"] != CATALOG_CONTRACT_VERSION:
            _reject()
        revision = value["registry_revision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or revision != 1:
            _reject()
        raw_capabilities = value["capabilities"]
        if not isinstance(raw_capabilities, list) or len(raw_capabilities) > _MAX_CAPABILITIES:
            _reject()
        contract_hash = value["contract_hash"]
        if not isinstance(contract_hash, str) or _HASH.fullmatch(contract_hash) is None:
            _reject()
        if hashlib.sha256(_canonical(raw_capabilities)).hexdigest() != contract_hash:
            _reject()
        capabilities = tuple(_entry(item) for item in raw_capabilities)
        ids = tuple(item.capability_id for item in capabilities)
        names = tuple(item.runtime_name for item in capabilities)
        if len(set(ids)) != len(ids) or len(set(names)) != len(names):
            _reject()
        return CapabilityCatalog(
            contract_version=CATALOG_CONTRACT_VERSION,
            registry_revision=revision,
            capabilities=capabilities,
            contract_hash=contract_hash,
        )
    except CapabilityCatalogError:
        raise
    except Exception:  # noqa: BLE001 - untrusted mapping subclasses may raise arbitrary errors
        raise CapabilityCatalogError() from None
