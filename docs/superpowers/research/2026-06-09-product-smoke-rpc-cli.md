# Product Smoke: MCP-Backed JSON-RPC CLI

Date: 2026-06-09

Historical note: this smoke captured older platform-source behavior. Current
deployments no longer need self-bindings such as `wf.std=wf.std` for built-in
platform sources, and current validation rejects explicit platform-source
bindings. The two rows below mentioning `wf.std=wf.std` are preserved as
historical output, not current guidance.

Target:

```powershell
wf --url http://127.0.0.1:8765/rpc ...
```

Server was already running when this smoke pass started.

## Summary

The remote CLI path is usable end-to-end:

- `wf status` reports remote target, sources, admin counts, registry availability,
  and capability samples.
- Source listing works.
- Direct `cap call` works for both built-in `wf.std` capabilities and upstream
  MCP-backed capabilities.
- Draft -> artifact -> deployment -> validate -> run -> inspect -> trace works
  through the JSON-RPC server.
- Deployment cleanup works.

## Commands Run

| Command | Result |
| --- | --- |
| `wf --url http://127.0.0.1:8765/rpc status` | OK; remote mode, 7 sources, 4 connections, registry available. |
| `wf --url ... source list --format compact` | OK; showed 4 MCP connections plus `wf.admin`, `wf.recipes`, `wf.std`. |
| `wf --url ... cap call wf.std.constant --input '{"value":"smoke constant"}'` | OK; output value echoed. |
| `wf --url ... cap call everything.default.echo --input '{"message":"smoke echo"}'` | OK; returned MCP content-block envelope. |
| `wf --url ... admin registry list` | OK; empty registry. |
| `wf --url ... draft create-from-capability smoke_ws_20260609 wf.std.constant ...` | OK; valid draft, high-confidence wrapper hints. |
| `wf --url ... draft validate smoke_ws_20260609` | OK; valid. |
| `wf --url ... draft inspect smoke_ws_20260609 --include-draft` | OK; full draft returned. |
| `wf --url ... draft save smoke_ws_20260609 --artifact smoke_artifact_20260609 --version 1 ...` | Historical: artifact saved and suggested `wf.std=wf.std`; current behavior should not suggest platform bindings. |
| `wf --url ... deploy save smoke_deploy_20260609 --artifact smoke_artifact_20260609 --version 1 --binding wf.std=wf.std` | Historical: accepted then; current validation rejects explicit platform bindings. |
| `wf --url ... deploy validate smoke_deploy_20260609` | OK; `status: runnable`. |
| `wf --url ... run start smoke_deploy_20260609 --input '{"value":"remote lifecycle smoke"}'` | OK; completed with expected output. |
| `wf --url ... run inspect run_7afdda9f958a4c258866192a78d1ef6b` | OK; compact completed run summary. |
| `wf --url ... run trace run_7afdda9f958a4c258866192a78d1ef6b --from 0 --limit 5` | OK; one trace frame with resolved input and state changes. |
| `wf --url ... admin auth list` | OK; empty auth list. |
| `wf --url ... deploy delete smoke_deploy_20260609` | OK; deployment deleted. |

## UX Gaps Found

1. `artifact inspect` takes `VERSION` as a positional argument, while nearby
   commands use `--version`. I first tried `artifact inspect <id> --version 1`
   and got a clean Typer error. This is not a crash, but it is inconsistent.

2. `cap call` for raw MCP tools returns the raw MCP content-block envelope. This
   is technically correct and already documented as a content-block boundary,
   but it is still user-visible friction for ordinary "just echo text" probes.

3. There is no CLI cleanup command for draft workspaces or artifacts. Smoke tests
   can delete deployments, but draft/artifact records remain unless the store is
   disposable or cleaned out of band.

## Suggested Follow-Ups

1. Add `--version` alias support for `wf artifact inspect` while keeping the
   positional form for compatibility.

2. Add explicit docs/examples for interpreting raw MCP content envelopes from
   `cap call`, or add a separate wrapper/extraction helper path. Do not silently
   flatten all content blocks.

3. Add safe cleanup commands:

   - `wf draft delete <workspace_id> --confirm`
   - `wf artifact delete <artifact_id> <version> --confirm`

   These should target stores only and should not delete deployments unless a
   separate explicit cascade option exists.
