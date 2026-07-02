# Workflow Console Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first executable `web/` slice: a local React console that
connects through Hono to a loopback workflow JSON-RPC server, lists workflow
sources, and shows interpreted output beside raw protocol evidence.

**Architecture:** A pnpm workspace contains a Vite/React browser app, a Hono
Node server, and a focused TypeScript RPC library. The RPC package owns
Effect schemas, loopback target validation, operation metadata, typed errors,
and upstream execution. Hono is the single `Effect.runPromise` boundary; React
receives ordinary JSON DTOs and never imports Effect at runtime.

**Tech Stack:** Node.js 22+, pnpm 11.3.0, TypeScript 6, React 19, Vite 8,
Hono 4, Effect 3, Vitest 4, React Testing Library, and `tsx`.

---

## Scope And Existing Contracts

Implement only the approved foundation in
`docs/superpowers/specs/2026-07-01-workflow-console-foundation-design.md`.

The public upstream operations are:

```text
workflow.health
workflow.sources.list
```

Current upstream shapes are defined by:

- `src/wf_transport_rpc_http/app.py`: `workflow.health` returns
  `{status, store_root}`.
- `src/wf_transport_rpc_http/models.py`: `workflow.sources.list` accepts
  `{cursor?: string, limit?: 1..100}`.
- `src/wf_api/source_admin.py`: source-list results contain
  `{sources, next_cursor, total}`.
- `src/wf_platform/sources.py`: each source summary contains `id`, `kind`,
  `enabled`, `description`, visibility, permissions, policy, capability counts,
  previews, and `has_more` flags.

Do not modify Python CORS behavior, add workflow mutations, start the Python
server from Node, or expose an arbitrary JSON-RPC relay.

## Locked File Layout

```text
web/
  package.json
  pnpm-lock.yaml
  pnpm-workspace.yaml
  tsconfig.base.json
  README.md
  apps/
    console/
      package.json
      index.html
      tsconfig.json
      vite.config.ts
      src/
        app/App.tsx
        app/state.ts
        components/ConnectionHeader.tsx
        components/ProtocolEvidence.tsx
        components/SourceInventory.tsx
        connection/api.ts
        connection/contracts.ts
        main.tsx
        styles/global.css
        test/setup.ts
    server/
      package.json
      tsconfig.json
      src/app.ts
      src/index.ts
      src/static.ts
  packages/
    rpc/
      package.json
      tsconfig.json
      src/errors.ts
      src/method-registry.ts
      src/protocol.ts
      src/service.ts
      src/target-policy.ts
      src/index.ts
```

Do not create `web/packages/ui` or `web/apps/presentation` in this slice.

### Task 1: Scaffold The pnpm Workspace

**Files:**

- Create: `web/package.json`
- Create: `web/pnpm-workspace.yaml`
- Create: `web/tsconfig.base.json`
- Create: `web/packages/rpc/package.json`
- Create: `web/packages/rpc/tsconfig.json`
- Create: `web/packages/rpc/src/index.ts`
- Create: `web/apps/server/package.json`
- Create: `web/apps/server/tsconfig.json`
- Create: `web/apps/server/src/index.ts`
- Create: `web/apps/console/package.json`
- Create: `web/apps/console/tsconfig.json`
- Create: `web/apps/console/index.html`
- Create: `web/apps/console/vite.config.ts`
- Create: `web/apps/console/src/main.tsx`
- Create: `web/apps/console/src/app/App.tsx`
- Generate: `web/pnpm-lock.yaml`

- [ ] **Step 1: Create the workspace manifests**

Use this root manifest. Keep package versions resolved into the lockfile; do
not add npm, Yarn, Turbo, or Nx configuration.

```json
{
  "name": "@lda/web",
  "private": true,
  "packageManager": "pnpm@11.3.0",
  "engines": { "node": ">=22" },
  "scripts": {
    "dev": "concurrently --kill-others-on-fail --names server,console --prefix-colors blue,green \"pnpm --filter @lda/web-server dev\" \"pnpm --filter @lda/console dev\"",
    "test": "pnpm -r --if-present test",
    "typecheck": "pnpm -r --if-present typecheck",
    "build": "pnpm --filter @lda/workflow-rpc build && pnpm --filter @lda/console build && pnpm --filter @lda/web-server build",
    "start": "pnpm --filter @lda/web-server start"
  },
  "devDependencies": {
    "concurrently": "10.0.3",
    "typescript": "6.0.3"
  }
}
```

```yaml
packages:
  - apps/*
  - packages/*
```

Set strict shared compiler options in `web/tsconfig.base.json`:

```json
{
  "compilerOptions": {
    "target": "ES2023",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

- [ ] **Step 2: Create focused package manifests**

`@lda/workflow-rpc` is private, emits declarations and JavaScript to `dist/`,
and exports no browser UI:

```json
{
  "name": "@lda/workflow-rpc",
  "private": true,
  "type": "module",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    }
  },
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "test": "vitest run",
    "typecheck": "tsc -p tsconfig.json --noEmit"
  },
  "dependencies": { "effect": "3.21.4" },
  "devDependencies": { "vitest": "4.1.9" }
}
```

`@lda/web-server` depends on the RPC package and uses TypeScript path mapping
during `tsx` development. Compiled production code resolves the built workspace
package normally.

```json
{
  "name": "@lda/web-server",
  "private": true,
  "type": "module",
  "scripts": {
    "predev": "pnpm --filter @lda/workflow-rpc build",
    "dev": "tsx watch src/index.ts",
    "prebuild": "pnpm --filter @lda/workflow-rpc build",
    "build": "tsc -p tsconfig.json",
    "start": "node dist/index.js",
    "test": "vitest run",
    "pretypecheck": "pnpm --filter @lda/workflow-rpc build",
    "typecheck": "tsc -p tsconfig.json --noEmit"
  },
  "dependencies": {
    "@hono/node-server": "2.0.6",
    "@lda/workflow-rpc": "workspace:*",
    "effect": "3.21.4",
    "hono": "4.12.27"
  },
  "devDependencies": {
    "@types/node": "26.1.0",
    "tsx": "4.22.4",
    "vitest": "4.1.9"
  }
}
```

`@lda/console` uses no Effect runtime:

```json
{
  "name": "@lda/console",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1 --port 5173 --strictPort",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "typecheck": "tsc -b --pretty false",
    "preview": "vite preview --host 127.0.0.1"
  },
  "dependencies": {
    "@fontsource/barlow-condensed": "5.2.8",
    "@fontsource-variable/source-sans-3": "5.2.9",
    "@fontsource/ibm-plex-mono": "5.2.7",
    "react": "19.2.7",
    "react-dom": "19.2.7"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "6.9.1",
    "@testing-library/react": "16.3.2",
    "@testing-library/user-event": "14.6.1",
    "@types/react": "19.2.17",
    "@types/react-dom": "19.2.3",
    "@vitejs/plugin-react": "6.0.3",
    "jsdom": "29.1.1",
    "vite": "8.1.2",
    "vitest": "4.1.9"
  }
}
```

- [ ] **Step 3: Add TypeScript package configurations**

Use `module`/`moduleResolution: "NodeNext"`, `composite: true`, declaration
output, `rootDir: "src"`, and `outDir: "dist"` for RPC and server packages.
The server imports `@lda/workflow-rpc` through its workspace package export.
Its `predev`, `prebuild`, and `pretypecheck` scripts build that dependency first,
so Node and TypeScript resolve `packages/rpc/dist/` without source-path aliases
or a third development watcher. The server config should reference the package:

```json
{
  "references": [{ "path": "../../packages/rpc" }]
}
```

Use `moduleResolution: "Bundler"`, `jsx: "react-jsx"`, DOM libraries,
`noEmit: true`, and `types: ["vite/client", "vitest/globals"]` for the console.

- [ ] **Step 4: Add a minimal bootable console and development proxy**

`vite.config.ts` must proxy `/api` without rewriting it:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8787",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
```

The placeholder React page should render `lda.chat Workflow Console`; the
placeholder server should be a valid module but must not listen until Task 4.

- [ ] **Step 5: Install and verify the workspace**

Run:

```powershell
pnpm --dir web install
pnpm --dir web typecheck
```

Expected: lockfile created and all three packages typecheck successfully.

- [ ] **Step 6: Commit the scaffold**

```powershell
git add web
git commit -m "build: scaffold workflow console workspace"
```

### Task 2: Define Target Policy And JSON-RPC Protocol Schemas

**Files:**

- Create: `web/packages/rpc/src/errors.ts`
- Create: `web/packages/rpc/src/target-policy.ts`
- Create: `web/packages/rpc/src/protocol.ts`
- Create: `web/packages/rpc/src/target-policy.test.ts`
- Create: `web/packages/rpc/src/protocol.test.ts`
- Modify: `web/packages/rpc/src/index.ts`

- [ ] **Step 1: Write failing target-policy tests**

Cover these exact cases:

```ts
it.each([
  ["http://127.0.0.1:8765/rpc", "http://127.0.0.1:8765/rpc"],
  ["http://localhost:8765/rpc", "http://localhost:8765/rpc"],
  ["http://[::1]:8765/rpc", "http://[::1]:8765/rpc"],
])("accepts loopback target %s", (input, expected) => {
  expect(normalizeLoopbackTarget(input)).toBe(expected);
});

it.each([
  "https://127.0.0.1:8765/rpc",
  "http://example.com:8765/rpc",
  "http://user:pass@127.0.0.1:8765/rpc",
  "http://127.0.0.1/rpc",
  "http://127.0.0.1:8765/rpc?x=1",
  "http://127.0.0.1:8765/rpc#fragment",
])("rejects unsafe target %s", (input) => {
  expect(() => normalizeLoopbackTarget(input)).toThrow(InvalidTargetError);
});
```

Run:

```powershell
pnpm --dir web --filter @lda/workflow-rpc test -- target-policy.test.ts
```

Expected: FAIL because the target-policy module does not exist.

- [ ] **Step 2: Implement loopback normalization**

`normalizeLoopbackTarget(raw: string): string` must:

1. call `new URL(raw)` and translate parse failures into
   `InvalidTargetError`;
2. require `protocol === "http:"`;
3. accept only `127.0.0.1`, `localhost`, and `[::1]` as `url.hostname` values;
4. reject credentials, missing explicit port, query, and fragment;
5. reject numeric ports outside `1..65535`;
6. return the normalized `url.toString()` value;
7. retain the path because configured RPC paths are valid public contracts.

Add a short comment explaining that DNS names other than literal `localhost`
are rejected to avoid DNS-rebinding ambiguity.

- [ ] **Step 3: Write failing protocol tests**

Define tests for:

- a success envelope with matching string id;
- a remote-error envelope with matching string id;
- mismatched ids;
- envelopes containing both `result` and `error`;
- envelopes containing neither;
- malformed JSON-RPC versions and error objects.

Use public helpers rather than testing Effect internals:

```ts
expect(decodeRpcResponse(payload, "req-1")).toEqual({
  jsonrpc: "2.0",
  id: "req-1",
  result: { status: "ok" },
});
```

- [ ] **Step 4: Implement protocol schemas and decoder**

Use `Schema.Struct`, `Schema.Literal`, `Schema.Union`, and
`Schema.decodeUnknownSync`; do not hand-roll field type validation. Decode with
`{onExcessProperty: "error"}` wherever an envelope or operation parameter must
reject unknown keys.

Export:

```ts
export type JsonRpcRequest = {
  readonly jsonrpc: "2.0";
  readonly id: string;
  readonly method: string;
  readonly params: unknown;
};

export type JsonRpcResponse = JsonRpcSuccess | JsonRpcFailure;

export function decodeRpcResponse(
  value: unknown,
  expectedId: string,
): JsonRpcResponse;
```

After schema decoding, explicitly reject a mismatched id. Represent schema or
shape failures as `RpcProtocolError`, not raw parse exceptions.

- [ ] **Step 5: Define all tagged errors**

Use `Data.TaggedError` for:

```text
InvalidTargetError
UnknownOperationError
UpstreamConnectionError
UpstreamTimeoutError
UpstreamResponseTooLargeError
RpcProtocolError
RpcRemoteError
RpcDecodeError
```

Each error carries a safe `message`; remote/protocol errors may additionally
carry bounded raw evidence. Never put stack traces into error DTOs.

- [ ] **Step 6: Run tests and commit**

```powershell
pnpm --dir web --filter @lda/workflow-rpc test
pnpm --dir web --filter @lda/workflow-rpc typecheck
git add web/packages/rpc
git commit -m "feat: define workflow rpc protocol boundary"
```

Expected: all RPC package tests pass.

### Task 3: Add The Method Registry And Effect RPC Service

**Files:**

- Create: `web/packages/rpc/src/method-registry.ts`
- Create: `web/packages/rpc/src/method-registry.test.ts`
- Create: `web/packages/rpc/src/service.ts`
- Create: `web/packages/rpc/src/service.test.ts`
- Modify: `web/packages/rpc/src/index.ts`

- [ ] **Step 1: Write failing registry tests**

Assert the exact public operations and metadata:

```ts
expect(listOperations()).toEqual([
  "workflow.health",
  "workflow.sources.list",
]);

expect(resolveOperation("workflow.sources.list")).toMatchObject({
  method: "workflow.sources.list",
  label: "List sources",
  idempotency: "read",
});

expect(() => resolveOperation("workflow.runs.start")).toThrow(
  UnknownOperationError,
);
```

- [ ] **Step 2: Implement schemas for selected upstream result fields**

Use Effect `Schema`, not handwritten type assertions:

```ts
export const HealthResultSchema = Schema.Struct({
  status: Schema.Literal("ok"),
  store_root: Schema.String,
});

export const SourceSummarySchema = Schema.Struct({
  id: Schema.String,
  kind: Schema.String,
  enabled: Schema.Boolean,
  description: Schema.NullOr(Schema.String),
  tool_count: Schema.Number,
  node_spec_count: Schema.Number,
  reducer_count: Schema.Number,
  prompt_count: Schema.Number,
  resource_count: Schema.Number,
});

export const SourceListResultSchema = Schema.Struct({
  sources: Schema.Array(SourceSummarySchema),
  next_cursor: Schema.NullOr(Schema.String),
  total: Schema.Number,
});
```

Define parameter schemas with an empty object for health and optional cursor
plus bounded integer limit for source list. Unknown parameter keys must be
rejected before fetch.

- [ ] **Step 3: Implement the declarative operation registry**

Each entry must own:

```ts
type OperationDefinition = {
  readonly method: OperationName;
  readonly label: string;
  readonly explanation: string;
  readonly idempotency: "read";
  readonly paramsSchema: Schema.Schema<unknown>;
  readonly resultSchema: Schema.Schema<unknown>;
  readonly equivalentCli: (params: unknown) => string;
  readonly interpret: (result: unknown) => unknown;
};
```

CLI strings are:

```text
uv run wf status
uv run wf source list --limit 50
```

Include `--cursor VALUE` only when a cursor is present. The health card may say
`Server healthy` and expose `storeRoot`; source interpretation returns compact
rows plus `total` and `nextCursor`.

- [ ] **Step 4: Write failing RPC execution tests with injected fetch**

Cover:

- generated string request id and exact JSON-RPC body;
- successful health decoding and interpretation;
- source-list decoding;
- invalid params fail before fetch;
- redirects are rejected;
- remote JSON-RPC errors become `RpcRemoteError`;
- malformed and mismatched responses become `RpcProtocolError`;
- result schema mismatch becomes `RpcDecodeError`;
- timeout becomes `UpstreamTimeoutError`;
- response body above 4 MiB becomes `UpstreamResponseTooLargeError`.

Inject a `fetch`-compatible function and deterministic id/clock dependencies;
do not monkeypatch globals.

- [ ] **Step 5: Implement bounded upstream execution as an Effect service**

Export a `WorkflowRpc` `Context.Tag` whose service has:

```ts
readonly execute: (
  operation: OperationName,
  target: string,
  params: unknown,
) => Effect.Effect<OperationExchange, WorkflowRpcError>;
```

`OperationExchange` contains:

```ts
{
  operation: OperationName;
  label: string;
  interpreted: unknown;
  exchange: {
    request: JsonRpcRequest;
    response: JsonRpcResponse | null;
  };
  equivalentCli: string;
  durationMs: number;
}
```

Implementation requirements:

1. normalize the target on every call;
2. resolve and decode operation params before fetch;
3. use `redirect: "manual"` and reject every `300..399` response;
4. use an `AbortController` with a five-second timeout;
5. check `content-length` when present, then stream and count response bytes so
   the 4 MiB limit is real even without that header;
6. parse JSON, decode the envelope, map remote errors, decode the operation
   result, and interpret it;
7. preserve request and response evidence for successful and remote-error
   cases;
8. do not retry.

Add comments around bounded body streaming and redirect rejection because they
are security behavior, not incidental transport code.

- [ ] **Step 6: Run tests and commit**

```powershell
pnpm --dir web --filter @lda/workflow-rpc test
pnpm --dir web --filter @lda/workflow-rpc typecheck
git add web/packages/rpc
git commit -m "feat: execute registered workflow rpc operations"
```

### Task 4: Expose The Browser-Facing Hono API

**Files:**

- Create: `web/apps/server/src/app.ts`
- Create: `web/apps/server/src/app.test.ts`
- Modify: `web/apps/server/src/index.ts`

- [ ] **Step 1: Write failing Hono route tests**

Build tests through `app.request()` with an injected operation runner. Cover:

```text
GET  /api/health -> 200 {ok:true,status:"ok"}
POST /api/connect -> invokes workflow.health
POST /api/rpc -> invokes workflow.sources.list
POST /api/rpc unknown operation -> 400 before runner call
POST body over 256 KiB -> 413
invalid JSON/body/target -> 400
upstream connection/protocol/decode/remote error -> 502
upstream timeout -> 504
```

Assert that error DTOs never contain `stack`.

- [ ] **Step 2: Define stable browser DTOs and error mapping**

Successful connect response:

```ts
{
  ok: true;
  connection: {
    status: "connected";
    target: string;
    serverStatus: "ok";
    storeRoot: string;
    durationMs: number;
  };
  exchange: { request: unknown; response: unknown };
  equivalentCli: "uv run wf status";
}
```

Successful operation response uses the approved shape:

```ts
{
  ok: true;
  operation: OperationName;
  label: string;
  interpreted: unknown;
  exchange: { request: unknown; response: unknown };
  equivalentCli: string;
  durationMs: number;
}
```

Failure response:

```ts
{
  ok: false;
  error: { code: BrowserErrorCode; message: string };
  exchange: { request: unknown | null; response: unknown | null };
}
```

Use stable codes such as `invalid_target`, `unknown_operation`,
`upstream_unreachable`, `upstream_timeout`, `rpc_remote_error`,
`rpc_protocol_error`, `rpc_decode_error`, and `response_too_large`.

- [ ] **Step 3: Implement `createApp` with dependency injection**

Export:

```ts
export type RunOperation = (
  operation: OperationName,
  target: string,
  params: unknown,
) => Promise<OperationExchange>;

export function createApp(dependencies: {
  readonly runOperation: RunOperation;
}): Hono;
```

Apply `bodyLimit({maxSize: 256 * 1024})` to both POST routes. Parse request
bodies once. `/api/connect` always calls health with `{}`. `/api/rpc` accepts
only the operation-name union exported by the registry.

- [ ] **Step 4: Make `index.ts` the single production Effect boundary**

Create the live RPC layer, construct `runOperation` with one
`Effect.runPromise` call per request, create the app, and bind:

```ts
serve({
  fetch: app.fetch,
  hostname: process.env.WEB_HOST ?? "127.0.0.1",
  port: Number(process.env.WEB_PORT ?? "8787"),
});
```

Reject invalid `WEB_PORT` at startup with one concise error and non-zero exit.
Do not bind all interfaces by default.

- [ ] **Step 5: Run tests and commit**

```powershell
pnpm --dir web --filter @lda/web-server test
pnpm --dir web --filter @lda/web-server typecheck
git add web/apps/server
git commit -m "feat: expose workflow console api"
```

### Task 5: Build Connection State And Connection UI

**Files:**

- Create: `web/apps/console/src/connection/contracts.ts`
- Create: `web/apps/console/src/connection/api.ts`
- Create: `web/apps/console/src/connection/api.test.ts`
- Create: `web/apps/console/src/app/state.ts`
- Create: `web/apps/console/src/app/state.test.ts`
- Create: `web/apps/console/src/components/ConnectionHeader.tsx`
- Create: `web/apps/console/src/components/ConnectionHeader.test.tsx`
- Create: `web/apps/console/src/test/setup.ts`
- Modify: `web/apps/console/src/app/App.tsx`
- Modify: `web/apps/console/src/main.tsx`

- [ ] **Step 1: Define plain browser contracts and API tests**

Mirror server DTOs as TypeScript discriminated unions. Do not import Effect or
the runtime RPC package. Test that the API client:

- posts the exact target to `/api/connect`;
- posts operation and params to `/api/rpc`;
- returns success DTOs;
- returns typed failure DTOs instead of throwing for expected HTTP failures;
- throws only for malformed browser-server responses or browser fetch failure.

- [ ] **Step 2: Define and test the reducer state machine**

Use these phases:

```ts
type ConnectionPhase =
  | "not_configured"
  | "connecting"
  | "connected"
  | "invalid_target"
  | "unreachable"
  | "rpc_error"
  | "malformed_response";
```

State retains `draftTarget` separately from `connectedTarget`. A failed attempt
updates the phase and message but never discards the entered URL or overwrites
the last successful session target.

Reducer tests must pin:

- submit transitions to connecting;
- success records normalized target and evidence;
- failure retains draft input;
- reconnect replaces target only on success;
- restored session target populates the input but remains `not_configured`.

- [ ] **Step 3: Implement the connection header behavior**

The form contains:

- label `Workflow JSON-RPC URL`;
- input defaulting to `http://127.0.0.1:8765/rpc` when no stored value exists;
- `Connect` or `Reconnect` button;
- visible phase, server status, store root, and duration after success;
- concise inline failure message after failure.

On successful connect only:

```ts
sessionStorage.setItem("lda.workflowConsole.target", normalizedTarget);
```

On reload, restore the value but do not call the server automatically.

- [ ] **Step 4: Write component tests**

Use Testing Library and user-event to verify:

- initial default and no automatic request;
- connecting disables only the submit action, not the input;
- invalid/unreachable states retain the typed value;
- successful target is persisted;
- restored target still requires explicit connect;
- status text is exposed through an `aria-live="polite"` region.

- [ ] **Step 5: Run tests and commit**

```powershell
pnpm --dir web --filter @lda/console test
pnpm --dir web --filter @lda/console typecheck
git add web/apps/console
git commit -m "feat: add workflow console connection flow"
```

### Task 6: Add Source Inventory, Protocol Evidence, And Visual System

**Files:**

- Create: `web/apps/console/src/components/SourceInventory.tsx`
- Create: `web/apps/console/src/components/SourceInventory.test.tsx`
- Create: `web/apps/console/src/components/ProtocolEvidence.tsx`
- Create: `web/apps/console/src/components/ProtocolEvidence.test.tsx`
- Create: `web/apps/console/src/styles/global.css`
- Modify: `web/apps/console/src/app/App.tsx`
- Modify: `web/apps/console/src/app/state.ts`
- Modify: `web/apps/console/src/main.tsx`

- [ ] **Step 1: Extend state for source loading and evidence history**

After health succeeds, call `workflow.sources.list` with `{limit: 50}`. Store:

```ts
type EvidenceRecord = {
  readonly id: string;
  readonly operation: string;
  readonly label: string;
  readonly equivalentCli: string;
  readonly request: unknown;
  readonly response: unknown;
  readonly durationMs: number;
};
```

Keep health and source-list records in chronological order. A source-list
failure must leave the connection healthy, show a source-specific error, and
retain both operation records where evidence exists.

- [ ] **Step 2: Write and implement source-inventory tests**

Test compact rows containing:

- source id and kind;
- enabled/disabled status;
- description when present;
- total count across tools, node specs, reducers, prompts, and resources.

An empty inventory renders `No workflow sources reported.` A failed inventory
renders its error without replacing the connection status.

- [ ] **Step 3: Write and implement evidence-drawer tests**

The drawer must:

- remain collapsed by default;
- list health and source-list operations as selectable records;
- display equivalent CLI, duration, formatted request JSON, and formatted
  response JSON;
- render evidence through `<pre><code>{text}</code></pre>`, never HTML;
- show `No response received.` for a null response;
- remain keyboard operable with native buttons and `<details>` or equivalent
  accessible disclosure semantics.

- [ ] **Step 4: Apply the visual direction**

Import the three checked-in npm fonts in `main.tsx`:

```ts
import "@fontsource/barlow-condensed/600.css";
import "@fontsource/barlow-condensed/700.css";
import "@fontsource-variable/source-sans-3";
import "@fontsource/ibm-plex-mono/400.css";
import "./styles/global.css";
```

Define CSS variables for warm paper, ink, slate, signal green, amber, and red.
Use a subtle two-axis grid made from CSS linear gradients. Use Barlow Condensed
for page and section headings, Source Sans 3 for body text, and IBM Plex Mono
for protocol evidence.

Desktop layout:

```text
connection header across full width
source inventory (minmax(0, 1fr)) | protocol evidence (minmax(22rem, 0.7fr))
```

At widths below 850px, stack inventory and evidence. At widths below 560px,
stack URL input and action. Use one connection-state transition and a short
staggered source-row reveal; respect `prefers-reduced-motion`.

Do not add dark mode, a CSS framework, gradients in purple hues, generic metric
cards, or decorative motion unrelated to state changes.

- [ ] **Step 5: Run accessibility-oriented component tests and build**

```powershell
pnpm --dir web --filter @lda/console test
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: tests pass and Vite emits `web/apps/console/dist/`.

- [ ] **Step 6: Commit the console surface**

```powershell
git add web/apps/console
git commit -m "feat: show source inventory and rpc evidence"
```

### Task 7: Serve The Production Console Through Hono

**Files:**

- Create: `web/apps/server/src/static.ts`
- Create: `web/apps/server/src/static.test.ts`
- Modify: `web/apps/server/src/app.ts`
- Modify: `web/apps/server/src/index.ts`
- Modify: `web/apps/server/tsconfig.json`

- [ ] **Step 1: Write failing production-static tests**

Build a temporary console directory containing `index.html` and one asset.
Create the app with that root and assert:

- `/assets/app.js` serves the asset;
- `/some/client/route` serves `index.html`;
- `/api/unknown` remains a JSON 404 and never falls back to HTML;
- a missing console root produces a clear startup error.

- [ ] **Step 2: Implement static and SPA fallback behavior**

Use `@hono/node-server/serve-static`. Resolve the default console directory
from `import.meta.url`, not `process.cwd()`, so `pnpm --dir web start` works from
any directory.

Register routes in this order:

1. all `/api/*` routes;
2. static files;
3. non-API GET fallback to `index.html`;
4. JSON 404 for everything else.

Expose the console root as an injectable `createApp` option so tests do not
depend on the real build output.

- [ ] **Step 3: Build and run the production process**

```powershell
pnpm --dir web build
pnpm --dir web start
```

Expected: one Hono process serves `/api/health`, `/`, static assets, and an SPA
fallback from `127.0.0.1:8787`.

- [ ] **Step 4: Commit production serving**

```powershell
git add web/apps/server
git commit -m "feat: serve workflow console production build"
```

### Task 8: Document, Smoke Test, And Close The Slice

**Files:**

- Create: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-07-01-workflow-console-foundation-design.md`
- Move after completion:
  `docs/superpowers/plans/2026-07-02-workflow-console-foundation.md` to
  `docs/historical/superpowers/plans/2026-07-02-workflow-console-foundation.md`

- [ ] **Step 1: Write the operator runbook**

Document these exact flows in `web/README.md`:

```powershell
# Terminal 1: workflow JSON-RPC server
uv run wf-rpc-server --config wf.config.json --host 127.0.0.1 --port 8765

# Terminal 2: Vite + Hono development processes
pnpm --dir web install
pnpm --dir web dev
```

The browser URL is `http://127.0.0.1:5173`; the pasted target is
`http://127.0.0.1:8765/rpc`.

Also document:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
pnpm --dir web start
```

State clearly that the server accepts loopback HTTP targets only and that the
console does not start or authenticate the Python workflow server.

- [ ] **Step 2: Run the live smoke test**

With the Python server running, verify in the browser:

1. the initial page makes no upstream request;
2. connect succeeds against `http://127.0.0.1:8765/rpc`;
3. source rows appear;
4. raw health and source-list exchanges are selectable;
5. equivalent CLI text is visible;
6. `http://example.com:8765/rpc` is rejected without upstream fetch;
7. stopping the Python server produces the unreachable state while preserving
   the entered URL.

Record only observed behavior in the implementation report. Do not add a
default live-server test to Vitest.

- [ ] **Step 3: Run complete scoped verification**

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
uv run pytest tests\docs -q -n0
uv run ruff check
uv run basedpyright --level error
git diff --check
```

Expected: all commands pass. If repository-wide Python checks expose a
pre-existing failure, prove it on `HEAD`, report it precisely, and do not claim
the suite is clean.

- [ ] **Step 4: Update live docs and archive the completed plan**

Mark roadmap item 3 completed and leave items 4-7 pending. Update the
foundation design status to `Implemented` and add the verification commands.
Move this plan to the historical path and update any live link that points to
the active plan location.

- [ ] **Step 5: Commit the completed slice**

```powershell
git add web docs/current_roadmap.md docs/superpowers/specs/2026-07-01-workflow-console-foundation-design.md docs/historical/superpowers/plans/2026-07-02-workflow-console-foundation.md
git commit -m "docs: record workflow console foundation"
```

## Final Acceptance Checklist

- [ ] `pnpm --dir web dev` starts Vite and Hono with one root command.
- [ ] The browser does not call workflow JSON-RPC directly.
- [ ] Every target is normalized and checked again for each operation.
- [ ] Only `workflow.health` and `workflow.sources.list` are registered.
- [ ] Unknown operations and non-loopback targets fail before fetch.
- [ ] Upstream redirect, timeout, protocol, remote, decode, and size failures
      map to stable browser DTOs.
- [ ] The UI distinguishes all approved connection states.
- [ ] Failed connection input remains editable and preserved.
- [ ] Session storage changes only after successful health.
- [ ] Source inventory and raw protocol evidence both render.
- [ ] Production Hono serves the Vite build and SPA fallback.
- [ ] No Python CORS changes, direct store reads, workflow mutations, graph UI,
      autoplay, replay, agent integration, or presentation app entered scope.
