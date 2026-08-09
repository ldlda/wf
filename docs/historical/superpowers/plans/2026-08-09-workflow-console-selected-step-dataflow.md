# Workflow Console Selected-Step Dataflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let console operators inspect and atomically replace capability-step input bindings, output-to-state bindings, and optional execution metadata without editing raw JSON.

**Architecture:** Extend the existing authored Effect/browser operation seam with the two focused binding methods already present in the checked contract manifest. Parse canonical draft data into pure selected-step projections, submit complete ordered binding lists through the shared draft-authoring client/controller, and render three inspector tabs that always rehydrate from the returned canonical draft.

**Tech Stack:** React 19, TypeScript, Effect RPC, generated workflow contract schemas, Valibot domain decoders, Vite/Vitest, Testing Library, Hono browser proxy, Playwright/Chrome smoke testing.

## Global Constraints

- The returned canonical draft is the only editable workflow document; do not add browser-owned graph persistence.
- Use `runtimeSchemasFor(...)` and the checked generated workflow contract; do not hand-write duplicate transport schemas.
- Input and output binding replacement preserves list order, nested paths, literals, explicit null, whole-payload bindings, and repeated-source fan-out.
- New output targets are projected into workflow state by the existing backend operation; the browser does not synthesize state schema patches.
- Blank retry and timeout values are optional. Retry accepts integer `0` or greater; timeout accepts values greater than `0` or remains absent.
- Keep the browser operation allowlist explicit and fail closed for unrelated mutations.
- Direct drag-to-bind, workflow-level contracts, non-capability steps, state deletion, and dataflow graph edges are out of scope.
- Preserve revision checks, target provenance, operation evidence, conflict reload/reapply, mobile sheets, and accessible keyboard alternatives.
- Use TDD for every task. Do not modify Serena configuration.

---

## File Structure

### Transport Boundary

- `src/wf_core/models/steps.py`: canonical recursive JSON literal type for input value bindings.
- `tests/core/test_canonical_node_bindings.py`: JSON literal model/schema coverage.
- `tests/wf_contract_manifest/test_generate.py`: generated manifest coverage for literal JSON values.
- `contracts/workflow-api.manifest.json`: regenerated neutral workflow contract.
- `web/packages/rpc/scripts/workflow-contract-generator.ts`: authored runtime operation cohort.
- `web/packages/rpc/scripts/workflow-contract-generator.test.ts`: runtime cohort generation coverage.
- `web/packages/rpc/src/generated/workflow-contract.ts`: regenerated TypeScript contract.
- `web/packages/rpc/src/rpcs.ts`: authored Effect RPC definitions generated from checked schemas.
- `web/packages/rpc/src/service.ts`: operation dispatch to the JSON-RPC client.
- `web/packages/rpc/src/method-registry.ts`: labels, interpretations, and equivalent CLI evidence.
- `web/packages/rpc/src/index.ts`: public exports.
- `web/apps/console/src/connection/contracts.ts`: browser response operation decoder.
- `web/apps/server/src/browser-operation-policy.ts`: explicit browser allowlist.

### Workspace Domain

- `web/apps/console/src/workspace/domain/draft-workspace-models.ts`: canonical binding and focused mutation input types.
- `web/apps/console/src/workspace/domain/draft-authoring-client.ts`: transport-neutral selected-step mutation interface.
- `web/apps/console/src/workspace/authoring/selected-step-dataflow.ts`: pure draft/schema projection and form serialization.
- `web/apps/console/src/workspace/authoring/useDraftAuthoring.ts`: mutation lifecycle, conflict preservation, and reapply.

### React Surfaces

- `web/apps/console/src/workspace/authoring/CapabilitySetupForm.tsx`: presence-aware metadata patch form.
- `web/apps/console/src/workspace/authoring/StepInputBindingsForm.tsx`: ordered path/literal input editor.
- `web/apps/console/src/workspace/authoring/StepOutputBindingsForm.tsx`: ordered output-to-state editor and inferred-schema preview.
- `web/apps/console/src/workspace/authoring/SelectedCapabilityInspector.tsx`: Setup/Inputs/Outputs tab composition.
- `web/apps/console/src/workspace/authoring/ContextInspector.tsx`: selection routing only.
- `web/apps/console/src/workspace/authoring/authoring-graph.ts`: compact binding-count summary on capability nodes.
- `web/apps/console/src/graph/graph-model.ts`: optional node summary carried through the shared graph model.
- `web/apps/console/src/graph/WorkflowGraph.tsx`: render the optional node summary.
- `web/apps/console/src/styles/global.css`: inspector tabs, ordered rows, responsive controls, and node summary styling.

---

### Task 1: Author The Two Binding RPC Operations

**Files:**

- Modify: `web/packages/rpc/src/rpcs.ts`
- Modify: `web/packages/rpc/src/service.ts`
- Modify: `web/packages/rpc/src/method-registry.ts`
- Modify: `web/packages/rpc/src/index.ts`
- Modify: `web/packages/rpc/src/service.test.ts`
- Modify: `web/packages/rpc/src/method-registry.test.ts`
- Modify: `web/packages/rpc/src/json-schema/runtime-schema.test.ts`
- Modify: `web/packages/rpc/src/json-schema/rpc-parity.test.ts`
- Modify: `web/packages/rpc/src/json-schema/authored-rpc-fixtures.ts`
- Modify: `web/packages/rpc/scripts/workflow-contract-generator.ts`
- Modify: `web/packages/rpc/scripts/workflow-contract-generator.test.ts`
- Modify: `src/wf_core/models/steps.py`
- Modify: `tests/core/test_canonical_node_bindings.py`
- Modify: `tests/wf_contract_manifest/test_generate.py`
- Regenerate: `contracts/workflow-api.manifest.json`
- Regenerate: `web/packages/rpc/src/generated/workflow-contract.ts`
- Modify: `web/apps/console/src/connection/contracts.ts`
- Modify: `web/apps/server/src/browser-operation-policy.ts`
- Modify: `web/apps/server/src/browser-operation-policy.test.ts`
- Modify: `web/apps/server/src/app.test.ts`

**Interfaces:**

- Produces: callable operations `workflow.draft_workspaces.set_step_input_bindings` and `workflow.draft_workspaces.set_step_output_bindings`.
- Produces: payload/result schema exports named `WorkflowDraftWorkspacesSetStepInputBindingsPayloadSchema`, `WorkflowDraftWorkspacesSetStepInputBindingsResultSchema`, `WorkflowDraftWorkspacesSetStepOutputBindingsPayloadSchema`, and `WorkflowDraftWorkspacesSetStepOutputBindingsResultSchema`.
- Preserves: the explicit browser policy independent from generated operation inventory.

- [ ] **Step 1: Write failing canonical JSON-literal and generator tests**

Add model and manifest tests proving `InputValueBinding.value` accepts and
describes every JSON value category: string, number, boolean, null, array, and
object. The generated TypeScript `InputValueBinding["value"]` must be a
recursive JSON value, not `{ [key: string]: unknown }`.

Replace the object-only `InputValueBindingSchema.value` in
`authored-rpc-fixtures.ts` with the same recursive JSON-value semantics. Add
fixture decode assertions for scalar, null, array, and object literals so
parity cannot pass with a narrower authored reference.

Extend `workflow-contract-generator.test.ts` so removing either focused binding
operation from the complete fixture fails with `missing runtime operation`, and
so both operation names and their reachable binding schemas appear in
`workflowRuntimeContract`.

- [ ] **Step 2: Run the contract tests and verify RED**

Run:

```powershell
uv run pytest tests/core/test_canonical_node_bindings.py tests/wf_contract_manifest/test_generate.py -q
pnpm --dir web --filter @lda/workflow-rpc test -- scripts/workflow-contract-generator.test.ts
```

Expected: failures because unconstrained Python `object` generates an
object-only TypeScript value and the two methods are absent from the runtime
operation cohort.

- [ ] **Step 3: Repair the canonical contract and regenerate checked outputs**

Define one recursive JSON-value alias at the canonical binding model seam and
use it for `InputValueBinding.value`. Keep booleans distinct from integers in
tests and reject non-JSON Python objects. Add both focused methods to
`runtimeOperationNameList`.

Regenerate in dependency order:

```powershell
uv run python -m wf_contract_manifest write
pnpm --dir web --filter @lda/workflow-rpc contract:write
pnpm --dir web --filter @lda/workflow-rpc contract:check
```

Do not edit either generated file manually.

- [ ] **Step 4: Write failing RPC service and registry tests**

Add representative cases to `service.test.ts`:

```ts
{
  operation: "workflow.draft_workspaces.set_step_input_bindings" as const,
  params: {
    workspace_id: "console.demo",
    revision: 3,
    step_id: "render",
    bindings: [
      { path: "input.title", target: "report.title" },
      { target: "format", value: "markdown" },
    ],
  },
  result: draftWorkspaceResult,
},
{
  operation: "workflow.draft_workspaces.set_step_output_bindings" as const,
  params: {
    workspace_id: "console.demo",
    revision: 4,
    step_id: "render",
    bindings: [{ source: "report", target: "state.report" }],
  },
  result: draftWorkspaceResult,
},
```

Add registry assertions that input bindings render `wf draft set-input` and
output bindings render `wf draft set-output`. Add dedicated evidence renderers
for these replacement commands: the existing add-capability renderer's
`--input` syntax must remain unchanged. Use `--clear` for an empty list; use
repeated `--map`/`--value` only when exactly representable, otherwise mark the
CLI evidence non-equivalent and point to `--bindings-file`.

- [ ] **Step 5: Write failing policy and contract tests**

Extend `browser-operation-policy.test.ts` to require both focused methods and
continue rejecting `workflow.draft_workspaces.replace_document`,
`workflow.draft_workspaces.remove_step`, and `workflow.admin.auth.list`.

Extend `app.test.ts` with one accepted request per operation. Extend runtime
schema and RPC parity tests so both payload and success sides translate from
the checked manifest and enforce exact canonical binding unions. Add matching
entries to `authored-rpc-fixtures.ts`; parity coverage must compare both
generated schemas against those authored reference schemas.

- [ ] **Step 6: Run the focused tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/workflow-rpc test -- src/service.test.ts src/method-registry.test.ts src/json-schema/runtime-schema.test.ts src/json-schema/rpc-parity.test.ts
pnpm --dir web --filter @lda/server test -- src/browser-operation-policy.test.ts src/app.test.ts
```

Expected: failures because the two operations are not in `WorkflowRpcs`,
service dispatch, registry metadata, browser contracts, or browser policy.

- [ ] **Step 7: Implement the authored RPC definitions and dispatch**

Follow the existing update-capability pattern in `rpcs.ts`:

```ts
const setStepInputBindingsSchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.set_step_input_bindings",
);
export const WorkflowDraftWorkspacesSetStepInputBindingsPayloadSchema =
  setStepInputBindingsSchemas.payload;
export const WorkflowDraftWorkspacesSetStepInputBindingsResultSchema =
  setStepInputBindingsSchemas.success;
export const WorkflowDraftWorkspacesSetStepInputBindings = Rpc.make(
  "workflow.draft_workspaces.set_step_input_bindings",
  {
    payload: WorkflowDraftWorkspacesSetStepInputBindingsPayloadSchema,
    success: WorkflowDraftWorkspacesSetStepInputBindingsResultSchema,
    error: Schema.Never,
  },
);
```

Create the matching output definition. Add both to `WorkflowRpcs`, service
imports/switch cases, registry metadata, and public exports. Decode parameters
before dispatch exactly like existing draft operations.

- [ ] **Step 8: Open only the narrow browser seam**

Add both names to `OperationNameSchema` and `browserAllowedOperationNames`.
Update tests in the same authored order. Do not derive the browser list from
generated `WorkflowOperationName`.

- [ ] **Step 9: Run focused verification and commit**

Run the focused commands from Step 6 plus:

```powershell
pnpm --dir web --filter @lda/workflow-rpc typecheck
pnpm --dir web --filter @lda/server typecheck
```

Expected: all pass.

Commit:

```powershell
git add web/packages/rpc web/apps/console/src/connection/contracts.ts web/apps/server/src
git add src/wf_core/models/steps.py tests/core/test_canonical_node_bindings.py tests/wf_contract_manifest/test_generate.py contracts/workflow-api.manifest.json
git commit -m "feat: expose canonical step binding RPCs"
```

---

### Task 2: Project Canonical Selected-Step Dataflow

**Files:**

- Modify: `web/apps/console/src/workspace/domain/draft-workspace-models.ts`
- Create: `web/apps/console/src/workspace/authoring/selected-step-dataflow.ts`
- Create: `web/apps/console/src/workspace/authoring/selected-step-dataflow.test.ts`
- Modify: `web/apps/console/src/workspace/authoring/canonical-capability-form.ts`
- Create: `web/apps/console/src/workspace/authoring/canonical-capability-form.test.ts`

**Interfaces:**

- Produces: `StatePath`, `OutputBinding`, `SetStepInputBindingsInput`, and `SetStepOutputBindingsInput` domain types.
- Produces: `SelectedStepDataflow`, `projectSelectedStepDataflow(draft, stepId)`, `inputBindingRows(...)`, `outputBindingRows(...)`, and canonical row serializers.
- Produces: `bindingDiagnosticsForStep(...)` for row-owned and unmatched diagnostics.
- Produces: `CapabilitySetupPatch`, shared by the controller and Setup form.
- Produces: metadata presence that distinguishes absent, explicit null, and numeric values.

- [ ] **Step 1: Write failing pure projection tests**

Use both a keyed draft and the equivalent compiled `nodes[]` draft containing:

```ts
steps: {
  render: {
    use: "wf.std.concat",
    input: [
      { path: "input.items", target: "items" },
      { target: "separator", value: null },
      { path: "state.fallback", target: "fallback" },
    ],
    output: [
      { source: "text", target: "state.report" },
      { source: "text", target: "state.audit.latest" },
    ],
    retry: 0,
  },
},
```

Assert exact list order, explicit null, repeated output source, absent timeout,
and `retry: 0`. Add cases for structural path objects, whole payload `.`, empty
lists, malformed records with explicit unsupported reasons, and a missing step.
The keyed and compiled shapes must project to the same `SelectedStepDataflow`.

- [ ] **Step 2: Run the pure test and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/authoring/selected-step-dataflow.test.ts
```

Expected: failure because the module and output binding types do not exist.

- [ ] **Step 3: Add canonical domain types**

Add:

```ts
export type StatePath =
  | string
  | { readonly root: "state"; readonly parts: string[] };

export type OutputBinding = {
  readonly source: LocalInputPath;
  readonly target: StatePath;
};

export type SetStepInputBindingsInput = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly stepId: string;
  readonly bindings: ReadonlyArray<InputBinding>;
};

export type SetStepOutputBindingsInput = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly stepId: string;
  readonly bindings: ReadonlyArray<OutputBinding>;
};
```

- [ ] **Step 4: Implement parser-first projection**

Define a compound return type with a docstring:

```ts
export type SelectedStepDataflow = {
  readonly stepId: string;
  readonly capabilityName: string;
  readonly description: string | null | undefined;
  readonly retry: number | null | undefined;
  readonly timeoutSeconds: number | null | undefined;
  readonly inputs: ReadonlyArray<InputBinding>;
  readonly outputs: ReadonlyArray<OutputBinding>;
  readonly unsupported: ReadonlyArray<UnsupportedBindingRow>;
};

export type UnsupportedBindingRow = {
  readonly field: "input" | "output";
  readonly index: number;
  readonly raw: unknown;
  readonly reason: string;
};

export type CapabilitySetupPatch = {
  readonly description?: string | null;
  readonly retry?: number | null;
  readonly timeoutSeconds?: number | null;
};
```

Use type guards for records and structural path variants. Preserve valid rows
in order. Do not coerce malformed bindings into maps or discard them silently;
append an indexed unsupported reason so the inspector can block destructive
replacement until the operator acknowledges or repairs the raw shape.

Unsupported rows remain in their original positions as read-only raw previews
with an explicit `Remove unsupported row` action. A save stays blocked while
any unsupported row remains. Removing one is an explicit repair decision and
serializes the remaining canonical rows in their original relative order.

Although `StatePath` remains wire-compatible with generated types, output-row
serialization must reject bare `state`, `state.`, empty structural `parts`, and
empty path segments. Test canonical nested targets and each rejected form.

Update `canonical-capability-form.ts` so absent metadata remains `undefined`
instead of being collapsed to `null` by `?? null`.

- [ ] **Step 5: Add schema-informed suggestions and preview helpers**

Add pure helpers that return canonical strings:

```ts
workflowSourceSuggestions(inputSchema, stateSchema): ReadonlyArray<string>
capabilityLocalPathSuggestions(capabilitySchema): ReadonlyArray<string>
stateTargetSuggestions(stateSchema): ReadonlyArray<string>
inferredStateSchemaPreview(outputSchema, source, target): unknown | null
bindingDiagnosticsForStep(diagnostics, stepId, field): BindingDiagnostics
```

Reuse `normalizeSchema`, `parseTOMLPath`, and `formatTOMLPath`. Do not implement
JSON Schema compatibility in the browser; the preview only shows the selected
source schema the backend will project.

`BindingDiagnostics` contains row issues keyed by binding index plus unmatched
issues. Accept only these structural path forms:

- `nodes[N].input[M]...` / `nodes[N].output[M]...`, where `N` is the selected
  step's index in the compiled `nodes[]` array;
- `/steps/<escaped-id>/input/M/...` / `/steps/<escaped-id>/output/M/...`, using
  JSON Pointer escaping; and
- `bindings[M]...` only when `diagnostic.step_id` equals the selected step and
  the caller supplies the field for the focused operation.

Field-level paths without `M`, mismatched `step_id`, unknown formats, and prose
messages are unmatched. Forms receive row issues explicitly. Unmatched issues
remain in the shared ContextInspector diagnostics panel. Add positive and
negative tests for every accepted form.

- [ ] **Step 6: Verify and commit**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/authoring/selected-step-dataflow.test.ts src/workspace/authoring/canonical-capability-form.test.ts
pnpm --dir web --filter @lda/console typecheck
```

Commit:

```powershell
git add web/apps/console/src/workspace/domain/draft-workspace-models.ts web/apps/console/src/workspace/authoring/selected-step-dataflow.* web/apps/console/src/workspace/authoring/canonical-capability-form*
git commit -m "feat: project selected-step dataflow"
```

---

### Task 3: Add Focused Binding Methods To The Console Client

**Files:**

- Modify: `web/apps/console/src/workspace/domain/draft-authoring-client.ts`
- Modify: `web/apps/console/src/workspace/domain/draft-authoring-client.test.ts`

**Interfaces:**

- Consumes: `SetStepInputBindingsInput` and `SetStepOutputBindingsInput` from Task 2.
- Produces: `DraftAuthoringClient.setStepInputBindings(input)` and `DraftAuthoringClient.setStepOutputBindings(input)`.

- [ ] **Step 1: Write exact payload tests**

Add tests that call both client methods and assert:

```ts
expect(run).toHaveBeenCalledWith(
  "workflow.draft_workspaces.set_step_output_bindings",
  {
    workspace_id: "report",
    revision: 7,
    step_id: "render",
    bindings: [
      { source: "text", target: "state.report" },
      { source: "text", target: "state.audit.latest" },
    ],
  },
  decodeDraftWorkspace,
);
```

Cover explicit input null, structural paths, empty arrays, blank identifiers,
and caller-array immutability.

- [ ] **Step 2: Run the client test and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/domain/draft-authoring-client.test.ts
```

Expected: failures because the methods are absent.

- [ ] **Step 3: Implement minimal focused methods**

Use `requireIdentifier`, copy each binding record into a fresh array, pass the
current revision unchanged, and decode with `decodeDraftWorkspace`. Do not add
merge flags because the UI replaces complete canonical lists.

- [ ] **Step 4: Verify and commit**

Run the focused test and console typecheck.

Commit:

```powershell
git add web/apps/console/src/workspace/domain/draft-authoring-client.ts web/apps/console/src/workspace/domain/draft-authoring-client.test.ts
git commit -m "feat: add selected-step binding client"
```

---

### Task 4: Extend The Authoring Controller Without Losing Conflict State

**Files:**

- Modify: `web/apps/console/src/workspace/authoring/useDraftAuthoring.ts`
- Modify: `web/apps/console/src/workspace/authoring/useDraftAuthoring.test.tsx`

**Interfaces:**

- Consumes: focused client methods from Task 3.
- Produces: `setStepInputs(bindings)`, `setStepOutputs(bindings)`, `updateSetup(patch)`, and tab-scoped preserved submissions.
- Preserves: one pending mutation, revision conflict reload/reapply, target provenance, and selected node identity.

- [ ] **Step 1: Write failing controller tests for all three submissions**

Test a selected node named `render` and assert:

- `setStepInputs` uses the selected node id and current revision;
- `setStepOutputs` accepts repeated sources and commits the returned draft;
- `updateSetup({ retry: 0 })` sends only retry;
- `updateSetup({ timeoutSeconds: null })` clears an existing timeout;
- an untouched optional field is absent from the update object;
- duplicate clicks share the same pending promise;
- a second different mutation is rejected while one is pending; and
- stale-target responses do not replace the current draft.

- [ ] **Step 2: Write failing conflict/reapply tests**

Return a conflict draft, change selection, reload revision 8, and call reapply.
Assert the mutation still targets the original immutable step id and preserves
the exact ordered rows. Add one test each for input and output submissions.
Assert the preserved submission records its tab and exact serializable form
payload. Controller state owns the last submitted mutation for conflict
reapply; it does not own every unsaved keystroke.

- [ ] **Step 3: Run controller tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/authoring/useDraftAuthoring.test.tsx
```

- [ ] **Step 4: Generalize last submissions at the controller seam**

Extend `LastSubmission` with:

```ts
| { readonly kind: "setup"; readonly targetStepId: string; readonly patch: CapabilitySetupPatch }
| { readonly kind: "inputs"; readonly targetStepId: string; readonly bindings: ReadonlyArray<InputBinding> }
| { readonly kind: "outputs"; readonly targetStepId: string; readonly bindings: ReadonlyArray<OutputBinding> }
```

Keep `runMutation` as the one lifecycle implementation. Add a small helper that
captures the selected node id before submission. Reapply dispatches through
the same focused controller methods against the refreshed revision.

- [ ] **Step 5: Preserve submitted conflict state without stealing form ownership**

Keep the discriminated `LastSubmission` as the exact submitted Setup, Inputs,
or Outputs payload. `SelectedCapabilityInspector`, keyed by selected `stepId`,
owns active tab and unsaved controlled rows. The existing mobile sheet remains
mounted while closed, so closing/reopening preserves these values. Reset local
forms only when selection changes, the operator explicitly reloads, or a
confirmed canonical response is adopted. On conflict, keep local values and
use `LastSubmission` for the explicit reapply action. Document this split near
the controller state seam.

- [ ] **Step 6: Verify and commit**

Run the focused tests and console typecheck.

Commit:

```powershell
git add web/apps/console/src/workspace/authoring/useDraftAuthoring.ts web/apps/console/src/workspace/authoring/useDraftAuthoring.test.tsx
git commit -m "feat: control selected-step dataflow mutations"
```

---

### Task 5: Build Presence-Aware Setup And Ordered Input Forms

**Files:**

- Create: `web/apps/console/src/workspace/authoring/CapabilitySetupForm.tsx`
- Create: `web/apps/console/src/workspace/authoring/CapabilitySetupForm.test.tsx`
- Create: `web/apps/console/src/workspace/authoring/StepInputBindingsForm.tsx`
- Create: `web/apps/console/src/workspace/authoring/StepInputBindingsForm.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/CapabilityNodeForm.tsx`
- Modify: `web/apps/console/src/workspace/authoring/CapabilityNodeForm.test.tsx`
- Modify: `web/apps/console/src/workspace/schema-form/schema-field.ts`
- Modify: `web/apps/console/src/workspace/schema-form/schema-field.test.ts`

**Interfaces:**

- Consumes: `CapabilitySetupPatch` from Task 2 with omitted/null/value metadata semantics.
- Produces: `StepInputBindingsForm` that submits a complete `ReadonlyArray<InputBinding>`.
- Consumes: input-row issues from `bindingDiagnosticsForStep(...)`; unmatched diagnostics remain outside the form.
- Reuses: normalized schema fields and `SchemaFieldControl` for literal editing.

- [ ] **Step 1: Pin the optional metadata regression**

Add a `CapabilityNodeForm` test that leaves retry and timeout blank, submits a
valid capability input, and expects both keys to be absent from the add value.
Add Setup tests for untouched blank, clearing an existing value, retry `0`,
rejected retry `-1`, rejected fractional retry, rejected timeout `0`, and valid
positive timeout.

- [ ] **Step 2: Write failing ordered input editor tests**

Render initial path, literal-null, and nested-target rows. Assert accessible
controls for target, source mode, source path/value, move up, move down, remove,
and add. Reorder rows and assert exact submission order. Select one source for
two targets and assert fan-out is preserved. Submit `[]` through an explicit
clear action.

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/authoring/CapabilityNodeForm.test.tsx src/workspace/authoring/CapabilitySetupForm.test.tsx src/workspace/authoring/StepInputBindingsForm.test.tsx
```

- [ ] **Step 4: Implement presence-aware setup values**

Use touched-field state rather than deriving patch presence from blank text:

For add-node `CapabilityNodeForm`, omit blank optional metadata. Preserve the
ability to add a step with explicit `retry: 0`. Use `min={0}`/`step={1}` for
retry and `min` greater than zero for timeout, plus explicit parser messages so
native validity is not the only error surface.

- [ ] **Step 5: Expose schema field lookup for literal rows**

Add a pure `schemaFieldAtPath(root, path)` helper to `schema-field.ts`. Test
nested object, array, `.`, and missing paths. `StepInputBindingsForm` uses the
matched field with `SchemaFieldControl`; an unmatched target falls back to a
labelled JSON value editor with an explicit explanation.

- [ ] **Step 6: Implement controlled ordered rows**

Keep stable row ids separate from canonical data. Convert rows to canonical
bindings only on change/submit. Validate:

- local target is nonblank;
- path source starts with `input.`, `state.`, or `context.`;
- a row contains exactly one of path or value; and
- canonical duplicates/overlaps remain server-authoritative unless locally
  unambiguous.

Buttons provide reorder behavior; do not add drag sorting.

- [ ] **Step 7: Verify and commit**

Run focused tests, console typecheck, and React Doctor changed scope.

Commit:

```powershell
git add web/apps/console/src/workspace/authoring/CapabilityNodeForm* web/apps/console/src/workspace/authoring/CapabilitySetupForm* web/apps/console/src/workspace/authoring/StepInputBindingsForm* web/apps/console/src/workspace/schema-form/schema-field*
git commit -m "feat: edit capability setup and inputs"
```

---

### Task 6: Build The Output-To-State Binding Form

**Files:**

- Create: `web/apps/console/src/workspace/authoring/StepOutputBindingsForm.tsx`
- Create: `web/apps/console/src/workspace/authoring/StepOutputBindingsForm.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**

- Consumes: `OutputBinding`, output/state suggestions, and inferred preview helpers from Task 2.
- Produces: complete ordered `ReadonlyArray<OutputBinding>` submissions.
- Consumes: output-row issues from `bindingDiagnosticsForStep(...)`; unmatched diagnostics remain outside the form.

- [ ] **Step 1: Write failing output form tests**

Cover:

- source choices from capability output schema;
- target choices from existing state schema;
- a new nested `state.report.markdown` target;
- inferred source schema preview;
- repeated source fan-out;
- move up/down and remove;
- explicit empty-list clearing confirmation;
- malformed stored rows that block replacement instead of disappearing; and
- row-scoped backend diagnostics.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/authoring/StepOutputBindingsForm.test.tsx
```

- [ ] **Step 3: Implement the controlled output editor**

Source uses a select plus an escape-hatch text value for valid nested/whole
local paths not represented by top-level schema suggestions. Target accepts a
canonical `state.*` path and suggests existing fields. Render the inferred
schema as a bounded summary, with raw JSON collapsed.

Use explicit copy:

```text
Saving a new target asks the workflow API to project this output schema into
state. Clearing bindings does not delete existing state fields.
```

- [ ] **Step 4: Add responsive and accessible styling**

Rows use a readable grid on desktop and stack inside the mobile inspector
sheet. Keep add/save/clear actions reachable without horizontal scrolling.
Hide no scrollbar that is needed to discover overflow.

- [ ] **Step 5: Verify and commit**

Run focused tests, console typecheck, and React Doctor changed scope.

Commit:

```powershell
git add web/apps/console/src/workspace/authoring/StepOutputBindingsForm* web/apps/console/src/styles/global.css
git commit -m "feat: edit capability output bindings"
```

---

### Task 7: Compose The Selected-Step Inspector And Acceptance Path

**Files:**

- Create: `web/apps/console/src/workspace/authoring/SelectedCapabilityInspector.tsx`
- Create: `web/apps/console/src/workspace/authoring/SelectedCapabilityInspector.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/ContextInspector.tsx`
- Modify: `web/apps/console/src/workspace/authoring/ContextInspector.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/authoring-graph.ts`
- Modify: `web/apps/console/src/workspace/authoring/authoring-graph.test.ts`
- Modify: `web/apps/console/src/graph/graph-model.ts`
- Modify: `web/apps/console/src/graph/graph-model.test.ts`
- Modify: `web/apps/console/src/graph/WorkflowGraph.tsx`
- Modify: `web/apps/console/src/graph/WorkflowGraph.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/DraftWorkbench.test.tsx`
- Modify: `web/apps/console/src/workspace/routes/DraftDetailRoute.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-08-09-workflow-console-selected-step-dataflow.md` to `docs/historical/superpowers/plans/2026-08-09-workflow-console-selected-step-dataflow.md`

**Interfaces:**

- Consumes: Tasks 2–6.
- Produces: complete Setup/Inputs/Outputs selected-step workflow.
- Preserves: add-capability form, route inspector, canvas inspector, operation evidence, navigation protection, and mobile sheets.

- [x] **Step 1: Write failing composition tests**

Select a capability node and assert three tabs with Setup active initially.
Switch to Inputs and Outputs without clearing local rows. Submit each form and
assert the correct controller method, selected step id, and returned revision.
Add tests for loading/error capability detail, unsupported stored binding
shape, diagnostics, saving state, revision conflict, reload, and reapply.
Close and reopen the mounted mobile sheet and assert the active tab and unsaved
rows survive. Change the selected step and assert the inspector rehydrates from
that step's canonical data instead of leaking the previous form.

- [x] **Step 2: Write failing graph summary tests**

Project a node with two inputs and one output. Assert its graph detail is
`2 inputs · 1 state write`. Use singular forms for one and omit the summary for
zero/zero. Assert `buildWorkflowGraph` carries a distinct `summary` field and
the generic WorkflowGraph renders it without replacing the existing
description/detail, route-edge selection, or node handles.

- [x] **Step 3: Run integration tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/authoring/SelectedCapabilityInspector.test.tsx src/workspace/authoring/ContextInspector.test.tsx src/workspace/authoring/authoring-graph.test.ts src/graph/graph-model.test.ts src/graph/WorkflowGraph.test.tsx src/workspace/authoring/DraftWorkbench.test.tsx src/workspace/routes/DraftDetailRoute.test.tsx
```

- [x] **Step 4: Extract selected capability composition**

Move the selected-node capability branch out of `ContextInspector` into
`SelectedCapabilityInspector`. Keep selection routing and generic diagnostics
in `ContextInspector`. Use stable tab ids and `role="tablist"`, `role="tab"`,
and `role="tabpanel"`. Restore the active tab and preserved form after mobile
sheet close/reopen and conflict reapply.

- [x] **Step 5: Add truthful node summaries**

Set an authoring-only raw-node `summary` from canonical binding counts and carry
it into a new optional `WorkflowGraphNodeData.summary`. Render `data.summary`
below the node reference while preserving `data.detail` for descriptions. Do
not draw binding edges or State nodes in this slice.

- [ ] **Step 6: Run full automated verification**

Run:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
Push-Location web/apps/console
npx react-doctor@latest --verbose --scope changed
Pop-Location
git diff --check
```

Expected: all tests and typechecks pass; build succeeds with only previously
accepted warnings; React Doctor does not regress.

- [ ] **Step 7: Run real-server browser smoke**

With the console, Hono server, and `wf-rpc-server` running:

1. Connect the console to `http://127.0.0.1:8765/rpc`.
2. Open a disposable draft containing a `wf.std.constant` or
   `wf.std.concat` capability step.
3. Confirm blank retry and timeout submit without entering zero.
4. Replace ordered input bindings, including one literal.
5. Bind one capability output to two `state.*` targets.
6. Confirm the returned revision increments and the state schema includes new
   projected targets.
7. Reload the route and confirm canonical rows persist in the same order.
8. Clear output bindings and confirm the state declarations remain.
9. Resize to the mobile breakpoint and confirm all tabs and reorder buttons
   remain usable.

Capture a screenshot and operation evidence for the input and output success
states under the gitignored `.visual-smoke/` directory.

- [x] **Step 8: Update live documentation and archive the plan**

Document selected-step Setup/Inputs/Outputs and canonical replacement behavior
in `web/README.md`. Mark Roadmap Slice 3 completed and retain Slices 4–7 as
planned. Move this completed plan to the historical path and update its roadmap
link.

- [x] **Step 9: Review and commit**

Run the requesting-code-review skill on the complete slice. Fix all valid
Critical and Important findings, rerun affected verification, then commit:

```powershell
git add web/apps/console web/README.md docs/current_roadmap.md docs/superpowers/specs/2026-08-09-workflow-console-selected-step-dataflow-design.md docs/historical/superpowers/plans/2026-08-09-workflow-console-selected-step-dataflow.md
git commit -m "feat: edit selected-step dataflow"
```
