"""Registering with flyto-core, and surviving its absence."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
import types

import pytest

import flyto_modules_robotics as pkg
from flyto_modules_robotics.modules import build_modules

MOVE = "robotics.move"
TURN = "robotics.turn"
STOP = "robotics.stop"

CANONICAL_CAPABILITIES = {
    "robotics.motion.move_relative": MOVE,
    "robotics.motion.turn_relative": TURN,
    "robotics.safety.safe_stop": STOP,
}


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


class StandInRegistry:
    """The part of flyto-core's ModuleRegistry this package's contract touches.

    Keyed by module id and last-write-wins, which is what makes re-registering a
    replacement rather than a duplicate; ``clear()`` is the emptying the real
    registry does when a host hot-reloads and rediscovers plugins. ``plugin`` is
    the ownership the *host* assigns around the ``register_all`` call, not
    something this package passes in — flyto-core 2.27 stamped ``robotics`` on
    all three modules that way.
    """

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
            cls._registered_metadata = metadata
            return cls
        return decorate

    def clear(self) -> None:
        self.entries.clear()

    def module_ids(self) -> list[str]:
        return list(self.entries)

    def capabilities(self) -> dict[str, str]:
        return {
            entry["metadata"]["provides_capability"]: module_id
            for module_id, entry in self.entries.items()
        }

    def owners(self) -> dict[str, str | None]:
        return {module_id: entry["plugin"] for module_id, entry in self.entries.items()}

    def snapshot(self) -> dict:
        """Everything about a registration except the class object's identity.

        The classes are rebuilt on every call by design, so comparing them would
        report a difference that is not one; the metadata and the ownership are
        what a builder and a device matcher actually read.
        """
        return {
            module_id: (entry["plugin"], entry["metadata"])
            for module_id, entry in self.entries.items()
        }


def install_flyto_core(monkeypatch, *, base=StandInModule, register_module=None):
    """Put a flyto-core-shaped ``core.modules.*`` into ``sys.modules``.

    Real module objects resolved by the real import system, rather than a
    patched ``builtins.__import__``. The difference is the point of these tests:
    ``register_all`` now decides what it may swallow partly from *where* the
    ImportError was raised, and a patched ``__import__`` raises from the patch's
    own frame — which is not where an absent flyto-core raises from, so it would
    prove nothing about the real boundary.

    Passing ``register_module=None`` leaves the decorator off the registry
    module: a flyto-core that is installed but does not offer the API this
    package registers through.
    """
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
    """A loader whose module body raises — flyto-core broken from the inside."""

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
    """An installed flyto-core whose ``core.modules.base`` blows up on import.

    The failure happens while flyto-core's own module body runs, which is what
    separates it from flyto-core not being there at all.
    """
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
    """No flyto-core on this machine, which is most machines.

    ``None`` in ``sys.modules`` is the import system's own "this name is not
    available" marker, so the ModuleNotFoundError comes from the machinery
    exactly as it would with nothing installed.
    """
    for name in ("core.modules.registry", "core.modules.base", "core.modules"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, "core", None)


def warnings_in(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def test_the_package_imports_without_flyto_core():
    """Most machines have no flyto-core; plan building must still be usable."""
    assert pkg.move_plan(robot_id="r1", distance_m=0.1)["plan_id"]


def test_the_public_version_matches_the_distribution_version():
    """A Pi installs the wheel and reads pkg.__version__; the two drifting
    apart means the metadata and the public API disagree about what is on the
    machine. Read from the repository's pyproject.toml, not from installed
    metadata, so the check holds on a source checkout too."""
    import tomllib
    from pathlib import Path as _Path

    pyproject = _Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert pkg.__version__ == declared, (
        f"__version__ {pkg.__version__!r} != pyproject version {declared!r}"
    )


def test_a_missing_flyto_core_is_logged_not_raised(monkeypatch, caplog):
    """flyto-core loads every plugin in one loop; raising would break the others.

    The absence is simulated through ``sys.modules`` rather than by patching
    ``builtins.__import__``: the patched version raised from its own frame,
    which is not where an absent flyto-core raises from, so it could no longer
    tell this case apart from flyto-core breaking on the way in.
    """
    uninstall_flyto_core(monkeypatch)
    with caplog.at_level(logging.WARNING):
        assert pkg.register_all() is None
    logged = warnings_in(caplog)
    assert logged and all("flyto-core" in message for message in logged)
    assert any("is not installed here" in message for message in logged)


def test_a_missing_flyto_core_registers_nothing(monkeypatch, caplog):
    """Returning quietly is only half the contract; nothing may reach a registry.

    Registered once against a present flyto-core so the stand-in registry is
    demonstrably reachable, then cleared and asked again with flyto-core gone.
    An empty registry only means something after it has been shown to fill.
    """
    registry = StandInRegistry()
    install_flyto_core(monkeypatch, register_module=registry.register_module)
    pkg.register_all()
    assert registry.module_ids() == [MOVE, TURN, STOP]

    monkeypatch.undo()
    registry.clear()
    uninstall_flyto_core(monkeypatch)
    with caplog.at_level(logging.WARNING):
        pkg.register_all()
    assert registry.entries == {}


def test_an_incompatible_flyto_core_api_is_logged_not_raised(monkeypatch, caplog):
    """An installed flyto-core without the decorator this package registers
    through is the other case a plugin may survive: the engine is there, the
    contract it offers is not the one this package was built against. Taking
    down every other plugin's discovery over it would be the wrong trade."""
    install_flyto_core(monkeypatch, register_module=None)
    with caplog.at_level(logging.WARNING):
        assert pkg.register_all() is None
    logged = warnings_in(caplog)
    assert logged and any(
        "does not provide the registration API" in message for message in logged
    )


def test_a_dependency_missing_inside_flyto_core_propagates(monkeypatch, caplog):
    """flyto-core failing on its own import is flyto-core's failure to report.

    Swallowed here it would read as "no flyto-core installed" on a machine that
    has one, and the three robot steps would be quietly missing from a canvas
    nobody had reason to suspect.
    """
    install_flyto_core_that_fails_while_importing(
        monkeypatch, ModuleNotFoundError("No module named 'yaml'", name="yaml")
    )
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ModuleNotFoundError) as caught:
            pkg.register_all()
    assert caught.value.name == "yaml"
    assert warnings_in(caplog) == []


def test_a_failure_inside_flyto_core_naming_a_core_module_is_not_relabelled(
    monkeypatch, caplog
):
    """The case a name test alone cannot see.

    flyto-core breaking on its *own* ``from core.modules.registry import ...``
    arrives here as an ImportError naming a module this package imports
    directly. Matching on the name would call that "flyto-core is absent" and
    hide a real breakage behind a reassuring warning, so where it was raised
    decides, not what it is called.
    """
    inner = ImportError(
        "cannot import name 'CapabilityDefinition' from 'core.modules.registry'",
        name="core.modules.registry",
    )
    install_flyto_core_that_fails_while_importing(monkeypatch, inner)
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ImportError) as caught:
            pkg.register_all()
    assert caught.value is inner
    assert warnings_in(caplog) == []


def test_a_broken_plugin_module_propagates(monkeypatch, caplog):
    """This package's own modules failing to import is this plugin failing."""
    registry = StandInRegistry()
    install_flyto_core(monkeypatch, register_module=registry.register_module)
    monkeypatch.setitem(sys.modules, "flyto_modules_robotics.modules", None)
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ImportError):
            pkg.register_all()
    assert warnings_in(caplog) == []
    assert registry.entries == {}


def test_a_decorator_that_raises_propagates(monkeypatch, caplog):
    """Registration failing mid-way must not be reported as flyto-core missing.

    The decorator here raises the most confusable failure there is — an
    import error naming flyto-core's own registry module — from the one place
    that is unambiguously past the point where flyto-core was found.
    """
    def register_module(**metadata):
        raise ModuleNotFoundError(
            "No module named 'core.modules.registry'", name="core.modules.registry"
        )

    install_flyto_core(monkeypatch, register_module=register_module)
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ModuleNotFoundError) as caught:
            pkg.register_all()
    assert caught.value.name == "core.modules.registry"
    assert warnings_in(caplog) == []


def test_a_build_failure_propagates(monkeypatch, caplog):
    """Same boundary, one layer further in: build_modules itself failing."""
    def build_modules_that_fails(base_module, register_module):
        raise RuntimeError("no plan table")

    install_flyto_core(monkeypatch, register_module=StandInRegistry().register_module)
    monkeypatch.setattr(
        "flyto_modules_robotics.modules.build_modules", build_modules_that_fails
    )
    with caplog.at_level(logging.WARNING):
        with pytest.raises(RuntimeError):
            pkg.register_all()
    assert warnings_in(caplog) == []


def test_repeated_discovery_registers_exactly_the_same_three_steps(monkeypatch):
    """Discovery runs more than once in a process; the result must not drift.

    Not by remembering that it already ran — see the hot-reload test below —
    but because the registry is keyed by module id, so a second pass replaces
    the same three entries with the same metadata under the same owner.
    """
    registry = StandInRegistry()
    install_flyto_core(monkeypatch, register_module=registry.register_module)
    registry.plugin_owner = "robotics"

    pkg.register_all()
    first = registry.snapshot()
    pkg.register_all()
    pkg.register_all()

    assert registry.module_ids() == [MOVE, TURN, STOP]
    assert registry.capabilities() == CANONICAL_CAPABILITIES
    assert registry.owners() == {MOVE: "robotics", TURN: "robotics", STOP: "robotics"}
    assert registry.snapshot() == first


def test_a_cleared_registry_is_repopulated_by_the_next_discovery(monkeypatch):
    """A host that hot-reloads clears the registry and rediscovers.

    This is why registration remembers nothing between calls. A process-global
    "already registered" flag would make the second pass a no-op and leave the
    fresh registry permanently short three steps — with no error anywhere,
    because from the flag's point of view the work was done.
    """
    registry = StandInRegistry()
    install_flyto_core(monkeypatch, register_module=registry.register_module)
    registry.plugin_owner = "robotics"

    pkg.register_all()
    before = registry.snapshot()

    registry.clear()
    assert registry.entries == {}

    pkg.register_all()

    assert registry.module_ids() == [MOVE, TURN, STOP]
    assert registry.capabilities() == CANONICAL_CAPABILITIES
    assert registry.owners() == {MOVE: "robotics", TURN: "robotics", STOP: "robotics"}
    assert registry.snapshot() == before


def test_ownership_stays_the_hosts_to_assign(monkeypatch):
    """The plugin name is the host's, not this package's, and re-registering
    must not overwrite it with a stale one."""
    registry = StandInRegistry()
    install_flyto_core(monkeypatch, register_module=registry.register_module)

    registry.plugin_owner = "robotics"
    pkg.register_all()
    registry.clear()
    registry.plugin_owner = "robotics-vendor-build"
    pkg.register_all()

    assert set(registry.owners().values()) == {"robotics-vendor-build"}


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


def test_every_step_declares_the_capability_it_needs_a_device_to_have():
    """The mapping a device is matched against, pinned exactly.

    Spelled out as literals rather than imported from ``modules`` on purpose:
    reading the same constants the code registers would assert only that a name
    equals itself, and would keep passing through the rename this test exists to
    catch.

    Two identifiers, not one. This assertion used to carry the version suffix
    and a note saying the suffix is part of the contract. The note is still
    true, but it is true of the *catalog* identifier in ``steps.py``, which is
    what a device is genuinely matched against -- and it still carries ``@1``.
    ``provides_capability`` is the flyto-core registry name, and flyto-core
    refuses ``@``: its rule is ``^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$``, and the
    refusal is not per-module. It rolled the whole plugin back, so all three
    steps left the workflow builder together, and nothing anywhere ever matched
    the versioned form of this particular identifier.
    """
    built = build_modules(StandInModule, fake_register_module)
    declared = {
        module_id: cls._registered_metadata["provides_capability"]
        for module_id, cls in built
    }
    assert declared == {
        "robotics.move": "robotics.motion.move_relative",
        "robotics.turn": "robotics.motion.turn_relative",
        "robotics.stop": "robotics.safety.safe_stop",
    }
    # Stated separately from the mapping above because it is a different claim:
    # the mapping says what each step asks for, this says no two steps ask for
    # the same thing. A device's abilities are matched to an authored step by
    # this identifier, so two steps sharing one would make a move and a turn
    # indistinguishable at match time -- and the wrong one could be selected.
    capabilities = list(declared.values())
    assert len(set(capabilities)) == len(capabilities), (
        f"two steps declare the same capability: {capabilities}"
    )


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


def test_the_versioned_catalog_identifier_is_the_one_a_device_is_matched_against():
    """The version suffix survives, on the identifier that actually uses it.

    Dropping `@1` from `provides_capability` is not the same as abandoning
    capability versioning. `steps.py` holds the table that is compared against
    the robot's own `flyto.robotics.capability-catalog.v1` document, and a
    device declaring `@2` is still a mismatch someone must decide about. If
    that table ever loses its suffix too, the versioning really is gone, and
    this says so.
    """
    from flyto_modules_robotics.steps import _CATALOG_CAPABILITIES

    assert _CATALOG_CAPABILITIES == {
        "robotics.move": "robotics.motion.move_relative@1",
        "robotics.turn": "robotics.motion.turn_relative@1",
        "robotics.stop": "robotics.safety.safe_stop@1",
    }


def test_the_two_identifiers_name_the_same_capability():
    """One is the other with the version suffix removed.

    They are separate tables for separate consumers, and separate tables drift.
    This is what keeps `robotics.move` from asking flyto-core for one capability
    while asking the robot's catalog for another.
    """
    from flyto_modules_robotics.steps import _CATALOG_CAPABILITIES

    built = build_modules(StandInModule, fake_register_module)
    for module_id, cls in built:
        registered = cls._registered_metadata["provides_capability"]
        catalog_id = _CATALOG_CAPABILITIES[module_id]

        assert catalog_id.split("@", 1)[0] == registered, (
            f"{module_id} registers {registered!r} with flyto-core but looks up "
            f"{catalog_id!r} in the device catalog"
        )
