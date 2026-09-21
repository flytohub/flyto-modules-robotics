# Contributing

Read `AGENTS.md`, `PROJECT.md`, `ARCHITECTURE.md`, `STATE.md` and
`DECISIONS.md` before changing this repository.

The production boundary is non-negotiable:

- workflow modules emit capability requests;
- execution-host placement belongs to AI Space / War Room;
- robots remain standard ROS 2 equipment;
- this package never imports ROS 2 or drives hardware;
- no workflow step carries a gateway URL, credential or execution host.

Before editing, inspect impact with Flyto Indexer. Before handing work off, run:

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
ruff check src tests
flyto-index verify . --strict
```

Do not weaken tests or verification thresholds to make a change pass.
