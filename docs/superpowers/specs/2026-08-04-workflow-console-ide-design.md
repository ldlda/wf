# Workflow Console IDE Design

Date: 2026-08-04

Status: Approved umbrella design. Implementation will proceed through bounded
vertical slices.

Related:

- [Workflow console foundation](2026-07-01-workflow-console-foundation-design.md)
- [Workflow console lifecycle explorer](2026-07-02-workflow-console-lifecycle-explorer.md)
- [Workflow contract manifest](2026-08-01-workflow-contract-manifest-design.md)
- [Current roadmap](../../current_roadmap.md)

## Goal

Turn the existing Workflow Console into a workflow IDE and operations console.
A human operator should be able to discover capabilities, author and validate a
typed workflow graph, freeze an artifact, bind a deployment, run and resume it,
inspect its trace and output, and compare prior runs without leaving the web
client.

The console is a client of the canonical workflow platform. It must expose real
backend state and diagnostics rather than recreate workflow semantics in the
browser. The same Python operations that support the CLI and agents must power
the UI.

## Product Position

The console is organized around the workflow lifecycle:

```text
Discover -> Draft -> Artifact -> Deploy -> Run -> Results
```

This lifecycle is the primary navigation model. Global artifact, deployment,
run, source, and administration indexes remain available, but they are
secondary ways to enter a lifecycle context.

The console is not one page per JSON-RPC method and is not a canvas with the
rest of the product attached as dialogs. It is a lifecycle workspace in which
the graph, forms, diagnostics, records, and execution evidence change emphasis
with the selected stage.

## Decisions

### Backend Support Powers Frontend Features

The browser does not invent durable workflow state. Draft revisions, artifacts,
deployments, bindings, runs, interruptions, traces, outputs, and future result
collections are persisted by backend modules before the console treats them as
durable.

Browser-only state is limited to presentation concerns such as selection,
viewport, panel visibility, pending form edits, and unsent mutation queues.

### Human IDE First

The first authoring interface is a human-operated graph IDE. A later agent or
chat authoring surface must invoke the same domain commands and consume the
same diagnostics. It must not introduce a second workflow mutation path.

### Desktop Authoring, Mobile Operations

Graph construction and wiring are desktop-first. Mobile supports:

- read-only graph inspection;
- run status and output inspection;
- diagnostics and evidence inspection; and
- typed interrupt responses.

Complex graph dragging, wiring, and schema editing are not mobile acceptance
requirements.

### Migrate, Do Not Preserve Two Consoles

The existing lifecycle explorer, graph, evidence, connection, and execution
modules are migration inputs. Useful behavior should move into the new
workspace. The old console layout should be removed once equivalent routes are
available rather than maintained as a compatibility UI.

## Workspace Architecture

The UI workflow workspace is a composition over canonical records, not a new
persisted backend `project` entity.

Initial routes are:

```text
/console/discover
/console/drafts
/console/drafts/:workspaceId
/console/artifacts
/console/artifacts/:artifactId/:version
/console/deployments
/console/deployments/:deploymentId
/console/runs
/console/runs/:runId
/console/results
/console/admin/sources
```

The collection routes are searchable indexes and creation entry points. The
command palette may open them or jump directly to a known identifier, but it is
not the only way to reach existing records. Selecting a record moves to its
identity route without hiding the relevant collection navigation.

The persistent shell contains:

- lifecycle navigation;
- active server target and connection status;
- breadcrumbs for the selected records;
- a command palette for route and lifecycle actions; and
- an activity/evidence surface for operation receipts and raw protocol data.

Each route owns one deep module:

| Module | Responsibility |
| --- | --- |
| `DiscoveryModule` | Search capabilities and node specifications for authoring. |
| `DraftEditorModule` | Edit a revisioned draft graph, contracts, mappings, and routes. |
| `ArtifactModule` | Inspect immutable versions, requirements, provenance, and diffs. |
| `DeploymentModule` | Bind requirements, validate readiness, and prepare a run. |
| `RunDebuggerModule` | Launch, monitor, interrupt, resume, trace, and inspect output. |
| `ResultsModule` | Search and compare immutable run results and evidence. |
| `SourceAdminModule` | Inspect source registry, auth summaries, and health; later host approved admin mutations. |

These modules communicate through route identifiers and domain results. They
must not import one another's internal React state.

## State Ownership

State has one owner at each level:

- the URL owns the durable selected lifecycle stage and record identity;
- the server owns drafts, revisions, artifacts, deployments, runs, and traces;
- the route module owns loaded data, request state, and mutations;
- local UI state owns node selection, viewport, open panels, and pending forms;
- the draft mutation queue owns ordering, debounce, and revision conflicts; and
- the evidence ledger records operations but is not an application-state store.

The design rejects a global mega-store. Cross-route state that must survive
navigation belongs in the URL or backend. Connection configuration may remain
in the existing connection module.

## Domain Client Seam

React modules do not call string-named JSON-RPC operations directly. They use
small domain-client interfaces:

- `CapabilityClient`;
- `DraftWorkspaceClient`;
- `ArtifactClient`;
- `DeploymentClient`;
- `RunClient`; and
- `SourceAdminClient`.

The clients are adapters over the generated and authored RPC contract. They
decode wire results, lower UI commands to concrete workflow operations, and
return domain results suitable for route modules.

Slice 1 introduces only the read interface it needs:

```ts
interface DraftWorkspaceClient {
  list(input: ListDraftWorkspacesInput): Promise<DraftWorkspacePage>;
  load(workspaceId: string): Promise<DraftWorkspaceResult>;
}
```

Slice 2 extends that module when mutation behavior exists:

```ts
interface DraftWorkspaceEditor extends DraftWorkspaceClient {
  create(input: CreateDraftWorkspaceInput): Promise<DraftWorkspaceResult>;
  mutate(command: DraftMutationCommand): Promise<DraftMutationResult>;
  validate(workspaceId: string): Promise<DraftValidationResult>;
  compile(workspaceId: string): Promise<DraftCompileResult>;
  createArtifact(input: CreateArtifactInput): Promise<ArtifactResult>;
}
```

`DraftMutationCommand` is a tagged UI command. Its adapter lowers commands to
the specific `workflow.draft_workspaces.*` operation. This hides operation-name
selection, revision threading, and wire decoding from React while preserving
typed, auditable behavior.

The domain-client seam must earn its depth. It should centralize contract
decoding, operation metadata, revision handling, and error normalization rather
than become a pass-through wrapper for every RPC method.

## Discovery

Discovery presents the information needed to construct a node:

- capability and node type;
- input and output schemas;
- declared outcomes;
- examples and description;
- provider/source availability; and
- constraints relevant to validation or deployment.

Users can search and filter the catalog, inspect a capability, and add it to an
open draft. If a capability is unavailable, the builder links to source health
or administration without exposing credentials inline.

Provider configuration, authentication summaries, registry reloads, and
enable/disable actions live under Administration. Discovery may report their
status but does not own those mutations. The initial route is read-only for
auth records and never reveals secret values. A user-facing credential editor,
OAuth flow, or production secret-store integration requires a separate backend
design before it appears here; the existence of admin auth RPC operations does
not by itself make a browser credential UI safe.

## Draft Graph Editor

The draft editor is graph-first and follows established workflow-builder
conventions rather than exposing raw JSON as the primary interface.

### Canvas

The canvas includes:

- compact nodes with type icon, name, capability/source, and outcomes;
- explicit start and terminal semantics;
- outcome-labelled handles and routes;
- pan, zoom, fit, minimap, and keyboard selection;
- validation markers attached to affected nodes, routes, and bindings; and
- graph-level selection for workflow contracts and settings.

Opening a node reveals a structured inspector. The node remains compact on the
canvas; forms and verbose schemas do not expand inside the graph.

### Inspector

The inspector supports:

- identity and description;
- step-specific configuration;
- typed input mappings and literals;
- node-output-to-state bindings;
- outcome routing;
- retry and timeout policy;
- diagnostics and suggested repairs; and
- an advanced raw-document escape hatch.

Graph selection opens workflow-level contracts, start state, exposed workflow
output, metadata, and validation. End nodes expose workflow completion and
output projection, not ordinary step execution fields.

The canonical `__end__` route target remains shorthand in the draft document.
The canvas renders each routed workflow outcome as a synthetic terminal node so
the graph is readable and wireable without adding a fake step to the persisted
document. Explicit end steps remain ordinary persisted steps when a workflow
uses them. Serialization maps synthetic terminal edges back to `__end__` and
never stores the synthetic node itself.

### Draft Operation Path

The editor uses `workflow.draft_workspaces.*` as its primary authoring surface.
Legacy `workflow.drafts.*` operations remain compatibility behavior and do not
receive a parallel editor.

### Autosave And Revision Conflicts

Draft changes use server-backed, debounced autosave:

1. a form or graph gesture emits a tagged mutation command;
2. the queue sends the current `workspace_id` and `revision`;
3. mutations are serialized for each workspace;
4. the canonical returned draft and revision replace local canonical state;
5. a revision conflict stops the queue and offers reload plus reapply or
   discard; and
6. validation diagnostics update without discarding semantically invalid work.

The browser may optimistically display a pending edit, but it must distinguish
pending, saved, invalid, and conflicted states. It must never label an edit
saved before backend confirmation.

Structurally valid but semantically invalid drafts may persist. Compilation and
artifact creation remain disabled until their backend gates pass.

## Artifact Inspection

Artifacts are immutable workflow versions. The artifact route provides:

- version selector and status;
- read-only workflow graph and contracts;
- logical requirements;
- provenance and catalog version;
- diagnostics;
- version comparison; and
- actions to create a deployment, export, or fork when supported by backend
  operations.

Any future fork action must create a real draft workspace. It must not mutate an
artifact or create an unsaved browser copy presented as durable.

## Deployment Binding

The deployment route makes the binding matrix primary and the graph supporting
context.

It displays:

- pinned artifact identity and version;
- each logical requirement mapped to a concrete source;
- source, schema, and catalog drift;
- static and live validation status;
- diagnostics grouped as missing, incompatible, unavailable, or drifted;
- suggested valid sources; and
- explicit save and delete actions.

The run form appears only when the deployment is runnable. Validation failure
does not erase attempted bindings; it returns actionable diagnostics.

## Run Debugger

### Launch

The launch surface derives a typed form from the workflow input contract and
also offers advanced raw JSON. It displays deployment identity and readiness,
then records an explicit operation receipt after the backend accepts or rejects
the start request.

### Execution

The run debugger correlates persisted runtime facts:

- run id, status, deployment, artifact, and version;
- graph nodes marked observed, interrupted, failed, or not yet observed when
  those states can be supported by persisted run and trace facts;
- bounded trace pages synchronized with the graph;
- selected frame input, output, state changes, outcome, and next node;
- diagnostics and operation evidence; and
- the final workflow output as a prominent inspectable result.

Initial updates use bounded polling. Streaming is introduced only after the
backend exposes a real event interface; the browser must not emulate streaming
by inventing intermediate states.

There is no per-node checkpoint stream. Node presentation is therefore an
explicit projection: returned trace frames prove observed nodes and outcomes;
the persisted interrupt identifies the interrupted point; and a top-level run
error may identify failure even when no frame exists. The UI may infer that
remaining graph nodes are not yet observed, but it must not label a node
currently executing or completed without supporting persisted evidence. When a
bounded trace page is insufficient to reconstruct the path, the graph says
`state unavailable` and offers the next trace page rather than guessing.

### Interrupt And Resume

An interrupted run displays the persisted interrupt request and generates a
typed response form from `resume_schema`. Available outcomes come from the
interrupt contract. Submitting the form invokes the canonical resume operation
and preserves the same run identity when the backend contract does so.

Cancellation, revision requests, and successful resumes must use the backend's
actual outcome language. The UI must not substitute presentation terminology
for persisted runtime facts.

## Results

The initial Results route is a projection over immutable runs rather than a new
result entity. It supports:

- filtering and searching runs;
- comparing input, output, status, artifact version, duration, and trace;
- exporting an evidence bundle; and
- starting a new run with a prior input.

Bookmarks, tags, collections, and reusable result assets are deferred until a
backend persistence model exists. They must not be stored only in the browser
and represented as shared platform records.

## Errors And Recovery

Errors are normalized at the domain-client seam into categories the UI can act
on:

- connection unavailable;
- contract or decode failure;
- not found;
- permission or browser-policy rejection;
- validation failure with diagnostics;
- revision conflict;
- operation failure; and
- unexpected server failure with evidence id.

Each route distinguishes initial loading, empty, stale, unavailable, and failed
states. A stale view may remain readable during reconnect, but mutations are
disabled until the target is ready.

Retry repeats idempotent reads automatically only when safe. Writes require an
explicit retry unless the operation contract carries an idempotency key. A late
response from a previous route selection cannot overwrite newer state.

## Accessibility And Responsive Behavior

The graph has a keyboard-accessible node list or equivalent non-canvas
navigation. Inspectors and dialogs restore focus, expose labelled regions, and
do not require color to communicate state. Forms associate diagnostics with
their fields and provide a summary for graph-level failures.

Desktop layouts prioritize canvas plus inspector. Narrow layouts collapse to a
single primary pane. Mobile users can inspect graphs and records, monitor runs,
read output and diagnostics, and answer typed interrupts. Authoring controls
that require wiring are unavailable rather than rendered as unusable miniature
canvas gestures.

## Testing Strategy

### Domain Client Contract Tests

Each domain client is tested through its public interface against representative
generated-schema payloads. Tests cover correct lowering, decoding, normalized
errors, and operation metadata. React tests mock domain clients rather than raw
JSON-RPC calls.

### Draft State Tests

Pure queue and reducer tests cover:

- serialized mutations and debounce;
- canonical revision replacement;
- optimistic pending state;
- validation failure that preserves the draft;
- conflict stop, reload, reapply, and discard;
- stale response rejection; and
- compile and artifact gate calculation.

### Route Integration Tests

Route tests cover direct URLs, loading and empty states, record changes,
connection loss, decode errors, and lifecycle navigation. Critical vertical
paths include:

1. discover capability -> create draft -> add and configure node;
2. validate draft -> compile -> create artifact;
3. bind deployment -> validate -> start run;
4. inspect interrupt -> submit typed resume -> inspect output; and
5. select trace frame -> correlate it with a graph node.

### Backend And Browser Acceptance

Every implemented vertical slice has an acceptance test against a real local
`wf-rpc-server` fixture. Browser smoke tests verify desktop authoring and mobile
inspection/approval at supported viewports. Tests assert persisted server state
after mutations instead of only checking rendered success messages.

## Delivery Slices

This umbrella design is intentionally not one implementation plan. Work proceeds
through backend-complete vertical slices:

1. **Workspace foundation:** routes, lifecycle shell, domain-client pattern,
   connection/evidence integration, and read-only draft loading.
2. **Draft graph authoring:** discovery, graph canvas, node inspector, mutation
   queue, revision conflicts, validation, and compile gates.
3. **Artifact and deployment:** immutable artifact inspection, version diff,
   binding matrix, readiness, and deployment save.
4. **Run debugger:** typed launch, polling, graph execution state, interrupts,
   resume, output, and bounded trace inspection.
5. **Results and administration:** run comparison/export plus separate source
   administration.

Each slice extends the transport stack before the UI when required:

1. Python operation and model support;
2. contract manifest and generated runtime schema coverage;
3. operation metadata and interpreted output;
4. Effect `RpcGroup` exposure;
5. Hono browser authorization;
6. browser response decoding;
7. domain-client behavior; and
8. route UI and acceptance tests.

The first executable implementation plan covers only Slice 1. Later slices get
their own plans after the preceding interface is exercised in the browser.

### Slice 1 Operation Matrix

Slice 1 intentionally expands the current browser policy. It requires only:

| Capability | Operations |
| --- | --- |
| Connection | `workflow.health` |
| Discovery | `workflow.capabilities.list`, `workflow.capabilities.inspect` |
| Draft index and detail | `workflow.draft_workspaces.list`, `workflow.draft_workspaces.get` |
| Existing lifecycle indexes | Current artifact, deployment, run, trace, and source read operations |

Before a route can call a newly listed operation, the slice must provide its
generated runtime schema, authored operation metadata where needed, Effect RPC
exposure, response decoding, and explicit Hono browser authorization. Browser
authorization remains an independent allowlist: generated contract coverage
must never authorize an operation automatically. Draft mutation and admin write
operations are not authorized in Slice 1.

## Non-Goals

This design does not add:

- a new backend project/workspace aggregate above existing records;
- browser-only durable workflow state;
- simultaneous multi-user draft editing;
- arbitrary JSON-RPC access from React;
- a second legacy-draft editor;
- mobile graph wiring;
- fake event streaming;
- persisted result collections without backend support; or
- agent/chat authoring before the human command path is stable.

## Success Criteria

The design is realized when a human can use the web console to complete the
canonical lifecycle against a real server without raw JSON as the primary
interface:

```text
discover -> draft -> validate -> artifact -> deploy -> run
         -> interrupt/resume -> output/trace -> compare result
```

At every stage, the console shows backend-confirmed identity, revision, status,
diagnostics, and evidence. The UI remains a client of the workflow platform,
and the same operations remain usable by the CLI and external agents.
