# Workflow Console Capability Playground Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe, schema-generated capability playground to Discover so an operator can inspect and directly call one capability without first creating a workflow.

**Architecture:** Extend the existing authored Effect RPC boundary for `workflow.capabilities.call`, expose it through a configured browser policy, and invoke it through the console's existing write executor. Resolve self-contained local JSON Schema references before field normalization, keep direct-call state in a focused controller, and sanitize/bound protocol evidence before it reaches application state.

**Tech Stack:** TypeScript 6, React 19, Effect RPC, Hono, Valibot, Vitest, Testing Library, Vite, pnpm.

## Global Constraints

- Direct capability calls are immediate operations, not workflow runs: do not create graph, state, route, run, or trace records in the UI.
- Never call on selection, tab change, reconnect, form change, or automatic retry.
- Require explicit side-effect acknowledgement before every selected capability can be called.
- Use generated JSON Schema through `runtimeSchemasFor`; do not handwrite transport payload/result schemas.
- Support only local JSON Pointer references beginning with `#/`; reject external references, cycles, and structural `$ref` siblings that require schema intersection.
- Browser capability calls are enabled automatically only when `WEB_HOST` is loopback. Non-loopback hosts require `WEB_ENABLE_CAPABILITY_CALLS=1`.
- Bound evidence to 100 records, depth 8, 100 collection entries, 4096 characters per string, and 32 KiB serialized per request or response.
- Redact keys case-insensitively for `authorization`, `cookie`, `set-cookie`, `token`, `access_token`, `refresh_token`, `secret`, `password`, `api_key`, and `api-key`.
- Preserve the existing package boundaries: RPC transport in `web/packages/rpc`, browser policy in `web/apps/server`, and product projection/UI in `web/apps/console`.
- Do not introduce MCP Inspector, n8n, another state store, or another transport as a dependency.
- Add comments or docstrings at security boundaries and non-obvious truncation/reference-resolution logic.

## Reference Patterns, Not Dependencies

- [MCP Inspector](https://github.com/modelcontextprotocol/inspector) demonstrates the useful product loop: inspect a tool contract, generate parameter inputs, execute explicitly, and show request/result/error history. Keep our implementation inside the existing workflow API and console architecture.
- [MCP Inspector documentation](https://modelcontextprotocol.io/docs/2026-07-28/tools/inspector) treats the inspector as a development surface rather than a workflow runtime. Preserve that same distinction.
- [n8n execution-data guidance](https://github.com/n8n-io/n8n-docs/blob/main/docs/deploy/host-n8n/configure-n8n/scaling/manage-execution-data.md) warns that retained execution data grows without pruning. Apply that lesson to the console evidence ledger with deterministic bounds and redaction.

---

### Task 1: Resolve Self-Contained Local Schema References

**Files:**
- Create: `web/apps/console/src/workspace/schema-form/schema-reference.ts`
- Create: `web/apps/console/src/workspace/schema-form/schema-reference.test.ts`
- Modify: `web/apps/console/src/workspace/schema-form/schema-field.ts`
- Modify: `web/apps/console/src/workspace/schema-form/schema-field.test.ts`
- Modify: `web/apps/console/src/workspace/schema-form/SchemaForm.tsx`
- Modify: `web/apps/console/src/workspace/schema-form/SchemaForm.test.tsx`
- Modify: `web/apps/console/src/workspace/schema-form/SchemaFieldControl.tsx`

**Interfaces:**
- Produces: `resolveLocalSchemaNode(rootSchema: unknown, schemaNode: unknown): SchemaReferenceResolution`.
- Produces: `SchemaReferenceResolution = { readonly ok: true; readonly schema: unknown } | { readonly ok: false; readonly reason: string }`.
- Extends: `SchemaFormProps` with `readonly showSourceControls?: boolean`, defaulting to `true`.
- Preserves: `normalizeSchema(schema: unknown): SchemaField` and all existing authoring callers.

- [ ] **Step 1: Add failing resolver tests**

Test direct and nested `#/$defs/...` references, `#/definitions/...`, escaped JSON Pointer tokens (`~0`, `~1`), annotation siblings (`title`, `description`, `default`), unresolved pointers, external references, cycles, and structural siblings such as `properties` beside `$ref`.

```ts
expect(resolveLocalSchemaNode(root, root.properties?.ref)).toEqual({
  ok: true,
  schema: {
    type: "object",
    title: "Resource",
    properties: {
      logical_source: { type: "string" },
      uri: { type: "string" },
    },
    required: ["logical_source", "uri"],
  },
});

expect(resolveLocalSchemaNode(root, { $ref: "https://example.test/schema" })).toEqual({
  ok: false,
  reason: "External schema references are not supported.",
});
```

- [ ] **Step 2: Verify the resolver tests fail**

Run: `pnpm --dir web --filter @lda/console test -- src/workspace/schema-form/schema-reference.test.ts`

Expected: FAIL because `schema-reference.ts` does not exist.

- [ ] **Step 3: Implement the local-reference resolver**

Implement an internal recursive resolver that carries the root document and an active-reference set. Decode pointer tokens with `~1 -> /` and `~0 -> ~`; only traverse own object properties and non-negative array indices. Merge only annotation siblings `title`, `description`, and `default` over the resolved schema.

```ts
export type SchemaReferenceResolution =
  | { readonly ok: true; readonly schema: unknown }
  | { readonly ok: false; readonly reason: string };

export const resolveLocalSchemaNode = (
  rootSchema: unknown,
  schemaNode: unknown,
): SchemaReferenceResolution => resolveNode(rootSchema, schemaNode, new Set());
```

Return a stable failure reason for malformed pointers, missing targets, cycles, external references, and structural siblings. Do not mutate the input schema.

- [ ] **Step 4: Integrate resolution into field normalization**

Change internal normalization to retain `rootSchema` across recursive object and array fields. Resolve each node before reading `type`, `properties`, or `items`. On failure, return the existing JSON fallback field with the resolver's reason.

Add a realistic `wf.source.read_resource` schema test whose `ref` property points to `#/$defs/SourceResourceRef`; assert generated child fields for `logical_source`, `uri`, and defaulted `kind`.

- [ ] **Step 5: Add and test source-control suppression**

Thread `showSourceControls` from `SchemaForm` into `SchemaFieldControl`. When false, render literal inputs only and do not render path-source selectors. Keep the default true so draft authoring behavior is unchanged.

```tsx
<SchemaForm
  schema={schema}
  showSourceControls={false}
  submitLabel="Call capability"
/>
```

- [ ] **Step 6: Run focused schema-form verification**

Run: `pnpm --dir web --filter @lda/console test -- src/workspace/schema-form/schema-reference.test.ts src/workspace/schema-form/schema-field.test.ts src/workspace/schema-form/SchemaForm.test.tsx`

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```powershell
git add web/apps/console/src/workspace/schema-form
git commit -m "feat: resolve local capability schema references"
```

---

### Task 2: Author the Capability Call RPC

**Files:**
- Modify: `web/packages/rpc/src/rpcs.ts`
- Modify: `web/packages/rpc/src/index.ts`
- Modify: `web/packages/rpc/src/method-registry.ts`
- Modify: `web/packages/rpc/src/service.ts`
- Modify: `web/packages/rpc/src/service.test.ts`
- Modify: `web/packages/rpc/src/json-schema/rpc-parity.test.ts`
- Modify: registry tests adjacent to `method-registry.ts` if present

**Interfaces:**
- Produces: `WorkflowCapabilitiesCallPayloadSchema`, `WorkflowCapabilitiesCallResultSchema`, and `WorkflowCapabilitiesCall`.
- Extends: `OperationName` with the already-generated `"workflow.capabilities.call"` operation.
- Produces interpreted camel-case result:

```ts
type CapabilityCallInterpreted = {
  readonly qualifiedName: string;
  readonly sourceId: string;
  readonly kind: "node_spec" | "wrapper_artifact";
  readonly deploymentId: string | null;
  readonly outcome: string;
  readonly output: Record<string, unknown> | null;
  readonly diagnostics: ReadonlyArray<{
    readonly boundSource: string | null;
    readonly code: string;
    readonly logicalRef: string;
    readonly message: string;
    readonly repairHint: string | null;
    readonly severity: string;
  }>;
};
```

- [ ] **Step 1: Add failing RPC parity and service tests**

Pin that the authored RPC group contains `workflow.capabilities.call`, malformed payloads fail decoding before fetch, and a successful exchange dispatches the exact JSON-RPC method with `qualified_name`, `payload`, and optional `deployment_id`.

- [ ] **Step 2: Verify RPC tests fail**

Run: `pnpm --dir web --filter @lda/workflow-rpc test -- src/json-schema/rpc-parity.test.ts src/service.test.ts`

Expected: FAIL because the generated inventory contains the operation but `WorkflowRpcs` does not.

- [ ] **Step 3: Define the RPC from generated runtime schemas**

```ts
const capabilityCallSchemas = runtimeSchemasFor("workflow.capabilities.call");
export const WorkflowCapabilitiesCallPayloadSchema = capabilityCallSchemas.payload;
export const WorkflowCapabilitiesCallResultSchema = capabilityCallSchemas.success;

export const WorkflowCapabilitiesCall = Rpc.make("workflow.capabilities.call", {
  payload: WorkflowCapabilitiesCallPayloadSchema,
  success: WorkflowCapabilitiesCallResultSchema,
  error: Schema.Never,
});
```

Add it to `WorkflowRpcs` and export it through `index.ts`.

- [ ] **Step 4: Add registry metadata and interpretation**

Register the operation with `idempotency: "write"`. Build the equivalent CLI as `uv run wf cap call <qualified-name> --input <json>` and append `--deployment <id>` only when present. Use the existing shell-argument helper for both the JSON payload and identifiers. Decode the result through `WorkflowCapabilitiesCallResultSchema`; do not cast raw objects.

- [ ] **Step 5: Dispatch the operation in the service switch**

Decode with `WorkflowCapabilitiesCallPayloadSchema`, then call:

```ts
return yield* client.workflow["capabilities.call"](payload);
```

Keep the exhaustive `unreachableOperation` guard intact.

- [ ] **Step 6: Run RPC package verification**

Run: `pnpm --dir web --filter @lda/workflow-rpc test`

Run: `pnpm --dir web --filter @lda/workflow-rpc typecheck`

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```powershell
git add web/packages/rpc/src
git commit -m "feat: expose capability calls through workflow rpc"
```

---

### Task 3: Configure the Browser Operation Security Boundary

**Files:**
- Modify: `web/apps/server/src/browser-operation-policy.ts`
- Modify: `web/apps/server/src/browser-operation-policy.test.ts`
- Modify: `web/apps/server/src/app.ts`
- Modify: `web/apps/server/src/app.test.ts`
- Modify: `web/apps/server/src/index.ts`
- Modify: `web/apps/console/src/connection/contracts.ts`
- Modify: `web/apps/console/src/connection/contracts.test.ts`

**Interfaces:**
- Produces: `BrowserOperationDecision = "allowed" | "disabled" | "unknown"`.
- Produces: `createBrowserOperationPolicy(options: { readonly enableCapabilityCalls: boolean }): { readonly classify(operation: string): BrowserOperationDecision }`.
- Produces: `capabilityCallsEnabledForHost(hostname: string, override: string | undefined): boolean`.
- Extends: `createApp` dependencies with an injected browser operation policy.
- Adds: browser error code `operation_disabled`.

- [ ] **Step 1: Add failing policy tests**

Assert that existing operations remain allowed, unknown operations remain unknown, and `workflow.capabilities.call` is disabled or allowed according to configuration. Cover `127.0.0.1`, `localhost`, `::1`, `0.0.0.0`, LAN addresses, and explicit `WEB_ENABLE_CAPABILITY_CALLS=1`.

- [ ] **Step 2: Verify policy tests fail**

Run: `pnpm --dir web --filter @lda/web-server test -- src/browser-operation-policy.test.ts src/app.test.ts`

Expected: FAIL because policy classification is currently boolean and static.

- [ ] **Step 3: Implement policy classification**

Keep the existing authored allowlist. Treat capability call as a known conditional operation rather than adding it unconditionally.

```ts
const conditionalOperations = new Set<OperationName>([
  "workflow.capabilities.call",
]);
```

`classify()` must return `unknown` for generated-but-unexposed operations such as admin methods.

- [ ] **Step 4: Return a distinct disabled response**

In `/api/rpc`, return HTTP 403 and:

```json
{
  "ok": false,
  "error": {
    "code": "operation_disabled",
    "message": "workflow.capabilities.call is disabled for this console server"
  },
  "exchange": { "request": null, "response": null }
}
```

Keep unknown operations on their existing 400 response. Add the new code to the Valibot browser contract.

- [ ] **Step 5: Wire startup configuration**

Build the policy once in `index.ts`. Loopback hosts enable direct calls by default; non-loopback hosts require the exact string `"1"`. Log a startup warning when the override enables calls on a non-loopback host. Do not claim authentication or TLS.

- [ ] **Step 6: Run server and connection-contract tests**

Run: `pnpm --dir web --filter @lda/web-server test`

Run: `pnpm --dir web --filter @lda/console test -- src/connection/contracts.test.ts`

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```powershell
git add web/apps/server/src web/apps/console/src/connection
git commit -m "feat: guard browser capability calls by host policy"
```

---

### Task 4: Bound and Redact Console Evidence

**Files:**
- Create: `web/apps/console/src/workspace/domain/evidence-policy.ts`
- Create: `web/apps/console/src/workspace/domain/evidence-policy.test.ts`
- Modify: `web/apps/console/src/app/state.ts`
- Modify: `web/apps/console/src/app/state.test.ts`
- Modify: `web/apps/console/src/workspace/domain/executor-protocol.ts`
- Modify: `web/apps/console/src/workspace/domain/read-executor.test.ts`
- Modify: `web/apps/console/src/workspace/domain/write-executor.test.ts`
- Modify: `web/apps/console/src/workspace/ConsoleWorkspace.tsx`
- Update: tests and fixtures constructing `EvidenceRecord`

**Interfaces:**
- Extends: `EvidenceRecord` with `readonly target: string`.
- Produces: `sanitizeEvidenceValue(value: unknown): unknown`.
- Produces: `sanitizeEvidenceRecord(record: EvidenceRecord): EvidenceRecord`.
- Produces: `retainEvidence(records: readonly EvidenceRecord[], record: EvidenceRecord): readonly EvidenceRecord[]`.

- [ ] **Step 1: Add failing evidence-policy tests**

Cover case-insensitive redaction, depth truncation, string truncation, array/object entry truncation, 32 KiB aggregate request/response budgets, preservation of ordinary scalar data, and retention of only the newest 100 records.

```ts
expect(sanitizeEvidenceValue({ Authorization: "Bearer secret", value: "ok" })).toEqual({
  Authorization: "[redacted]",
  value: "ok",
});
```

- [ ] **Step 2: Verify evidence tests fail**

Run: `pnpm --dir web --filter @lda/console test -- src/workspace/domain/evidence-policy.test.ts src/app/state.test.ts`

Expected: FAIL because evidence is currently unbounded and unsanitized.

- [ ] **Step 3: Implement the pure sanitizer**

Use a recursive projector with an explicit byte budget. Redact matching keys before traversing their values. Use stable markers such as `[redacted]`, `[truncated: depth limit]`, and `[truncated: evidence limit]`. Never mutate source objects.

Document why the aggregate budget is applied independently to request and response.

- [ ] **Step 4: Apply policy before application state**

Replace `appendEvidence` with `retainEvidence`, sanitizing the incoming record and slicing to the newest 100. This makes the reducer the single retention boundary for live console evidence.

- [ ] **Step 5: Record the target on every executor path**

Add `target: options.target` in `createConsoleExecutor` records, including invocation failure, protocol failure, mismatch, and success. Add the connected target to the health evidence constructed in `ConsoleWorkspace`.

- [ ] **Step 6: Update fixtures and run focused tests**

Run: `pnpm --dir web --filter @lda/console test -- src/workspace/domain/evidence-policy.test.ts src/workspace/domain/read-executor.test.ts src/workspace/domain/write-executor.test.ts src/app/state.test.ts`

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```powershell
git add web/apps/console/src/app web/apps/console/src/workspace web/apps/console/src/components web/apps/console/src/presentation
git commit -m "feat: bound and redact console operation evidence"
```

---

### Task 5: Add the Capability Call Domain Boundary

**Files:**
- Modify: `web/apps/console/src/workspace/domain/capability-models.ts`
- Modify: `web/apps/console/src/workspace/domain/capability-models.test.ts`
- Create: `web/apps/console/src/workspace/domain/capability-call-client.ts`
- Create: `web/apps/console/src/workspace/domain/capability-call-client.test.ts`
- Create: `web/apps/console/src/workspace/routes/useCapabilityPlayground.ts`
- Create: `web/apps/console/src/workspace/routes/useCapabilityPlayground.test.tsx`

**Interfaces:**
- Produces: `CapabilityCallResult` and `decodeCapabilityCallResult(value: unknown): CapabilityCallResult`.
- Produces: `callCapability(executor, request): Promise<CapabilityCallResult>`.
- Produces controller fields `phase`, `result`, `message`, `acknowledged`, `deploymentId`, `setAcknowledged`, `setDeploymentId`, `call`, and `reset`.

```ts
export type CapabilityCallRequest = {
  readonly qualifiedName: string;
  readonly payload: Record<string, unknown>;
  readonly deploymentId?: string;
};
```

- [ ] **Step 1: Add failing decoder/client tests**

Pin successful output, `runtime_error` as a decoded completed result, dependency diagnostics, malformed results, snake-case request payload, and omission of blank deployment IDs.

- [ ] **Step 2: Verify domain tests fail**

Run: `pnpm --dir web --filter @lda/console test -- src/workspace/domain/capability-models.test.ts src/workspace/domain/capability-call-client.test.ts`

Expected: FAIL because the call model/client do not exist.

- [ ] **Step 3: Implement the Valibot decoder and client**

Reuse the existing `decode()` helper. Model the exact interpreted camel-case shape emitted by Task 2. The client must use `ConsoleExecutor.run("workflow.capabilities.call", ...)`; it must not call `fetch` or `callOperation` directly.

- [ ] **Step 4: Add failing controller tests**

Cover disconnected, idle, calling, result, and error phases; acknowledgement and deployment reset when capability or target changes; double-submit suppression; and stale completion suppression after selection changes.

- [ ] **Step 5: Implement the controller**

Use request identity or an incrementing generation ref so an earlier promise cannot overwrite a newer selection. Keep `runtime_error` in `phase: "result"`; only transport/protocol/decode failures use `phase: "error"`.

- [ ] **Step 6: Run focused domain/controller tests**

Run: `pnpm --dir web --filter @lda/console test -- src/workspace/domain/capability-models.test.ts src/workspace/domain/capability-call-client.test.ts src/workspace/routes/useCapabilityPlayground.test.tsx`

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```powershell
git add web/apps/console/src/workspace/domain web/apps/console/src/workspace/routes/useCapabilityPlayground.ts web/apps/console/src/workspace/routes/useCapabilityPlayground.test.tsx
git commit -m "feat: add capability playground controller"
```

---

### Task 6: Build the Discover-Route Playground

**Files:**
- Create: `web/apps/console/src/workspace/routes/CapabilityPlayground.tsx`
- Create: `web/apps/console/src/workspace/routes/CapabilityPlayground.test.tsx`
- Modify: `web/apps/console/src/workspace/routes/DiscoverRoute.tsx`
- Modify: `web/apps/console/src/workspace/routes/DiscoverRoute.test.tsx`
- Modify: `web/apps/console/src/styles/workspace.css`
- Move: `web/apps/console/src/workspace/authoring/format-bounded-json.ts` to `web/apps/console/src/workspace/domain/format-bounded-json.ts`
- Move: `web/apps/console/src/workspace/authoring/format-bounded-json.test.ts` to `web/apps/console/src/workspace/domain/format-bounded-json.test.ts`
- Modify: imports of `formatBoundedJson` in workspace authoring/routes

**Interfaces:**
- Consumes: Tasks 1, 4, and 5.
- Produces: `CapabilityPlayground({ capability, target, executor }: CapabilityPlaygroundProps)`.
- Preserves: existing capability search, inspect, pagination, and Add to draft behavior.

- [ ] **Step 1: Move the bounded JSON helper without behavior changes**

Move the generic formatter to `workspace/domain`, update all imports, and run its existing test before adding UI behavior.

Run: `pnpm --dir web --filter @lda/console test -- src/workspace/domain/format-bounded-json.test.ts`

Expected: PASS.

- [ ] **Step 2: Add failing playground component tests**

Test Contract/Try capability views, generated literal-only form, immediate-execution warning, acknowledgement gate, wrapper-only deployment input, in-flight state, successful outcome/output/diagnostics, `runtime_error`, and rejected operation alert.

Assert that changing capability resets acknowledgement and result. Assert no call occurs on render, tab selection, or form change.

- [ ] **Step 3: Verify UI tests fail**

Run: `pnpm --dir web --filter @lda/console test -- src/workspace/routes/CapabilityPlayground.test.tsx src/workspace/routes/DiscoverRoute.test.tsx`

Expected: FAIL because the component is absent.

- [ ] **Step 4: Implement the detail tabs and call form**

Keep the capability list unchanged. Replace the detail body's always-expanded raw schemas with tabs:

- **Contract:** current facts, input/output schemas, wrapper hints, Add to draft.
- **Try capability:** `SchemaForm` with `showSourceControls={false}`, acknowledgement checkbox, optional wrapper deployment ID, and `Call capability` button.

The submit handler must reject serialization issues and non-object root values locally. It passes only literal `result.value` to the controller.

- [ ] **Step 5: Implement the result receipt**

Show capability name, outcome, duration/provenance supplied by evidence where available, diagnostics as a readable list, and output through `formatBoundedJson`. Label `runtime_error` as a completed capability outcome and explain that no workflow run or trace was created.

Use existing workspace visual language and Lucide icons. Do not clone MCP Inspector or n8n styling.

- [ ] **Step 6: Integrate with DiscoverRoute**

Obtain `writeExecutor` and `connectedTarget` from the workspace context, create the controller for the selected capability, and preserve `CreateDraftDialog`. Ensure the conditional operation-disabled response appears inline instead of disconnecting the console.

- [ ] **Step 7: Run focused UI tests and React Doctor**

Run: `pnpm --dir web --filter @lda/console test -- src/workspace/routes/CapabilityPlayground.test.tsx src/workspace/routes/DiscoverRoute.test.tsx`

Run: `pnpm --dir web --filter @lda/console exec react-doctor --verbose`

Expected: tests PASS; no new React Doctor errors.

- [ ] **Step 8: Commit Task 6**

```powershell
git add web/apps/console/src/workspace web/apps/console/src/styles/workspace.css
git commit -m "feat: add capability playground to discover"
```

---

### Task 7: Document, Smoke-Test, and Close the Slice

**Files:**
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/project_map.md` if it enumerates console workspace modules
- Move after all gates pass: `docs/superpowers/plans/2026-08-11-workflow-console-capability-playground.md` to `docs/historical/superpowers/plans/2026-08-11-workflow-console-capability-playground.md`

**Interfaces:**
- Documents: loopback defaults, non-loopback opt-in, side-effect warning, direct-call semantics, evidence limits, and known platform-context limitation.
- Verifies: the complete vertical slice against a running workflow RPC server.

- [ ] **Step 1: Add user-facing runbook documentation**

Document:

```powershell
uv run wf-rpc-server --config wf.config.json --host 127.0.0.1 --port 8765
pnpm --dir web dev
```

Explain that `wf.std.concat` is a suitable direct-call smoke test. Explain that `wf.source.read_resource` should render a proper form after local `$ref` support, but a node-spec direct call can still return `runtime_error` when it requires workflow platform context. State that this is truthful behavior, not a failed form implementation.

Document `WEB_ENABLE_CAPABILITY_CALLS=1` as an explicit non-loopback risk acceptance, not authentication.

- [ ] **Step 2: Run scoped package verification**

Run: `pnpm --dir web --filter @lda/workflow-rpc test`

Run: `pnpm --dir web --filter @lda/web-server test`

Run: `pnpm --dir web --filter @lda/console test`

Expected: PASS.

- [ ] **Step 3: Run full web verification**

Run: `pnpm --dir web test`

Run: `pnpm --dir web typecheck`

Run: `pnpm --dir web build`

Run: `git diff --check`

Expected: all tests and typechecks pass; build succeeds except any already-documented chunk-size warning; no whitespace errors.

- [ ] **Step 4: Perform browser smoke verification**

At `/console/discover`:

1. Connect to `http://127.0.0.1:8765/rpc`.
2. Select `wf.std.concat`; confirm Contract shows schemas and Try capability shows generated fields.
3. Confirm no request occurs before acknowledgement and submit.
4. Submit `items: ["hello", "world"]`, `separator: " "`; verify output and operation evidence.
5. Select `wf.source.read_resource`; verify `logical_source`, `uri`, and defaulted `kind` fields render instead of unresolved `$ref` JSON.
6. Call it without platform context and verify a completed `runtime_error` receipt rather than a transport alert.
7. Verify the evidence ledger shows the target and redacts a synthetic sensitive key in a test fixture; do not send real credentials.
8. Run the web server with a non-loopback host and no override; verify the Try surface receives `operation_disabled` without exposing the call.

- [ ] **Step 5: Request independent code review**

Use the `requesting-code-review` skill against the slice commits. Fix every Critical/Important finding or record a technically specific deferral in the final report.

- [ ] **Step 6: Update roadmap and archive the completed plan**

Mark Workflow Console Slice 4 completed in `docs/current_roadmap.md`, link the historical plan, update any project-map entry, and move this plan only after verification succeeds.

- [ ] **Step 7: Commit Task 7**

```powershell
git add web/README.md docs/current_roadmap.md docs/project_map.md docs/superpowers docs/historical
git commit -m "docs: complete capability playground slice"
```

## Plan Self-Review

- **Spec coverage:** Tasks 1–7 cover local `$ref`, authored RPC parity, browser policy, evidence safety, decoding/controller state, Discover UI, documentation, live smoke, and completion gates.
- **Placeholder scan:** No `TBD`, `TODO`, unspecified error handling, or unnamed test steps remain.
- **Type consistency:** `CapabilityCallRequest`, `CapabilityCallResult`, `SchemaReferenceResolution`, `BrowserOperationDecision`, and evidence-policy function names are defined before downstream use.
- **Scope control:** Composite mixed array/object source bindings remain Workflow Console Slice 5; this plan does not fake `items.0` support or alter Python workflow semantics.
