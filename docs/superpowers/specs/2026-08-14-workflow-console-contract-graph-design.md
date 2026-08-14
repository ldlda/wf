# Workflow Console Contract Graph Design

Date: 2026-08-14

Status: Approved design for Workflow Console authoring Slice 6.

Related:

- [Workflow Console IDE](2026-08-04-workflow-console-ide-design.md)
- [Workflow Console draft authoring workbench](2026-08-05-workflow-console-draft-authoring-workbench-design.md)
- [Workflow Console selected-step dataflow](2026-08-09-workflow-console-selected-step-dataflow-design.md)
- [Composite input expressions](2026-08-12-composite-input-expressions-design.md)
- [Current roadmap](../../current_roadmap.md)

## Goal

Make workflow-level contracts visible and editable as first-class graph
projections, and make every binding surface discoverable without requiring an
author to inspect raw JSON for path names.

The graph exposes Input, State, Output, and Outcomes as selectable projections.
The selected inspector edits workflow schemas, entry point, final output
bindings, and declared workflow outcomes through existing focused mutations.
One backend-owned authoring contract inventory supplies readable sources and
writable targets to the console.

## Design Principles

- The persisted draft remains the only editable workflow document.
- Input, State, Output, and Outcomes are projections of workflow-level
  contracts, not fake executable steps.
- Runtime context is transient and node-scoped. It appears in binding pickers
  only when applicable and never occupies a permanent graph node.
- The backend owns path availability, schema metadata, and execution-scope
  semantics. React does not maintain a second registry of known paths.
- The console offers human-readable selection first. Canonical paths and raw
  JSON remain available as details and advanced escape hatches.
- Client compatibility guidance is advisory. Complete server validation remains
  authoritative after every mutation.

## Scope

Slice 6 includes:

- selectable Input, State, Output, and Outcomes graph projections;
- focused workflow contract forms for input, state, and output schemas;
- explicit workflow outcome editing;
- entry-point selection from executable draft steps;
- canonical final workflow output binding editing;
- a protocol-neutral authoring contract inspection operation;
- a reusable searchable source and target picker;
- node-scoped runtime context suggestions;
- schema/type summaries and compatibility guidance; and
- responsive, accessible inspector behavior with operation evidence.

Slice 6 excludes:

- explicit End-node creation;
- typed creation forms for interrupt, condition, subgraph, foreach, or join;
- graph gesture binding by drawing edges;
- arbitrary schema inference from runtime values;
- renaming existing step ids;
- a new persisted workflow title field for individual steps; and
- making custom context paths statically safe when the runtime does not declare
  them.

Those exclusions preserve the roadmap boundary between contract authoring,
typed step authoring, and direct graph gestures.

## Graph Composition

The draft graph adds four projection nodes around the executable graph:

1. **Input** summarizes workflow input fields and identifies the configured
   entry step.
2. **State** summarizes durable workflow state fields and their reducer/default
   metadata where available.
3. **Output** summarizes the public workflow output schema and final output
   bindings.
4. **Outcomes** summarizes the workflow-level declared outcomes.

Projection nodes use a visually distinct contract treatment and cannot be
routed to, executed, duplicated, or deleted as steps. Selecting one opens its
focused inspector. Existing binding summaries may render dataflow connectors
between projections and executable steps, but those connectors are derived from
canonical bindings and are not independently persisted.

The graph does not add a Context projection. Context exists only for a running
execution frame and may differ by node. Showing it as a permanent workflow
contract would be misleading.

## Authoring Contract Inventory

Add `workflow.draft_workspaces.inspect_authoring_contract`, a protocol-neutral
read operation scoped to a draft workspace revision and an optional selected
step id. Its surface method and semantic interface are:

```text
inspect_draft_authoring_contract(
  workspace_id,
  revision,
  selected_step_id?,
) -> AuthoringContractInventory
```

The inventory contains four categories:

- **workflow sources**: readable `input.*` and `state.*` paths;
- **runtime sources**: declared `context.*` paths available or conditionally
  available for the selected step;
- **selected-step contract**: capability-local input targets, local output
  sources, and declared step outcomes; and
- **workflow targets**: writable state fields, public output fields, executable
  entry-point candidates, and declared workflow outcomes.

Each path entry includes:

- canonical path;
- origin and semantic role;
- human-readable label and optional description;
- normalized JSON Schema fragment when known;
- required/optional status when known;
- availability and an optional reason;
- permitted binding uses; and
- compatibility metadata sufficient for the UI to reject only obvious local
  mismatches.

The operation returns a revision-aware projection. A stale revision produces a
normal revision conflict rather than choices derived from a different document.
The operation does not mutate the workspace.

## Source Availability

Workflow input and state choices are derived from the canonical draft schemas.
Nested object and array fields remain browseable without exposing raw schema
syntax. The current client-side `workflowSourceSuggestions` behavior becomes a
fallback or is replaced by the backend inventory; it must not remain an
independent source of truth once the operation is available.

Standard frame context currently includes values such as prior outcome, active
incoming edge, scope id, lineage id, and parent lineage id. Foreach iteration
frames additionally expose loop item, loop index, and the configured foreach
alias. Future fork/join features may add branch-scoped context through the same
inventory without changing high-level clients.

Context availability is computed by core/API code using workflow graph and
execution-frame semantics:

- always-available frame keys may be suggested for every executable step;
- foreach keys are suggested when the selected step is proven to execute in the
  child frame entered through a foreach `loop` route;
- a node reachable both inside and outside that frame receives conditional
  entries with a warning rather than a false guarantee;
- ambiguous or malformed control flow never produces a guaranteed scoped key;
  and
- nested foreach scopes expose only the keys actually carried by the current
  execution frame. Today that means the innermost iteration alias rather than
  automatic inheritance of every enclosing alias; a future runtime inheritance
  change updates the inventory at the same backend seam.

This analysis is intentionally conservative and advisory. Existing validation
accepts syntactically valid custom `context.*` paths because the runtime may
provide extensions that static analysis does not know. Runtime resolution
therefore remains authoritative; this slice does not claim strict static
context-scope enforcement.

## Source And Target Picker

One reusable picker renders inventory entries wherever an author chooses a path
or field. It is used by:

- capability-step input bindings;
- composite path expressions;
- condition and interrupt forms when those typed editors arrive;
- selected-step output bindings;
- workflow final output bindings.

The standalone capability playground remains literal-only in this slice. It
has no draft workspace, workflow input/state schema, or execution frame from
which to derive truthful path choices. A future workflow-scoped playground may
reuse the picker once that context exists.

The default experience is browsing and search, not typing paths:

- group choices by Workflow input, State, Step output, and Runtime context;
- show a friendly label prominently and the canonical path secondarily;
- show type, required status, and concise descriptions;
- allow nested fields to expand without opening raw JSON;
- filter incompatible choices when compatibility is certain;
- explain disabled or conditional choices in place; and
- hide the Runtime context group entirely when it has no applicable entries.

The picker writes the canonical path after selection. A compact Advanced action
reveals manual path entry for forward-compatible runtime extensions and repair
of persisted unknown paths. Custom paths are never the normal authoring flow.

## Focused Inspectors And Mutations

The Input inspector edits the workflow input schema and entry point. Entry-point
choices come from real executable steps and lower through the existing focused
`set_draft_start` operation.

The State inspector edits the workflow state schema, including field schemas,
defaults, and reducers supported by the canonical state model. State-field
removal must show affected bindings before submission and rely on server
validation for the final decision.

The Output inspector edits the public output schema and ordered final output
bindings. Its source picker consumes workflow input and state sources; its
targets come from declared output fields. Final workflow projection currently
runs without execution-frame context, so `context.*` is not offered here and a
persisted context-backed output is shown as an unsupported repair value. It
lowers through
`set_draft_contract` and `set_workflow_output_bindings` without lossy output
maps.

The Outcomes inspector edits the ordered declared workflow outcomes. Outcome
names remain workflow-level contract values; explicit End-node authoring is
deferred to Slice 7.

Contract schema edits lower through the existing focused `set_draft_contract`
operation. The console may coordinate sequential focused mutations when one
user action changes two independent contracts, but it must report partial
success honestly and must not claim cross-operation atomicity.

## Step Inspector Metadata

Selected capability steps continue to use their id as the primary heading.
Setup exposes description, retry, and timeout using the existing focused update
operation. Retry and timeout remain optional and presence-aware.

This slice does not add a persisted step title or casual id rename. Renaming an
existing id rewrites routes and graph references and belongs in a future
dedicated graph transformation. New-step id selection arrives with the typed Add
step palette in Slice 7.

## Validation And Errors

The browser performs only local, deterministic checks:

- required selections and non-empty canonical names;
- parseable custom paths;
- duplicate destinations where the canonical model forbids them;
- obvious schema incompatibility reported by the inventory; and
- incomplete binding rows.

The backend validates schema documents, graph references, ordinary path
availability, binding overlap, output completeness, route/outcome consistency,
and the full revised draft. Runtime-context inventory remains advisory for the
reason described above.

An invalid but persisted draft still replaces the displayed canonical draft and
shows diagnostics. A transport failure preserves confirmed state and local
edits. A revision conflict preserves the selected projection, active form, and
unsaved changes so reload/reapply can use the established workbench flow.

If inventory inspection fails, existing canonical values remain visible and
repairable. The UI disables catalog-dependent additions, retains Advanced raw
path repair, and explains that suggestions are unavailable; it does not silently
fall back to a stale hardcoded list.

## Evidence And Accessibility

Every write records bounded operation evidence through the shared mutation
executor. Inventory reads use normal loading, stale, empty, and failure states
but do not crowd the persistent operation evidence surface.

Projection nodes are keyboard-selectable and identify themselves as workflow
contracts rather than steps. Pickers support search, keyboard navigation,
group labels, type descriptions, and announced conditional/disabled reasons.
Desktop preserves the graph while the focused inspector scrolls independently.
Mobile uses the existing mounted inspector sheet without losing unsaved edits
when closed.

## Verification

The implementation must include:

- unit tests for schema flattening and normalized inventory entries;
- graph-scope tests for common context, serial/concurrent foreach bodies,
  aliases, nested foreach, mixed reachability, and malformed graphs;
- operation-model, protocol dispatch, generated-schema parity, and browser
  allowlist tests for inventory inspection;
- picker tests for grouping, search, nested fields, compatibility, conditional
  context, hidden empty context groups, and Advanced custom paths;
- projection tests proving Input, State, Output, and Outcomes are selectable but
  never serialized as executable steps;
- exact mutation payload tests for contract, start, outcome, and final output
  edits;
- revision-conflict and inventory-failure retention tests;
- desktop and mobile integration tests preserving selection and unsaved forms;
- a real-server smoke path covering inventory inspection and one focused
  contract mutation; and
- focused Python, RPC, console, typecheck, and build verification.

## Success Criteria

- An author can discover normal input, state, step-output, and applicable
  context fields without reading JSON or memorizing path syntax.
- The same source/target vocabulary appears consistently across
  workflow-scoped authoring surfaces. The standalone capability playground
  remains literal-only until it receives workflow scope.
- Foreach aliases appear only where the backend can justify their availability.
- Input, State, Output, and Outcomes read as workflow contracts in the graph and
  remain absent from the persisted executable step list.
- Entry point, workflow schemas/outcomes, and final output bindings are editable
  through focused canonical operations.
- Custom paths remain possible without dominating the normal experience.
- No high-level TypeScript module hardcodes runtime context key names.
