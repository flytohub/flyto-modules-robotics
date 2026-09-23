"""Optional robotics authoring modules for Flyto2 workflows.

flyto-core discovers this package through its `flyto.modules` entry point.
Move / Turn / Stop emit bounded `flyto.capability-request.v1` requests for
commanded equipment.  Execution placement and physical transport live outside
this package and outside the robot.
"""

from __future__ import annotations

import logging
import os

from .capability_request import (
    CAPABILITY_ADVANCE,
    CAPABILITY_HALT,
    CAPABILITY_REQUEST_VERSION,
    CAPABILITY_RETREAT,
    CAPABILITY_ROTATE,
    DEFAULT_SPEED_MPS,
    MAX_ADVANCE_SPEED_MPS,
    MAX_DISTANCE_M,
    MAX_RETREAT_SPEED_MPS,
    MAX_TURN_DEGREES,
    MIN_DISTANCE_M,
    MIN_SPEED_MPS,
    MIN_TURN_DEGREES,
    CapabilityRequestError,
    PlanBuildError,
    capability_request_for_step,
)
from .steps import (
    MODULE_IDS,
    MODULE_MOVE,
    MODULE_STOP,
    MODULE_TURN,
    is_robotics_step,
    step_module_id,
)

__all__ = [
    "CAPABILITY_ADVANCE",
    "CAPABILITY_HALT",
    "CAPABILITY_REQUEST_VERSION",
    "CAPABILITY_RETREAT",
    "CAPABILITY_ROTATE",
    "DEFAULT_SPEED_MPS",
    "MAX_ADVANCE_SPEED_MPS",
    "MAX_DISTANCE_M",
    "MAX_RETREAT_SPEED_MPS",
    "MAX_TURN_DEGREES",
    "MIN_DISTANCE_M",
    "MIN_SPEED_MPS",
    "MIN_TURN_DEGREES",
    "MODULE_IDS",
    "MODULE_MOVE",
    "MODULE_STOP",
    "MODULE_TURN",
    "CapabilityRequestError",
    "PlanBuildError",
    "capability_request_for_step",
    "is_robotics_step",
    "register_all",
    "step_module_id",
]

__version__ = "0.2.0"

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


def register_all() -> None:
    """Register the robotics authoring modules with flyto-core.

    Core is imported only here so the pure capability-request API remains
    importable without an execution engine.  A missing/incompatible Core API is
    logged; failures inside Core or this plugin continue to propagate.
    Registration is intentionally repeatable for registry reloads.
    """

    try:
        from core.modules.base import BaseModule
        from core.modules.registry import register_module
    except ImportError as exc:
        reason = _core_unusable_reason(exc)
        if reason is None:
            raise
        logger.warning(
            "flyto-modules-robotics registered no robot steps because flyto-core "
            "%s: %s",
            reason,
            exc,
        )
        return

    from .modules import build_modules

    registered = build_modules(BaseModule, register_module)
    logger.info(
        "flyto-modules-robotics registered %d robot steps: %s",
        len(registered),
        ", ".join(module_id for module_id, _ in registered),
    )
