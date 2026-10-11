"""The mobile robot's HMI declaration (``flyto.resource-presentation.v1``).

The schema is the copy flyto-cloud validates with and flyto-app published
(``docs/contracts``, commit f6dd4f3c); its sha256 is pinned here and in both,
so a one-sided edit fails. The block's canonical sha256 is pinned too.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from flyto_modules_robotics import presentation
from flyto_modules_robotics.capabilities import SPECS

BLOCK_CANONICAL_SHA256 = "1e1b6563e9d58ae2275736f77e53f1795a3e3dfb7ce313c63d0fac863221e8df"
SCHEMA_FILE_SHA256 = "1c600a65996ed336b18986e6e7d71e6e75698e912f877c7a946d441286193c80"

# The shape flyto-robotics ``adapter_provider._manifest`` publishes today: no
# telemetry channel of its own. Cloud's host adds ``connection`` before upload.
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
    "telemetry_channels": [],
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
        if "channel" in source:
            # The only channel a ROS 2 robot resource carries: the host's link status.
            assert source == {"channel": presentation.CONNECTION_CHANNEL, "field": "state"}
        elif "capability" in source:
            assert source["capability"] in capabilities
        else:
            assert source["resource"] in {"presence.state", "deployment_mode"}


def test_no_panel_claims_a_channel_the_robot_does_not_publish():
    text = presentation.canonical_bytes(presentation.presentation_block()).decode("utf-8")
    for absent in ("battery", "pose", "nav.goal", "distance", "position2d", "gauge"):
        assert absent not in text, absent


def test_state_options_cover_exactly_each_source_vocabulary():
    vocab = {
        "presence.state": set(presentation.PRESENCE_STATES),
        "deployment_mode": set(presentation.DEPLOYMENT_MODES),
        presentation.CONNECTION_CHANNEL: set(presentation.CONNECTION_STATES),
    }
    for panel in presentation.presentation_block()["panels"]:
        if panel["kind"] != "state":
            continue
        source = panel["source"]
        key = source.get("resource") or source.get("channel")
        expected = vocab.get(key, {True, False})
        assert {option["value"] for option in panel["states"]} == expected, panel["id"]


def test_link_alert_names_only_known_connection_states():
    alert = next(p for p in presentation.presentation_block()["panels"] if p["kind"] == "alert")
    assert set(alert["when"]["in"]) <= set(presentation.CONNECTION_STATES)


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
