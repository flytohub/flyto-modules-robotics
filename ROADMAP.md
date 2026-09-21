# Roadmap

## Near term

1. Keep the three named authoring steps compatible with the current
   `flyto-core` registry and builder.
2. Add a generic `robotics.command` authoring step only if its capability and
   parameter schema can be supplied by an approved external adapter without
   weakening the named Move / Turn / Stop experience.
3. Add simulator-backed acceptance through the same external adapter contract
   used by physical robots. Simulator-specific control paths are not allowed.
4. Confirm the three named steps on the real Flyto2 builder canvas.

## Later

- Evaluate MHS / ROS 2 / Nav2 / Open-RMF adapters as interchangeable external
  execution backends.
- Decide whether preview metadata may be refreshed from a cached approved
  adapter catalog while remaining usable offline.

## Explicitly out of scope

- Robot-local Flyto2 runtime.
- Pi job runner.
- Direct browser-to-robot WebSocket control.
- Hard-coded gateway URLs.
- ROS, serial or motor control in this package.
- Treating executor success as mission completion.
