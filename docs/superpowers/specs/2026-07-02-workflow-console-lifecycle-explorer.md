# Workflow Console Lifecycle Explorer

Date: 2026-07-02

Status: Approved design. Implementation pending.

Related:

- [Workflow console, agent demo, and defense presentation](2026-07-01-workflow-console-agent-demo.md)
- [Workflow console foundation](2026-07-01-workflow-console-foundation-design.md)
- [Self-describing interrupt contracts](2026-07-01-self-describing-interrupt-contracts.md)
- [Current roadmap](../../current_roadmap.md)

## Goal

Add the first read-only lifecycle explorer to the Workflow Console. A user can
move from an artifact version to its deployments and runs, inspect a workflow
as a graph, and correlate a selected run with a bounded trace without reading
raw JSON.

The implementation is generic for stored workflows. The deterministic
`examples/lda_report_workflow/` case is the reference fixture and visual
acceptance case.

This slice does not mutate workflow state. Draft editing, run start/resume,
typed approval, autoplay, replay, the demo agent, and presentation routes remain
later work.

## User Journey

After connecting to a loopback workflow server, the user can:

1. select **Lifecycle**;
2. choose an artifact and version;
3. inspect its title, outcomes, required source bindings, and workflow plan;
4. choose a deployment that references that artifact;
5. inspect bindings and validation/readiness state;
6. choose a run of that deployment;
7. inspect status, output, interrupt data, and bounded trace frames;
8. switch between lifecycle, graph, execution, and raw evidence focus modes.

The selected artifact, deployment, and run form one navigation context. Empty
or unrelated stores remain valid: each list renders an explicit empty state,
and records that cannot be linked remain independently inspectable.

## Public RPC Surface

Extend the existing declarative operation registry with these read methods:

- `workflow.artifacts.list`;
- `workflow.artifacts.inspect`;
- `workflow.deployments.list`;
- `workflow.deployments.inspect`;
- `workflow.deployments.validate`;
- `workflow.runs.list`;
- `workflow.runs.inspect`;
- `workflow.runs.trace`.

No new Python RPC methods are required. Effect schemas decode the public
results at the browser-facing boundary. Operation metadata continues to own the
label, explanation, equivalent CLI formatter, idempotency classification, and
interpretation function.

List requests use the existing bounded contracts:

- artifacts: optional query, kind, cursor, and `limit` from 1 through 100;
- deployments: no filters in the current public method;
- runs: optional stopped status, cursor, and `limit` from 1 through 100;
- traces: required run id plus an explicit bounded trace range.

The console initially requests 50 artifacts and runs. It renders a **Load more**
action only when the public result includes a continuation cursor. Trace reads
request one bounded page and expose a next-page action rather than silently
loading an unbounded execution history.

Every call records raw request, raw response, interpreted result, duration, and
equivalent CLI evidence through the existing RPC service.

## UI Architecture

Use four focus modes within the existing React console shell:

- **Lifecycle:** linked artifact, deployment, and run master-detail columns;
- **Graph:** workflow graph for the selected artifact plan;
- **Execution:** selected run summary and trace timeline correlated to nodes;
- **Raw:** the existing protocol evidence list and drawers.

The lifecycle shell owns selection ids and loading/error state. Domain-specific
adapters convert interpreted RPC results into plain React view models. React
components do not decode external payloads or run Effect programs.

The first pass uses in-memory selection state. URL-addressable selections and
browser routing are deferred until presentation or replay requires stable deep
links.

## Lifecycle Linking

Link records using public identifiers only:

```text
artifact_id + version
  -> deployment.artifact reference
  -> run.deployment_id
  -> trace.run_id
```

The console never reads the workflow store directly. If a list result lacks
enough summary data to link records, inspect the candidate through its public
RPC method. Do not infer relationships from filesystem paths or naming
conventions.

Selecting a parent resets stale descendants:

- selecting an artifact clears deployment and run selection;
- selecting a deployment clears run selection;
- reconnecting clears the complete lifecycle context and invalidates pending
  requests.

The request-generation guard introduced by the foundation applies to every
list and inspect operation so late responses cannot overwrite a newer
selection.

## Workflow Graph

Add `@xyflow/react` for the interactive workflow graph. The graph adapter
accepts the selected artifact's public plan and emits React Flow nodes and
edges.

Node presentation distinguishes the existing core node kinds:

- capability use;
- condition;
- interrupt;
- foreach;
- join;
- end and other control nodes.

Each node shows its stable id and concise semantic label. Selecting a node opens
a detail drawer with its node kind, capability/source reference, input/output
bindings, declared outcomes, and routes. The drawer may include raw node JSON
as supporting evidence, but raw JSON is not the primary presentation.

The graph uses deterministic layout derived from graph structure. Layout
coordinates are presentation state only and are never written back to an
artifact or draft.

## Execution And Trace

The execution view presents:

- run id, deployment id, status, outcome, and resume readiness;
- output or failure summary;
- typed interrupt summary when present;
- bounded trace frames in execution order.

Each trace frame identifies its workflow node and displays status, outcome,
duration when available, and concise input/output summaries. Selecting a frame
focuses the corresponding graph node. Selecting a graph node filters or
highlights matching frames without mutating the stored trace.

Interrupted runs display the public interrupt kind, request payload, outcomes,
request schema, resume schema, and typed flag. This slice renders that contract
read-only; it does not submit a resume payload.

## Error And Empty States

Errors remain scoped to the operation that failed:

- a failed deployment validation does not erase artifact details;
- a failed trace page keeps the run summary visible;
- malformed decoded results render an RPC decode error with protocol evidence;
- stale responses are ignored after selection or target changes;
- missing records render a not-found state without crashing the shell.

The console differentiates loading, empty, unavailable, invalid, interrupted,
failed, and completed states. It does not use a single generic spinner or error
banner for the whole explorer.

## Testing

Default frontend tests remain independent of a live Python server.

Add tests for:

- Effect schemas and interpretation for every mapped method;
- pagination and bounded trace parameter formatting;
- operation registry metadata and equivalent CLI commands;
- lifecycle selection resets and stale-response suppression;
- artifact-to-deployment-to-run linking;
- graph adaptation for capability and control nodes;
- trace-to-node correlation;
- interrupted-run contract rendering;
- loading, empty, decode-error, not-found, and partial-failure states;
- production build and Hono static fallback regression.

Add an optional documented smoke path against `wf-rpc-server` using the
`lda_report_workflow` config. The smoke proves artifact inspection, deployment
inspection/validation, run inspection, bounded trace reading, graph rendering,
and raw evidence capture.

## Delivery Slices

Implement this design in two internal tasks within one product slice:

1. **Lifecycle read spine:** RPC mappings, view models, artifact/deployment/run
   lists and inspectors, linking, evidence, and state tests.
2. **Graph and execution:** React Flow adapter/canvas, node drawer, bounded
   trace timeline, node-frame correlation, and interrupted-run contract view.

Draft workspace list/get/validate/compile views reuse this shell afterward.
They are not required to complete the first artifact-to-run vertical path.

## Success Criteria

The slice is complete when:

1. a connected user can browse artifacts, deployments, and runs without direct
   store access;
2. selecting an artifact can lead to related deployments and runs using public
   identifiers;
3. the selected artifact renders as an interactive workflow graph;
4. a selected run renders status, output/interrupt information, and a bounded
   trace timeline;
5. trace frames correlate with graph nodes;
6. every RPC operation retains raw evidence and an equivalent CLI command;
7. stale requests and partial failures cannot corrupt newer selections;
8. the `lda_report_workflow` lifecycle is readable without scrolling raw JSON;
9. frontend tests, typecheck, production build, and optional live smoke pass.

