"""Registration, builder visibility, and host-dispatch boundaries."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

import flyto_modules_robotics as pkg
from flyto_modules_robotics.modules import (
    HOST_DISPATCHER_CONTEXT_KEY,
    MOVE_PARAMS_SCHEMA,
    STOP_PARAMS_SCHEMA,
    TURN_PARAMS_SCHEMA,
    build_modules,
)

MOVE = "robotics.move"
TURN = "robotics.turn"
STOP = "robotics.stop"


class StandInModule:
    module_id = ""

    def __init__(self, params, context):
        self.params = params
        self.context = context
        self.validate_params()

    def validate_params(self):
        pass


def fake_register_module(**metadata):
    def decorate(cls):
        cls._registered_metadata = metadata
        return cls

    return decorate


class StandInRegistry:
    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}
        self.plugin_owner: str | None = None

    def register_module(self, **metadata):
        def decorate(cls):
            self.entries[metadata["module_id"]] = {
                "cls": cls,
                "metadata": dict(metadata),
                "plugin": self.plugin_owner,
            }
            return cls

        return decorate

    def clear(self) -> None:
        self.entries.clear()

    def snapshot(self) -> dict:
        return {
            module_id: (entry["plugin"], entry["metadata"])
            for module_id, entry in self.entries.items()
        }


def install_flyto_core(monkeypatch, *, base=StandInModule, register_module=None):
    core = types.ModuleType("core")
    core.__path__ = []
    modules = types.ModuleType("core.modules")
    modules.__path__ = []
    base_module = types.ModuleType("core.modules.base")
    base_module.BaseModule = base
    registry_module = types.ModuleType("core.modules.registry")
    if register_module is not None:
        registry_module.register_module = register_module
    core.modules = modules
    modules.base = base_module
    modules.registry = registry_module
    for name, module in (
        ("core", core),
        ("core.modules", modules),
        ("core.modules.base", base_module),
        ("core.modules.registry", registry_module),
    ):
        monkeypatch.setitem(sys.modules, name, module)


class _ExplodingLoader:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        raise self.exc


class _ExplodingFinder:
    def __init__(self, fullname: str, exc: BaseException) -> None:
        self.fullname = fullname
        self.loader = _ExplodingLoader(exc)

    def find_spec(self, fullname, path=None, target=None):
        if fullname != self.fullname:
            return None
        return importlib.util.spec_from_loader(fullname, self.loader)


def install_flyto_core_that_fails_while_importing(monkeypatch, exc):
    core = types.ModuleType("core")
    core.__path__ = []
    modules = types.ModuleType("core.modules")
    modules.__path__ = []
    monkeypatch.setitem(sys.modules, "core", core)
    monkeypatch.setitem(sys.modules, "core.modules", modules)
    monkeypatch.delitem(sys.modules, "core.modules.base", raising=False)
    monkeypatch.delitem(sys.modules, "core.modules.registry", raising=False)
    monkeypatch.setattr(
        sys, "meta_path", [_ExplodingFinder("core.modules.base", exc), *sys.meta_path]
    )


def uninstall_flyto_core(monkeypatch):
    for name in ("core.modules.registry", "core.modules.base", "core.modules"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, "core", None)


def warnings_in(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]


def test_package_imports_without_flyto_core():
    request = pkg.capability_request_for_step(
        MOVE, {"distance_m": 0.1}, resource_id="robot-1"
    )
    assert request["capability_id"] == "motion.advance"


def test_public_version_matches_distribution_version():
    import tomllib

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert pkg.__version__ == declared


def test_missing_flyto_core_is_logged_not_raised(monkeypatch, caplog):
    uninstall_flyto_core(monkeypatch)
    with caplog.at_level(logging.WARNING):
        assert pkg.register_all() is None
    assert any("is not installed here" in item for item in warnings_in(caplog))


def test_incompatible_core_registration_api_is_logged(monkeypatch, caplog):
    install_flyto_core(monkeypatch, register_module=None)
    with caplog.at_level(logging.WARNING):
        assert pkg.register_all() is None
    assert any("does not provide the registration API" in item for item in warnings_in(caplog))


def test_failure_inside_flyto_core_propagates(monkeypatch, caplog):
    install_flyto_core_that_fails_while_importing(
        monkeypatch, ModuleNotFoundError("No module named 'yaml'", name="yaml")
    )
    with caplog.at_level(logging.WARNING), pytest.raises(ModuleNotFoundError):
        pkg.register_all()
    assert warnings_in(caplog) == []


def test_plugin_build_failure_propagates(monkeypatch):
    install_flyto_core(
        monkeypatch,
        register_module=StandInRegistry().register_module,
    )

    def fail(*_args, **_kwargs):
        raise RuntimeError("broken plugin")

    monkeypatch.setattr("flyto_modules_robotics.modules.build_modules", fail)
    with pytest.raises(RuntimeError, match="broken plugin"):
        pkg.register_all()


def test_registration_is_repeatable_and_host_owns_plugin_identity(monkeypatch):
    registry = StandInRegistry()
    install_flyto_core(monkeypatch, register_module=registry.register_module)
    registry.plugin_owner = "robotics"
    pkg.register_all()
    first = registry.snapshot()

    registry.clear()
    registry.plugin_owner = "robotics-vendor-build"
    pkg.register_all()

    assert list(registry.entries) == [MOVE, TURN, STOP]
    assert {item["plugin"] for item in registry.entries.values()} == {
        "robotics-vendor-build"
    }
    assert {
        module_id: metadata
        for module_id, (_plugin, metadata) in first.items()
    } == {
        module_id: entry["metadata"]
        for module_id, entry in registry.entries.items()
    }


def test_builder_metadata_is_complete_and_not_fake_resource_capability_metadata():
    built = build_modules(StandInModule, fake_register_module)
    metadata = {
        module_id: cls._registered_metadata
        for module_id, cls in built
    }

    assert list(metadata) == [MOVE, TURN, STOP]
    assert metadata[MOVE]["params_schema"] == MOVE_PARAMS_SCHEMA
    assert metadata[TURN]["params_schema"] == TURN_PARAMS_SCHEMA
    assert metadata[STOP]["params_schema"] == STOP_PARAMS_SCHEMA
    for module_id, item in metadata.items():
        assert item["module_id"] == module_id
        assert item["category"] == "robotics"
        assert item["label"]
        assert item["requires_credentials"] is False
        assert item["concurrent_safe"] is False
        assert "provides_capability" not in item or item["provides_capability"] is None


def test_real_flyto_core_builder_registry_exposes_nodes_and_canonical_request():
    """Accept against the actual installed flyto-core consumer, not a stand-in."""

    script = """
import asyncio
import json
import sys

sys.path.insert(0, sys.argv[1])

from core.modules.base import BaseModule
from core.modules.registry import ModuleRegistry, register_module
from flyto_modules_robotics.modules import build_modules

ModuleRegistry.clear()
try:
    build_modules(BaseModule, register_module)
    metadata = ModuleRegistry.get_all_metadata()
    cls = ModuleRegistry.get("robotics.move")
    node = cls({"distance_m": 0.4}, {"resource_id": "robot-1"})
    result = asyncio.run(node.execute())
    print(json.dumps({
        "ids": sorted(k for k in metadata if k.startswith("robotics.")),
        "move_schema": metadata["robotics.move"]["params_schema"],
        "requires_credentials": metadata["robotics.move"]["requires_credentials"],
        "result": result,
    }, sort_keys=True))
finally:
    ModuleRegistry.clear()
"""
    checkout_src = Path(__file__).resolve().parents[1] / "src"
    completed = subprocess.run(
        [sys.executable, "-c", script, str(checkout_src)],
        check=False,
        capture_output=True,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        text=True,
    )
    if completed.returncode and "unsupported operand type(s) for |" in completed.stderr:
        pytest.skip("installed flyto-core requires a newer Python interpreter")
    assert completed.returncode == 0, completed.stderr

    observed = json.loads(completed.stdout.strip().splitlines()[-1])
    assert observed["ids"] == [MOVE, STOP, TURN]
    assert observed["move_schema"]["distance_m"]["min"] == 0.05
    assert observed["requires_credentials"] is False
    request = observed["result"]["capability_request"]
    assert request["contract_version"] == "flyto.capability-request.v1"
    assert request["resource_id"] == "robot-1"
    assert request["capability_id"] == "motion.advance"
    assert observed["result"]["dispatched"] is False


def test_bad_distance_fails_during_module_configuration():
    _, move = build_modules(StandInModule, fake_register_module)[0]
    with pytest.raises(pkg.CapabilityRequestError, match="distance_m"):
        move({"distance_m": 99.0}, {})


def test_module_declares_standard_capability_work_and_drives_nothing():
    _, move = build_modules(StandInModule, fake_register_module)[0]
    result = asyncio.run(
        move({"distance_m": 0.4}, {"resource_id": "robot-1"}).execute()
    )
    assert result["dispatched"] is False
    assert result["commanded_resource"] == "robot-1"
    assert result["capability_request"]["capability_id"] == "motion.advance"
    serialized = json.dumps(result, sort_keys=True)
    assert "gateway" not in serialized
    assert "8766" not in serialized


class TrustedDispatcher:
    _flyto_runtime_opaque = True

    def __init__(self, outcome="completed"):
        self.outcome = outcome
        self.requests = []

    async def invoke(self, request):
        self.requests.append(dict(request))
        return {
            "outcome": self.outcome,
            "detail": "" if self.outcome == "completed" else "blocked by fixture",
            "observation": {"pose": {"x": 1.0}},
        }


def test_trusted_execution_host_dispatches_original_canonical_request():
    _, move = build_modules(StandInModule, fake_register_module)[0]
    dispatcher = TrustedDispatcher()
    result = asyncio.run(
        move(
            {"distance_m": 0.4},
            {
                "resource_id": "robot-1",
                HOST_DISPATCHER_CONTEXT_KEY: dispatcher,
            },
        ).execute()
    )
    assert result["ok"] is True
    assert result["dispatched"] is True
    assert dispatcher.requests == [result["capability_request"]]


def test_failed_external_capability_becomes_bounded_step_failure():
    _, move = build_modules(StandInModule, fake_register_module)[0]
    dispatcher = TrustedDispatcher("failed")
    result = asyncio.run(
        move(
            {"distance_m": 0.4},
            {
                "resource_id": "robot-1",
                HOST_DISPATCHER_CONTEXT_KEY: dispatcher,
            },
        ).execute()
    )
    assert result["ok"] is False
    assert result["error_code"] == "EXTERNAL_CAPABILITY_FAILED"
    assert "blocked" in result["error"]


def test_workflow_cannot_fake_dispatcher_authority():
    _, move = build_modules(StandInModule, fake_register_module)[0]
    with pytest.raises(RuntimeError, match="untrusted external capability dispatcher"):
        asyncio.run(
            move(
                {"distance_m": 0.4},
                {
                    "resource_id": "robot-1",
                    HOST_DISPATCHER_CONTEXT_KEY: {"invoke": "not trusted"},
                },
            ).execute()
        )


def test_bad_runtime_parameter_is_reported_not_raised():
    _, move = build_modules(StandInModule, fake_register_module)[0]
    step = move.__new__(move)
    step.params = {"distance_m": 99.0}
    step.context = {"resource_id": "robot-1"}
    result = asyncio.run(step.execute())
    assert result["dispatched"] is False
    assert "distance_m" in result["error"]


def test_every_step_execute_is_async():
    import inspect

    for module_id, cls in build_modules(StandInModule, fake_register_module):
        assert inspect.iscoroutinefunction(cls.execute), module_id
