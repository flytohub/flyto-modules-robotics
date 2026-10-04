"""Provider artifacts, declared recovery, and the Open-RMF fleet pack.

Covers the flyto-core 2.36.0 optional contract keys this pack declares
(``role``, ``artifacts``, ``recovery``, ``expected_duration_ms``), how a step
reports a declared recovery and keeps artifact bytes out of its output, and
the ``fleet`` pack. Where flyto-core's capability host is installed the steps
run through it end to end with fake adapters; nothing contacts a robot, a
fleet or a network.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest
from contract_rules import ContractInvalid, validate_contract

import flyto_modules_robotics as pkg
from flyto_modules_robotics import fleet_pack
from flyto_modules_robotics.capabilities import (
    ALL_SPECS_BY_MODULE,
    DETOUR_CAPABILITIES,
    FLEET_SPECS,
    FLEET_SPECS_BY_MODULE,
    OPTIONAL_CONTRACT_KEYS,
    SPECS,
    SPECS_BY_MODULE,
)
from flyto_modules_robotics.modules import (
    HOST_DISPATCHER_CONTEXT_KEY,
    build_fleet_modules,
    build_modules,
)
from flyto_modules_robotics.recovery import SECTORS, recovery_for, sector_clearance

FLEET_TABLE = {
    "fleet.navigate": "motion.navigate_to_waypoint",
    "fleet.dock": "motion.dock",
    "fleet.load": "transport.load",
    "fleet.unload": "transport.unload",
}


class StandInModule:
    module_id = ""

    def __init__(self, params, context):
        self.params = params
        self.context = context
        self.validate_params()

    def validate_params(self):
        pass


def fake_register_module(module_id, contract=None, **metadata):
    metadata = {"module_id": module_id, "contract": contract, **metadata}

    def decorate(cls):
        cls._registered_metadata = metadata
        return cls

    return decorate


ALL_KEYS = frozenset(OPTIONAL_CONTRACT_KEYS)
# flyto-core 2.38.0's measure ops.
ALL_OPS = frozenset(
    ("distance", "along", "delta", "angle_delta", "abs_angle_delta", "distance_to", "angle_to")
)


def robotics(optional_keys=ALL_KEYS, measure_ops=ALL_OPS):
    return dict(
        build_modules(
            StandInModule, fake_register_module, optional_keys=optional_keys, measure_ops=measure_ops
        )
    )


def fleet(optional_keys=ALL_KEYS, measure_ops=ALL_OPS):
    return dict(
        build_fleet_modules(
            StandInModule, fake_register_module, optional_keys=optional_keys, measure_ops=measure_ops
        )
    )


class Dispatcher:
    _flyto_runtime_opaque = True

    def __init__(self, record):
        self.record = record
        self.requests = []

    async def invoke(self, request):
        self.requests.append(request)
        return dict(self.record)


def run_step(cls, params, record, resource="robot-1"):
    dispatcher = Dispatcher(record)
    node = cls(params, {"resource_id": resource, HOST_DISPATCHER_CONTEXT_KEY: dispatcher})
    return asyncio.run(node.execute()), dispatcher


# -- the declared optional keys -----------------------------------------------


def test_halt_is_the_safe_stop_role():
    contract = SPECS_BY_MODULE["robotics.halt"].contract
    assert contract["role"] == "safe_stop"
    assert [spec.module_id for spec in SPECS if "role" in spec.contract] == ["robotics.halt"]


def test_captures_declare_the_artifacts_the_adapter_returns():
    photo = SPECS_BY_MODULE["robotics.observe"].contract["artifacts"]
    drawn = SPECS_BY_MODULE["robotics.map"].contract["artifacts"]
    assert photo == [{"kind": "photo", "media_types": ["image/jpeg"], "max_bytes": 2_000_000}]
    assert drawn == [
        {"kind": "map", "media_types": ["image/jpeg", "image/png"], "max_bytes": 8 * 1024 * 1024}
    ]


@pytest.mark.parametrize("module_id", ["robotics.advance", "robotics.retreat"])
def test_straight_motions_declare_the_detour_recovery(module_id):
    recovery = SPECS_BY_MODULE[module_id].contract["recovery"]
    assert recovery["capabilities"] == ["motion.rotate", "motion.advance", "motion.retreat"]
    assert recovery["observe"] == "recovery_context"
    assert "0.35 m" in recovery["guidance"] and len(recovery["guidance"]) <= 500
    # Every substitute is a capability this pack provides.
    provided = {spec.capability_id for spec in SPECS}
    assert set(recovery["capabilities"]) <= provided
    assert DETOUR_CAPABILITIES == recovery["capabilities"]


@pytest.mark.parametrize("spec", (*SPECS, *FLEET_SPECS), ids=lambda spec: spec.module_id)
def test_every_contract_satisfies_the_vendored_2_36_rules(spec):
    validate_contract(dict(spec.contract), spec.params_schema)


@pytest.mark.parametrize("spec", (*SPECS, *FLEET_SPECS), ids=lambda spec: spec.module_id)
def test_every_contract_is_flyto_core_normalized(spec):
    module = pytest.importorskip("core.capability_contract")
    if "role" not in getattr(module, "OPTIONAL_FIELDS", ()):
        pytest.skip("installed flyto-core predates the 2.36.0 optional keys")
    assert module.validate_contract(dict(spec.contract), dict(spec.params_schema)) == spec.contract


def test_vendored_rules_reject_a_bad_optional_key():
    advance = SPECS_BY_MODULE["robotics.advance"]
    halt = SPECS_BY_MODULE["robotics.halt"]
    with pytest.raises(ContractInvalid):
        validate_contract({**advance.contract, "role": "safe_stop"}, advance.params_schema)
    with pytest.raises(ContractInvalid):
        validate_contract({**halt.contract, "role": "brake"}, halt.params_schema)
    with pytest.raises(ContractInvalid):
        validate_contract({**advance.contract, "recovery": {"capabilities": []}}, advance.params_schema)
    with pytest.raises(ContractInvalid):
        validate_contract(
            {**advance.contract, "expected_duration_ms": True}, advance.params_schema
        )


def test_an_older_core_registers_without_the_newer_keys_and_logs_once(caplog):
    with caplog.at_level(logging.WARNING):
        steps = robotics(optional_keys=frozenset())
    for module_id, cls in steps.items():
        registered = cls._registered_metadata["contract"]
        assert not (OPTIONAL_CONTRACT_KEYS & set(registered))
        expected = {
            key: value
            for key, value in SPECS_BY_MODULE[module_id].contract.items()
            if key not in OPTIONAL_CONTRACT_KEYS
        }
        assert registered == expected
    warned = [item.getMessage() for item in caplog.records if "2.36.0" in item.getMessage()]
    assert len(warned) == 1


def test_an_older_core_registers_navigate_without_its_arrival_and_logs_once(caplog):
    older = ALL_OPS - {"distance_to", "angle_to"}
    with caplog.at_level(logging.WARNING):
        steps = robotics(measure_ops=older)
    for module_id, cls in steps.items():
        registered = cls._registered_metadata["contract"]
        spec = SPECS_BY_MODULE[module_id].contract
        if module_id == "robotics.navigate":
            assert registered == {**spec, "evidence": []}
        else:
            assert registered == spec
    warned = [item.getMessage() for item in caplog.records if "2.38.0" in item.getMessage()]
    assert len(warned) == 1


def test_a_current_core_registers_the_spec_row_unchanged():
    for module_id, cls in robotics().items():
        assert cls._registered_metadata["contract"] == SPECS_BY_MODULE[module_id].contract
        assert cls._registered_metadata["version"] == pkg.__version__


# -- recovery ------------------------------------------------------------------


def cloud_sector_clearance(sweep):
    """flyto-cloud services/space_tasks/detour.py, transcribed."""
    nearest = {name: None for name, _, _ in SECTORS}
    start = float(sweep["angle_min_rad"])
    step = float(sweep["angle_increment_rad"])
    for index, distance in enumerate(list(sweep["ranges_m"])):
        if not isinstance(distance, (int, float)) or isinstance(distance, bool):
            continue
        degrees = math.degrees(
            math.atan2(math.sin(start + index * step), math.cos(start + index * step))
        )
        for name, low, high in SECTORS:
            angle = degrees + 360.0 if high > 180.0 and degrees < 0 else degrees
            if low <= angle <= high and (nearest[name] is None or distance < nearest[name]):
                nearest[name] = round(float(distance), 2)
    return nearest


def test_sectors_equal_clouds_detour_on_random_sweeps():
    import random

    rng = random.Random(20261004)
    for _ in range(300):
        count = rng.randint(8, 720)
        sweep = {
            "angle_min_rad": rng.uniform(-math.pi, 0.0),
            "angle_increment_rad": 2 * math.pi / count,
            "ranges_m": [
                None if rng.random() < 0.1 else round(rng.uniform(0.1, 6.0), 3)
                for _ in range(count)
            ],
        }
        assert sector_clearance(sweep) == cloud_sector_clearance(sweep)


def test_an_unreadable_sweep_has_no_sectors():
    assert set(sector_clearance(None).values()) == {None}
    assert set(sector_clearance({"ranges_m": [1.0]}).values()) == {None}
    assert sector_clearance(
        {"angle_min_rad": 0.0, "angle_increment_rad": 0.1, "ranges_m": [math.inf]}
    )["ahead"] is None


SWEEP = {
    "angle_min_rad": -math.pi,
    "angle_increment_rad": math.pi / 2,
    "ranges_m": [2.0, 0.6, 0.33, 1.2],
}


def blocked_record(evidence):
    return {"call_id": "c", "outcome": "failed", "detail": "obstacle_blocked", "adapter_evidence": evidence}


def test_a_blocked_advance_reports_the_declared_recovery_with_the_adapter_s_facts():
    spec = SPECS_BY_MODULE["robotics.advance"]
    context = {
        "reason": "obstacle_blocked",
        "requested_distance_m": 0.5,
        "travelled_m": 0.12,
        "remaining_m": 0.38,
        "minimum_range_at_stop_m": 0.33,
        "clearance_floor_m": 0.35,
        "sweep": SWEEP,
    }
    recovery = recovery_for(spec, blocked_record({"recovery_context": context}))
    assert recovery["capabilities"] == DETOUR_CAPABILITIES
    assert recovery["guidance"] == spec.contract["recovery"]["guidance"]
    facts = recovery["context"]
    assert facts["reason"] == "obstacle_blocked"
    assert (facts["travelled_m"], facts["remaining_m"]) == (0.12, 0.38)
    assert facts["travel_sector"] == "ahead"
    assert facts["sectors"]["ahead"] == 0.33
    assert facts["sectors"]["right"] == 0.6
    assert facts["sectors"]["left"] == 1.2
    assert facts["sectors"]["behind"] == 2.0


def test_an_older_adapter_s_motion_outcome_still_gives_the_distances():
    spec = SPECS_BY_MODULE["robotics.retreat"]
    outcome = {
        "reason": "obstacle_blocked",
        "start_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
        "final_pose": {"x": -0.1, "y": 0.02, "yaw": 0.0},
        "requested_distance_m": 0.25,
        "minimum_range_at_stop_m": 0.3,
        "clearance_floor_m": 0.35,
    }
    facts = recovery_for(spec, blocked_record({"motion_outcome": outcome}))["context"]
    assert facts["travelled_m"] == pytest.approx(0.1)
    assert facts["remaining_m"] == pytest.approx(0.15)
    assert facts["travel_sector"] == "behind"
    assert set(facts["sectors"].values()) == {None}


@pytest.mark.parametrize("outcome", ["completed", "refused", "cancelled"])
def test_only_a_failure_or_timeout_offers_recovery(outcome):
    spec = SPECS_BY_MODULE["robotics.advance"]
    assert recovery_for(spec, {"outcome": outcome, "adapter_evidence": {}}) is None


def test_a_capability_without_declared_recovery_offers_none():
    assert recovery_for(SPECS_BY_MODULE["robotics.rotate"], blocked_record({})) is None


def test_the_failed_step_carries_its_recovery():
    cls = robotics()["robotics.advance"]
    result, _ = run_step(
        cls,
        {"distance_m": 0.5},
        blocked_record({"recovery_context": {"reason": "obstacle_blocked", "sweep": SWEEP}}),
    )
    assert result["ok"] is False
    assert result["error_code"] == "EXTERNAL_CAPABILITY_FAILED"
    assert result["recovery"]["context"]["sectors"]["ahead"] == 0.33
    rotated, _ = run_step(robotics()["robotics.rotate"], {"yaw_radians": 1.0}, blocked_record({}))
    assert "recovery" not in rotated


# -- artifacts in a step's output ---------------------------------------------


def test_a_step_output_keeps_the_artifact_digest_not_its_bytes():
    picture = b"\xff\xd8 photo bytes"
    encoded = base64.b64encode(picture).decode("ascii")
    record = {
        "call_id": "c",
        "outcome": "completed",
        "adapter_evidence": {
            "capture": {"kind": "photo"},
            "artifacts": [{"kind": "photo", "media_type": "image/jpeg", "data_base64": encoded}],
        },
    }
    result, _ = run_step(robotics()["robotics.observe"], {}, record)
    assert result["ok"] is True
    assert result["execution"]["adapter_evidence"]["artifacts"] == [
        {
            "kind": "photo",
            "media_type": "image/jpeg",
            "bytes": len(picture),
            "sha256": hashlib.sha256(picture).hexdigest(),
        }
    ]
    assert encoded not in json.dumps(result)


@pytest.mark.parametrize(
    ("capture", "field"),
    [
        ({"kind": "photo", "media_type": "image/jpeg"}, "data"),
        ({"kind": "map", "width": 2, "height": 2, "resolution": 0.05}, "cells"),
    ],
)
def test_a_step_output_drops_the_legacy_capture_bytes_too(capture, field):
    raw = b"\xff\xd8 legacy capture bytes"
    encoded = base64.b64encode(raw).decode("ascii")
    record = {
        "call_id": "c",
        "outcome": "completed",
        "adapter_evidence": {"capture": {**capture, f"{field}_base64": encoded}},
    }
    result, _ = run_step(robotics()["robotics.observe"], {}, record)
    kept = result["execution"]["adapter_evidence"]["capture"]
    assert encoded not in json.dumps(result)
    assert kept[f"{field}_bytes"] == len(raw)
    assert kept[f"{field}_sha256"] == hashlib.sha256(raw).hexdigest()
    assert kept["kind"] == capture["kind"]
    # The dispatcher's own record is left as it was.
    assert record["adapter_evidence"]["capture"][f"{field}_base64"] == encoded


# -- the fleet pack -------------------------------------------------------------


def test_the_fleet_pack_registers_four_steps_with_contracts():
    steps = fleet()
    assert {module_id: cls._registered_metadata["provides_capability"] for module_id, cls in steps.items()} == FLEET_TABLE
    for module_id, cls in steps.items():
        metadata = cls._registered_metadata
        spec = FLEET_SPECS_BY_MODULE[module_id]
        assert metadata["contract"] == spec.contract
        assert metadata["category"] == "fleet"
        assert metadata["params_schema"] == {"waypoint": spec.params_schema["waypoint"]}
        assert metadata["concurrent_safe"] is False
    assert not set(FLEET_TABLE) & set(SPECS_BY_MODULE)
    assert set(ALL_SPECS_BY_MODULE) == set(FLEET_TABLE) | set(SPECS_BY_MODULE)


@pytest.mark.parametrize("module_id", sorted(FLEET_TABLE))
def test_a_fleet_task_moves_but_cannot_promise_a_fleet_wide_stop(module_id):
    contract = FLEET_SPECS_BY_MODULE[module_id].contract
    assert contract["actuates"] is True
    assert contract["safety_class"] == "movement"
    # Open-RMF has no fleet-wide stop; the adapter refuses safe_stop.
    assert contract["requires_safe_stop"] is False
    assert contract["cancellable"] is True
    assert contract["expected_duration_ms"] == 600_000
    assert contract["evidence"] == []


def test_a_fleet_step_sends_its_waypoint_to_the_fleet_resource():
    cls = fleet()["fleet.navigate"]
    result, dispatcher = run_step(
        cls, {"waypoint": "  ward_3 "}, {"outcome": "completed"}, resource="fleet:tinyRobot"
    )
    assert result["ok"] is True
    assert dispatcher.requests == [
        {
            "resource_id": "fleet:tinyRobot",
            "capability_id": "motion.navigate_to_waypoint",
            "arguments": {"waypoint": "ward_3"},
        }
    ]


@pytest.mark.parametrize(
    "waypoint", ["", "   ", 7, None, "x" * 129, "ward\n3", ["ward_3"]]
)
def test_a_waypoint_that_is_not_bounded_text_is_refused(waypoint):
    with pytest.raises(pkg.CapabilityRequestError):
        pkg.capability_request_for_step(
            "fleet.dock", {"waypoint": waypoint}, resource_id="fleet:tinyRobot"
        )


def test_a_fleet_step_takes_no_distance():
    with pytest.raises(pkg.CapabilityRequestError, match="does not take"):
        pkg.capability_request_for_step(
            "fleet.navigate", {"waypoint": "a", "distance_m": 1.0}, resource_id="fleet:a"
        )


def test_the_fleet_entry_point_is_declared_and_described():
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    assert 'fleet = "flyto_modules_robotics.fleet_pack:register_fleet"' in pyproject
    assert fleet_pack.PACK_DESCRIPTION
    assert pkg.PACK_DESCRIPTION


# -- through flyto-core: the registry and the capability host -------------------


SCRIPT = """
import asyncio
import base64
import json
import sys

sys.path.insert(0, sys.argv[1])

from core.capability_host import CapabilityHost
from core.modules.base import BaseModule
from core.modules.registry import ModuleRegistry, register_module
from flyto_modules_robotics.modules import build_fleet_modules, build_modules


class Result:
    def __init__(self, call_id, outcome, evidence=None, detail=""):
        self.call_id, self.outcome = call_id, outcome
        self.evidence, self.detail = evidence or {}, detail


class Fleet:
    deployment_mode = "simulation"

    def __init__(self, resource_id):
        self.resource_id = resource_id
        self.calls = []

    def invoke(self, request):
        self.calls.append((request.capability_id, dict(request.arguments), request.deadline_seconds))
        return Result(request.call_id, "completed", {"rmf_task_id": "t-1", "rmf_status": "completed"})

    def cancel(self, call_id):
        return Result(call_id, "refused")

    def safe_stop(self):
        return Result("stop", "refused", detail="no fleet-wide stop")


class Robot:
    deployment_mode = "simulation"

    def __init__(self, resource_id):
        self.stops = 0

    def invoke(self, request):
        if request.capability_id == "vision.observe":
            jpeg = base64.b64encode(b"\\xff\\xd8 frame").decode("ascii")
            return Result(request.call_id, "completed", {
                "capture": {"kind": "photo", "media_type": "image/jpeg", "data_base64": jpeg},
                "artifacts": [{"kind": "photo", "media_type": "image/jpeg", "data_base64": jpeg}],
            })
        if request.capability_id == "motion.halt":
            return Result(request.call_id, "completed")
        return Result(request.call_id, "failed", {"recovery_context": {
            "reason": "obstacle_blocked", "requested_distance_m": 0.5, "travelled_m": 0.1,
            "remaining_m": 0.4, "sweep": {"angle_min_rad": 0.0, "angle_increment_rad": 0.1,
            "ranges_m": [0.3]}}}, "obstacle_blocked")

    def cancel(self, call_id):
        return Result(call_id, "cancelled")

    def safe_stop(self):
        self.stops += 1
        return Result("stop", "completed")

    def observe(self, phase="preflight", execution_id=None):
        return {"pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}}

    def wait_until_stationary(self, seconds):
        return {"stationary": True}


def step(module_id, params, host):
    cls = ModuleRegistry.get(module_id)
    node = cls(params, {"resource_id": host.resource_id, **host.context()})
    return asyncio.run(node.execute())


ModuleRegistry.clear()
try:
    build_modules(BaseModule, register_module)
    build_fleet_modules(BaseModule, register_module)
    fleet_host = CapabilityHost(adapter_id="open_rmf.fleet", resource_id="fleet:tinyRobot",
                                allow=["motion.navigate_to_waypoint"], adapter_factory=Fleet)
    navigate = step("fleet.navigate", {"waypoint": "ward_3"}, fleet_host)
    refused = step("fleet.load", {"waypoint": "ward_3"}, fleet_host)
    robot_host = CapabilityHost(adapter_id="ros2.generic", resource_id="robot-1",
                                allow=["motion.advance"], adapter_factory=Robot, settle_seconds=0)
    photo = step("robotics.observe", {}, robot_host)
    blocked = step("robotics.advance", {"distance_m": 0.5}, robot_host)
    halt = step("robotics.halt", {}, robot_host)
    print(json.dumps({
        "capabilities": {k: v for k, v in ModuleRegistry.capabilities().items()},
        "navigate": navigate, "refused": refused, "photo": photo,
        "blocked": blocked, "halt": halt,
        "fleet_records": fleet_host.records(), "robot_records": robot_host.records(),
    }, default=str))
finally:
    ModuleRegistry.clear()
"""


def test_core_capability_host_runs_both_packs_end_to_end():
    """The steps through flyto-core's own registry and capability host."""

    pytest.importorskip("core.capability_host")
    checkout_src = Path(__file__).resolve().parents[1] / "src"
    completed = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(checkout_src)],
        check=False,
        capture_output=True,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout.strip().splitlines()[-1])

    capabilities = observed["capabilities"]
    assert capabilities["motion.dock"] == ["fleet.dock"]
    # One contract per capability id: neither navigation shadows the other.
    assert capabilities["motion.navigate"] == ["robotics.navigate"]
    assert capabilities["motion.navigate_to_waypoint"] == ["fleet.navigate"]

    # The fleet: allowed navigate runs with the contract's deadline; a load the
    # run did not allow is refused by the host before the adapter sees it.
    navigate = observed["navigate"]
    assert navigate["ok"] is True
    fleet_record = observed["fleet_records"][0]
    assert fleet_record["capability_id"] == "motion.navigate_to_waypoint"
    assert fleet_record["arguments"] == {"waypoint": "ward_3"}
    assert fleet_record["contract_status"] == "declared"
    # The contract's expected_duration_ms, not a default: a fleet task queues.
    assert fleet_record["deadline_seconds"] == 600.0
    assert observed["refused"]["error_code"] == "EXTERNAL_CAPABILITY_REFUSED"
    assert observed["fleet_records"][1]["refused_by"] == "host"

    # The photo: the host kept the declared artifact.
    photo = observed["photo"]
    assert photo["ok"] is True
    kept = photo["execution"]["artifacts"]
    assert kept[0]["kind"] == "photo" and kept[0]["media_type"] == "image/jpeg"
    assert "data_base64" not in json.dumps(photo["execution"]["adapter_evidence"])

    # The blocked advance: failed, safe-stopped by the host, recovery offered.
    blocked = observed["blocked"]
    assert blocked["ok"] is False
    assert "safe_stop=completed" in blocked["execution"]["safety_recovery"]
    assert blocked["recovery"]["capabilities"] == DETOUR_CAPABILITIES
    assert blocked["recovery"]["context"]["sectors"]["ahead"] == 0.3

    # Halt is the safe_stop role: allowed although the run did not name it.
    assert observed["halt"]["ok"] is True
    halt_record = observed["robot_records"][-1]
    assert halt_record["policy"]["safe_stop_role"] is True
