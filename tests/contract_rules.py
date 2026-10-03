"""A minimal copy of the flyto.capability-contract.v1 rules and arithmetic.

Vendored so the suite proves the contracts are well formed without flyto-core.
When flyto-core's own ``core.capability_contract`` is installed, the tests run
the same contracts through it as well; this copy is never shipped.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
CONTRACT_KEYS = {
    "actuates",
    "safety_class",
    "requires_safe_stop",
    "cancellable",
    "idempotent",
    "effects",
    "requires",
    "evidence",
}
REQUIRED_KEYS = {"actuates", "safety_class", "requires_safe_stop", "cancellable", "idempotent"}
SAFETY_CLASSES = {"read_only", "controlled", "movement", "dangerous"}
EVIDENCE_KEYS = {"kind", "observe", "phases", "measure", "expect", "tolerance", "settle"}
PHASES = ("before", "after", "settled")
SINGLE_FIELD_OPS = {"delta", "angle_delta", "abs_angle_delta"}
OPS = {"distance", *SINGLE_FIELD_OPS}


class ContractInvalid(ValueError):
    pass


def _identifier(value: Any, where: str) -> None:
    if type(value) is not str or len(value) > 96 or not IDENTIFIER.fullmatch(value):
        raise ContractInvalid(f"{where} is not a bounded identifier")


def _identifiers(value: Any, where: str, limit: int) -> None:
    if type(value) is not list or len(value) > limit:
        raise ContractInvalid(f"{where} must be a list of at most {limit}")
    for item in value:
        _identifier(item, where)
    if len(set(value)) != len(value):
        raise ContractInvalid(f"{where} has duplicates")


def _non_negative(value: Any, where: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ContractInvalid(f"{where} must be a finite non-negative number")


def _evidence(item: Any, params_schema: Mapping[str, Any]) -> None:
    if type(item) is not dict or not set(item) <= EVIDENCE_KEYS:
        raise ContractInvalid("evidence item has unknown keys")
    if not {"kind", "observe", "phases", "measure", "expect", "tolerance"} <= set(item):
        raise ContractInvalid("evidence item is incomplete")
    _identifier(item["kind"], "evidence.kind")
    _identifier(item["observe"], "evidence.observe")
    phases = item["phases"]
    if (
        type(phases) is not list
        or len(phases) < 2
        or not set(phases) <= set(PHASES)
        or phases != sorted(set(phases), key=PHASES.index)
    ):
        raise ContractInvalid("evidence.phases must be an ordered subset of before|after|settled")
    measure = item["measure"]
    if type(measure) is not dict or set(measure) != {"op", "fields"} or measure["op"] not in OPS:
        raise ContractInvalid("evidence.measure is invalid")
    fields = measure["fields"]
    if type(fields) is not list or not 1 <= len(fields) <= 3:
        raise ContractInvalid("evidence.measure.fields must have 1..3 identifiers")
    for name in fields:
        _identifier(name, "evidence.measure.fields")
    if measure["op"] in SINGLE_FIELD_OPS and len(fields) != 1:
        raise ContractInvalid(f"{measure['op']} measures exactly one field")
    expect = item["expect"]
    if type(expect) is not dict or len(expect) != 1:
        raise ContractInvalid("evidence.expect names one argument or one value")
    if "argument" in expect:
        if expect["argument"] not in params_schema:
            raise ContractInvalid("evidence.expect.argument is not a declared parameter")
    elif "value" in expect:
        value = expect["value"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ContractInvalid("evidence.expect.value must be finite")
    else:
        raise ContractInvalid("evidence.expect is invalid")
    tolerance = item["tolerance"]
    if type(tolerance) is not dict or not tolerance or not set(tolerance) <= {"absolute", "relative"}:
        raise ContractInvalid("evidence.tolerance is invalid")
    for key, value in tolerance.items():
        _non_negative(value, f"evidence.tolerance.{key}")
    if "settle" in item:
        settle = item["settle"]
        if type(settle) is not dict or set(settle) != {"max_drift"}:
            raise ContractInvalid("evidence.settle is invalid")
        _non_negative(settle["max_drift"], "evidence.settle.max_drift")
        if not {"after", "settled"} <= set(phases):
            raise ContractInvalid("evidence.settle needs the after and settled phases")


def validate_contract(contract: Any, params_schema: Mapping[str, Any]) -> None:
    if type(contract) is not dict or not set(contract) <= CONTRACT_KEYS:
        raise ContractInvalid("contract has unknown keys")
    if not REQUIRED_KEYS <= set(contract):
        raise ContractInvalid("contract is missing required keys")
    for key in ("actuates", "requires_safe_stop", "cancellable", "idempotent"):
        if type(contract[key]) is not bool:
            raise ContractInvalid(f"{key} must be a boolean")
    if contract["safety_class"] not in SAFETY_CLASSES:
        raise ContractInvalid("safety_class is not known")
    _identifiers(contract.get("effects", []), "effects", 16)
    _identifiers(contract.get("requires", []), "requires", 16)
    evidence = contract.get("evidence", [])
    if type(evidence) is not list or len(evidence) > 8:
        raise ContractInvalid("evidence must be a list of at most 8")
    for item in evidence:
        _evidence(item, params_schema)
    if contract["actuates"]:
        for name, field in params_schema.items():
            if field.get("type") == "number" and not {"min", "max"} <= set(field):
                raise ContractInvalid(f"actuating parameter {name} must declare min and max")


def _wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def _measure(op: str, fields: list[str], start: Mapping[str, float], end: Mapping[str, float]) -> float:
    if op == "distance":
        return math.sqrt(sum((end[name] - start[name]) ** 2 for name in fields))
    (name,) = fields
    if op == "delta":
        return end[name] - start[name]
    if op == "angle_delta":
        return _wrap(end[name] - start[name])
    return abs(_wrap(end[name] - start[name]))


def judge(
    spec: Mapping[str, Any],
    arguments: Mapping[str, float],
    observations: Mapping[str, Mapping[str, float]],
) -> dict[str, Any]:
    """|measured - expected| <= max(absolute, relative*|expected|), plus settle drift."""

    phases = spec["phases"]
    op, fields = spec["measure"]["op"], spec["measure"]["fields"]
    measured = _measure(op, fields, observations[phases[0]], observations[phases[-1]])
    expect = spec["expect"]
    expected = float(arguments[expect["argument"]]) if "argument" in expect else float(expect["value"])
    tolerance = spec["tolerance"]
    allowed = max(tolerance.get("absolute", 0.0), tolerance.get("relative", 0.0) * abs(expected))
    usable = abs(measured - expected) <= allowed
    drift = None
    if "settle" in spec:
        drift = _measure(op, fields, observations["after"], observations["settled"])
        usable = usable and abs(drift) <= spec["settle"]["max_drift"]
    return {
        "usable": usable,
        "measured": measured,
        "expected": expected,
        "allowed": allowed,
        "settle_drift": drift,
    }
