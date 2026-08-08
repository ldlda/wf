# Workflow Console Draft Authoring Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the read-only draft route into a typed, evidenced workflow-authoring workbench where operators create drafts, add and edit capability nodes, set routes, and validate canonical revisions without editing raw JSON.

**Architecture:** Extend the checked JSON-Schema-to-Effect RPC cohort with exactly six browser-authorized authoring operations. Above that boundary, add one mutation executor and typed authoring client; React composes schema-form, graph-selection, and workbench modules around canonical draft responses. Local form/selection state never becomes workflow truth: every successful mutation replaces the displayed draft with the decoded server result.

**Tech Stack:** TypeScript 6, React 19, Effect RPC/Schema, Valibot, React Router, `@xyflow/react`, Tailwind 4 plus existing console CSS/shadcn controls, Vitest, Testing Library, Playwright.

## Global Constraints

- Keep `workflow.runs.start` and `workflow.runs.resume` browser-authorized.
- Add exactly these browser authoring methods: `create_empty`, `create_from_capability`, `add_step_from_capability`, `update_capability_step`, `set_route`, and `validate`.
- Do not expose generic patch, replacement, deletion, artifact creation, deployment mutation, run mutation beyond the existing run allowlist, or administration methods.
- React components must not call `callOperation` or own raw operation-name strings.
- Use the existing evidence ledger, graph boundary, shadcn/Radix controls, and route workspace.
- Every mutation includes the loaded revision when the operation contract supports revision and replaces UI state only with a decoded canonical response.
- Do not autosave; preserve dirty form input on failures and revision conflicts.
- Unsupported schema constructs use a field-scoped JSON fallback with an explanation.
- Deferred product actions remain visible, disabled, keyboard discoverable, and labelled `Later`; they never dispatch operations.
- Add comments around stale-response generation checks, schema fallback rules, and route insertion lowering.

---

### Task 1: Typed RPC And Browser Authorization

**Files:**
- Modify: `web/packages/rpc/scripts/workflow-contract-generator.ts`
- Modify: `web/packages/rpc/src/rpcs.ts`
- Modify: `web/packages/rpc/src/service.ts`
- Modify: `web/packages/rpc/src/method-registry.ts`
- Modify: `web/packages/rpc/src/index.ts`
- Modify: `web/packages/rpc/src/json-schema/runtime-schema.test.ts`
- Modify: `web/packages/rpc/src/service.test.ts`
- Modify: `web/packages/rpc/src/method-registry.test.ts`
- Modify: `web/apps/server/src/browser-operation-policy.ts`
- Modify: `web/apps/server/src/browser-operation-policy.test.ts`
- Modify: `web/apps/server/src/app.test.ts`

**Interfaces:**
- Produces six typed `Rpc.make(...)` definitions using `runtimeSchemasFor(Name)`.
- Produces `OperationName` support and method-registry metadata for all six methods.
- Browser policy authorizes those six names independently of RPC membership.

- [ ] **Step 1: Write failing cohort, service, metadata, and policy tests**

Pin exact membership and representative payloads:

```ts
expect(runtimeSchemasFor("workflow.draft_workspaces.create_empty")).toBeDefined();
expect(browserAllowedOperationNames).toContain(
  "workflow.draft_workspaces.add_step_from_capability",
);
expect(browserAllowedOperationNames).not.toContain(
  "workflow.draft_workspaces.replace_document",
);
```

Service tests must execute each case through the existing handler runner and assert the exact operation name and decoded params. Registry tests must assert equivalent CLI and interpreted canonical draft fields.

- [ ] **Step 2: Run RED checks**

Run:

```powershell
pnpm --dir web --filter @lda/workflow-rpc test
pnpm --dir web --filter @lda/web-server test -- src/browser-operation-policy.test.ts src/app.test.ts
```

Expected: failures because the six methods are absent from the runtime cohort/service/policy.

- [ ] **Step 3: Extend the runtime cohort and RPC surface**

Add the exact names to `runtimeOperationNameList`, export payload/result schemas, define RPCs, add service switch cases, registry entries, and public exports. Use generated `WorkflowOperationParams<Name>` and `WorkflowOperationResult<Name>`; do not reproduce payload schemas manually.

- [ ] **Step 4: Extend the independent browser allowlist**

Add only:

```ts
"workflow.draft_workspaces.create_empty",
"workflow.draft_workspaces.create_from_capability",
"workflow.draft_workspaces.add_step_from_capability",
"workflow.draft_workspaces.update_capability_step",
"workflow.draft_workspaces.set_route",
"workflow.draft_workspaces.validate",
```

Retain every existing read and run entry.

- [ ] **Step 5: Verify and commit**

Run RPC tests, server tests, both typechecks, and `contract:check`. Commit:

```powershell
git commit -am "feat: expose typed draft authoring operations"
```

---

### Task 2: Mutation Executor And Typed Authoring Client

**Files:**
- Create: `web/apps/console/src/workspace/domain/write-executor.ts`
- Create: `web/apps/console/src/workspace/domain/write-executor.test.ts`
- Create: `web/apps/console/src/workspace/domain/draft-authoring-client.ts`
- Create: `web/apps/console/src/workspace/domain/draft-authoring-client.test.ts`
- Modify: `web/apps/console/src/workspace/domain/draft-workspace-models.ts`
- Modify: `web/apps/console/src/workspace/domain/draft-workspace-models.test.ts`
- Modify: `web/apps/console/src/workspace/ConsoleWorkspace.tsx`
- Modify: `web/apps/console/src/workspace/context.ts`

**Interfaces:**

```ts
export interface ConsoleWriteExecutor {
  run<T>(operation: OperationName, params: unknown, decode: (value: unknown) => T): Promise<T>;
}

export interface DraftAuthoringClient {
  createEmpty(input: CreateEmptyDraftInput): Promise<DraftWorkspace>;
  createFromCapability(input: CreateFromCapabilityInput): Promise<DraftWorkspace>;
  addCapabilityStep(input: AddCapabilityStepInput): Promise<DraftWorkspace>;
  updateCapabilityStep(input: UpdateCapabilityStepInput): Promise<DraftWorkspace>;
  setRoute(input: SetDraftRouteInput): Promise<DraftWorkspace>;
  validate(workspaceId: string): Promise<DraftWorkspace>;
}
```

All mutation inputs use camelCase in UI code and lower to generated snake_case payloads in the client.

- [ ] **Step 1: Write executor RED tests**

Cover success evidence, operation mismatch, server failure, decode failure, duration, stale-target suppression through `shouldRecordEvidence`, and preserved causes. Copy no implementation from `read-executor`; extract a shared internal helper only if both executors remain clearer.

- [ ] **Step 2: Write authoring-client RED tests**

Assert exact lowering for all six methods, trimmed identifiers, revision propagation, and canonical `decodeDraftWorkspace` output. Include malformed canonical response and blank-id failures.

- [ ] **Step 3: Implement executor and client**

The write executor records the same evidence shape as reads and verifies `response.operation === operation` before decoding. Add `writeExecutor` to `ConsoleWorkspaceContext`; construct it only for a connected target and preserve the existing target-generation evidence guard.

- [ ] **Step 4: Verify and commit**

Run the new tests plus `ConsoleWorkspace.test.tsx` and console typecheck. Commit:

```powershell
git commit -am "feat: add console draft authoring client"
```

---

### Task 3: Shared JSON Schema Form Model

**Files:**
- Create: `web/apps/console/src/workspace/schema-form/schema-field.ts`
- Create: `web/apps/console/src/workspace/schema-form/schema-field.test.ts`
- Create: `web/apps/console/src/workspace/schema-form/schema-values.ts`
- Create: `web/apps/console/src/workspace/schema-form/schema-values.test.ts`
- Create: `web/apps/console/src/workspace/schema-form/SchemaForm.tsx`
- Create: `web/apps/console/src/workspace/schema-form/SchemaForm.test.tsx`
- Create: `web/apps/console/src/workspace/schema-form/SchemaFieldControl.tsx`
- Create: `web/apps/console/src/workspace/schema-form/BindingSourceControl.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**

```ts
export type SchemaField = {
  readonly path: ReadonlyArray<string | number>;
  readonly key: string;
  readonly title: string;
  readonly description: string | null;
  readonly kind: "string" | "number" | "integer" | "boolean" | "enum" |
    "object" | "array" | "json";
  readonly required: boolean;
  readonly hasDefault: boolean;
  readonly defaultValue: unknown;
  readonly enumValues: ReadonlyArray<string | number | boolean | null>;
  readonly children: ReadonlyArray<SchemaField>;
  readonly item: SchemaField | null;
  readonly fallbackReason: string | null;
};

export type FieldSource =
  | { readonly mode: "literal"; readonly value: unknown }
  | { readonly mode: "bind"; readonly sourcePath: string };
```

- [ ] **Step 1: Write normalization RED tests**

Cover string/multiline, number/integer, boolean, enum, nested object, array, required, explicit `null` default, unconstrained `{}`, unsupported `oneOf`, and unresolved `$ref`. `{}` must become a JSON fallback, never an object.

- [ ] **Step 2: Write serialization RED tests**

Cover optional omission, required incomplete preservation, explicit defaults, primitive parsing, nested paths, arrays, and malformed binding paths.

- [ ] **Step 3: Implement pure normalization and serialization**

Keep JSON Schema operations in these pure modules. Return field-local issues rather than throwing for user-entered values.

- [ ] **Step 4: Implement accessible controls**

Render labels, descriptions, required markers, enum selects, checkboxes, nested fieldsets, array editors, `Literal | Bind`, field diagnostics, and collapsed raw schema. Unsupported fields render a textarea JSON editor and the exact fallback reason.

- [ ] **Step 5: Verify and commit**

Run schema-form tests, React Doctor changed scope, and typecheck. Commit:

```powershell
git commit -am "feat: add schema driven workflow forms"
```

---

### Task 4: Authoring Graph Model And Persistent Workbench Shell

**Files:**
- Create: `web/apps/console/src/workspace/authoring/authoring-graph.ts`
- Create: `web/apps/console/src/workspace/authoring/authoring-graph.test.ts`
- Create: `web/apps/console/src/workspace/authoring/AuthoringGraph.tsx`
- Create: `web/apps/console/src/workspace/authoring/AuthoringGraph.test.tsx`
- Create: `web/apps/console/src/workspace/authoring/DraftWorkbench.tsx`
- Create: `web/apps/console/src/workspace/authoring/DraftWorkbench.test.tsx`
- Create: `web/apps/console/src/workspace/authoring/CapabilityPalette.tsx`
- Create: `web/apps/console/src/workspace/authoring/ContextInspector.tsx`
- Modify: `web/apps/console/src/graph/WorkflowGraph.tsx`
- Modify: `web/apps/console/src/workspace/routes/DraftDetailRoute.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**

```ts
export type WorkbenchSelection =
  | { readonly kind: "canvas" }
  | { readonly kind: "capability"; readonly qualifiedName: string }
  | { readonly kind: "node"; readonly nodeId: string }
  | { readonly kind: "edge"; readonly stepId: string; readonly outcome: string };
```

`AuthoringGraph` extends the existing React Flow boundary with selectable edges and nodes; it does not add a second layout implementation.

- [ ] **Step 1: Write graph projection and selection RED tests**

Pin normal, interrupt, and end node kinds; route outcome labels; stable IDs; selected node; selected connector; and insertion context derivation.

- [ ] **Step 2: Implement the tri-pane shell**

Desktop renders palette, graph, inspector simultaneously. The inspector switches on `WorkbenchSelection`; unsupported nodes are read-only. Preserve `RawDraft` as a collapsed escape hatch below the summary inspector.

- [ ] **Step 3: Add deferred affordances**

Render disabled `Undo — Later`, `Redo — Later`, `Delete node — Later`, `Delete route — Later`, `Add other step — Later`, and `Create artifact — Later`. Add no handlers that call the executor.

- [ ] **Step 4: Verify and commit**

Run graph/workbench/route tests and React Doctor. Commit:

```powershell
git commit -am "feat: compose draft authoring workbench"
```

---

### Task 5: Authoring Controller, Canonical Mutations, And Conflicts

**Files:**
- Create: `web/apps/console/src/workspace/authoring/useDraftAuthoring.ts`
- Create: `web/apps/console/src/workspace/authoring/useDraftAuthoring.test.tsx`
- Create: `web/apps/console/src/workspace/authoring/CapabilityNodeForm.tsx`
- Create: `web/apps/console/src/workspace/authoring/CapabilityNodeForm.test.tsx`
- Create: `web/apps/console/src/workspace/authoring/RouteForm.tsx`
- Create: `web/apps/console/src/workspace/authoring/RouteForm.test.tsx`
- Modify: `web/apps/console/src/workspace/authoring/DraftWorkbench.tsx`

**Interfaces:**

```ts
export type DraftAuthoringPhase = "idle" | "saving" | "conflict" | "error";
export interface DraftAuthoringController {
  readonly draft: DraftWorkspace;
  readonly selection: WorkbenchSelection;
  readonly dirty: boolean;
  readonly phase: DraftAuthoringPhase;
  addCapability(input: CapabilityNodeFormValue): Promise<void>;
  updateCapability(input: CapabilityNodeFormValue): Promise<void>;
  setRoute(input: RouteFormValue): Promise<void>;
  validate(): Promise<void>;
  reload(): Promise<void>;
}
```

- [ ] **Step 1: Write controller RED tests**

Cover add unconnected, add after selected node/outcome, update, route replacement, validate, canonical response replacement, new-node selection, failure preserving fields, conflict preserving fields, reload/reapply choice, stale target response rejection, and coalesced submit.

- [ ] **Step 2: Implement explicit form submission**

Lower insertion context only when a node or connector is selected. With no insertion context, omit route information and surface returned connectivity diagnostics. Never invent an outcome.

- [ ] **Step 3: Implement dirty navigation protection**

Use a route blocker plus `beforeunload` while dirty. Closing a mobile sheet must not clear dirty values.

- [ ] **Step 4: Verify and commit**

Run controller/form/workbench tests and typecheck. Commit:

```powershell
git commit -am "feat: mutate canonical drafts from workbench"
```

---

### Task 6: Discover And Draft-Index Handoffs

**Files:**
- Modify: `web/apps/console/src/workspace/routes/DiscoverRoute.tsx`
- Modify: `web/apps/console/src/workspace/routes/DiscoverRoute.test.tsx`
- Modify: `web/apps/console/src/workspace/routes/DraftIndexRoute.tsx`
- Modify: `web/apps/console/src/workspace/routes/DraftIndexRoute.test.tsx`
- Create: `web/apps/console/src/workspace/authoring/CreateDraftDialog.tsx`
- Create: `web/apps/console/src/workspace/authoring/CreateDraftDialog.test.tsx`
- Modify: `web/apps/console/src/app/AppRoutes.tsx`

- [ ] **Step 1: Write RED handoff tests**

Discover: inspect a capability, click `Add to draft`, choose existing or create seeded, then assert navigation to `/console/drafts/:workspaceId?capability=:encodedName`. Draft index: click `New draft`, submit workspace id/name/title, assert canonical creation then direct-route navigation.

- [ ] **Step 2: Implement dialogs and URL-owned handoff**

Use `DraftAuthoringClient`; do not call transport from components. Draft detail reads the optional `capability` search parameter into initial selection without persisting it.

- [ ] **Step 3: Verify and commit**

Run Discover, DraftIndex, routes, and authoring tests. Commit:

```powershell
git commit -am "feat: hand capabilities into draft authoring"
```

---

### Task 7: Responsive Sheets And Real-Server Acceptance

**Files:**
- Modify: `web/apps/console/src/workspace/authoring/DraftWorkbench.tsx`
- Modify: `web/apps/console/src/styles/global.css`
- Modify: `web/apps/console/e2e/workflow-console.spec.ts`
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move: this plan to `docs/historical/superpowers/plans/2026-08-09-workflow-console-draft-authoring-workbench.md`

- [ ] **Step 1: Add responsive component tests**

Assert mobile palette/inspector sheet controls, persistent selection, dirty-value preservation, accessible names, focus return, and touch-safe graph ownership.

- [ ] **Step 2: Implement mobile sheets**

At the established console breakpoint, keep graph primary and render palette/inspector as full-height sheets. Give each independent scrolling and preserve mounted form state while closed.

- [ ] **Step 3: Extend self-owned Playwright acceptance**

Using isolated Python and built web servers, perform: create empty draft; add first capability unconnected; add second after selected node/outcome; edit it; set route; validate; reload direct URL; verify graph, revision, diagnostics, evidence. Repeat the core add/inspect flow at mobile viewport. Assert only owned child processes are terminated.

- [ ] **Step 4: Run final verification**

Run:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
pnpm --dir web test:workflow-console:e2e
pnpx react-doctor@latest --verbose --scope changed
git diff --check
```

Document any pre-existing unrelated failures exactly; do not weaken assertions.

- [ ] **Step 5: Update docs, archive, review, and commit**

Update README flow and roadmap completion, archive this plan, run independent code review, fix actionable findings, and commit:

```powershell
git commit -am "feat: complete draft authoring workbench"
```

## Self-Review

- Spec coverage: RPC authorization, evidence, schemas, literal/bind, graph insertion, update, route, validate, conflicts, dirty navigation, Discover/Drafts handoff, deferred controls, desktop/mobile, and real-server acceptance each map to a task.
- Placeholder scan: no `TBD`, generic “handle errors”, or undefined neighboring interface remains.
- Type consistency: `DraftWorkspace`, `ConsoleWriteExecutor`, `DraftAuthoringClient`, `SchemaField`, `FieldSource`, and `WorkbenchSelection` are defined before consumers.
- Boundary check: artifact/deployment/run redesign and deletion remain excluded.
