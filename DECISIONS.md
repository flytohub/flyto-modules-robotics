# Decisions


## 2026-09-21 — Robot execution is external; this package is authoring-only

Decision: `flyto-modules-robotics` no longer owns a robot-local HTTP client,
Pi runner contract, localhost gateway default, or Gazebo lower-runtime verifier.
It registers bounded authoring steps and produces transport-neutral plan
declarations. A separate adapter is the only component allowed to translate
those declarations into ROS 2, Nav2, Open-RMF, a simulator, or another machine
runtime.

Reason: the Flyto2 Space Task runtime already owns capability approval,
permission, resource binding, evidence and verification. Keeping a second
robot-local execution path in this package duplicated authority and made the
same workflow depend on where the code happened to run. Simulator and physical
robots must use the same adapter boundary.

This decision supersedes the transport portions of the 2026-08-05 and
2026-08-06 decisions below. Their historical rationale is retained for
provenance; the current architecture is the 2026-09-21 decision.


## 2026-08-05 — Hardware arrives as an optional package, not as a flyto-core module

Decision: robot steps live in this separate, optionally installed package,
discovered through `flyto-core`'s existing `flyto.modules` entry point.

Reason: two constraints together force it. Hardware must not enter `flyto-core`,
which is the software execution engine; and commands must be authorable in the
builder, whose available steps come from `flyto-core`'s module registry. An
optional plugin is the only shape that satisfies both. `flyto-core` documents this
entry point for exactly this purpose and uses it for its own `community` modules.

## 2026-08-05 — A step posts a plan over loopback rather than calling a library

Decision: a step builds a plan and posts it to the robot's own gateway; it never
imports `flyto-robotics` or touches ROS.

Reason: `rclpy`'s init and shutdown are process-global, so a long-running
workflow executor cannot host them safely. More importantly, a caller that died
mid-mission would leave nothing to stop the robot, while the gateway is a service
with signal handling that sends the final zero-velocity stop. Running out of
process is the point of the hop.

## 2026-08-05 — The gateway address is configuration, not a parameter

Decision: `FLYTO_ROBOTICS_GATEWAY_URL`, defaulting to loopback. No step takes a
host.

Reason: the job was already dispatched to a device, so the step runs on the robot
it drives. A host in a workflow would bind it to one machine — the same
duplication the capability model exists to remove, wearing a URL instead of a
device id. A test asserts no plan ever contains one.

## 2026-08-06 — A step declares motion; the robot's runner performs it

Decision: `modules.py` never posts to a gateway. It builds a plan, names the
device that must carry it out, and returns that as the job payload.

Reason: these modules register into `flyto-core`, and `flyto-core` runs on the
worker and the desktop — not on the robot. The first version posted to
`127.0.0.1:8766`, which is correct only if the code runs on the Pi. On a worker
that address is the container's own loopback, so the request would either fail
or find something else listening. Thirty-six tests passed against that design
because every one of them assumed the module ran on the robot.

Reversal of the transport half of the 2026-08-05 entry above. The plan format,
the bounds and the address-is-configuration rule are unchanged; only who sends
it moved.

## 2026-08-10 — A step declares one versioned capability, named apart from the plan's verbs

Decision: each module passes exactly one `provides_capability` to
`register_module` — `robotics.move` → `robotics.motion.move_relative@1`,
`robotics.turn` → `robotics.motion.turn_relative@1`, `robotics.stop` →
`robotics.safety.safe_stop@1` — and those identifiers are kept distinct from the
bare verbs `plan.py` writes into the executed plan.

Reason: the registry is what matches a device's declared abilities to an authored
step, so the mapping has to be one-to-one. Two steps sharing a capability would
make two different motions indistinguishable at match time, and a step declaring
none could be authored against a device that cannot carry it out. The version
suffix makes a device on an older contract a mismatch the builder can show,
rather than a robot that moves unexpectedly.

Keeping the two vocabularies apart is the other half of the decision, and the
tempting simplification is to merge them. It must not be merged: the registry
identifier is a *matching* name and the plan verb is an *executed* one. Merged,
renaming a registry contract for the builder's sake would change the bytes the
gateway runs — a documentation-shaped edit with a hardware-shaped consequence.

Proved on the actual sibling `flyto-core` 2.27.0 rather than on a stand-in: a
wheel of the current source, installed and consumed through the public
`flyto.modules` entry point, produced plugin owner `robotics` on all three
modules and a `ModuleRegistry.capabilities()` mapping of exactly these three
capabilities to exactly one module each. That proof registers and discovers; it
executes nothing. See STATE.md.

## 2026-08-11 — `register_all` swallows two named failures and re-raises the rest

Decision: `register_all` suppresses and logs an `ImportError` only when it is
*this package's own* `from core.modules…` statement failing to resolve, and only
when the error names one of `core`, `core.modules`, `core.modules.base` or
`core.modules.registry`. Every other `ImportError` — including one raised while
flyto-core's own module body runs, one from this package's `modules`, one from
the `register_module` decorator and one from `build_modules` — is re-raised
unchanged.

Reason: the previous `except ImportError: log and return` could not tell "no
flyto-core on this machine" from "flyto-core is installed and broke on the way
in". Those two need opposite handling. The first is the ordinary case on most
machines and must not take down the single loop in which flyto-core loads every
plugin. The second is *this plugin failing*, and only flyto-core's discovery
boundary can say which plugin failed and why — swallowed here it became a
warning that pointed at the wrong machine, on an installation that had a
perfectly good engine and three silently missing robot steps.

Naming alone is not enough to separate them, which is the subtle half. A
flyto-core that fails on its own `from core.modules.registry import …` arrives
here as an `ImportError` naming a module in the suppression set, and a name test
would relabel it "flyto-core is absent". So origin decides: the traceback is
walked, and anything in it that is neither this file nor the import machinery
means the import reached code behind the boundary and failed there, which is not
ours to answer for. The alternative considered and rejected was checking whether
flyto-core is importable first — `find_spec` imports the parent packages, so it
has exactly the same problem one level earlier.

## 2026-08-11 — Registration is repeated, never remembered

Decision: `register_all` rebuilds and re-registers all three modules on every
call. No module-level "already registered" flag, no cached class objects.

Reason: a host may clear its registry and rediscover — a hot reload, a
`discover_plugins(force=True)`, a second engine in one process. A process-global
flag would make the second pass a no-op and leave the fresh registry
permanently three steps short, with nothing raised and nothing logged, because
from the flag's point of view the work had been done. Repeating is safe because
the registry is keyed by module id: the same three ids arrive in the same order
carrying the same capability metadata, so a second pass is a replacement rather
than a duplicate. The plugin ownership stays the host's to assign — flyto-core
stamps it around the `register_all` call, so re-registering re-stamps whatever
the host is currently calling this plugin rather than pinning the first name it
ever had.

## 2026-08-13 — The lower execution catalog is verified before it is trusted

Decision: the authenticated gateway client reads `GET /v1/capabilities`, then a
standard-library-only parser requires the exact v1 fields, identities, types,
approval/executor invariants, finite bounds, registry revision, entry schema
hashes and overall contract hash. It returns frozen records containing tuples
and read-only mappings. Every rejection has the fixed message `capability
catalog invalid`.

Reason: authentication says who answered, not that a response is complete,
current, bounded or safe to turn into authoring constraints. Strict hashes and
shape checks preserve the lower registry as authority; immutability prevents a
validated schema from changing afterward. This decision only creates the
trusted consumer. It does not yet replace `plan.py` constants or register a
generic command.

## 2026-08-13 — Execution planning fails closed; preview compatibility is named

Decision: `plan_for_step` requires an immutable validated catalog by default and
derives the three named nodes' runtime arguments, bounds and defaults from it.
Missing capabilities, incompatible schemas, unsupported required arguments and
catalog-derived values outside bounds are errors. The old constant-based path is
available only as `preview_plan_for_step` or by the explicit
`require_trusted_catalog=False` compatibility request.

Runtime argument names are also lower-owned contract data. In particular,
`robotics.motion.move_relative@1` declares and consumes `speed`, so the derived
plan emits `speed`; this package does not translate it to a locally invented
alias.

Reason: a Pi runner must not turn a missing or changed lower contract into motion
using stale package constants. The lower catalog is planning authority and the
gateway still performs final enforcement. Keeping preview explicit preserves the
three offline canvas nodes without presenting their compatibility bounds as an
execution guarantee.
