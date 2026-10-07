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
SINGLE_FIELD_OPS = {"delta", "angle_delta", "abs_angle_delta", "angle_to"}
ANGLE_OPS = {"angle_delta", "abs_angle_delta", "angle_to"}
# flyto-core 2.38.0: compared with a target in the call's arguments.
ABSOLUTE_OPS = {"distance_to", "angle_to"}
OPS = {"distance", "along", "distance_to", *SINGLE_FIELD_OPS}


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
    measure = item["measure"]
    if type(measure) is not dict or measure.get("op") not in OPS:
        raise ContractInvalid("evidence.measure is invalid")
    absolute = measure["op"] in ABSOLUTE_OPS
    needed = {"after"} if absolute else {"before", "after"}
    if (
        type(phases) is not list
        or not needed <= set(phases)
        or not set(phases) <= set(PHASES)
        or phases != sorted(set(phases), key=PHASES.index)
    ):
        raise ContractInvalid(
            "evidence.phases must be an ordered subset of before|after|settled with "
            + " and ".join(sorted(needed))
        )
    expected_keys = {"op", "fields", "heading_field"} if measure["op"] == "along" else {"op", "fields"}
    if set(measure) - {"frame"} != expected_keys:
        raise ContractInvalid("evidence.measure keys do not fit its op")
    if "frame" in measure:
        _identifier(measure["frame"], "evidence.measure.frame")
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
    if absolute:
        _absolute_expect(measure["op"], fields, expect, params_schema)
    elif "argument" in expect:
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
    if absolute and tolerance.get("relative", 0) != 0:
        raise ContractInvalid("an absolute target takes no relative tolerance")
    if "settle" in item:
        settle = item["settle"]
        if type(settle) is not dict or set(settle) != {"max_drift"}:
            raise ContractInvalid("evidence.settle is invalid")
        _non_negative(settle["max_drift"], "evidence.settle.max_drift")
        if "settled" not in phases:
            raise ContractInvalid("evidence.settle needs the settled phase")


def _numeric_parameter(name: Any, params_schema: Mapping[str, Any]) -> None:
    if type(name) is not str or params_schema.get(name, {}).get("type") not in ("number", "integer"):
        raise ContractInvalid("evidence.expect names no declared numeric parameter")


def _absolute_expect(op: str, fields: list[str], expect: Mapping[str, Any], params_schema) -> None:
    if op == "distance_to":
        targets = expect.get("arguments")
        if set(expect) != {"arguments"} or type(targets) is not dict or set(targets) != set(fields):
            raise ContractInvalid("distance_to names one parameter per measured field")
        for name in targets.values():
            _numeric_parameter(name, params_schema)
        return
    if not {"argument"} <= set(expect) <= {"argument", "optional"}:
        raise ContractInvalid("angle_to takes argument and optional only")
    _numeric_parameter(expect["argument"], params_schema)
    optional = expect.get("optional", False)
    if type(optional) is not bool:
        raise ContractInvalid("evidence.expect.optional must be a bool")
    if optional and params_schema[expect["argument"]].get("required") is True:
        raise ContractInvalid("an optional target cannot be a required parameter")


RECOVERY_REPORT = {"capabilities", "observe", "guidance"}
# flyto-core 2.39.0
RECOVERY_SEMANTICS = {"on", "alternatives", "preserves", "resource_scope", "fills"}
STOP_FAMILIES = {"obstruction", "no_passage", "stopped_short"}
PRESERVES = {"destination", "target"}


def _closed(value: Any, allowed: set, where: str) -> None:
    if type(value) is not list or not 1 <= len(value) <= len(allowed) or len(set(value)) != len(value):
        raise ContractInvalid(f"{where} must be 1..{len(allowed)} distinct values")
    if not set(value) <= allowed:
        raise ContractInvalid(f"{where} may name only {sorted(allowed)}")


def _roles(value: Any, where: str) -> None:
    _identifiers(value, where, 8)
    if not value:
        raise ContractInvalid(f"{where} is empty")


def _recovery(recovery: Any) -> None:
    if type(recovery) is not dict:
        raise ContractInvalid("recovery must be a mapping")
    if not set(recovery) <= RECOVERY_REPORT | RECOVERY_SEMANTICS:
        raise ContractInvalid("recovery has unknown keys")
    if not {"capabilities", "alternatives", "fills"} & set(recovery):
        raise ContractInvalid("recovery declares neither capabilities, alternatives nor fills")
    if "capabilities" in recovery:
        _roles(recovery["capabilities"], "recovery.capabilities")
    if "observe" in recovery:
        _identifier(recovery["observe"], "recovery.observe")
    guidance = recovery.get("guidance", "x")
    if type(guidance) is not str or not guidance.strip() or len(guidance) > 500:
        raise ContractInvalid("recovery.guidance is 1..500 characters")
    if "on" in recovery:
        _closed(recovery["on"], STOP_FAMILIES, "recovery.on")
    if "preserves" in recovery:
        _closed(recovery["preserves"], PRESERVES, "recovery.preserves")
    for key in ("alternatives", "fills"):
        if key in recovery:
            _roles(recovery[key], f"recovery.{key}")
    if "resource_scope" in recovery and recovery["resource_scope"] != "same_resource":
        raise ContractInvalid("recovery.resource_scope must be same_resource")
    recovers = "alternatives" in recovery
    if ("on" in recovery) != recovers or recovers != ("resource_scope" in recovery):
        raise ContractInvalid("recovery.on, alternatives and resource_scope come together")
    if "preserves" in recovery and not recovers:
        raise ContractInvalid("recovery.preserves describes a way round")


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
        _recovery(contract["recovery"])
    if "expected_duration_ms" in contract:
        duration = contract["expected_duration_ms"]
        if type(duration) is not int or not 1 <= duration <= 3_600_000:
            raise ContractInvalid("expected_duration_ms is out of range")


def wrap(angle: float) -> float:
    """Wrap into (-pi, pi]."""

    r = math.remainder(angle, 2 * math.pi)
    return r + 2 * math.pi if r <= -math.pi else r


def _is_finite(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


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
    if op in ("distance", "along", "distance_to"):
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
    """The arithmetic of flyto-core docs/CAPABILITY_CONTRACT.md "Judging evidence".

    Observations are assumed present and numeric (the suite's own fixtures);
    a frame mismatch and an omitted optional target are decided first.
    """

    measure, phases = spec["measure"], spec["phases"]
    expect = spec["expect"]
    op = measure["op"]
    if op == "angle_to" and expect.get("optional") and arguments.get(expect["argument"]) is None:
        return {"usable": True, "measured": None, "expected": None, "allowed": None, "settle_drift": None}
    frame = measure.get("frame")
    if frame is not None and any(observations[phase].get("frame") != frame for phase in phases):
        return {"usable": False, "measured": None, "expected": None, "allowed": None, "settle_drift": None}
    last = observations[phases[-1]]
    named = list(expect["arguments"].values()) if op == "distance_to" else [expect.get("argument")]
    if any(name is not None and not _is_finite(arguments.get(name)) for name in named):
        # As core: a missing target argument is an unusable verdict, not an error.
        return {"usable": False, "measured": None, "expected": None, "allowed": None, "settle_drift": None}
    if op == "distance_to":
        measured = math.sqrt(
            sum((last[name] - float(arguments[expect["arguments"][name]])) ** 2 for name in measure["fields"])
        )
    elif op == "angle_to":
        measured = last[measure["fields"][0]]
    else:
        measured = _measure(measure, observations["before"], last)
    if op == "distance_to":
        expected = 0.0
    elif op == "angle_to":
        expected = float(arguments[expect["argument"]])
    elif "argument" in expect:
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
