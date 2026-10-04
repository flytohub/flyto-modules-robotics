"""Authored parameters become bounded requests; out-of-bounds is refused, never clamped."""

from __future__ import annotations

import math

import pytest

from flyto_modules_robotics.capability_request import (
    CAPABILITY_REQUEST_VERSION,
    CapabilityRequestError,
    capability_request_for_step,
)


def request(module_id, params, resource_id="tb3-1"):
    return capability_request_for_step(module_id, params, resource_id=resource_id)


def test_advance_request_states_the_adapter_default_speed():
    assert request("robotics.advance", {"distance_m": 0.4}) == {
        "contract_version": CAPABILITY_REQUEST_VERSION,
        "resource_id": "tb3-1",
        "capability_id": "motion.advance",
        "arguments": {"distance_m": 0.4, "speed_mps": 0.12},
    }


def test_retreat_uses_its_own_default_and_positive_distance():
    made = request("robotics.retreat", {"distance_m": 0.4})
    assert made["capability_id"] == "motion.retreat"
    assert made["arguments"] == {"distance_m": 0.4, "speed_mps": 0.10}


def test_rotate_is_signed_radians():
    assert request("robotics.rotate", {"yaw_radians": -1.2})["arguments"] == {
        "yaw_radians": -1.2
    }


def test_navigate_optional_heading_is_omitted_when_absent():
    assert request("robotics.navigate", {"x": 1.5, "y": -2})["arguments"] == {
        "x": 1.5,
        "y": -2.0,
    }
    assert request("robotics.navigate", {"x": 0, "y": 0, "yaw_radians": 3.0})[
        "arguments"
    ]["yaw_radians"] == 3.0


@pytest.mark.parametrize(
    ("module_id", "capability_id"),
    [
        ("robotics.halt", "motion.halt"),
        ("robotics.observe", "vision.observe"),
        ("robotics.map", "sensing.map"),
    ],
)
def test_argument_free_capabilities(module_id, capability_id):
    made = request(module_id, {})
    assert made["capability_id"] == capability_id
    assert made["arguments"] == {}


@pytest.mark.parametrize(
    ("module_id", "params"),
    [
        ("robotics.advance", {"distance_m": 0.05}),
        ("robotics.advance", {"distance_m": 2.0, "speed_mps": 0.25}),
        ("robotics.advance", {"distance_m": 1.0, "speed_mps": 0.02}),
        ("robotics.retreat", {"distance_m": 2.0, "speed_mps": 0.20}),
        ("robotics.rotate", {"yaw_radians": math.pi}),
        ("robotics.rotate", {"yaw_radians": -math.pi}),
        ("robotics.navigate", {"x": 1000, "y": -1000}),
    ],
)
def test_bounds_are_inclusive(module_id, params):
    made = request(module_id, params)
    for name, value in params.items():
        assert made["arguments"][name] == value


@pytest.mark.parametrize(
    ("module_id", "params", "name"),
    [
        ("robotics.advance", {"distance_m": 0.049}, "distance_m"),
        ("robotics.advance", {"distance_m": 2.01}, "distance_m"),
        ("robotics.advance", {"distance_m": 1.0, "speed_mps": 0.26}, "speed_mps"),
        ("robotics.advance", {"distance_m": 1.0, "speed_mps": 0.01}, "speed_mps"),
        # A retreat at advance speed is refused, not slowed down.
        ("robotics.retreat", {"distance_m": 1.0, "speed_mps": 0.25}, "speed_mps"),
        ("robotics.rotate", {"yaw_radians": 3.2}, "yaw_radians"),
        ("robotics.rotate", {"yaw_radians": -3.2}, "yaw_radians"),
        ("robotics.navigate", {"x": 1000.5, "y": 0}, "x"),
        ("robotics.navigate", {"x": 0, "y": 0, "yaw_radians": 4}, "yaw_radians"),
    ],
)
def test_out_of_bounds_is_refused_never_clamped(module_id, params, name):
    with pytest.raises(CapabilityRequestError, match=name):
        request(module_id, params)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True, "0.4", None])
def test_non_numbers_are_refused(value):
    with pytest.raises(CapabilityRequestError, match="distance_m"):
        request("robotics.advance", {"distance_m": value})


@pytest.mark.parametrize(
    ("module_id", "params", "name"),
    [
        ("robotics.advance", {}, "distance_m"),
        ("robotics.retreat", {"speed_mps": 0.1}, "distance_m"),
        ("robotics.rotate", {}, "yaw_radians"),
        ("robotics.mark_place", {}, "place"),
    ],
)
def test_required_arguments(module_id, params, name):
    with pytest.raises(CapabilityRequestError, match=f"{name} is required"):
        request(module_id, params)


def test_navigate_without_a_whole_target_says_what_it_needs():
    with pytest.raises(CapabilityRequestError, match="x and y are required unless a place"):
        request("robotics.navigate", {"x": 1.0})


@pytest.mark.parametrize(
    ("module_id", "params"),
    [
        ("robotics.advance", {"distance_m": 0.4, "speed": 0.1}),
        ("robotics.advance", {"distance_m": 0.4, "reverse": True}),
        ("robotics.halt", {"dwell_s": 1}),
        ("robotics.observe", {"host": "10.0.0.2"}),
    ],
)
def test_undeclared_parameters_are_refused(module_id, params):
    with pytest.raises(CapabilityRequestError, match="does not take"):
        request(module_id, params)


def test_resource_id_is_routing_not_an_argument():
    made = request("robotics.halt", {"resource_id": "tb3-2"})
    assert made["arguments"] == {}


@pytest.mark.parametrize("resource_id", ["", "   ", "x" * 129, None])
def test_commanded_resource_is_required_and_bounded(resource_id):
    with pytest.raises(CapabilityRequestError, match="commanded resource"):
        request("robotics.halt", {}, resource_id=resource_id)


def test_unknown_steps_are_not_claimed():
    assert request("browser.click", {}) is None
    assert request("robotics.move", {"distance_m": 0.4}) is None


def test_parameters_must_be_an_object():
    with pytest.raises(CapabilityRequestError, match="object"):
        request("robotics.halt", ["distance_m"])


def test_request_names_commanded_resource_and_nothing_about_a_host():
    text = repr(request("robotics.advance", {"distance_m": 0.2})).lower()
    for forbidden in ("host", "gateway", "token", "8766", "url"):
        assert forbidden not in text
