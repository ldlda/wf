# CLI / API Alignment Notes

## Context

`wf_api.WorkflowApiSurface` is now the shared workflow operation contract.
`WorkflowApi` implements it in-process, and `RpcWorkflowApiClient` implements it
by calling fixed JSON-RPC methods. The CLI now uses target-aware context for the
basic workflow lifecycle:

- capability list/inspect
- draft workspace list/inspect/create/patch/validate/save
- artifact list/inspect
- deployment list/inspect/save/validate/delete
- run start/inspect/trace/resume

This means `wf` can target either:

- `local`: same-process stores/runtime built from config
- `rpc_http`: a long-lived workflow server that owns its own stores/runtime

The target store is the authority. For example, `wf run resume` does not resume
"client-local" state when pointed at `--url`; it resumes the run persisted in the
server's run store.

## Current Boundary

```text
CLI command
  -> CliContext.handlers: WorkflowApiSurface
  -> WorkflowApi                  # local target
  -> RpcWorkflowApiClient         # rpc_http target
```

Server side:

```text
JSON-RPC request
  -> wf_transport_rpc_http methods_* module
  -> WorkflowServer.api: WorkflowApi
  -> wf_api domain service
  -> WorkflowOperationContext
```

The JSON-RPC transport is split by workflow domain. `RpcWorkflowApiClient`
remains one flat surface implementation, backed by a base transport plus
stateless domain mixins.

## Design Rules

- CLI commands should type against `WorkflowApiSurface` whenever they can work
  with local or remote targets.
- Use `load_local_cli_context_from_typer` only for commands that truly need
  same-process access to stores, config files, or non-surface internals.
- Remote clients should not infer workflow state from client-local config. The
  selected target owns persisted runs, deployments, artifacts, and draft
  workspaces.
- JSON-RPC methods remain fixed and dotted, such as `workflow.runs.resume`.
  Do not dynamically register saved workflows as JSON-RPC methods.
- Transport packages adapt calls. Workflow validation, resume policy, wrapper
  hints, and next actions stay in `wf_api`.

## Local-Only Audit Result

Audit result: no workflow lifecycle command imports
`load_local_cli_context_from_typer`. The capability, draft workspace, artifact,
deployment, and run command groups all load `CliContext.handlers:
WorkflowApiSurface`, so they can target either local or JSON-RPC HTTP.

The remaining non-lifecycle command groups are static/local by design for now:

- `wf docs`
- `wf schema`
- `wf explain`

`wf docs` and `wf schema` are currently empty Typer groups reserved for future
commands. `wf explain` reads the packaged explanation registry and does not need
workflow stores or remote server state. If these need remote behavior later,
decide whether they belong on `WorkflowApiSurface`, a sibling admin/docs
surface, or plain local CLI utilities.

## Next Slices

1. **Store-backed source registry**
   - Read-only source/admin operations are now available through JSON-RPC HTTP
     and `wf source list` / `wf source inspect`.
   - Read-only admin/config operations are now available through JSON-RPC HTTP
     and `wf admin connections`, `wf admin statuses`, and `wf admin events`.
   - Next source work is persistence for server-owned dynamic source changes.
   - Keep mutation out until the store-backed source registry is designed.

2. **Mutable source/admin commands**
   - Config can bootstrap sources, but server-owned dynamic source changes
     should persist through the store.
   - Keep source identity structural: source id, provider/account/profile, and
     concrete transport details should not be inferred from dotted display names.

3. **Transport sibling planning**
   - JSON-RPC over HTTP is the first transport.
   - If streaming/progress becomes important, add a WebSocket transport sibling
     rather than changing workflow semantics.
   - A future MCP server transport can expose the same server-owned
     `WorkflowApiSurface` plus any sibling admin/docs surfaces.

## Open Questions

- Source/admin and admin/config read-only operations currently live in `wf_api`
  as sibling surfaces. If mutation grows into a larger management domain, split
  that later instead of overloading `WorkflowApiSurface`.
- Should `wf schema` describe local CLI command payloads only, or query a remote
  server for supported method schemas?
- Should `wf docs` read packaged local docs, remote server docs, or both?
