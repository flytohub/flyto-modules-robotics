"""The mobile robot's HMI declaration (``flyto.resource-presentation.v1``).

The schema is the copy flyto-cloud validates with
(``services/device/schemas``, sha256 ``cede95aa...``, the same file flyto-app
published before it added ``request_examples`` / ``check_kinds``); its sha256
is pinned here and in Cloud, so a one-sided edit fails. The block's canonical
sha256 is pinned too.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from flyto_modules_robotics import presentation
from flyto_modules_robotics.capabilities import SPECS

BLOCK_CANONICAL_SHA256 = "36d57fe241854b2f653fa5a029ae54f641abb0db8bbd2146393d747c7e04da22"
SCHEMA_FILE_SHA256 = "cede95aa69b7e16c52b3cf3bfdc7004bb7c74f06e5669463c2dd5b871b3a5736"

# The live channels flyto-robotics (0.8.0, ``live_telemetry.CHANNELS``)
# declares and samples, and their payload fields. flyto-robotics
# ``tests/test_live_telemetry.py`` pins the same table; change both together.
ROBOT_CHANNEL_FIELDS = {
    "power.battery": {"percent", "voltage_v"},
    "pose.planar": {
        "x", "y", "heading_deg", "frame", "goal_x", "goal_y",
        "view_x_min", "view_x_max", "view_y_min", "view_y_max",
    },
    "nav.goal": {"state", "distance_m", "progress_pct", "goal_x", "goal_y", "reason"},
}
NAVIGATION_STATES = ("idle", "navigating", "arrived", "blocked", "cancelled", "failed")

# The shape flyto-robotics ``adapter_provider._manifest`` publishes. Cloud's
# host adds ``connection`` before upload.
MANIFEST = {
    "contract": "flyto.resource-manifest.v1",
    "resource_id": "tb3-01",
    "resource_type": "robot",
    "display_name": "ROS 2 robot (demo)",
    "revision": 1,
    "adapter": {"adapter_id": "ros2.generic", "version": "1.0.0", "provider": "Flyto2 Robotics"},
    "deployment_mode": "real",
    "capability_ids": ["motion.navigate", "vision.observe"],
    "capability_contracts": [],
    "settings": [],
    "telemetry_channels": [{"channel_id": channel} for channel in ROBOT_CHANNEL_FIELDS],
    "observed_at": "2026-10-12T08:00:00+00:00",
    "contract_hash": "",
}


def _sources(node):
    """Every SourceRef in the declaration, of any form."""
    if isinstance(node, dict):
        if {"channel", "resource", "capability"} & node.keys() and len(node) <= 2:
            yield node
        for value in node.values():
            yield from _sources(value)
    elif isinstance(node, list):
        for item in node:
            yield from _sources(item)


def test_block_and_schema_are_the_pinned_shared_versions():
    block = presentation.presentation_block()
    assert hashlib.sha256(presentation.canonical_bytes(block)).hexdigest() == BLOCK_CANONICAL_SHA256
    schema_bytes = presentation.schema_text().encode("utf-8")
    assert hashlib.sha256(schema_bytes).hexdigest() == SCHEMA_FILE_SHA256


def test_block_is_valid_against_the_schema_and_within_the_size_cap():
    jsonschema = pytest.importorskip("jsonschema", reason="install the dev extra to validate the schema")
    schema = json.loads(presentation.schema_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(presentation.presentation_block())
    assert len(presentation.canonical_bytes(presentation.presentation_block())) <= presentation.MAX_CANONICAL_BYTES


def test_every_source_is_one_the_robot_resource_really_carries():
    capabilities = {spec.capability_id for spec in SPECS}
    sources = list(_sources(presentation.presentation_block()))
    assert sources
    for source in sources:
        if source.get("channel") == presentation.CONNECTION_CHANNEL:
            # The host's link status, declared by Cloud's execution host.
            assert source == {"channel": presentation.CONNECTION_CHANNEL, "field": "state"}
        elif "channel" in source:
            # A channel the robot runtime declares, and a field it fills.
            assert source["field"] in ROBOT_CHANNEL_FIELDS[source["channel"]], source
        elif "capability" in source:
            assert source["capability"] in capabilities
        else:
            assert source["resource"] in {"presence.state", "deployment_mode"}


def test_the_mirrored_channel_table_is_the_packs_own():
    assert presentation.ROBOT_CHANNEL_FIELDS == {
        key: frozenset(value) for key, value in ROBOT_CHANNEL_FIELDS.items()
    }
    assert presentation.NAVIGATION_STATES == NAVIGATION_STATES


def _panels():
    return {panel["id"]: panel for panel in presentation.presentation_block()["panels"]}


def test_the_robot_shows_its_live_values():
    panels = _panels()
    battery = panels["battery"]
    assert battery["kind"] == "gauge"
    assert battery["source"] == {"channel": "power.battery", "field": "percent"}
    assert battery["range"] == {"min": 0, "max": 100} and battery["unit"] == "%"
    assert [rule["tone"] for rule in battery["severity_map"]] == ["refused", "attention"]
    assert panels["voltage"]["source"] == {"channel": "power.battery", "field": "voltage_v"}
    assert panels["voltage"]["kind"] == "readout" and panels["voltage"]["unit"] == "V"

    pose = panels["position"]
    assert pose["kind"] == "position2d"
    assert {pose[axis]["field"] for axis in ("x", "y", "heading", "goal_x", "goal_y")} == {
        "x", "y", "heading_deg", "goal_x", "goal_y"
    }
    assert {pose["plane"]["x"]["min"]["field"], pose["plane"]["y"]["max"]["field"]} == {
        "view_x_min", "view_y_max"
    }

    distance = panels["goal_distance"]
    assert distance["kind"] == "readout" and distance["priority"] == "hero"
    assert distance["source"] == {"channel": "nav.goal", "field": "distance_m"}
    assert distance["when"]["in"] == ["navigating"]
    progress = panels["goal_progress"]
    assert progress["kind"] == "progress" and progress["range"] == {"min": 0, "max": 100}
    assert panels["navigation_state"]["source"] == {"channel": "nav.goal", "field": "state"}


def test_only_kinds_the_app_registry_renders():
    rendered = {"readout", "gauge", "state", "progress", "list", "position2d", "joints", "media", "alert"}
    assert {panel["kind"] for panel in presentation.presentation_block()["panels"]} <= rendered


def test_no_field_cloud_does_not_validate_yet():
    # flyto-app's newer schema adds these; Cloud's copy (pinned above) does not.
    text = presentation.canonical_bytes(presentation.presentation_block()).decode("utf-8")
    for absent in ("check_kinds", "request_examples"):
        assert absent not in text, absent


def test_state_options_cover_exactly_each_source_vocabulary():
    vocab = {
        "presence.state": set(presentation.PRESENCE_STATES),
        "deployment_mode": set(presentation.DEPLOYMENT_MODES),
        presentation.CONNECTION_CHANNEL: set(presentation.CONNECTION_STATES),
        "nav.goal": set(NAVIGATION_STATES),
    }
    for panel in presentation.presentation_block()["panels"]:
        if panel["kind"] != "state":
            continue
        source = panel["source"]
        key = source.get("resource") or source.get("channel")
        expected = vocab.get(key, {True, False})
        assert {option["value"] for option in panel["states"]} == expected, panel["id"]


def test_link_alert_names_only_known_connection_states():
    alert = _panels()["link_lost"]
    assert set(alert["when"]["in"]) <= set(presentation.CONNECTION_STATES)


def test_the_pack_offers_its_block_to_the_robot_runtime():
    """flyto-robotics finds the block by entry point ``robotics`` in this group."""
    import tomllib
    from pathlib import Path

    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text("utf-8"))
    group = pyproject["project"]["entry-points"]["flyto2.resource_presentations"]
    assert group == {"robotics": "flyto_modules_robotics.presentation:presentation_block"}


def test_block_is_a_copy_and_the_constant_is_read_only():
    first = presentation.presentation_block()
    first["panels"].clear()
    assert presentation.presentation_block()["panels"]
    with pytest.raises(TypeError):
        presentation.MOBILE_ROBOT_PRESENTATION["schema"] = "x"  # type: ignore[index]


@pytest.mark.parametrize("extensions", [None, [], ["module_pack", "transport"], "presentation", b"presentation", 3])
def test_manifest_without_the_extension_is_unchanged(extensions):
    before = presentation.canonical_bytes(MANIFEST)
    result = presentation.manifest_with_presentation(MANIFEST, extensions)
    # What an older Cloud receives: the same keys and the same canonical hash.
    assert result == MANIFEST
    assert hashlib.sha256(presentation.canonical_bytes(result)).hexdigest() == hashlib.sha256(before).hexdigest()
    assert presentation.canonical_bytes(MANIFEST) == before  # input untouched


def test_manifest_carries_the_block_only_when_asked():
    result = presentation.manifest_with_presentation(MANIFEST, ["module_pack", "presentation"])
    assert result["presentation"] == presentation.presentation_block()
    assert {key: value for key, value in result.items() if key != "presentation"} == MANIFEST
    assert "presentation" not in MANIFEST
