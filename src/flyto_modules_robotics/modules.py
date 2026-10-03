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
from collections.abc import Callable, Mapping
from typing import Any

from .capabilities import (
    ALL_SPECS_BY_MODULE,
    FLEET_SPECS,
    MODULE_ADVANCE,
    MODULE_HALT,
    MODULE_MAP,
    MODULE_NAVIGATE,
    MODULE_OBSERVE,
    MODULE_RETREAT,
    MODULE_ROTATE,
    OPTIONAL_CONTRACT_KEYS,
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
    "core_optional_contract_keys",
    "supports_contract",
]

logger = logging.getLogger(__name__)

CATEGORY = "robotics"
FLEET_CATEGORY = "fleet"
PACK_VERSION = "1.1.0"

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


def _registrar(
    register_module: Callable[..., Any], optional_keys: frozenset[str] | None = None
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

    accepted = core_optional_contract_keys() if optional_keys is None else optional_keys
    unsupported = OPTIONAL_CONTRACT_KEYS - frozenset(accepted)
    if not unsupported:
        return register_module
    logged: list[bool] = []

    def without_newer_keys(**metadata: Any) -> Any:
        contract = metadata.get("contract")
        if isinstance(contract, Mapping) and unsupported & set(contract):
            if not logged:
                logged.append(True)
                logger.warning(
                    "flyto-core does not accept the contract keys %s; steps register "
                    "without them (install flyto-core>=2.36.0)",
                    ", ".join(sorted(unsupported & set(contract))),
                )
            metadata["contract"] = {
                key: value for key, value in contract.items() if key not in unsupported
            }
        return register_module(**metadata)

    return without_newer_keys


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


def _without_artifact_bytes(record: Mapping[str, Any]) -> dict[str, Any]:
    """The execution record as a step output, without the pictures' bytes.

    The host keeps returned artifacts itself (and uploads them); a step output
    travels with the run's progress, so each artifact is reduced to its kind,
    media type, size and digest there.
    """
    execution = dict(record)
    evidence = execution.get("adapter_evidence")
    if not isinstance(evidence, Mapping) or not isinstance(evidence.get("artifacts"), list):
        return execution
    summaries = []
    for item in evidence["artifacts"]:
        if not isinstance(item, Mapping):
            continue
        summary = {key: item[key] for key in ("kind", "media_type") if key in item}
        data = item.get("data_base64")
        if isinstance(data, str):
            try:
                raw = base64.b64decode(data, validate=True)
            except (ValueError, binascii.Error):
                raw = None
            if raw is not None:
                summary["bytes"] = len(raw)
                summary["sha256"] = hashlib.sha256(raw).hexdigest()
        summaries.append(summary)
    execution["adapter_evidence"] = {**evidence, "artifacts": summaries}
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
    base_module, register_module, *, optional_keys: frozenset[str] | None = None
) -> list[tuple[str, type]]:
    """Register the Open-RMF fleet steps (the ``fleet`` pack).

    Same contract, same dispatcher: the host routes the request to the
    flyto-robotics ``open_rmf.fleet`` adapter for a ``fleet:<name>`` resource.
    """

    register = _registrar(register_module, optional_keys)
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
    base_module, register_module, *, optional_keys: frozenset[str] | None = None
) -> list[tuple[str, type]]:
    """Register the seven capability steps against flyto-core's API."""

    register = _registrar(register_module, optional_keys)
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

    return [
        (MODULE_ADVANCE, Advance),
        (MODULE_RETREAT, Retreat),
        (MODULE_ROTATE, Rotate),
        (MODULE_HALT, Halt),
        (MODULE_NAVIGATE, Navigate),
        (MODULE_OBSERVE, Observe),
        (MODULE_MAP, CaptureMap),
    ]
