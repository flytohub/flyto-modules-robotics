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
CONTRACT_SCHEMA = "flyto.capability-contract.v1"
CONTRACT_KEYS = {
    "schema",
    "actuates",
    "safety_class",
    "requires_safe_stop",
    "cancellable",
    "idempotent",
    "effects",
    "requires",
    "evidence",
    # flyto-core 2.36.0
    "role",
    "artifacts",
    "recovery",
    "expected_duration_ms",
}
OPTIONAL_KEYS = {"role", "artifacts", "recovery", "expected_duration_ms"}
MEDIA_TYPE = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]{0,63}/[a-z0-9][a-z0-9!#$&^_.+-]{0,63}$")
ARTIFACT_MAX_BYTES = 20 * 1024 * 1024
REQUIRED_KEYS = {"actuates", "safety_class", "requires_safe_stop", "cancellable", "idempotent"}
SAFETY_CLASSES = {"read_only", "controlled", "movement", "dangerous"}
EVIDENCE_KEYS = {"kind", "observe", "phases", "measure", "expect", "tolerance", "settle"}
PHASES = ("before", "after", "settled")
SINGLE_FIELD_OPS = {"delta", "angle_delta", "abs_angle_delta"}
ANGLE_OPS = {"angle_delta", "abs_angle_delta"}
OPS = {"distance", "along", *SINGLE_FIELD_OPS}


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
        or not {"before", "after"} <= set(phases)
        or not set(phases) <= set(PHASES)
        or phases != sorted(set(phases), key=PHASES.index)
    ):
        raise ContractInvalid(
            "evidence.phases must be an ordered subset of before|after|settled with before and after"
        )
    measure = item["measure"]
    if type(measure) is not dict or measure.get("op") not in OPS:
        raise ContractInvalid("evidence.measure is invalid")
    expected_keys = {"op", "fields", "heading_field"} if measure["op"] == "along" else {"op", "fields"}
    if set(measure) != expected_keys:
        raise ContractInvalid("evidence.measure keys do not fit its op")
    fields = measure["fields"]
    if type(fields) is not list or not 1 <= len(fields) <= 3:
        raise ContractInvalid("evidence.measure.fields must have 1..3 identifiers")
    for name in fields:
        _identifier(name, "evidence.measure.fields")
    if len(set(fields)) != len(fields):
        raise ContractInvalid("evidence.measure.fields has duplicates")
    if measure["op"] in SINGLE_FIELD_OPS and len(fields) != 1:
        raise ContractInvalid(f"{measure['op']} measures exactly one field")
    if measure["op"] == "along":
        if len(fields) != 2:
            raise ContractInvalid("along measures exactly two position fields")
        _identifier(measure["heading_field"], "evidence.measure.heading_field")
        if measure["heading_field"] in fields:
            raise ContractInvalid("heading_field is not one of the position fields")
    expect = item["expect"]
    if type(expect) is not dict:
        raise ContractInvalid("evidence.expect is invalid")
    if "argument" in expect:
        if not set(expect) <= {"argument", "scale"}:
            raise ContractInvalid("evidence.expect has unknown keys")
        if params_schema.get(expect["argument"], {}).get("type") not in ("number", "integer"):
            raise ContractInvalid("evidence.expect.argument is not a declared numeric parameter")
        scale = expect.get("scale", 1)
        if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale == 0:
            raise ContractInvalid("evidence.expect.scale must be finite and non-zero")
    elif set(expect) == {"value"}:
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
        if "settled" not in phases:
            raise ContractInvalid("evidence.settle needs the settled phase")


def validate_contract(contract: Any, params_schema: Mapping[str, Any]) -> None:
    if type(contract) is not dict or not set(contract) <= CONTRACT_KEYS:
        raise ContractInvalid("contract has unknown keys")
    if contract.get("schema", CONTRACT_SCHEMA) != CONTRACT_SCHEMA:
        raise ContractInvalid("contract schema is not v1")
    if not REQUIRED_KEYS <= set(contract):
        raise ContractInvalid("contract is missing required keys")
    for key in ("actuates", "requires_safe_stop", "cancellable", "idempotent"):
        if type(contract[key]) is not bool:
            raise ContractInvalid(f"{key} must be a boolean")
    if contract["safety_class"] not in SAFETY_CLASSES:
        raise ContractInvalid("safety_class is not known")
    if contract["actuates"] and contract["safety_class"] == "read_only":
        raise ContractInvalid("an actuating contract cannot be read_only")
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
    _optional(contract)


def _optional(contract: Mapping[str, Any]) -> None:
    """The four keys flyto-core 2.36.0 added, checked only when declared."""
    if "role" in contract:
        if contract["role"] != "safe_stop":
            raise ContractInvalid("role must be safe_stop")
        if contract["cancellable"] or contract["requires_safe_stop"] or not contract["idempotent"]:
            raise ContractInvalid("a safe_stop is uncancellable, idempotent and needs no stop")
    if "artifacts" in contract:
        artifacts = contract["artifacts"]
        if type(artifacts) is not list or not 1 <= len(artifacts) <= 8:
            raise ContractInvalid("artifacts must be 1..8 declarations")
        kinds = []
        for item in artifacts:
            if type(item) is not dict or set(item) != {"kind", "media_types", "max_bytes"}:
                raise ContractInvalid("an artifact declares exactly kind, media_types, max_bytes")
            _identifier(item["kind"], "artifacts.kind")
            kinds.append(item["kind"])
            media = item["media_types"]
            if type(media) is not list or not 1 <= len(media) <= 8 or len(set(media)) != len(media):
                raise ContractInvalid("artifacts.media_types must be 1..8 distinct types")
            for media_type in media:
                if type(media_type) is not str or not MEDIA_TYPE.fullmatch(media_type):
                    raise ContractInvalid("artifacts.media_types holds lower-case type/subtype")
            size = item["max_bytes"]
            if type(size) is not int or not 1 <= size <= ARTIFACT_MAX_BYTES:
                raise ContractInvalid("artifacts.max_bytes is out of range")
        if len(set(kinds)) != len(kinds):
            raise ContractInvalid("artifacts declare a kind twice")
    if "recovery" in contract:
        recovery = contract["recovery"]
        if type(recovery) is not dict or "capabilities" not in recovery:
            raise ContractInvalid("recovery needs capabilities")
        if not set(recovery) <= {"capabilities", "observe", "guidance"}:
            raise ContractInvalid("recovery has unknown keys")
        _identifiers(recovery["capabilities"], "recovery.capabilities", 8)
        if not recovery["capabilities"]:
            raise ContractInvalid("recovery.capabilities is empty")
        if "observe" in recovery:
            _identifier(recovery["observe"], "recovery.observe")
        guidance = recovery.get("guidance", "x")
        if type(guidance) is not str or not guidance.strip() or len(guidance) > 500:
            raise ContractInvalid("recovery.guidance is 1..500 characters")
    if "expected_duration_ms" in contract:
        duration = contract["expected_duration_ms"]
        if type(duration) is not int or not 1 <= duration <= 3_600_000:
            raise ContractInvalid("expected_duration_ms is out of range")


def wrap(angle: float) -> float:
    """Wrap into (-pi, pi]."""

    r = math.remainder(angle, 2 * math.pi)
    return r + 2 * math.pi if r <= -math.pi else r


def _euclidean(fields, start, end) -> float:
    return math.sqrt(sum((end[name] - start[name]) ** 2 for name in fields))


def _measure(measure: Mapping[str, Any], start: Mapping[str, float], end: Mapping[str, float]) -> float:
    op, fields = measure["op"], measure["fields"]
    if op == "distance":
        return _euclidean(fields, start, end)
    if op == "along":
        heading = start[measure["heading_field"]]
        first, second = fields
        return (end[first] - start[first]) * math.cos(heading) + (end[second] - start[second]) * math.sin(
            heading
        )
    (name,) = fields
    if op == "delta":
        return end[name] - start[name]
    if op == "angle_delta":
        return wrap(end[name] - start[name])
    return abs(wrap(end[name] - start[name]))


def _drift(measure: Mapping[str, Any], after: Mapping[str, float], settled: Mapping[str, float]) -> float:
    op, fields = measure["op"], measure["fields"]
    if op in ("distance", "along"):
        return _euclidean(fields, after, settled)
    (name,) = fields
    if op == "delta":
        return abs(settled[name] - after[name])
    return abs(wrap(settled[name] - after[name]))


def judge(
    spec: Mapping[str, Any],
    arguments: Mapping[str, float],
    observations: Mapping[str, Mapping[str, float]],
) -> dict[str, Any]:
    """The arithmetic of flyto-core docs/CAPABILITY_CONTRACT.md "Judging evidence"."""

    measure, phases = spec["measure"], spec["phases"]
    measured = _measure(measure, observations["before"], observations[phases[-1]])
    expect = spec["expect"]
    if "argument" in expect:
        expected = float(expect.get("scale", 1)) * float(arguments[expect["argument"]])
        if measure["op"] == "abs_angle_delta":
            expected = abs(expected)
    else:
        expected = float(expect["value"])
    tolerance = spec["tolerance"]
    allowed = max(tolerance.get("absolute", 0.0), tolerance.get("relative", 0.0) * abs(expected))
    if measure["op"] in ANGLE_OPS:
        error = abs(wrap(measured - expected))
    else:
        error = abs(measured - expected)
    drift = None
    if "settle" in spec:
        drift = _drift(measure, observations["after"], observations["settled"])
    usable = error <= allowed and (drift is None or drift <= spec["settle"]["max_drift"])
    return {
        "usable": usable,
        "measured": measured,
        "expected": expected,
        "allowed": allowed,
        "settle_drift": drift,
    }
