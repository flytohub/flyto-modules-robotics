"""The declarations must satisfy the real flyto-core, not a stand-in for it.

`test_registration.py` substitutes a fake `core.modules.registry` so the plugin
can be tested without flyto-core installed. That is the right call for a
zero-dependency package -- and it is also how this shipped broken.

flyto-core added an identifier rule to `register_module`:

    ^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$

`@` is not in it. This package declared `robotics.motion.move_relative@1`, and
the rejection is not per-module: flyto-core rolls the whole plugin back, so all
three of `robotics.move`, `robotics.turn` and `robotics.stop` disappeared from
the workflow builder at once. Measured against a real registry before the fix:
`Failed to load plugin robotics: provides_capability must be a safe bounded
identifier`, zero modules loaded. After: 443 modules, plugin `robotics` loaded.

Three things had to line up for that to go unnoticed, and each is a reason this
file exists rather than another assertion inside the existing suite:

  1. the rule landed in flyto-core after these strings did, so nothing changed
     here on the day it broke;
  2. every test injected a registry that does not apply the rule;
  3. the CI job that installs flyto-core runs only on tag push, and HEAD was
     never tagged.

Skips when flyto-core is absent, which is the normal state of a bare
`pip install -e .` checkout. A skip says "not checked here". A pass would say
"checked and fine", and that substitution is the whole defect.
"""
from __future__ import annotations

import re

import pytest

from flyto_modules_robotics.modules import (
    CAPABILITY_MOVE,
    CAPABILITY_STOP,
    CAPABILITY_TURN,
)

DECLARED = (CAPABILITY_MOVE, CAPABILITY_TURN, CAPABILITY_STOP)


def test_the_declared_capabilities_carry_no_version_suffix():
    """Runs without flyto-core, so the regression is caught in a bare checkout.

    The rule is restated here rather than imported, deliberately: importing it
    would make this test pass whenever flyto-core relaxed, and the point is to
    notice a divergence, not to inherit one.
    """
    identifier = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")

    offenders = [c for c in DECLARED if not identifier.fullmatch(c) or len(c) > 96]

    assert not offenders, (
        "flyto-core refuses these and rolls the whole plugin back, so every "
        f"robotics step leaves the builder together: {offenders}"
    )


def test_the_rule_this_restates_is_still_the_rule_core_applies():
    """Guard against the restatement above drifting from flyto-core's source."""
    core = pytest.importorskip(
        "core.modules.registry.core", reason="flyto-core is not installed here"
    )
    from pathlib import Path

    source = Path(core.__file__).read_text(encoding="utf-8")

    assert r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$" in source, (
        "flyto-core's identifier rule changed; the pattern restated in this "
        "file no longer matches it and must be updated deliberately"
    )


def test_the_real_registry_loads_the_plugin_and_lists_all_three_steps():
    """The end the user sees: three steps present in the builder's catalog."""
    registry_module = pytest.importorskip(
        "core.modules.registry", reason="flyto-core is not installed here"
    )

    registry = registry_module.get_registry()
    metadata = registry.get_all_metadata()

    listed = sorted(k for k in metadata if str(k).startswith("robotics."))
    assert listed == ["robotics.move", "robotics.stop", "robotics.turn"], (
        "the robotics plugin did not register; flyto-core rolls a plugin back "
        f"entirely when any one declaration is refused. Listed: {listed}"
    )
    assert {metadata[k].get("provides_capability") for k in listed} == set(DECLARED)
