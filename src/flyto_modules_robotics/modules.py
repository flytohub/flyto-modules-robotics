# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""The robotics steps, registered with flyto-core: one decorator per capability.

Each step is an ordinary ``@register_module`` carrying ``provides_capability``
and a ``flyto.capability-contract.v1`` contract.  That is the whole integration
surface: Flyto2 contains no robot-specific code for these steps to plug into.

At run time a step validates its arguments, then hands
``{resource_id, capability_id, arguments}`` to the opaque dispatcher the AI
Space execution host injected into the step context.  The host's dispatcher
calls the flyto-robotics ROS 2 adapter.  This package never imports ROS, opens
a socket or picks a host, and nothing from it runs on the robot.  Without a
dispatcher a step only declares the request it would make.
"""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import inspect
import logging
import math
import unicodedata
from collections.abc import Callable, Mapping
from typing import Any

from .capabilities import (
    ABSOLUTE_MEASURE_OPS,
    ALL_SPECS_BY_MODULE,
    FLEET_SPECS,
    MODULE_ADVANCE,
    MODULE_HALT,
    MODULE_MAP,
    MODULE_MARK_PLACE,
    MODULE_NAVIGATE,
    MODULE_OBSERVE,
    MODULE_PLACES,
    MODULE_RETREAT,
    MODULE_ROTATE,
    OPTIONAL_CONTRACT_KEYS,
    RESOLVED_ARGUMENTS,
    SPECS_BY_MODULE,
    CapabilitySpec,
)
from .capability_request import (
    RESOURCE_PARAM,
    CapabilityRequestError,
    capability_request_for_step,
)
from .recovery import recovery_for

__all__ = [
    "HOST_DISPATCHER_CONTEXT_KEY",
    "build_fleet_modules",
    "build_modules",
    "core_measure_ops",
    "core_optional_contract_keys",
    "registrable_contract",
    "resolved_arguments",
    "supports_contract",
]

logger = logging.getLogger(__name__)

CATEGORY = "robotics"
FLEET_CATEGORY = "fleet"
PACK_VERSION = "1.3.0"

# flyto-core's context key for the host-created dispatcher (the same key
# core's own ``capability.invoke`` reads).  Workflow data cannot create one.
HOST_DISPATCHER_CONTEXT_KEY = "_flyto_runtime_external_capability_dispatcher"

# Adapter outcomes (flyto-robotics adapter_contract.OUTCOME_*) and the step
# error each one becomes.  Anything else is a failure.
OUTCOME_COMPLETED = "completed"
_OUTCOME_ERRORS = {
    "refused": "EXTERNAL_CAPABILITY_REFUSED",
    "timeout": "EXTERNAL_CAPABILITY_TIMEOUT",
    "cancelled": "EXTERNAL_CAPABILITY_CANCELLED",
    "failed": "EXTERNAL_CAPABILITY_FAILED",
}
_DISPATCH_KEYS = ("resource_id", "capability_id", "arguments")


def supports_contract(register_module: Callable[..., Any]) -> bool:
    """Whether this flyto-core's ``register_module`` accepts ``contract=``.

    flyto-core 2.35.0 adds it.  An older core is still a valid host; the steps
    then register without their contract instead of failing to register.
    """

    try:
        parameters = inspect.signature(register_module).parameters
    except (TypeError, ValueError):
        return False
    return "contract" in parameters or any(
        item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters.values()
    )


def core_optional_contract_keys() -> frozenset[str]:
    """The optional contract keys this flyto-core accepts (2.36.0 adds four).

    Feature-detected as flyto-core documents it: an older core has no
    ``OPTIONAL_FIELDS`` and its closed schema rejects the keys.
    """
    try:
        from core.capability_contract import OPTIONAL_FIELDS
    except ImportError:
        return frozenset()
    try:
        return frozenset(str(item) for item in OPTIONAL_FIELDS)
    except TypeError:
        return frozenset()


def core_measure_ops() -> frozenset[str]:
    """The evidence measure ops this flyto-core judges (2.38.0 adds the absolute ones).

    Feature-detected as flyto-core documents it: ``"distance_to" in
    core.capability_contract.MEASURE_OPS``.
    """
    try:
        from core.capability_contract import MEASURE_OPS
    except ImportError:
        return frozenset()
    try:
        return frozenset(str(item) for item in MEASURE_OPS)
    except TypeError:
        return frozenset()


def registrable_contract(
    contract: Mapping[str, Any],
    optional_keys: frozenset[str],
    measure_ops: frozenset[str],
) -> dict[str, Any]:
    """The contract as a flyto-core that accepts these keys and ops registers it.

    Optional keys it does not know are left out; so is an evidence item whose
    measure uses an absolute op it does not know (its closed schema rejects
    the whole contract otherwise). The step then still registers, with less
    declared proof, and a host holds it to what remains.
    """
    unsupported_keys = OPTIONAL_CONTRACT_KEYS - frozenset(optional_keys)
    unsupported_ops = ABSOLUTE_MEASURE_OPS - frozenset(measure_ops)
    kept = {key: value for key, value in contract.items() if key not in unsupported_keys}
    evidence = kept.get("evidence")
    if unsupported_ops and isinstance(evidence, list):
        kept["evidence"] = [
            item
            for item in evidence
            if not (isinstance(item, Mapping) and (item.get("measure") or {}).get("op") in unsupported_ops)
        ]
    return kept


def _registrar(
    register_module: Callable[..., Any],
    optional_keys: frozenset[str] | None = None,
    measure_ops: frozenset[str] | None = None,
) -> Callable[..., Any]:
    if not supports_contract(register_module):
        logger.warning(
            "flyto-core's register_module does not accept contract=; robotics steps "
            "register without their capability contracts (install flyto-core>=2.35.0)"
        )

        def without_contract(**metadata: Any) -> Any:
            metadata.pop("contract", None)
            return register_module(**metadata)

        return without_contract

    accepted = frozenset(core_optional_contract_keys() if optional_keys is None else optional_keys)
    ops = frozenset(core_measure_ops() if measure_ops is None else measure_ops)
    unsupported = OPTIONAL_CONTRACT_KEYS - accepted
    unsupported_ops = ABSOLUTE_MEASURE_OPS - ops
    if not unsupported and not unsupported_ops:
        return register_module
    logged: set[str] = set()

    def warn_once(what: str, message: str, *args: Any) -> None:
        if what not in logged:
            logged.add(what)
            logger.warning(message, *args)

    def without_newer_features(**metadata: Any) -> Any:
        contract = metadata.get("contract")
        if isinstance(contract, Mapping):
            reduced = registrable_contract(contract, accepted, ops)
            dropped_keys = sorted(set(contract) - set(reduced))
            if dropped_keys:
                warn_once(
                    "keys",
                    "flyto-core does not accept the contract keys %s; steps register "
                    "without them (install flyto-core>=2.36.0)",
                    ", ".join(dropped_keys),
                )
            if reduced.get("evidence") != contract.get("evidence"):
                warn_once(
                    "ops",
                    "flyto-core does not judge the measure ops %s; steps register "
                    "without that evidence (install flyto-core>=2.38.0)",
                    ", ".join(sorted(unsupported_ops)),
                )
            metadata["contract"] = reduced
        return register_module(**metadata)

    return without_newer_features


def _declared(spec: CapabilitySpec) -> dict[str, Any]:
    """What every step registers besides its identity, from its spec row.

    Copied, so a host that mutates registered metadata cannot change the row.
    """

    return {
        "version": PACK_VERSION,
        "category": CATEGORY if spec.module_id in SPECS_BY_MODULE else FLEET_CATEGORY,
        "subcategory": spec.capability_id.split(".", 1)[0],
        "tags": list(spec.tags),
        "label": spec.label,
        "label_key": f"modules.{spec.module_id}.label",
        "description": spec.description,
        "description_key": f"modules.{spec.module_id}.description",
        "icon": spec.icon,
        "color": spec.color,
        "input_types": ["*"],
        "output_types": ["object"],
        "can_receive_from": ["*"],
        "can_connect_to": ["*"],
        "params_schema": copy.deepcopy(dict(spec.params_schema)),
        "contract": copy.deepcopy(dict(spec.contract)),
        "timeout_ms": spec.timeout_ms,
        "retryable": spec.retryable,
        # One commanded resource is driven by one call at a time.
        "concurrent_safe": False,
        "requires_credentials": False,
        "handles_sensitive_data": False,
    }


def _resource_id(step: Any) -> str:
    """The commanded resource, never the computer executing the workflow."""

    named = str(step.params.get(RESOURCE_PARAM) or "").strip()
    return named or str(step.context.get(RESOURCE_PARAM, "")).strip()


def _refused(module_id: str, exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": str(exc)[:300],
        "error_code": "CAPABILITY_ARGUMENTS_REFUSED",
        "dispatched": False,
        "module_id": module_id,
    }


def _trusted(dispatcher: Any) -> bool:
    # Checked on the type: an instance attribute set from workflow data, or a
    # plain mapping with an "invoke" key, is not host authority.
    return getattr(type(dispatcher), "_flyto_runtime_opaque", False) is True and callable(
        getattr(dispatcher, "invoke", None)
    )


async def _dispatch_or_declare(step: Any, request: dict[str, Any]) -> dict[str, Any]:
    """Run the request through the host's dispatcher, or only declare it."""

    dispatcher = step.context.get(HOST_DISPATCHER_CONTEXT_KEY)
    if dispatcher is None:
        return {
            "dispatched": False,
            "commanded_resource": request["resource_id"],
            "capability_request": request,
        }
    if not _trusted(dispatcher):
        raise RuntimeError("untrusted external capability dispatcher")

    record = await dispatcher.invoke({key: request[key] for key in _DISPATCH_KEYS})
    if not isinstance(record, Mapping):
        return {
            "ok": False,
            "error": "the host dispatcher returned no execution record",
            "error_code": "EXTERNAL_CAPABILITY_FAILED",
            "dispatched": True,
            "commanded_resource": request["resource_id"],
        }
    outcome = str(record.get("outcome") or "")
    result: dict[str, Any] = {
        "dispatched": True,
        "commanded_resource": request["resource_id"],
        "capability_request": request,
        "outcome": outcome,
        "execution": _without_artifact_bytes(record),
    }
    result.update(_place_facts(request, record))
    if outcome == OUTCOME_COMPLETED:
        return {"ok": True, **result}
    failed = {
        "ok": False,
        "error": str(record.get("detail") or outcome or "external capability failed")[:300],
        "error_code": _OUTCOME_ERRORS.get(outcome, "EXTERNAL_CAPABILITY_FAILED"),
        **result,
    }
    spec = ALL_SPECS_BY_MODULE.get(step.module_id)
    recovery = recovery_for(spec, record) if spec is not None else None
    if recovery is not None:
        # The contract's declared recovery with the adapter's measurements:
        # what a planner may try instead, and what it is told about the stop.
        failed["recovery"] = recovery
    return failed


def _adapter_evidence(record: Mapping[str, Any]) -> Mapping[str, Any]:
    evidence = record.get("adapter_evidence")
    return evidence if isinstance(evidence, Mapping) else {}


def _finite(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def resolved_arguments(
    arguments: Mapping[str, Any], record: Mapping[str, Any]
) -> dict[str, Any] | None:
    """A navigation by place's arguments with the coordinates it resolved to.

    The arrival evidence reads its target from the call's arguments
    (``distance_to`` over ``x``/``y``, ``angle_to`` on ``yaw_radians``); a
    call by place names none of them. The adapter, the one resolver, reports
    what the place stood for, and this is the call's arguments overlaid with
    it: what a host judges the contract's evidence against. None unless the
    call named a place and the adapter reports finite coordinates for that
    same place; an authored argument is never replaced.
    """
    place = arguments.get("place")
    if not isinstance(place, str):
        return None
    evidence = _adapter_evidence(record)
    resolved = evidence.get(RESOLVED_ARGUMENTS)
    target = evidence.get("navigation_target")
    if not isinstance(resolved, Mapping) or not isinstance(target, Mapping):
        return None
    # The adapter normalises the name (NFC, case of the stored place), so the
    # target names the place it found; compare as the adapter does.
    named = target.get("place")
    if not isinstance(named, str) or (
        unicodedata.normalize("NFC", named.casefold())
        != unicodedata.normalize("NFC", place.strip().casefold())
    ):
        return None
    if not (_finite(resolved.get("x")) and _finite(resolved.get("y"))):
        return None
    filled = {
        key: float(resolved[key])
        for key in ("x", "y", "yaw_radians")
        if _finite(resolved.get(key)) and key not in arguments
    }
    return {**dict(arguments), **filled}


def _place_facts(request: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any]:
    """What the places capabilities and a navigation by place add to a step's output."""
    capability_id = request.get("capability_id")
    evidence = _adapter_evidence(record)
    facts: dict[str, Any] = {}
    if capability_id == SPECS_BY_MODULE[MODULE_NAVIGATE].capability_id:
        resolved = resolved_arguments(request.get("arguments") or {}, record)
        if resolved is not None:
            facts[RESOLVED_ARGUMENTS] = resolved
        if isinstance(evidence.get("known_places"), list):
            facts["known_places"] = [str(item) for item in evidence["known_places"]]
    elif capability_id == SPECS_BY_MODULE[MODULE_PLACES].capability_id:
        if isinstance(evidence.get("places"), list):
            facts["places"] = [dict(item) for item in evidence["places"] if isinstance(item, Mapping)]
    elif capability_id == SPECS_BY_MODULE[MODULE_MARK_PLACE].capability_id:
        if isinstance(evidence.get("place"), Mapping):
            facts["place"] = dict(evidence["place"])
    return facts


# Encoded picture fields of the legacy ``capture`` (flyto-robotics before the
# artifact transport, still sent beside ``artifacts``): the photo's JPEG and the
# map's occupancy cells.
_CAPTURE_BYTE_FIELDS = ("data_base64", "cells_base64")


def _digest(data: Any) -> dict[str, Any] | None:
    """``{bytes, sha256}`` of a base64 string, or None when it is not one."""
    if not isinstance(data, str):
        return None
    try:
        raw = base64.b64decode(data, validate=True)
    except (ValueError, binascii.Error):
        return {}
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _without_artifact_bytes(record: Mapping[str, Any]) -> dict[str, Any]:
    """The execution record as a step output, without the pictures' bytes.

    The host keeps returned artifacts itself (and uploads them); a step output
    travels with the run's progress, so each artifact is reduced to its kind,
    media type, size and digest there. The legacy ``capture`` the adapter
    still sends beside them carries the same picture (or the map's cells) and
    is reduced the same way: a host that reads ``capture`` reads it from the
    adapter's result, before the step output exists.
    """
    execution = dict(record)
    evidence = execution.get("adapter_evidence")
    if not isinstance(evidence, Mapping):
        return execution
    reduced = dict(evidence)
    if isinstance(evidence.get("artifacts"), list):
        summaries = []
        for item in evidence["artifacts"]:
            if not isinstance(item, Mapping):
                continue
            summary = {key: item[key] for key in ("kind", "media_type") if key in item}
            summary.update(_digest(item.get("data_base64")) or {})
            summaries.append(summary)
        reduced["artifacts"] = summaries
    capture = evidence.get("capture")
    if isinstance(capture, Mapping) and any(field in capture for field in _CAPTURE_BYTE_FIELDS):
        kept = {key: value for key, value in capture.items() if key not in _CAPTURE_BYTE_FIELDS}
        for field in _CAPTURE_BYTE_FIELDS:
            if field in capture:
                stem = field[: -len("_base64")]
                for key, value in (_digest(capture[field]) or {}).items():
                    kept[f"{stem}_{key}"] = value
        reduced["capture"] = kept
    execution["adapter_evidence"] = reduced
    return execution


def _capability_step(base_module) -> type:
    class CapabilityStep(base_module):
        """Shared behaviour: validate against the spec, then dispatch or declare."""

        module_id = ""

        def validate_params(self) -> None:
            # Bounds are checked on the canvas, before anything is dispatched.
            capability_request_for_step(
                self.module_id, self.params, resource_id="validation-only"
            )

        async def execute(self) -> dict[str, Any]:
            try:
                request = capability_request_for_step(
                    self.module_id, self.params, resource_id=_resource_id(self)
                )
            except CapabilityRequestError as exc:
                return _refused(self.module_id, exc)
            if request is None:  # pragma: no cover - ids and specs are co-owned
                return _refused(self.module_id, CapabilityRequestError("unknown step"))
            return await _dispatch_or_declare(self, request)

    return CapabilityStep


def build_fleet_modules(
    base_module,
    register_module,
    *,
    optional_keys: frozenset[str] | None = None,
    measure_ops: frozenset[str] | None = None,
) -> list[tuple[str, type]]:
    """Register the Open-RMF fleet steps (the ``fleet`` pack).

    Same contract, same dispatcher: the host routes the request to the
    flyto-robotics ``open_rmf.fleet`` adapter for a ``fleet:<name>`` resource.
    """

    register = _registrar(register_module, optional_keys, measure_ops)
    step = _capability_step(base_module)
    registered: list[tuple[str, type]] = []
    for spec in FLEET_SPECS:
        name = "".join(part.capitalize() for part in spec.module_id.replace(".", "_").split("_"))
        cls = type(name, (step,), {"module_id": spec.module_id})
        cls = register(
            module_id=spec.module_id,
            provides_capability=spec.capability_id,
            **_declared(spec),
        )(cls)
        registered.append((spec.module_id, cls))
    return registered


def build_modules(
    base_module,
    register_module,
    *,
    optional_keys: frozenset[str] | None = None,
    measure_ops: frozenset[str] | None = None,
) -> list[tuple[str, type]]:
    """Register the nine capability steps against flyto-core's API."""

    register = _registrar(register_module, optional_keys, measure_ops)
    CapabilityStep = _capability_step(base_module)

    def spec(module_id: str) -> CapabilitySpec:
        return SPECS_BY_MODULE[module_id]

    @register(
        module_id=MODULE_ADVANCE,
        provides_capability=spec(MODULE_ADVANCE).capability_id,
        **_declared(spec(MODULE_ADVANCE)),
    )
    class Advance(CapabilityStep):
        module_id = MODULE_ADVANCE

    @register(
        module_id=MODULE_RETREAT,
        provides_capability=spec(MODULE_RETREAT).capability_id,
        **_declared(spec(MODULE_RETREAT)),
    )
    class Retreat(CapabilityStep):
        module_id = MODULE_RETREAT

    @register(
        module_id=MODULE_ROTATE,
        provides_capability=spec(MODULE_ROTATE).capability_id,
        **_declared(spec(MODULE_ROTATE)),
    )
    class Rotate(CapabilityStep):
        module_id = MODULE_ROTATE

    @register(
        module_id=MODULE_HALT,
        provides_capability=spec(MODULE_HALT).capability_id,
        **_declared(spec(MODULE_HALT)),
    )
    class Halt(CapabilityStep):
        module_id = MODULE_HALT

    @register(
        module_id=MODULE_NAVIGATE,
        provides_capability=spec(MODULE_NAVIGATE).capability_id,
        **_declared(spec(MODULE_NAVIGATE)),
    )
    class Navigate(CapabilityStep):
        module_id = MODULE_NAVIGATE

    @register(
        module_id=MODULE_OBSERVE,
        provides_capability=spec(MODULE_OBSERVE).capability_id,
        **_declared(spec(MODULE_OBSERVE)),
    )
    class Observe(CapabilityStep):
        module_id = MODULE_OBSERVE

    @register(
        module_id=MODULE_MAP,
        provides_capability=spec(MODULE_MAP).capability_id,
        **_declared(spec(MODULE_MAP)),
    )
    class CaptureMap(CapabilityStep):
        module_id = MODULE_MAP

    @register(
        module_id=MODULE_PLACES,
        provides_capability=spec(MODULE_PLACES).capability_id,
        **_declared(spec(MODULE_PLACES)),
    )
    class Places(CapabilityStep):
        module_id = MODULE_PLACES

    @register(
        module_id=MODULE_MARK_PLACE,
        provides_capability=spec(MODULE_MARK_PLACE).capability_id,
        **_declared(spec(MODULE_MARK_PLACE)),
    )
    class MarkPlace(CapabilityStep):
        module_id = MODULE_MARK_PLACE

    return [
        (MODULE_ADVANCE, Advance),
        (MODULE_RETREAT, Retreat),
        (MODULE_ROTATE, Rotate),
        (MODULE_HALT, Halt),
        (MODULE_NAVIGATE, Navigate),
        (MODULE_OBSERVE, Observe),
        (MODULE_MAP, CaptureMap),
        (MODULE_PLACES, Places),
        (MODULE_MARK_PLACE, MarkPlace),
    ]
