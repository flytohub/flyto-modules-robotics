# flyto-modules-robotics

Robot capabilities for Flyto2, contributed through `@register_module` alone.

This package is the proof that Flyto2 needs no robot-specific platform code. A
robot SDK plugs in the same way any other provider does: one
`@register_module` per capability, each carrying `provides_capability` and a
declared capability contract. Flyto2 Core, Cloud and the builder read those
declarations as data. Nothing in them knows what a robot is.

## How a robot plugs in

```python
@register_module(
    module_id="robotics.advance",
    provides_capability="motion.advance",
    params_schema={
        "distance_m": {"type": "number", "min": 0.05, "max": 2.0, "unit": "m", "required": True},
        "speed_mps": {"type": "number", "min": 0.02, "max": 0.25, "unit": "m/s", "default": 0.12},
    },
    contract={
        "schema": "flyto.capability-contract.v1",
        "actuates": True,
        "safety_class": "movement",
        "requires_safe_stop": True,
        "cancellable": True,
        "idempotent": True,
        "effects": ["position.changed"],
        "requires": ["observation.fresh", "safety-basis.met"],
        "evidence": [{
            "kind": "displacement",
            "observe": "pose",
            "phases": ["before", "after", "settled"],
            "measure": {"op": "along", "fields": ["x", "y"], "heading_field": "yaw"},
            "expect": {"argument": "distance_m", "scale": 1},
            "tolerance": {"absolute": 0.03, "relative": 0.3},
            "settle": {"max_drift": 0.02},
        }, ...],
    },
    concurrent_safe=False,
    timeout_ms=180000,
)
class Advance(CapabilityStep): ...
```

That is the whole integration. The rows live in
`src/flyto_modules_robotics/capabilities.py` and the decorators in
`src/flyto_modules_robotics/modules.py`.

1. **Discovery.** `pyproject.toml` declares the `flyto.modules` entry point
   `robotics = flyto_modules_robotics:register_all`. flyto-core's plugin
   discovery calls it, and the seven steps appear in the builder and in Core's
   capability manifest. A Flyto2 install without this package stays pure
   software.
2. **Contract.** Each step declares what it does as data
   (`flyto.capability-contract.v1`): whether it actuates, its safety class,
   whether it needs a safe stop, whether it can be cancelled, whether a retry
   repeats the effect, and what evidence proves it worked. Parameter bounds
   are the step's `params_schema` `min`/`max`/`unit`.
3. **Execution.** Steps run on the AI Space execution host, not on the robot.
   The host injects an opaque dispatcher into the step context; the step hands
   it `{resource_id, capability_id, arguments}`, and the dispatcher calls the
   [flyto-robotics](https://github.com/flytohub/flyto-robotics) Generic ROS 2
   adapter, which speaks standard ROS 2 to the robot. Without that dispatcher a
   step only declares the request it would make.

Nothing from Flyto2 runs on the robot. It runs its standard ROS 2 stack and
nothing else.

```text
Builder / Space task
      |  robotics.advance {distance_m: 0.4}
      v
AI Space execution host (Flyto2 Desktop)
      |  flyto-core runs the step -> host dispatcher
      |  {resource_id, capability_id: motion.advance, arguments}
      v
flyto-robotics Generic ROS 2 adapter (on the host)
      |  standard ROS 2 action / topic
      v
robot (stock ROS 2, no Flyto2 software)
```

## Capabilities

| Step | Provides | Parameters (bounds) | Contract |
|---|---|---|---|
| `robotics.advance` | `motion.advance` | `distance_m` 0.05–2.0 m (required), `speed_mps` 0.02–0.25 m/s (default 0.12) | actuates, movement, safe stop, cancellable; evidence: travel along the starting heading within max(0.03 m, 30%) of `distance_m`, settle ≤ 0.02 m, heading held within 0.15 rad |
| `robotics.retreat` | `motion.retreat` | `distance_m` 0.05–2.0 m (required), `speed_mps` 0.02–0.20 m/s (default 0.10) | same as advance, expecting backward travel (`scale: -1`) |
| `robotics.rotate` | `motion.rotate` | `yaw_radians` −π..π (required, signed) | actuates, movement, safe stop, cancellable; evidence: signed rotation within max(0.1 rad, 20%), position drift ≤ 0.05 m, settle ≤ 0.02 m |
| `robotics.halt` | `motion.halt` | none | actuates, controlled; it is the stop itself, so no safe stop and not cancellable |
| `robotics.navigate` | `motion.navigate` | `x`, `y` −1000..1000 m (required), `yaw_radians` −π..π | actuates, movement, safe stop, cancellable; requires LiDAR clearance and a localised map |
| `robotics.observe` | `vision.observe` | none | read only: one camera photo |
| `robotics.map` | `sensing.map` | none | read only: the occupancy map built so far |

Parameters and bounds are the adapter's own declared arguments
(`generic_ros2_adapter.ARGUMENTS` in flyto-robotics), and a test pins them
equal. A value outside them is refused, never clamped, so the builder never
accepts a step the adapter is known to reject. The evidence tolerances are the
ones Cloud has judged motion with since 2026-10-02, and the suite runs
flyto-core's own `judge` over them against a transcription of Cloud's check
(fixed cases plus 2,000 seeded random motions per capability): every verdict
is the same.

## Safety invariants, and where each is enforced

| Invariant | Enforced by |
|---|---|
| Out-of-bounds arguments are refused, never clamped | This package, on the canvas (`validate_params`) and again before dispatch; the adapter re-checks its declared bounds |
| Only the host can execute; workflow data cannot forge that authority | The dispatcher must be a host type marked `_flyto_runtime_opaque` (checked here and in flyto-core's `capability.invoke`) |
| One commanded resource per job, and only approved capabilities | The host dispatcher (flyto-cloud `local/external_capability_dispatch.py`) refuses any other resource or a capability outside the job's allowlist |
| Motion needs fresh odometry and a safety basis: LiDAR clearance ≥ 0.35 m, or a declared present operator with tighter limits | The adapter's motion preflight (flyto-robotics) |
| A timeout or failure ends in a safe stop | The host dispatcher cancels the call and commands the adapter's safe stop |
| A retry never repeats an effect | The adapter keeps each call's result by call id (`idempotent: true`) |
| Physical and simulated robots are not confused | The adapter refuses motion when the ROS graph is not the configured deployment mode |
| Success means the effect was observed, not that a call returned | Cloud judges the declared evidence against the host's before / after / settled poses |
| No Flyto2 software runs on the robot | This package imports no ROS and opens no socket; the robot runs stock ROS 2 |

## Installation

```bash
pip install "flyto-modules-robotics[core]"
```

Install it on the AI Space execution host, never on the robot. The package has
no hard dependencies. The `core` extra states the floor that understands
`contract=` (`flyto-core>=2.35.0`). With an older flyto-core the steps still
register, without their contracts, and one warning says so. Without flyto-core
at all, `register_all` logs and returns; the pure request API still imports.

## API

```python
from flyto_modules_robotics import capability_request_for_step

capability_request_for_step("robotics.rotate", {"yaw_radians": -1.57}, resource_id="tb3-lab")
# {"contract_version": "flyto.capability-request.v1", "resource_id": "tb3-lab",
#  "capability_id": "motion.rotate", "arguments": {"yaw_radians": -1.57}}
```

`SPECS` lists every capability row (identity, `params_schema`, contract).

## Configuration

None. There is no robot hostname, gateway, credential or adapter address in
this package or in any step parameter. The control plane chooses the execution
host; the host chooses the adapter.

## Testing

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
ruff check src tests
flyto-index verify . --strict
```

No robot, simulator or flyto-core is needed. The suite validates every
contract against the v1 rules (a vendored copy, and flyto-core's own
`validate_contract` and `judge` when flyto-core 2.35.0+ is installed), pins
parameters and bounds to the adapter's table, checks the declared evidence
reproduces Cloud's verdicts, and exercises the dispatch, declare-only and
refusal paths. A real flyto-core registry run is included
when flyto-core is installed. Physical robot acceptance is a separate step.

## Development

Adding a capability: see `workflows/add-a-capability.md`. Keep the package
pure: no ROS imports, no network, no execution-host selection. Update the
project-memory files when a boundary changes.

## Release

Not yet published to PyPI. The repository contains a Trusted Publishing
workflow for an explicit release decision.

## License

Apache-2.0. See `LICENSE`.
