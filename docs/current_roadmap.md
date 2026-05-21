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

- **Native subgraphs / graph-as-node**: add child run state, child trace
  preservation, interrupt bubbling, and resume back into the child workflow.
  Wrapper artifacts currently execute as deployments and return run status;
  true graph-as-node outcome propagation belongs here.
- **Async parallel foreach**: add explicit scheduling, reducer/merge semantics,
  and failure policy. Do not model this as plain parallel calls over sync
  handlers.
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

Frame stress points to solve before either feature:

- `RunState.current_frame_id` currently models one active execution cursor.
  Parallel foreach likely needs multiple runnable child frames.
- `ExecutionFrame.metadata` currently carries ad hoc foreach data. Subgraphs and
  parallel foreach should get typed frame payloads or strongly bounded helper
  accessors before metadata grows more meanings.
- Subgraph frames need child workflow identity/version/deployment binding, not
  just a generic metadata dictionary.
- `RunState.current_node_id` duplicates the current frame's node id for
  convenience. Any multi-frame scheduler must either keep that as a selected
  cursor or replace it with an explicit scheduling view.

## Why This Order

The MCP workflow authoring path is now usable enough for real testing. The next
bottleneck is runtime/platform correctness: resumable child execution,
parallel scheduling, persistent run history, and protocol-native progress
reporting. Those pieces should come before adding more high-level authoring
sugar.
