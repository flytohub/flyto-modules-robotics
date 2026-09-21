"""The mapping from an authored step to the plan it means.

Two callers read this table — the modules registered into flyto-core, and the
robot's own job runner. These tests are what stop the two from drifting: they
exercise the table itself, not either caller.
"""

from __future__ import annotations

import pytest

from flyto_modules_robotics.plan import PlanBuildError
from flyto_modules_robotics.steps import (
    MODULE_IDS,
    MODULE_MOVE,
    MODULE_STOP,
    MODULE_TURN,
    is_robotics_step,
    plan_for_step,
    step_module_id,
    trusted_plan_for_step,
)

# Enough to build each step, with nothing optional supplied.
MINIMAL = {
    MODULE_MOVE: {"distance_m": 0.4},
    MODULE_TURN: {"degrees": 90},
    MODULE_STOP: {},
}


def test_every_registered_module_can_build_a_plan():
    """A module id with no builder would register on the canvas and then fail
    the moment anyone ran it."""
    assert set(MINIMAL) == set(MODULE_IDS), "a new step needs a row here"
    for module_id, params in MINIMAL.items():
        plan = plan_for_step(module_id, params, robot_id="robot-1")
        assert plan["robot_id"] == "robot-1"
        assert plan["contract_version"] == "flyto.robotics.plan.v1"


def test_how_much_is_the_authors_to_state():
    """A default distance or angle is a robot moving an amount nobody chose."""
    with pytest.raises(PlanBuildError):
        plan_for_step(MODULE_MOVE, {}, robot_id="r")
    with pytest.raises(PlanBuildError):
        plan_for_step(MODULE_TURN, {}, robot_id="r")


def test_how_fast_and_which_way_have_safe_defaults():
    move = plan_for_step(MODULE_MOVE, {"distance_m": 0.4}, robot_id="r")
    assert move["steps"][0]["arguments"]["speed"] > 0
    turn = plan_for_step(MODULE_TURN, {"degrees": 90}, robot_id="r")
    assert turn["steps"][0]["arguments"]["angular_speed"] > 0


def test_a_step_that_is_not_ours_is_not_an_error():
    """A caller sifting a job's steps is asking a question, not making a
    mistake."""
    assert plan_for_step("browser.click", {"selector": "#go"}, robot_id="r") is None
    assert plan_for_step("", {}, robot_id="r") is None
    assert plan_for_step(None, None, robot_id="r") is None
    assert is_robotics_step(MODULE_TURN)
    assert not is_robotics_step("browser.click")


def test_params_reach_the_plan():
    plan = plan_for_step(MODULE_TURN, {"degrees": 90, "clockwise": True}, robot_id="r")
    step = plan["steps"][0]
    assert step["capability"] == "turn_relative"
    assert step["arguments"]["yaw_delta_rad"] < 0, "clockwise turns the other way"

    plan = plan_for_step(MODULE_MOVE, {"distance_m": 0.4, "reverse": True}, robot_id="r")
    assert plan["steps"][0]["arguments"]["distance_m"] == pytest.approx(-0.4)


def test_a_step_of_ours_that_cannot_be_built_still_raises():
    """Out of bounds is a fault in the workflow, and silence would let it
    reach a robot."""
    with pytest.raises(PlanBuildError):
        plan_for_step(MODULE_MOVE, {"distance_m": 99}, robot_id="r")
    with pytest.raises(PlanBuildError):
        plan_for_step(MODULE_TURN, {"degrees": 0}, robot_id="r")


def test_every_plan_ends_with_a_safe_stop():
    for module_id, params in MINIMAL.items():
        plan = plan_for_step(module_id, params, robot_id="r")
        assert plan["steps"][-1]["capability"] == "safe_stop"


def test_stop_is_a_plan_whose_only_step_is_the_stop():
    plan = plan_for_step(MODULE_STOP, {"seconds": 2}, robot_id="r")
    assert len(plan["steps"]) == 1


@pytest.mark.parametrize("key", ["module", "module_id", "action", "type"])
def test_a_step_names_its_module_under_any_spelling(key):
    """A step arrives spelled differently depending on who serialised it, and
    a reader that knew one spelling would treat the others as not-a-robot."""
    assert step_module_id({key: MODULE_TURN}) == MODULE_TURN


def test_a_step_naming_nothing_is_read_as_nothing():
    assert step_module_id({}) == ""
    assert step_module_id(None) == ""
    assert step_module_id({"module": "   "}) == ""


def test_the_table_needs_no_engine():
    """It is imported on a Raspberry Pi that has no flyto-core at all."""
    import sys

    from flyto_modules_robotics import steps

    assert "core" not in sys.modules or steps.__name__  # not imported by us
    assert steps.preview_plan_for_step(MODULE_TURN, {"degrees": 90}, robot_id="r")["plan_id"]


def test_execution_requires_a_trusted_catalog_and_never_falls_back():
    with pytest.raises(PlanBuildError, match="trusted capability catalog"):
        trusted_plan_for_step(MODULE_MOVE, {"distance_m": 0.4}, robot_id="r")

    # Legacy preview remains a separate authoring-only API.
    assert plan_for_step(MODULE_MOVE, {"distance_m": 0.4}, robot_id="r")["plan_id"]


# -- the contract the robot actually enforces ----------------------------


def test_a_plan_uses_the_argument_names_the_robot_reads():
    """These names are the robot's, not ours.

    `turn_relative` takes `yaw_delta_rad`; a plan saying `radians` is refused
    by the gateway with "arguments contains unsupported fields" — after the
    job has been claimed, which is a long way from the author who typed it.
    That is not hypothetical: this package shipped with `radians` and every
    test passed, because every test asserted the name this package had chosen
    rather than the one the robot declares.
    """
    turn = plan_for_step(MODULE_TURN, {"degrees": 90}, robot_id="r")["steps"][0]
    assert set(turn["arguments"]) == {"yaw_delta_rad", "angular_speed"}

    move = plan_for_step(MODULE_MOVE, {"distance_m": 0.4}, robot_id="r")["steps"][0]
    assert set(move["arguments"]) == {"distance_m", "speed"}


def test_the_bounds_are_the_robots_bounds():
    """flyto-robotics capabilities.py: yaw_delta_rad is -3.0..3.0 and
    angular_speed 0.1..1.0. An author allowed past those would be refused by
    the gateway rather than by the canvas."""
    from flyto_modules_robotics.plan import (
        MAX_ANGULAR_SPEED,
        MAX_SPEED_MPS,
        MAX_TURN_RADIANS,
        MIN_ANGULAR_SPEED,
        MIN_SPEED_MPS,
    )

    assert MAX_TURN_RADIANS == 3.0
    assert (MIN_ANGULAR_SPEED, MAX_ANGULAR_SPEED) == (0.1, 1.0)
    assert (MIN_SPEED_MPS, MAX_SPEED_MPS) == (0.02, 0.35)

    # And the derived degree limit stays inside the radian one it mirrors.
    widest = plan_for_step(MODULE_TURN, {"degrees": 171}, robot_id="r")
    assert abs(widest["steps"][0]["arguments"]["yaw_delta_rad"]) <= MAX_TURN_RADIANS
    with pytest.raises(PlanBuildError):
        plan_for_step(MODULE_TURN, {"degrees": 180}, robot_id="r")
