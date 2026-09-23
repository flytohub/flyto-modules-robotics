"""Canonical robotics authoring contract for external equipment."""

from __future__ import annotations

import math

import pytest

from flyto_modules_robotics.capability_request import (
    CAPABILITY_ADVANCE,
    CAPABILITY_HALT,
    CAPABILITY_REQUEST_VERSION,
    CAPABILITY_RETREAT,
    CAPABILITY_ROTATE,
    MAX_ADVANCE_SPEED_MPS,
    MAX_DISTANCE_M,
    MAX_RETREAT_SPEED_MPS,
    MIN_DISTANCE_M,
    CapabilityRequestError,
    capability_request_for_step,
)
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


@pytest.mark.parametrize("distance", [MIN_DISTANCE_M, MAX_DISTANCE_M])
def test_move_accepts_generic_adapter_distance_boundaries(distance):
    request = capability_request_for_step(
        MODULE_MOVE, {"distance_m": distance}, resource_id="tb3-1"
    )
    assert request["arguments"]["distance_m"] == distance


@pytest.mark.parametrize("distance", [0.01, 2.01])
def test_move_refuses_distance_outside_generic_adapter_contract(distance):
    with pytest.raises(CapabilityRequestError, match="distance_m"):
        capability_request_for_step(
            MODULE_MOVE, {"distance_m": distance}, resource_id="tb3-1"
        )


def test_forward_and_reverse_speed_limits_match_adapter_contract():
    forward = capability_request_for_step(
        MODULE_MOVE,
        {"distance_m": 0.4, "speed": MAX_ADVANCE_SPEED_MPS},
        resource_id="tb3-1",
    )
    assert forward["arguments"]["speed_mps"] == MAX_ADVANCE_SPEED_MPS

    reverse = capability_request_for_step(
        MODULE_MOVE,
        {
            "distance_m": 0.4,
            "reverse": True,
            "speed": MAX_RETREAT_SPEED_MPS,
        },
        resource_id="tb3-1",
    )
    assert reverse["arguments"]["speed_mps"] == MAX_RETREAT_SPEED_MPS

    with pytest.raises(CapabilityRequestError, match="speed"):
        capability_request_for_step(
            MODULE_MOVE,
            {
                "distance_m": 0.4,
                "reverse": True,
                "speed": MAX_RETREAT_SPEED_MPS + 0.01,
            },
            resource_id="tb3-1",
        )


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
    assert left["arguments"]["yaw_radians"] == pytest.approx(math.pi / 2)
    assert right["arguments"]["yaw_radians"] == pytest.approx(-math.pi / 2)


def test_turn_accepts_adapter_pi_boundary_and_refuses_beyond_it():
    request = capability_request_for_step(
        MODULE_TURN, {"degrees": 180}, resource_id="tb3-1"
    )
    assert request["arguments"]["yaw_radians"] == pytest.approx(math.pi)
    with pytest.raises(CapabilityRequestError, match="degrees"):
        capability_request_for_step(
            MODULE_TURN, {"degrees": 181}, resource_id="tb3-1"
        )


def test_stop_is_exact_motion_halt_contract():
    request = capability_request_for_step(MODULE_STOP, {}, resource_id="tb3-1")
    assert request == {
        "contract_version": CAPABILITY_REQUEST_VERSION,
        "resource_id": "tb3-1",
        "capability_id": CAPABILITY_HALT,
        "arguments": {},
        "goal": "halt robot motion safely",
    }


@pytest.mark.parametrize(
    ("module_id", "params", "field"),
    [
        (MODULE_MOVE, {"distance_m": 0.4, "angular_speed": 0.2}, "angular_speed"),
        (MODULE_TURN, {"degrees": 90, "angular_speed": 0.2}, "angular_speed"),
        (MODULE_STOP, {"seconds": 2}, "seconds"),
    ],
)
def test_retired_gateway_parameters_fail_closed(module_id, params, field):
    with pytest.raises(CapabilityRequestError, match=field):
        capability_request_for_step(module_id, params, resource_id="tb3-1")


@pytest.mark.parametrize(
    ("module_id", "params", "field"),
    [
        (MODULE_MOVE, {}, "distance_m"),
        (MODULE_MOVE, {"distance_m": 0.4, "reverse": "false"}, "reverse"),
        (MODULE_MOVE, {"distance_m": float("nan")}, "distance_m"),
        (MODULE_TURN, {}, "degrees"),
        (MODULE_TURN, {"degrees": 90, "clockwise": 1}, "clockwise"),
        (MODULE_TURN, {"degrees": float("inf")}, "degrees"),
    ],
)
def test_invalid_authoring_values_fail_closed(module_id, params, field):
    with pytest.raises(CapabilityRequestError, match=field):
        capability_request_for_step(module_id, params, resource_id="tb3-1")


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


def test_missing_or_oversized_commanded_resource_fails_closed():
    with pytest.raises(CapabilityRequestError, match="commanded resource"):
        capability_request_for_step(
            MODULE_MOVE, {"distance_m": 0.2}, resource_id=""
        )
    with pytest.raises(CapabilityRequestError, match="128"):
        capability_request_for_step(
            MODULE_MOVE, {"distance_m": 0.2}, resource_id="r" * 129
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
