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
from flyto_modules_robotics.capabilities import OPTIONAL_CONTRACT_KEYS, SPECS, SPECS_BY_MODULE
from flyto_modules_robotics.modules import (
    HOST_DISPATCHER_CONTEXT_KEY,
    build_modules,
    core_optional_contract_keys,
    supports_contract,
)

MODULE_IDS = [spec.module_id for spec in SPECS]
ACTUATING = {"robotics.advance", "robotics.retreat", "robotics.rotate", "robotics.halt", "robotics.navigate"}


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


def legacy_register_module(
    module_id,
    version="1.0.0",
    category=None,
    subcategory=None,
    tags=None,
    provides_capability=None,
    label=None,
    label_key=None,
    description=None,
    description_key=None,
    icon=None,
    color=None,
    input_types=None,
    output_types=None,
    can_receive_from=None,
    can_connect_to=None,
    params_schema=None,
    timeout_ms=None,
    retryable=False,
    concurrent_safe=True,
    requires_credentials=False,
    handles_sensitive_data=False,
):
    """The signature of a flyto-core released before `contract=` existed."""

    captured = {
        "module_id": module_id,
        "provides_capability": provides_capability,
        "params_schema": params_schema,
    }

    def decorate(cls):
        cls._registered_metadata = captured
        return cls

    return decorate


def built_metadata(register=fake_register_module):
    return {module_id: cls._registered_metadata for module_id, cls in build_modules(StandInModule, register)}


def step(module_id, params, context=None):
    cls = dict(build_modules(StandInModule, fake_register_module))[module_id]
    return cls(params, {"resource_id": "robot-1", **(context or {})})


def test_package_imports_without_flyto_core():
    request = pkg.capability_request_for_step(
        "robotics.advance", {"distance_m": 0.1}, resource_id="robot-1"
    )
    assert request["capability_id"] == "motion.advance"


def test_public_version_matches_distribution_version():
    import tomllib

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text())["project"]
    assert pkg.__version__ == project["version"]
    # Core is an optional extra: the package installs without the engine.
    assert project["dependencies"] == []
    assert project["optional-dependencies"]["core"] == ["flyto-core>=2.35.0"]


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

    assert list(registry.entries) == MODULE_IDS
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


def test_each_module_declares_its_capability_and_contract():
    metadata = built_metadata()
    assert list(metadata) == MODULE_IDS
    for module_id, item in metadata.items():
        spec = SPECS_BY_MODULE[module_id]
        assert item["module_id"] == module_id
        assert item["provides_capability"] == spec.capability_id
        assert item["params_schema"] == spec.params_schema
        # The 2.36.0 optional keys only where this flyto-core accepts them.
        dropped = OPTIONAL_CONTRACT_KEYS - core_optional_contract_keys()
        assert item["contract"] == {
            key: value for key, value in spec.contract.items() if key not in dropped
        }
        assert item["category"] == "robotics"
        assert item["label"]
        assert item["requires_credentials"] is False
        assert item["concurrent_safe"] is False


def test_registered_metadata_is_a_copy_of_the_spec_row():
    metadata = built_metadata()
    metadata["robotics.advance"]["params_schema"]["distance_m"]["max"] = 99
    metadata["robotics.advance"]["contract"]["evidence"].clear()
    spec = SPECS_BY_MODULE["robotics.advance"]
    assert spec.params_schema["distance_m"]["max"] == 2.0
    assert spec.contract["evidence"]


def test_actuating_steps_are_not_concurrent_and_navigate_has_time_to_arrive():
    metadata = built_metadata()
    for module_id in ACTUATING:
        assert metadata[module_id]["concurrent_safe"] is False
        assert metadata[module_id]["retryable"] is (module_id == "robotics.halt")
    assert metadata["robotics.navigate"]["timeout_ms"] >= 180000
    assert metadata["robotics.advance"]["timeout_ms"] >= 180000


def test_contract_support_is_detected_from_the_signature():
    assert supports_contract(fake_register_module)
    assert supports_contract(StandInRegistry().register_module)
    assert not supports_contract(legacy_register_module)


def test_older_core_registers_without_contract_and_logs_once(caplog):
    with caplog.at_level(logging.WARNING):
        metadata = built_metadata(legacy_register_module)
    assert list(metadata) == MODULE_IDS
    for module_id, item in metadata.items():
        assert item["provides_capability"] == SPECS_BY_MODULE[module_id].capability_id
    contract_warnings = [item for item in warnings_in(caplog) if "contract=" in item]
    assert len(contract_warnings) == 1


def test_real_flyto_core_registry_exposes_capabilities_and_requests():
    """Accept against the actual installed flyto-core consumer, not a stand-in."""

    script = """
import asyncio
import json
import sys

sys.path.insert(0, sys.argv[1])

from core.modules.base import BaseModule
from core.modules.registry import ModuleRegistry, register_module
from flyto_modules_robotics.modules import (
    build_modules,
    core_optional_contract_keys,
    supports_contract,
)

ModuleRegistry.clear()
try:
    build_modules(BaseModule, register_module)
    metadata = ModuleRegistry.get_all_metadata()
    cls = ModuleRegistry.get("robotics.advance")
    node = cls({"distance_m": 0.4}, {"resource_id": "robot-1"})
    result = asyncio.run(node.execute())
    print(json.dumps({
        "capabilities": {
            k: v for k, v in ModuleRegistry.capabilities().items()
            if any(m.startswith("robotics.") for m in v)
        },
        "contract_supported": supports_contract(register_module),
        "optional_keys": sorted(core_optional_contract_keys()),
        "advance": metadata["robotics.advance"],
        "result": result,
    }, sort_keys=True, default=str))
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
    if completed.returncode and "No module named 'core'" in completed.stderr:
        pytest.skip("flyto-core is not installed in this interpreter")
    if completed.returncode and "unsupported operand type(s) for |" in completed.stderr:
        pytest.skip("installed flyto-core requires a newer Python interpreter")
    assert completed.returncode == 0, completed.stderr

    observed = json.loads(completed.stdout.strip().splitlines()[-1])
    assert observed["capabilities"] == {
        spec.capability_id: [spec.module_id] for spec in SPECS
    }
    advance = observed["advance"]
    assert advance["params_schema"]["distance_m"]["min"] == 0.05
    assert advance["provides_capability"] == "motion.advance"
    if observed["contract_supported"]:
        dropped = OPTIONAL_CONTRACT_KEYS - set(observed["optional_keys"])
        expected = {
            key: value
            for key, value in SPECS_BY_MODULE["robotics.advance"].contract.items()
            if key not in dropped
        }
        assert advance["contract"] == json.loads(json.dumps(expected))
    request = observed["result"]["capability_request"]
    assert request["resource_id"] == "robot-1"
    assert request["capability_id"] == "motion.advance"
    assert observed["result"]["dispatched"] is False


def test_out_of_bounds_fails_while_configuring_the_step():
    with pytest.raises(pkg.CapabilityRequestError, match="distance_m"):
        step("robotics.advance", {"distance_m": 2.5})


def test_out_of_bounds_at_run_time_is_refused_and_never_dispatched():
    dispatcher = TrustedDispatcher()
    advance = step("robotics.advance", {"distance_m": 0.4}, {HOST_DISPATCHER_CONTEXT_KEY: dispatcher})
    advance.params = {"distance_m": 2.5}
    result = asyncio.run(advance.execute())
    assert result["ok"] is False
    assert result["error_code"] == "CAPABILITY_ARGUMENTS_REFUSED"
    assert result["dispatched"] is False
    assert dispatcher.requests == []


def test_without_a_dispatcher_the_step_only_declares():
    result = asyncio.run(step("robotics.advance", {"distance_m": 0.4}).execute())
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
        self.requests.append(request)
        return {
            "call_id": "call-1",
            "outcome": self.outcome,
            "detail": "" if self.outcome == "completed" else f"{self.outcome} by fixture",
            "observation": {"pose": {"x": 1.0}},
        }


@pytest.mark.parametrize(
    ("module_id", "params", "arguments"),
    [
        ("robotics.advance", {"distance_m": 0.4}, {"distance_m": 0.4, "speed_mps": 0.12}),
        ("robotics.retreat", {"distance_m": 0.3, "speed_mps": 0.05}, {"distance_m": 0.3, "speed_mps": 0.05}),
        ("robotics.rotate", {"yaw_radians": -0.5}, {"yaw_radians": -0.5}),
        ("robotics.halt", {}, {}),
        ("robotics.navigate", {"x": 1, "y": 2}, {"x": 1.0, "y": 2.0}),
        ("robotics.observe", {}, {}),
        ("robotics.map", {}, {}),
    ],
)
def test_dispatcher_receives_exactly_resource_capability_arguments(module_id, params, arguments):
    dispatcher = TrustedDispatcher()
    result = asyncio.run(step(module_id, params, {HOST_DISPATCHER_CONTEXT_KEY: dispatcher}).execute())
    assert dispatcher.requests == [
        {
            "resource_id": "robot-1",
            "capability_id": SPECS_BY_MODULE[module_id].capability_id,
            "arguments": arguments,
        }
    ]
    assert result["ok"] is True
    assert result["dispatched"] is True
    assert result["outcome"] == "completed"
    assert result["execution"]["call_id"] == "call-1"


def test_resource_param_overrides_context_resource():
    dispatcher = TrustedDispatcher()
    asyncio.run(
        step("robotics.halt", {"resource_id": "robot-2"}, {HOST_DISPATCHER_CONTEXT_KEY: dispatcher}).execute()
    )
    assert dispatcher.requests[0]["resource_id"] == "robot-2"


@pytest.mark.parametrize(
    ("outcome", "error_code"),
    [
        ("refused", "EXTERNAL_CAPABILITY_REFUSED"),
        ("timeout", "EXTERNAL_CAPABILITY_TIMEOUT"),
        ("cancelled", "EXTERNAL_CAPABILITY_CANCELLED"),
        ("failed", "EXTERNAL_CAPABILITY_FAILED"),
        ("", "EXTERNAL_CAPABILITY_FAILED"),
        ("exploded", "EXTERNAL_CAPABILITY_FAILED"),
    ],
)
def test_adapter_outcomes_map_to_step_failures(outcome, error_code):
    dispatcher = TrustedDispatcher(outcome)
    result = asyncio.run(
        step("robotics.advance", {"distance_m": 0.4}, {HOST_DISPATCHER_CONTEXT_KEY: dispatcher}).execute()
    )
    assert result["ok"] is False
    assert result["error_code"] == error_code
    assert result["dispatched"] is True
    assert result["outcome"] == outcome
    # The execution record is kept, so an unfinished motion's poses still reach Cloud.
    assert result["execution"]["observation"] == {"pose": {"x": 1.0}}


def test_dispatcher_returning_no_record_is_a_failure():
    class Silent(TrustedDispatcher):
        async def invoke(self, request):
            return None

    result = asyncio.run(
        step("robotics.halt", {}, {HOST_DISPATCHER_CONTEXT_KEY: Silent()}).execute()
    )
    assert result["ok"] is False
    assert result["error_code"] == "EXTERNAL_CAPABILITY_FAILED"


@pytest.mark.parametrize("forged", [{"invoke": "not trusted"}, types.SimpleNamespace(_flyto_runtime_opaque=True, invoke=print)])
def test_workflow_data_cannot_forge_dispatcher_authority(forged):
    with pytest.raises(RuntimeError, match="untrusted external capability dispatcher"):
        asyncio.run(step("robotics.halt", {}, {HOST_DISPATCHER_CONTEXT_KEY: forged}).execute())


def test_every_step_execute_is_async():
    import inspect

    for module_id, cls in build_modules(StandInModule, fake_register_module):
        assert inspect.iscoroutinefunction(cls.execute), module_id
