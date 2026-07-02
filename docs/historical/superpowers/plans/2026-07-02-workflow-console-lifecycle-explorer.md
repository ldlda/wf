# Workflow Console Lifecycle Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a generic read-only artifact -> deployment -> run -> trace explorer with an interactive workflow graph, exercised through `examples/lda_report_workflow/`.

**Architecture:** Extend the existing Effect RPC registry with public lifecycle read operations, then adapt decoded results into plain console view models. A focused React lifecycle shell owns selection and request generations; `@xyflow/react` renders workflow plans laid out by `@dagrejs/dagre`, while a separate execution adapter correlates bounded trace frames to graph nodes.

**Tech Stack:** TypeScript 6, React 19, Vite 8, Effect 3 / `@effect/rpc`, Valibot, Vitest, Testing Library, `@xyflow/react`, `@dagrejs/dagre`, Hono.

## Global Constraints

- Use only public JSON-RPC methods; never read workflow stores directly.
- Add no Python RPC methods in this slice.
- Keep the slice read-only: no draft mutation, run start/resume, autoplay, replay, agent, or presentation code.
- Decode external results before React components receive them; React consumes plain view models and does not run Effect programs.
- Preserve raw request, raw response, duration, and equivalent CLI evidence for every operation.
- Request at most 50 artifacts/runs initially and one bounded trace page of 50 frames.
- Ignore stale responses after target or selection changes.
- Use `@xyflow/react` and `@dagrejs/dagre`; do not hand-roll graph layout.
- Use `examples/lda_report_workflow/` as the reference fixture without hard-coding its ids in production components.
- Do not use `any`, unchecked TypeScript assertions, or direct mutation of decoded transport objects.

---

## File Structure

Create focused modules instead of expanding `App.tsx`:

```text
web/apps/console/src/
  lifecycle/
    models.ts                 # Valibot decoding and plain lifecycle view models
    models.test.ts
    state.ts                  # Pure selection/loading reducer
    state.test.ts
    useLifecycleExplorer.ts   # RPC orchestration and stale-response guards
    LifecycleExplorer.tsx     # Focus navigation and master-detail composition
    LifecycleExplorer.test.tsx
    RecordColumns.tsx         # Artifact/deployment/run list columns
    RecordDetails.tsx         # Read-only selected-record details
  graph/
    graph-model.ts            # Raw plan -> laid-out React Flow model
    graph-model.test.ts
    WorkflowGraph.tsx         # Canvas and node selection
    WorkflowGraph.test.tsx
    NodeInspector.tsx         # Semantic node detail drawer
  execution/
    trace-model.ts            # Trace decoding/correlation view model
    trace-model.test.ts
    ExecutionView.tsx         # Run summary, interrupt, and trace timeline
    ExecutionView.test.tsx
```

Modify the existing RPC package, browser contracts, App shell, styles, docs,
and package manifests only where their responsibility requires it.

### Task 1: Map Lifecycle Read Operations Through Effect RPC

**Files:**
- Modify: `web/packages/rpc/src/rpcs.ts`
- Modify: `web/packages/rpc/src/method-registry.ts`
- Modify: `web/packages/rpc/src/service.ts`
- Modify: `web/packages/rpc/src/index.ts`
- Modify: `web/packages/rpc/src/service.test.ts`
- Modify: `web/apps/server/src/app.test.ts`

**Interfaces:**
- Produces operation names for artifact list/inspect, deployment list/inspect/validate, and run list/inspect/trace.
- Produces interpreted transport objects whose field names are camelCase and whose full raw responses remain in `OperationExchange.exchange`.
- Consumers in later tasks call the existing `WorkflowRpc.execute(operation, target, params)` API.

- [ ] **Step 1: Write failing RPC service tests for all new methods**

Add table-driven cases to `service.test.ts` using the existing fake-fetch pattern:

```ts
const lifecycleCases = [
  {
    operation: "workflow.artifacts.list",
    params: { limit: 50 },
    result: {
      nodes: [{
        name: "workflow.report@1",
        artifact_id: "report",
        version: 1,
        kind: "workflow",
        display_name: "Report",
        description: null,
        outcomes: ["ok"],
        input_schema: { type: "object" },
        output_schema: { type: "object" },
        required_sources: ["local.report"],
        diagnostics: [],
      }],
      total: 1,
      cursor: null,
      next_cursor: null,
      limit: 50,
    },
  },
  {
    operation: "workflow.deployments.list",
    params: {},
    result: {
      deployments: [{
        id: "report.default",
        artifact_id: "report",
        artifact_version: 1,
        binding_count: 1,
        drift_policy: "block",
      }],
    },
  },
  {
    operation: "workflow.runs.list",
    params: { limit: 50 },
    result: {
      runs: [{
        run_id: "run_1",
        deployment_id: "report.default",
        artifact_id: "report",
        artifact_version: 1,
        status: "interrupted",
        resume_readiness: "ready",
        diagnostic_count: 0,
        created_at: "2026-07-02T00:00:00Z",
        updated_at: "2026-07-02T00:00:01Z",
      }],
      total: 1,
      cursor: null,
      next_cursor: null,
      limit: 50,
    },
  },
] as const;
```

For inspect/validate/trace, assert at least the identity, status, plan, bindings,
diagnostics, interrupt, and bounded trace fields used by later view models.

- [ ] **Step 2: Run the focused tests and confirm the red state**

Run:

```powershell
pnpm --dir web --filter @lda/workflow-rpc test -- service.test.ts
```

Expected: FAIL because the operation names are unknown or absent from
`WorkflowRpcs`.

- [ ] **Step 3: Add Effect schemas and RPC declarations**

In `rpcs.ts`, introduce reusable strict primitives and public result schemas:

```ts
const PositiveIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, Number.MAX_SAFE_INTEGER),
);

const JsonObjectSchema = Schema.Record({
  key: Schema.String,
  value: Schema.Unknown,
});

export const ArtifactRefSchema = Schema.Struct({
  artifact_id: Schema.String,
  version: PositiveIntegerSchema,
});

export const TraceRangeSchema = Schema.Struct({
  start: NonNegativeIntegerSchema,
  limit: PositiveIntegerSchema,
});
```

Define one `Rpc.make` per exact public method and add each to `WorkflowRpcs`.
Payloads must mirror `src/wf_transport_rpc_http/models.py`; success schemas
must decode the selected UI fields and preserve plan/output/interrupt/trace
objects as schema-checked records or explicit nullable fields.

- [ ] **Step 4: Extend the operation registry and execution switch**

Add one `OperationMeta` entry per method. Equivalent CLI strings must be:

```text
uv run wf artifact list --limit 50
uv run wf artifact inspect ARTIFACT_ID --version VERSION
uv run wf deploy list
uv run wf deploy inspect DEPLOYMENT_ID
uv run wf deploy validate DEPLOYMENT_ID
uv run wf run list --limit 50
uv run wf run inspect RUN_ID
uv run wf run trace RUN_ID --from START --limit LIMIT
```

Extend `OperationName` and the `executeImpl` switch. Follow the existing
generated-client access style, for example:

```ts
case "workflow.artifacts.list": {
  const payload = yield* decodeParams(WorkflowArtifactsListPayloadSchema, params);
  return yield* client.workflow["artifacts.list"](payload);
}
```

Keep `metadata.interpret()` inside `decodeOperationMetadata` so schema failures
remain `RpcDecodeError` values with evidence.

- [ ] **Step 5: Run RPC and server tests**

Run:

```powershell
pnpm --dir web --filter @lda/workflow-rpc test
pnpm --dir web --filter @lda/web-server test
```

Expected: all tests pass, including an app test proving a newly registered
operation reaches `RunOperation` rather than returning `unknown_operation`.

- [ ] **Step 6: Commit the RPC read surface**

```powershell
git add web/packages/rpc web/apps/server/src/app.test.ts
git commit -m "feat: expose lifecycle reads to web console"
```

### Task 2: Add Typed Browser Contracts And Lifecycle View Models

**Files:**
- Modify: `web/apps/console/src/connection/contracts.ts`
- Modify: `web/apps/console/src/connection/api.test.ts`
- Create: `web/apps/console/src/lifecycle/models.ts`
- Create: `web/apps/console/src/lifecycle/models.test.ts`

**Interfaces:**
- Produces `ArtifactSummary`, `ArtifactDetail`, `DeploymentSummary`, `DeploymentDetail`, `DeploymentValidation`, `RunSummary`, `RunDetail`, and `TracePage`.
- Produces `decodeArtifactList`, `decodeArtifactDetail`, `decodeDeploymentList`, `decodeDeploymentDetail`, `decodeDeploymentValidation`, `decodeRunList`, `decodeRunDetail`, and `decodeTracePage`.
- Later React tasks consume only these view models.

- [ ] **Step 1: Write failing adapter tests**

Cover valid payloads, missing required identities, negative counts, malformed
plans, nullable interrupt/output fields, and bounded trace metadata. Example:

```ts
it("decodes an artifact list into immutable summaries", () => {
  const result = decodeArtifactList({
    nodes: [{
      artifactId: "report",
      version: 1,
      kind: "workflow",
      displayName: "Report",
      description: null,
      outcomes: ["ok"],
      requiredSources: ["local.report"],
      diagnosticCount: 0,
    }],
    nextCursor: null,
    total: 1,
  });
  expect(result.items[0]?.key).toBe("report@1");
});
```

- [ ] **Step 2: Run tests and confirm missing adapters**

```powershell
pnpm --dir web --filter @lda/console test -- models.test.ts
```

Expected: FAIL because `lifecycle/models.ts` does not exist.

- [ ] **Step 3: Extend the operation-name browser contract**

Add all lifecycle method literals to `OperationNameSchema`. Keep the envelope
forward-compatible for error codes, but reject unknown success operation names.

- [ ] **Step 4: Implement Valibot-backed lifecycle adapters**

Each decoder validates `unknown` and returns a plain immutable object. Use a
shared error wrapper:

```ts
const decode = <T>(
  label: string,
  schema: v.GenericSchema<unknown, T>,
  value: unknown,
): T => {
  const result = v.safeParse(schema, value);
  if (result.success) return result.output;
  throw new Error(`${label} is malformed: ${result.issues[0]?.message ?? "unknown issue"}`);
};
```

Do not pass transport snake_case values into React. Normalize stable keys,
display labels, status enums, counts, pagination cursors, and inspect payloads
inside these adapters.

- [ ] **Step 5: Run console adapter/API tests**

```powershell
pnpm --dir web --filter @lda/console test -- models.test.ts api.test.ts
```

Expected: all focused tests pass.

- [ ] **Step 6: Commit browser lifecycle models**

```powershell
git add web/apps/console/src/connection web/apps/console/src/lifecycle
git commit -m "feat: add lifecycle console view models"
```

### Task 3: Build Lifecycle Selection State And RPC Orchestration

**Files:**
- Create: `web/apps/console/src/lifecycle/state.ts`
- Create: `web/apps/console/src/lifecycle/state.test.ts`
- Create: `web/apps/console/src/lifecycle/useLifecycleExplorer.ts`
- Create: `web/apps/console/src/lifecycle/useLifecycleExplorer.test.tsx`

**Interfaces:**
- Produces `LifecycleState`, `LifecycleAction`, `lifecycleReducer`, and `initialLifecycleState`.
- Produces `useLifecycleExplorer(target)` with selection commands, refresh commands, load-more commands, and plain state.

- [ ] **Step 1: Write reducer tests for selection invariants**

Pin these transitions:

```ts
selectArtifact("report@1")
// clears selectedDeploymentId, selectedRunId, deployment detail, run detail, trace

selectDeployment("report.default")
// clears selectedRunId, run detail, trace

targetChanged()
// returns the complete lifecycle state to its initial value
```

Also cover loading, empty, partial error, append-page, inspect-success, and
trace-page states.

- [ ] **Step 2: Run reducer tests and confirm red**

```powershell
pnpm --dir web --filter @lda/console test -- lifecycle/state.test.ts
```

Expected: FAIL because the reducer is missing.

- [ ] **Step 3: Implement the pure reducer**

Use separate operation states rather than one global loading flag:

```ts
type LoadState<T> =
  | { readonly phase: "idle" }
  | { readonly phase: "loading"; readonly previous: T | null }
  | { readonly phase: "loaded"; readonly value: T }
  | { readonly phase: "error"; readonly message: string; readonly previous: T | null };
```

Keep ids and decoded records separate so selection changes do not mutate list
objects.

- [ ] **Step 4: Write hook tests with deferred promises**

Mock `callOperation` and prove:

- initial target load requests artifact/deployment/run lists with limit 50;
- selecting an artifact requests inspect once;
- a late artifact response is ignored after a newer selection;
- reconnect invalidates all outstanding generations;
- deployment validation failure leaves artifact detail visible;
- trace next-page appends only the matching run's frames.

- [ ] **Step 5: Implement `useLifecycleExplorer`**

Use one generation counter for target-wide list loads and one counter per
selected inspect/trace chain. Dispatch evidence through a supplied callback:

```ts
export const useLifecycleExplorer = (
  target: string | null,
  recordEvidence: (record: EvidenceRecord) => void,
): LifecycleExplorerController => { /* orchestrate callOperation */ };
```

Never duplicate evidence DTO construction; extract the existing App logic into
a small helper if both source inventory and lifecycle operations need it.

- [ ] **Step 6: Run reducer and hook tests**

```powershell
pnpm --dir web --filter @lda/console test -- lifecycle
```

Expected: all lifecycle state/orchestration tests pass.

- [ ] **Step 7: Commit lifecycle state management**

```powershell
git add web/apps/console/src/lifecycle
git commit -m "feat: orchestrate lifecycle explorer reads"
```

### Task 4: Render The Lifecycle Master-Detail Explorer

**Files:**
- Create: `web/apps/console/src/lifecycle/RecordColumns.tsx`
- Create: `web/apps/console/src/lifecycle/RecordDetails.tsx`
- Create: `web/apps/console/src/lifecycle/LifecycleExplorer.tsx`
- Create: `web/apps/console/src/lifecycle/LifecycleExplorer.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**
- Consumes `LifecycleExplorerController` from Task 3.
- Produces a generic artifact -> deployment -> run navigation shell and focus-mode buttons.
- Emits selected artifact plan and selected run/trace data to graph/execution children introduced later.

- [ ] **Step 1: Write component tests for the complete read spine**

Render a loaded controller fixture and assert:

```ts
expect(screen.getByRole("button", { name: /Report.*version 1/i })).toBeVisible();
expect(screen.getByRole("button", { name: /report.default/i })).toBeVisible();
expect(screen.getByRole("button", { name: /run_1.*interrupted/i })).toBeVisible();
```

Click each level and assert descendant selection callbacks. Add explicit tests
for empty artifacts, unrelated deployments, unavailable trace, and partial
validation errors.

- [ ] **Step 2: Run the component test and confirm red**

```powershell
pnpm --dir web --filter @lda/console test -- LifecycleExplorer.test.tsx
```

Expected: FAIL because the components do not exist.

- [ ] **Step 3: Implement accessible list columns and record details**

Use semantic buttons/lists and visible selection state. Details must prioritize
interpreted values:

- artifact: title, id/version, kind, outcomes, required sources;
- deployment: id, artifact ref, drift policy, bindings, validation status and diagnostics;
- run: id, deployment, artifact ref, status, readiness, outcome, updated time.

Do not render whole-object JSON in these panels.

- [ ] **Step 4: Implement focus navigation**

`LifecycleExplorer` owns four buttons: Lifecycle, Graph, Execution, Raw. Disable
Graph without an inspected artifact and Execution without an inspected run.
Raw remains available when evidence exists.

- [ ] **Step 5: Add responsive styles**

Desktop uses three linked columns plus a details panel. Narrow screens use
horizontal focus navigation and one active column at a time; do not shrink all
columns until unreadable.

- [ ] **Step 6: Run explorer tests and typecheck**

```powershell
pnpm --dir web --filter @lda/console test -- LifecycleExplorer.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: both commands pass.

- [ ] **Step 7: Commit the lifecycle UI**

```powershell
git add web/apps/console/src/lifecycle web/apps/console/src/styles/global.css
git commit -m "feat: render lifecycle master detail explorer"
```

### Task 5: Add Library-Backed Workflow Graph Adaptation

**Files:**
- Modify: `web/apps/console/package.json`
- Modify: `web/pnpm-lock.yaml`
- Create: `web/apps/console/src/graph/graph-model.ts`
- Create: `web/apps/console/src/graph/graph-model.test.ts`

**Interfaces:**
- Produces `WorkflowGraphModel`, `WorkflowGraphNodeData`, and `buildWorkflowGraph(plan)`.
- Uses `@dagrejs/dagre` only for layout; it never writes coordinates back to workflow data.

- [ ] **Step 1: Install graph dependencies**

```powershell
pnpm --dir web --filter @lda/console add @xyflow/react@12.11.1 @dagrejs/dagre@3.0.0
```

Both pinned packages ship TypeScript declarations; do not add a legacy
`@types/dagre` package.

- [ ] **Step 2: Write failing graph-model tests**

Use fixtures containing capability use, condition, interrupt, foreach, join,
and end nodes. Assert stable ids, semantic labels, route edges, node kinds,
deterministic coordinates, and immutability of the input plan.

```ts
const first = buildWorkflowGraph(plan);
const second = buildWorkflowGraph(structuredClone(plan));
expect(second).toEqual(first);
expect(plan).toEqual(originalPlan);
```

- [ ] **Step 3: Run graph-model tests and confirm red**

```powershell
pnpm --dir web --filter @lda/console test -- graph-model.test.ts
```

Expected: FAIL because the adapter is missing.

- [ ] **Step 4: Implement plan normalization and Dagre layout**

Decode only the plan structures required to render nodes/edges. Convert all
supported node variants into a common view model:

```ts
export type WorkflowGraphNodeData = {
  readonly nodeId: string;
  readonly kind: "use" | "condition" | "interrupt" | "foreach" | "join" | "end" | "control";
  readonly label: string;
  readonly capability: string | null;
  readonly outcomes: ReadonlyArray<string>;
  readonly raw: Readonly<Record<string, unknown>>;
};
```

Use Dagre's directed layout with fixed presentation dimensions. Sort nodes and
edges by stable ids before layout so identical plans produce identical models.

- [ ] **Step 5: Run graph tests and typecheck**

```powershell
pnpm --dir web --filter @lda/console test -- graph-model.test.ts
pnpm --dir web --filter @lda/console typecheck
```

Expected: all checks pass.

- [ ] **Step 6: Commit graph dependencies and model**

```powershell
git add web/apps/console/package.json web/pnpm-lock.yaml web/apps/console/src/graph
git commit -m "feat: adapt workflow plans for graph rendering"
```

### Task 6: Render The Workflow Graph And Node Inspector

**Files:**
- Create: `web/apps/console/src/graph/WorkflowGraph.tsx`
- Create: `web/apps/console/src/graph/WorkflowGraph.test.tsx`
- Create: `web/apps/console/src/graph/NodeInspector.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**
- Consumes `WorkflowGraphModel` and an optional active trace node id.
- Produces node selection events and a semantic inspector drawer.

- [ ] **Step 1: Write failing graph interaction tests**

Mock `@xyflow/react` only where jsdom lacks layout APIs. Assert that nodes and
edges render, selecting `review` opens the inspector, and `activeNodeId` marks
the matching node without changing graph data.

- [ ] **Step 2: Run the component test and confirm red**

```powershell
pnpm --dir web --filter @lda/console test -- WorkflowGraph.test.tsx
```

Expected: FAIL because the graph components are missing.

- [ ] **Step 3: Implement the graph canvas**

Import `@xyflow/react/dist/style.css`, render controls/background/fit-view, and
use custom node presentation for semantic kinds. Keep the graph read-only:
disable connect, delete, drag persistence, and mutation callbacks.

- [ ] **Step 4: Implement the node inspector**

Show node kind, capability/source reference, input/output bindings, outcomes,
and routes. Put raw node JSON behind a collapsed disclosure labeled
**Raw node definition**.

- [ ] **Step 5: Run graph component tests and accessibility checks**

```powershell
pnpm --dir web --filter @lda/console test -- WorkflowGraph.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: all checks pass with no missing accessible names.

- [ ] **Step 6: Commit graph presentation**

```powershell
git add web/apps/console/src/graph web/apps/console/src/styles/global.css
git commit -m "feat: render interactive workflow graph"
```

### Task 7: Add Run Execution, Trace, And Interrupt Views

**Files:**
- Create: `web/apps/console/src/execution/trace-model.ts`
- Create: `web/apps/console/src/execution/trace-model.test.ts`
- Create: `web/apps/console/src/execution/ExecutionView.tsx`
- Create: `web/apps/console/src/execution/ExecutionView.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**
- Produces `TraceFrameView`, `buildTraceFrames(tracePage)`, and `ExecutionView`.
- Emits selected frame node ids to `WorkflowGraph` for correlation.

- [ ] **Step 1: Write failing trace adapter tests**

Use the public trace shape:

```ts
{
  frame_id: "root",
  node_id: "review",
  step_type: "interrupt",
  resolved_input: { report: "..." },
  outcome: "submitted",
  next_node_id: "create_issues",
  output: {},
  state_changes: {},
}
```

Assert stable frame keys, node correlation, concise summaries, ordering, and
next-page state from `trace_start`, `trace_limit`, and `trace_truncated`.

- [ ] **Step 2: Run trace tests and confirm red**

```powershell
pnpm --dir web --filter @lda/console test -- trace-model.test.ts
```

Expected: FAIL because trace adapters are missing.

- [ ] **Step 3: Implement trace adaptation**

Never stringify unbounded input/output into list rows. Produce counts and short
field summaries; retain full decoded values only for the selected frame drawer.

- [ ] **Step 4: Write and implement execution component tests**

Cover completed, failed, and interrupted runs. The interrupted fixture must
render `kind`, payload, outcomes, request schema, resume schema, and typed flag,
but no submit/resume button.

Selecting a trace frame must call:

```ts
onSelectNode(frame.nodeId);
```

- [ ] **Step 5: Run execution tests and typecheck**

```powershell
pnpm --dir web --filter @lda/console test -- execution
pnpm --dir web --filter @lda/console typecheck
```

Expected: all checks pass.

- [ ] **Step 6: Commit execution and trace views**

```powershell
git add web/apps/console/src/execution web/apps/console/src/styles/global.css
git commit -m "feat: render run execution and trace"
```

### Task 8: Integrate The Explorer, Document Smoke, And Verify

**Files:**
- Modify: `web/apps/console/src/app/App.tsx`
- Modify: `web/apps/console/src/app/App.test.tsx`
- Modify: `web/apps/console/src/app/state.ts`
- Modify: `web/apps/console/src/components/ProtocolEvidence.tsx`
- Modify: `web/apps/console/src/styles/global.css`
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-07-02-workflow-console-lifecycle-explorer.md` -> `docs/historical/superpowers/plans/2026-07-02-workflow-console-lifecycle-explorer.md`

**Interfaces:**
- Connects the existing connection/source foundation to Lifecycle, Graph, Execution, and Raw focus modes.
- Preserves the current source inventory and protocol evidence behavior.

- [ ] **Step 1: Write the failing App integration test**

Mock lifecycle RPC responses and prove this sequence:

```text
Connect -> artifacts load -> select artifact -> Graph enabled
        -> select deployment -> select run -> Execution enabled
        -> select trace frame -> matching graph node active
        -> Raw shows evidence for each call
```

Also prove reconnect clears lifecycle selection and ignores late responses from
the previous target.

- [ ] **Step 2: Run the App test and confirm red**

```powershell
pnpm --dir web --filter @lda/console test -- App.test.tsx
```

Expected: FAIL because App does not mount the explorer.

- [ ] **Step 3: Integrate focus modes without growing App orchestration**

`App.tsx` should instantiate `useLifecycleExplorer` and pass the controller to
`LifecycleExplorer`; it must not absorb lifecycle reducer cases or transport
decoding. Reuse `ProtocolEvidence` for Raw focus rather than adding a second raw
viewer.

- [ ] **Step 4: Document the optional live smoke**

Add these exact prerequisites and checks to `web/README.md`:

```powershell
uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
pnpm --dir web dev
```

Document how to seed or generate the example's artifact/deployment/run using
its existing README or build script; do not introduce a helper that drives
`WorkflowApi` directly. The smoke passes when artifact, deployment, run, graph,
trace, and raw evidence are visible.

- [ ] **Step 5: Run complete verification**

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
uv run pytest tests/docs -q -n0
git diff --check
```

Expected: all commands exit 0. CRLF conversion warnings are acceptable;
whitespace errors are not.

- [ ] **Step 6: Perform the optional live smoke**

With the Python server and web dev process running, verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/health
```

Then inspect the lifecycle through `http://127.0.0.1:5173`. Record any skipped
fixture setup explicitly; do not claim live smoke success from unit tests.

- [ ] **Step 7: Update roadmap and archive the plan**

Mark roadmap item 4 completed only after the full verification and live smoke
requirements have been met. Move this plan to the historical mirror path and
update any live links.

- [ ] **Step 8: Commit integration and documentation**

```powershell
git add web docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-02-workflow-console-lifecycle-explorer.md
git commit -m "feat: add workflow lifecycle explorer"
```

## Plan Self-Review

- Spec coverage: public RPC reads, pagination, stale guards, linking, graph,
  trace, interrupt contract, evidence, error states, testing, and live smoke
  each map to explicit tasks.
- Scope: draft workspace inspection remains a named follow-up and is not mixed
  into the artifact-to-run vertical slice.
- Type consistency: lifecycle adapters feed the controller; the controller
  feeds React; graph and trace models share stable `nodeId` strings.
- Placeholder scan: no TBD/TODO or unspecified implementation steps remain.
