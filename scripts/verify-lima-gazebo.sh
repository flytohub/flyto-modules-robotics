#!/usr/bin/env bash
# Copyright 2026 Flyto2. Licensed under Apache-2.0. See LICENSE.
#
# Bottom-up closed-loop verifier: Gazebo, through this package's own code.
#
# The question this answers is narrow, and it is the one no unit test in this
# repository can answer: does a step *authored here* still mean something to the
# robot runtime *accepted below*? Every test under tests/ asserts that this
# package is self-consistent. A fixture that agrees with the code it tests
# proves only that — the 2026-08-08 handoff records three argument names that
# passed every test in this repository and were still wrong at the gateway.
#
# So this script does not assert against fixtures. It retests its own lower
# layer, then drives that layer through this repository's real code:
#
#   1. run flyto-robotics' own accepted verifier into a results directory this
#      run names, and refuse to continue on anything but its own fresh,
#      exactly-versioned pass;
#   2. put this repository's Python source — and nothing else — into a bounded
#      scratch directory inside the already-running Lima guest;
#   3. take one fixed world-pose anchor and require the freshly cold-started
#      world to hold it: real simulation time advancing while the chassis stays
#      within a centimetre of that single anchor, which is never replaced;
#   4. call steps.plan_for_step() for an authored `robotics.move`, wrap it with
#      plan.run_request(), and hand it to gateway.start_plan() /
#      gateway.await_session(). No hand-authored substitute plan; if the
#      contract drifted, this is where it shows;
#   5. read Gazebo's own world-pose topic before and after, require the chassis
#      to have moved a distance suitable for the command, and then require it
#      to hold the *exact* pose it was in at the moment the gateway reported
#      terminal success.
#
# What it deliberately is not:
#
# * It is not hardware evidence. A Gazebo pass says the contract survives to a
#   simulated chassis. Physical TurtleBot3 evidence is recorded separately in
#   STATE.md and the two are not interchangeable.
# * It does not drive anything itself. It imports no ROS client library — no
#   rclpy — publishes no velocity — nothing here writes cmd_vel — and reads no
#   odometry: /odom is the robot's own opinion of its motion, which is the
#   claim under test, so it is not admissible as evidence for it. It publishes
#   nothing to Gazebo either. The only motion it causes travels the ordinary
#   path: this package's gateway client -> the flyto-robotics gateway -> the
#   robot. That gateway owns the final stop, here as everywhere.
#
#   Those forbidden names appear in this comment and nowhere in the executable
#   body. The tests grep the script with its comments and docstrings stripped,
#   exactly so that naming what is forbidden and not doing it can both be true
#   at once; an earlier draft had to choose, and chose to delete the
#   explanation, which is the wrong half to give up.
# * It never edits flyto-robotics. The sibling checkout is read and executed,
#   never written.
#
# Usage:  scripts/verify-lima-gazebo.sh
# Exit:   0 only if every recorded invariant passed *and* restoration succeeded.

set -euo pipefail

# ---------------------------------------------------------------------------
# Lower-layer coupling.
#
# Everything this script assumes about flyto-robotics is named here, in one
# block, rather than spelled inline where a drift would be invisible.
#
# These are contracts, not preferences, so they are constants and not
# environment overrides. An earlier draft made every one of them overridable;
# that is a contract you can silently switch off from a shell, which is the
# opposite of what a verifier is for. The single thing that is genuinely a
# location rather than a contract — where the sibling checkout lives — stays
# overridable.
#
# The lower verifier takes its run id from the environment. It has no --run-id
# flag; passing one would be interpreted as something else or rejected.
# ---------------------------------------------------------------------------
LOWER_REPO="${FLYTO_ROBOTICS_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/flyto-robotics}"
LOWER_VERIFIER="scripts/verify-lima-gazebo.sh"
LOWER_RUN_ID_ENV="FLYTO_GAZEBO_VERIFY_RUN_ID"
LOWER_RESULTS_DIR="results/virtual-robot"
LOWER_REPORT_NAME="report.json"
LOWER_CLEANUP_NAME="cleanup.json"
LOWER_REPORT_CONTRACT="flyto.robotics.burger-gazebo-acceptance.v1"
LOWER_CLEANUP_CONTRACT="flyto.robotics.runtime-cleanup.v1"

# The lower runtime's *public* way back to a normal, non-fault gateway runtime.
# It takes no flags: it publishes a best-effort zero command and then restarts
# the managed runtime. There is no separate restore script and no --safe-stop.
# Restoration is the lower layer's job, not ours — it owns the robot and it
# owns the stop.
LOWER_RESTORE="scripts/run-lima-gazebo.sh"

LIMA_INSTANCE="flyto-robot-gazebo"

# The runtime's own gateway environment file holds shell `export` assignments,
# not a bare token, so it is *sourced* — inside the guest, by the guest, once.
# It is never read on the host, never copied back, never echoed, and never
# written to an artifact.
#
# Its path is not a constant here. It is written verbatim into the guest
# wrapper below, `$HOME` and all, because it is the guest's home directory that
# resolves it; a constant on this side would either expand to this machine's
# home or need escaping through a heredoc, and both are ways of getting it
# wrong quietly.
#
# It belongs to the mission wrapper and to nothing else. The read-only pose
# probe has its own wrapper, and that wrapper does not source this file, does
# not `set -a`, and needs no credential at all: reading Gazebo's world-pose
# topic is not an authenticated operation, so handing the probe a bearer token
# would widen what a read-only observer can reach for no reason whatsoever.

GATEWAY_URL="${FLYTO_ROBOTICS_GATEWAY_URL:-http://127.0.0.1:8766}"
ROBOT_ID="flyto-rover-sim-001"

# Independent physical evidence. Exact topic, exact model — a prefix match would
# happily accept a different world or a second spawned robot.
GZ_TOPIC="/world/flyto_turtlebot3_fidelity/pose/info"
GZ_MODEL="burger"

# The authored step under test. A plain forward move: the shortest path from a
# canvas parameter to a wheel, with nothing clever in between.
STEP_MODULE_ID="robotics.move"
STEP_DISTANCE_M="0.40"
STEP_SPEED_MPS="0.12"

# The displacement window, in metres, for that 0.40 m command.
#
# Lower bound 0.30: the physical TurtleBot3 measured 0.371-0.372 m against the
#   same 0.400 m command (STATE.md), so a correct run lands near 0.37 and a
#   floor of 0.30 leaves room for a simulated drivetrain that under-runs harder
#   than the physical one. It is also thirty times the 0.01 m drift the physics
#   gate below tolerates, so "it twitched while settling" can never be read as
#   "it drove".
# Upper bound 0.50: a 0.40 m command that carries past half a metre is not a
#   slow floor, it is a stop that did not happen. That must fail loudly rather
#   than round off into a pass.
MIN_DISPLACEMENT_M="0.30"
MAX_DISPLACEMENT_M="0.50"

# The cold-start physics gate.
#
# The lower verifier's cleanup restarts the managed runtime, so by the time we
# arrive the world is a *fresh cold start*: physics that has been stepping for
# seconds, not minutes, with a chassis that may still be settling onto the
# ground plane. A "before" sample taken during that settle would be subtracted
# from the "after" sample and reported as motion this package caused.
#
# So the gate is stated in the simulator's own clock, not the wall clock: ten
# seconds of world-pose simulation time must pass with the Burger drifting no
# more than a centimetre from ONE fixed anchor, and the whole search is bounded
# at ninety wall seconds. A world that is paused advances no sim time and fails
# the gate; a world that is running slower than about one ninth of real time
# also fails it, which is the correct answer — nothing downstream of here would
# be trustworthy.
#
# The anchor is taken once and never replaced. An earlier draft re-anchored
# whenever drift exceeded the tolerance, on the reasoning that a settling
# chassis should be waited out. The effect was the opposite of a gate: a
# chassis moving steadily produced an unbroken run of small per-anchor drifts,
# each one inside tolerance, and the window "passed" after the robot had
# travelled an arbitrary distance. Drift past the tolerance is now a failure,
# and so is a simulation clock that runs backwards — a world reset mid-window
# makes nothing measured across it comparable. Neither is a state to sample
# from, and neither may be waited out.
PHYSICS_GATE_MIN_SIM_S="10.0"
PHYSICS_GATE_MAX_DRIFT_M="0.01"
PHYSICS_GATE_WALL_TIMEOUT="90"

# The post-mission stability gate. Same shape, shorter, and anchored harder:
# its anchor is not a fresh sample but the *exact* pose-end sample taken the
# moment the gateway reported terminal success. That is the difference between
# "the gateway stopped it" and "we sampled it mid-coast" — a coasting chassis
# re-anchored on would hold each new anchor perfectly well while travelling,
# and would be reported as stopped. Three seconds of simulation time within a
# centimetre of the pose the gateway claimed to have stopped in, or the run
# fails.
STOPPED_GATE_MIN_SIM_S="3.0"
STOPPED_GATE_MAX_DRIFT_M="0.01"
STOPPED_GATE_WALL_TIMEOUT="60"

# Bounds. Every wait in this script has one. A verifier that can hang is a
# verifier that gets killed by hand, and a verifier killed by hand does not run
# its restoration.
LOWER_VERIFIER_TIMEOUT="${LOWER_VERIFIER_TIMEOUT:-2400}"
SAMPLE_TIMEOUT="${SAMPLE_TIMEOUT:-30}"
COPY_TIMEOUT="${COPY_TIMEOUT:-120}"
MISSION_TIMEOUT="${MISSION_TIMEOUT:-120}"
RESTORE_TIMEOUT="${RESTORE_TIMEOUT:-300}"
SCRATCH_TIMEOUT="${SCRATCH_TIMEOUT:-60}"

REPORT_CONTRACT="flyto.modules-robotics.gazebo-closed-loop.v1"
CLEANUP_CONTRACT="flyto.modules-robotics.gazebo-cleanup.v1"

# The identity of what this verifier *does*, as distinct from what it says.
#
# verifier_sha256 already binds the bytes, but it changes when a comment is
# reflowed, so it cannot answer "was this evidence produced by a verifier that
# had the two known defects fixed?". This string can, and it is exact rather
# than a range: the aggregation below refuses to write a report under a
# revision it was not written for, so the script and the aggregation cannot
# drift apart and still produce an artifact.
#
# The two behaviours it names, both of which were wrong in the draft before it:
#
#   fixed-anchor      the stopped gate's anchor is the pose-end sample itself,
#                     handed to the probe, and is never replaced by a later one;
#   process-quiescence  cleanup terminates every process this run started —
#                     including the ones started inside command substitutions,
#                     which no in-memory shell register can see — before it
#                     restores the lower runtime.
#
# Change either behaviour and this constant must change with it. It is not a
# version to bump for tidiness.
VERIFIER_BEHAVIOR_REVISION="fixed-anchor-process-quiescence.v1"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_ID="mrg-$(date -u +%Y%m%dT%H%M%SZ)-$$"

# The lower run id is ours and unique to this run. Because the lower cleanup
# contract carries no run_id field of its own, freshness cannot be proved by
# reading one; it is proved by the *path*. We name a directory that must not
# already exist, refuse to continue if it does, and then bind what we read
# there to this run by SHA-256.
LOWER_RUN_ID="${RUN_ID}-lower"
LOWER_RUN_DIR="${LOWER_REPO}/${LOWER_RESULTS_DIR}/${LOWER_RUN_ID}"

OUT_DIR="${REPO_ROOT}/${FLYTO_RESULTS_ROOT:-results/modules-robotics-gazebo}/${RUN_ID}"
GUEST_DIR="/tmp/flyto-modules-robotics-verify/${RUN_ID}"

mkdir -p "${OUT_DIR}"

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%SZ)" "$*" >&2; }
fail() { log "FAIL: $*"; exit 1; }

# A JSON string, quoted rather than pasted: a stray quote in an error detail
# would otherwise produce an artifact that is not JSON at all.
jstr() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))' "$1"
  else
    printf '"%s"' "$(printf '%s' "$1" | tr -d '\000-\037' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
  fi
}

sha256_of() {
  python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
}

# Every process id in a tree, parent last. `ps -Ao pid,ppid` is the one listing
# both macOS and Linux agree on; `pkill -P` and `ps --forest` are not portable
# here, and neither is `setsid`, so the tree is walked rather than signalled as
# a process group.
#
# The walk has to happen *before* anything is killed. Once a parent dies its
# children are reparented to init and the tree that connected them is gone —
# which is precisely how an earlier draft left a timed-out lower verifier's
# children running.
descendants_of() {
  command -v python3 >/dev/null 2>&1 || return 0
  python3 - "$1" <<'PY'
import subprocess, sys

root = int(sys.argv[1])
try:
    listing = subprocess.run(["ps", "-Ao", "pid,ppid"],
                             capture_output=True, text=True, timeout=15).stdout
except Exception:
    sys.exit(0)

children = {}
for line in listing.splitlines()[1:]:
    parts = line.split()
    if len(parts) < 2:
        continue
    try:
        pid, ppid = int(parts[0]), int(parts[1])
    except ValueError:
        continue
    children.setdefault(ppid, []).append(pid)

found, stack = [], [root]
while stack:
    for child in children.get(stack.pop(), ()):
        if child != root and child not in found:
            found.append(child)
            stack.append(child)
sys.stdout.write(" ".join(str(pid) for pid in found))
PY
}

# Terminate a process and everything it started, bounded. TERM to the whole
# tree, a grace period, then KILL to whatever is left. The grace is what makes
# this a termination rather than a guess.
terminate_tree() {
  local root="${1:?terminate_tree needs a pid}" grace="${2:-10}"
  local tree target waited alive
  tree="$(descendants_of "${root}" || true) ${root}"
  for target in ${tree}; do
    kill -TERM "${target}" 2>/dev/null || true
  done
  waited=0
  while [ "${waited}" -lt "${grace}" ]; do
    alive=0
    for target in ${tree}; do
      if kill -0 "${target}" 2>/dev/null; then alive=1; fi
    done
    if [ "${alive}" -eq 0 ]; then break; fi
    sleep 1
    waited=$((waited + 1))
  done
  for target in ${tree}; do
    kill -KILL "${target}" 2>/dev/null || true
  done
  wait "${root}" 2>/dev/null || true
}

# Bounded execution, portable. `timeout` is coreutils and this runs on macOS.
# BOUNDED_TIMED_OUT distinguishes "the command exited 124" from "we killed it",
# which matters because the restoration's exit code is recorded exactly.
#
# BOUNDED_ACTIVE_PIDS is the register of processes this script has started and
# not yet reaped. Cleanup reads it before restoring the lower runtime: a
# verifier that timed out must not still be talking to the runtime that
# restoration is about to restart, because that is two writers and one robot.
#
# A shell variable alone cannot carry that register, and the reason is not
# subtle once seen: `bounded` is called from inside `$( ... )` for the mission,
# for every pose sample and for both hold windows. A command substitution is a
# subshell, so every assignment `bounded` makes there — BOUNDED_ACTIVE_PIDS and
# BOUNDED_TIMED_OUT alike — is discarded when the substitution closes. The
# in-memory register is therefore empty for exactly the processes that matter
# most: the mission driver and the probes, the ones that speak to the runtime.
#
# So the register is also a file, in this run's own artifact directory, which a
# subshell and its parent do share. `bounded` appends a pid to it on start and
# removes that pid on a normal reap, so what remains is what is still running.
# Cleanup reads the file *and* the variable and deduplicates the two.
BOUNDED_TIMED_OUT=0
BOUNDED_ACTIVE_PIDS=""
BOUNDED_KILL_GRACE="${BOUNDED_KILL_GRACE:-10}"
BOUNDED_PID_FILE="${OUT_DIR}/active-pids"
: >"${BOUNDED_PID_FILE}"

# Append. Best effort on the file: a registry we could not write is a weaker
# cleanup, not a reason to abandon a run that is otherwise fine.
_bounded_register() {
  local pid="$1"
  BOUNDED_ACTIVE_PIDS="${BOUNDED_ACTIVE_PIDS} ${pid}"
  printf '%s\n' "${pid}" >>"${BOUNDED_PID_FILE}" 2>/dev/null || true
}

# Remove one pid from the shared registry. Rewrite-and-rename rather than
# in-place editing, so a reader never sees a half-written file.
_bounded_registry_drop() {
  local drop="$1" tmp
  [ -f "${BOUNDED_PID_FILE}" ] || return 0
  tmp="${BOUNDED_PID_FILE}.tmp.$$"
  { grep -v -x -F "${drop}" "${BOUNDED_PID_FILE}" || true; } >"${tmp}" 2>/dev/null || true
  mv -f "${tmp}" "${BOUNDED_PID_FILE}" 2>/dev/null || rm -f "${tmp}" 2>/dev/null || true
}

# The normal reap: forget the pid in memory and in the registry file, so the
# registry only ever hands cleanup processes that had not been waited for.
_bounded_forget() {
  local drop="$1" kept="" pid
  for pid in ${BOUNDED_ACTIVE_PIDS}; do
    if [ "${pid}" != "${drop}" ]; then kept="${kept} ${pid}"; fi
  done
  BOUNDED_ACTIVE_PIDS="${kept}"
  _bounded_registry_drop "${drop}"
}

bounded() {
  local limit="${1:?bounded needs a limit}"; shift
  if [ "${1:-}" = "--" ]; then shift; fi
  BOUNDED_TIMED_OUT=0
  "$@" &
  local pid=$! waited=0 rc=0
  _bounded_register "${pid}"
  while kill -0 "${pid}" 2>/dev/null; do
    if [ "${waited}" -ge "${limit}" ]; then
      BOUNDED_TIMED_OUT=1
      terminate_tree "${pid}" "${BOUNDED_KILL_GRACE}"
      _bounded_forget "${pid}"
      return 124
    fi
    sleep 1
    waited=$((waited + 1))
  done
  wait "${pid}" || rc=$?
  _bounded_forget "${pid}"
  return "${rc}"
}

# ---------------------------------------------------------------------------
# Restoration. Installed BEFORE any runtime action, on purpose.
#
# Everything below this block can leave a robot moving or a runtime in a fault
# state. Nothing above it can. Registering the trap first is the difference
# between "we clean up after the things we did" and "we clean up after the
# things we did, plus the one that failed while we were still deciding what to
# do".
#
# There is exactly one restoration owner and exactly one restoration command.
# The lower layer's run-lima-gazebo.sh already publishes a best-effort zero
# command before it restarts the managed runtime, so a separate stop step here
# would be this package inventing a stop — which AGENTS.md forbids, and which
# would be a second, differently-implemented safety path besides.
#
# It runs exactly once, on success, on failure, and on signal. It never improves
# the exit status: a run that failed at the gateway and restored perfectly is
# still a failed run. It can only make it worse — a restoration that did not
# happen is itself a failure, because the next person to walk up to this
# exhibition inherits whatever state we left.
# ---------------------------------------------------------------------------
CLEANUP_DONE=0
RESTORE_ATTEMPTED=false
RESTORE_INVOCATIONS=0
RESTORE_EXIT=-1
RESTORE_TIMED_OUT=false
RESTORE_OK=false
RESTORE_DETAIL="not attempted"
SCRATCH_REMOVED=false
LOWER_QUIESCED=true
QUIESCE_GRACE="${QUIESCE_GRACE:-15}"

on_exit() {
  local status=$?

  # Disarm before doing anything else. The status has been captured, so from
  # here on the only thing that can end this process is the tail of this
  # function. Removing the EXIT trap stops the `exit` calls below from
  # re-entering the handler, and ignoring INT and TERM means a second Ctrl-C —
  # the reflex when a restoration looks slow — cannot abort restoration
  # half-done. An interrupted restoration is worse than a slow one: it leaves a
  # runtime that was being restarted and now is neither stopped nor running.
  # CLEANUP_DONE stays as the belt to this braces, and the status behaviour it
  # guards is unchanged.
  trap - EXIT
  trap '' INT TERM

  if [ "${CLEANUP_DONE}" -eq 1 ]; then exit "${status}"; fi
  CLEANUP_DONE=1
  set +e

  # Quiesce first, restore second. `bounded` kills the process it started, but
  # a lower verifier killed at its timeout can have left children behind, and
  # those children speak to the same runtime restoration is about to restart.
  # Restoring underneath a still-running writer is how a runtime ends up in a
  # state neither of them intended.
  #
  # Both registers are read: the in-memory one, which holds the calls made in
  # this shell, and the run-scoped registry file, which is the only one that
  # holds the calls made inside command substitutions — the mission and the
  # probes. They overlap, so the union is deduplicated before anything is
  # signalled; sending TERM twice would be harmless, but reporting the same pid
  # twice as un-quiesced would not be honest.
  local pid candidate seen="" registry=""
  if [ -f "${BOUNDED_PID_FILE}" ]; then
    registry="$(tr '\n' ' ' <"${BOUNDED_PID_FILE}" 2>/dev/null || true)"
  fi
  for candidate in ${BOUNDED_ACTIVE_PIDS} ${registry}; do
    case " ${seen} " in *" ${candidate} "*) continue ;; esac
    seen="${seen} ${candidate}"
    pid="${candidate}"
    if kill -0 "${pid}" 2>/dev/null; then
      log "cleanup: terminating a still-running process tree (pid ${pid}) before restoring"
      terminate_tree "${pid}" "${QUIESCE_GRACE}"
      if kill -0 "${pid}" 2>/dev/null; then LOWER_QUIESCED=false; fi
    fi
  done

  log "cleanup: returning the lower runtime to a normal, non-fault gateway"

  # The one restoration command, with no flags, exactly once, on every path.
  if [ -x "${LOWER_REPO}/${LOWER_RESTORE}" ]; then
    RESTORE_ATTEMPTED=true
    bounded "${RESTORE_TIMEOUT}" -- "${LOWER_REPO}/${LOWER_RESTORE}" \
      >"${OUT_DIR}/restore.log" 2>&1
    RESTORE_EXIT=$?
    # Counted after the fact, because it is a count of what ran and not a
    # statement of what we meant to run.
    RESTORE_INVOCATIONS=1
    if [ "${BOUNDED_TIMED_OUT}" -eq 1 ]; then
      RESTORE_TIMED_OUT=true
      RESTORE_DETAIL="restoration exceeded ${RESTORE_TIMEOUT}s and was killed; see restore.log"
    elif [ "${RESTORE_EXIT}" -eq 0 ]; then
      RESTORE_OK=true
      RESTORE_DETAIL="run-lima-gazebo.sh returned 0; normal gateway runtime restarted"
    else
      RESTORE_DETAIL="run-lima-gazebo.sh exited ${RESTORE_EXIT}; see restore.log"
    fi
  else
    # Nothing ran, so nothing is recorded as having run. An earlier draft wrote
    # restoration_invocations: 1 unconditionally, which meant the artifact for
    # the one case where restoration was impossible — no executable, no process,
    # no exit status — was the case that claimed most confidently to have
    # restored something. restoration_attempted stays false, the count stays 0,
    # the exit code stays the -1 that means "no process, no status", and
    # restoration_timed_out stays false because nothing existed to time out.
    RESTORE_DETAIL="lower restoration path is not executable: ${LOWER_REPO}/${LOWER_RESTORE}"
  fi

  # Our own bounded scratch inside the guest. Best effort, and not an invariant:
  # a leftover directory under /tmp is untidy, not unsafe.
  bounded "${SCRATCH_TIMEOUT}" -- limactl shell "${LIMA_INSTANCE}" -- \
    rm -rf "${GUEST_DIR}" >/dev/null 2>&1 && SCRATCH_REMOVED=true

  # A run only passes if exactly one restoration ran, returned 0, was not
  # killed at its bound, and had nothing of ours still running beside it.
  local final="${status}"
  if [ "${final}" -eq 0 ]; then
    if [ "${RESTORE_INVOCATIONS}" -ne 1 ] || [ "${RESTORE_OK}" != true ] \
       || [ "${RESTORE_EXIT}" -ne 0 ] || [ "${RESTORE_TIMED_OUT}" != false ] \
       || [ "${LOWER_QUIESCED}" != true ]; then
      final=1
    fi
  fi

  cat >"${OUT_DIR}/cleanup.json" <<EOF
{
  "contract_version": "${CLEANUP_CONTRACT}",
  "run_id": "${RUN_ID}",
  "lower_run_id": "${LOWER_RUN_ID}",
  "restoration_command": $(jstr "${LOWER_REPO}/${LOWER_RESTORE}"),
  "restoration_flags": [],
  "restoration_invocations": ${RESTORE_INVOCATIONS},
  "restoration_attempted": ${RESTORE_ATTEMPTED},
  "restoration_exit_code": ${RESTORE_EXIT},
  "restoration_timed_out": ${RESTORE_TIMED_OUT},
  "restored_normal_gateway_runtime": ${RESTORE_OK},
  "lower_processes_quiesced": ${LOWER_QUIESCED},
  "quiesce_grace_seconds": ${QUIESCE_GRACE},
  "restoration_detail": $(jstr "${RESTORE_DETAIL}"),
  "zero_command_owner": "flyto-robotics run-lima-gazebo.sh publishes it best-effort before restarting the runtime; this package never publishes one",
  "guest_scratch_path": $(jstr "${GUEST_DIR}"),
  "guest_scratch_removed": ${SCRATCH_REMOVED},
  "incoming_status": ${status},
  "final_status": ${final}
}
EOF

  # Preserve the original failure; a clean restoration cannot rescue it.
  if [ "${status}" -ne 0 ]; then
    log "cleanup: done (the run had already failed with ${status})"
    exit "${status}"
  fi
  if [ "${RESTORE_OK}" != true ]; then
    log "cleanup: FAILED to restore the normal gateway runtime — failing an otherwise-passing run"
    exit 1
  fi
  if [ "${final}" -ne 0 ]; then
    log "cleanup: restoration was not provably one clean invocation — failing an otherwise-passing run"
    exit "${final}"
  fi
  log "cleanup: done"
  exit 0
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# --- end of the no-runtime-action zone -------------------------------------

log "run ${RUN_ID}; artifacts under ${OUT_DIR}"

# ---------------------------------------------------------------------------
# Preflight. Cheap, total, and before anything moves.
# ---------------------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || fail "python3 is required"
command -v limactl >/dev/null 2>&1 || fail "limactl is required"
command -v tar >/dev/null 2>&1 || fail "tar is required"
[ -d "${LOWER_REPO}" ] || fail "flyto-robotics not found at ${LOWER_REPO}"
[ -x "${LOWER_REPO}/${LOWER_VERIFIER}" ] || fail "lower verifier not executable: ${LOWER_REPO}/${LOWER_VERIFIER}"
[ -x "${LOWER_REPO}/${LOWER_RESTORE}" ] || fail "lower restoration not executable: ${LOWER_REPO}/${LOWER_RESTORE}"
[ -d "${REPO_ROOT}/src/flyto_modules_robotics" ] || fail "this package's source is missing"

# Freshness, established before the fact rather than inferred after it. The
# lower cleanup contract carries no run_id, so the only thing that can bind its
# evidence to this run is that we chose a path nothing had written to yet.
[ ! -e "${LOWER_RUN_DIR}" ] || fail "the chosen lower results path already exists: ${LOWER_RUN_DIR}"

SCRIPT_SHA256="$(sha256_of "${BASH_SOURCE[0]}")"
REPO_COMMIT="$(git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || echo unknown)"
LOWER_COMMIT="$(git -C "${LOWER_REPO}" rev-parse HEAD 2>/dev/null || echo unknown)"

# ---------------------------------------------------------------------------
# 1. Retest the lower layer, and believe only its own evidence.
#
# Running it is not the point; running it into a directory we named is. That is
# what makes the report and cleanup we then read provably this run's, and not a
# file left behind by a pass three weeks ago.
# ---------------------------------------------------------------------------
log "running the accepted flyto-robotics verifier (${LOWER_RUN_ID_ENV}=${LOWER_RUN_ID})"
if ! bounded "${LOWER_VERIFIER_TIMEOUT}" -- \
      env "${LOWER_RUN_ID_ENV}=${LOWER_RUN_ID}" "${LOWER_REPO}/${LOWER_VERIFIER}" \
      >"${OUT_DIR}/lower-verifier.log" 2>&1; then
  fail "the lower verifier did not pass; see ${OUT_DIR}/lower-verifier.log"
fi

LOWER_REPORT="${LOWER_RUN_DIR}/${LOWER_REPORT_NAME}"
LOWER_CLEANUP="${LOWER_RUN_DIR}/${LOWER_CLEANUP_NAME}"
[ -f "${LOWER_REPORT}" ] || fail "no lower report at ${LOWER_REPORT}"
[ -f "${LOWER_CLEANUP}" ] || fail "no lower cleanup evidence at ${LOWER_CLEANUP}"

# Missing, malformed, false, wrong-typed and wrong-version evidence are five
# different ways of not having proof, and none of them is a pass.
LOWER_EVIDENCE="$(python3 - "${LOWER_REPORT}" "${LOWER_CLEANUP}" "${LOWER_RUN_ID}" \
                    "${LOWER_REPORT_CONTRACT}" "${LOWER_CLEANUP_CONTRACT}" "${LOWER_RUN_DIR}" <<'PY'
import hashlib, json, sys

(report_path, cleanup_path, run_id,
 report_contract, cleanup_contract, run_dir) = sys.argv[1:7]


def load(path, contract):
    raw = open(path, "rb").read()
    try:
        doc = json.loads(raw)
    except Exception as exc:
        sys.exit(f"malformed JSON in {path}: {exc}")
    if not isinstance(doc, dict):
        sys.exit(f"{path} is not a JSON object")
    got = doc.get("contract_version")
    if got != contract:
        sys.exit(f"{path} has contract_version {got!r}, expected {contract!r}")
    return doc, hashlib.sha256(raw).hexdigest()


def exactly_true(doc, field, path):
    # `is True`, not truthy: the string "false" and the number 0 are both things
    # a report generator has emitted before, and only one of them looks false.
    if doc.get(field) is not True:
        sys.exit(f"{path}: {field} is {doc.get(field)!r}, expected exactly true")


def exactly_int_zero(doc, field, path):
    value = doc.get(field)
    # bool is an int in Python; True would otherwise pass an == 0 style check
    # in the one direction that matters least and fail in the one that matters.
    if isinstance(value, bool) or not isinstance(value, int) or value != 0:
        sys.exit(f"{path}: {field} is {value!r}, expected exactly the integer 0")


report, report_digest = load(report_path, report_contract)
cleanup, cleanup_digest = load(cleanup_path, cleanup_contract)

exactly_true(report, "passed", report_path)

# The lower report may or may not restate the run id. When it does it must
# agree; when it does not, the path we chose is what binds it to this run.
report_run_id = report.get("run_id")
if report_run_id is not None and report_run_id != run_id:
    sys.exit(f"{report_path} carries run_id {report_run_id!r}, expected {run_id!r}")

# The cleanup contract has no run_id field at all. Not looking for one is
# deliberate: an absent field must not be read as a mismatch, and freshness for
# this document comes from the unique path plus the digest recorded here.
exactly_true(cleanup, "passed", cleanup_path)
exactly_true(cleanup, "restored_normal_gateway_runtime", cleanup_path)
exactly_true(cleanup, "zero_command_published", cleanup_path)
exactly_int_zero(cleanup, "normal_runtime_restoration_exit_code", cleanup_path)
exactly_int_zero(cleanup, "verification_status", cleanup_path)

json.dump({
    "lower_run_id": run_id,
    "lower_run_dir": run_dir,
    "freshness": "the results directory was proved not to exist before the lower verifier ran",
    "report_path": report_path,
    "report_sha256": report_digest,
    "report_contract_version": report_contract,
    "report_passed": True,
    "cleanup_path": cleanup_path,
    "cleanup_sha256": cleanup_digest,
    "cleanup_contract_version": cleanup_contract,
    "cleanup_checked": {
        "passed": True,
        "restored_normal_gateway_runtime": True,
        "zero_command_published": True,
        "normal_runtime_restoration_exit_code": 0,
        "verification_status": 0,
    },
    "cleanup_has_no_run_id_field_by_contract": "run_id" not in cleanup,
    "passed": True,
}, sys.stdout)
PY
)" || fail "the lower layer's evidence was rejected"
printf '%s\n' "${LOWER_EVIDENCE}" >"${OUT_DIR}/lower-evidence.json"
log "lower layer verified and its evidence accepted"

# ---------------------------------------------------------------------------
# 2. This repository's source, and only that, into a bounded guest directory.
#
# Source only: no results, no .git, no venv, and nothing at all in the other
# direction. flyto-robotics is read and run; it is never written.
# ---------------------------------------------------------------------------
log "staging this package's source into ${GUEST_DIR}"
bounded "${COPY_TIMEOUT}" -- limactl shell "${LIMA_INSTANCE}" -- \
  mkdir -p "${GUEST_DIR}/src" || fail "could not create the guest verification directory"

STAGE="$(mktemp -d)"
COPYFILE_DISABLE=1 tar -C "${REPO_ROOT}/src" --exclude '__pycache__' \
  -cf "${STAGE}/source.tar" flyto_modules_robotics || fail "could not stage this package's source"
SOURCE_SHA256="$(sha256_of "${STAGE}/source.tar")"

bounded "${COPY_TIMEOUT}" -- limactl copy "${STAGE}/source.tar" \
  "${LIMA_INSTANCE}:${GUEST_DIR}/source.tar" \
  || fail "could not copy this package's source into the guest"
bounded "${COPY_TIMEOUT}" -- limactl shell "${LIMA_INSTANCE}" -- \
  tar -xf "${GUEST_DIR}/source.tar" -C "${GUEST_DIR}/src" \
  || fail "could not unpack this package's source in the guest"

# ---------------------------------------------------------------------------
# The guest-side programs. Written here so the whole verifier reads as one
# file, and so nothing that touches the runtime's secret persists on the host.
# ---------------------------------------------------------------------------
GZ_PROBE="${STAGE}/gz_probe.py"
cat >"${GZ_PROBE}" <<'PY'
"""Read-only samples of Gazebo's own world-pose topic.

This is the independent evidence. Nothing on the mission path — not the plan,
not the gateway, not odometry — writes to this topic; it is the simulator
reporting where the chassis actually is. Odometry would be the robot's own
opinion of its motion, which is exactly the claim under test.

Read-only in the literal sense: `gz topic -e` echoes. There is no publish here,
no ROS client library, no velocity, and no way for this file to move anything.

Three modes:

  sample                                     one pose, with its simulation stamp
  hold      MIN_SIM MAX_DRIFT WALL           hold an anchor this run takes
  hold-from MIN_SIM MAX_DRIFT WALL SIM X Y   hold an anchor the caller supplies

`hold` and `hold-from` are the same function and differ only in where the one
anchor comes from: its own first usable sample, or the exact pose the caller
already measured. Either way MIN_SIM seconds of *simulation* time must pass
with the model inside MAX_DRIFT metres of that single anchor, and the anchor is
never replaced.

That last clause is the whole invariant, so it is worth being explicit about
what it costs and why it is still right. Re-anchoring is tempting because a
cold-started chassis really is settling, and waiting that out really is what a
gate should do. But a re-anchoring window cannot distinguish settling from
travelling: a chassis moving at a steady centimetre per sample satisfies every
successive anchor it is given, and the window reports quiet after the robot has
crossed the room. Drift past the tolerance is therefore a failure. So is a
simulation clock that runs backwards, which means the world was reset and
nothing measured across the boundary is comparable. So is exhausting WALL
seconds — a world that is paused, or running far below real time, or simply
never still, is not a world to sample from. All three fail closed.
"""
import json, math, subprocess, sys, time
import re

_OPEN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\{$")
_FIELD = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


def parse_text_proto(text):
    """Text-format protobuf into nested dicts of lists.

    A brace-and-indent parser rather than one big regex. The regex version this
    replaces matched `pose { ... }` non-greedily up to the first line-initial
    `}`, which is the *inner* brace of the first nested block — so it read a
    truncated body and could silently miss the model it was looking for.
    """
    root = {}
    stack = [root]
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "}":
            if len(stack) > 1:
                stack.pop()
            continue
        opened = _OPEN.match(line)
        if opened:
            child = {}
            stack[-1].setdefault(opened.group(1), []).append(child)
            stack.append(child)
            continue
        field = _FIELD.match(line)
        if field:
            stack[-1].setdefault(field.group(1), []).append(field.group(2).strip())
    return root


def _first(node, key):
    values = node.get(key) or []
    return values[0] if values else None


def _number(node, key):
    raw = _first(node, key)
    if not isinstance(raw, str):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _name(node):
    raw = _first(node, "name")
    if not isinstance(raw, str):
        return None
    return raw.strip().strip('"')


def _sim_time(root):
    header = _first(root, "header")
    if not isinstance(header, dict):
        return None
    stamp = _first(header, "stamp")
    if not isinstance(stamp, dict):
        return None
    seconds = _number(stamp, "sec")
    if seconds is None:
        return None
    return seconds + (_number(stamp, "nsec") or 0.0) / 1e9


def _model_xy(root, model):
    for entry in root.get("pose", []):
        # Exact model name, never a prefix: a second spawned robot must not be
        # mistaken for this one.
        if not isinstance(entry, dict) or _name(entry) != model:
            continue
        position = _first(entry, "position")
        if not isinstance(position, dict):
            continue
        x, y = _number(position, "x"), _number(position, "y")
        if x is not None and y is not None:
            return x, y
    return None


def sample(topic, model, timeout):
    started = time.monotonic()
    try:
        proc = subprocess.run(
            ["gz", "topic", "-e", "-t", topic, "-n", "1"],
            capture_output=True, text=True, timeout=max(1.0, timeout),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"no message on {topic} within {timeout:g}s"}
    except FileNotFoundError:
        return {"ok": False, "error": "the `gz` command is not available in the guest"}
    if proc.returncode != 0:
        return {"ok": False, "error": f"`gz topic -e` exited {proc.returncode}"}

    root = parse_text_proto(proc.stdout)
    sim_time = _sim_time(root)
    xy = _model_xy(root, model)
    if sim_time is None or xy is None:
        return {"ok": False,
                "error": f"no simulation-stamped pose for model {model!r} on {topic}"}
    if not all(math.isfinite(v) for v in (sim_time, xy[0], xy[1])):
        return {"ok": False, "error": "Gazebo reported a non-finite pose or stamp"}
    return {"ok": True, "topic": topic, "model": model,
            "source": "gazebo.world.pose.info",
            "sim_time": sim_time, "x": xy[0], "y": xy[1],
            "sampled_in_wall_seconds": round(time.monotonic() - started, 3)}


def hold_window(topic, model, min_sim, max_drift, wall_timeout, sample_timeout,
                anchor=None):
    """Hold ONE anchor pose for min_sim seconds of the simulator's own clock.

    `anchor` is either supplied by the caller or taken from the first usable
    sample. It is assigned at most once, and there is deliberately no code path
    in this function that assigns it a second time.
    """
    anchor_source = "caller-supplied pose" if anchor is not None else "first usable sample"
    deadline = time.monotonic() + wall_timeout
    samples = 0
    peak_drift = 0.0
    advance = None
    last_error = None

    def verdict(ok, final=None, error=None):
        out = {"ok": ok, "topic": topic, "model": model,
               "source": "gazebo.world.pose.info",
               "anchor_source": anchor_source,
               "re_anchored": False,
               "required_sim_seconds": min_sim,
               "sim_seconds_observed": advance,
               "max_drift_allowed_m": max_drift,
               "max_drift_observed_m": peak_drift,
               "drift_is_finite": True,
               "samples": samples,
               "wall_seconds_allowed": wall_timeout,
               "anchor": anchor,
               "final": final}
        if not ok:
            out["drift_is_finite"] = math.isfinite(peak_drift)
            out["error"] = error
        return out

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        current = sample(topic, model, min(sample_timeout, max(1.0, remaining)))
        if current.get("ok") is not True:
            last_error = current.get("error")
            time.sleep(0.5)
            continue
        samples += 1
        here = {k: current[k] for k in ("sim_time", "x", "y")}

        # The one and only assignment of the anchor.
        if anchor is None:
            anchor = here

        # A simulation clock that went backwards means the world was reset.
        # Anything measured across that boundary is meaningless, and taking a
        # fresh anchor would launder the reset into a pass.
        if here["sim_time"] < anchor["sim_time"]:
            return verdict(False, final=here, error=(
                "the simulation clock went backwards from "
                f"{anchor['sim_time']:.3f}s to {here['sim_time']:.3f}s: the world "
                "was reset, so nothing measured across it is comparable"))

        drift = math.hypot(here["x"] - anchor["x"], here["y"] - anchor["y"])
        if not math.isfinite(drift):
            return verdict(False, final=here,
                           error="Gazebo reported a pose that is not finite")
        peak_drift = max(peak_drift, drift)
        if drift > max_drift:
            return verdict(False, final=here, error=(
                f"the model moved {drift:.4f}m from its fixed anchor, past the "
                f"{max_drift:g}m tolerance; the anchor is never replaced, so "
                "this is a failure and not something to wait out"))

        advance = here["sim_time"] - anchor["sim_time"]
        if advance >= min_sim:
            return verdict(True, final=here)
        time.sleep(0.5)

    return verdict(False, error=last_error or (
        f"no {min_sim:g}s of simulation time within {max_drift:g}m of the fixed "
        f"anchor appeared inside {wall_timeout:g} wall seconds"))


mode, topic, model, sample_timeout = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
if mode == "sample":
    print(json.dumps(sample(topic, model, sample_timeout)))
elif mode in ("hold", "hold-from"):
    fixed = None
    if mode == "hold-from":
        fixed = {"sim_time": float(sys.argv[8]),
                 "x": float(sys.argv[9]), "y": float(sys.argv[10])}
        if not all(math.isfinite(value) for value in fixed.values()):
            print(json.dumps({"ok": False,
                              "error": "the supplied anchor pose is not finite"}))
            raise SystemExit(0)
    print(json.dumps(hold_window(topic, model, float(sys.argv[5]), float(sys.argv[6]),
                                 float(sys.argv[7]), sample_timeout, fixed)))
else:
    print(json.dumps({"ok": False, "error": f"unknown mode {mode!r}"}))
PY

# The pose probe's own guest runtime environment.
#
# `gz` is not on the PATH that a plain `limactl shell ... python3` inherits. It
# lives at /opt/ros/jazzy/opt/gz_tools_vendor/bin/gz, which is put on the PATH by
# the runtime's two setup files and by nothing else — so a probe run without
# them raises FileNotFoundError, every sample fails, and the hold window reports
# samples: 0 with "the `gz` command is not available in the guest". That is
# exactly what run mrg-20260809T090403Z-64172 recorded in physics-gate.json: a
# verifier failing on its own environment rather than on anything about the
# robot. The accepted lower verifier sources these same two files, which is what
# makes this the runtime's environment rather than a PATH this script invented.
#
# This heredoc is quoted, so every line below is written verbatim and every
# expansion happens in the guest. That is the point for $HOME: the workspace
# lives under the *guest's* home directory, and expanding it here would name
# this machine's home, which holds none of it.
#
# What this wrapper deliberately does not do: it does not source the runtime's
# gateway environment file, and it does not `set -a`. Echoing a world-pose topic
# needs no bearer token, and a read-only observer that carries one is a
# credential in a process that has no use for it.
#
# `set +u` around the sourcing, and only around it: ROS setup files legitimately
# read variables that are not set yet, and `set -u` would abort on the first of
# them before the PATH was ever extended. Failing closed is restored immediately
# after.
PROBE_SH="${STAGE}/probe.sh"
cat >"${PROBE_SH}" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
PROBE_ROS_SETUP="/opt/ros/jazzy/setup.bash"
PROBE_WORKSPACE_SETUP="$HOME/.local/share/flyto-robot-gazebo/workspace/install/setup.bash"
if [ ! -r "${PROBE_ROS_SETUP}" ]; then
  printf '%s\n' '{"ok": false, "error": "the guest ROS setup file is not readable"}'
  exit 0
fi
if [ ! -r "${PROBE_WORKSPACE_SETUP}" ]; then
  printf '%s\n' '{"ok": false, "error": "the guest workspace setup file is not readable"}'
  exit 0
fi
set +u
# shellcheck source=/dev/null
. "${PROBE_ROS_SETUP}"
# shellcheck source=/dev/null
. "${PROBE_WORKSPACE_SETUP}"
set -u
exec python3 "${FLYTO_PROBE_ROOT}/gz_probe.py" "$@"
SH

MISSION="${STAGE}/mission.py"
cat >"${MISSION}" <<'PY'
"""The mission, driven through this repository's real code.

Deliberately not a hand-authored plan. The whole point is that whatever
steps.plan_for_step() produces *today* is what the gateway receives — if an
argument name drifts again, this is where it must fail, and not in a fixture
that was updated alongside the drift.

The runtime's credentials are already in this process's environment: the
wrapper sourced the gateway environment file, in the guest, and exported what
it defines. Nothing here reads that file, prints an environment, or puts a
credential in the JSON it emits. The only thing recorded about the token is
which variable name carried it.
"""
import json, os, sys, time, uuid

sys.path.insert(0, os.environ["FLYTO_VERIFY_SRC"])

from flyto_modules_robotics import gateway
from flyto_modules_robotics.plan import (
    PLAN_CONTRACT_VERSION, PLAN_RUN_REQUEST_CONTRACT_VERSION, run_request,
)
from flyto_modules_robotics.steps import plan_for_step

module_id, distance_m, speed, robot, fallback_url, timeout = (
    sys.argv[1], float(sys.argv[2]), float(sys.argv[3]),
    sys.argv[4], sys.argv[5], float(sys.argv[6]),
)


def die(detail, **extra):
    print(json.dumps({"ok": False, "error": detail, **extra}))
    raise SystemExit(0)


# AGENTS.md: never put a host in a step parameter. The gateway address is
# configuration, and a plan that carries one is a plan that has stopped being
# portable between a simulator and a robot.
#
# The predecessor of this scan was a substring test over json.dumps(plan):
# `"://" not in serialised and "127.0.0.1" not in serialised`. That is two
# spellings of one host out of many, and it is the two a reviewer thinks of
# first, which is exactly why it read as sufficient. A plan carrying
# {"hostname": "robot-7.local"}, or {"endpoint": "gateway:8766"}, or
# {"address": "192.168.1.40"}, or a bare "localhost", passed it without
# comment — and those are the shapes a drifting capability contract actually
# produces, because none of them look like a URL.
#
# So the check is structural instead: every dictionary key and every string
# value, at every depth of the exact plan document that is about to be sent.
HOST_KEY_NAMES = frozenset({
    "addr", "address", "authority", "base_url", "endpoint", "gateway",
    "gateway_url", "host", "hostname", "hosts", "ip", "ip_address", "netloc",
    "origin", "port", "server", "uri", "url",
})
# Compound keys — "robot_host", "gateway_endpoint", "callback_url" — are the
# common case, so the name is matched by fragment as well as in full.
HOST_KEY_FRAGMENTS = ("host", "url", "uri", "endpoint", "address", "netloc")
HOST_VALUE_FRAGMENTS = ("://", "localhost", "127.0.0.1", "0.0.0.0", "::1", ".local")
HOST_SCAN_MAX_DEPTH = 32


def host_findings(node, path="plan", depth=0):
    """Every host-bearing key or string value in `node`, as readable findings.

    Fail-closed in four directions, because a scanner that reports "nothing
    found" when it did not understand what it was looking at is worse than no
    scanner at all:

      * a key that is not a string is a finding, not a key to skip;
      * a value of a type this cannot walk is a finding, not an absence of one;
      * nesting past HOST_SCAN_MAX_DEPTH is a finding, since a plan that deep is
        not a plan and may be a cycle;
      * anything raised while walking is caught at the call site and turned into
        a finding.

    Returning a list rather than a bool is deliberate: the artifact records
    *what* was found, so a failure is diagnosable from report.json alone.
    """
    if depth > HOST_SCAN_MAX_DEPTH:
        return [f"{path}: nested deeper than {HOST_SCAN_MAX_DEPTH} levels"]
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if not isinstance(key, str):
                found.append(f"{path}: non-string key {key!r}")
                continue
            here = f"{path}.{key}"
            lowered = key.lower()
            if lowered in HOST_KEY_NAMES:
                found.append(f"{here}: key names a host or an address")
            else:
                for fragment in HOST_KEY_FRAGMENTS:
                    if fragment in lowered:
                        found.append(f"{here}: key contains {fragment!r}")
                        break
            found.extend(host_findings(value, here, depth + 1))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            found.extend(host_findings(value, f"{path}[{index}]", depth + 1))
    elif isinstance(node, str):
        lowered = node.lower()
        for fragment in HOST_VALUE_FRAGMENTS:
            if fragment in lowered:
                found.append(f"{path}: value contains {fragment!r}")
    elif node is None or isinstance(node, (bool, int, float)):
        pass
    else:
        found.append(f"{path}: value of type {type(node).__name__} cannot be walked")
    return found


# The variable the sourced file used to carry the bearer token. This package's
# own name is tried first; the rest are names the runtime has used, and the
# search fails loudly rather than sending an empty Authorization header.
TOKEN_ENV_CANDIDATES = (
    gateway.TOKEN_ENV, "FLYTO_ROBOTICS_TOKEN", "FLYTO_GATEWAY_TOKEN",
    "FLYTO_ROBOT_GATEWAY_TOKEN", "FLYTO_DELIVERY_TOKEN", "DELIVERY_TOKEN",
    "GATEWAY_TOKEN",
)
token_env = next(
    (name for name in TOKEN_ENV_CANDIDATES if (os.environ.get(name) or "").strip()),
    None,
)
if token_env is None:
    die("the sourced gateway environment defines no recognised bearer-token variable")
os.environ[gateway.TOKEN_ENV] = os.environ[token_env].strip()

# The address is configuration. If the runtime's own environment names it, that
# is the authority; otherwise the loopback default this script was given.
gateway_url = (os.environ.get(gateway.GATEWAY_URL_ENV) or "").strip() or fallback_url
os.environ[gateway.GATEWAY_URL_ENV] = gateway_url

# A robot id we disagree with is a mismatch to report, not to paper over.
runtime_robot = (os.environ.get(gateway.ROBOT_ID_ENV) or "").strip()
if runtime_robot and runtime_robot != robot:
    die(f"the runtime names robot {runtime_robot!r} but this run targets {robot!r}")
os.environ[gateway.ROBOT_ID_ENV] = robot

try:
    plan = plan_for_step(module_id, {"distance_m": distance_m, "speed": speed}, robot_id=robot)
except Exception as exc:  # noqa: BLE001 - PlanBuildError, or a drift that renamed it
    die(f"this package refused to build the plan: {type(exc).__name__}: {exc}")
if plan is None:
    die(f"{module_id} is not a step this package maps")

# The safety properties, asserted on the exact document about to be sent rather
# than on a rebuilt copy of it.
final_step = plan["steps"][-1]
first_step = plan["steps"][0]

# The host scan runs on that same document, before anything is posted. An
# exception from the walk is a finding, not a pass: the one case where the
# scanner does not know what it is looking at must not be the case that clears
# the plan.
try:
    plan_host_scan = host_findings(plan)
except Exception as exc:  # noqa: BLE001 - an unwalkable plan is not a clean plan
    plan_host_scan = [f"plan: the host scan raised {type(exc).__name__}: {exc}"]

request = run_request(
    plan,
    request_id=f"verify-{uuid.uuid4().hex[:12]}",
    requested_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
)

evidence = {
    "module_id": module_id,
    "token_env_var": token_env,
    "gateway_url": gateway_url,
    "plan_contract_version": plan.get("contract_version"),
    "expected_plan_contract_version": PLAN_CONTRACT_VERSION,
    "request_contract_version": request.get("contract_version"),
    "expected_request_contract_version": PLAN_RUN_REQUEST_CONTRACT_VERSION,
    "plan_id": plan.get("plan_id"),
    "robot_id": plan.get("robot_id"),
    "request_id": request.get("request_id"),
    "step_count": len(plan["steps"]),
    "first_step_capability": first_step.get("capability"),
    "first_step_arguments": first_step.get("arguments"),
    "final_step_id": final_step.get("step_id"),
    "final_step_capability": final_step.get("capability"),
    "plan_terminates_in_safe_stop": final_step.get("capability") == "safe_stop",
    "plan_host_scan_findings": plan_host_scan,
    "plan_host_scan_depth_limit": HOST_SCAN_MAX_DEPTH,
    "plan_contains_no_host": plan_host_scan == [],
}

# Refused here, before the gateway ever sees it. Recording the finding and
# posting anyway would let a plan that names a host move a robot, and leave the
# aggregate to disapprove of it afterwards.
if plan_host_scan:
    die("the plan carries a host, which AGENTS.md forbids: "
        + "; ".join(plan_host_scan), **evidence)

try:
    session = gateway.start_plan(request)
except gateway.GatewayError as exc:
    die(f"{type(exc).__name__}: {exc}", **evidence)

session_id = str(session.get("session_id") or session.get("id")
                 or session.get("delivery_id") or "").strip()
if not session_id:
    die("the gateway returned no session id", **evidence)

# What the gateway below actually calls a mission that finished.
#
# It reports MissionState.COMPLETED, which arrives here as "completed". An
# earlier draft required "succeeded" and nothing else, so a real mission that
# ran to completion was read as a failure — the verifier would have failed a
# passing exhibition and sent someone hunting a defect in the plan contract that
# was never there.
#
# The set is exact and closed, not a prefix or a substring test. "completed" and
# "succeeded" are the two spellings of terminal success; every other state the
# gateway can report — running, failed, cancelled, aborted, timed_out — is not
# one, and a state this set does not name is not a success just because it is
# unfamiliar.
TERMINAL_SUCCESS_STATES = frozenset({"completed", "succeeded"})

final = gateway.await_session(session_id, timeout_seconds=timeout)
state = str(final.get("state") or final.get("status") or "").lower()
timed_out = bool(final.get("timed_out"))

print(json.dumps({
    **evidence,
    "ok": True,
    "session_id": session_id,
    "session_state": state,
    "terminal_success_states": sorted(TERMINAL_SUCCESS_STATES),
    "session_timed_out": timed_out,
    "session_terminal_success": state in TERMINAL_SUCCESS_STATES and not timed_out,
}))
PY

MISSION_SH="${STAGE}/mission.sh"
cat >"${MISSION_SH}" <<'SH'
#!/usr/bin/env bash
# The wrapper exists for one reason: the runtime's gateway environment file
# holds shell `export` assignments, so it has to be sourced by a shell, in the
# guest, once — and the sourcing must not be traced, echoed or logged anywhere.
#
# This heredoc is quoted, so every line below is written verbatim and every
# expansion happens in the guest. That is the point for $HOME: the file lives
# under the *guest's* home directory.
set -euo pipefail
set +x
GATEWAY_ENV="$HOME/.local/share/flyto-robot-gazebo/runtime/gateway.env"
if [ ! -r "${GATEWAY_ENV}" ]; then
  printf '%s\n' '{"ok": false, "error": "the guest gateway environment file is not readable"}'
  exit 0
fi
set -a
# shellcheck source=/dev/null
. "${GATEWAY_ENV}"
set +a
export FLYTO_VERIFY_SRC="${FLYTO_VERIFY_ROOT}/src"
exec python3 "${FLYTO_VERIFY_ROOT}/mission.py" "$@"
SH

bounded "${COPY_TIMEOUT}" -- limactl copy "${GZ_PROBE}" "${LIMA_INSTANCE}:${GUEST_DIR}/gz_probe.py" \
  || fail "could not stage the Gazebo probe"
bounded "${COPY_TIMEOUT}" -- limactl copy "${PROBE_SH}" "${LIMA_INSTANCE}:${GUEST_DIR}/probe.sh" \
  || fail "could not stage the Gazebo probe wrapper"
bounded "${COPY_TIMEOUT}" -- limactl copy "${MISSION}" "${LIMA_INSTANCE}:${GUEST_DIR}/mission.py" \
  || fail "could not stage the mission driver"
bounded "${COPY_TIMEOUT}" -- limactl copy "${MISSION_SH}" "${LIMA_INSTANCE}:${GUEST_DIR}/mission.sh" \
  || fail "could not stage the mission wrapper"
rm -rf "${STAGE}"

# The one and only path from this script to the read-only pose probe.
#
# All three modes — sample, hold, hold-from — go through here, because the guest
# runtime environment is the kind of thing that gets fixed in the one call site
# someone was debugging and left broken in the other two. The failure that costs
# is not the loud one: a `sample_pose` that works while `hold_window` still runs
# without `gz` produces a gate with samples: 0 and a run that blames the world.
# One helper is what makes "the probe runs under the runtime environment" a
# property of this script rather than of three call sites that agree today.
#
# Bounded, like every other external call here, and bounded by the caller: each
# mode knows its own wall budget and this helper does not guess one for it.
run_gz_probe() {
  local wall_bound="${1:?run_gz_probe needs a bound}"; shift
  bounded "${wall_bound}" -- limactl shell "${LIMA_INSTANCE}" -- \
    env "FLYTO_PROBE_ROOT=${GUEST_DIR}" bash "${GUEST_DIR}/probe.sh" "$@"
}

sample_pose() {
  run_gz_probe $((SAMPLE_TIMEOUT + 30)) \
    sample "${GZ_TOPIC}" "${GZ_MODEL}" "${SAMPLE_TIMEOUT}"
}

# Hold an anchor this run takes for itself: the cold-start gate.
hold_window() {
  local min_sim="$1" max_drift="$2" wall="$3"
  run_gz_probe $((wall + 60)) \
    hold "${GZ_TOPIC}" "${GZ_MODEL}" \
    "${SAMPLE_TIMEOUT}" "${min_sim}" "${max_drift}" "${wall}"
}

# Hold an anchor measured elsewhere: the stopped-pose proof, whose anchor must
# be the pose-end sample and not a pose taken later, after any coasting.
hold_window_from() {
  local min_sim="$1" max_drift="$2" wall="$3" anchor_sim="$4" anchor_x="$5" anchor_y="$6"
  run_gz_probe $((wall + 60)) \
    hold-from "${GZ_TOPIC}" "${GZ_MODEL}" \
    "${SAMPLE_TIMEOUT}" "${min_sim}" "${max_drift}" "${wall}" \
    "${anchor_sim}" "${anchor_x}" "${anchor_y}"
}

json_ok() {
  printf '%s' "$1" | python3 -c 'import json,sys
try:
    print("yes" if json.load(sys.stdin).get("ok") is True else "no")
except Exception:
    print("no")'
}

# One field out of a probe result, in a form the shell can compare. Floats go
# through repr(), which round-trips exactly, so the anchor handed back to the
# guest is bit-for-bit the pose that was sampled.
json_field() {
  printf '%s' "$1" | python3 -c 'import json, sys
try:
    doc = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
if not isinstance(doc, dict) or sys.argv[1] not in doc:
    raise SystemExit(1)
value = doc[sys.argv[1]]
if isinstance(value, bool):
    print("true" if value else "false")
elif value is None:
    raise SystemExit(1)
elif isinstance(value, float):
    print(repr(value))
else:
    print(value)' "$2"
}

# ---------------------------------------------------------------------------
# 3. The cold-start physics gate, before the start sample and before the
#    mission. See the constants above for why it is stated in simulation time.
# ---------------------------------------------------------------------------
log "holding one anchor for ${PHYSICS_GATE_MIN_SIM_S}s of simulation time (bounded ${PHYSICS_GATE_WALL_TIMEOUT} wall seconds)"
GATE_JSON="$(hold_window "${PHYSICS_GATE_MIN_SIM_S}" "${PHYSICS_GATE_MAX_DRIFT_M}" \
                         "${PHYSICS_GATE_WALL_TIMEOUT}")" \
  || fail "the physics gate did not complete"
printf '%s\n' "${GATE_JSON}" >"${OUT_DIR}/physics-gate.json"
[ "$(json_ok "${GATE_JSON}")" = "yes" ] \
  || fail "the world never held still for ${PHYSICS_GATE_MIN_SIM_S}s of simulation time; see physics-gate.json"
log "physics gate satisfied"

# ---------------------------------------------------------------------------
# 4. Start, mission, end.
# ---------------------------------------------------------------------------
START_JSON="$(sample_pose)" || fail "could not sample the world pose before the mission"
printf '%s\n' "${START_JSON}" >"${OUT_DIR}/pose-start.json"
[ "$(json_ok "${START_JSON}")" = "yes" ] || fail "the start pose sample is not usable; see pose-start.json"

log "posting the step-built plan through this package's gateway client"
MISSION_JSON="$(bounded $((MISSION_TIMEOUT + 90)) -- limactl shell "${LIMA_INSTANCE}" -- \
  env "FLYTO_VERIFY_ROOT=${GUEST_DIR}" bash "${GUEST_DIR}/mission.sh" \
  "${STEP_MODULE_ID}" "${STEP_DISTANCE_M}" "${STEP_SPEED_MPS}" "${ROBOT_ID}" \
  "${GATEWAY_URL}" "${MISSION_TIMEOUT}")" \
  || fail "the mission driver did not complete"
printf '%s\n' "${MISSION_JSON}" >"${OUT_DIR}/mission.json"

END_JSON="$(sample_pose)" || fail "could not sample the world pose after the mission"
printf '%s\n' "${END_JSON}" >"${OUT_DIR}/pose-end.json"
[ "$(json_ok "${END_JSON}")" = "yes" ] || fail "the end pose sample is not usable; see pose-end.json"

# The stopped-pose window is anchored on the pose-end sample itself, so a coast
# between the mission and the start of the window is measured, not skipped over.
# Each extraction is fail-closed: an absent or unusable field ends the run here
# rather than handing the guest a blank anchor to hold against.
END_SIM_TIME="$(json_field "${END_JSON}" sim_time)" \
  || fail "the end pose sample has no usable sim_time; see pose-end.json"
END_X="$(json_field "${END_JSON}" x)" \
  || fail "the end pose sample has no usable x; see pose-end.json"
END_Y="$(json_field "${END_JSON}" y)" \
  || fail "the end pose sample has no usable y; see pose-end.json"

# ---------------------------------------------------------------------------
# 5. The stopped pose has to *stay* stopped. A single after-sample cannot tell
#    a stop from a slow coast; simulation time passing with no drift can.
# ---------------------------------------------------------------------------
log "confirming the stopped pose holds for ${STOPPED_GATE_MIN_SIM_S}s of simulation time"
STOPPED_JSON="$(hold_window_from "${STOPPED_GATE_MIN_SIM_S}" "${STOPPED_GATE_MAX_DRIFT_M}" \
                                 "${STOPPED_GATE_WALL_TIMEOUT}" \
                                 "${END_SIM_TIME}" "${END_X}" "${END_Y}")" \
  || fail "the stopped-pose check did not complete"
printf '%s\n' "${STOPPED_JSON}" >"${OUT_DIR}/stopped-pose.json"

# Checked here, immediately, and not only in the aggregate below. The window is
# the last thing this run measures and the one that says the robot is actually
# stopped; leaving its verdict to be discovered during aggregation means every
# step between here and there runs against a chassis that may still be moving,
# and the failure, when it finally arrives, arrives as one name in a list of
# invariants rather than as the thing that went wrong. The aggregate keeps its
# own copy of this check as defence in depth — two independent readers of one
# artifact, not one reader trusted twice.
[ "$(json_ok "${STOPPED_JSON}")" = "yes" ] \
  || fail "the stopped pose did not hold for ${STOPPED_GATE_MIN_SIM_S}s of simulation time within ${STOPPED_GATE_MAX_DRIFT_M}m of the pose the gateway reported stopping in; see ${OUT_DIR}/stopped-pose.json"

# ---------------------------------------------------------------------------
# 6. The aggregate report. `passed` is a conjunction, computed once, from the
#    recorded values — never asserted separately from what the artifact says.
# ---------------------------------------------------------------------------
FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 - "${OUT_DIR}" "${RUN_ID}" "${REPORT_CONTRACT}" "${MIN_DISPLACEMENT_M}" \
          "${MAX_DISPLACEMENT_M}" "${GZ_TOPIC}" "${GZ_MODEL}" "${STEP_MODULE_ID}" \
          "${STEP_DISTANCE_M}" "${STEP_SPEED_MPS}" "${STARTED_AT}" "${FINISHED_AT}" \
          "${SCRIPT_SHA256}" "${SOURCE_SHA256}" "${REPO_COMMIT}" "${LOWER_COMMIT}" \
          "${LIMA_INSTANCE}" "${ROBOT_ID}" "${LOWER_REPO}/${LOWER_VERIFIER}" \
          "${LOWER_RUN_ID_ENV}" "${VERIFIER_BEHAVIOR_REVISION}" <<'PY' || fail "the run did not satisfy every invariant"
import json, math, os, platform, sys

(out_dir, run_id, contract, lo, hi, topic, model, module_id, distance, speed,
 started_at, finished_at, script_sha, source_sha, repo_commit, lower_commit,
 lima_instance, robot_id, lower_verifier, lower_run_id_env,
 behavior_revision) = sys.argv[1:22]
lo, hi, distance, speed = float(lo), float(hi), float(distance), float(speed)

# The revision this aggregation was written for, spelled out here rather than
# taken on trust from the caller. The shell constant above is a claim about what
# the script does; this literal is what the aggregation knows how to write a
# report for. They are compared, and a mismatch ends the run before report.json
# is written.
#
# Being exact about what "before" means here, because the looser phrasing was
# wrong: this run's other artifacts already exist by now — the lower evidence,
# the physics gate, both pose samples, the stopped-pose window and the mission
# result were all written above, and none of them is retracted. What a mismatch
# refuses is the aggregate verdict, which is the only document that says the run
# passed. That is the one worth refusing: a report emitted under a revision this
# code was not written for would be evidence for a behaviour nobody checked.
EXPECTED_BEHAVIOR_REVISION = "fixed-anchor-process-quiescence.v1"
if behavior_revision != EXPECTED_BEHAVIOR_REVISION:
    sys.exit(
        "verifier behaviour revision mismatch: this aggregation was written for "
        f"{EXPECTED_BEHAVIOR_REVISION!r} but the script passed "
        f"{behavior_revision!r}; no report was written"
    )

read = lambda name: json.load(open(os.path.join(out_dir, name)))
lower = read("lower-evidence.json")
gate = read("physics-gate.json")
start = read("pose-start.json")
end = read("pose-end.json")
stopped = read("stopped-pose.json")
mission = read("mission.json")

poses_ok = start.get("ok") is True and end.get("ok") is True
displacement = None
if poses_ok:
    displacement = math.hypot(end["x"] - start["x"], end["y"] - start["y"])

invariants = {
    # The layer below was retested by this run, and said so in its own words.
    "lower_layer_verified": lower.get("passed") is True,
    # The world was stepping and still before anything was measured.
    "physics_gate_satisfied": gate.get("ok") is True,
    "world_pose_sampled": poses_ok,
    # The plan is this package's, built now, not a hand-authored stand-in. The
    # `is not None` half matters: two absent fields compare equal, and a
    # mission that died before building anything would otherwise pass this.
    "plan_built_by_this_package": (
        mission.get("plan_contract_version") is not None
        and mission.get("plan_contract_version")
        == mission.get("expected_plan_contract_version")
    ),
    "request_contract_matches": (
        mission.get("request_contract_version") is not None
        and mission.get("request_contract_version")
        == mission.get("expected_request_contract_version")
    ),
    "final_step_is_safe_stop": mission.get("final_step_capability") == "safe_stop",
    "plan_contains_no_host": mission.get("plan_contains_no_host") is True,
    # The gateway ran it to a terminal success, not to a timeout we gave up on.
    "gateway_terminal_success": mission.get("session_terminal_success") is True,
    "gateway_did_not_time_out": mission.get("session_timed_out") is False,
    # It moved, measurably, in the simulator's own frame.
    "displacement_is_finite": displacement is not None and math.isfinite(displacement),
    "displacement_in_window": displacement is not None and lo <= displacement <= hi,
    # And then it stayed where it stopped.
    "stopped_pose_is_stable": stopped.get("ok") is True,
}

report = {
    "contract_version": contract,
    "run_id": run_id,
    "passed": all(invariants.values()),
    "scope": "Gazebo simulation only; this is not physical-hardware evidence",
    "provenance": {
        "started_at": started_at,
        "finished_at": finished_at,
        "host_platform": platform.platform(),
        "repo_commit": repo_commit,
        "lower_repo_commit": lower_commit,
        "verifier_sha256": script_sha,
        # What the verifier *does*, as distinct from the bytes it is made of.
        # verifier_sha256 changes when a comment is reflowed; this does not.
        "verifier_behavior_revision": behavior_revision,
        "package_source_sha256": source_sha,
        "lima_instance": lima_instance,
        "gateway_robot_id": robot_id,
        "lower_verifier": lower_verifier,
        "lower_run_id_env": lower_run_id_env,
        "token_env_var": mission.get("token_env_var"),
        "gateway_url": mission.get("gateway_url"),
        "secrets_recorded": "none; the bearer token is sourced inside the guest and never leaves it",
    },
    "lower_layer": lower,
    "step": {
        "module_id": module_id,
        "commanded_distance_m": distance,
        "commanded_speed_mps": speed,
        "plan_id": mission.get("plan_id"),
        "robot_id": mission.get("robot_id"),
        "request_id": mission.get("request_id"),
        "plan_contract_version": mission.get("plan_contract_version"),
        "request_contract_version": mission.get("request_contract_version"),
        "step_count": mission.get("step_count"),
        "first_step_capability": mission.get("first_step_capability"),
        "first_step_arguments": mission.get("first_step_arguments"),
        "final_step_id": mission.get("final_step_id"),
        "final_step_capability": mission.get("final_step_capability"),
        # What the recursive host scan found, not merely whether it found
        # anything: a failure has to be diagnosable from this file alone.
        "plan_host_scan_findings": mission.get("plan_host_scan_findings"),
        "plan_host_scan_depth_limit": mission.get("plan_host_scan_depth_limit"),
    },
    "gateway_session": {
        "session_id": mission.get("session_id"),
        "state": mission.get("session_state"),
        "terminal_success_states": mission.get("terminal_success_states"),
        "timed_out": mission.get("session_timed_out"),
        "error": mission.get("error"),
    },
    "physical_evidence": {
        "source": "gazebo.world.pose.info",
        "topic": topic,
        "model": model,
        "note": "world pose, not odometry; nothing on the mission path writes here",
        "physics_gate": gate,
        "start": {k: start.get(k) for k in ("sim_time", "x", "y")},
        "end": {k: end.get(k) for k in ("sim_time", "x", "y")},
        "displacement_m": displacement,
        "window_m": {"min": lo, "max": hi},
        "stopped_pose": stopped,
    },
    "invariants": invariants,
}

with open(os.path.join(out_dir, "report.json"), "w") as handle:
    json.dump(report, handle, indent=2)
    handle.write("\n")

if not report["passed"]:
    failed = sorted(name for name, held in invariants.items() if not held)
    sys.exit("failed invariants: " + ", ".join(failed))
print(f"displacement {displacement:.4f} m; every invariant passed")
PY

log "PASS — report at ${OUT_DIR}/report.json"
