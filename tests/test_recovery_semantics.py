"""Recovery semantics on the motion contracts (flyto-core 2.39.0).

advance, retreat, rotate and navigate declare, as roles, what a stopped
motion may be worked round with and what each motion fills. Flyto2 Cloud
trusts a declaration only when its definition hash equals one it reviewed;
for these four that is ``services/space_tasks/recovery_semantics.FIRST_PARTY_REVIEWED``.
The hashes below were computed by that module (Cloud branch
``claude/recovery-semantics``, 711b7bba3) and are recomputed here the same
way, so a change to any declaration fails this suite before it reaches Cloud.

On a core without the semantics the keys are left out, and a block that only
stated roles is left out whole: the host then sees what it saw before 1.4.0.
"""

from __future__ import annotations

import hashlib
import json
import logging

import pytest

from flyto_modules_robotics.capabilities import (
    RECOVERY_REPORT_KEYS,
    RECOVERY_SEMANTIC_KEYS,
    SPECS,
    SPECS_BY_CAPABILITY,
)
from flyto_modules_robotics.modules import build_modules, registrable_contract
from flyto_modules_robotics.recovery import recovery_for

from test_evidence_recovery_fleet import (
    ALL_KEYS,
    ALL_OPS,
    ALL_RECOVERY,
    StandInModule,
    blocked_record,
    fake_register_module,
)

# Cloud's FIRST_PARTY_REVIEWED, as definitions and their hashes.
FIRST_PARTY = {
    "motion.advance": (
        {
            "on": ["obstruction"],
            "alternatives": ["reorient", "reposition", "travel_to"],
            "preserves": ["destination"],
            "resource_scope": "same_resource",
            "fills": ["reposition"],
        },
        "724c793cce32119d6191219b83cbe08136a809a018a8af5e2361ea2af989a771",
    ),
    "motion.retreat": (
        {"fills": ["reposition"]},
        "a050250c93af5a530c47f1d78f47135b991c5ab4c2aa656e00e2b7dd345423a9",
    ),
    "motion.rotate": (
        {"fills": ["reorient"]},
        "04b788c8d8da39024a30fd0156d017ac8e6ff01d21ee4606f0be0bbb59d17348",
    ),
    "motion.navigate": (
        {"fills": ["travel_to"]},
        "9db9ad546a2fe28c8ef7ff2b3377d1e526d071f37725b58c8cb387b3e464c384",
    ),
}


def semantics(capability_id: str) -> dict:
    recovery = SPECS_BY_CAPABILITY[capability_id].contract.get("recovery") or {}
    return {key: value for key, value in recovery.items() if key in RECOVERY_SEMANTIC_KEYS}


def cloud_definition_hash(capability_id: str, declared: dict) -> str:
    """``RecoverySemantics.definition_hash`` as Cloud computes it."""
    definition = {
        "capability_id": capability_id,
        "on": sorted(declared.get("on", [])),
        "alternatives": list(declared.get("alternatives", [])),
        "preserves": sorted(declared.get("preserves", [])),
        "resource_scope": declared.get("resource_scope", ""),
        "fills": sorted(declared.get("fills", [])),
    }
    encoded = json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@pytest.mark.parametrize("capability_id", sorted(FIRST_PARTY))
def test_each_motion_declares_exactly_cloud_s_reviewed_semantics(capability_id):
    declared, reviewed_hash = FIRST_PARTY[capability_id]
    assert semantics(capability_id) == declared
    assert cloud_definition_hash(capability_id, semantics(capability_id)) == reviewed_hash


def test_no_other_capability_declares_semantics():
    declaring = {spec.capability_id for spec in SPECS if semantics(spec.capability_id)}
    assert declaring == set(FIRST_PARTY)


def test_every_role_a_way_round_names_is_filled_on_the_same_robot():
    filled = {role for spec in SPECS for role in semantics(spec.capability_id).get("fills", [])}
    assert set(semantics("motion.advance")["alternatives"]) <= filled


def test_the_host_report_is_unchanged_beside_the_semantics():
    for capability_id in ("motion.advance", "motion.retreat"):
        recovery = SPECS_BY_CAPABILITY[capability_id].contract["recovery"]
        assert {key: recovery[key] for key in RECOVERY_REPORT_KEYS} == {
            "capabilities": ["motion.rotate", "motion.advance", "motion.retreat"],
            "observe": "recovery_context",
            "guidance": recovery["guidance"],
        }


@pytest.mark.parametrize("module_id", ["robotics.rotate", "robotics.navigate"])
def test_a_block_of_roles_alone_offers_the_planner_no_report(module_id):
    from flyto_modules_robotics.capabilities import SPECS_BY_MODULE

    assert recovery_for(SPECS_BY_MODULE[module_id], blocked_record({})) is None


def test_a_current_core_registers_the_semantics():
    steps = dict(
        build_modules(
            StandInModule, fake_register_module,
            optional_keys=ALL_KEYS, measure_ops=ALL_OPS, recovery_fields=ALL_RECOVERY,
        )
    )
    for spec in SPECS:
        assert steps[spec.module_id]._registered_metadata["contract"] == spec.contract


def test_a_core_without_the_semantics_registers_what_it_did_before_and_logs_once(caplog):
    with caplog.at_level(logging.WARNING):
        steps = dict(
            build_modules(
                StandInModule, fake_register_module,
                optional_keys=ALL_KEYS, measure_ops=ALL_OPS, recovery_fields=RECOVERY_REPORT_KEYS,
            )
        )
    for spec in SPECS:
        registered = steps[spec.module_id]._registered_metadata["contract"]
        recovery = spec.contract.get("recovery")
        if recovery is None or "capabilities" not in recovery:
            # rotate and navigate: no block at all, as in 1.3.0.
            assert "recovery" not in registered, spec.module_id
            assert registered == {k: v for k, v in spec.contract.items() if k != "recovery"}
        else:
            # advance and retreat: the 1.3.0 host report, nothing more.
            assert registered["recovery"] == {key: recovery[key] for key in RECOVERY_REPORT_KEYS}
    warned = [record.getMessage() for record in caplog.records if "2.39.0" in record.getMessage()]
    assert len(warned) == 1
    assert not [record for record in caplog.records if "2.36.0" in record.getMessage()]


def test_registrable_contract_keeps_the_block_when_not_told_otherwise():
    advance = SPECS_BY_CAPABILITY["motion.advance"].contract
    assert registrable_contract(advance, ALL_KEYS, ALL_OPS) == advance


def test_the_older_core_s_registration_passes_its_own_schema():
    """What a 2.36-2.38 core receives is valid under its closed rules."""
    from contract_rules import RECOVERY_REPORT, validate_contract

    for spec in SPECS:
        reduced = registrable_contract(spec.contract, ALL_KEYS, ALL_OPS, RECOVERY_REPORT_KEYS)
        if "recovery" in reduced:
            assert set(reduced["recovery"]) <= RECOVERY_REPORT
            assert "capabilities" in reduced["recovery"]
        validate_contract(reduced, spec.params_schema)


@pytest.mark.parametrize("capability_id", sorted(FIRST_PARTY))
def test_flyto_core_admits_the_declaration(capability_id):
    module = pytest.importorskip("core.capability_contract")
    if "fills" not in getattr(module, "RECOVERY_FIELDS", ()):
        pytest.skip("installed flyto-core predates the 2.39.0 recovery semantics")
    spec = SPECS_BY_CAPABILITY[capability_id]
    normalized = module.validate_contract(dict(spec.contract), dict(spec.params_schema))
    assert {k: v for k, v in normalized["recovery"].items() if k in RECOVERY_SEMANTIC_KEYS} == FIRST_PARTY[capability_id][0]


@pytest.mark.parametrize("capability_id", sorted(FIRST_PARTY))
def test_a_core_before_2_39_refuses_the_unreduced_block(capability_id):
    """Why the reduction exists: a 2.36-2.38 core requires capabilities and refuses the roles."""
    module = pytest.importorskip("core.capability_contract")
    if "recovery" not in getattr(module, "OPTIONAL_FIELDS", ()) or hasattr(module, "RECOVERY_FIELDS"):
        pytest.skip("needs a flyto-core between 2.36.0 and 2.38.x")
    spec = SPECS_BY_CAPABILITY[capability_id]
    with pytest.raises(ValueError, match="recovery"):
        module.validate_contract(dict(spec.contract), dict(spec.params_schema))
