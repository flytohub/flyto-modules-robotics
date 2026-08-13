"""Strict consumption of the lower capability-catalog contract."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

from flyto_modules_robotics.catalog import (
    CATALOG_ERROR,
    CapabilityCatalogError,
    parse_capability_catalog,
)


def _hash(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def valid_catalog():
    arguments = [
        {
            "name": "distance_m",
            "type": "number",
            "required": True,
            "description": "Signed travel distance.",
            "minimum": -2.0,
            "maximum": 2.0,
        },
        {
            "name": "speed",
            "type": "number",
            "required": False,
            "description": "Travel speed.",
            "minimum": 0.05,
            "maximum": 0.5,
            "default": 0.2,
        },
    ]
    capability = {
        "capability_id": "robotics.motion.move_relative@1",
        "runtime_name": "move_relative",
        "version": "1.0.0",
        "executor_kind": "flyto-robotics",
        "approval_status": "APPROVED",
        "safety_class": "controlled",
        "requires_safe_stop": True,
        "required_observations": ["odometry"],
        "required_resources": ["base_controller"],
        "required_permissions": ["robot.motion"],
        "arguments": arguments,
        "schema_hash": _hash(arguments),
    }
    capabilities = [capability]
    return {
        "contract_version": "flyto.robotics.capability-catalog.v1",
        "registry_revision": 1,
        "capabilities": capabilities,
        "contract_hash": _hash(capabilities),
    }


def rehash(value):
    for capability in value.get("capabilities", []):
        capability["schema_hash"] = _hash(capability["arguments"])
    value["contract_hash"] = _hash(value.get("capabilities"))
    return value


def test_valid_lower_shaped_catalog_is_deterministic_and_immutable():
    source = valid_catalog()
    first = parse_capability_catalog(source)
    second = parse_capability_catalog(copy.deepcopy(source))
    assert first == second
    assert first.capabilities[0].arguments[0]["minimum"] == -2.0
    source["capabilities"][0]["arguments"][0]["minimum"] = -999
    assert first.capabilities[0].arguments[0]["minimum"] == -2.0
    with pytest.raises(FrozenInstanceError):
        first.registry_revision = 2
    with pytest.raises(TypeError):
        first.capabilities[0].arguments[0]["minimum"] = -3.0


def test_exact_id_runtime_and_argument_lookups_return_frozen_records():
    parsed = parse_capability_catalog(valid_catalog())
    capability = parsed.capability_by_id("robotics.motion.move_relative@1")
    assert capability is parsed.capability_by_runtime_name("move_relative")
    assert capability.argument_by_name("speed")["default"] == 0.2
    assert parsed.capability_by_id("robotics.motion.move_relative") is None
    assert parsed.capability_by_runtime_name("MOVE_RELATIVE") is None
    assert capability.argument_by_name("Speed") is None
    with pytest.raises(TypeError):
        capability.argument_by_name("speed")["default"] = 0.3


def test_hashes_use_lower_canonical_json_rule_and_cover_the_right_payloads():
    value = valid_catalog()
    parsed = parse_capability_catalog(value)
    assert parsed.capabilities[0].schema_hash == _hash(
        value["capabilities"][0]["arguments"]
    )
    assert parsed.contract_hash == _hash(value["capabilities"])
    changed = copy.deepcopy(value)
    changed["capabilities"][0]["arguments"][0]["maximum"] = 3.0
    with pytest.raises(CapabilityCatalogError, match=f"^{CATALOG_ERROR}$"):
        parse_capability_catalog(changed)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda v: v.update(extra=True),
        lambda v: v.pop("registry_revision"),
        lambda v: v.update(registry_revision=True),
        lambda v: v.update(registry_revision=2),
        lambda v: v["capabilities"][0].update(extra=True),
        lambda v: v["capabilities"][0].pop("safety_class"),
        lambda v: v["capabilities"][0].update(executor_kind="shell"),
        lambda v: v["capabilities"][0].update(approval_status="PENDING"),
        lambda v: v["capabilities"][0].update(requires_safe_stop=1),
        lambda v: v["capabilities"][0].update(capability_id="../unsafe"),
        lambda v: v["capabilities"][0].update(runtime_name="bad name"),
        lambda v: v["capabilities"][0]["arguments"][0].update(minimum=True),
        lambda v: v["capabilities"][0]["arguments"][0].update(maximum=float("inf")),
        lambda v: v["capabilities"][0]["arguments"][0].update(unknown="x"),
        lambda v: v["capabilities"][0]["arguments"][0].pop("type"),
        lambda v: v["capabilities"][0]["arguments"][0].update(description="bad\x00text"),
    ],
)
def test_adversarial_shapes_fail_with_one_content_free_error(mutate):
    value = valid_catalog()
    mutate(value)
    rehash(value)
    with pytest.raises(CapabilityCatalogError) as caught:
        parse_capability_catalog(value)
    assert str(caught.value) == CATALOG_ERROR


def test_malformed_contract_hash_is_rejected():
    value = valid_catalog()
    value["contract_hash"] = "A" * 64
    with pytest.raises(CapabilityCatalogError) as caught:
        parse_capability_catalog(value)
    assert str(caught.value) == CATALOG_ERROR


def test_duplicate_capability_and_runtime_identities_are_rejected():
    for field in ("capability_id", "runtime_name"):
        value = valid_catalog()
        duplicate = copy.deepcopy(value["capabilities"][0])
        other = "robotics.other@1" if field == "capability_id" else "other"
        duplicate[field] = other
        value["capabilities"].append(duplicate)
        value["capabilities"][0][field] = other
        rehash(value)
        with pytest.raises(CapabilityCatalogError):
            parse_capability_catalog(value)


def test_oversized_and_deep_argument_payloads_are_rejected():
    oversized = valid_catalog()
    oversized["capabilities"][0]["arguments"][0]["description"] = "x" * 70_000
    rehash(oversized)
    with pytest.raises(CapabilityCatalogError):
        parse_capability_catalog(oversized)

    deep = valid_catalog()
    deep["capabilities"][0]["arguments"][0]["required_when"] = {
        "argument": "mode",
        "equals": {"nested": {"too": "deep"}},
    }
    rehash(deep)
    with pytest.raises(CapabilityCatalogError):
        parse_capability_catalog(deep)
