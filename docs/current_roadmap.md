# Current Roadmap

This is the short active roadmap after the core type-shape cleanup and MCP
workflow authoring cleanup pass. It is based on both the current docs and the
implementation state.

## Completed Cleanup Pass

1. **Docs index and prune**
   - Current architecture docs are separated from historical plans and scratch
     notes.
   - The active roadmap now lives here instead of being scattered through older
     planning files.

2. **MCP workflow authoring UX**
   - The operator manual categorizes workflow tools into discovery, draft
     workspace, stateless draft, artifact/deployment, run/debug, and raw escape
     hatch groups.
   - List-style tools are more compact, while inspect/run tools carry the
     detailed payloads.

3. **Wrapper creation ergonomics**
   - Wrapper draft helpers can suggest state schema, input bindings, output
     bindings, default `ok` / `error` handling, and missing decisions.
   - The end-to-end runbook documents the wrapper path from capability
     discovery through deployment/run.

4. **Run and deployment story**
   - Deployment listing is summary-first, with dedicated inspection for detail.
   - `run_deployment` returns compact status by default and exposes trace slices
     through an explicit `trace_range`.
   - Dependency validation and error output remain part of the run path.

5. **Source inventory polish**
   - `list_sources` / `inspect_source` now present source-owned capabilities
     progressively.
   - Source inventory distinguishes external sources, local workflow-facing
     sources, docs/resources, and admin-only control surfaces.

## Runtime and Platform Roadmap

- Scheduler foundation decision record:
  [ADR 0001](./adr/0001-scheduler-foundation-before-concurrent-foreach.md).
- Concurrent foreach policy decision record:
  [ADR 0002](./adr/0002-concurrent-foreach-policy-and-barrier-commits.md).
- Native subgraph design spec:
  [2026-05-24 native subgraphs](./superpowers/specs/2026-05-24-native-subgraphs-design.md).
- **Native subgraphs / graph-as-node**: core has `SubgraphNode`, structural
  `WorkflowRef`, workflow-level outcomes plus explicit `EndNode` termination,
  authoring helpers (`subgraph_ref` / `WorkflowBuilder.subgraph`), and artifact
  reference conversion helpers. Core can now execute a prepared local child
  workflow through an isolated child scope/lineage, preserve its trace entries,
  map child output through the boundary, and route by the child's terminal
  outcome. Prepared child interrupts now bubble through a typed internal route
  and resume inside child scope while the public request identifies the parent
  subgraph boundary. The workflow platform now resolves non-interrupting saved
  child artifact refs into native prepared dependencies; descendant logical
  capabilities inherit the root deployment binding environment, and missing or
  cyclic saved children fail validation before a run starts. Wrapper helpers
  currently run child workflows as ordinary nodes; native
  `SubgraphNode` is now the graph-as-node path for prepared children.
  `WorkflowBuilder.prepare_subgraph()` and `WorkflowBuilder.resume()` make the
  local runnable/resumable path available without core-runtime plumbing.
  Saved interrupting artifacts can now pause and resume through
  `run_deployment`/`resume_run` for the duration of the MCP server process
  (in-memory only). Persisted resume across process restarts remains future
  work.
- **Concurrent foreach**: implemented in core with explicit scheduling,
  reducer/merge semantics, item error policy, async handler batching, and
  quiescent interrupt behavior. Remaining work is polish and future reuse of
  its barrier/lineage machinery by native subgraphs and fork/gather. Current
  lineage progress includes ordered `StateWrite` records, `LineageStateView`,
  foreach item `lineage_id`s, nested foreach lineage identity, root
  `RuntimeScope` / `LineageState` storage, scope-aware reads, and non-root write
  buffering. New concurrent foreach item writes are stored in
  `RunState.lineages`, while `ForeachBarrierState` keeps scheduling/result
  metadata and compatibility patches. Scope-root commits now apply to both the
  root workflow and prepared native child scopes through the explicit
  scope/lineage commit helper.
- **Persistent run history**: add a run store before adding stable `run_id`,
  `inspect_run`, or `read_run_trace(run_id, range)` APIs. Current traces are
  returned directly from immediate run responses.
- **Protocol-native long-running runs**: investigate MCP tasks/progress
  notifications for long-running workflow execution. Avoid inventing a custom
  "start" convention unless protocol-native behavior is insufficient.
- **Dynamic saved workflows as tools**: defer until the stable run/inspect
  surface is strong. Many MCP clients do not refresh tool lists reliably, so
  `wf.workflow.run_deployment` remains the dependable front door.
- **Dashboard/source controls**: future UI should consume the same source
  inventory and deployment metadata instead of reverse-engineering MCP tools.

Frame stress points remaining for native subgraphs and future fork/gather:

- `RunState.current_frame_id` remains the selected execution cursor even though
  concurrent foreach now schedules multiple child frames. Native subgraphs
  must preserve that cursor model while owning a nested child execution scope.
- `ExecutionFrame.metadata` has typed foreach access paths, but subgraphs still
  need typed child-workflow ownership and completion metadata rather than new
  ad hoc dictionary fields.
- Subgraph frames need child workflow identity/version/deployment binding, not
  just a generic metadata dictionary.
- `RunState.current_node_id` duplicates the current frame's node id for
  convenience. Any multi-frame scheduler must either keep that as a selected
  cursor or replace it with an explicit scheduling view.

## Why This Order

The MCP workflow authoring path is now usable enough for real testing. The next
bottleneck is runtime/platform correctness: durable resume/run history,
optional per-use-site child deployment overrides, and protocol-native progress
reporting. Concurrent foreach, native saved child execution, and process-local
interrupt resume now supply scheduler/lineage precedent. Those remaining pieces
should come before adding more high-level authoring sugar.
