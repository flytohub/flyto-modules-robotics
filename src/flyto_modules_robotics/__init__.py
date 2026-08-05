"""Optional robot-control modules for Flyto2 workflows.

flyto-core discovers this package through its ``flyto.modules`` entry point and
calls :func:`register_all`. Installing the package is therefore the whole
decision: without it Flyto2 is pure software automation, and with it the builder
gains motion steps.
"""

from __future__ import annotations

import logging

from .gateway import (
    DEFAULT_GATEWAY_URL,
    GatewayError,
    GatewayRefused,
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

__all__ = [
    "DEFAULT_GATEWAY_URL",
    "MAX_DISTANCE_M",
    "MAX_SPEED_MPS",
    "GatewayError",
    "GatewayRefused",
    "PlanBuildError",
    "gateway_url",
    "move_plan",
    "register_all",
    "robot_id",
    "run_request",
    "stop_plan",
    "turn_plan",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)


def register_all() -> None:
    """Register the robotics modules with flyto-core's registry.

    Imports flyto-core here rather than at module scope: this package must stay
    importable — and its plan building testable — where flyto-core is absent.

    A missing or incompatible flyto-core is logged and returns rather than
    raising. flyto-core loads every plugin in one loop, so a raise here would
    take down module discovery for every other plugin as well.
    """
    try:
        from core.modules.base import BaseModule
        from core.modules.registry import register_module
    except ImportError as exc:  # pragma: no cover - depends on the host install
        logger.warning(
            "flyto-modules-robotics could not reach flyto-core, so no robot "
            "steps were registered: %s",
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
