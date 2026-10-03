# Adding a capability

A capability is one row and one decorator. Nothing outside this package
changes.

1. **Start from the adapter.** The flyto-robotics adapter must already declare
   the capability in `generic_ros2_adapter.ARGUMENTS`. Copy its argument names,
   bounds and units exactly; never invent bounds that disagree with it.
2. **Add the row in `capabilities.py`.** `params_schema` carries the bounds as
   `min`/`max`/`unit`. Write the `flyto.capability-contract.v1` contract: safety
   class and safe-stop/cancel flags equal the adapter's
   `adapter_contract._CAPABILITY_METADATA`; evidence only if the host reports
   an observation a v1 measure op can compare.
3. **Register it in `modules.py`** with one `@register_module(...)` carrying
   `provides_capability` and the contract.
4. **Pin it in tests.** Add the adapter arguments to the table in
   `tests/test_capabilities.py`; the contract must pass `contract_rules.py`.
5. **Run the suite.** No test may need a robot.
