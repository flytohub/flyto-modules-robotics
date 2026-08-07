"""Registering with flyto-core, and surviving its absence."""

from __future__ import annotations

import asyncio

import logging

import flyto_modules_robotics as pkg
from flyto_modules_robotics.modules import build_modules


class StandInModule:
    """The shape flyto-core's BaseModule presents to a module class."""

    module_id = ""

    def __init__(self, params, context):
        self.params = params
        self.context = context
        self.validate_params()

    def validate_params(self):  # pragma: no cover - overridden
        pass


def fake_register_module(**metadata):
    """Stands in for flyto-core's decorator, recording what it was told."""
    def decorate(cls):
        cls._registered_metadata = metadata
        return cls
    return decorate


def test_the_package_imports_without_flyto_core():
    """Most machines have no flyto-core; plan building must still be usable."""
    assert pkg.move_plan(robot_id="r1", distance_m=0.1)["plan_id"]


def test_a_missing_flyto_core_is_logged_not_raised(monkeypatch, caplog):
    """flyto-core loads every plugin in one loop; raising would break the others."""
    import builtins

    real_import = builtins.__import__

    def deny(name, *args, **kwargs):
        if name.startswith("core."):
            raise ImportError("no flyto-core here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny)
    with caplog.at_level(logging.WARNING):
        pkg.register_all()
    assert any("flyto-core" in record.message for record in caplog.records)


def test_three_motion_steps_are_defined():
    built = build_modules(StandInModule, fake_register_module)
    assert [module_id for module_id, _ in built] == [
        "robotics.move",
        "robotics.turn",
        "robotics.stop",
    ]


def test_every_step_declares_itself_to_the_builder():
    for module_id, cls in build_modules(StandInModule, fake_register_module):
        metadata = cls._registered_metadata
        assert metadata["module_id"] == module_id
        assert metadata["category"] == "robotics"
        assert metadata["label"], "a step with no label cannot be found on the canvas"
        assert metadata["requires_credentials"] is True
        # Two robot commands must never be run at once on one machine.
        assert metadata["concurrent_safe"] is False


def test_a_bad_distance_fails_when_the_step_is_configured_not_when_it_runs():
    _, move = build_modules(StandInModule, fake_register_module)[0]
    try:
        move({"distance_m": 99.0}, {})
    except Exception as exc:
        assert "distance_m" in str(exc)
    else:
        raise AssertionError("an out-of-range distance was accepted")


def test_a_step_declares_the_plan_and_drives_nothing():
    """flyto-core runs on the worker, not the robot. A step reaching for a
    gateway here would find whatever is on the worker's loopback."""
    _, move = build_modules(StandInModule, fake_register_module)[0]
    result = asyncio.run(move({"distance_m": 0.4}, {"resource_id": "robot-1"}).execute())
    assert result["dispatched"] is False, "declaring, not driving"
    assert result["requires_device"] == "robot-1"
    assert result["request"]["plan"]["steps"][0]["capability"] == "move_relative"
    assert result["request"]["plan"]["steps"][-1]["capability"] == "safe_stop"


def test_no_step_reaches_for_a_gateway():
    """The wrong-machine bug, kept from coming back.

    Checks imports and calls rather than the word, because the docstring
    explaining why this must not happen legitimately contains it — a grep for
    prose would fail on the very comment that keeps the rule understood.
    """
    import ast
    from pathlib import Path as _Path

    source = _Path(__file__).resolve().parents[1] / "src" / "flyto_modules_robotics" / "modules.py"
    tree = ast.parse(source.read_text())

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    assert not {"gateway", ".gateway"} & imported, "modules.py imports the gateway client"

    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not {"start_plan", "await_session", "session"} & called


def test_a_bad_parameter_is_reported_not_raised():
    """A workflow needs a result it can branch on, not a traceback."""
    _, move = build_modules(StandInModule, fake_register_module)[0]
    step = move.__new__(move)
    step.params = {"distance_m": 99.0}
    step.context = {"resource_id": "robot-1"}
    result = asyncio.run(step.execute())
    assert result["dispatched"] is False and "distance_m" in result["error"]


def test_every_step_is_a_coroutine_because_the_engine_awaits_it():
    """flyto-core runs a module with `return await self.execute()`
    (core/modules/base.py). A plain function there dies at runtime with
    "object dict can't be used in 'await' expression" — which is not a failure
    a workflow author can act on, and not one this suite could see: the
    stand-in base class below calls .execute() directly, so for 36 green tests
    the engine's own contract was never in the room.
    """
    import inspect

    for module_id, cls in build_modules(StandInModule, fake_register_module):
        assert inspect.iscoroutinefunction(cls.execute), (
            f"{module_id}.execute must be async — flyto-core awaits it"
        )
