"""Named places: two steps, and navigation by name judged where the place is.

The places live on the execution host (flyto-robotics ``places.py``); this
pack only declares the steps, bounds their arguments and carries the
adapter's facts into the step output. What is pinned here:

* ``robotics.places`` is read-only and declares its list as a ``places``
  artifact a host can cite; ``robotics.mark_place`` writes the host's places
  file and moves nothing.
* A navigation names exactly one target: a place, or x and y.
* An unknown place comes back refused, with the known names, and nothing in
  this pack turns that into motion.
* The arrival evidence is judged against the coordinates the place resolved
  to, never against nothing and never against a different place's.
"""

from __future__ import annotations

import asyncio

import pytest
from contract_rules import judge, validate_contract

from flyto_modules_robotics.capabilities import (
    RECOVERY_REPORT_KEYS,
    ABSOLUTE_MEASURE_OPS,
    MAX_PLACE_NAME_LENGTH,
    PLACE_EFFECT,
    RESOLVED_ARGUMENTS,
    SPECS_BY_MODULE,
)
from flyto_modules_robotics.capability_request import (
    CapabilityRequestError,
    capability_request_for_step,
)
from flyto_modules_robotics.modules import (
    HOST_DISPATCHER_CONTEXT_KEY,
    build_modules,
    registrable_contract,
    resolved_arguments,
)

LOBBY = {"name": "Lobby", "frame": "map", "x": 1.5, "y": -2.25, "yaw": 0.5}
LOBBY_RESOLVED = {"x": 1.5, "y": -2.25, "yaw_radians": 0.5}


def request(module_id, params):
    return capability_request_for_step(module_id, params, resource_id="robot-1")


class StandInModule:
    module_id = ""

    def __init__(self, params, context):
        self.params = params
        self.context = context
        self.validate_params()

    def validate_params(self):
        pass


def _register(module_id, contract=None, **metadata):
    def decorate(cls):
        cls._registered_metadata = {"module_id": module_id, "contract": contract, **metadata}
        return cls

    return decorate


class Adapter:
    """A host dispatcher whose adapter answers with a fixed record."""

    _flyto_runtime_opaque = True

    def __init__(self, outcome, evidence, detail=""):
        self.record = {"call_id": "c1", "outcome": outcome, "detail": detail,
                       "adapter_evidence": evidence}
        self.requests = []

    async def invoke(self, dispatched):
        self.requests.append(dispatched)
        return dict(self.record)


def run(module_id, params, adapter):
    cls = dict(build_modules(StandInModule, _register))[module_id]
    step = cls(params, {"resource_id": "robot-1", HOST_DISPATCHER_CONTEXT_KEY: adapter})
    return asyncio.run(step.execute())


# --- the two steps ----------------------------------------------------------------


def test_places_is_read_only_and_declares_its_list_as_a_places_artifact():
    spec = SPECS_BY_MODULE["robotics.places"]
    assert spec.capability_id == "places.list"
    assert spec.params_schema == {}
    contract = spec.contract
    assert (contract["actuates"], contract["safety_class"], contract["effects"]) == (
        False, "read_only", []
    )
    assert contract["artifacts"] == [
        {"kind": "places", "media_types": ["application/json"], "max_bytes": 256 * 1024}
    ]


def test_mark_place_writes_the_places_file_and_moves_nothing():
    spec = SPECS_BY_MODULE["robotics.mark_place"]
    assert spec.capability_id == "places.mark"
    contract = spec.contract
    assert contract["actuates"] is False
    assert contract["safety_class"] == "controlled"
    assert contract["requires_safe_stop"] is False and contract["cancellable"] is False
    assert contract["effects"] == [PLACE_EFFECT] == ["places.written"]
    assert contract["requires"] == ["map.localized"]
    assert contract["evidence"] == []
    assert spec.params_schema["place"]["required"] is True


@pytest.mark.parametrize("module_id", ["robotics.places", "robotics.mark_place", "robotics.navigate"])
def test_the_contracts_hold_under_the_rules_and_core(module_id):
    spec = SPECS_BY_MODULE[module_id]
    validate_contract(dict(spec.contract), spec.params_schema)
    core = pytest.importorskip("core.capability_contract")
    registered = registrable_contract(
        spec.contract,
        frozenset(getattr(core, "OPTIONAL_FIELDS", ())),
        frozenset(getattr(core, "MEASURE_OPS", ())),
        frozenset(getattr(core, "RECOVERY_FIELDS", RECOVERY_REPORT_KEYS)),
    )
    core.validate_contract(registered, dict(spec.params_schema))


def test_an_older_core_registers_places_without_its_artifact():
    """Before 2.36.0 there are no artifacts; the step still registers."""
    reduced = registrable_contract(SPECS_BY_MODULE["robotics.places"].contract, frozenset(), frozenset())
    assert "artifacts" not in reduced and reduced["actuates"] is False


# --- one target --------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"place": "Lobby", "x": 1.0, "y": 2.0},
        {"place": "Lobby", "x": 1.0},
        {"place": "Lobby", "yaw_radians": 0.2},
        {"x": 1.0},
        {"y": 1.0, "yaw_radians": 0.2},
        {},
    ],
)
def test_place_and_coordinates_are_exclusive(params):
    with pytest.raises(CapabilityRequestError):
        request("robotics.navigate", params)


def test_either_target_alone_is_a_request():
    assert request("robotics.navigate", {"place": " 一樓大廳 "})["arguments"] == {"place": "一樓大廳"}
    assert request("robotics.navigate", {"x": 1, "y": 2, "yaw_radians": 0.1})["arguments"] == {
        "x": 1.0, "y": 2.0, "yaw_radians": 0.1,
    }
    # A blank coordinate from a form is not a target.
    assert request("robotics.navigate", {"place": "Lobby", "x": None})["arguments"] == {"place": "Lobby"}


@pytest.mark.parametrize("module_id", ["robotics.navigate", "robotics.mark_place"])
@pytest.mark.parametrize(
    "name", ["", "  ", "x" * (MAX_PLACE_NAME_LENGTH + 1), "a\nb", "a\x85b", "a b", 7]
)
def test_bad_place_names_are_refused(module_id, name):
    with pytest.raises(CapabilityRequestError, match="place"):
        request(module_id, {"place": name})


def test_a_name_is_counted_in_characters():
    name = "廳" * MAX_PLACE_NAME_LENGTH
    assert request("robotics.mark_place", {"place": name})["arguments"] == {"place": name}


# --- what the step reports ------------------------------------------------------------


def test_places_step_returns_the_list():
    adapter = Adapter("completed", {"places": [LOBBY], "map_id": "default", "artifacts": [
        {"kind": "places", "media_type": "application/json", "data_base64": "W10="}
    ]})
    result = run("robotics.places", {}, adapter)

    assert result["ok"] is True
    assert result["places"] == [LOBBY]
    assert adapter.requests == [{"resource_id": "robot-1", "capability_id": "places.list", "arguments": {}}]
    # The artifact's bytes stay with the host; the output keeps its digest.
    assert "data_base64" not in result["execution"]["adapter_evidence"]["artifacts"][0]


def test_mark_place_step_returns_the_saved_place():
    adapter = Adapter("completed", {"place": LOBBY, "replaced": None, "map_id": "default"})
    result = run("robotics.mark_place", {"place": "Lobby"}, adapter)

    assert result["ok"] is True
    assert result["place"] == LOBBY
    assert adapter.requests[0]["arguments"] == {"place": "Lobby"}


def test_an_unknown_place_is_refused_with_the_known_names():
    adapter = Adapter(
        "refused",
        {"known_places": ["Lobby", "Dock"]},
        detail="unknown place 'Kitchen'; known places: Lobby, Dock",
    )
    result = run("robotics.navigate", {"place": "Kitchen"}, adapter)

    assert result["ok"] is False
    assert result["error_code"] == "EXTERNAL_CAPABILITY_REFUSED"
    assert result["known_places"] == ["Lobby", "Dock"]
    assert "Lobby, Dock" in result["error"]
    assert RESOLVED_ARGUMENTS not in result
    # One request, the navigation itself: nothing retries it as a motion.
    assert len(adapter.requests) == 1


def _navigated(place="Lobby", resolved=None, named="Lobby"):
    return Adapter("completed", {
        "navigation_target": {"frame": "map", **(resolved or LOBBY_RESOLVED), "place": named},
        RESOLVED_ARGUMENTS: dict(resolved or LOBBY_RESOLVED),
    })


def test_a_navigation_by_place_reports_the_arguments_it_resolved_to():
    adapter = _navigated()
    result = run("robotics.navigate", {"place": "lobby"}, adapter)

    assert result["ok"] is True
    # The request says what was asked; the resolution sits beside it.
    assert result["capability_request"]["arguments"] == {"place": "lobby"}
    assert result[RESOLVED_ARGUMENTS] == {"place": "lobby", **LOBBY_RESOLVED}


@pytest.mark.parametrize(
    "evidence",
    [
        {},
        {RESOLVED_ARGUMENTS: LOBBY_RESOLVED},
        {"navigation_target": {"frame": "map", **LOBBY_RESOLVED, "place": "Lobby"}},
        # Resolved for another place than the one asked.
        {"navigation_target": {"frame": "map", **LOBBY_RESOLVED, "place": "Dock"},
         RESOLVED_ARGUMENTS: LOBBY_RESOLVED},
        {"navigation_target": {"frame": "map", "place": "Lobby"},
         RESOLVED_ARGUMENTS: {"x": float("nan"), "y": 0.0}},
        {"navigation_target": {"frame": "map", "place": "Lobby"},
         RESOLVED_ARGUMENTS: {"x": True, "y": 0.0}},
    ],
)
def test_nothing_is_resolved_that_the_adapter_did_not_report_for_this_place(evidence):
    assert resolved_arguments({"place": "Lobby"}, {"adapter_evidence": evidence}) is None


def test_a_navigation_by_coordinates_is_never_overlaid():
    record = {"adapter_evidence": {RESOLVED_ARGUMENTS: {"x": 9.0, "y": 9.0}}}
    assert resolved_arguments({"x": 1.0, "y": 2.0}, record) is None


# --- the arrival is judged where the place is --------------------------------------------


def _core_judge():
    core = pytest.importorskip("core.capability_contract")
    if not ABSOLUTE_MEASURE_OPS <= set(getattr(core, "MEASURE_OPS", ())):
        pytest.skip("installed flyto-core predates the absolute measure ops (2.38.0)")
    return core.judge


@pytest.fixture(params=["vendored", "core"])
def arrival_judge(request):
    return judge if request.param == "vendored" else _core_judge()


def _settled_at(x, y, yaw):
    pose = {"frame": "map", "x": x, "y": y, "yaw": yaw}
    return {"after": pose, "settled": pose}


def _verdicts(judge_fn, arguments, observations):
    evidence = SPECS_BY_MODULE["robotics.navigate"].contract["evidence"]
    return {item["kind"]: judge_fn(item, arguments, observations) for item in evidence}


def test_the_arrival_is_judged_against_the_resolved_place(arrival_judge):
    result = run("robotics.navigate", {"place": "Lobby"}, _navigated())
    judged = result[RESOLVED_ARGUMENTS]

    at_lobby = _verdicts(arrival_judge, judged, _settled_at(1.6, -2.2, 0.55))
    elsewhere = _verdicts(arrival_judge, judged, _settled_at(0.0, 0.0, 0.5))
    facing_away = _verdicts(arrival_judge, judged, _settled_at(1.5, -2.25, -2.5))

    assert all(verdict["usable"] for verdict in at_lobby.values())
    assert elsewhere["arrival"]["usable"] is False
    assert facing_away["arrival"]["usable"] is True
    assert facing_away["arrival.heading"]["usable"] is False


def test_without_the_resolution_the_arrival_fails_closed(arrival_judge):
    """The authored arguments of a call by place name no coordinates."""
    verdicts = _verdicts(arrival_judge, {"place": "Lobby"}, _settled_at(1.5, -2.25, 0.5))
    assert verdicts["arrival"]["usable"] is False


def test_core_measures_the_distance_to_the_resolved_place():
    core_judge = _core_judge()
    result = run("robotics.navigate", {"place": "Lobby"}, _navigated())
    arrival = SPECS_BY_MODULE["robotics.navigate"].contract["evidence"][0]

    verdict = core_judge(arrival, result[RESOLVED_ARGUMENTS], _settled_at(1.5, -1.85, 0.5))

    assert verdict["usable"] is False
    assert verdict["measured"] == pytest.approx(0.4)
    assert verdict["allowed"] == pytest.approx(0.3)
