"""Registering with flyto-core, and surviving its absence."""

from __future__ import annotations

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


def test_an_unreachable_robot_is_reported_not_raised(monkeypatch):
    """A workflow needs a result it can branch on, not a traceback."""
    monkeypatch.setenv("FLYTO_ROBOTICS_DELIVERY_TOKEN", "t" * 40)
    monkeypatch.setenv("FLYTO_ROBOTICS_ROBOT_ID", "flyto-tb3-lab-001")
    monkeypatch.setenv("FLYTO_ROBOTICS_GATEWAY_URL", "http://127.0.0.1:1")
    _, move = build_modules(StandInModule, fake_register_module)[0]
    result = move({"distance_m": 0.4, "wait": False}, {}).execute()
    assert result["succeeded"] is False
    assert result["state"] == "unavailable"
    assert "127.0.0.1:1" in result["error"]
