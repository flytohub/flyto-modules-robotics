"""Each capability's parameters equal the adapter's, and its contract is valid."""

from __future__ import annotations

import math

import pytest
from contract_rules import ContractInvalid, judge, validate_contract

from flyto_modules_robotics.capabilities import (
    SPECS,
    SPECS_BY_CAPABILITY,
    SPECS_BY_MODULE,
)

# The flyto-robotics Generic ROS 2 adapter's declared arguments, copied from
# flyto-robotics origin/main ab252f1, flyto_robotics/generic_ros2_adapter.py
# lines 287-319 (`ARGUMENTS`), as (name, required, minimum, maximum, unit).
# If the adapter changes, this table and capabilities.py change together.
ADAPTER_ARGUMENTS = {
    "motion.navigate": (
        ("x", True, -1000.0, 1000.0, "m"),
        ("y", True, -1000.0, 1000.0, "m"),
        ("yaw_radians", False, -math.pi, math.pi, "rad"),
    ),
    "vision.observe": (),
    "sensing.map": (),
    "motion.advance": (
        ("distance_m", True, 0.05, 2.0, "m"),
        ("speed_mps", False, 0.02, 0.25, "m/s"),
    ),
    "motion.retreat": (
        ("distance_m", True, 0.05, 2.0, "m"),
        ("speed_mps", False, 0.02, 0.20, "m/s"),
    ),
    "motion.rotate": (("yaw_radians", True, -math.pi, math.pi, "rad"),),
    "motion.halt": (),
}

# The adapter's own speed defaults (generic_ros2_adapter.py ~:1421).
ADAPTER_SPEED_DEFAULTS = {"motion.advance": 0.12, "motion.retreat": 0.10}

# flyto-robotics adapter_contract._CAPABILITY_METADATA.
ADAPTER_METADATA = {
    "motion.navigate": ("movement", True, True),
    "vision.observe": ("read_only", False, False),
    "sensing.map": ("read_only", False, False),
    "motion.advance": ("movement", True, True),
    "motion.retreat": ("movement", True, True),
    "motion.rotate": ("movement", True, True),
    "motion.halt": ("controlled", False, False),
}

EXPECTED_TABLE = {
    "robotics.advance": "motion.advance",
    "robotics.retreat": "motion.retreat",
    "robotics.rotate": "motion.rotate",
    "robotics.halt": "motion.halt",
    "robotics.navigate": "motion.navigate",
    "robotics.observe": "vision.observe",
    "robotics.map": "sensing.map",
}


def test_one_module_per_capability_exactly_the_spec_table():
    assert {spec.module_id: spec.capability_id for spec in SPECS} == EXPECTED_TABLE
    assert len(SPECS_BY_MODULE) == len(SPECS_BY_CAPABILITY) == len(SPECS) == 7


def test_capability_set_equals_the_adapters():
    assert set(SPECS_BY_CAPABILITY) == set(ADAPTER_ARGUMENTS)


@pytest.mark.parametrize("capability_id", sorted(ADAPTER_ARGUMENTS))
def test_parameters_and_bounds_equal_the_adapters(capability_id):
    schema = SPECS_BY_CAPABILITY[capability_id].params_schema
    declared = tuple(
        (name, field["required"], field["min"], field["max"], field["unit"])
        for name, field in schema.items()
    )
    assert declared == ADAPTER_ARGUMENTS[capability_id]
    for field in schema.values():
        assert field["type"] == "number"


@pytest.mark.parametrize("capability_id", sorted(ADAPTER_SPEED_DEFAULTS))
def test_speed_default_equals_the_adapters(capability_id):
    schema = SPECS_BY_CAPABILITY[capability_id].params_schema
    assert schema["speed_mps"]["default"] == ADAPTER_SPEED_DEFAULTS[capability_id]


@pytest.mark.parametrize("capability_id", sorted(ADAPTER_METADATA))
def test_safety_metadata_equals_the_adapters(capability_id):
    contract = SPECS_BY_CAPABILITY[capability_id].contract
    assert (
        contract["safety_class"],
        contract["requires_safe_stop"],
        contract["cancellable"],
    ) == ADAPTER_METADATA[capability_id]


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.module_id)
def test_every_contract_satisfies_the_v1_rules(spec):
    validate_contract(dict(spec.contract), spec.params_schema)


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.module_id)
def test_every_contract_satisfies_flyto_core_when_installed(spec):
    module = pytest.importorskip("core.capability_contract")
    module.validate_contract(dict(spec.contract), dict(spec.params_schema))


def test_actuation_matches_the_spec_table():
    actuating = {spec.module_id for spec in SPECS if spec.actuates}
    assert actuating == {
        "robotics.advance",
        "robotics.retreat",
        "robotics.rotate",
        "robotics.halt",
        "robotics.navigate",
    }


def test_halt_is_the_stop_itself():
    contract = SPECS_BY_MODULE["robotics.halt"].contract
    assert contract["actuates"] is True
    assert contract["safety_class"] == "controlled"
    assert contract["requires_safe_stop"] is False
    assert contract["cancellable"] is False


def _evidence(module_id, kind):
    (item,) = [
        item for item in SPECS_BY_MODULE[module_id].contract["evidence"] if item["kind"] == kind
    ]
    return item


@pytest.mark.parametrize("module_id", ["robotics.advance", "robotics.retreat"])
def test_linear_tolerances_equal_the_spec_table(module_id):
    displacement = _evidence(module_id, "displacement")
    assert displacement["measure"] == {"op": "distance", "fields": ["x", "y"]}
    assert displacement["expect"] == {"argument": "distance_m"}
    assert displacement["tolerance"] == {"absolute": 0.03, "relative": 0.3}
    assert displacement["settle"] == {"max_drift": 0.02}
    heading = _evidence(module_id, "heading.hold")
    assert heading["measure"] == {"op": "abs_angle_delta", "fields": ["yaw"]}
    assert heading["expect"] == {"value": 0.0}
    assert heading["tolerance"]["absolute"] == 0.15


def test_rotation_tolerances_equal_the_spec_table():
    rotation = _evidence("robotics.rotate", "rotation")
    assert rotation["measure"] == {"op": "angle_delta", "fields": ["yaw"]}
    assert rotation["expect"] == {"argument": "yaw_radians"}
    assert rotation["tolerance"] == {"absolute": 0.1, "relative": 0.2}
    drift = _evidence("robotics.rotate", "position.drift")
    assert drift["measure"] == {"op": "distance", "fields": ["x", "y"]}
    assert drift["expect"] == {"value": 0.0}
    assert drift["tolerance"]["absolute"] == 0.05
    assert drift["settle"] == {"max_drift": 0.02}


def _poses(before, after, settled):
    keys = ("x", "y", "yaw")
    return {
        "before": dict(zip(keys, before)),
        "after": dict(zip(keys, after)),
        "settled": dict(zip(keys, settled)),
    }


def test_declared_evidence_reproduces_clouds_motion_verdicts():
    displacement = _evidence("robotics.advance", "displacement")
    # The physical TurtleBot3 run of 2026-10-02: 0.119 m for 0.10 m asked.
    assert judge(displacement, {"distance_m": 0.10}, _poses((0, 0, 0), (0.119, 0, 0), (0.119, 0, 0)))["usable"]
    # 0.30 * 1.0 = 0.30 m allowed at 1 m; 0.31 m short is not.
    assert not judge(displacement, {"distance_m": 1.0}, _poses((0, 0, 0), (0.69, 0, 0), (0.69, 0, 0)))["usable"]
    # Still moving 0.03 m after it was told to stop.
    assert not judge(displacement, {"distance_m": 0.5}, _poses((0, 0, 0), (0.5, 0, 0), (0.53, 0, 0)))["usable"]

    rotation = _evidence("robotics.rotate", "rotation")
    assert judge(rotation, {"yaw_radians": -1.5}, _poses((0, 0, 0.1), (0, 0, -1.3), (0, 0, -1.35)))["usable"]
    # Turning the wrong way is refused: signed, not absolute.
    assert not judge(rotation, {"yaw_radians": -1.5}, _poses((0, 0, 0), (0, 0, 1.5), (0, 0, 1.5)))["usable"]
    # Wrapped across +/-pi.
    assert judge(rotation, {"yaw_radians": 0.5}, _poses((0, 0, 3.0), (0, 0, -2.78), (0, 0, -2.78)))["usable"]


def test_vendored_rules_reject_what_v1_forbids():
    schema = SPECS_BY_MODULE["robotics.advance"].params_schema
    good = dict(SPECS_BY_MODULE["robotics.advance"].contract)
    with pytest.raises(ContractInvalid):
        validate_contract({**good, "verdict": "pass"}, schema)
    with pytest.raises(ContractInvalid):
        validate_contract({**good, "safety_class": "harmless"}, schema)
    unbounded = {"distance_m": {"type": "number", "min": 0.05}}
    with pytest.raises(ContractInvalid):
        validate_contract({**good, "evidence": []}, unbounded)
    bad_argument = [{**good["evidence"][0], "expect": {"argument": "speed"}}]
    with pytest.raises(ContractInvalid):
        validate_contract({**good, "evidence": bad_argument}, schema)
