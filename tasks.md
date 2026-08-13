# Tasks

- [x] Run the unit suite and record the real count — 222 passed in 0.23s via
      `/Users/chester/flytohub/flyto-ai/.venv/bin/python -m pytest -o pythonpath=src tests/ -q`
- [x] Run the bottom-up Gazebo verifier on the machine with the
      `flyto-robot-gazebo` Lima guest — passed, run `mrg-20260809T101631Z-79266`,
      displacement 0.3716104562185889 m, report SHA-256
      `a47186f33eb05a1c833185806cdbc5f6b0f522fb1b8691d011ed205be123e25d`
- [x] Fix the version contract drift and guard it — built wheel
      `flyto_modules_robotics-0.1.1-py3-none-any.whl` reports `0.1.1` from both
      `__version__` and `importlib.metadata`, guarded in the unit suite and in
      the built-wheel CI consumer check
- [x] **Verify the 2026-08-11 registration-boundary change** — accepted, not
      inferred from a review pass. Job `job_46d0f9c1892d458eb4e2cd9c` checked
      the official repository at implementation revision
      `039d29ae50c5f6b6558ee599b7d8e4958c733b564d60c5b42d2fe75236861a12` and
      recorded **232 passed** with strict route / Flyto Indexer verification
      accepted. Registration was exercised against a real `flyto-core` over two
      discovery cycles; both cycles discovered `robotics.move`, `robotics.turn`
      and `robotics.stop` with exactly the three declared capabilities. No
      module executed, nothing contacted.
- [x] **Route-validation job `job_e3c87cdd21c54c8f9e2e96c0` failed route
      validation and was not accepted.** Nothing it produced is evidence for
      any item here.
- [x] Mirror the accepted registration-boundary result into STATE.md "Last
      verification" — done. STATE.md now carries job
      `job_46d0f9c1892d458eb4e2cd9c`, implementation revision
      `039d29ae50c5f6b6558ee599b7d8e4958c733b564d60c5b42d2fe75236861a12`, the
      232-passed official repository check and the accepted strict route /
      Indexer verification, in both "The registration boundary" and "Last
      verification".
- [ ] **Revalidate physical motion (0.05 m, then 0.10 m) after the
      `flyto-robotics` tolerance fix**, once the area is safely cleared. The
      fresh preflight refused (left and closest 0.2039999962 m) and the robot is
      stopped. Gazebo evidence does not satisfy this.
- [x] Add a pure runner-facing named-plan API that requires the verified lower
      catalog, derives bounds/defaults from it and never implicitly falls back
      to the separately named legacy preview path (ROADMAP 1 contract slice)
- [ ] Add the generic `robotics.command` step (ROADMAP 2)
- [x] **Re-prove registration against the current `flyto-core` 2.27 line** —
      done. A wheel built from an isolated copy of the current source
      (`flyto_modules_robotics-0.1.1-py3-none-any.whl`, SHA-256
      `868805c58bf2dd08b35b0bafd136527cbe0cdbe80facca7eb22b308adc3ffb0b`) was
      installed and consumed by the actual sibling `flyto-core` 2.27.0 through
      the public entry point `robotics -> flyto_modules_robotics:register_all`.
      Plugin owner `robotics` on all three modules;
      `ModuleRegistry.capabilities()` returned exactly the three canonical
      capabilities, each mapped to its one module. No module executed, nothing
      contacted. Recorded in STATE.md.
- [ ] **Load the Flyto2 builder canvas** with this installed alongside a real
      `flyto-core` and confirm the three steps are visible and usable there. The
      2.27 consumer proof closed registration and capability discovery only; it
      says nothing about the canvas.
- [ ] Clear the setuptools license deprecation warning emitted by the isolated
      build (packaging metadata follow-up). It did not fail the build and did not
      affect registration; it is a packaging cleanup, not a defect in the plugin.
- [ ] Decide whether to publish to PyPI, and under which account. Nothing has
      been uploaded; 0.1.0 and 0.1.1 are local builds only.
