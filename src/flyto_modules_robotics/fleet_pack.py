# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""The ``fleet`` pack: Open-RMF fleets through the same capability contract.

A separate ``flyto.modules`` entry point, so a site with fleets and no single
robot (or the reverse) shows only the pack it uses. Four steps, each one
``@register_module`` with a ``flyto.capability-contract.v1`` contract:
``fleet.navigate`` (``motion.navigate``), ``fleet.dock`` (``motion.dock``),
``fleet.load`` (``transport.load``) and ``fleet.unload``
(``transport.unload``). Each takes a named waypoint; the commanded resource is
a fleet (``fleet:<name>``), and the host's dispatcher calls flyto-robotics'
``open_rmf.fleet`` adapter, which lets Open-RMF pick the robot.
"""

from __future__ import annotations

import logging

from . import _core_api

#: What flyto-core reports for this pack (``PluginInfo.description``).
PACK_DESCRIPTION = "Open-RMF fleets: navigate, dock, load and unload at named waypoints"

logger = logging.getLogger(__name__)


def register_fleet() -> None:
    """Register the Open-RMF fleet steps with flyto-core (repeatable)."""

    api = _core_api("fleet")
    if api is None:
        return

    from .modules import build_fleet_modules

    registered = build_fleet_modules(*api)
    logger.info(
        "flyto-modules-robotics registered %d fleet steps: %s",
        len(registered),
        ", ".join(module_id for module_id, _ in registered),
    )


__all__ = ["PACK_DESCRIPTION", "register_fleet"]
