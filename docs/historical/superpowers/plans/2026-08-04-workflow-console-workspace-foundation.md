# Workflow Console Workspace Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat console home with a routed lifecycle workspace that can discover capabilities and inspect persisted draft workspaces through the real browser-authorized workflow RPC path.

**Architecture:** Extend the authored Effect RPC surface with four generated-schema read operations, then expose them through the independent Hono browser policy. React routes consume small capability and draft domain clients built over one evidence-aware read executor; the workspace shell owns connection and evidence while route modules own their reads. Existing artifact/deployment/run exploration remains available through routed lifecycle adapters until later slices replace it.

**Tech Stack:** React 19.2.7, React Router 7.18.1, TypeScript 6.0.3, Effect 3.21.4, Effect RPC 0.75.1, Valibot 1.4.2, Vitest 4.1.9, Playwright 1.61.1, Hono 4.12.27, Vite 8.1.2.

## Global Constraints

- Implement only Slice 1 of `docs/superpowers/specs/2026-08-04-workflow-console-ide-design.md`.
- Add only these browser read operations: `workflow.capabilities.list`, `workflow.capabilities.inspect`, `workflow.draft_workspaces.list`, and `workflow.draft_workspaces.get`.
- Keep Hono authorization independent from generated contract and Effect client coverage.
- Use `runtimeSchemasFor()` for Effect payload and success schemas; do not handwrite duplicate Effect schemas.
- Keep React ignorant of string-named operations; only domain adapters may call the generic read executor.
- Decode interpreted browser payloads with Valibot before route state sees them.
- Do not add draft mutation, artifact creation, admin writes, credential editing, graph editing, result persistence, or fake streaming.
- Preserve `/present`, `/presenter`, and presentation synchronization behavior.
- Desktop and mobile must support read-only discovery and draft inspection; mobile graph wiring is out of scope.
- Reuse the established editorial console typography and color tokens. Do not introduce a second theme or purple styling.
- Add a concise comment or docstring at non-obvious security, stale-response, and process-lifecycle seams.
- Run scoped tests after every task. Do not rely on the full Python suite for this TypeScript slice.

---

## File Structure

New console workspace files:

```text
web/apps/console/src/workspace/
  ConsoleShell.tsx                 persistent lifecycle navigation and outlet
  ConsoleWorkspace.tsx             connection/evidence owner
  context.ts                       route-facing workspace interface
  EvidenceLedger.tsx               operation receipt details
  domain/
    errors.ts                      normalized console read errors
    read-executor.ts               callOperation + evidence + decode seam
    capability-client.ts           capability list/inspect interface and adapter
    capability-models.ts           Valibot interpreted decoders
    draft-workspace-client.ts      draft list/load interface and adapter
    draft-workspace-models.ts      Valibot interpreted decoders
    lifecycle-clients.ts           artifact/deployment/run read interfaces
  routes/
    DiscoverRoute.tsx              capability search/list/detail
    DraftIndexRoute.tsx            persisted workspace index
    DraftDetailRoute.tsx           summary, diagnostics, and raw-document escape hatch
    LifecycleRoute.tsx             routed adapter over existing explorer
```

Tests live beside the module they exercise. `global.css` remains the console
stylesheet for this slice; do not create another global stylesheet.

---

### Task 1: Add Capability And Draft Read RPCs

**Files:**
- Modify: `web/packages/rpc/src/rpcs.ts`
- Modify: `web/packages/rpc/src/method-registry.ts`
- Modify: `web/packages/rpc/src/service.ts`
- Modify: `web/packages/rpc/src/index.ts`
- Modify: `web/packages/rpc/src/json-schema/authored-rpc-fixtures.ts`
- Modify: `web/packages/rpc/src/json-schema/rpc-parity.test.ts`
- Modify: `web/packages/rpc/src/generated/workflow-contract.test.ts`
- Modify: `web/packages/rpc/src/service.test.ts`

**Interfaces:**
- Consumes: `runtimeSchemasFor(method)` and the checked generated workflow manifest.
- Produces: four new authored `Rpc` values, operation metadata, interpreted result types, and executable `WorkflowRpc.execute()` cases.

- [ ] **Step 1: Add failing authored-boundary and service tests**

Extend the expected authored methods in `rpc-parity.test.ts` and
`workflow-contract.test.ts` in the established authored registry order:

```ts
const expectedMethods = [
  "workflow.health",
  "workflow.sources.list",
  "workflow.capabilities.list",
  "workflow.capabilities.inspect",
  "workflow.draft_workspaces.list",
  "workflow.draft_workspaces.get",
  "workflow.artifacts.list",
  "workflow.artifacts.inspect",
  "workflow.deployments.list",
  "workflow.deployments.inspect",
  "workflow.deployments.validate",
  "workflow.runs.list",
  "workflow.runs.inspect",
  "workflow.runs.start",
  "workflow.runs.resume",
  "workflow.runs.trace",
];
```

Add service cases with these representative parameters and wire results:

```ts
{
  operation: "workflow.capabilities.list",
  params: { query: "document", source_id: "local.lda_docs", limit: 25 },
  result: {
    capabilities: [{
      kind: "node_spec",
      name: "local.lda_docs.read_documents",
      source_id: "local.lda_docs",
      description: "Read selected project documents.",
      outcomes: ["ok", "error"],
      is_async: false,
      input_fields: ["names"],
      output_fields: ["documents"],
    }],
    next_cursor: null,
    total: 1,
  },
}
```

Add corresponding fixtures for capability inspect, draft list, and draft get.
The draft get fixture must set `include_draft: true` and include a minimal
canonical draft object so optional full-document decoding is exercised.

- [ ] **Step 2: Run the RPC tests and confirm the red state**

Run:

```powershell
pnpm --dir web --filter @lda/workflow-rpc test -- src/generated/workflow-contract.test.ts src/json-schema/rpc-parity.test.ts src/service.test.ts
```

Expected: failures report the four methods missing from `WorkflowRpcs`, the
operation registry, or service dispatch.

- [ ] **Step 3: Define generated runtime RPC schemas**

In `rpcs.ts`, add one generated schema pair and `Rpc.make` per method:

```ts
const capabilityListSchemas = runtimeSchemasFor("workflow.capabilities.list");
export const WorkflowCapabilitiesListPayloadSchema = capabilityListSchemas.payload;
export const WorkflowCapabilitiesListResultSchema = capabilityListSchemas.success;
export const WorkflowCapabilitiesList = Rpc.make("workflow.capabilities.list", {
  payload: WorkflowCapabilitiesListPayloadSchema,
  success: WorkflowCapabilitiesListResultSchema,
  error: Schema.Never,
});
```

Repeat this exact pattern for:

```text
workflow.capabilities.inspect
workflow.draft_workspaces.list
workflow.draft_workspaces.get
```

Add the four RPCs to `WorkflowRpcs`. Keep list before inspect/get within each
namespace and keep existing namespace ordering stable.

- [ ] **Step 4: Add interpreted result models and metadata**

In `method-registry.ts`, add public interpreted types with camel-case fields:

```ts
export type CapabilitySummaryInterpreted = {
  readonly kind: "node_spec" | "wrapper_artifact";
  readonly name: string;
  readonly sourceId: string;
  readonly description: string | null;
  readonly outcomes: ReadonlyArray<string>;
  readonly isAsync: boolean;
  readonly inputFields: ReadonlyArray<string>;
  readonly outputFields: ReadonlyArray<string>;
  readonly artifactId?: string;
  readonly version?: number;
  readonly title?: string;
};

export type DraftWorkspaceInterpreted = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly title: string | null;
  readonly status: "valid" | "invalid" | "conflict";
  readonly diagnostics: ReadonlyArray<{
    readonly code: string;
    readonly path: string;
    readonly message: string;
    readonly stepId: string | null;
    readonly repairHint: string | null;
    readonly details: Readonly<Record<string, unknown>>;
  }>;
  readonly summary: {
    readonly name: unknown;
    readonly start: unknown;
    readonly stepCount: number;
    readonly routeCount: number;
    readonly steps: ReadonlyArray<string>;
  };
  readonly draft: Readonly<Record<string, unknown>> | null;
};
```

Interpret capability details without flattening away `input_schema`,
`output_schema`, `wrapper_hints`, or wrapper `required_capabilities`. Return
those JSON objects under camel-case names.

Use these equivalent CLI formatters:

```ts
// list: uv run wf cap list [--query X] [--source X] [--cursor X] [--limit N]
// inspect: uv run wf cap inspect QUALIFIED_NAME
// draft list: uv run wf draft list
// draft get: uv run wf draft inspect WORKSPACE_ID [--include-draft]
```

Decode params and results with the exported generated schemas before
formatting/interpreting. Do not cast raw `unknown` results.

- [ ] **Step 5: Wire service dispatch and exports**

Import the four payload schemas in `service.ts` and add exhaustive switch cases:

```ts
case "workflow.draft_workspaces.get": {
  const payload = yield* decodePayload(
    WorkflowDraftWorkspacesGetPayloadSchema,
    params,
  );
  return yield* client["workflow.draft_workspaces.get"](payload);
}
```

Use the existing `decodePayload` helper and preserve the final `never`
exhaustiveness check. Export new RPC values, schemas, and interpreted types from
`index.ts`.

- [ ] **Step 6: Make parity fixtures describe the four operations**

Add `AuthoredRpcFixture` entries using the generated payload/success schemas.
Each entry must include one valid payload, one invalid payload, one valid
success, and one invalid success. For example, capability inspect rejects a
blank `qualified_name`, and draft get rejects a missing `workspace_id`.

Update only the expected authored method count. The exact existing run mismatch
list remains unchanged and the translator blocker list remains empty.

- [ ] **Step 7: Verify Task 1**

Run:

```powershell
pnpm --dir web --filter @lda/workflow-rpc test
pnpm --dir web --filter @lda/workflow-rpc typecheck
pnpm --dir web --filter @lda/workflow-rpc contract:check
```

Expected: all RPC tests pass, six existing skips remain, contract drift is
clean, and the authored Effect operation count is 16.

- [ ] **Step 8: Commit Task 1**

```powershell
git add web/packages/rpc/src
git commit -m "feat: expose console discovery reads"
```

---

### Task 2: Authorize The New Browser Reads

**Files:**
- Modify: `web/apps/server/src/browser-operation-policy.ts`
- Modify: `web/apps/server/src/browser-operation-policy.test.ts`
- Modify: `web/apps/server/src/app.test.ts`
- Modify: `web/apps/console/src/connection/contracts.ts`
- Modify: `web/apps/console/src/connection/api.test.ts`

**Interfaces:**
- Consumes: Task 1 `OperationName` union and operation metadata.
- Produces: Hono-authorized read methods and browser DTO decoding for their success envelopes.

- [ ] **Step 1: Pin the intended allowlist in failing tests**

Insert the four methods after `workflow.sources.list` in the exact allowlist
test. Add one table-driven `/api/rpc` test that sends all four methods and
expects the runner to receive them. Retain the negative admin test and add a
negative mutation case for `workflow.draft_workspaces.create_empty`.

```ts
it.each([
  "workflow.capabilities.list",
  "workflow.capabilities.inspect",
  "workflow.draft_workspaces.list",
  "workflow.draft_workspaces.get",
] as const)("authorizes the read operation %s", async (operation) => {
  // POST /api/rpc and assert HTTP 200 plus the same operation.
});
```

- [ ] **Step 2: Run server tests and confirm the red state**

Run:

```powershell
pnpm --dir web --filter @lda/web-server test -- src/browser-operation-policy.test.ts src/app.test.ts
```

Expected: the four read operations are rejected as unknown.

- [ ] **Step 3: Extend the independent Hono allowlist**

Add exactly the four read methods to `browserAllowedOperationNames`. Keep the
security comment and do not derive this array from `WorkflowRpcs` or generated
operation inventory.

- [ ] **Step 4: Extend the console success-envelope operation decoder**

Add the same four literals to `OperationNameSchema` in
`connection/contracts.ts`. Do not replace the Valibot browser DTO with Effect
runtime dependencies in this slice.

Add an API test that returns a successful `workflow.draft_workspaces.get`
envelope and verifies `callOperation()` accepts it. Keep `interpreted` unknown
at this transport seam; domain clients decode it in Task 3.

- [ ] **Step 5: Verify Task 2**

Run:

```powershell
pnpm --dir web --filter @lda/web-server test
pnpm --dir web --filter @lda/console test -- src/connection/api.test.ts
pnpm --dir web --filter @lda/web-server typecheck
pnpm --dir web --filter @lda/console typecheck
```

Expected: all commands pass, admin auth and draft mutation remain rejected.

- [ ] **Step 6: Commit Task 2**

```powershell
git add web/apps/server/src web/apps/console/src/connection
git commit -m "feat: authorize console workspace reads"
```

---

### Task 3: Add Evidence-Aware Domain Clients

**Files:**
- Create: `web/apps/console/src/workspace/domain/errors.ts`
- Create: `web/apps/console/src/workspace/domain/read-executor.ts`
- Create: `web/apps/console/src/workspace/domain/read-executor.test.ts`
- Create: `web/apps/console/src/workspace/domain/capability-models.ts`
- Create: `web/apps/console/src/workspace/domain/capability-models.test.ts`
- Create: `web/apps/console/src/workspace/domain/capability-client.ts`
- Create: `web/apps/console/src/workspace/domain/capability-client.test.ts`
- Create: `web/apps/console/src/workspace/domain/draft-workspace-models.ts`
- Create: `web/apps/console/src/workspace/domain/draft-workspace-models.test.ts`
- Create: `web/apps/console/src/workspace/domain/draft-workspace-client.ts`
- Create: `web/apps/console/src/workspace/domain/draft-workspace-client.test.ts`
- Create: `web/apps/console/src/workspace/domain/lifecycle-clients.ts`
- Create: `web/apps/console/src/workspace/domain/lifecycle-clients.test.ts`

**Interfaces:**
- Consumes: `callOperation`, `OperationName`, `RpcResponse`, and app `EvidenceRecord`.
- Produces: `ConsoleReadExecutor`, `CapabilityClient`, read-only `DraftWorkspaceClient`, `ArtifactClient`, `DeploymentClient`, and `RunClient`.

- [ ] **Step 1: Write failing decoder tests**

Pin the browser view models:

```ts
export type CapabilitySummary = {
  readonly kind: "node_spec" | "wrapper_artifact";
  readonly name: string;
  readonly sourceId: string;
  readonly description: string | null;
  readonly outcomes: ReadonlyArray<string>;
  readonly inputFields: ReadonlyArray<string>;
  readonly outputFields: ReadonlyArray<string>;
};

export type DraftWorkspace = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly title: string | null;
  readonly status: "valid" | "invalid" | "conflict";
  readonly diagnostics: ReadonlyArray<DraftDiagnostic>;
  readonly summary: DraftWorkspaceSummary;
  readonly draft: Readonly<Record<string, unknown>> | null;
};
```

Tests must prove discriminated capability kinds, nullable fields, optional draft
documents, malformed diagnostic rejection, and unconstrained `summary.name` /
`summary.start` preservation.

- [ ] **Step 2: Implement Valibot decoders**

Use focused schemas and a shared local `decode(label, schema, value)` helper in
each models file. Export:

```ts
decodeCapabilityPage(value: unknown): CapabilityPage
decodeCapabilityDetail(value: unknown): CapabilityDetail
decodeDraftWorkspacePage(value: unknown): DraftWorkspacePage
decodeDraftWorkspace(value: unknown): DraftWorkspace
```

Do not decode raw snake-case wire payloads here. These schemas decode the
camel-case interpreted results produced by Task 1.

- [ ] **Step 3: Write failing executor tests**

Define the interface:

```ts
export interface ConsoleReadExecutor {
  run<T>(
    operation: OperationName,
    params: unknown,
    decode: (value: unknown) => T,
  ): Promise<T>;
}
```

Tests must prove:

- a success records one evidence receipt and returns decoded data;
- a browser failure records failed evidence and throws `ConsoleClientError`;
- a decoder failure becomes `ConsoleClientError` with kind `decode`;
- a rejected fetch becomes kind `transport`; and
- evidence ids remain unique across consecutive reads.

- [ ] **Step 4: Implement normalized errors and executor**

In `errors.ts`, define:

```ts
export type ConsoleClientErrorKind =
  | "connection"
  | "not_found"
  | "permission"
  | "decode"
  | "transport"
  | "operation";

export class ConsoleClientError extends Error {
  readonly name = "ConsoleClientError";
  constructor(
    readonly kind: ConsoleClientErrorKind,
    readonly operation: OperationName,
    message: string,
  ) {
    super(message);
  }
}
```

`createConsoleReadExecutor({ target, recordEvidence, invoke = callOperation })`
owns a monotonically increasing evidence sequence. Map `invalid_target` and
`upstream_unreachable` to `connection`, `unknown_operation` to `permission`,
`rpc_decode_error` to `decode`, and other structured failures to `operation`.
Thrown network errors map to `transport`.

- [ ] **Step 5: Write failing domain-client tests**

Pin these interfaces:

```ts
export interface CapabilityClient {
  list(input: {
    readonly query?: string;
    readonly sourceId?: string;
    readonly cursor?: string;
    readonly limit?: number;
  }): Promise<CapabilityPage>;
  inspect(qualifiedName: string): Promise<CapabilityDetail>;
}

export interface DraftWorkspaceClient {
  list(): Promise<DraftWorkspacePage>;
  load(workspaceId: string): Promise<DraftWorkspace>;
}

export interface ArtifactClient {
  list(input: { readonly cursor?: string; readonly limit?: number }): Promise<ArtifactList>;
  inspect(artifactId: string, version: number): Promise<ArtifactDetail>;
}

export interface DeploymentClient {
  list(): Promise<DeploymentList>;
  inspect(deploymentId: string): Promise<DeploymentDetail>;
  validate(deploymentId: string): Promise<DeploymentValidation>;
}

export interface RunClient {
  list(input: { readonly cursor?: string; readonly limit?: number }): Promise<RunList>;
  inspect(runId: string): Promise<RunDetail>;
  trace(runId: string, start: number, limit: number): Promise<TracePage>;
}
```

Assert exact lowering for the new and existing read domains:

```ts
expect(executor.run).toHaveBeenCalledWith(
  "workflow.capabilities.list",
  { query: "document", source_id: "local.lda_docs", limit: 50 },
  decodeCapabilityPage,
);

expect(executor.run).toHaveBeenCalledWith(
  "workflow.draft_workspaces.get",
  { workspace_id: "draft-report", include_draft: true },
  decodeDraftWorkspace,
);

expect(executor.run).toHaveBeenCalledWith(
  "workflow.runs.trace",
  { run_id: "run_123", trace_range: { start: 50, limit: 50 } },
  decodeTracePage,
);
```

- [ ] **Step 6: Implement both client adapters**

Export `createCapabilityClient(executor)`,
`createDraftWorkspaceClient(executor)`, and
`createLifecycleClients(executor)`. The latter returns
`{ artifacts, deployments, runs }` satisfying the three interfaces above and
reuses the existing lifecycle Valibot decoders. Omit undefined list parameters
rather than sending explicit `undefined`. Reject blank inspect/load identifiers
and invalid versions/ranges before calling the executor with a
`ConsoleClientError` of kind `operation`.

- [ ] **Step 7: Verify Task 3**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/domain
pnpm --dir web --filter @lda/console typecheck
```

Expected: all domain tests and typecheck pass.

- [ ] **Step 8: Commit Task 3**

```powershell
git add web/apps/console/src/workspace/domain
git commit -m "feat: add console read clients"
```

---

### Task 4: Build The Routed Workspace Shell

**Files:**
- Create: `web/apps/console/src/workspace/context.ts`
- Create: `web/apps/console/src/workspace/ConsoleWorkspace.tsx`
- Create: `web/apps/console/src/workspace/ConsoleWorkspace.test.tsx`
- Create: `web/apps/console/src/workspace/ConsoleShell.tsx`
- Create: `web/apps/console/src/workspace/ConsoleShell.test.tsx`
- Create: `web/apps/console/src/workspace/EvidenceLedger.tsx`
- Create: `web/apps/console/src/workspace/EvidenceLedger.test.tsx`
- Modify: `web/apps/console/src/app/AppRoutes.tsx`
- Modify: `web/apps/console/src/app/App.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**
- Consumes: existing connection reducer, `ConnectionHeader`, Task 3 executor factory.
- Produces: `ConsoleWorkspaceContextValue`, nested `/console/*` route shell, and persistent evidence surface.

- [ ] **Step 1: Write failing shell and route tests**

Test these behaviors with `MemoryRouter`:

- `/` redirects to `/console/discover`;
- `/console` redirects to `/console/discover`;
- lifecycle links include Discover, Drafts, Artifacts, Deployments, Runs, and Results;
- `/present` and `/presenter` do not render console navigation;
- disconnected routes show the connection prompt and a route-level unavailable
  message rather than issuing reads;
- connecting records health evidence once; and
- evidence remains visible after navigating between console routes.

Use a tiny test outlet that reads the workspace context; do not mock internal
React state.

- [ ] **Step 2: Define the route-facing context**

In `context.ts`:

```ts
export type ConsoleWorkspaceContextValue = {
  readonly connection: ConnectionState;
  readonly connectedTarget: string | null;
  readonly recordEvidence: (record: EvidenceRecord) => void;
  readonly readExecutor: ConsoleReadExecutor | null;
};

export const useConsoleWorkspace = (): ConsoleWorkspaceContextValue =>
  useOutletContext<ConsoleWorkspaceContextValue>();
```

`readExecutor` is `null` while disconnected. Route modules must render an
unavailable state instead of constructing a client without a target.

- [ ] **Step 3: Implement connection ownership**

Move the connect-generation logic from `ConsoleHome` into `ConsoleWorkspace`.
Keep stale health responses from changing a newer target. Do not load sources,
demo state, lifecycle lists, or route data in this module.

Render:

```tsx
<ConsoleShell connection={state} onConnect={onSubmit} onDraftChange={onDraftChange}>
  <Outlet context={workspaceContext} />
</ConsoleShell>
```

Create one memoized read executor per connected target. Memoize or otherwise
stabilize `recordEvidence` and the context value so route effects do not refire
on unrelated shell renders or reset the executor's evidence sequence.

- [ ] **Step 4: Implement the shell and evidence ledger**

Use semantic regions:

```tsx
<div className="console-workspace">
  <header className="console-workspace__header">
    <ConnectionHeader
      state={connection}
      onSubmit={onConnect}
      onDraftChange={onDraftChange}
    />
  </header>
  <nav aria-label="Workflow lifecycle">
    {lifecycleLinks.map((link) => (
      <NavLink key={link.to} to={link.to}>{link.label}</NavLink>
    ))}
  </nav>
  <main id="console-workspace-main">{children}</main>
  <aside aria-label="Operation evidence">
    <EvidenceLedger records={connection.evidence} />
  </aside>
</div>
```

Use `NavLink` active state. The evidence ledger renders operation, duration,
equivalent CLI, request, and response in collapsed `<details>` rows. Keep the
connection target form available in the header without occupying a full-width
card after connection.

The desktop shell uses a narrow lifecycle rail, flexible main pane, and bounded
evidence pane. Below 850 px, use a horizontal scrollable nav and move evidence
below main content. Ensure keyboard focus and reduced-motion behavior remain
intact.

- [ ] **Step 5: Define nested application routes**

Update `AppRoutes.tsx` to this shape. In Task 4, define a local
`WorkspaceRoutePending({ label })` and use it for each nested leaf; do not
import route modules that do not exist yet:

```tsx
<Route path="/" element={<Navigate to="/console/discover" replace />} />
<Route path="/console" element={<ConsoleWorkspace />}>
  <Route index element={<Navigate to="discover" replace />} />
  <Route path="discover" element={<WorkspaceRoutePending label="Discover" />} />
  <Route path="drafts" element={<WorkspaceRoutePending label="Drafts" />} />
  <Route path="drafts/:workspaceId" element={<WorkspaceRoutePending label="Draft" />} />
  <Route path="artifacts" element={<WorkspaceRoutePending label="Artifacts" />} />
  <Route path="artifacts/:artifactId/:version" element={<WorkspaceRoutePending label="Artifact" />} />
  <Route path="deployments" element={<WorkspaceRoutePending label="Deployments" />} />
  <Route path="deployments/:deploymentId" element={<WorkspaceRoutePending label="Deployment" />} />
  <Route path="runs" element={<WorkspaceRoutePending label="Runs" />} />
  <Route path="runs/:runId" element={<WorkspaceRoutePending label="Run" />} />
</Route>
```

During this task, use a local `WorkspaceRoutePending` element for routes whose
modules arrive in Tasks 5-7. Delete every pending element in Task 7; no pending
route ships in the completed slice.

- [ ] **Step 6: Verify Task 4**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/ConsoleWorkspace.test.tsx src/workspace/ConsoleShell.test.tsx src/workspace/EvidenceLedger.test.tsx src/app/App.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: shell tests pass; presentation routes remain isolated.

- [ ] **Step 7: Commit Task 4**

```powershell
git add web/apps/console/src/workspace web/apps/console/src/app web/apps/console/src/styles/global.css
git commit -m "feat: add console workspace shell"
```

---

### Task 5: Implement Capability Discovery

**Files:**
- Create: `web/apps/console/src/workspace/routes/DiscoverRoute.tsx`
- Create: `web/apps/console/src/workspace/routes/DiscoverRoute.test.tsx`
- Create: `web/apps/console/src/workspace/routes/useCapabilityDiscovery.ts`
- Create: `web/apps/console/src/workspace/routes/useCapabilityDiscovery.test.tsx`
- Modify: `web/apps/console/src/app/AppRoutes.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**
- Consumes: `useConsoleWorkspace`, `createCapabilityClient`, and Task 3 capability models.
- Produces: searchable `/console/discover` list/detail route with bounded pagination.

- [ ] **Step 1: Write failing controller tests**

Pin controller state and actions:

```ts
export type CapabilityDiscoveryController = {
  readonly phase: "disconnected" | "loading" | "ready" | "error";
  readonly query: string;
  readonly sourceId: string;
  readonly items: ReadonlyArray<CapabilitySummary>;
  readonly selected: CapabilityDetail | null;
  readonly nextCursor: string | null;
  readonly message: string | null;
  readonly setQuery: (value: string) => void;
  readonly setSourceId: (value: string) => void;
  readonly search: () => void;
  readonly loadMore: () => void;
  readonly inspect: (qualifiedName: string) => void;
};
```

Tests cover initial load with `limit: 50`, explicit search, source filtering,
page append, capability inspect, malformed-result error, disconnected state,
and stale list/inspect responses after a newer request.

- [ ] **Step 2: Implement the discovery controller**

Create clients from `readExecutor`. Use separate generation refs for
list and inspect operations. Search replaces items; load-more appends by
capability name without duplicates. A target change clears selection and starts
one fresh list request.

- [ ] **Step 3: Write failing route tests**

Test the visible contract:

- heading `Discover capabilities`;
- search and source-filter fields;
- compact rows with kind, source, input fields, output fields, and outcomes;
- explicit empty, loading, and error states;
- selected detail showing input/output schema and wrapper hints;
- `Load more capabilities` only when `nextCursor` exists; and
- no Add-to-draft button in this read-only slice.

- [ ] **Step 4: Implement the split discovery view**

Use a two-pane desktop layout: searchable results on the left and selected
contract on the right. On mobile, stack the selected detail after the list.
Use Lucide icons already installed for node-spec and wrapper-artifact kinds;
retain visible text labels. Render JSON schemas in scroll-contained `<pre>`
regions under meaningful headings, not as the page's primary content.

- [ ] **Step 5: Replace the pending discovery route and verify**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/routes/DiscoverRoute.test.tsx src/workspace/routes/useCapabilityDiscovery.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: all discovery tests pass and no operation fires while disconnected.

- [ ] **Step 6: Commit Task 5**

```powershell
git add web/apps/console/src/workspace/routes web/apps/console/src/app/AppRoutes.tsx web/apps/console/src/styles/global.css
git commit -m "feat: add capability discovery route"
```

---

### Task 6: Implement Read-Only Draft Routes

**Files:**
- Create: `web/apps/console/src/workspace/routes/DraftIndexRoute.tsx`
- Create: `web/apps/console/src/workspace/routes/DraftIndexRoute.test.tsx`
- Create: `web/apps/console/src/workspace/routes/DraftDetailRoute.tsx`
- Create: `web/apps/console/src/workspace/routes/DraftDetailRoute.test.tsx`
- Create: `web/apps/console/src/workspace/routes/useDraftWorkspace.ts`
- Create: `web/apps/console/src/workspace/routes/useDraftWorkspace.test.tsx`
- Modify: `web/apps/console/src/app/AppRoutes.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**
- Consumes: `useConsoleWorkspace`, `createDraftWorkspaceClient`, and route `workspaceId`.
- Produces: `/console/drafts` and `/console/drafts/:workspaceId` with URL-owned identity.

- [ ] **Step 1: Write failing draft controller tests**

`useDraftWorkspace` accepts `workspaceId: string | null` and exposes list and
detail load states plus `refresh()`. Tests prove:

- list uses `client.list()`;
- detail uses `client.load(workspaceId)` with `include_draft: true` through the adapter;
- changing workspace id ignores the first late detail response;
- reconnect clears stale data and reloads;
- errors retain no false saved/valid state; and
- refresh repeats the currently relevant read.

- [ ] **Step 2: Implement the controller**

Use distinct list/detail generation refs. Do not put selected workspace identity
in reducer state; it comes from the URL. Preserve a previously loaded list while
refreshing, but clear detail when the URL id changes.

- [ ] **Step 3: Write failing index and detail route tests**

Index assertions:

- heading `Draft workspaces`;
- rows link to `/console/drafts/:workspaceId`;
- title fallback uses workspace id;
- revision, status, step count, and route count are visible;
- empty and error states are explicit.

Detail assertions:

- breadcrumbs include Drafts and workspace id;
- status and revision are prominent facts;
- summary lists start step and step ids;
- diagnostics show code, path, message, step id, and repair hint;
- raw draft is closed by default in `<details>`;
- missing draft displays `Full draft document was not returned`;
- no mutation, compile, or artifact buttons exist.

- [ ] **Step 4: Implement both routes**

Use semantic tables/lists for the index and definition lists for facts. Status
must be text plus color. Keep diagnostics adjacent to summary facts. The raw
document escape hatch uses a bounded, horizontally scrollable code region.

- [ ] **Step 5: Replace pending draft routes and verify**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/routes/DraftIndexRoute.test.tsx src/workspace/routes/DraftDetailRoute.test.tsx src/workspace/routes/useDraftWorkspace.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: all draft tests pass and direct detail URLs load independently of the
index route.

- [ ] **Step 6: Commit Task 6**

```powershell
git add web/apps/console/src/workspace/routes web/apps/console/src/app/AppRoutes.tsx web/apps/console/src/styles/global.css
git commit -m "feat: add draft workspace routes"
```

---

### Task 7: Route Existing Lifecycle Exploration And Remove The Flat Home

**Files:**
- Create: `web/apps/console/src/workspace/routes/LifecycleRoute.tsx`
- Create: `web/apps/console/src/workspace/routes/LifecycleRoute.test.tsx`
- Modify: `web/apps/console/src/lifecycle/LifecycleExplorer.tsx`
- Modify: `web/apps/console/src/lifecycle/LifecycleExplorer.test.tsx`
- Modify: `web/apps/console/src/lifecycle/useLifecycleExplorer.ts`
- Modify: `web/apps/console/src/lifecycle/useLifecycleExplorer.test.tsx`
- Modify: `web/apps/console/src/lifecycle/state.ts`
- Modify: `web/apps/console/src/lifecycle/state.test.ts`
- Modify: `web/apps/console/src/app/AppRoutes.tsx`
- Modify: `web/apps/console/src/app/App.test.tsx`
- Modify: `web/apps/console/src/app/state.ts`
- Modify: `web/apps/console/src/app/state.test.ts`
- Delete: `web/apps/console/src/app/ConsoleHome.tsx`
- Delete: `web/apps/console/src/components/SourceInventory.tsx`
- Delete: `web/apps/console/src/components/SourceInventory.test.tsx`
- Delete: `web/apps/console/src/demo/LdaReportDemoPanel.tsx`
- Delete: `web/apps/console/src/demo/LdaReportDemoPanel.test.tsx`
- Modify: `web/apps/console/src/styles/global.css`

**Interfaces:**
- Consumes: Task 3 lifecycle read clients, existing explorer state, workspace context, and route params.
- Produces: routed artifact/deployment/run collection and detail entry points without the old flat console.

- [ ] **Step 1: Write failing route-synchronization tests**

For each route kind, assert:

```text
/console/artifacts/report/2 -> selectArtifact("report@2")
/console/deployments/report.default -> selectDeployment("report.default")
/console/runs/run_123 -> selectRun("run_123")
```

Clicking a record must navigate to its canonical detail URL. Collection routes
must render the explorer without selecting a record. A late inspect response
after navigating to another id remains rejected by the existing generation
guards.

- [ ] **Step 2: Implement `LifecycleRoute`**

Accept `kind: "artifact" | "deployment" | "run"`. Construct Task 3 lifecycle
clients from the workspace `readExecutor` and pass those clients to
`useLifecycleExplorer`. Read route params and select the matching record in an
effect. Wrap selection callbacks so clicks navigate first and controller
selection follows the URL.

Refactor `useLifecycleExplorer` so it accepts
`{ artifacts, deployments, runs } | null` instead of target plus
`recordEvidence`. Replace every internal operation string and `callOperation`
call with the matching domain-client method. Keep the existing generation
guards and load-state reducer behavior.

Pass `primaryKind` to `LifecycleExplorer` and set
`data-primary-lifecycle-kind` on its root. Use CSS order/emphasis to put the
route's collection first without hiding the linked lifecycle context. Do not
redesign graph or execution modes in this slice.

Remove the explorer-local Raw focus mode, `rawEvidenceRef`, and raw-evidence
reducer state. The persistent shell evidence ledger is now the single evidence
surface, so retaining both would duplicate records and ownership.

- [ ] **Step 3: Remove pending route elements and wire all routes**

Replace every `WorkspaceRoutePending` with a real route from Tasks 5-7. Add a
Results nav item that is visibly marked `Later` and non-link text; do not create
an empty `/console/results` route in this slice. This is the only exception to
the target route map and avoids shipping a placeholder page.

- [ ] **Step 4: Remove the old flat home and dead console-only panels**

Delete `ConsoleHome`, `SourceInventory`, and the standalone
`LdaReportDemoPanel`. Do not delete timeline hooks or presentation modules used
by `/present`.

Remove `SourceRecord`, source loading fields, and source reducer actions from
`app/state.ts`; discovery now owns capability reads and later administration
will own source inventory. Update reducer tests to retain only connection and
evidence behavior.

- [ ] **Step 5: Run focused migration tests**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/workspace/routes/LifecycleRoute.test.tsx src/lifecycle src/app
pnpm --dir web --filter @lda/console typecheck
```

Expected: console routes pass, presentation route tests pass, and no import of
`ConsoleHome`, `SourceInventory`, or `LdaReportDemoPanel` remains. Also verify:

```powershell
rg -n -g '!*.test.*' "callOperation|workflow\.artifacts|workflow\.deployments|workflow\.runs" web/apps/console/src/lifecycle web/apps/console/src/workspace/routes
```

Expected: no direct transport call or operation-name string remains in React
route/lifecycle modules; operation names occur only in domain adapters and tests.

- [ ] **Step 6: Commit Task 7**

```powershell
git add web/apps/console/src
git commit -m "refactor: route console lifecycle workspace"
```

---

### Task 8: Add Real-Server Acceptance And Complete Documentation

**Files:**
- Create: `web/apps/console/e2e/workflow-console.spec.ts`
- Modify: `web/package.json`
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/project_map.md`
- Move after all verification passes: `docs/superpowers/plans/2026-08-04-workflow-console-workspace-foundation.md` to `docs/historical/superpowers/plans/2026-08-04-workflow-console-workspace-foundation.md`

**Interfaces:**
- Consumes: built console/server, `uv run wf-rpc-server`, example Python sources, and public browser routes.
- Produces: deterministic full-stack acceptance coverage and current documentation.

- [x] **Step 1: Build a self-contained Playwright process harness**

Follow the process ownership pattern in `e2e/presentation-sync.spec.ts`: reserve
ports, spawn only recorded child processes, collect output, wait for readiness,
and terminate children in `afterAll` without killing unrelated developer
servers.

The test creates a temporary config with:

```json
{
  "server": {
    "store": { "kind": "filesystem", "root": "<temp>/store" },
    "transports": [{
      "kind": "rpc_http",
      "host": "127.0.0.1",
      "port": 0,
      "path": "/rpc"
    }],
    "sources": [{
      "id": "local.lda_docs",
      "kind": "python",
      "path": "<absolute examples/lda_report_workflow>",
      "module": "document_source",
      "registry": "registry"
    }]
  }
}
```

Replace the shown port `0` with the reserved RPC port before writing JSON. Spawn:

```text
uv run wf-rpc-server --config <temp-config> --host 127.0.0.1 --port <rpc-port>
node web/apps/server/dist/index.js
```

Set `WEB_HOST=127.0.0.1` and the reserved web port for the Hono child. The built
server serves `console/dist`; do not start Vite in this acceptance test.

- [x] **Step 2: Seed one real draft through direct JSON-RPC**

After the Python server is healthy, POST this request directly to its `/rpc`
endpoint. Direct seeding is test setup and does not broaden browser policy:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "workflow.draft_workspaces.create_from_capability",
  "params": {
    "workspace_id": "console-e2e",
    "capability_name": "local.lda_docs.read_documents",
    "name": "console_e2e",
    "title": "Console E2E Draft"
  }
}
```

Assert the seed response has no JSON-RPC error before opening the browser.

- [x] **Step 3: Add desktop acceptance assertions**

At 1280 x 800:

1. open `/console/discover`;
2. enter the dynamic RPC target and connect;
3. assert `local.lda_docs.read_documents` is listed;
4. select it and assert input/output contract headings;
5. navigate to Drafts;
6. open `Console E2E Draft`;
7. assert workspace id, revision 1, status, step count, and diagnostics region;
8. expand raw draft and assert `local.lda_docs.read_documents`; and
9. expand evidence and assert capability list plus draft get receipts.

- [x] **Step 4: Add mobile inspection assertions**

At 390 x 844, open the seeded draft detail directly after setting the target in
session storage, then click Connect and wait for the detail read. Assert the
lifecycle nav scrolls horizontally, summary and diagnostics remain readable,
raw draft can open, and no graph-authoring control or mutation button exists.

- [x] **Step 5: Add the acceptance script**

Add:

```json
"test:workflow-console:e2e": "pnpm build && pnpm --filter @lda/console exec playwright test e2e/workflow-console.spec.ts --workers=1"
```

Do not add a second Playwright dependency or global process manager.

- [x] **Step 6: Run the full verification gate**

Run:

```powershell
pnpm --dir web --filter @lda/workflow-rpc contract:check
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
pnpm --dir web test:workflow-console:e2e
git diff --check
```

Expected: all tests, typechecks, builds, contract checks, and both Playwright
viewports pass. The known Vite chunk-size warning may remain; no new warning is
accepted silently.

- [x] **Step 7: Run final code review and fix valid findings**

Use the repository code-review workflow against the first task commit. Review
both standards and this plan. Fix concrete correctness, security, accessibility,
or spec findings and rerun their narrowest relevant tests before the full gate.

- [x] **Step 8: Update live documentation**

Document:

- new `/console/*` routes and connection flow in `web/README.md`;
- Slice 1 completion and Slice 2 draft graph authoring as the next console item
  in `docs/current_roadmap.md`; and
- `workspace/domain` clients plus the routed console shell in
  `docs/project_map.md`.

Move this completed plan to the matching `docs/historical/` path and update any
live link to the historical path.

- [x] **Step 9: Commit Task 8**

```powershell
git add web/apps/console/e2e web/package.json web/README.md docs/current_roadmap.md docs/project_map.md docs/superpowers/plans docs/historical/superpowers/plans
git commit -m "test: verify console workspace foundation"
```

---

## Completion Checklist

- [x] The browser can call exactly the four new read operations and no new writes.
- [x] React route modules call domain clients, not `callOperation` or operation strings.
- [x] Artifact, deployment, and run reads also cross domain-client interfaces.
- [x] `/` and `/console` resolve to `/console/discover`.
- [x] Capability discovery supports search, source filter, inspect, and pagination.
- [x] Draft index and direct detail routes use backend workspace identity and revision.
- [x] Existing artifact/deployment/run exploration remains reachable through canonical routes.
- [x] The old flat `ConsoleHome` and dead console-only demo/source panels are removed.
- [x] Connection and evidence persist across console route navigation.
- [x] Desktop and mobile read-only acceptance passes against a real Python server.
- [x] Presentation and presenter routes remain unchanged in behavior.
- [x] Docs describe the implemented state rather than the target state of later slices.
