# WfMcpService Remaining Responsibility Audit

Date: 2026-06-02

## Summary

`WfMcpService` is now mostly a compatibility coordinator. The major ownership
areas have moved into focused services:

- `ConnectionService`: connection registry, connection registration, config sync.
- `SourceCatalogService`: capability sources, catalog snapshots, source/resource/prompt inventory.
- `UpstreamTransportService`: adapters, auth, upstream reads/prompts/raw calls, catalog refresh.
- `WorkflowRuntimeService`: plan compilation and run/resume execution.
- `BrokerEventRecorder`: broker-local event recording and catalog change fanout.

The remaining class still has two kinds of code:

- Thin compatibility delegates that can stay until callers move to service/domain APIs.
- One meaningful mixed responsibility: local documentation resource/prompt handling before
  forwarding to upstream transport.

## Remaining Members

| Member | Current role | Classification | Recommendation |
| --- | --- | --- | --- |
| `__post_init__` | Wires focused services together and installs builtin/admin sources | Coordinator | Keep for now; eventually move construction to a factory/builder if HTTP/API frontends need the same bundle without `WfMcpService`. |
| `capability_sources` | Property returning `source_catalog.capability_sources` | Compatibility facade | Keep while `wf_api` operation context and tests use it; prefer direct `SourceCatalogService` in new internals. |
| `connections` | Property returning `connection_service.connections` | Compatibility facade | Keep for admin/CLI/tests; do not add new logic here. |
| `adapters` | Property returning `upstream.adapters` | Compatibility facade | Keep for config/server reload code; eventually expose adapter registration through `UpstreamTransportService`. |
| `register_connection` | Delegates to `ConnectionService` | Compatibility facade | Keep for old service callers; new broker internals should call `connection_service`. |
| `sync_connections_from_config` | Delegates to `ConnectionService` | Compatibility facade | Keep for `server/core.py` reload callback until that code depends on `ConnectionService` directly. |
| `register_adapter` | Delegates to `UpstreamTransportService` | Compatibility facade | Keep for config and tests; new code should call `upstream`. |
| `_tool_executor_for` | Delegates to `UpstreamTransportService` | Compatibility/private shim | Remove after confirming no callers outside tests/legacy paths need it. |
| `save_auth`, `load_auth` | Delegate to `UpstreamTransportService` | Compatibility facade | Keep until admin/control surfaces use upstream service directly. |
| `register_specs` | Delegates to `SourceCatalogService` with event fanout callback | Thin coordinator | Acceptable for now; later expose `source_catalog.register_specs(..., record_catalog_change_events=events.record_catalog_change_events)` through a smaller service bundle. |
| Catalog/source list/inspect methods | Delegate to `SourceCatalogService` | Compatibility facade | Keep while admin/MCP surfaces use `WfMcpService`; new code should call `source_catalog`. |
| `workflow_artifact_catalog_entry` | Calls pure `wf_artifacts.artifact_catalog_entry()` | Misplaced pure projection | Move this out of `WfMcpService`/operation context later; `wf_api` can call `wf_artifacts` directly or use a small artifact projection protocol. |
| `read_resource` | Handles local docs special-case, records event, else forwards upstream | Mixed real responsibility | Extract next into a focused resource/prompt access service. |
| `invoke_method`, `send_notification` | Lookup connection, forward upstream | Compatibility facade | Could move with resource/prompt access or leave as upstream delegates. |
| `render_prompt` | Handles local docs special-case, records event, else forwards upstream | Mixed real responsibility | Extract next with `read_resource`. |
| `refresh_connection_catalog` | Lookup connection, call upstream refresh with source/event callbacks | Thin coordinator | Could move to `UpstreamTransportService` if it accepts connection id + connection lookup, or stay as facade. Not as urgent as resources/prompts. |
| Runtime methods | Delegate to `WorkflowRuntimeService` | Compatibility facade | Keep while `wf_api` runtime adapter points through service; new internals should use `workflow_runtime`. |
| `list_events` | Delegates to `BrokerEventRecorder` | Compatibility facade | Keep for admin/tests; new code should call `events`. |
| `register_capability_source` | Directly mutates `source_catalog.capability_sources` | Compatibility facade | Replace implementation with `source_catalog.register_capability_source(source)` to make ownership explicit. |
| `_get_qualified_spec` | Delegates to `SourceCatalogService` | Compatibility/private shim | Keep only for tests/legacy paths; new code should call `source_catalog.get_qualified_spec`. |
| `_record_event`, `_record_catalog_change_events` | Delegate to `BrokerEventRecorder` | Compatibility/private shim | Remove when remaining `WfMcpService` methods stop needing local event helpers. |

## Best Next Slice

Extract a resource/prompt access service, tentatively named
`BrokerContentAccessService` or `ResourcePromptAccessService`.

Why this is next:

- `read_resource` and `render_prompt` are the last methods with real branching logic in
  `WfMcpService`.
- They combine three dependencies: `SourceCatalogService`, `ConnectionService`, and
  `UpstreamTransportService`.
- They also record local documentation events directly. That makes the boundary useful
  and testable, not just mechanical delegation.

Proposed ownership:

- `read_resource(qualified_name) -> dict[str, Any]`
- `render_prompt(qualified_name, arguments=None) -> dict[str, Any]`
- Optional: `invoke_method` and `send_notification` if the slice wants all
  connection-id-to-upstream forwarding in one place.

Keep out of scope for that slice:

- Catalog refresh. It has different semantics and should stay with upstream/catalog
  coordination until there is a clearer need.
- Workflow runtime methods. They are already clean delegates.
- `workflow_artifact_catalog_entry`. It is not broker content access; handle it in a
  separate small cleanup.

## Small Cleanup Before Or After Next Slice

These are safe, low-risk cleanups:

- Change `register_capability_source()` to delegate to
  `self.source_catalog.register_capability_source(source)` instead of mutating the dict.
- Move `workflow_artifact_catalog_entry()` out of `WfMcpService` if the `wf_api`
  operation context can call `wf_artifacts.artifact_catalog_entry()` directly.
- Add a docstring to `WfMcpService` itself stating that it is now a compatibility
  coordinator around focused broker services.

## Durable API Implication

This audit supports the durable API direction: most backend concerns are now behind
focused services. A future `wf_api`/HTTP server can compose these services directly
instead of depending on MCP tool handlers. The remaining blocker is not runtime
execution; it is choosing a durable service bundle/factory that owns process-local
stores, event recorder, connection service, source catalog, upstream transport, and
workflow runtime without requiring `WfMcpService` as the public object.
