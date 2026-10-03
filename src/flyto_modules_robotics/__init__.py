"""Robot capabilities for Flyto2, contributed through ``@register_module`` alone.

flyto-core discovers this package through its ``flyto.modules`` entry point and
calls :func:`register_all`.  Each capability (advance, retreat, rotate, halt,
navigate, observe, map) is one registered module carrying
``provides_capability`` and a ``flyto.capability-contract.v1`` contract.  Steps
execute on the AI Space host through its dispatcher, which calls the
flyto-robotics ROS 2 adapter; nothing from this package runs on the robot.

A second entry point, ``fleet`` (:mod:`flyto_modules_robotics.fleet_pack`),
registers Open-RMF fleet steps through the same contract.
"""

from __future__ import annotations

import logging
import os

from .capabilities import (
    CAPABILITY_ADVANCE,
    CAPABILITY_DOCK,
    CAPABILITY_LOAD,
    CAPABILITY_NAVIGATE_TO_WAYPOINT,
    CAPABILITY_UNLOAD,
    FLEET_SPECS,
    CAPABILITY_HALT,
    CAPABILITY_MAP,
    CAPABILITY_NAVIGATE,
    CAPABILITY_OBSERVE,
    CAPABILITY_RETREAT,
    CAPABILITY_ROTATE,
    CONTRACT_SCHEMA,
    MODULE_ADVANCE,
    MODULE_HALT,
    MODULE_MAP,
    MODULE_NAVIGATE,
    MODULE_OBSERVE,
    MODULE_RETREAT,
    MODULE_ROTATE,
    SPECS,
    CapabilitySpec,
)
from .capability_request import (
    CAPABILITY_REQUEST_VERSION,
    CapabilityRequestError,
    capability_request_for_step,
)
from .steps import FLEET_MODULE_IDS, MODULE_IDS, is_robotics_step, step_module_id

__all__ = [
    "CAPABILITY_ADVANCE",
    "CAPABILITY_DOCK",
    "CAPABILITY_LOAD",
    "CAPABILITY_NAVIGATE_TO_WAYPOINT",
    "CAPABILITY_UNLOAD",
    "FLEET_MODULE_IDS",
    "FLEET_SPECS",
    "PACK_DESCRIPTION",
    "CAPABILITY_HALT",
    "CAPABILITY_MAP",
    "CAPABILITY_NAVIGATE",
    "CAPABILITY_OBSERVE",
    "CAPABILITY_REQUEST_VERSION",
    "CAPABILITY_RETREAT",
    "CAPABILITY_ROTATE",
    "CONTRACT_SCHEMA",
    "MODULE_ADVANCE",
    "MODULE_HALT",
    "MODULE_IDS",
    "MODULE_MAP",
    "MODULE_NAVIGATE",
    "MODULE_OBSERVE",
    "MODULE_RETREAT",
    "MODULE_ROTATE",
    "SPECS",
    "CapabilityRequestError",
    "CapabilitySpec",
    "capability_request_for_step",
    "is_robotics_step",
    "register_all",
    "step_module_id",
]

__version__ = "1.1.0"

#: What flyto-core reports for this pack (``PluginInfo.description``).
PACK_DESCRIPTION = "Robot motion, camera and map through a standard ROS 2 adapter"

logger = logging.getLogger(__name__)

_CORE_API_MODULES = frozenset({"core.modules.base", "core.modules.registry"})
_CORE_API_PACKAGES = frozenset({"core", "core.modules"})


def _is_import_machinery(filename: str) -> bool:
    """Whether a traceback frame belongs to the import system itself."""

    if filename.startswith(("<frozen importlib", "<frozen zipimport")):
        return True
    marker = os.sep + "importlib" + os.sep + "_bootstrap"
    return marker in filename


def _raised_by_our_own_import(exc: ImportError) -> bool:
    """Whether an ImportError is this package's own Core import failing."""

    here = os.path.normcase(os.path.abspath(__file__))
    tb = exc.__traceback__
    while tb is not None:
        filename = tb.tb_frame.f_code.co_filename
        if (
            not _is_import_machinery(filename)
            and os.path.normcase(os.path.abspath(filename)) != here
        ):
            return False
        tb = tb.tb_next
    return True


def _core_unusable_reason(exc: ImportError) -> str | None:
    """Return the two expected Core incompatibility cases, else re-raise."""

    if not _raised_by_our_own_import(exc):
        return None
    name = exc.name
    if isinstance(exc, ModuleNotFoundError):
        if name in _CORE_API_MODULES or name in _CORE_API_PACKAGES:
            return "is not installed here"
        return None
    if name in _CORE_API_MODULES:
        return "does not provide the registration API this package registers through"
    return None


def _core_api(what: str):
    """flyto-core's ``(BaseModule, register_module)``, or None when unusable.

    Core is imported only here so the pure capability and request API remains
    importable without an execution engine.  A missing/incompatible Core API is
    logged; failures inside Core or this plugin continue to propagate.
    """

    try:
        from core.modules.base import BaseModule
        from core.modules.registry import register_module
    except ImportError as exc:
        reason = _core_unusable_reason(exc)
        if reason is None:
            raise
        logger.warning(
            "flyto-modules-robotics registered no %s steps because flyto-core %s: %s",
            what,
            reason,
            exc,
        )
        return None
    return BaseModule, register_module


def register_all() -> None:
    """Register the robotics capability steps with flyto-core.

    Registration is intentionally repeatable for registry reloads.
    """

    api = _core_api("robotics")
    if api is None:
        return

    from .modules import build_modules

    registered = build_modules(*api)
    logger.info(
        "flyto-modules-robotics registered %d robotics steps: %s",
        len(registered),
        ", ".join(module_id for module_id, _ in registered),
    )
