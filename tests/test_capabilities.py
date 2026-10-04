"""Each capability's parameters equal the adapter's, and its contract is valid."""

from __future__ import annotations

import math

import pytest
from contract_rules import ContractInvalid, judge, validate_contract

from flyto_modules_robotics.capabilities import (
    ABSOLUTE_MEASURE_OPS,
    NAVIGATE_HEADING_TOLERANCE_RAD,
    NAVIGATE_POSITION_TOLERANCE_M,
    SPECS,
    SPECS_BY_CAPABILITY,
    SPECS_BY_MODULE,
)
from flyto_modules_robotics.modules import registrable_contract

# The flyto-robotics Generic ROS 2 adapter's declared arguments, copied from
# flyto-robotics 0.3.0 (branch claude/robot-places),
# flyto_robotics/generic_ros2_adapter.py `ARGUMENTS`, as (name, required,
# minimum, maximum, unit) for numbers and (name, required, "string",
# max_length) for text. If the adapter changes, this table and
# capabilities.py change together.
ADAPTER_ARGUMENTS = {
    "motion.navigate": (
        ("x", False, -1000.0, 1000.0, "m"),
        ("y", False, -1000.0, 1000.0, "m"),
        ("yaw_radians", False, -math.pi, math.pi, "rad"),
        ("place", False, "string", 64),
    ),
    "vision.observe": (),
    "sensing.map": (),
    "places.list": (),
    "places.mark": (("place", True, "string", 64),),
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
    "places.list": ("read_only", False, False),
    "places.mark": ("controlled", False, False),
}

EXPECTED_TABLE = {
    "robotics.advance": "motion.advance",
    "robotics.retreat": "motion.retreat",
    "robotics.rotate": "motion.rotate",
    "robotics.halt": "motion.halt",
    "robotics.navigate": "motion.navigate",
    "robotics.observe": "vision.observe",
    "robotics.map": "sensing.map",
    "robotics.places": "places.list",
    "robotics.mark_place": "places.mark",
}


def test_one_module_per_capability_exactly_the_spec_table():
    assert {spec.module_id: spec.capability_id for spec in SPECS} == EXPECTED_TABLE
    assert len(SPECS_BY_MODULE) == len(SPECS_BY_CAPABILITY) == len(SPECS) == 9


def test_capability_set_equals_the_adapters():
    assert set(SPECS_BY_CAPABILITY) == set(ADAPTER_ARGUMENTS)


@pytest.mark.parametrize("capability_id", sorted(ADAPTER_ARGUMENTS))
def test_parameters_and_bounds_equal_the_adapters(capability_id):
    schema = SPECS_BY_CAPABILITY[capability_id].params_schema
    declared = tuple(
        (name, field["required"], "string", field["maxLength"])
        if field["type"] == "string"
        else (name, field["required"], field["min"], field["max"], field["unit"])
        for name, field in schema.items()
    )
    assert declared == ADAPTER_ARGUMENTS[capability_id]
    for field in schema.values():
        assert field["type"] in ("number", "string")


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


def _as_registered(spec, module):
    """The contract as this flyto-core registers it (2.36.0 keys, 2.38.0 ops)."""
    return registrable_contract(
        spec.contract,
        frozenset(getattr(module, "OPTIONAL_FIELDS", ())),
        frozenset(getattr(module, "MEASURE_OPS", ())),
    )


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.module_id)
def test_every_contract_satisfies_flyto_core_when_installed(spec):
    module = pytest.importorskip("core.capability_contract")
    module.validate_contract(_as_registered(spec, module), dict(spec.params_schema))


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


@pytest.mark.parametrize(("module_id", "scale"), [("robotics.advance", 1), ("robotics.retreat", -1)])
def test_linear_tolerances_equal_the_spec_table(module_id, scale):
    displacement = _evidence(module_id, "displacement")
    assert displacement["phases"] == ["before", "after", "settled"]
    assert displacement["measure"] == {"op": "along", "fields": ["x", "y"], "heading_field": "yaw"}
    assert displacement["expect"] == {"argument": "distance_m", "scale": scale}
    assert displacement["tolerance"] == {"absolute": 0.03, "relative": 0.3}
    assert displacement["settle"] == {"max_drift": 0.02}
    heading = _evidence(module_id, "heading.hold")
    assert heading["phases"] == ["before", "after", "settled"]
    assert heading["measure"] == {"op": "abs_angle_delta", "fields": ["yaw"]}
    assert heading["expect"] == {"value": 0.0}
    assert heading["tolerance"] == {"absolute": 0.15, "relative": 0.0}


def test_rotation_tolerances_equal_the_spec_table():
    rotation = _evidence("robotics.rotate", "rotation")
    assert rotation["phases"] == ["before", "after", "settled"]
    assert rotation["measure"] == {"op": "angle_delta", "fields": ["yaw"]}
    assert rotation["expect"] == {"argument": "yaw_radians", "scale": 1}
    assert rotation["tolerance"] == {"absolute": 0.1, "relative": 0.2}
    drift = _evidence("robotics.rotate", "position.drift")
    assert drift["phases"] == ["before", "after", "settled"]
    assert drift["measure"] == {"op": "distance", "fields": ["x", "y"]}
    assert drift["expect"] == {"value": 0.0}
    assert drift["tolerance"] == {"absolute": 0.05, "relative": 0.0}
    assert drift["settle"] == {"max_drift": 0.02}


def _core_judge(*, absolute=False):
    module = pytest.importorskip("core.capability_contract")
    if not hasattr(module, "judge"):  # pragma: no cover - partial core
        pytest.skip("installed flyto-core has no capability_contract.judge")
    if absolute and not ABSOLUTE_MEASURE_OPS <= set(getattr(module, "MEASURE_OPS", ())):
        pytest.skip("installed flyto-core predates the absolute measure ops (2.38.0)")
    return module.judge


@pytest.fixture(params=["vendored", "core"])
def judge_fn(request):
    return judge if request.param == "vendored" else _core_judge()


def _poses(before, after, settled):
    keys = ("x", "y", "yaw")
    return {
        "before": dict(zip(keys, before)),
        "after": dict(zip(keys, after)),
        "settled": dict(zip(keys, settled)),
    }


def contract_verdict(judge_fn, module_id, arguments, observations):
    """Usable only when every declared evidence item is usable."""

    evidence = SPECS_BY_MODULE[module_id].contract["evidence"]
    return all(judge_fn(item, arguments, observations)["usable"] for item in evidence)


# Cloud's motion verdicts (flyto-cloud services/space_tasks/motion_verification.py).
CLOUD_CASES = [
    # The physical TurtleBot3 run of 2026-10-02: 0.119 m for 0.10 m asked.
    ("robotics.advance", {"distance_m": 0.10}, ((0, 0, 0), (0.119, 0, 0.02), (0.119, 0, 0.02)), True),
    ("robotics.retreat", {"distance_m": 0.2}, ((0, 0, 0), (-0.19, 0, 0), (-0.19, 0, 0)), True),
    # Still moving 0.03 m after it was told to stop.
    ("robotics.advance", {"distance_m": 0.5}, ((0, 0, 0), (0.5, 0, 0), (0.53, 0, 0)), False),
    # Drifted 0.06 m while turning.
    ("robotics.rotate", {"yaw_radians": 1.0}, ((0, 0, 0), (0.06, 0, 1.0), (0.06, 0, 1.0)), False),
    # Retreat asked, drove forward.
    ("robotics.retreat", {"distance_m": 0.2}, ((0, 0, 0), (0.19, 0, 0), (0.19, 0, 0)), False),
    # Slid sideways the full distance: no progress along the heading.
    ("robotics.advance", {"distance_m": 0.3}, ((0, 0, 0), (0, 0.3, 0), (0, 0.3, 0)), False),
    # Heading changed 0.2 rad on a straight move.
    ("robotics.advance", {"distance_m": 0.3}, ((0, 0, 0), (0.3, 0, 0.2), (0.3, 0, 0.2)), False),
    # Turned the wrong way.
    ("robotics.rotate", {"yaw_radians": -1.5}, ((0, 0, 0), (0, 0, 1.5), (0, 0, 1.5)), False),
    # A turn across +/-pi, compared the short way round.
    ("robotics.rotate", {"yaw_radians": 0.5}, ((0, 0, 3.0), (0, 0, -2.78), (0, 0, -2.78)), True),
]


@pytest.mark.parametrize(("module_id", "arguments", "poses", "usable"), CLOUD_CASES)
def test_declared_evidence_reproduces_clouds_verdicts(judge_fn, module_id, arguments, poses, usable):
    assert contract_verdict(judge_fn, module_id, arguments, _poses(*poses)) is usable


def test_core_judge_numbers_on_the_cloud_cases():
    core_judge = _core_judge()
    advance = _evidence("robotics.advance", "displacement")
    verdict = core_judge(advance, {"distance_m": 0.10}, _poses((0, 0, 0), (0.119, 0, 0.02), (0.119, 0, 0.02)))
    assert verdict["usable"] is True
    assert verdict["measured"] == pytest.approx(0.119)
    assert verdict["allowed"] == pytest.approx(0.03)
    retreat = _evidence("robotics.retreat", "displacement")
    verdict = core_judge(retreat, {"distance_m": 0.2}, _poses((0, 0, 0), (-0.19, 0, 0), (-0.19, 0, 0)))
    assert verdict["usable"] is True
    assert verdict["measured"] == pytest.approx(-0.19)
    assert verdict["expected"] == pytest.approx(-0.2)
    assert verdict["allowed"] == pytest.approx(0.06)
    verdict = core_judge(advance, {"distance_m": 0.5}, _poses((0, 0, 0), (0.5, 0, 0), (0.53, 0, 0)))
    assert verdict["usable"] is False
    assert verdict["settle_drift"] == pytest.approx(0.03)
    drift = _evidence("robotics.rotate", "position.drift")
    verdict = core_judge(drift, {"yaw_radians": 1.0}, _poses((0, 0, 0), (0.06, 0, 1.0), (0.06, 0, 1.0)))
    assert verdict["usable"] is False
    assert verdict["measured"] == pytest.approx(0.06)


def _cloud_reference(capability_id, arguments, observed):
    """Cloud's judge, transcribed from motion_verification.judge (2026-10-04)."""

    def wrap_(angle):
        return math.atan2(math.sin(angle), math.cos(angle))

    before, after, settled = observed["before"], observed["after"], observed["settled"]
    settle = math.hypot(settled["x"] - after["x"], settled["y"] - after["y"])
    dx, dy = settled["x"] - before["x"], settled["y"] - before["y"]
    turned = wrap_(settled["yaw"] - before["yaw"])
    if capability_id in ("motion.advance", "motion.retreat"):
        sign = 1 if capability_id == "motion.advance" else -1
        expected = sign * arguments["distance_m"]
        along = dx * math.cos(before["yaw"]) + dy * math.sin(before["yaw"])
        tolerance = max(0.03, 0.3 * abs(arguments["distance_m"]))
        return abs(along - expected) <= tolerance and abs(turned) <= 0.15 and settle <= 0.02
    yaw = arguments["yaw_radians"]
    tolerance = max(0.1, 0.2 * abs(yaw))
    return abs(wrap_(turned - yaw)) <= tolerance and math.hypot(dx, dy) <= 0.05 and settle <= 0.02


@pytest.mark.parametrize("module_id", ["robotics.advance", "robotics.retreat", "robotics.rotate"])
def test_verdicts_equal_clouds_on_random_motions(judge_fn, module_id):
    import random

    rng = random.Random(20261004)
    spec = SPECS_BY_MODULE[module_id]
    agree = 0
    for _ in range(2000):
        before = (rng.uniform(-5, 5), rng.uniform(-5, 5), rng.uniform(-math.pi, math.pi))
        if spec.capability_id == "motion.rotate":
            arguments = {"yaw_radians": rng.uniform(-math.pi, math.pi)}
            turn = arguments["yaw_radians"] + rng.gauss(0, 0.25)
            after = (before[0] + rng.gauss(0, 0.04), before[1] + rng.gauss(0, 0.04), before[2] + turn)
        else:
            arguments = {"distance_m": rng.uniform(0.05, 2.0)}
            sign = 1 if spec.capability_id == "motion.advance" else -1
            travel = sign * arguments["distance_m"] * rng.uniform(0.5, 1.5)
            heading = before[2] + rng.gauss(0, 0.12)
            after = (
                before[0] + travel * math.cos(heading),
                before[1] + travel * math.sin(heading),
                heading,
            )
        settled = (after[0] + rng.gauss(0, 0.012), after[1] + rng.gauss(0, 0.012), after[2] + rng.gauss(0, 0.02))
        observations = _poses(before, after, settled)
        expected = _cloud_reference(spec.capability_id, arguments, observations)
        assert contract_verdict(judge_fn, module_id, arguments, observations) is expected
        agree += expected
    # Both verdicts occur, so the comparison is not vacuous.
    assert 0 < agree < 2000


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


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.module_id)
def test_contracts_are_already_in_core_normalized_form(spec):
    module = pytest.importorskip("core.capability_contract")
    registered = _as_registered(spec, module)
    normalized = module.validate_contract(registered, dict(spec.params_schema))
    assert normalized == registered


# ---------------------------------------------------------------------------
# Navigation arrival: the end pose in the map frame against the asked goal
# ---------------------------------------------------------------------------


@pytest.fixture(params=["vendored", "core"])
def arrival_judge(request):
    return judge if request.param == "vendored" else _core_judge(absolute=True)


def _map(x, y, yaw=0.0, frame="map"):
    return {"frame": frame, "x": x, "y": y, "yaw": yaw}


def _settled_at(pose):
    return {"after": pose, "settled": pose}


def test_navigate_declares_its_arrival_in_the_map_frame():
    arrival = _evidence("robotics.navigate", "arrival")
    assert arrival == {
        "kind": "arrival",
        "observe": "map_pose",
        "phases": ["after", "settled"],
        "measure": {"op": "distance_to", "fields": ["x", "y"], "frame": "map"},
        "expect": {"arguments": {"x": "x", "y": "y"}},
        "tolerance": {"absolute": 0.3, "relative": 0.0},
    }
    heading = _evidence("robotics.navigate", "arrival.heading")
    assert heading["measure"] == {"op": "angle_to", "fields": ["yaw"], "frame": "map"}
    assert heading["expect"] == {"argument": "yaw_radians", "optional": True}
    assert heading["tolerance"] == {"absolute": 0.3, "relative": 0.0}


def test_arrival_tolerances_are_nav2s_goal_checker_plus_a_small_margin():
    # turtlebot3_navigation2 burger.yaml, run unchanged on the robot and twin.
    assert NAVIGATE_POSITION_TOLERANCE_M == pytest.approx(0.25 + 0.05)
    assert NAVIGATE_HEADING_TOLERANCE_RAD == pytest.approx(0.25 + 0.05)
    # Never looser than a tenth of a metre beyond what Nav2 accepts.
    assert NAVIGATE_POSITION_TOLERANCE_M - 0.25 <= 0.1


# The twin run of 2026-10-04: Nav2 SUCCEEDED, the robot stopped 0.63 m short.
SHORT_GOAL = {"x": 1.196, "y": -0.005, "yaw_radians": 0.0028}
SHORT_STOP = _map(0.566, -0.005, 0.01)

NAVIGATE_CASES = [
    ("succeeded 0.63 m short", SHORT_GOAL, _settled_at(SHORT_STOP), False),
    ("inside Nav2's own tolerance", {"x": 1.0, "y": 0.0}, _settled_at(_map(1.2, 0.1)), True),
    ("just beyond the margin", {"x": 1.0, "y": 0.0}, _settled_at(_map(1.31, 0.0)), False),
    ("odometry, not the map frame", {"x": 1.0, "y": 0.0}, _settled_at(_map(1.0, 0.0, frame="odom")), False),
    ("arrived, facing the asked heading", {"x": 1.0, "y": 0.0, "yaw_radians": 1.5},
     _settled_at(_map(1.0, 0.0, 1.7)), True),
    ("arrived, facing away", {"x": 1.0, "y": 0.0, "yaw_radians": 1.5},
     _settled_at(_map(1.0, 0.0, -1.5)), False),
    ("arrived across +/-pi", {"x": 1.0, "y": 0.0, "yaw_radians": 3.1},
     _settled_at(_map(1.0, 0.0, -3.1)), True),
    ("no heading asked", {"x": 1.0, "y": 0.0}, _settled_at(_map(1.0, 0.0, 2.0)), True),
]


@pytest.mark.parametrize(
    ("arguments", "observations", "usable"),
    [case[1:] for case in NAVIGATE_CASES],
    ids=[case[0] for case in NAVIGATE_CASES],
)
def test_navigate_is_verified_only_where_it_arrived(arrival_judge, arguments, observations, usable):
    assert contract_verdict(arrival_judge, "robotics.navigate", arguments, observations) is usable


def test_core_judge_numbers_on_the_short_navigation():
    core_judge = _core_judge(absolute=True)
    verdict = core_judge(_evidence("robotics.navigate", "arrival"), SHORT_GOAL, _settled_at(SHORT_STOP))
    assert verdict["usable"] is False
    assert verdict["measured"] == pytest.approx(0.63)
    assert verdict["allowed"] == pytest.approx(0.3)


def test_vendored_rules_reject_a_malformed_arrival():
    navigate = SPECS_BY_MODULE["robotics.navigate"]
    arrival, heading = navigate.contract["evidence"]
    for bad in (
        {**arrival, "tolerance": {"absolute": 0.3, "relative": 0.1}},
        {**arrival, "expect": {"arguments": {"x": "x"}}},
        {**arrival, "phases": ["before"]},
        {**heading, "expect": {"argument": "yaw_radians", "optional": "yes"}},
    ):
        with pytest.raises(ContractInvalid):
            validate_contract({**navigate.contract, "evidence": [bad]}, navigate.params_schema)
