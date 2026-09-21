# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.

"""What `scripts/verify-lima-gazebo.sh` promises, asserted by reading it.

These tests do **not** verify anything about a robot, a simulator, or a
gateway. They cannot: the verifier's whole value is that it runs against a live
lower layer, and nothing here runs it. A green suite means the script still
*says* what it is supposed to say — that the restoration owner is installed
before the first runtime action, that the lower layer is invoked and read the
way that layer actually works, that the mission goes through this package's own
code rather than a hand-authored substitute.

That is a real thing to protect. Every invariant below has a plausible, quiet
way of being edited out: a refactor that moves the trap down two lines, a
`--run-id` flag reintroduced because it reads better than an environment
variable, a topic loosened to a prefix during debugging, a `plan_for_step` call
replaced by an inline dict when the import got awkward. None of those would fail
any other test in this suite, and all of them would turn a passing exhibition
run into a lie.

The exact lower-layer facts asserted here — the environment variable that names
the run, the results path, the two contract versions, the five cleanup fields,
the flagless restoration script — are not this package's to choose. They are
`flyto-robotics`' surface, recorded so that a drift in either direction fails
here instead of at a robot.

But a pass here is not evidence the exhibition works. See STATE.md: the real
run is pending, and only Codex, on the machine with the Lima guest, can produce
it.
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify-lima-gazebo.sh"
EXPECTED_BEHAVIOR_REVISION = "fixed-anchor-process-quiescence.v1"
EXPECTED_REPORT_CONTRACT = "flyto.modules-robotics.gazebo-closed-loop.v1"
BEHAVIOR_ASSIGNMENT_RE = r"^VERIFIER_BEHAVIOR_REVISION="


@pytest.fixture(scope="module")
def text() -> str:
    return SCRIPT.read_text()


@pytest.fixture(scope="module")
def lines(text: str) -> list[str]:
    return text.splitlines()


_DOCSTRING = re.compile(r'"""(?:.|\n)*?"""')


def strip_prose(text: str) -> str:
    """The script with its comments and its embedded docstrings removed.

    The verifier names what it must never do — `rclpy`, `cmd_vel`, `/odom`, a
    `--run-id` flag, a `--safe-stop` — in prose, precisely so that the reason
    survives the next refactor. A whole-file substring search cannot tell that
    apart from doing it, and an earlier draft resolved the conflict by deleting
    the explanation, which is the wrong half to give up. So the checks that must
    not be satisfiable by a comment run against this instead.
    """
    body = _DOCSTRING.sub("", text)
    return "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("#")
    )


@pytest.fixture(scope="module")
def executable_text(text: str) -> str:
    return strip_prose(text)


def first_line_matching(lines: list[str], pattern: str) -> int:
    for index, line in enumerate(lines):
        if re.search(pattern, line):
            return index
    raise AssertionError(f"no line matches {pattern!r}")


def lines_matching(lines: list[str], pattern: str) -> list[int]:
    return [i for i, line in enumerate(lines) if re.search(pattern, line)]


def exit_owner_region(lines: list[str]) -> range:
    """The body of the one EXIT handler, so its own actions can be excused.

    The handler is *defined* above the `trap` that installs it, so a naive
    "nothing before the trap" test would flag the restoration itself.
    """
    return range(
        first_line_matching(lines, r"^on_exit\(\) \{"),
        first_line_matching(lines, r"^trap on_exit EXIT"),
    )


# ---------------------------------------------------------------------------
# Shape.
# ---------------------------------------------------------------------------

def test_the_verifier_exists_and_is_a_bash_script(text: str):
    assert SCRIPT.is_file()
    assert text.startswith("#!/usr/bin/env bash")


def test_the_verifier_is_invocable_however_its_mode_bit_reads():
    """Deliberately not an assertion about the executable bit.

    The mode this file arrives with depends on how it was checked out and on
    what the authoring environment was permitted to change; STATE.md records
    that it is currently not executable and README documents running it as
    ``bash scripts/verify-lima-gazebo.sh``. A test that failed on the bit would
    fail for a reason that has nothing to do with what the script says, which
    is the only thing this file can honestly check.
    """
    mode = SCRIPT.stat().st_mode
    assert stat.S_ISREG(mode)


def test_it_fails_closed(text: str):
    """`set -euo pipefail`: an unset lower-layer path must stop the run, not
    expand to empty and quietly verify nothing."""
    assert "set -euo pipefail" in text


# ---------------------------------------------------------------------------
# Safety ordering. The one property whose value is entirely positional.
# ---------------------------------------------------------------------------

RUNTIME_ACTIONS = [
    r"\$\{LOWER_REPO\}/\$\{LOWER_VERIFIER\}",   # runs the lower verifier
    r"\$\{LOWER_REPO\}/\$\{LOWER_RESTORE\}",    # restarts the lower runtime
    r"limactl shell",                            # touches the guest
    r"limactl copy",                             # writes into the guest
    r"mission\.sh",                              # posts a plan
]


@pytest.mark.parametrize("pattern", RUNTIME_ACTIONS)
def test_the_restoration_owner_is_installed_before_any_runtime_action(
    lines: list[str], pattern: str
):
    """The trap must precede the first thing that can leave a robot moving or a
    runtime in a fault state.

    Not a style point. A failure between "start the lower verifier" and
    "register cleanup" leaves a runtime that nothing is going to restore.
    """
    trap = first_line_matching(lines, r"^trap on_exit EXIT")
    owner = exit_owner_region(lines)
    offenders = [i for i in lines_matching(lines, pattern) if i < trap and i not in owner]
    assert not offenders, (
        f"{pattern!r} appears at line(s) {[i + 1 for i in offenders]}, "
        "before the cleanup trap is installed"
    )


def test_signals_route_through_the_same_exit_owner(text: str):
    """INT and TERM exit rather than clean up themselves, so restoration has
    exactly one implementation and runs exactly once."""
    assert "trap 'exit 130' INT" in text
    assert "trap 'exit 143' TERM" in text
    assert "CLEANUP_DONE" in text
    assert re.search(r'if \[ "\$\{CLEANUP_DONE\}" -eq 1 \]; then exit "\$\{status\}"', text)


# ---------------------------------------------------------------------------
# Restoration: one command, no flags, exactly once, on every path.
# ---------------------------------------------------------------------------

def test_restoration_is_the_lower_layers_own_flagless_run_script(text: str):
    """`run-lima-gazebo.sh` with no flags is the accepted public way back to a
    normal, non-fault gateway runtime."""
    assert 'LOWER_RESTORE="scripts/run-lima-gazebo.sh"' in text


@pytest.mark.parametrize(
    "invention",
    ["lima-gazebo-restore.sh", "--safe-stop", "--normal-gateway"],
)
def test_the_verifier_does_not_invent_a_restoration_interface(
    executable_text: str, invention: str
):
    """None of these exist in `flyto-robotics`. An earlier draft called all
    three; every one of them would have failed at the shell, after the mission
    had already moved a robot.

    Asserted against the executable body only. The block above `LOWER_RESTORE`
    names `--safe-stop` in order to say there is no such flag, and that sentence
    is worth more than the substring search it would otherwise break.
    """
    assert invention not in executable_text


def test_restoration_runs_exactly_once_and_only_from_the_exit_owner(lines: list[str]):
    invocation = r'^\s*bounded "\$\{RESTORE_TIMEOUT\}" -- "\$\{LOWER_REPO\}/\$\{LOWER_RESTORE\}" \\$'
    found = lines_matching(lines, invocation)
    assert len(found) == 1, f"expected exactly one restoration call, found {len(found)}"
    assert found[0] in exit_owner_region(lines)
    # No flags: the line ends at the script path and continues only to a redirect.
    assert lines[found[0] + 1].strip() == '>"${OUT_DIR}/restore.log" 2>&1'


def test_the_zero_command_is_the_lower_layers_to_publish(text: str):
    """`run-lima-gazebo.sh` publishes a best-effort zero command itself before
    restarting the runtime. A second stop from here would be this package
    inventing one, which AGENTS.md forbids, and a second differently-implemented
    safety path besides."""
    assert '"zero_command_owner"' in text
    assert "this package never publishes one" in text


def test_the_exact_restoration_exit_code_is_recorded(text: str):
    assert "RESTORE_EXIT=$?" in text
    assert '"restoration_exit_code": ${RESTORE_EXIT}' in text
    assert '"restoration_timed_out": ${RESTORE_TIMED_OUT}' in text
    assert '"restoration_invocations": ${RESTORE_INVOCATIONS}' in text


def test_the_restoration_count_is_what_ran_not_what_was_meant_to_run(
    lines: list[str], text: str
):
    """An earlier draft wrote `restoration_invocations: 1` as a literal, so the
    one case where restoration was impossible — no executable, no process, no
    exit status — was the case whose artifact claimed most confidently to have
    restored something.

    The count now starts at 0 and is raised to 1 only on the branch where the
    restoration command actually ran, after it ran.
    """
    assert '"restoration_attempted": ${RESTORE_ATTEMPTED}' in text
    assert re.search(r"^RESTORE_INVOCATIONS=0$", text, re.M), "the count starts at zero"

    raised = lines_matching(lines, r"^\s+RESTORE_INVOCATIONS=1$")
    assert len(raised) == 1, f"expected one place to raise the count, found {len(raised)}"

    guard = first_line_matching(
        lines, r'^\s*if \[ -x "\$\{LOWER_REPO\}/\$\{LOWER_RESTORE\}" \]; then$'
    )
    ran = first_line_matching(lines, r'^\s*bounded "\$\{RESTORE_TIMEOUT\}"')
    unavailable = first_line_matching(lines, r"lower restoration path is not executable")
    assert guard < ran < raised[0] < unavailable, (
        "the count must be raised inside the branch that ran the command, after "
        "the command, and never on the branch where there was nothing to run"
    )

    # And the count is a gate, not a decoration: a run that cannot show exactly
    # one invocation does not pass.
    assert re.search(r'\[ "\$\{RESTORE_INVOCATIONS\}" -ne 1 \]', text)


def test_a_timeout_is_not_confused_with_an_exit_code(text: str):
    """The bounded helper returns 124 when it kills something. That is not the
    restoration's own exit code, and recording it as one would be a lie in an
    artifact."""
    assert "BOUNDED_TIMED_OUT" in text
    assert re.search(r'if \[ "\$\{BOUNDED_TIMED_OUT\}" -eq 1 \]', text)


def test_cleanup_preserves_an_existing_failure(text: str):
    """A perfect restoration must not turn a failed run green."""
    assert re.search(r'if \[ "\$\{status\}" -ne 0 \]; then', text)
    assert re.search(r'exit "\$\{status\}"', text)


def test_a_failed_restoration_fails_an_otherwise_passing_run(text: str):
    assert re.search(r'if \[ "\$\{RESTORE_OK\}" != true \]; then\s*\n.*\n\s*exit 1', text)


def test_cleanup_emits_versioned_evidence(text: str):
    assert 'CLEANUP_CONTRACT="flyto.modules-robotics.gazebo-cleanup.v1"' in text
    assert 'cat >"${OUT_DIR}/cleanup.json"' in text
    assert '"contract_version": "${CLEANUP_CONTRACT}"' in text
    assert '"restored_normal_gateway_runtime": ${RESTORE_OK}' in text


def test_the_exit_owner_disarms_itself_before_it_restores(text: str):
    """The handler drops the EXIT trap and ignores INT and TERM before it does
    anything else.

    A second Ctrl-C is the reflex when a restoration looks slow, and an
    interrupted restoration is worse than a slow one: it leaves a runtime that
    was being restarted and is now neither stopped nor running. The status has
    already been captured by then, so nothing is lost by refusing the signal.
    """
    assert re.search(r"^\s*trap - EXIT$", text, re.M), "the EXIT trap is removed"
    assert re.search(r"^\s*trap '' INT TERM$", text, re.M), "INT and TERM are ignored"

    disarm = text.index("trap - EXIT")
    ignore = text.index("trap '' INT TERM")
    restore = text.index('bounded "${RESTORE_TIMEOUT}"')
    assert disarm < ignore < restore, (
        "disarming must come before the restoration it is protecting"
    )
    # Belt to the braces: re-entry is still refused explicitly.
    assert "CLEANUP_DONE=1" in text


def test_the_pid_registry_outlives_the_subshells_that_write_it(
    lines: list[str], text: str
):
    """`bounded` is called from inside `$( ... )` for the mission and for every
    probe, and a command substitution is a subshell — so every assignment it
    makes to the in-memory register is discarded when the substitution closes.
    The register is therefore also a file, which a subshell and its parent do
    share, and cleanup reads both and deduplicates the union.
    """
    assert 'BOUNDED_PID_FILE="${OUT_DIR}/active-pids"' in text

    # Remembered on start.
    assert '>>"${BOUNDED_PID_FILE}"' in text
    assert '_bounded_register "${pid}"' in text

    # Forgotten on a normal reap, so the registry only ever hands cleanup
    # processes that were never waited for.
    assert '_bounded_forget "${pid}"' in text
    assert 'grep -v -x -F "${drop}" "${BOUNDED_PID_FILE}"' in text

    # Consumed by cleanup, unioned with the in-memory register, deduplicated.
    assert "for candidate in ${BOUNDED_ACTIVE_PIDS} ${registry}; do" in text

    consumed = first_line_matching(lines, r'registry="\$\(tr .* <"\$\{BOUNDED_PID_FILE\}"')
    quiesced = first_line_matching(lines, r'terminate_tree "\$\{pid\}" "\$\{QUIESCE_GRACE\}"')
    restore = first_line_matching(lines, r'^\s*bounded "\$\{RESTORE_TIMEOUT\}"')
    assert consumed < quiesced < restore, (
        "the registry must be read and its processes terminated before the lower "
        "runtime is restarted; restoring underneath a still-running writer of "
        "ours is two writers and one robot"
    )
    assert '"lower_processes_quiesced": ${LOWER_QUIESCED}' in text


# ---------------------------------------------------------------------------
# The lower layer, invoked the way that layer actually works.
# ---------------------------------------------------------------------------

def test_the_lower_run_id_travels_in_the_environment_not_a_flag(
    text: str, executable_text: str
):
    """`flyto-robotics/scripts/verify-lima-gazebo.sh` has no `--run-id`. An
    earlier draft passed one; it would have been rejected or misread, and the
    report we then went looking for would never have existed.

    The absence is asserted against the executable body, because the coupling
    block above says in words that the flag does not exist — which is the note
    that stops it being reintroduced.
    """
    assert 'LOWER_RUN_ID_ENV="FLYTO_GAZEBO_VERIFY_RUN_ID"' in text
    assert 'env "${LOWER_RUN_ID_ENV}=${LOWER_RUN_ID}" "${LOWER_REPO}/${LOWER_VERIFIER}"' in text
    assert "--run-id" not in executable_text


def test_the_lower_artifacts_are_read_from_the_accepted_path(text: str):
    assert 'LOWER_RESULTS_DIR="results/virtual-robot"' in text
    assert 'LOWER_RUN_DIR="${LOWER_REPO}/${LOWER_RESULTS_DIR}/${LOWER_RUN_ID}"' in text
    assert 'LOWER_REPORT="${LOWER_RUN_DIR}/${LOWER_REPORT_NAME}"' in text
    assert 'LOWER_CLEANUP="${LOWER_RUN_DIR}/${LOWER_CLEANUP_NAME}"' in text


@pytest.mark.parametrize(
    "contract",
    [
        'LOWER_REPORT_CONTRACT="flyto.robotics.burger-gazebo-acceptance.v1"',
        'LOWER_CLEANUP_CONTRACT="flyto.robotics.runtime-cleanup.v1"',
    ],
)
def test_the_lower_contract_versions_are_exact(text: str, contract: str):
    assert contract in text


def test_the_lower_contracts_are_constants_not_environment_overrides(text: str):
    """A contract you can switch off from a shell is not a contract. Only the
    checkout *location* stays overridable, because that is a location."""
    for name in ("LOWER_REPORT_CONTRACT", "LOWER_CLEANUP_CONTRACT", "LOWER_RESULTS_DIR",
                 "LOWER_RESTORE", "LOWER_RUN_ID_ENV", "LIMA_INSTANCE", "ROBOT_ID"):
        assert not re.search(rf'^{name}="\$\{{[A-Z_]+:-', text, re.M), (
            f"{name} must be a constant, not an environment override"
        )
    assert 'LOWER_REPO="${FLYTO_ROBOTICS_REPO:-' in text


def test_freshness_comes_from_a_path_that_did_not_exist(text: str):
    """The lower cleanup contract carries no run_id, so nothing inside it can
    prove it is this run's. A directory proved absent beforehand can."""
    assert '[ ! -e "${LOWER_RUN_DIR}" ] || fail' in text
    assert "the chosen lower results path already exists" in text


def test_the_cleanup_document_is_not_required_to_carry_a_run_id(text: str):
    """Asserting an absent field would fail every real run. Saying so in the
    script is what stops someone adding the check back."""
    assert "The cleanup contract has no run_id field at all" in text
    assert '"cleanup_has_no_run_id_field_by_contract"' in text


@pytest.mark.parametrize(
    "field",
    [
        "passed",
        "restored_normal_gateway_runtime",
        "zero_command_published",
        "normal_runtime_restoration_exit_code",
        "verification_status",
    ],
)
def test_every_agreed_cleanup_field_is_checked(text: str, field: str):
    assert f'"{field}"' in text


def test_booleans_are_checked_identically_and_zeros_are_checked_as_integers(text: str):
    """`"false"` and `0` are both things a report has carried, and only one of
    them looks false to a truthiness test. In the other direction `True == 0` is
    False but `True` is an `int`, so the type check has to exclude `bool`."""
    assert "def exactly_true(" in text
    assert "def exactly_int_zero(" in text
    assert 'if doc.get(field) is not True:' in text
    assert "isinstance(value, bool) or not isinstance(value, int) or value != 0" in text


@pytest.mark.parametrize(
    "rejection",
    [
        "no lower report at",                       # missing
        "no lower cleanup evidence at",             # missing
        "malformed JSON in",                        # malformed
        "is not a JSON object",                     # wrong shape
        "expected {contract!r}",                    # wrong version
        "expected exactly true",                    # false
        "expected exactly the integer 0",           # wrong type or value
    ],
)
def test_bad_lower_evidence_is_rejected(text: str, rejection: str):
    assert rejection in text


def test_the_report_records_the_lower_evidence_digests(text: str):
    assert "report_sha256" in text
    assert "cleanup_sha256" in text
    assert "hashlib.sha256(raw).hexdigest()" in text
    assert '"lower_layer"' in text


# ---------------------------------------------------------------------------
# The step under test is this package's real code.
# ---------------------------------------------------------------------------

def test_the_plan_comes_from_this_packages_own_mapping(text: str):
    """Not a hand-authored plan. If an argument name drifts from the robot's
    capability contract again, it has to fail here — which is the only reason
    this script is worth running."""
    assert "from flyto_modules_robotics.steps import plan_for_step" in text
    assert "plan = plan_for_step(module_id," in text
    assert "request = run_request(" in text


def test_the_gateway_client_under_test_is_this_packages(text: str):
    assert "from flyto_modules_robotics import gateway" in text
    assert "gateway.start_plan(request)" in text
    assert "gateway.await_session(session_id, timeout_seconds=timeout)" in text


def test_the_authored_step_is_a_bounded_robotics_move(text: str):
    assert 'STEP_MODULE_ID="robotics.move"' in text
    assert 'STEP_DISTANCE_M="0.40"' in text
    assert 'STEP_SPEED_MPS="0.12"' in text


def test_the_safe_stop_is_asserted_on_the_document_that_is_sent(text: str):
    assert 'final_step = plan["steps"][-1]' in text
    assert 'final_step.get("capability") == "safe_stop"' in text
    assert '"final_step_is_safe_stop": mission.get("final_step_capability") == "safe_stop"' in text


def test_no_host_reaches_the_plan(text: str):
    """AGENTS.md: never put a host in a step parameter.

    The verdict is computed from a recursive scan, and the aggregate requires it
    to be exactly True — an absent field must not read as an absent host.
    """
    assert '"plan_contains_no_host": plan_host_scan == []' in text
    assert '"plan_contains_no_host": mission.get("plan_contains_no_host") is True' in text


def test_the_host_check_is_a_recursive_scan_not_a_substring_test(
    text: str, executable_text: str
):
    """The predecessor was `"://" not in serialised and "127.0.0.1" not in
    serialised` — two spellings of one host, and the two anyone thinks of first,
    which is why it read as sufficient.

    A plan carrying `{"hostname": "robot-7.local"}`, `{"endpoint":
    "gateway:8766"}`, `{"address": "192.168.1.40"}` or a bare `"localhost"`
    passed it without comment, and those are the shapes a drifting capability
    contract actually produces, because none of them looks like a URL.
    """
    # The substring test is gone, not merely supplemented. Asserted against the
    # executable body: the block above the scan quotes the old expression in
    # order to say why it was insufficient, and that sentence is worth more than
    # the substring search it would otherwise break.
    assert '"://" not in serialised' not in executable_text, (
        "the substring test must not survive"
    )
    assert "serialised = json.dumps(plan)" not in executable_text

    # A real walk: keys, string values, nesting, and both container types.
    assert "def host_findings(node, path=\"plan\", depth=0):" in text
    assert "found.extend(host_findings(value, here, depth + 1))" in text, (
        "dictionary values are walked recursively"
    )
    assert re.search(
        r"found\.extend\(host_findings\(value, f\"\{path\}\[\{index\}\]\", depth \+ 1\)\)",
        text,
    ), "list elements are walked recursively"

    # Keys are matched in full and by fragment, so compound names are caught.
    assert "HOST_KEY_NAMES = frozenset({" in text
    assert "HOST_KEY_FRAGMENTS = (" in text
    assert "if lowered in HOST_KEY_NAMES:" in text
    assert "if fragment in lowered:" in text

    # String values are matched too — a host can be a value under an innocent key.
    assert "HOST_VALUE_FRAGMENTS = (" in text
    assert 'for fragment in HOST_VALUE_FRAGMENTS:' in text


@pytest.mark.parametrize(
    "spelling",
    ["host", "hostname", "gateway_url", "endpoint", "address", "url", "uri",
     "netloc", "ip_address", "port"],
)
def test_the_host_scan_knows_the_host_bearing_key_names(text: str, spelling: str):
    """Each of these is a field a plan could carry a host in. The scan has to
    know the name; a check that only knows `url` is the old check with more
    steps."""
    scan = text.split("HOST_KEY_NAMES = frozenset({")[1].split("})")[0]
    assert f'"{spelling}"' in scan, f"the scan does not know the key {spelling!r}"


@pytest.mark.parametrize(
    "spelling", ["://", "localhost", "127.0.0.1", "0.0.0.0", "::1"]
)
def test_the_host_scan_knows_the_host_bearing_value_spellings(text: str, spelling: str):
    fragments = text.split("HOST_VALUE_FRAGMENTS = (")[1].split(")")[0]
    assert f'"{spelling}"' in fragments, f"the scan does not know the value {spelling!r}"


def test_the_host_scan_fails_closed_on_what_it_cannot_walk(text: str):
    """A scanner that reports "nothing found" because it did not understand what
    it was looking at is worse than no scanner: it converts ignorance into
    evidence. Every direction it can fail in is a finding instead."""
    assert "found.append(f\"{path}: non-string key {key!r}\")" in text
    assert "cannot be walked" in text, "an unwalkable value type is a finding"
    assert "HOST_SCAN_MAX_DEPTH" in text
    assert re.search(
        r"if depth > HOST_SCAN_MAX_DEPTH:\s*\n\s*return \[", text
    ), "nesting past the limit is a finding, not a silent stop"
    assert re.search(
        r"except Exception as exc:[^\n]*\n\s*plan_host_scan = \[", text
    ), "an exception during the walk is a finding, not a pass"


def test_the_host_scan_runs_on_the_sent_plan_and_blocks_the_send(
    lines: list[str], text: str
):
    """Scanned before the post, and refused there.

    Recording the finding and posting anyway would let a plan that names a host
    move a robot, leaving the aggregate to disapprove of it afterwards — which
    is a report about a thing that already happened, not a gate.
    """
    assert "plan_host_scan = host_findings(plan)" in text, (
        "the scan runs on the plan document, not a rebuilt copy"
    )
    assert 'die("the plan carries a host, which AGENTS.md forbids: "' in text

    scanned = first_line_matching(lines, r"^\s*plan_host_scan = host_findings\(plan\)$")
    refused = first_line_matching(lines, r"^if plan_host_scan:$")
    posted = first_line_matching(lines, r"^\s*session = gateway\.start_plan\(request\)$")
    assert scanned < refused < posted, (
        "the plan must be scanned and refused before it reaches the gateway"
    )

    # And the findings themselves reach the artifact, so a failure is
    # diagnosable from report.json without rerunning anything.
    assert '"plan_host_scan_findings": plan_host_scan,' in text
    assert '"plan_host_scan_findings": mission.get("plan_host_scan_findings"),' in text


def test_the_gateway_must_reach_terminal_success_not_a_timeout(text: str):
    assert '"session_terminal_success": state in TERMINAL_SUCCESS_STATES and not timed_out' in text
    assert '"gateway_did_not_time_out": mission.get("session_timed_out") is False' in text


def test_the_gateways_own_completed_state_is_a_success(
    text: str, executable_text: str
):
    """The real lower gateway reports `MissionState.COMPLETED`, which arrives
    here as `completed`.

    Requiring `succeeded` and nothing else meant a mission that ran to
    completion was read as a failure — the verifier would have failed a passing
    exhibition and sent someone hunting a defect in the plan contract that was
    never there. That is the worst kind of verifier bug: it manufactures work
    and discredits the thing it was built to protect.
    """
    assert 'TERMINAL_SUCCESS_STATES = frozenset({"completed", "succeeded"})' in text

    # Exact membership in a closed set, not a prefix or a substring test: a
    # state this set does not name is not a success just because it is
    # unfamiliar.
    assert "state in TERMINAL_SUCCESS_STATES" in text
    assert 'state == "succeeded"' not in executable_text, (
        "the single-spelling comparison must not survive in the executable body"
    )

    states = text.split("TERMINAL_SUCCESS_STATES = frozenset({")[1].split("})")[0]
    assert '"completed"' in states, "the gateway's own COMPLETED must count"
    assert '"succeeded"' in states
    for not_a_success in ("running", "failed", "cancelled", "aborted", "pending"):
        assert f'"{not_a_success}"' not in states, (
            f"{not_a_success!r} is not terminal success"
        )

    # The accepted set is recorded, so a report says what it would have accepted.
    assert '"terminal_success_states": sorted(TERMINAL_SUCCESS_STATES),' in text


# ---------------------------------------------------------------------------
# The package's own safety constraints, still true of the verifier itself.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "forbidden", ["rclpy", "cmd_vel", "/odom", "ros2 topic pub", "ros2 run"]
)
def test_the_verifier_never_drives_anything_itself(executable_text: str, forbidden: str):
    """No rclpy, no topic publish, no velocity, no odometry. Motion travels the
    ordinary path — this package's client, the gateway, the robot — or it does
    not happen.

    Scoped to the executable shell and the embedded guest programs. The header
    comment lists these names in order to say the script does not use them, and
    naming what is forbidden and not doing it have to be able to be true at
    once.
    """
    assert forbidden not in executable_text


def test_gazebo_is_only_ever_echoed_never_published_to(text: str):
    assert '"gz", "topic", "-e", "-t", topic, "-n", "1"' in text
    assert not re.search(r"\bgz\b[^\n]*\btopic\b[^\n]*\s-p\b", text), "no Gazebo publish"


def test_the_gateway_address_is_loopback_configuration(text: str):
    """A host never becomes a step parameter; the mission driver is handed a
    loopback URL naming the guest it is already running inside, and the
    runtime's own environment may override it."""
    assert ': "${FLYTO_ROBOTICS_GATEWAY_URL:?set FLYTO_ROBOTICS_GATEWAY_URL explicitly for the legacy Gazebo verifier}"' in text
    assert 'GATEWAY_URL="${FLYTO_ROBOTICS_GATEWAY_URL%/}"' in text
    assert "gateway_url = (os.environ.get(gateway.GATEWAY_URL_ENV) or \"\").strip() or fallback_url" in text


def test_the_robot_id_is_the_gateways_own(text: str):
    assert 'ROBOT_ID="flyto-rover-sim-001"' in text


def test_a_robot_id_disagreement_is_reported_not_papered_over(text: str):
    assert "if runtime_robot and runtime_robot != robot:" in text


def test_the_lima_instance_is_the_gazebo_one(text: str):
    assert 'LIMA_INSTANCE="flyto-robot-gazebo"' in text


def test_the_sibling_repository_is_never_written(text: str):
    """Read it, run it, never edit it."""
    for pattern in (r">\s*\"\$\{LOWER_REPO\}", r"rm -rf \"\$\{LOWER_REPO\}",
                    r"limactl copy[^\n]*\$\{LOWER_REPO\}"):
        assert not re.search(pattern, text), f"writes into flyto-robotics: {pattern}"


# ---------------------------------------------------------------------------
# Secrets.
# ---------------------------------------------------------------------------

def test_the_gateway_environment_file_is_the_agreed_one(text: str):
    """Written into the guest wrapper verbatim, with `$HOME` unexpanded, so the
    guest's own shell resolves it. Expanding it on the host would name this
    machine's home directory, which is not where the runtime keeps anything."""
    assert 'GATEWAY_ENV="$HOME/.local/share/flyto-robot-gazebo/runtime/gateway.env"' in text


def test_the_environment_file_is_sourced_in_the_guest_not_read_as_a_token(text: str):
    """It holds shell `export` assignments, so a `read().strip()` would send the
    literal text `export FLYTO_...=...` as a bearer token. It is sourced, by a
    shell, in the guest, once."""
    assert '. "${GATEWAY_ENV}"' in text
    assert "set -a" in text
    assert "handle.read().strip()" not in text, "the env file is not a raw token"


def test_the_host_never_reads_the_environment_file(lines: list[str]):
    """`$HOME` is left unexpanded on the host on purpose: it is the guest's home
    that matters. Nothing on the host may cat, copy or source that path."""
    for index in lines_matching(lines, r"gateway\.env"):
        line = lines[index].strip()
        assert not line.startswith(("cat ", "limactl copy", ". ", "source ")), (
            f"line {index + 1} reads the guest's gateway env on the host: {line}"
        )


def test_no_artifact_or_log_carries_the_token(text: str):
    """The mission driver's JSON is built field by field; nothing splats an
    environment or echoes the token. Only the *name* of the variable that
    carried it is recorded, which is provenance, not a secret."""
    assert '"token":' not in text
    assert "dict(os.environ)" not in text
    assert "os.environ.copy()" not in text
    assert '"token_env_var": token_env' in text
    assert "the bearer token is sourced inside the guest and never leaves it" in text


def test_the_mission_wrapper_never_traces_its_own_sourcing(text: str):
    assert "set +x" in text


# ---------------------------------------------------------------------------
# Physical evidence, and what does not count as it.
# ---------------------------------------------------------------------------

def test_the_gazebo_topic_and_model_are_exact(text: str):
    assert 'GZ_TOPIC="/world/flyto_turtlebot3_fidelity/pose/info"' in text
    assert 'GZ_MODEL="burger"' in text


def test_the_model_is_matched_exactly_not_by_prefix(text: str):
    """A second spawned robot must not be mistaken for this one."""
    assert "_name(entry) != model" in text
    assert "Exact model name, never a prefix" in text


def test_the_pose_message_is_parsed_structurally_not_by_one_greedy_regex(text: str):
    """The regex this replaced matched `pose { ... }` up to the first
    line-initial `}` — the *inner* brace of the first nested block — so it read
    a truncated body and could miss the model it was looking for."""
    assert "def parse_text_proto(text):" in text
    assert "stack.pop()" in text


def test_odometry_alone_is_not_accepted_as_proof(text: str):
    assert "world pose, not odometry" in text


# ---------------------------------------------------------------------------
# The pose probe's guest runtime environment.
#
# Run mrg-20260809T090403Z-64172 failed here and nowhere else: physics-gate.json
# recorded samples: 0 with "the `gz` command is not available in the guest". A
# plain `limactl shell ... python3` gets a PATH without `gz`; the binary lives at
# /opt/ros/jazzy/opt/gz_tools_vendor/bin/gz and is put on the PATH by the
# runtime's two setup files, which the accepted lower verifier also sources.
#
# That is a verifier failing on its own environment while reporting a verdict
# about the world, which is the most expensive kind of false negative this
# repository can produce. These tests pin the fix so it cannot be half-undone.
# ---------------------------------------------------------------------------

PROBE_ROS_SETUP = "/opt/ros/jazzy/setup.bash"
PROBE_WORKSPACE_SETUP = (
    "$HOME/.local/share/flyto-robot-gazebo/workspace/install/setup.bash"
)
PROBE_MODES = ("sample_pose", "hold_window", "hold_window_from")


@pytest.fixture(scope="module")
def probe_wrapper(text: str) -> str:
    """The body of the guest-side pose-probe wrapper, as written verbatim."""
    marker = "cat >\"${PROBE_SH}\" <<'SH'\n"
    assert marker in text, "the pose probe has no guest runtime wrapper"
    return text.split(marker, 1)[1].split("\nSH\n", 1)[0]


def shell_function_body(text: str, name: str) -> str:
    start = text.index(f"\n{name}() {{\n")
    return text[start:text.index("\n}\n", start)]


def test_the_pose_probe_runs_through_a_guest_runtime_wrapper(text: str):
    """Not `python3 gz_probe.py` directly. The probe needs a PATH it only gets
    from a shell that sourced the runtime's setup files, and a wrapper is the
    only place a shell exists on the guest side of `limactl shell`."""
    assert 'PROBE_SH="${STAGE}/probe.sh"' in text
    assert 'exec python3 "${FLYTO_PROBE_ROOT}/gz_probe.py" "$@"' in text
    assert re.search(
        r'bounded "\$\{COPY_TIMEOUT\}" -- limactl copy "\$\{PROBE_SH\}" '
        r'"\$\{LIMA_INSTANCE\}:\$\{GUEST_DIR\}/probe\.sh"',
        text,
    ), "the wrapper must be staged into the guest, bounded like every other copy"


def test_the_probe_wrapper_sources_both_runtime_setup_files(probe_wrapper: str):
    """Both, and in the order the runtime layers them: the distribution's own
    setup file, then the overlay workspace that the Gazebo world is built in.
    Sourcing one alone leaves `gz` off the PATH, which is the defect this
    replaces — and the accepted lower verifier sources exactly these two."""
    assert f'PROBE_ROS_SETUP="{PROBE_ROS_SETUP}"' in probe_wrapper
    assert f'PROBE_WORKSPACE_SETUP="{PROBE_WORKSPACE_SETUP}"' in probe_wrapper

    ros = probe_wrapper.index('. "${PROBE_ROS_SETUP}"')
    workspace = probe_wrapper.index('. "${PROBE_WORKSPACE_SETUP}"')
    execd = probe_wrapper.index('exec python3 "${FLYTO_PROBE_ROOT}/gz_probe.py"')
    assert ros < workspace < execd, (
        "both setup files must be sourced, in that order, before the probe runs"
    )


def test_an_unreadable_setup_file_fails_closed_as_probe_json(probe_wrapper: str):
    """A missing setup file must arrive as an `ok: false` result the caller
    already knows how to fail on, not as a silent PATH that produces
    samples: 0 and a verdict about the world."""
    for name in ("PROBE_ROS_SETUP", "PROBE_WORKSPACE_SETUP"):
        assert f'if [ ! -r "${{{name}}}" ]; then' in probe_wrapper
    assert '"error": "the guest ROS setup file is not readable"' in probe_wrapper
    assert '"error": "the guest workspace setup file is not readable"' in probe_wrapper


def test_the_probe_workspace_path_is_expanded_in_the_guest_not_on_the_host(
    text: str, lines: list[str], probe_wrapper: str
):
    """`$HOME` is written verbatim into a quoted heredoc, exactly as the mission
    wrapper's gateway env path is. The workspace lives under the *guest's* home
    directory; expanding it here would name this machine's home, which holds
    none of it."""
    assert "cat >\"${PROBE_SH}\" <<'SH'" in text, "the heredoc must be quoted"
    assert "$HOME/.local/share/flyto-robot-gazebo/workspace" in probe_wrapper

    # And nothing on the host side touches that path itself.
    for index in lines_matching(lines, r"workspace/install/setup\.bash"):
        line = lines[index].strip()
        assert not line.startswith(("cat ", "limactl copy", ". ", "source ")), (
            f"line {index + 1} resolves the guest workspace setup on the host: {line}"
        )
    assert "${HOME}/.local/share/flyto-robot-gazebo/workspace" not in text, (
        "the host must not expand the guest's home directory"
    )


@pytest.mark.parametrize("mode", PROBE_MODES)
def test_every_pose_probe_path_goes_through_the_one_helper(text: str, mode: str):
    """All three read-only modes — sample, hold, hold-from — or the environment
    gets fixed in the one call site someone was debugging and stays broken in
    the other two. A `sample_pose` that works while `hold_window` still runs
    without `gz` produces a gate with samples: 0 and a run that blames the
    world."""
    body = shell_function_body(text, mode)
    assert "run_gz_probe " in body, f"{mode} does not go through the shared helper"
    assert "limactl" not in body, (
        f"{mode} reaches the guest itself instead of through the helper"
    )
    assert "python3 " not in body, (
        f"{mode} invokes the probe directly, outside the runtime environment"
    )


def test_the_shared_probe_helper_is_the_only_caller_of_the_probe(text: str):
    """One helper, one guest invocation. Two would be two environments."""
    helper = shell_function_body(text, "run_gz_probe")
    assert 'bash "${GUEST_DIR}/probe.sh" "$@"' in helper
    assert 'env "FLYTO_PROBE_ROOT=${GUEST_DIR}"' in helper

    invocations = re.findall(r'bash "\$\{GUEST_DIR\}/probe\.sh"', text)
    assert len(invocations) == 1, (
        f"expected exactly one probe invocation, found {len(invocations)}"
    )
    # The guest path to the probe module appears once, and that once is the
    # staging copy. Nothing runs it except the wrapper, which reaches it through
    # FLYTO_PROBE_ROOT after the runtime environment is in place.
    assert len(re.findall(r'\$\{GUEST_DIR\}/gz_probe\.py', text)) == 1
    assert not re.search(r'python3 "\$\{GUEST_DIR\}/gz_probe\.py"', text), (
        "the probe must never be run outside the runtime environment"
    )


def test_the_shared_probe_helper_is_bounded_by_its_caller(text: str):
    """Every external call in this script has a bound, and each mode knows its
    own wall budget — the helper takes one rather than guessing."""
    helper = shell_function_body(text, "run_gz_probe")
    assert 'local wall_bound="${1:?run_gz_probe needs a bound}"; shift' in helper
    assert 'bounded "${wall_bound}" -- limactl shell "${LIMA_INSTANCE}"' in helper
    for mode, expected in (
        ("sample_pose", r"run_gz_probe \$\(\(SAMPLE_TIMEOUT \+ 30\)\)"),
        ("hold_window", r"run_gz_probe \$\(\(wall \+ 60\)\)"),
        ("hold_window_from", r"run_gz_probe \$\(\(wall \+ 60\)\)"),
    ):
        assert re.search(expected, shell_function_body(text, mode)), (
            f"{mode} must pass the helper its own bound"
        )


def test_the_pose_probe_never_sources_the_gateway_credential_environment(
    probe_wrapper: str,
):
    """Echoing a world-pose topic is not an authenticated operation.

    The mission wrapper sources the runtime's gateway environment because it has
    to post a plan; the probe has no such need, and a read-only observer that
    carries a bearer token is a credential in a process with no use for it. The
    two wrappers are separate for this reason and must stay separate.
    """
    for credential in ("gateway.env", "GATEWAY_ENV", "set -a", "TOKEN", "token",
                       "FLYTO_VERIFY_SRC", "mission"):
        assert credential not in probe_wrapper, (
            f"the pose probe wrapper exposes {credential!r}"
        )


def test_the_probe_wrapper_relaxes_unset_checking_only_around_the_sourcing(
    probe_wrapper: str,
):
    """ROS setup files legitimately read variables that are not set yet, so
    `set -u` would abort before the PATH was ever extended. Failing closed is
    restored immediately afterwards rather than abandoned for the whole file."""
    assert probe_wrapper.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    relaxed = probe_wrapper.index("\nset +u\n")
    restored = probe_wrapper.index("\nset -u\n")
    execd = probe_wrapper.index('exec python3 "${FLYTO_PROBE_ROOT}/gz_probe.py"')
    assert relaxed < restored < execd
    assert probe_wrapper.index('. "${PROBE_ROS_SETUP}"') > relaxed
    assert probe_wrapper.index('. "${PROBE_WORKSPACE_SETUP}"') < restored


def test_the_missing_gz_failure_is_still_reported_as_itself(text: str):
    """The environment fix does not remove the diagnosis. If `gz` is ever off
    the PATH again, the probe must say so in the artifact rather than report an
    empty window."""
    assert '"error": "the `gz` command is not available in the guest"' in text


# ---------------------------------------------------------------------------
# The cold-start physics gate.
# ---------------------------------------------------------------------------

def test_the_physics_gate_is_stated_in_simulation_time(text: str):
    """After the lower verifier's cleanup the runtime is a fresh cold start.
    Wall-clock patience proves nothing about a world that may be paused; ten
    seconds of the simulator's own clock does."""
    assert 'PHYSICS_GATE_MIN_SIM_S="10.0"' in text
    assert 'PHYSICS_GATE_MAX_DRIFT_M="0.01"' in text
    assert 'PHYSICS_GATE_WALL_TIMEOUT="90"' in text


def test_the_physics_gate_requires_finite_drift(text: str):
    """Two branches, not one condition: a non-finite drift and a drift past the
    tolerance are different failures and are reported as different failures.
    Both end the window; neither is waited out."""
    assert re.search(
        r"if not math\.isfinite\(drift\):\s*\n\s*return verdict\(False,", text
    ), "a non-finite drift ends the window"
    assert re.search(
        r"if drift > max_drift:\s*\n\s*return verdict\(False,", text
    ), "drift past the tolerance ends the window"
    assert '"drift_is_finite": True' in text
    assert 'out["drift_is_finite"] = math.isfinite(peak_drift)' in text


def test_a_backwards_simulation_clock_fails_instead_of_re_anchoring(text: str):
    """A world reset mid-window would otherwise be measured across, and taking a
    fresh anchor there would launder the reset into a pass. So it returns a
    false verdict, and the anchor is left exactly as it was."""
    assert re.search(
        r'if here\["sim_time"\] < anchor\["sim_time"\]:\s*\n\s*return verdict\(False,',
        text,
    )
    assert "was reset, so nothing measured across it is comparable" in text
    assert "# The one and only assignment of the anchor." in text
    assert '"re_anchored": False' in text
    assert len(re.findall(r"^\s*anchor = here$", text, re.M)) == 1, (
        "the anchor is assigned in exactly one place"
    )


def test_the_physics_gate_precedes_the_start_sample_and_the_mission(lines: list[str]):
    """A cold-start chassis still dropping onto the ground plane would be
    subtracted into displacement this package did not cause."""
    gate = first_line_matching(lines, r'^GATE_JSON="\$\(hold_window "')
    start = first_line_matching(lines, r'^START_JSON="\$\(sample_pose\)"')
    mission = first_line_matching(lines, r'^MISSION_JSON="\$\(bounded')
    assert gate < start < mission


def test_the_gate_result_is_checked_and_not_merely_recorded(text: str):
    assert "the world never held still for" in text
    assert '"physics_gate_satisfied": gate.get("ok") is True' in text


# ---------------------------------------------------------------------------
# Displacement, and the stop that has to hold.
# ---------------------------------------------------------------------------

def test_displacement_must_be_finite_and_inside_a_tight_window(text: str):
    assert 'MIN_DISPLACEMENT_M="0.30"' in text
    assert 'MAX_DISPLACEMENT_M="0.50"' in text
    assert "math.isfinite(displacement)" in text
    assert "lo <= displacement <= hi" in text


def test_the_displacement_window_is_documented_with_its_reasoning(text: str):
    assert "Lower bound 0.30:" in text
    assert "Upper bound 0.50:" in text
    assert "0.371-0.372 m" in text, "the window cites the measurement it is centred on"


def test_the_window_cannot_be_satisfied_by_settling_drift(text: str):
    """The floor has to be far above the drift the physics gate tolerates, or
    "it twitched" would read as "it drove"."""
    assert float(re.search(r'MIN_DISPLACEMENT_M="([\d.]+)"', text).group(1)) >= 10 * float(
        re.search(r'PHYSICS_GATE_MAX_DRIFT_M="([\d.]+)"', text).group(1)
    )


def test_the_stopped_pose_must_hold_across_simulation_time(text: str):
    """One sample after the mission cannot tell a stop from a slow coast."""
    assert 'STOPPED_GATE_MIN_SIM_S="3.0"' in text
    assert 'STOPPED_GATE_MAX_DRIFT_M="0.01"' in text
    assert 'STOPPED_GATE_WALL_TIMEOUT="60"' in text
    assert '"stopped_pose_is_stable": stopped.get("ok") is True' in text


def test_the_stopped_pose_check_comes_after_the_end_sample(lines: list[str]):
    end = first_line_matching(lines, r'^END_JSON="\$\(sample_pose\)"')
    stopped = first_line_matching(lines, r'^STOPPED_JSON="\$\(hold_window_from')
    assert end < stopped


def test_the_stopped_anchor_is_the_end_sample_itself(lines: list[str], text: str):
    """Not a fresh sample taken once the window opens.

    That is the whole difference between "the gateway stopped it" and "we
    sampled it mid-coast": a coasting chassis re-anchored on holds each new
    anchor perfectly well while travelling, and would be reported as stopped.
    So the anchor is the exact pose-end sample, pulled out of END_JSON field by
    field and handed to the guest.
    """
    for name, field in (("END_SIM_TIME", "sim_time"), ("END_X", "x"), ("END_Y", "y")):
        assert f'{name}="$(json_field "${{END_JSON}}" {field})"' in text, (
            f"{name} must be derived from the end pose sample"
        )
        # Fail-closed: a missing or unusable field ends the run rather than
        # handing the guest a blank anchor to hold against.
        assert f"the end pose sample has no usable {field}" in text

    assert 'STOPPED_JSON="$(hold_window_from "${STOPPED_GATE_MIN_SIM_S}"' in text
    assert '"${END_SIM_TIME}" "${END_X}" "${END_Y}")"' in text

    end = first_line_matching(lines, r'^END_JSON="\$\(sample_pose\)"')
    derived = first_line_matching(lines, r'^END_SIM_TIME="\$\(json_field')
    stopped = first_line_matching(lines, r'^STOPPED_JSON="\$\(hold_window_from')
    assert end < derived < stopped

    # The guest side takes it as a supplied anchor and says so in the artifact.
    assert 'hold-from "${GZ_TOPIC}"' in text
    assert 'anchor_source = "caller-supplied pose" if anchor is not None' in text


def test_no_re_anchoring_quiet_window_survives(executable_text: str):
    """`quiet_window` was the re-anchoring predecessor of these two, and the
    name is the tell: it asserted quiet, not a held anchor. Nothing executable
    may still call it."""
    assert "quiet_window" not in executable_text
    assert "hold_window() {" in executable_text
    assert "hold_window_from() {" in executable_text


def test_the_stopped_pose_verdict_is_checked_the_moment_it_is_written(
    lines: list[str], text: str
):
    """Not deferred to the aggregate.

    The stopped-pose window is the last thing this run measures and the only one
    that distinguishes "the gateway stopped it" from "it is still coasting".
    Leaving its verdict to be discovered during aggregation means everything
    between here and there runs against a chassis that may still be moving, and
    the eventual failure arrives as one name in a list of invariants rather than
    as the thing that went wrong.

    So the check is immediate, on the line after the artifact is written, with a
    message that names the gate that failed and the file to read. The aggregate
    keeps its own copy of the check as defence in depth.
    """
    written = first_line_matching(
        lines,
        r'^printf .*"\$\{STOPPED_JSON\}" >"\$\{OUT_DIR\}/stopped-pose\.json"$',
    )
    checked = first_line_matching(
        lines, r'^\[ "\$\(json_ok "\$\{STOPPED_JSON\}"\)" = "yes" \]'
    )
    assert written < checked, (
        "the stopped-pose artifact is written before its verdict is read"
    )

    # Immediately after: nothing executable may run between the write and the
    # check, or the run continues against a robot that may not have stopped.
    between = [
        line.strip()
        for line in lines[written + 1:checked]
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not between, f"executable lines sit between the write and the check: {between}"

    # Actionable, not just "failed": the gate, its tolerance, and the artifact.
    assert "the stopped pose did not hold for" in text
    assert "${STOPPED_GATE_MIN_SIM_S}s of simulation time" in text
    assert "see ${OUT_DIR}/stopped-pose.json" in text
    assert re.search(
        r'\[ "\$\(json_ok "\$\{STOPPED_JSON\}"\)" = "yes" \][^\n]*\n\s*\|\| fail ', text
    ), "the check must fail the run, not merely log"

    # And it happens before aggregation, which keeps its own check regardless.
    aggregate = first_line_matching(lines, r'^python3 - "\$\{OUT_DIR\}" "\$\{RUN_ID\}"')
    assert checked < aggregate
    assert '"stopped_pose_is_stable": stopped.get("ok") is True' in text


def test_the_stopped_pose_evidence_reaches_the_aggregate(text: str):
    """A window that ran, was written, and was then never read would be a file
    nobody's pass depends on."""
    assert '>"${OUT_DIR}/stopped-pose.json"' in text
    assert 'stopped = read("stopped-pose.json")' in text
    assert '"stopped_pose_is_stable": stopped.get("ok") is True' in text
    assert '"stopped_pose": stopped,' in text


# ---------------------------------------------------------------------------
# Artifacts.
# ---------------------------------------------------------------------------

def test_artifacts_are_versioned_and_run_bounded(text: str):
    assert f'REPORT_CONTRACT="{EXPECTED_REPORT_CONTRACT}"' in text
    assert 'OUT_DIR="${REPO_ROOT}/${FLYTO_RESULTS_ROOT:-results/modules-robotics-gazebo}/${RUN_ID}"' in text
    assert 'GUEST_DIR="/tmp/flyto-modules-robotics-verify/${RUN_ID}"' in text
    assert 'RUN_ID="mrg-$(date -u +%Y%m%dT%H%M%SZ)-$$"' in text


def test_the_behaviour_revision_names_the_two_fixed_defects_exactly(text: str):
    """`verifier_sha256` binds the bytes, but it changes when a comment is
    reflowed, so it cannot answer "did this evidence come from a verifier with
    the two known defects fixed?". This string can, and it is exact rather than
    a range — change either behaviour and it must change with it.

    `fixed-anchor`: the stopped gate's anchor is the pose-end sample itself and
    is never replaced. `process-quiescence`: cleanup terminates every process
    this run started, including the ones started inside command substitutions,
    before it restores the lower runtime.
    """
    assert f'VERIFIER_BEHAVIOR_REVISION="{EXPECTED_BEHAVIOR_REVISION}"' in text
    assert len(re.findall(BEHAVIOR_ASSIGNMENT_RE, text, re.M)) == 1


def test_the_behaviour_revision_is_evidence_and_not_a_dead_constant(text: str):
    """A constant that is assigned and never read is a comment with a `=` in it.

    It was exactly that — ShellCheck SC2034, an unused variable — which meant the
    script could claim a behaviour revision that nothing checked and no artifact
    carried. It now crosses the shell/Python boundary as the final argument to
    the aggregation, is compared there against the literal that aggregation was
    written for, and is written into the report as provenance.
    """
    # Used, not merely assigned: SC2034 cannot be raised against it again.
    assert re.search(r'"\$\{VERIFIER_BEHAVIOR_REVISION\}"', text), (
        "the revision is never read; that is ShellCheck SC2034"
    )

    # Crossing the boundary: the last argv to the aggregate heredoc.
    assert '"${LOWER_RUN_ID_ENV}" "${VERIFIER_BEHAVIOR_REVISION}" <<\'PY\'' in text

    # Unpacked with the argv count grown to match, so a forgotten argument is a
    # ValueError at the top rather than a silently shifted tuple.
    assert "behavior_revision) = sys.argv[1:22]" in text


def test_the_aggregate_refuses_a_revision_it_was_not_written_for(
    lines: list[str], text: str
):
    """Exact, and fail-closed, and before `report.json` is written.

    The shell constant is a claim about what the script does; the literal inside
    the aggregation is what that code knows how to write a report for. Comparing
    them is what stops the two drifting apart and still producing an artifact —
    a report emitted under an unrecognised revision would be evidence for a
    behaviour nobody checked.

    Precisely `report.json`, and not "before any artifact exists": by the time
    the aggregation runs, this run has already written the lower evidence, the
    physics gate, both pose samples, the stopped-pose window and the mission
    result. Those stay. What a mismatch refuses is the aggregate verdict, which
    is the only document that says the run passed.
    """
    assert f'EXPECTED_BEHAVIOR_REVISION = "{EXPECTED_BEHAVIOR_REVISION}"' in text
    assert re.search(
        r"^if behavior_revision != EXPECTED_BEHAVIOR_REVISION:\s*\n\s*sys\.exit\(",
        text,
        re.M,
    ), "the comparison must end the run, not warn"
    assert "verifier behaviour revision mismatch" in text

    # Before the verdict: a rejected revision leaves no report to mistake for a
    # pass, though the run's earlier evidence files remain on disk.
    guard = first_line_matching(
        lines, r"^if behavior_revision != EXPECTED_BEHAVIOR_REVISION:$"
    )
    written = first_line_matching(
        lines, r'open\(os\.path\.join\(out_dir, "report\.json"\), "w"\)'
    )
    assert guard < written, "the revision is checked before a report is written"


def test_the_behaviour_revision_is_recorded_as_provenance(text: str):
    """`verifier_sha256` binds the bytes and changes when a comment is reflowed,
    so it cannot answer "did this evidence come from a verifier with the two
    known defects fixed?". The revision recorded beside it can."""
    assert '"verifier_behavior_revision": behavior_revision,' in text


def test_the_cleanup_document_names_each_key_once(text: str):
    """A duplicated key in a JSON heredoc is not a syntax error — the last one
    silently wins. `restoration_invocations` is the field a run's pass depends
    on, so a second copy would be a gate decided by line order."""
    assert len(re.findall(r'^\s*"restoration_invocations":', text, re.M)) == 1


def test_the_pose_parser_initialises_its_root_once(text: str):
    """One initialisation, because two were redundant and hard to read.

    Being accurate about what the duplicate did and did not do, since an earlier
    version of this docstring overstated it. The pair was

        root = {}
        root = {}
        stack = [root]

    and because `stack` was built after both, it was rooted in the same dict that
    `root` named. Nothing was lost and no parsed field went missing; the first
    dict was created and immediately discarded. The cost was to the reader, who
    has to stop and work out which of the two `stack` points at.

    It is pinned at one anyway, and the second assertion is why: an edit that
    moved `stack = [root]` *between* two initialisations would silently drop
    every parsed field into a dict nobody returns, and that failure looks exactly
    like a world with no matching model in it.
    """
    assert len(re.findall(r"^\s*root = \{\}$", text, re.M)) == 1
    assert re.search(r"^\s*root = \{\}\n\s*stack = \[root\]$", text, re.M), (
        "the stack must be rooted in the one dict that is returned"
    )


@pytest.mark.parametrize(
    "field",
    [
        "provenance", "lower_layer", "step", "gateway_session", "physical_evidence",
        "invariants", "passed", "scope", "plan_id", "request_id",
        "plan_contract_version", "request_contract_version", "displacement_m",
        "physics_gate", "stopped_pose",
    ],
)
def test_the_report_carries_the_field(text: str, field: str):
    assert f'"{field}"' in text


@pytest.mark.parametrize(
    "provenance",
    [
        "started_at", "finished_at", "repo_commit", "lower_repo_commit",
        "verifier_sha256", "verifier_behavior_revision", "package_source_sha256",
        "lima_instance", "gateway_robot_id", "lower_verifier", "lower_run_id_env",
        "gateway_url",
    ],
)
def test_the_report_carries_the_provenance_field(text: str, provenance: str):
    assert f'"{provenance}"' in text


def test_passed_is_a_conjunction_of_every_invariant(text: str):
    """Not a separately asserted boolean that could disagree with the list
    printed beside it."""
    assert '"passed": all(invariants.values())' in text


def test_the_report_says_this_is_not_hardware_evidence(text: str):
    assert "not physical-hardware evidence" in text


def test_the_guest_scratch_is_removed_but_is_not_an_invariant(text: str):
    """A leftover directory under /tmp is untidy, not unsafe. Failing a good run
    over it would be the tail wagging the dog."""
    assert '"guest_scratch_removed": ${SCRATCH_REMOVED}' in text
    assert "SCRATCH_REMOVED" not in text.split("invariants = {")[1].split("}")[0]


# ---------------------------------------------------------------------------
# Bounds.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bound",
    ["LOWER_VERIFIER_TIMEOUT", "SAMPLE_TIMEOUT", "COPY_TIMEOUT",
     "MISSION_TIMEOUT", "RESTORE_TIMEOUT", "SCRATCH_TIMEOUT"],
)
def test_every_external_wait_has_a_bound(text: str, bound: str):
    assert re.search(rf'{bound}="\$\{{{bound}:-\d+\}}"', text)


def test_no_external_command_runs_unbounded(text: str):
    """Every limactl invocation goes through the bounded helper. A verifier that
    can hang is one that gets killed by hand, and a verifier killed by hand
    never runs its restoration."""
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#") or "limactl" not in stripped:
            continue
        if stripped.startswith(("LIMA_INSTANCE=", "command -v")):
            continue
        assert "bounded " in stripped, f"unbounded external command at line {number}: {stripped}"


def test_the_lower_verifier_call_is_bounded_too(text: str):
    assert re.search(
        r'bounded "\$\{LOWER_VERIFIER_TIMEOUT\}" -- \\\n\s*env "\$\{LOWER_RUN_ID_ENV\}', text
    )


def test_the_guest_side_waits_are_bounded_from_the_inside_as_well(text: str):
    """Belt and braces: the probe stops itself at its own deadline rather than
    relying only on the host killing it."""
    assert "deadline = time.monotonic() + wall_timeout" in text
    assert "while time.monotonic() < deadline:" in text
    assert "subprocess.TimeoutExpired" in text


# ---------------------------------------------------------------------------
# What this file is not.
# ---------------------------------------------------------------------------

def test_these_tests_disclaim_being_a_real_run():
    """Stated in the module docstring, and asserted so a future edit that
    quietly drops the disclaimer fails."""
    assert __doc__ is not None
    # Whitespace-normalised: the disclaimer is prose that gets rewrapped, and a
    # reflow is not a dropped disclaimer.
    disclaimer = " ".join(__doc__.split())
    assert "do **not** verify anything about a robot" in disclaimer
    assert "the real run is pending" in disclaimer
