"""Optional robot-control modules for Flyto2 workflows.

flyto-core discovers this package through its ``flyto.modules`` entry point and
calls :func:`register_all`. Installing the package is therefore the whole
decision: without it Flyto2 is pure software automation, and with it the builder
gains motion steps.
"""

from __future__ import annotations

import logging
import os

from .catalog import Capability, CapabilityCatalog, CapabilityCatalogError

from .gateway import (
    DEFAULT_GATEWAY_URL,
    GatewayError,
    GatewayRefused,
    capability_catalog,
    gateway_url,
    robot_id,
)
from .plan import (
    MAX_DISTANCE_M,
    MAX_SPEED_MPS,
    PlanBuildError,
    move_plan,
    run_request,
    stop_plan,
    turn_plan,
)
from .steps import plan_for_step, preview_plan_for_step, trusted_plan_for_step

__all__ = [
    "DEFAULT_GATEWAY_URL",
    "MAX_DISTANCE_M",
    "MAX_SPEED_MPS",
    "GatewayError",
    "GatewayRefused",
    "Capability",
    "CapabilityCatalog",
    "CapabilityCatalogError",
    "PlanBuildError",
    "gateway_url",
    "capability_catalog",
    "move_plan",
    "plan_for_step",
    "preview_plan_for_step",
    "trusted_plan_for_step",
    "register_all",
    "robot_id",
    "run_request",
    "stop_plan",
    "turn_plan",
]

__version__ = "0.1.1"

logger = logging.getLogger(__name__)

# The flyto-core names this package imports directly, and the packages they sit
# in. An ImportError naming one of these, raised by this file's own import
# statement, is the one expected outcome: flyto-core is not installed on this
# machine, or the installed one no longer offers the API this package registers
# through. Everything else -- a dependency missing inside flyto-core, a broken
# module in this package, a decorator that raises -- is a real plugin failure
# and belongs to flyto-core's discovery boundary, which is what can report
# *which* plugin failed and why.
_CORE_API_MODULES = frozenset({"core.modules.base", "core.modules.registry"})
_CORE_API_PACKAGES = frozenset({"core", "core.modules"})


def _is_import_machinery(filename: str) -> bool:
    """Whether a traceback frame belongs to the import system itself."""
    if filename.startswith("<frozen importlib") or filename.startswith("<frozen zipimport"):
        return True
    marker = os.sep + "importlib" + os.sep + "_bootstrap"
    return marker in filename


def _raised_by_our_own_import(exc: ImportError) -> bool:
    """Whether this ImportError is *this file's* import statement failing.

    An import that reached flyto-core's code and failed inside it leaves that
    code's frame in the traceback. CPython removes the import machinery's own
    frames for ImportError, and the few that survive are recognised above. So a
    traceback holding nothing but this file and the machinery means the import
    itself did not resolve -- not that something behind it blew up.

    Without this check the name test below is forgeable: flyto-core failing on
    its own ``from core.modules.registry import ...`` would arrive here naming a
    module in ``_CORE_API_MODULES`` and would be mislabelled "flyto-core is
    absent", hiding a real breakage behind a reassuring warning.
    """
    here = os.path.normcase(os.path.abspath(__file__))
    tb = exc.__traceback__
    while tb is not None:
        filename = tb.tb_frame.f_code.co_filename
        if not _is_import_machinery(filename):
            if os.path.normcase(os.path.abspath(filename)) != here:
                return False
        tb = tb.tb_next
    return True


def _core_unusable_reason(exc: ImportError) -> str | None:
    """Why flyto-core cannot be registered into here, or None to re-raise.

    Returns a reason only for the two cases this package is entitled to
    swallow, and None for every other ImportError so it keeps travelling.
    """
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
    """Register the robotics modules with flyto-core's registry.

    Imports flyto-core here rather than at module scope: this package must stay
    importable — and its plan building testable — where flyto-core is absent.

    A flyto-core that is absent, or present on a contract without the API this
    package imports, is logged and returns rather than raising. flyto-core loads
    every plugin in one loop, so raising for the ordinary "not installed here"
    case would take module discovery down for every other plugin as well.

    Every other failure is re-raised, deliberately. A dependency missing *inside*
    flyto-core, a broken import in this package's own ``modules``, a decorator or
    a ``build_modules`` that raises — those are this plugin failing, and only
    flyto-core's discovery boundary can say so. Reporting them as "flyto-core is
    absent" would leave an installed engine silently short three robot steps with
    a warning pointing at the wrong machine.

    Registration is redone on every call and nothing is remembered between them.
    That is what makes it survive a registry that was cleared or hot-reloaded: a
    process-global "already registered" flag would skip the second call and leave
    the fresh registry permanently empty. Repeating is safe because the registry
    is keyed by module id — the same three ids, in the same order, carrying the
    same capability metadata, and the plugin ownership the host stamps around
    this call is re-stamped with them.
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
