"""Stable robotics step identity helpers."""

from __future__ import annotations

from flyto_modules_robotics.steps import MODULE_IDS, is_robotics_step, step_module_id


def test_the_steps_are_stable():
    assert MODULE_IDS == (
        "robotics.advance",
        "robotics.retreat",
        "robotics.rotate",
        "robotics.halt",
        "robotics.navigate",
        "robotics.observe",
        "robotics.map",
        "robotics.places",
        "robotics.mark_place",
    )


def test_is_robotics_step_claims_only_owned_steps():
    for module_id in MODULE_IDS:
        assert is_robotics_step(module_id)
    assert not is_robotics_step("robotics.move")
    assert not is_robotics_step("browser.click")
    assert not is_robotics_step("")
    assert not is_robotics_step(None)


def test_step_module_id_accepts_supported_serialized_spellings():
    for key in ("module", "module_id", "action", "type"):
        assert step_module_id({key: "robotics.halt"}) == "robotics.halt"
    assert step_module_id({"module": "  robotics.rotate  "}) == "robotics.rotate"
    assert step_module_id({"module": "", "module_id": "robotics.map"}) == "robotics.map"
    assert step_module_id({}) == ""
    assert step_module_id(None) == ""
