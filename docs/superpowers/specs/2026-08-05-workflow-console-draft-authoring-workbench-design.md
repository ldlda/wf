# Workflow Console Draft Authoring Workbench Design

Date: 2026-08-05

Status: Approved design for Workflow Console Slice 2.

Related:

- [Workflow Console IDE](2026-08-04-workflow-console-ide-design.md)
- [Workflow Console workspace foundation](../../historical/superpowers/plans/2026-08-04-workflow-console-workspace-foundation.md)
- [Capability step update](2026-07-26-capability-step-update-design.md)
- [Atomic step output bindings](2026-07-23-atomic-step-output-bindings-design.md)
- [Current roadmap](../../current_roadmap.md)

## Goal

Turn the read-only draft route into the first real workflow-authoring surface.
A human operator can discover a capability, create or select a draft, add the
capability to the visible workflow graph, configure it through generated
schema fields, edit an existing capability node, set its incoming route, and
validate the resulting canonical draft without leaving the workbench.

This slice also establishes shared schema-form primitives for later deployment
bindings, run inputs, interrupts, and route-specific lifecycle inspectors.

## Scope Decision

This is an authoring-first bridge slice. It includes:

- Inspector-style schema presentation in Discover;
- empty and capability-seeded draft creation;
- capability-node insertion and update;
- incoming route creation or replacement;
- explicit draft validation;
- one persistent graph/palette/inspector workspace; and
- desktop and mobile real-server acceptance.

It does not redesign artifact, deployment, or run pages. Those pages will use
the stable schema and graph primitives in a later independent slice.

## Product Layout

`/console/drafts/:workspaceId` becomes a persistent tri-pane authoring
workbench:

```text
Capability palette | Workflow graph | Context inspector
```

The graph remains visible while a capability is selected or configured. The
right inspector is driven by the current selection:

- selected capability: configure a new capability node;
- selected capability node: edit that node;
- selected connector: configure its source outcome and target;
- canvas or no selection: draft summary, validation, and diagnostics;
- unsupported step kind: read-only step inspection.

The draft index keeps its current read-only list and adds **New draft**.
Discover adds **Add to draft**, which chooses an existing draft or creates a
new capability-seeded draft before navigating to the workbench with the
capability selected.

### Responsive Behavior

Desktop keeps all three panes visible. The graph receives the flexible center
column; the palette and inspector have bounded widths and independent scrolling.

Mobile keeps the graph primary. The capability palette and context inspector
open as full-height sheets. Opening or closing a sheet does not clear graph
selection or unsent form edits. Graph pan and zoom remain touch-safe.

## Shared Schema Form

The console follows the MCP Inspector interaction model rather than presenting
JSON Schema as the primary UI. The implementation is source-owned and composed
from the console's existing shadcn/Radix controls. It does not import the MCP
Inspector application.

The module has three boundaries:

```text
JSON Schema -> SchemaField model -> field controls -> authoring bindings
```

The normalized `SchemaField` model preserves:

- property path;
- title and description;
- primitive or container type;
- required state;
- explicit default;
- enum values;
- nested object properties;
- array item schema; and
- a reason when the schema cannot be represented natively.

The initial native controls cover strings, multiline strings, numbers,
integers, booleans, enums, nested objects, and arrays. Unsupported unions,
conditionals, or unresolved references use a field-scoped JSON editor with an
explicit explanation. A collapsed raw-schema view remains available for
evidence and debugging.

### Serialization Semantics

The form follows these rules:

- omit empty optional fields;
- preserve explicit defaults when selected, including `null`;
- preserve required fields even when locally incomplete so the server can
  return canonical diagnostics;
- parse primitive controls before submission;
- preserve nested property paths; and
- never reinterpret an unconstrained schema as an object schema.

The client checks required presence, primitive parsing, enum selection, and
malformed binding paths. The backend remains authoritative for JSON Schema
validation, schema projection, compatibility, routing, draft validity, and
revision conflicts.

## Capability Input Sources

Every capability input field has a compact source mode:

```text
Literal | Bind
```

Literal mode renders the native schema control. Bind mode offers permitted
workflow input, state, or context sources. Candidate sources are presented as
schema-informed suggestions, not accepted locally as canonical compatibility.
The backend validates and projects the chosen binding atomically.

Bindings preserve their canonical source and target paths. A server diagnostic
that names a field or path is attached to that control. Diagnostics that cannot
be matched remain visible in the draft diagnostics panel.

## Graph Authoring

The workbench uses the existing `@xyflow/react` graph boundary and established
console node vocabulary. It must not add a second manually positioned graph.

Normal action nodes, typed human boundaries, and terminal nodes remain visually
distinct. Route outcome labels are visible and selectable. The graph selection
is browser-only state; the draft graph and revision come from the backend.

### Adding A Node

The operator selects a capability and optionally selects an insertion point:

- selected node or connector: insert the new node after that point, using an
  explicit source step and outcome;
- no insertion point: add an unconnected node and display the resulting
  backend diagnostic instead of guessing connectivity.

The inspector collects node id, description, retry, timeout, input bindings,
output bindings, and incoming route information. **Add node** sends one atomic
operation. On success, the returned canonical draft and revision replace the
displayed graph, and the new node becomes selected.

### Editing A Node

Selecting an existing capability node opens the same generated form populated
from canonical step data. **Apply changes** sends one atomic capability-step
update. Unsupported step kinds remain read-only.

### Routes

Selecting a connector opens the route inspector. The operator may replace its
source outcome target through the canonical route operation. Route deletion is
deferred.

## Persistence And Concurrency

Form edits are local and explicitly dirty. The console does not autosave.

Every mutation:

1. includes the currently loaded draft revision;
2. is sent through a typed authoring client and shared write executor;
3. verifies that the response operation matches the request;
4. records request, response, duration, equivalent CLI, and failure evidence;
5. ignores a response from an obsolete target or connection generation; and
6. replaces the workbench with the returned canonical draft only on success.

Revision conflicts preserve local form values and present a reload/reapply
choice. General failures preserve the form and map typed diagnostics to the
field, node, connector, or draft panel that owns them. Navigation with dirty
edits requires confirmation.

## Domain And Transport Boundaries

React components do not call `callOperation` or own operation-name strings.
The workspace domain adds a typed draft-authoring client above the shared
executor boundary.

The browser server independently allows exactly these authoring operations:

- `workflow.draft_workspaces.create_empty`;
- `workflow.draft_workspaces.create_from_capability`;
- `workflow.draft_workspaces.add_step_from_capability`;
- `workflow.draft_workspaces.update_capability_step`;
- `workflow.draft_workspaces.set_route`; and
- `workflow.draft_workspaces.validate`.

Generic patching, document replacement/import, deletion, artifact creation,
deployment or run mutations, and administration operations remain rejected by
the browser policy. Positive tests cover every allowed payload. Negative tests
pin representative generic patch, deletion, artifact, deployment, run, and
admin operations.

## User Flows

### Start From Discover

1. Select a capability.
2. Inspect its generated input/output contract.
3. Choose **Add to draft**.
4. Select an existing draft or create a capability-seeded draft.
5. Navigate to the workbench with the capability selected.
6. Configure and add it while the target graph remains visible.

### Start From Drafts

1. Choose **New draft**.
2. Enter workspace id, name, and title.
3. Create the empty canonical workspace.
4. Navigate to its workbench.
5. Select capabilities from the persistent palette and build the graph.

### Edit And Validate

1. Select an existing capability node.
2. Change literal values or bindings.
3. Apply one atomic update.
4. Select **Validate draft**.
5. Follow diagnostics back to graph nodes and generated fields.

## Evidence

All reads and mutations use the existing persistent evidence ledger. A mutation
receipt includes operation, duration, equivalent CLI, request, response, and
normalized failure details. Raw schema and draft JSON are collapsed escape
hatches and do not replace interpreted UI.

## Testing

### Unit And Component Tests

- JSON Schema normalization for primitives, objects, arrays, enums, defaults,
  required fields, unconstrained schemas, and unsupported constructs;
- form serialization, optional omission, explicit defaults, and nested paths;
- literal/binding mode changes and server-diagnostic mapping;
- authoring client payload lowering and response decoding;
- browser allowlist positive and negative cases;
- graph projection, node/connector selection, and insertion context;
- add/update/route/validate success and failure;
- revision conflict and dirty-navigation behavior;
- stale target and stale mutation response rejection;
- Discover and Draft index handoff into the workbench; and
- accessible desktop panes and mobile sheets.

### Real-Server Acceptance

A self-owned Playwright harness will:

1. start isolated Python RPC and built web servers;
2. create an empty draft;
3. add a capability as the first node;
4. add another capability after a selected node and outcome;
5. edit the capability node;
6. set a route;
7. validate the draft;
8. reload its direct URL; and
9. verify the persisted graph, revision, diagnostics, and evidence receipts.

The acceptance runs at desktop and mobile viewports and terminates only its own
recorded process trees.

## Deferred

- node or route deletion;
- arbitrary non-capability step creation;
- undo and redo;
- collaborative editing;
- artifact creation;
- deployment and run mutations;
- full artifact, deployment, and run view redesign; and
- local implementation of complete JSON Schema validation.

The next independent console slice will redesign artifact, deployment, and run
inspection using the schema and graph primitives established here.

## Success Criteria

- Capability selection, graph context, and generated configuration are visible
  in one workbench.
- A user can create a draft and add or edit capability nodes without raw JSON.
- Node insertion uses an explicit selected route outcome or remains visibly
  unconnected.
- The graph updates only from canonical backend mutation results.
- Discover uses interpreted schema controls and can hand off to authoring.
- Every mutation is independently authorized, typed, evidenced, and protected
  against stale targets and revisions.
- Desktop and mobile real-server acceptance passes.
