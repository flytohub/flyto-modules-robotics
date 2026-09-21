"""Canonical robotics workflow output for the external adapter architecture."""

from __future__ import annotations

import pytest

from flyto_modules_robotics.capability_request import (
    CAPABILITY_ADVANCE,
    CAPABILITY_HALT,
    CAPABILITY_REQUEST_VERSION,
    CAPABILITY_RETREAT,
    CAPABILITY_ROTATE,
    capability_request_for_step,
)
from flyto_modules_robotics.plan import PlanBuildError
from flyto_modules_robotics.steps import MODULE_MOVE, MODULE_STOP, MODULE_TURN


def test_forward_move_becomes_motion_advance():
    request = capability_request_for_step(
        MODULE_MOVE,
        {"distance_m": 0.4},
        resource_id="tb3-1",
    )
    assert request == {
        "contract_version": CAPABILITY_REQUEST_VERSION,
        "resource_id": "tb3-1",
        "capability_id": CAPABILITY_ADVANCE,
        "arguments": {"distance_m": 0.4, "speed_mps": pytest.approx(0.12)},
        "goal": "move forward 0.40 m then stop safely",
    }


def test_reverse_move_becomes_motion_retreat_with_positive_distance():
    request = capability_request_for_step(
        MODULE_MOVE,
        {"distance_m": 0.4, "reverse": True},
        resource_id="tb3-1",
    )
    assert request["capability_id"] == CAPABILITY_RETREAT
    assert request["arguments"]["distance_m"] == pytest.approx(0.4)
    assert request["arguments"]["speed_mps"] > 0


def test_turn_becomes_motion_rotate_with_signed_radians():
    left = capability_request_for_step(
        MODULE_TURN, {"degrees": 90}, resource_id="tb3-1"
    )
    right = capability_request_for_step(
        MODULE_TURN,
        {"degrees": 90, "clockwise": True},
        resource_id="tb3-1",
    )
    assert left["capability_id"] == CAPABILITY_ROTATE
    assert left["arguments"]["yaw_radians"] > 0
    assert right["arguments"]["yaw_radians"] < 0


def test_stop_becomes_motion_halt_without_gateway_specific_arguments():
    request = capability_request_for_step(
        MODULE_STOP, {"seconds": 2}, resource_id="tb3-1"
    )
    assert request["capability_id"] == CAPABILITY_HALT
    assert request["arguments"] == {}


def test_request_names_commanded_resource_not_execution_host():
    request = capability_request_for_step(
        MODULE_MOVE,
        {"distance_m": 0.2},
        resource_id="tb3-1",
    )
    text = repr(request).lower()
    assert request["resource_id"] == "tb3-1"
    assert "host" not in text
    assert "gateway" not in text
    assert "token" not in text
    assert "8766" not in text
    assert "robot_id" not in request


def test_missing_commanded_resource_fails_closed():
    with pytest.raises(PlanBuildError, match="commanded resource"):
        capability_request_for_step(
            MODULE_MOVE,
            {"distance_m": 0.2},
            resource_id="",
        )


def test_unknown_step_is_not_claimed():
    assert (
        capability_request_for_step(
            "browser.click",
            {"selector": "#go"},
            resource_id="tb3-1",
        )
        is None
    )
