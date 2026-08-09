# Workflow Console Selected-Step Dataflow Design

Date: 2026-08-09

Status: Approved design for Workflow Console Slice 3.

Related:

- [Workflow Console draft authoring workbench](2026-08-05-workflow-console-draft-authoring-workbench-design.md)
- [Atomic step input bindings](2026-07-22-atomic-step-input-bindings-design.md)
- [Atomic step output bindings](2026-07-23-atomic-step-output-bindings-design.md)
- [Capability step update](2026-07-26-capability-step-update-design.md)
- [Current roadmap](../../current_roadmap.md)

## Goal

Make capability-step dataflow fully editable from the console. An operator can
inspect and atomically replace ordered step inputs, bind capability outputs into
workflow state, and edit optional execution metadata without using raw JSON.

This slice deepens the existing selected-step inspector. It does not introduce
a second editable graph model or broaden into workflow-level contract editing.

## Roadmap Context

The remaining graph-authoring work is split into independently useful slices:

1. selected-step input and output dataflow;
2. workflow Input, State, and Outcomes contract projections;
3. explicit End authoring and a typed Add step palette;
4. typed interrupt, control, subgraph, foreach, and join forms; and
5. direct graph gestures lowered through the same canonical mutations.

This document specifies only the first item.

## Scope

Slice 3 includes:

- separate selected-step Setup, Inputs, and Outputs inspector views;
- ordered canonical path and literal input bindings;
- ordered capability-output-to-state bindings;
- schema-informed source and target choices;
- automatic projection of missing state fields from capability output schemas;
- presence-aware retry and timeout editing;
- revision conflict preservation and reapply;
- operation evidence for every mutation; and
- the two focused binding operations in the authored TypeScript and browser
  boundary.

Slice 3 excludes:

- manual workflow input, state, or output schema replacement;
- final workflow output projection;
- non-capability step creation or editing;
- direct drag-to-bind;
- state-field deletion; and
- dataflow edges that require the future State contract graph node.

## Inspector Composition

Selecting a capability step shows three compact tabs:

### Setup

Setup edits description, retry count, and timeout. Step id and capability
reference remain visible but read-only. Changing the capability itself remains
an explicit remove/add operation.

Metadata is presence-aware:

- adding a step with blank retry or timeout omits that field;
- editing an absent value without touching it sends no update for that field;
- clearing an existing value sends explicit `null`;
- retry accepts integers greater than or equal to zero; and
- timeout accepts values greater than zero or remains absent.

The UI must never require operators to enter `0` in blank optional controls to
make a mutation submit.

### Inputs

Inputs replace the complete ordered canonical input-binding list. Each row has:

- a capability-local target derived from the capability input schema;
- a source mode of Path or Value;
- an `input.*` or `state.*` graph path in Path mode;
- a schema-driven literal editor in Value mode; and
- remove and reorder controls.

Explicit `null`, nested local targets, whole-payload projection, repeated source
fan-out, and mixed path/literal bindings preserve their canonical forms. The UI
does not lower these records into the lossy compatibility input map.

### Outputs

Outputs replace the complete ordered canonical step-output binding list. Each
row has:

- a source derived from the capability output schema;
- a `state.*` target path;
- a schema summary for the source; and
- remove and reorder controls.

Existing state paths are suggested. A new target previews the state field schema
that the backend will project from the selected capability output. Repeated
sources remain valid for fan-out. Submitting an empty list deliberately clears
the step output bindings but does not silently delete state declarations that
already exist.

## Canonical Dataflow

The returned draft remains the only graph document. Components edit local form
models, then submit complete canonical binding lists. On success, the returned
draft, diagnostics, status, and revision replace the workbench state.

```text
canonical draft + capability schemas
  -> selected-step form projection
  -> local ordered binding rows
  -> focused revision-checked mutation
  -> returned canonical draft
  -> inspector and graph reprojection
```

Slice 3 may show compact input/output binding summaries on a graph node. It does
not invent temporary state nodes or browser-only dataflow edges. Binding edges
arrive with the real State contract projection in Slice 4.

## Module Boundaries

The workspace domain exposes focused selected-step mutations through the
existing draft-authoring client. React components do not own operation names or
call the transport directly.

The selected-step form projection is a pure module that:

- parses canonical bindings from keyed or compiled draft shapes;
- preserves binding order and repeated sources;
- returns explicit unsupported reasons rather than guessing malformed shapes;
- derives schema-informed field choices from capability detail and workflow
  contracts; and
- serializes form rows back to canonical transport records.

The draft-authoring controller remains the single mutation module. Setup,
Inputs, and Outputs are separate form surfaces but share revision checking,
pending state, evidence, conflict retention, reload, and reapply behavior.

## TypeScript And Browser Boundary

The checked contract manifest already contains:

- `workflow.draft_workspaces.set_step_input_bindings`; and
- `workflow.draft_workspaces.set_step_output_bindings`.

Slice 3 makes those operations callable through the authored Effect RPC group,
method registry, console operation union, service dispatch, and Hono browser
allowlist. Runtime payload and success schemas come from the checked generated
contract through the existing supported schema translator. The implementation
must not hand-write duplicate transport schemas.

The browser allowlist remains explicit. Adding these two focused draft
operations must not expose generic patching, replacement/import, deletion,
artifact, deployment, run, source-admin, or secret operations.

## Validation And Errors

Client validation covers errors that are local and unambiguous:

- blank or malformed paths;
- unsupported source roots;
- duplicate local targets where canonical semantics forbid them;
- invalid retry or timeout values;
- malformed literal values; and
- incomplete binding rows.

The workflow API remains authoritative for schema projection, compatibility,
overlap, semantic validation, draft validity, and revision conflicts.

Server diagnostics attach to the owning binding row when their path identifies
one. Unmatched diagnostics remain visible in the draft diagnostics panel. A
semantically invalid but persisted draft still replaces the displayed canonical
draft and shows its invalid status. Transport failures preserve the last
confirmed draft and all local edits.

Revision conflicts retain the exact active tab and ordered local rows. Reload
discards local edits in favor of the server draft. Reapply reruns the same
focused mutation against the refreshed revision.

## Evidence And Truthfulness

Every mutation records the operation name, bounded request and response,
duration, target, equivalent CLI guidance, and failure details through the
shared write executor. The UI must distinguish:

- unsaved local rows;
- a pending mutation;
- a confirmed canonical draft;
- a persisted invalid draft with diagnostics; and
- a failed or conflicted mutation that did not replace confirmed state.

## Responsive And Accessible Behavior

Desktop keeps the graph visible while the inspector tab changes. Each tab owns
its vertical scrolling and keeps its primary save action reachable.

Mobile continues to use the existing context-inspector sheet. Closing and
reopening the sheet preserves selection, active tab, binding order, and unsaved
rows. Reorder controls have button alternatives and do not require drag.

Binding rows use fieldsets or labelled groups. Source mode, source, target,
schema summary, row errors, and remove/reorder actions have stable accessible
names. Status and conflict changes use the existing live regions.

## Verification

The implementation must include:

- generated-schema parity tests for both newly authored RPC operations;
- service dispatch and browser allowlist positive tests;
- browser allowlist negative tests for representative unrelated mutations;
- exact client payload tests for ordered bindings and metadata
  omitted/null/value semantics;
- pure projection tests for nested paths, literals, explicit null, fan-out,
  whole-payload bindings, malformed stored data, and empty lists;
- controller tests for success, invalid persisted drafts, failures, stale
  responses, conflicts, reload, and reapply;
- inspector tests for all tabs, row editing, reorder alternatives, inferred
  state previews, clearing, diagnostics, and optional metadata;
- responsive sheet regression coverage; and
- a real-server browser smoke that selects a `wf.*` capability step, replaces
  inputs and outputs, and confirms the returned revision and projected state
  contract.

Focused tests, the full console test suite, TypeScript typecheck, production
build, React Doctor changed-scope scan, and `git diff --check` are completion
gates.

