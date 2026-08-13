"""Adversarial plans derived only from the lower trusted catalog."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from flyto_modules_robotics.catalog import parse_capability_catalog
from flyto_modules_robotics.plan import PlanBuildError
from flyto_modules_robotics.steps import (
    MODULE_MOVE,
    MODULE_STOP,
    MODULE_TURN,
    plan_for_step,
    trusted_plan_for_step,
)


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _argument(name, minimum, maximum, default=None):
    value = {
        "name": name,
        "type": "number",
        "required": default is None,
        "description": name,
        "minimum": minimum,
        "maximum": maximum,
    }
    if default is not None:
        value["default"] = default
    return value


def _entry(capability_id, runtime_name, arguments, *, safe_stop=True):
    return {
        "capability_id": capability_id,
        "runtime_name": runtime_name,
        "version": "1.0.0",
        "executor_kind": "flyto-robotics",
        "approval_status": "APPROVED",
        "safety_class": "controlled",
        "requires_safe_stop": safe_stop,
        "required_observations": [],
        "required_resources": ["base_controller"],
        "required_permissions": ["robot.motion"],
        "arguments": arguments,
        "schema_hash": _hash(arguments),
    }


def catalog(
    *,
    distance_min=-0.6,
    distance_max=0.6,
    yaw_min=-1.0,
    yaw_max=1.0,
    speed_default=0.11,
    stop_default=0.0,
):
    entries = [
        _entry(
            "robotics.motion.move_relative@1",
            "move_relative",
            [
                _argument("distance_m", distance_min, distance_max),
                _argument("speed", 0.04, 0.2, speed_default),
            ],
        ),
        _entry(
            "robotics.motion.turn_relative@1",
            "turn_relative",
            [
                _argument("yaw_delta_rad", yaw_min, yaw_max),
                _argument("angular_speed", 0.2, 0.5, 0.3),
            ],
        ),
        _entry(
            "robotics.safety.safe_stop@1",
            "safe_stop",
            [_argument("seconds", 0.0, 10.0, stop_default)],
            safe_stop=False,
        ),
    ]
    return parse_capability_catalog(
        {
            "contract_version": "flyto.robotics.capability-catalog.v1",
            "registry_revision": 1,
            "capabilities": entries,
            "contract_hash": _hash(entries),
        }
    )


def test_move_uses_lower_names_defaults_and_tighter_bounds():
    trusted = catalog(distance_max=0.6, speed_default=0.11)
    plan = trusted_plan_for_step(
        MODULE_MOVE, {"distance_m": 0.6}, robot_id="r", catalog=trusted
    )
    assert plan["steps"][0]["arguments"] == {"distance_m": 0.6, "speed": 0.11}
    assert plan["steps"][-1]["capability"] == "safe_stop"

    with pytest.raises(PlanBuildError, match="trusted catalog maximum"):
        trusted_plan_for_step(
            MODULE_MOVE, {"distance_m": 0.61}, robot_id="r", catalog=trusted
        )


def test_canvas_directions_are_derived_before_asymmetric_catalog_validation():
    trusted = catalog(distance_min=-0.4, distance_max=0.7, yaw_min=-0.3, yaw_max=0.8)
    forward = trusted_plan_for_step(
        MODULE_MOVE, {"distance_m": 0.6}, robot_id="r", catalog=trusted
    )
    assert forward["steps"][0]["arguments"]["distance_m"] == 0.6
    with pytest.raises(PlanBuildError, match="minimum"):
        trusted_plan_for_step(
            MODULE_MOVE,
            {"distance_m": 0.5, "reverse": True},
            robot_id="r",
            catalog=trusted,
        )

    left = trusted_plan_for_step(
        MODULE_TURN, {"degrees": 40}, robot_id="r", catalog=trusted
    )
    assert left["steps"][0]["arguments"]["yaw_delta_rad"] > 0
    with pytest.raises(PlanBuildError, match="minimum"):
        trusted_plan_for_step(
            MODULE_TURN,
            {"degrees": 20, "clockwise": True},
            robot_id="r",
            catalog=trusted,
        )


def test_catalog_can_authorize_beyond_preview_constants_without_legacy_veto():
    trusted = catalog(distance_max=3.0)
    plan = trusted_plan_for_step(
        MODULE_MOVE, {"distance_m": 2.5}, robot_id="r", catalog=trusted
    )
    assert plan["steps"][0]["arguments"]["distance_m"] == 2.5


def test_missing_or_schema_drifted_capability_fails_instead_of_falling_back():
    trusted = catalog()
    without_move = parse_capability_catalog(
        {
            "contract_version": trusted.contract_version,
            "registry_revision": 1,
            "capabilities": [],
            "contract_hash": _hash([]),
        }
    )
    with pytest.raises(PlanBuildError, match="does not provide"):
        trusted_plan_for_step(
            MODULE_MOVE, {"distance_m": 0.2}, robot_id="r", catalog=without_move
        )

    drifted_entries = [
        _entry(
            "robotics.motion.turn_relative@1",
            "turn_relative",
            [
                _argument("yaw_delta_rad", -1.0, 1.0),
                _argument("angular_velocity", 0.2, 0.5, 0.3),
            ],
        ),
        _entry(
            "robotics.safety.safe_stop@1",
            "safe_stop",
            [_argument("seconds", 0.0, 10.0, 0.0)],
            safe_stop=False,
        ),
    ]
    drifted = parse_capability_catalog(
        {
            "contract_version": trusted.contract_version,
            "registry_revision": 1,
            "capabilities": drifted_entries,
            "contract_hash": _hash(drifted_entries),
        }
    )
    with pytest.raises(PlanBuildError, match="incompatible"):
        trusted_plan_for_step(
            MODULE_TURN, {"degrees": 30}, robot_id="r", catalog=drifted
        )


def test_manually_replaced_mutable_catalog_projection_is_not_trusted():
    trusted = catalog()
    mutable_move = replace(
        trusted.capabilities[0],
        arguments=tuple(dict(argument) for argument in trusted.capabilities[0].arguments),
    )
    mutable_catalog = replace(
        trusted,
        capabilities=(mutable_move, *trusted.capabilities[1:]),
    )

    with pytest.raises(PlanBuildError, match="trusted capability catalog"):
        trusted_plan_for_step(
            MODULE_MOVE,
            {"distance_m": 0.2},
            robot_id="r",
            catalog=mutable_catalog,
        )


def test_motion_requires_catalog_safe_stop_and_rejects_new_required_arguments():
    entries = [
        _entry(
            "robotics.motion.move_relative@1",
            "move_relative",
            [
                _argument("distance_m", -1.0, 1.0),
                _argument("speed", 0.04, 0.2, 0.1),
                _argument("new_required", 0.0, 1.0),
            ],
        )
    ]
    incomplete = parse_capability_catalog(
        {
            "contract_version": "flyto.robotics.capability-catalog.v1",
            "registry_revision": 1,
            "capabilities": entries,
            "contract_hash": _hash(entries),
        }
    )
    with pytest.raises(PlanBuildError, match="safe_stop"):
        trusted_plan_for_step(
            MODULE_MOVE, {"distance_m": 0.2}, robot_id="r", catalog=incomplete
        )

    stop_arguments = [_argument("seconds", 0.0, 10.0, 0.0)]
    entries.append(
        _entry(
            "robotics.safety.safe_stop@1",
            "safe_stop",
            stop_arguments,
            safe_stop=False,
        )
    )
    unsupported = parse_capability_catalog(
        {
            "contract_version": "flyto.robotics.capability-catalog.v1",
            "registry_revision": 1,
            "capabilities": entries,
            "contract_hash": _hash(entries),
        }
    )
    with pytest.raises(PlanBuildError, match="unsupported required"):
        trusted_plan_for_step(
            MODULE_MOVE, {"distance_m": 0.2}, robot_id="r", catalog=unsupported
        )


def test_turn_and_stop_are_bounded_by_the_catalog():
    trusted = catalog()
    with pytest.raises(PlanBuildError, match="trusted catalog maximum"):
        trusted_plan_for_step(
            MODULE_TURN, {"degrees": 60}, robot_id="r", catalog=trusted
        )
    with pytest.raises(PlanBuildError, match="trusted catalog maximum"):
        trusted_plan_for_step(
            MODULE_STOP, {"seconds": 11}, robot_id="r", catalog=trusted
        )


def test_public_plan_for_step_keeps_the_offline_preview_contract():
    plan = plan_for_step(MODULE_TURN, {"degrees": 30}, robot_id="r")
    assert plan["steps"][0]["arguments"]["yaw_delta_rad"] == pytest.approx(
        30 * 3.141592653589793 / 180
    )


def test_preview_direction_flags_are_strict_booleans():
    with pytest.raises(PlanBuildError, match="reverse must be a boolean"):
        plan_for_step(
            MODULE_MOVE, {"distance_m": 0.2, "reverse": "false"}, robot_id="r"
        )


def test_trusted_canvas_controls_are_literal_booleans():
    trusted = catalog()
    for module_id, params, control in (
        (MODULE_MOVE, {"distance_m": 0.2, "reverse": 1}, "reverse"),
        (MODULE_TURN, {"degrees": 20, "clockwise": "false"}, "clockwise"),
    ):
        with pytest.raises(PlanBuildError, match=f"{control} must be a boolean"):
            trusted_plan_for_step(module_id, params, robot_id="r", catalog=trusted)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
@pytest.mark.parametrize(
    ("module_id", "name"),
    [(MODULE_MOVE, "distance_m"), (MODULE_TURN, "degrees")],
)
def test_trusted_motion_rejects_zero_negative_and_non_finite_canvas_amounts(
    module_id, name, value
):
    with pytest.raises(PlanBuildError):
        trusted_plan_for_step(
            module_id, {name: value}, robot_id="r", catalog=catalog()
        )


@pytest.mark.parametrize(
    ("module_id", "params"),
    [
        (MODULE_MOVE, {"distance_m": 0.2, "speed": float("nan")}),
        (MODULE_MOVE, {"distance_m": 0.2, "speed": float("inf")}),
        (MODULE_TURN, {"degrees": 20, "angular_speed": float("nan")}),
        (MODULE_STOP, {"seconds": float("inf")}),
    ],
)
def test_trusted_optional_numbers_must_be_finite(module_id, params):
    with pytest.raises(PlanBuildError, match="finite"):
        trusted_plan_for_step(module_id, params, robot_id="r", catalog=catalog())


def test_motion_appends_immediate_catalog_stop_without_requiring_a_default():
    trusted = catalog()
    raw = []
    for capability in trusted.capabilities:
        arguments = [dict(argument) for argument in capability.arguments]
        if capability.runtime_name == "safe_stop":
            arguments[0].pop("default")
        raw.append(
            _entry(
                capability.capability_id,
                capability.runtime_name,
                arguments,
                safe_stop=capability.requires_safe_stop,
            )
        )
    no_stop_default = parse_capability_catalog(
        {
            "contract_version": trusted.contract_version,
            "registry_revision": 1,
            "capabilities": raw,
            "contract_hash": _hash(raw),
        }
    )
    plan = trusted_plan_for_step(
        MODULE_MOVE, {"distance_m": 0.2}, robot_id="r", catalog=no_stop_default
    )
    assert plan["steps"][-1]["arguments"] == {"seconds": 0.0}
    with pytest.raises(PlanBuildError, match="seconds.*incompatible"):
        trusted_plan_for_step(MODULE_STOP, {}, robot_id="r", catalog=no_stop_default)


def test_appended_stop_validates_literal_zero_and_never_falls_back():
    trusted = catalog()
    entries = []
    for capability in trusted.capabilities:
        arguments = [dict(argument) for argument in capability.arguments]
        if capability.runtime_name == "safe_stop":
            arguments[0]["minimum"] = 0.1
            arguments[0]["default"] = 0.1
        entries.append(
            _entry(
                capability.capability_id,
                capability.runtime_name,
                arguments,
                safe_stop=capability.requires_safe_stop,
            )
        )
    incompatible = parse_capability_catalog(
        {
            "contract_version": trusted.contract_version,
            "registry_revision": 1,
            "capabilities": entries,
            "contract_hash": _hash(entries),
        }
    )
    with pytest.raises(PlanBuildError, match="minimum"):
        trusted_plan_for_step(
            MODULE_MOVE, {"distance_m": 0.2}, robot_id="r", catalog=incompatible
        )


def test_missing_bounds_defaults_and_id_runtime_drift_fail_closed():
    trusted = catalog()

    def rebuilt(change):
        entries = []
        for capability in trusted.capabilities:
            arguments = [dict(argument) for argument in capability.arguments]
            runtime = capability.runtime_name
            capability_id = capability.capability_id
            runtime, capability_id, arguments = change(
                runtime, capability_id, arguments
            )
            entries.append(
                _entry(
                    capability_id,
                    runtime,
                    arguments,
                    safe_stop=capability.requires_safe_stop,
                )
            )
        return parse_capability_catalog(
            {
                "contract_version": trusted.contract_version,
                "registry_revision": 1,
                "capabilities": entries,
                "contract_hash": _hash(entries),
            }
        )

    def missing_bound(runtime, capability_id, arguments):
        if runtime == "move_relative":
            arguments[0].pop("maximum")
        return runtime, capability_id, arguments

    def missing_default(runtime, capability_id, arguments):
        if runtime == "move_relative":
            arguments[1].pop("default")
            arguments[1]["required"] = True
        return runtime, capability_id, arguments

    def runtime_drift(runtime, capability_id, arguments):
        if runtime == "move_relative":
            runtime = "move_relative_v2"
        return runtime, capability_id, arguments

    for changed in (rebuilt(missing_bound), rebuilt(missing_default), rebuilt(runtime_drift)):
        with pytest.raises(PlanBuildError, match="incompatible"):
            trusted_plan_for_step(
                MODULE_MOVE, {"distance_m": 0.2}, robot_id="r", catalog=changed
            )


def test_preview_and_trusted_apis_are_separate_and_exported():
    import flyto_modules_robotics as package

    assert package.plan_for_step is plan_for_step
    assert package.trusted_plan_for_step is trusted_plan_for_step
    assert plan_for_step(MODULE_MOVE, {"distance_m": 0.2}, robot_id="r")
    with pytest.raises(PlanBuildError, match="trusted capability catalog"):
        trusted_plan_for_step(MODULE_MOVE, {"distance_m": 0.2}, robot_id="r")
