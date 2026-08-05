"""Plans a workflow step builds, and the bounds it may not exceed."""

from __future__ import annotations

import pytest

from flyto_modules_robotics.plan import (
    MAX_DISTANCE_M,
    PlanBuildError,
    move_plan,
    run_request,
    stop_plan,
    turn_plan,
)

ROBOT = "flyto-tb3-lab-001"


def test_a_move_plan_always_ends_with_a_safe_stop():
    """The gateway refuses a moving plan that does not, so never build one."""
    plan = move_plan(robot_id=ROBOT, distance_m=0.4)
    assert [step["capability"] for step in plan["steps"]] == [
        "move_relative",
        "safe_stop",
    ]


def test_direction_is_a_choice_not_a_sign():
    """An author types a positive distance and picks a direction."""
    forward = move_plan(robot_id=ROBOT, distance_m=0.4)
    backward = move_plan(robot_id=ROBOT, distance_m=0.4, reverse=True)
    assert forward["steps"][0]["arguments"]["distance_m"] == 0.4
    assert backward["steps"][0]["arguments"]["distance_m"] == -0.4
    assert "forward" in forward["plan_id"] and "backward" in backward["plan_id"]


@pytest.mark.parametrize("distance", [0.0, -0.4, MAX_DISTANCE_M + 0.1, "far", True, None])
def test_a_distance_outside_the_bounds_is_refused_before_anything_moves(distance):
    with pytest.raises(PlanBuildError):
        move_plan(robot_id=ROBOT, distance_m=distance)


@pytest.mark.parametrize("speed", [0.0, 0.9, -0.1, "fast"])
def test_a_speed_outside_the_bounds_is_refused(speed):
    with pytest.raises(PlanBuildError):
        move_plan(robot_id=ROBOT, distance_m=0.4, speed=speed)


def test_a_missing_robot_id_is_refused():
    with pytest.raises(PlanBuildError):
        move_plan(robot_id="", distance_m=0.4)


def test_a_turn_plan_converts_degrees_and_keeps_the_stop():
    plan = turn_plan(robot_id=ROBOT, degrees=90)
    radians = plan["steps"][0]["arguments"]["radians"]
    assert 1.57 < radians < 1.58
    assert plan["steps"][-1]["capability"] == "safe_stop"
    assert turn_plan(robot_id=ROBOT, degrees=90, clockwise=True)["steps"][0][
        "arguments"
    ]["radians"] < 0


@pytest.mark.parametrize("degrees", [0, 361, "ninety"])
def test_a_turn_outside_the_bounds_is_refused(degrees):
    with pytest.raises(PlanBuildError):
        turn_plan(robot_id=ROBOT, degrees=degrees)


def test_a_stop_plan_is_only_the_stop():
    plan = stop_plan(robot_id=ROBOT, seconds=2.0)
    assert [step["capability"] for step in plan["steps"]] == ["safe_stop"]
    assert plan["steps"][0]["arguments"]["seconds"] == 2.0


def test_the_timeout_leaves_room_for_a_slow_floor():
    """An estimate is a seed; overrunning it a little is not a failure."""
    plan = move_plan(robot_id=ROBOT, distance_m=0.4, speed=0.12)
    assert plan["steps"][0]["timeout_seconds"] >= 0.4 / 0.12


def test_the_wrapper_carries_the_contract_the_gateway_expects():
    request = run_request(
        move_plan(robot_id=ROBOT, distance_m=0.4),
        request_id="wf-0001",
        requested_at="2026-08-05T00:00:00Z",
    )
    assert request["contract_version"] == "flyto.cloud.plan-run-request.v1"
    assert set(request) == {"contract_version", "request_id", "plan", "requested_at"}


def test_no_plan_ever_names_a_machine():
    """A host in a workflow would bind it to one robot, which is the duplication
    the capability model exists to remove."""
    text = repr(move_plan(robot_id=ROBOT, distance_m=0.4))
    for leak in ("http", "127.0.0.1", "localhost", ":8766"):
        assert leak not in text
