"""Stable robotics authoring-node identity helpers."""

from __future__ import annotations

from flyto_modules_robotics.steps import (
    MODULE_IDS,
    MODULE_MOVE,
    MODULE_STOP,
    MODULE_TURN,
    is_robotics_step,
    step_module_id,
)


def test_three_authoring_nodes_are_stable():
    assert MODULE_IDS == (MODULE_MOVE, MODULE_TURN, MODULE_STOP)
    assert MODULE_IDS == ("robotics.move", "robotics.turn", "robotics.stop")


def test_is_robotics_step_claims_only_owned_nodes():
    assert is_robotics_step(MODULE_MOVE)
    assert is_robotics_step(MODULE_TURN)
    assert is_robotics_step(MODULE_STOP)
    assert not is_robotics_step("browser.click")
    assert not is_robotics_step("")
    assert not is_robotics_step(None)


def test_step_module_id_accepts_supported_serialized_spellings():
    for key in ("module", "module_id", "action", "type"):
        assert step_module_id({key: MODULE_MOVE}) == MODULE_MOVE
    assert step_module_id({"module": "  robotics.turn  "}) == MODULE_TURN
    assert step_module_id({"module": "", "module_id": MODULE_STOP}) == MODULE_STOP
    assert step_module_id({}) == ""
    assert step_module_id(None) == ""
