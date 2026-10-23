# Step output: drop the legacy capture's bytes as well as the artifacts'

Owner: claude
Branch: claude/strip-capture-bytes
Date: 2026-10-04

## Confirmed defect fixed

PR #10 reduced `adapter_evidence.artifacts` in a step's output to kind, media
type, size and sha256, and its handoff said 1.1.0 keeps the photo's base64 out
of the step output. That held only behind Flyto2 Cloud's dispatcher, which pops
`capture` before the step sees the record. Behind flyto-core's
`CapabilityHost` the record's `adapter_evidence` is the adapter's verbatim, and
flyto-robotics 0.2.0 still sends the legacy `capture` beside `artifacts`, so
the step output carried the whole JPEG (`capture.data_base64`, up to 2 MB) or
the map's cells (`capture.cells_base64`, up to 4,000,000 cells). The #10
end-to-end test only checked the `artifacts` list, so it passed.

`_without_artifact_bytes` now also replaces `capture.data_base64` /
`capture.cells_base64` with `data_bytes`/`data_sha256` and
`cells_bytes`/`cells_sha256`. The dispatcher's own record is not modified.
The end-to-end test now asserts no `data_base64` anywhere in
`adapter_evidence`; it failed on the #10 code.

## Verified

- flyto-core origin/main (2.36.0 dev) installed in a scratch venv: 209 passed,
  including the CapabilityHost end-to-end test.
- Without flyto-core: 169 passed, 40 skipped.
- ruff 0.15.15 clean; `flyto-index verify . --strict` 20/0/0.

## Not verified

- No Desktop or Cloud run; no robot. MCP `task(action='validate')` not run
  (the MCP server is pinned to another repo).
