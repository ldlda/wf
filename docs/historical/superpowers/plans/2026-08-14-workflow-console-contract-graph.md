# Workflow Console Contract Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make workflow Input, State, Output, and Outcomes selectable and editable in the console while one backend-owned inventory supplies discoverable source and target choices, including node-scoped runtime context.

**Architecture:** Add a deep, read-only authoring-contract inspection interface above canonical draft schemas, capability contracts, and core execution-scope analysis. Carry its generated contract into the existing Effect RPC and console domain layers, then use one reusable path picker and four graph projections to drive focused canonical mutations. Existing focused write operations remain authoritative; the browser does not invent a second workflow model.

**Tech Stack:** Python 3.14, Pydantic 2, JSON Schema Draft 2020-12, pytest, JSON-RPC/OpenRPC, generated workflow contract manifest, React 19, TypeScript, Effect Schema, Valibot, React Flow, Vitest, Testing Library, Vite.

## Global Constraints

- Input, State, Output, and Outcomes are derived graph projections, never persisted executable steps.
- Runtime context appears only when the backend reports applicable entries for the selected step; do not add a permanent Context graph projection.
- No high-level TypeScript module may hardcode runtime context key names.
- The current runtime exposes only the current foreach iteration alias; do not claim automatic inheritance of enclosing aliases.
- The normal UI is a searchable, grouped picker with labels, paths, types, and descriptions. Manual paths live under Advanced.
- The backend inventory is advisory for discoverability and obvious compatibility. Existing complete workflow validation remains authoritative.
- Preserve canonical ordered bindings, revision checks, conflict reapply, invalid-draft visibility, and mounted mobile-inspector state.
- Do not add step-id rename or a persisted per-step title. Existing step id remains the selected-step heading.
- Retry and timeout remain optional and presence-aware.
- Reuse existing focused operations for start, contract, and final output bindings. Do not introduce generic JSON Patch from the browser.
- Use checked generated transport schemas; do not hand-write duplicate wire contracts.
- Add comments/docstrings around graph-scope traversal, conservative availability, and unsupported-schema preservation.
- Do not modify Serena configuration.

---

## File Structure

### Core And Workflow API

- `src/wf_core/context_contracts.py`: canonical runtime-context keys and schema descriptions shared by execution and inspection.
- `src/wf_core/analysis/context_scopes.py`: conservative abstract graph traversal that projects context availability by node.
- `src/wf_core/runtime/ops/frames.py`: runtime value projection using shared context key constants.
- `src/wf_api/models/authoring_contracts.py`: transport-neutral inventory payload types.
- `src/wf_api/authoring_contracts.py`: schema flattening, capability contract projection, and complete inventory composition.
- `src/wf_api/surface.py`, `service.py`: protocol-neutral inspection interface.
- `src/wf_transport_rpc_http/models.py`, `methods/drafts.py`, `client/drafts.py`: JSON-RPC request, dispatch, and remote client support.

### Generated And Authored TypeScript Contract

- `contracts/workflow-api.manifest.json`: regenerated canonical operation contract.
- `web/packages/rpc/src/generated/workflow-contract.ts`: regenerated TypeScript wire inventory.
- `web/packages/rpc/src/rpcs.ts`, `method-registry.ts`, `service.ts`: authored Effect operation.
- `web/apps/console/src/connection/contracts.ts`: explicit browser operation allowlist.

### Console Domain And Authoring

- `web/apps/console/src/workspace/domain/authoring-contract-models.ts`: decoded browser inventory types.
- `web/apps/console/src/workspace/domain/authoring-contract-client.ts`: read adapter for inventory inspection.
- `web/apps/console/src/workspace/authoring/useAuthoringContract.ts`: selection/revision-aware inventory controller.
- `web/apps/console/src/workspace/authoring/AuthoringPathPicker.tsx`: grouped searchable source/target picker.
- `web/apps/console/src/workspace/authoring/workflow-contract-editor.ts`: lossless contract form projection.
- `web/apps/console/src/workspace/authoring/WorkflowContractInspector.tsx`: Input, State, Output, and Outcomes forms.
- `web/apps/console/src/workspace/authoring/authoring-graph.ts`: contract projection nodes and binding-derived connectors.
- `web/apps/console/src/workspace/authoring/AuthoringGraph.tsx`, `ContextInspector.tsx`, `DraftWorkbench.tsx`: selection and composition.
- `web/apps/console/src/workspace/authoring/useDraftAuthoring.ts`: focused contract/start/output mutations and conflict reapply.
- `web/apps/console/src/styles/global.css`: contract projection, picker, and responsive inspector styles.

---

### Task 1: Model Schema-Derived Authoring Choices

**Files:**

- Create: `src/wf_api/models/authoring_contracts.py`
- Create: `src/wf_api/authoring_contracts.py`
- Create: `tests/wf_api/test_authoring_contracts.py`
- Modify: `src/wf_api/models/__init__.py`

**Interfaces:**

- Produces: `AuthoringPathOptionPayload`, `AuthoringStepContractPayload`, and `AuthoringContractInventoryPayload`.
- Produces: `schema_path_options(schema, *, root, uses) -> list[AuthoringPathOptionPayload]`.
- Produces: `project_authoring_contract_inventory(...) -> AuthoringContractInventoryPayload`; Task 2 supplies its context entries and Task 3 supplies persisted workspace/capability data.

- [ ] **Step 1: Write failing schema inventory tests**

Create fixtures with nested objects, required fields, arrays, `$defs`, descriptions, and unconstrained `additionalProperties`. Assert exact entries such as:

```python
assert options[0] == {
    "path": "input.request",
    "label": "Request",
    "origin": "workflow_input",
    "schema": {"type": "object", "properties": {"id": {"type": "string"}}},
    "required": True,
    "availability": "available",
    "uses": ["step_input", "workflow_output"],
}
```

Assert deterministic parent-before-child order, `$ref` resolution through the existing bounded schema helpers, whole-array selection without synthetic wildcard paths, and omission of invented names for unconstrained additional properties.

- [ ] **Step 2: Run the tests and verify RED**

```powershell
uv run pytest tests/wf_api/test_authoring_contracts.py -q
```

Expected: import failures because the inventory models and projector do not exist.

- [ ] **Step 3: Implement explicit payload types**

Define these literals and payloads without `Any`-shaped public fields beyond JSON Schema objects:

```python
type AuthoringPathOrigin = Literal[
    "workflow_input", "workflow_state", "runtime_context",
    "step_input", "step_output", "workflow_output",
]
type AuthoringPathAvailability = Literal["available", "conditional"]
type AuthoringPathUse = Literal[
    "step_input", "step_output_source", "state_target", "workflow_output",
]

class AuthoringPathOptionPayload(TypedDict):
    path: str
    label: str
    origin: AuthoringPathOrigin
    schema: JsonObject
    required: bool
    availability: AuthoringPathAvailability
    uses: list[AuthoringPathUse]
    description: NotRequired[str]
    reason: NotRequired[str]
```

`AuthoringContractInventoryPayload` contains `workspace_id`, `revision`, `selected_step_id`, `readable_sources`, `step_input_targets`, `step_output_sources`, `state_targets`, `workflow_output_targets`, `entry_steps`, `workflow_outcomes`, and `warnings`.

- [ ] **Step 4: Implement bounded schema flattening and inventory composition**

Reuse `schema_fragment_at_location` and local `$ref` limits from `wf_api.schema_projection`. Derive labels from schema `title`, otherwise humanize the final path segment. Copy descriptions only when they are strings. Return `{}` for a known path whose schema is intentionally unconstrained; never infer a type from a field name or runtime value.

Keep `project_authoring_contract_inventory` pure: pass all schemas, selected-step details, context entries, entry candidates, and warnings as arguments. Do not make it load stores or capability sources itself.

- [ ] **Step 5: Verify and commit**

```powershell
uv run pytest tests/wf_api/test_authoring_contracts.py tests/wf_api/test_schema_projection.py -q
uv run basedpyright --level error src/wf_api/authoring_contracts.py src/wf_api/models/authoring_contracts.py
```

Commit:

```powershell
git add src/wf_api/authoring_contracts.py src/wf_api/models/authoring_contracts.py src/wf_api/models/__init__.py tests/wf_api/test_authoring_contracts.py
git commit -m "feat: project authoring contract choices"
```

---

### Task 2: Analyze Node-Scoped Runtime Context

**Files:**

- Create: `src/wf_core/context_contracts.py`
- Create: `src/wf_core/analysis/context_scopes.py`
- Create: `src/wf_core/analysis/__init__.py`
- Modify: `src/wf_core/runtime/ops/frames.py`
- Create: `tests/core/test_context_scopes.py`
- Modify: `tests/core/test_scheduler.py`
- Modify: `tests/wf_api/test_authoring_contracts.py`

**Interfaces:**

- Produces: `STANDARD_CONTEXT_FIELDS`, `foreach_context_fields(alias, item_schema)`, and the existing `frame_context_values(frame)` behavior using shared key constants.
- Produces: `context_fields_by_node(workflow: Workflow) -> dict[str, tuple[ContextFieldAvailability, ...]]`.
- Consumes: Task 1 inventory composition and returns runtime-context options with `available` or `conditional` availability.

- [ ] **Step 1: Write failing runtime-contract and graph-analysis tests**

Cover:

- standard frame keys on ordinary nodes;
- serial and concurrent foreach loop targets;
- configured alias plus `loop_item` and `loop_index`;
- a node reached only inside one foreach as `available`;
- a node reached both from root and a foreach child as `conditional`;
- nested foreach where the inner child exposes only the inner alias;
- return to the outer frame after the nested foreach preserves the outer alias;
- malformed/missing loop routes produce warnings and no guaranteed alias; and
- traversal terminates on cyclic graphs by memoizing `(node_id, frame_scope)`.

Use field-level assertions rather than whole-object equality for warning text.

- [ ] **Step 2: Run the tests and verify RED**

```powershell
uv run pytest tests/core/test_context_scopes.py tests/core/test_scheduler.py tests/wf_api/test_authoring_contracts.py -q
```

Expected: imports fail for the new context contract and analysis modules.

- [ ] **Step 3: Centralize runtime-context names and schemas**

Move the semantic key registry, not runtime values, into `context_contracts.py`:

```python
STANDARD_CONTEXT_FIELDS = (
    ContextFieldContract("prior_outcome", {"type": ["string", "null"]}, "Prior route outcome"),
    ContextFieldContract("activated_incoming_edge", {"type": ["string", "null"]}, "Incoming step id"),
    ContextFieldContract("scope_id", {"type": "string"}, "Execution scope id"),
    ContextFieldContract("lineage_id", {"type": "string"}, "Execution lineage id"),
    ContextFieldContract("parent_lineage_id", {"type": ["string", "null"]}, "Parent lineage id"),
)
```

`frame_context_values` continues to read actual frame values but uses these constants. `foreach_context_fields` returns `loop_item`, `loop_index`, and the configured alias, deduplicating an alias equal to a standard loop key.

- [ ] **Step 4: Implement conservative abstract traversal**

Traverse states shaped as `(node_id, active_foreach_id | None)`. Normal routes retain the active frame scope. A foreach `loop` route enters a new child frame owned by that foreach; its other routes stay in the current frame. A nested foreach child replaces, rather than inherits, the outer iteration metadata because that matches `frame_context_values` today.

Aggregate every frame scope that can reach each node:

- a field present in every reachable scope is `available`;
- a field present in only some scopes is `conditional` with a concise reason;
- malformed route targets and absent loop routes add bounded warnings; and
- no traversal result may grant a scoped alias that runtime cannot provide.

Add a docstring explaining why this is an abstract execution-frame analysis rather than ordinary graph reachability.

- [ ] **Step 5: Feed context options into Task 1 inventory**

Project canonical paths as `context.<key>`. Derive foreach item schema from the `over` source when the source schema is declared and array-valued; otherwise use `{}`. Runtime context options are offered only for `step_input`. Final workflow projection currently executes without frame context, so the inventory must not advertise `context.*` for `workflow_output`.

- [ ] **Step 6: Verify and commit**

```powershell
uv run pytest tests/core/test_context_scopes.py tests/core/test_scheduler.py tests/wf_api/test_authoring_contracts.py -q
uv run basedpyright --level error src/wf_core/context_contracts.py src/wf_core/analysis src/wf_core/runtime/ops/frames.py
```

Commit:

```powershell
git add src/wf_core/context_contracts.py src/wf_core/analysis src/wf_core/runtime/ops/frames.py src/wf_api/authoring_contracts.py tests/core/test_context_scopes.py tests/core/test_scheduler.py tests/wf_api/test_authoring_contracts.py
git commit -m "feat: inspect node runtime context"
```

---

### Task 3: Expose Authoring Contract Inspection Through Workflow API And JSON-RPC

**Files:**

- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/authoring_contracts.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `tests/wf_api/test_drafts_service.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`
- Modify: `tests/wf_transport_rpc_http/test_client.py`
- Modify: `tests/wf_transport_rpc_http/test_openrpc_contract.py`

**Interfaces:**

- Produces: `WorkflowDraftSurface.inspect_draft_authoring_contract(*, workspace_id: str, revision: int, selected_step_id: str | None = None) -> AuthoringContractInventoryPayload`, implemented by `WorkflowApi`.
- Produces: JSON-RPC operation `workflow.draft_workspaces.inspect_authoring_contract` with the same fields.
- Consumes: Tasks 1-2 pure inventory modules.

- [ ] **Step 1: Write failing service tests**

Create a persisted draft with input/state/output schemas and a selected capability step. Assert that inspection:

- returns the requested workspace id and exact revision;
- resolves the selected capability input/output schemas and outcomes;
- lists executable entry candidates but not projection ids or `__end__`;
- returns context options from Task 2;
- rejects an unknown selected step;
- returns the standard workflow choices plus warnings for a persisted invalid draft whose selected step cannot be interpreted; and
- returns a normal conflict result/error for a stale revision without mutating the workspace.

- [ ] **Step 2: Run service tests and verify RED**

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k authoring_contract
```

Expected: `WorkflowDraftSurface` has no inspection method.

- [ ] **Step 3: Implement the service method**

Load the persisted workspace with its canonical draft, verify the supplied revision, and project tolerant workflow-level schemas before selected-step details. Resolve a capability contract only when the selected keyed step is a valid capability use. Compile the workflow for context analysis when possible; on compile failure return no scoped context and add a warning rather than making the entire inventory unusable.

Do not mutate, validate-and-save, or increment the revision during inspection.

- [ ] **Step 4: Add JSON-RPC params, dispatch, and client**

Define:

```python
class InspectDraftAuthoringContractParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    selected_step_id: str | None = Field(default=None, min_length=1)
```

Register `workflow.draft_workspaces.inspect_authoring_contract` in `methods/drafts.py` and add the matching remote client method. Keep errors in the existing JSON-RPC mapping: malformed request parameters map to `-32602`; an unknown selected step follows the existing workflow-domain error mapping; missing workspace uses the established not-found mapping; stale revision uses the existing conflict semantics.

- [ ] **Step 5: Add RPC and OpenRPC tests**

Assert exact snake_case payload/result fields, nullable `selected_step_id`, conditional `reason`, schema fragments, and no mutation after success or failure. Verify the OpenRPC document references the named payload types rather than an unconstrained object.

- [ ] **Step 6: Verify and commit**

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_openrpc_contract.py -q
uv run basedpyright --level error src/wf_api src/wf_transport_rpc_http
```

Commit:

```powershell
git add src/wf_api src/wf_transport_rpc_http tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http
git commit -m "feat: expose authoring contract inventory"
```

---

### Task 4: Generate And Author The Browser RPC Contract

**Files:**

- Modify: `tests/wf_contract_manifest/test_generate.py`
- Regenerate: `contracts/workflow-api.manifest.json`
- Modify: `web/packages/rpc/scripts/workflow-contract-generator.ts`
- Modify: `web/packages/rpc/scripts/workflow-contract-generator.test.ts`
- Regenerate: `web/packages/rpc/src/generated/workflow-contract.ts`
- Modify: `web/packages/rpc/src/rpcs.ts`
- Modify: `web/packages/rpc/src/method-registry.ts`
- Modify: `web/packages/rpc/src/service.ts`
- Modify: `web/packages/rpc/src/index.ts`
- Modify: `web/packages/rpc/src/json-schema/authored-rpc-fixtures.ts`
- Modify: `web/packages/rpc/src/json-schema/rpc-parity.test.ts`
- Modify: `web/packages/rpc/src/generated/workflow-contract.test.ts`
- Modify: `web/packages/rpc/src/method-registry.test.ts`
- Modify: `web/packages/rpc/src/service.test.ts`
- Modify: `web/apps/console/src/connection/contracts.ts`
- Modify: `web/apps/server/src/browser-operation-policy.ts`
- Modify: `web/apps/server/src/browser-operation-policy.test.ts`
- Modify: `web/apps/server/src/app.test.ts`

**Interfaces:**

- Produces: authored Effect RPCs for `inspect_authoring_contract`, `set_contract`, `set_start`, and `set_workflow_output_bindings`.
- Produces: console `OperationName` literals for those four operations.
- Preserves: Hono/browser authorization as an explicit allowlist independent of generated operation coverage.

- [ ] **Step 1: Write failing generated-contract and allowlist tests**

Assert all four methods are in the authored RPC cohort and generated inventory. Add positive browser authorization tests for those methods and a negative test proving adjacent generic `patch` and `replace_document` operations remain blocked.

- [ ] **Step 2: Regenerate checked contracts**

```powershell
uv run python -m wf_contract_manifest write
pnpm --dir web --filter @lda/workflow-rpc contract:write
pnpm --dir web --filter @lda/workflow-rpc contract:check
```

Do not hand-edit generated artifacts.

- [ ] **Step 3: Add authored Effect schemas and registry entries**

Confirm `.repos/effect` is present, consult the local Effect Schema guide, and
follow the package's existing authored-RPC patterns. Use
`runtimeSchemasFor(...)` for payload and success schemas. Register inspection
as idempotency `"read"`; register the three focused mutations as `"write"`. Add
exhaustive service switch cases and export the RPCs through the package index.

Author representative parity fixtures containing one input source, one state target, one conditional context source with `reason`, selected-step input/output choices, and entry/outcome lists.

- [ ] **Step 4: Extend the console and proxy allowlists**

Add exactly the four operation literals. Do not authorize source-admin, artifact deletion, generic patch, complete document replacement, or run mutations as a side effect.

- [ ] **Step 5: Verify and commit**

```powershell
uv run pytest tests/wf_contract_manifest/test_generate.py tests/wf_contract_manifest/test_committed_manifest.py -q
pnpm --dir web --filter @lda/workflow-rpc test
pnpm --dir web --filter @lda/workflow-rpc typecheck
pnpm --dir web --filter @lda/console test -- src/connection
pnpm --dir web --filter @lda/server test -- src/browser-operation-policy.test.ts src/app.test.ts
```

Commit:

```powershell
git add tests/wf_contract_manifest contracts/workflow-api.manifest.json web/packages/rpc web/apps/console/src/connection web/apps/server/src/browser-operation-policy.ts web/apps/server/src/browser-operation-policy.test.ts web/apps/server/src/app.test.ts
git commit -m "feat: authorize workflow contract authoring"
```

---

### Task 5: Decode Inventory And Build The Reusable Path Picker

**Files:**

- Create: `web/apps/console/src/workspace/domain/authoring-contract-models.ts`
- Create: `web/apps/console/src/workspace/domain/authoring-contract-models.test.ts`
- Create: `web/apps/console/src/workspace/domain/authoring-contract-client.ts`
- Create: `web/apps/console/src/workspace/domain/authoring-contract-client.test.ts`
- Create: `web/apps/console/src/workspace/authoring/useAuthoringContract.ts`
- Create: `web/apps/console/src/workspace/authoring/useAuthoringContract.test.tsx`
- Create: `web/apps/console/src/workspace/authoring/AuthoringPathPicker.tsx`
- Create: `web/apps/console/src/workspace/authoring/AuthoringPathPicker.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**

- Produces: `AuthoringPathOption`, `AuthoringStepContract`, and `AuthoringContractInventory` camelCase browser types.
- Produces: `createAuthoringContractClient(executor).inspect(input) -> Promise<AuthoringContractInventory>`.
- Produces: `useAuthoringContract({ workspaceId, revision, selectedStepId })` returning `{ phase, inventory, message, refresh }`.
- Produces: `<AuthoringPathPicker options uses value onChange label allowCustom />`.

- [ ] **Step 1: Write failing decoder and client tests**

Decode a complete snake_case wire result into camelCase fields. Reject unknown origins, availability values, uses, malformed schemas, and a response whose workspace/revision does not match the request. Assert the client sends the exact inspection params through the read executor.

- [ ] **Step 2: Implement boundary decoding and the read adapter**

Use Valibot at the external boundary. Preserve JSON Schema fragments as decoded JSON objects; do not use casts. Filter picker entries by their declared `uses` instead of their origin names.

- [ ] **Step 3: Write failing hook lifecycle tests**

Cover disconnected, loading, ready, stale response after selection change, failed inspection retaining the last matching inventory, revision change, and manual refresh. Use stable executor mocks and abort/ignore stale requests following existing workspace hooks.

- [ ] **Step 4: Implement the hook**

Key requests by connected target, workspace id, revision, and selected step id. Selecting a contract projection passes `null`; selecting an executable node passes its id. Never copy context names into the hook.

- [ ] **Step 5: Write failing picker interaction tests**

Assert:

- options group as Workflow input, State, Step output, and Runtime context;
- searching matches label, path, and description;
- canonical path is secondary text;
- conditional entries show their reason;
- Runtime context is absent when no context options exist;
- disabled incompatible entries cannot be selected;
- nested choices remain keyboard reachable; and
- Advanced reveals a custom path text control without replacing normal options.

- [ ] **Step 6: Implement the picker**

Use native labelled controls and the existing console visual language. Keep the options panel internally scrollable and mobile-safe. The picker emits only a canonical string; its caller owns row state and validation.

- [ ] **Step 7: Verify and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/domain/authoring-contract-models.test.ts src/workspace/domain/authoring-contract-client.test.ts src/workspace/authoring/useAuthoringContract.test.tsx src/workspace/authoring/AuthoringPathPicker.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Commit:

```powershell
git add web/apps/console/src/workspace/domain/authoring-contract-* web/apps/console/src/workspace/authoring/useAuthoringContract* web/apps/console/src/workspace/authoring/AuthoringPathPicker* web/apps/console/src/styles/global.css
git commit -m "feat: browse authoring contract paths"
```

---

### Task 6: Replace Local Suggestion Lists In Existing Binding Editors

**Files:**

- Modify: `web/apps/console/src/workspace/authoring/StepInputBindingsForm.tsx`
- Modify: `web/apps/console/src/workspace/authoring/StepInputBindingsForm.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/InputExpressionControl.tsx`
- Modify: `web/apps/console/src/workspace/authoring/InputExpressionControl.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/StepOutputBindingsForm.tsx`
- Modify: `web/apps/console/src/workspace/authoring/StepOutputBindingsForm.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/SelectedCapabilityInspector.tsx`
- Modify: `web/apps/console/src/workspace/authoring/SelectedCapabilityInspector.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/selected-step-dataflow.ts`
- Modify: `web/apps/console/src/workspace/authoring/selected-step-dataflow.test.ts`

**Interfaces:**

- Consumes: `AuthoringContractInventory` and `AuthoringPathPicker` from Task 5.
- Preserves: canonical `StepInputBinding` and `OutputBinding` submissions.
- Removes as source of truth: `workflowSourceSuggestions`; schema-local output paths may remain a pure fallback only for unsupported/repair state.

- [ ] **Step 1: Write failing integration tests for inventory-backed choices**

Render a selected step with inventory options. Assert that input path rows and every recursive path expression use the same picker, context appears only when supplied, and output rows use inventory step-output sources plus state targets. Confirm a selected canonical path serializes unchanged.

- [ ] **Step 2: Verify RED**

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/authoring/StepInputBindingsForm.test.tsx src/workspace/authoring/InputExpressionControl.test.tsx src/workspace/authoring/StepOutputBindingsForm.test.tsx src/workspace/authoring/SelectedCapabilityInspector.test.tsx
```

Expected: forms still render datalists or local schema suggestions.

- [ ] **Step 3: Thread inventory options through the selected-step inspector**

Pass filtered options rather than schemas into normal picker paths:

- step inputs consume options with `step_input`;
- expression path leaves consume the same options;
- step outputs consume `step_output_source` for source and `state_target` for destination.

Existing malformed or custom persisted paths initialize Advanced mode and remain repairable. Do not silently replace them with the first catalog value.

- [ ] **Step 4: Retire duplicate frontend path discovery**

Remove `workflowSourceSuggestions` once all production callers use inventory. Keep schema navigation helpers still needed for local capability targets, output preview, expression schema validation, and unsupported-record repair. Add a test proving no production authoring file contains hardcoded `context.loop_item` or similar runtime keys.

- [ ] **Step 5: Verify and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/authoring
pnpm --dir web --filter @lda/console typecheck
```

Commit:

```powershell
git add web/apps/console/src/workspace/authoring
git commit -m "refactor: use canonical authoring choices"
```

---

### Task 7: Project Workflow Contracts Into The Graph

**Files:**

- Modify: `web/apps/console/src/graph/graph-model.ts`
- Modify: `web/apps/console/src/graph/WorkflowGraph.tsx`
- Modify: `web/apps/console/src/graph/WorkflowGraph.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/authoring-graph.ts`
- Modify: `web/apps/console/src/workspace/authoring/authoring-graph.test.ts`
- Modify: `web/apps/console/src/workspace/authoring/AuthoringGraph.tsx`
- Modify: `web/apps/console/src/workspace/authoring/AuthoringGraph.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/DraftWorkbench.tsx`
- Modify: `web/apps/console/src/workspace/authoring/DraftWorkbench.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**

- Extends: `WorkbenchSelection` with `{ kind: "contract"; contract: "input" | "state" | "output" | "outcomes" }`.
- Extends: `WorkflowGraphNodeKind` with contract-specific visual kinds or one `contract` kind plus explicit contract metadata.
- Produces: stable ids `contract:input`, `contract:state`, `contract:output`, and `contract:outcomes`.

- [ ] **Step 1: Write failing pure graph projection tests**

Assert every canonical draft produces exactly four stable contract nodes; their summaries reflect schema/outcome counts; none appear in persisted draft steps; insertion order does not alter ids or positions; entry and binding connectors are derived from canonical start/input/output data; and malformed bindings omit only the affected connector.

- [ ] **Step 2: Implement graph projection records**

Build contract records before calling the Dagre-backed graph model. Use a left-to-right authoring layout with Input near entry steps, State adjacent to executable dataflow, Output near terminal flow, and Outcomes separated from executable End nodes. Derived connectors use distinct non-route styling and cannot be selected as route outcomes.

- [ ] **Step 3: Add contract node rendering and selection**

Render readable contract labels and concise field counts. Do not reuse execution status colors or imply the projections run. Contract nodes are selectable by mouse, Enter, and Space; React Flow panning and zoom remain intact.

- [ ] **Step 4: Preserve responsive selection state**

Selecting a contract opens the existing inspector sheet on mobile and remains selected after close/reopen. Canvas selection clears it. Contract selection must not create insertion context or expose capability-only deferred actions.

- [ ] **Step 5: Verify and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/graph src/workspace/authoring/authoring-graph.test.ts src/workspace/authoring/AuthoringGraph.test.tsx src/workspace/authoring/DraftWorkbench.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Commit:

```powershell
git add web/apps/console/src/graph web/apps/console/src/workspace/authoring/authoring-graph* web/apps/console/src/workspace/authoring/AuthoringGraph* web/apps/console/src/workspace/authoring/DraftWorkbench* web/apps/console/src/styles/global.css
git commit -m "feat: project workflow contracts in graph"
```

---

### Task 8: Add Focused Workflow Contract Editors

**Files:**

- Create: `web/apps/console/src/workspace/authoring/workflow-contract-editor.ts`
- Create: `web/apps/console/src/workspace/authoring/workflow-contract-editor.test.ts`
- Create: `web/apps/console/src/workspace/authoring/WorkflowSchemaFieldsForm.tsx`
- Create: `web/apps/console/src/workspace/authoring/WorkflowSchemaFieldsForm.test.tsx`
- Create: `web/apps/console/src/workspace/authoring/WorkflowContractInspector.tsx`
- Create: `web/apps/console/src/workspace/authoring/WorkflowContractInspector.test.tsx`
- Modify: `web/apps/console/src/workspace/domain/draft-workspace-models.ts`
- Modify: `web/apps/console/src/workspace/domain/draft-authoring-client.ts`
- Modify: `web/apps/console/src/workspace/domain/draft-authoring-client.test.ts`
- Modify: `web/apps/console/src/workspace/authoring/useDraftAuthoring.ts`
- Modify: `web/apps/console/src/workspace/authoring/useDraftAuthoring.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/ContextInspector.tsx`
- Modify: `web/apps/console/src/workspace/authoring/ContextInspector.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**

- Produces: `WorkflowContractPatch`, `WorkflowOutputBindingRow`, and lossless schema field projection helpers.
- Extends: `DraftAuthoringClient` with `setContract`, `setStart`, and `setWorkflowOutputBindings`.
- Extends: `DraftAuthoringController` with the same focused mutations and conflict-reapply submissions.
- Consumes: Task 5 inventory and Task 7 contract selection.

- [ ] **Step 1: Write failing pure schema-editor tests**

Project ordinary object schemas into ordered rows with `name`, `type`, `required`, `description`, nested object fields, array item schema, and state-only `default`/`reducer` metadata. Assert round-trip preservation of untouched `$defs`, root metadata, and unsupported field fragments.

Unsupported composition such as `oneOf` remains visible as a bounded read-only fragment. Saving is blocked until the author leaves it untouched, explicitly removes it, or replaces it with a supported field model; never discard it during another field edit.

- [ ] **Step 2: Build the recursive workflow schema form**

Support `string`, `integer`, `number`, `boolean`, `object`, `array`, and unconstrained value fields. Object fields recursively edit children; array fields edit one item schema. Keep recursion bounded by the existing schema normalization limit and show a concise unsupported message past that boundary.

State rows expose default and reducer controls only where the canonical state schema accepts them. Input and Output rows do not render state-only fields.

- [ ] **Step 3: Add client methods and exact payload tests**

Define domain inputs:

```ts
type SetWorkflowContractInput = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly inputSchema?: JsonObject;
  readonly stateSchema?: JsonObject;
  readonly outputSchema?: JsonObject;
  readonly outcomes?: ReadonlyArray<string>;
};

type SetWorkflowStartInput = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly stepId: string;
};

type SetWorkflowOutputBindingsInput = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly bindings: ReadonlyArray<InputBinding>;
};
```

Assert exact operation names and snake_case payloads. Deep-copy schemas and bindings without JSON stringify round trips.

- [ ] **Step 4: Add controller mutations and conflict reapply**

Extend `LastSubmission` with `contract`, `start`, and `workflow_outputs`. Reapply the exact prior payload against the refreshed revision. Deduplicate identical pending submissions and preserve contract selection/dirty state on conflicts using the existing mutation runner.

If one user gesture needs both output schema and output bindings, submit them as two explicit operations in order. Show confirmed partial success if the second fails; do not present the pair as atomic.

- [ ] **Step 5: Build focused contract inspectors**

- Input: schema fields plus entry-step picker from `inventory.entrySteps`.
- State: state fields with defaults/reducers and affected-binding summaries before removal.
- Output: schema fields plus ordered final output bindings using
  `AuthoringPathPicker` for workflow input/state sources and inventory output
  targets. Exclude runtime context because final projection has no execution
  frame; preserve an existing `context.*` source only as an unsupported repair
  value.
- Outcomes: ordered non-blank unique workflow outcomes with add/remove/reorder controls.

All forms show unsaved, saving, invalid-confirmed, conflict, and failed states truthfully. Raw schema appears only in an Advanced details region for unsupported repair.

- [ ] **Step 6: Route contract selection through ContextInspector**

Render `WorkflowContractInspector` only for `selection.kind === "contract"`. Hide capability-only deferred actions. Keep shared diagnostics and bounded raw draft available below the focused form.

- [ ] **Step 7: Verify and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/domain/draft-authoring-client.test.ts src/workspace/authoring/workflow-contract-editor.test.ts src/workspace/authoring/WorkflowSchemaFieldsForm.test.tsx src/workspace/authoring/WorkflowContractInspector.test.tsx src/workspace/authoring/useDraftAuthoring.test.tsx src/workspace/authoring/ContextInspector.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Commit:

```powershell
git add web/apps/console/src/workspace/domain web/apps/console/src/workspace/authoring web/apps/console/src/styles/global.css
git commit -m "feat: edit workflow contracts in console"
```

---

### Task 9: Verify The Complete Slice And Update Live Documentation

**Files:**

- Modify: `web/apps/console/src/workspace/routes/DraftDetailRoute.authoring-sync.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/DraftWorkbench.test.tsx`
- Modify: `web/README.md`
- Modify: `docs/project_map.md`
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-08-14-workflow-console-contract-graph.md` to `docs/historical/superpowers/plans/2026-08-14-workflow-console-contract-graph.md`

**Interfaces:**

- Consumes: all prior tasks.
- Produces: route-level proof that a real inventory read and focused contract writes update one canonical draft without browser-only state divergence.

- [ ] **Step 1: Add route-level integration tests**

Mock the actual browser operation sequence and assert:

1. opening a draft reads canonical workspace and inventory;
2. selecting Input opens its schema/start form;
3. selecting a capability node refreshes inventory with `selected_step_id`;
4. foreach context appears only for a proven loop-body node;
5. selecting and saving one input binding sends the catalog path unchanged;
6. editing final output sends ordered canonical bindings;
7. an inventory failure retains confirmed draft values and exposes Advanced repair;
8. a stale write preserves the selected contract and local form; and
9. closing/reopening the mobile inspector preserves unsaved rows.

- [ ] **Step 2: Run focused Python and web suites**

```powershell
uv run pytest tests/core/test_context_scopes.py tests/core/test_scheduler.py tests/wf_api/test_authoring_contracts.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_openrpc_contract.py tests/wf_contract_manifest/test_generate.py tests/wf_contract_manifest/test_committed_manifest.py -q
pnpm --dir web --filter @lda/workflow-rpc test
pnpm --dir web --filter @lda/console test -- src/workspace
pnpm --dir web typecheck
pnpm --dir web build
```

- [ ] **Step 3: Run a real-server smoke test**

Against the existing example config, start the JSON-RPC server if one is not already available:

```powershell
uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
```

Use the console to create or open a draft, inspect the four contract projections, select a normal source without reading raw JSON, save one focused contract edit, reload, and confirm the returned revision and graph projection match. Also inspect a foreach-body node if the fixture contains one; otherwise exercise context-scope behavior through the focused automated tests rather than inventing demo data.

- [ ] **Step 4: Run React and interface diagnostics**

Run the React diagnostic against changed console files:

```powershell
pnpm dlx react-doctor@latest --verbose --scope changed
```

Then run:

```powershell
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Fix actionable accessibility, stale-effect, or component-interface findings in touched files. Do not broaden into unrelated presentation UI.

- [ ] **Step 5: Update live docs and archive the plan**

Document the authoring inventory, four contract projections, normal picker workflow, Advanced custom-path fallback, and current typed-step exclusions in `web/README.md` and `docs/project_map.md`. Mark Slice 6 completed in the roadmap and link the historical plan path. Move the plan with PowerShell `Move-Item`, then stage the active and historical plan directories with `git add -A` so both tracked and untracked source states are handled.

- [ ] **Step 6: Run final verification and review**

```powershell
uv run ruff check
uv run basedpyright --level error
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Run an independent two-axis review against the approved design. Fix Critical and Important findings, and record any deliberate Minor deferrals with concrete rationale.

- [ ] **Step 7: Commit the completed slice**

```powershell
git add -A -- web/README.md docs/project_map.md docs/current_roadmap.md docs/superpowers/plans docs/historical/superpowers/plans web/apps/console/src/workspace/routes/DraftDetailRoute.authoring-sync.test.tsx web/apps/console/src/workspace/authoring/DraftWorkbench.test.tsx
git commit -m "docs: complete workflow contract graph"
```

---

## Final Acceptance Checklist

- [ ] The API returns one revision-scoped inventory for workflow and selected-step authoring choices.
- [ ] Input/state fields and step-applicable context fields are selectable without raw JSON inspection.
- [ ] Final output choices exclude runtime context until final projection has defined context semantics.
- [ ] Runtime context disappears entirely when no applicable options exist.
- [ ] Conditional foreach paths are labelled honestly and never presented as guaranteed.
- [ ] Existing input, expression, and output editors use the same inventory-backed picker.
- [ ] Input, State, Output, and Outcomes are selectable graph projections but absent from stored steps.
- [ ] Start, contract, outcomes, and final output writes use focused canonical operations.
- [ ] Unsupported persisted schemas and custom paths remain visible and repairable without data loss.
- [ ] Desktop and mobile preserve selection and unsaved edits through inventory refreshes and conflicts.
- [ ] Generated contracts, Effect RPCs, browser authorization, Python tests, web tests, typechecks, and builds pass.
