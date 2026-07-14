# LAN Presentation Synchronization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Pair `/present` and `/presenter` over a trusted LAN so either route can navigate the same canonical presentation hash, reconnect to the latest server snapshot, and end the session from the presenter UI.

**Architecture:** Add a small `@lda/presentation-sync` package that owns bounded wire contracts and decoders shared by browser and server. `@lda/web-server` owns an in-memory room service plus Hono HTTP and WebSocket routes; the console owns one source-owned controller and one pairing panel reused by both routes. Navigation continues to flow through the existing canonical URL hash, so no storyboard behavior moves into the server or sync protocol.

**Tech Stack:** TypeScript 6, Effect Schema 3.21.4, Hono 4.12.27, `@hono/node-server` 2.0.6 WebSocket upgrade support, `ws` 8.21.0, React 19.2.7, `react-qr-code` 2.2.0, Vite 8.1.2, Vitest 4.1.9, Testing Library.

## Global Constraints

- The first release is trusted-LAN only. Do not add TLS, authentication claims, hosted relay behavior, or public-internet setup.
- Synchronize only complete canonical hashes beginning with `#scene/` or `#discuss/`; do not synchronize scroll, forms, timers, disclosures, workflow actions, or local evidence state.
- Existing local controls remain authoritative for navigation semantics. The server stores hashes and revisions but must not import storyboard data.
- Local navigation must continue when pairing, WebSocket connection, or reconnection fails.
- The server snapshot wins after reconnect. Do not merge divergent local and remote histories.
- A room remains reconnectable for 10 minutes after its final connection closes and expires after 2 hours without activity.
- The location revision is monotonic. The first publish at a base revision wins; stale publishers receive the accepted snapshot.
- Pairing works symmetrically from `/present` and `/presenter` through the same panel. A created link targets the opposite route.
- Only a client joined with role `presenter` may send `session.end`.
- Every inbound HTTP and WebSocket payload is bounded and schema-decoded before use.
- Add comments around remote-application suppression, stale-revision convergence, room expiry, and WebSocket proxy behavior because those seams are non-obvious.
- Use TDD and focused test commands in every task. Preserve unrelated working-tree changes.

---

### Task 1: Shared Presentation Sync Contracts

**Files:**

- Create: `web/packages/presentation-sync/package.json`
- Create: `web/packages/presentation-sync/tsconfig.json`
- Create: `web/packages/presentation-sync/src/protocol.ts`
- Create: `web/packages/presentation-sync/src/protocol.test.ts`
- Create: `web/packages/presentation-sync/src/index.ts`
- Modify: `web/package.json`

**Interfaces:**

- Produces `PresentationRole`, `PresentationSnapshot`, `PresentationPresence`, `ClientSyncMessage`, `ServerSyncMessage`, `CreateSessionRequest`, `JoinSessionRequest`, and `SessionGrant`.
- Produces `decodeClientSyncMessage`, `decodeServerSyncMessage`, `decodeCreateSessionRequest`, and `decodeJoinSessionRequest`, each returning a discriminated `{ ok: true, value } | { ok: false, error }` result without exposing Effect internals.
- Produces `isCanonicalPresentationHash`, `normalizeJoinCode`, `MAX_SYNC_MESSAGE_BYTES`, and `MAX_PRESENTATION_HASH_LENGTH`.

- [x] **Step 1: Scaffold the shared package and make the workspace build it first**

Create `web/packages/presentation-sync/package.json` with the same private ESM package pattern as `@lda/workflow-rpc`:

```json
{
  "name": "@lda/presentation-sync",
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
  "dependencies": {
    "effect": "3.21.4"
  },
  "devDependencies": {
    "@types/node": "26.1.0",
    "vitest": "4.1.9"
  }
}
```

Create `web/packages/presentation-sync/tsconfig.json` by copying the compiler shape from `web/packages/rpc/tsconfig.json`, changing only the package path naturally. Modify `web/package.json` so `build` explicitly builds `@lda/presentation-sync` before the console and web server.

- [x] **Step 2: Write failing protocol tests**

Cover these exact behaviors in `protocol.test.ts`:

```ts
it("accepts bounded canonical location publishes", () => {
  expect(decodeClientSyncMessage(JSON.stringify({
    type: "location.publish",
    hash: "#scene/architecture/client/focus/client-operations",
    baseRevision: 4,
    messageId: "msg-4",
  }))).toEqual({
    ok: true,
    value: {
      type: "location.publish",
      hash: "#scene/architecture/client/focus/client-operations",
      baseRevision: 4,
      messageId: "msg-4",
    },
  });
});

it.each(["", "#unknown/x", "scene/thesis/title"])(
  "rejects non-canonical hash %s",
  (hash) => expect(isCanonicalPresentationHash(hash)).toBe(false),
);

it("rejects oversized websocket payloads before JSON decoding", () => {
  const result = decodeClientSyncMessage("x".repeat(MAX_SYNC_MESSAGE_BYTES + 1));
  expect(result).toEqual({ ok: false, error: "message_too_large" });
});

it("normalizes human-entered join codes", () => {
  expect(normalizeJoinCode(" ab-cd 7 ")).toBe("ABCD7");
});
```

Also test unknown variants, negative/fractional revisions, overlong hashes, invalid roles, valid `session.end`/`ping`, all server message variants, and malformed JSON.

- [x] **Step 3: Run the protocol tests and confirm RED**

Run: `pnpm --dir web --filter @lda/presentation-sync test`

Expected: FAIL because `src/protocol.ts` and its exports do not exist.

- [x] **Step 4: Implement bounded Effect Schema decoders**

In `protocol.ts`, define the wire model with these exact bounds and variants:

```ts
export const MAX_SYNC_MESSAGE_BYTES = 16 * 1024;
export const MAX_PRESENTATION_HASH_LENGTH = 2_048;
export const JOIN_CODE_LENGTH = 6;

export type PresentationRole = "presenter" | "audience";
export type PresentationSnapshot = {
  readonly hash: string;
  readonly revision: number;
};
export type PresentationPresence = {
  readonly presenters: number;
  readonly audience: number;
};

export type CreateSessionRequest = {
  readonly role: PresentationRole;
  readonly initialHash: string;
};
export type JoinSessionRequest = {
  readonly role: PresentationRole;
  readonly code: string;
};
export type SessionGrant = {
  readonly sessionId: string;
  readonly code: string;
  readonly connectionToken: string;
  readonly websocketPath: "/api/presentation-sync/ws";
  readonly snapshot: PresentationSnapshot;
};

export type ClientSyncMessage =
  | { readonly type: "location.publish"; readonly hash: string; readonly baseRevision: number; readonly messageId: string }
  | { readonly type: "session.end" }
  | { readonly type: "ping"; readonly nonce: string };

export type ServerSyncMessage =
  | { readonly type: "location.snapshot"; readonly snapshot: PresentationSnapshot; readonly originatingMessageId: string | null }
  | { readonly type: "presence.snapshot"; readonly presence: PresentationPresence }
  | { readonly type: "location.rejected"; readonly reason: "stale_revision"; readonly current: PresentationSnapshot; readonly messageId: string }
  | { readonly type: "session.ended"; readonly reason: "presenter_ended" | "expired" }
  | { readonly type: "protocol.error"; readonly code: "invalid_message" | "message_too_large" | "forbidden"; readonly message: string };
```

Use Effect Schema for runtime shape decoding. Keep the public decoder result plain and stable:

```ts
export type DecodeResult<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: "invalid_json" | "invalid_message" | "message_too_large" };
```

`isCanonicalPresentationHash` must enforce the length bound and only `#scene/` or `#discuss/` prefixes. Bound `messageId` and `nonce` to 128 characters. `normalizeJoinCode` must remove spaces and hyphens, uppercase the value, and leave final length validation to the request decoder.

- [x] **Step 5: Export the contract and verify GREEN**

Export every public symbol from `src/index.ts`. Run:

```powershell
pnpm --dir web --filter @lda/presentation-sync test
pnpm --dir web --filter @lda/presentation-sync typecheck
pnpm --dir web --filter @lda/presentation-sync build
```

Expected: all commands pass.

- [x] **Step 6: Commit the shared protocol**

```powershell
git add web/package.json web/packages/presentation-sync
git commit -m "feat: define presentation sync protocol"
```

---

### Task 2: In-Memory Room State Machine

**Files:**

- Create: `web/apps/server/src/presentation-sync/rooms.ts`
- Create: `web/apps/server/src/presentation-sync/rooms.test.ts`
- Modify: `web/apps/server/package.json`
- Modify: `web/apps/server/tsconfig.json`

**Interfaces:**

- Consumes the shared protocol types from Task 1.
- Produces `createPresentationRoomService(options?)` returning `create`, `join`, `connect`, `disconnect`, `publish`, `ping`, `end`, and `sweepExpired` methods.
- Produces `PresentationPeer`, a transport-neutral `{ send(message), close(code, reason) }` interface so room logic does not import Hono or `ws`.

- [x] **Step 1: Add shared package references**

Add `@lda/presentation-sync: "workspace:*"` to `@lda/web-server` dependencies. Add a TypeScript project reference to `../../packages/presentation-sync`. Update the server's `predev`, `prebuild`, and `pretypecheck` scripts to build both shared packages before server compilation.

- [x] **Step 2: Write failing room-state tests with a fake clock and peers**

Use a deterministic clock and token/code generator. Pin these behaviors:

```ts
const peer = () => ({
  send: vi.fn(),
  close: vi.fn(),
});

it("creates a room at revision zero and joins the opposite role", () => {
  const service = makeService();
  const created = service.create({ role: "presenter", initialHash: "#scene/thesis/title" });
  const joined = service.join({ role: "audience", code: created.code });
  expect(created.snapshot).toEqual({ hash: "#scene/thesis/title", revision: 0 });
  expect(joined.sessionId).toBe(created.sessionId);
});

it("accepts one publish and rejects a stale competing publish", () => {
  const { service, presenterToken, audienceToken } = connectedRoom();
  expect(service.publish(presenterToken, {
    type: "location.publish",
    hash: "#scene/problem/direct-actions",
    baseRevision: 0,
    messageId: "presenter-1",
  }).kind).toBe("accepted");
  expect(service.publish(audienceToken, {
    type: "location.publish",
    hash: "#scene/positioning/landscape",
    baseRevision: 0,
    messageId: "audience-stale",
  })).toEqual({
    kind: "stale",
    current: { hash: "#scene/problem/direct-actions", revision: 1 },
  });
});
```

Also test unique codes, initial snapshot/presence on connect, duplicate-token connection replacement, disconnect presence, 10-minute reconnect grace, 2-hour inactivity expiry, ping activity, presenter termination, audience termination rejection, and broadcast isolation between rooms.

- [x] **Step 3: Run the room tests and confirm RED**

Run: `pnpm --dir web --filter @lda/web-server test -- src/presentation-sync/rooms.test.ts`

Expected: FAIL because `rooms.ts` does not exist.

- [x] **Step 4: Implement the room service**

Use these public constants and method boundary:

```ts
export const EMPTY_ROOM_GRACE_MS = 10 * 60 * 1_000;
export const ROOM_INACTIVITY_TTL_MS = 2 * 60 * 60 * 1_000;

export type PresentationPeer = {
  readonly send: (message: ServerSyncMessage) => void;
  readonly close: (code: number, reason: string) => void;
};

export const createPresentationRoomService = (options: {
  readonly now?: () => number;
  readonly makeId?: () => string;
  readonly makeCode?: () => string;
  readonly makeToken?: () => string;
} = {}) => ({
  create(input: { readonly role: PresentationRole; readonly initialHash: string }): SessionGrant,
  join(input: { readonly role: PresentationRole; readonly code: string }): SessionGrant,
  connect(token: string, peer: PresentationPeer): ConnectResult,
  disconnect(token: string, peer: PresentationPeer): void,
  publish(token: string, peer: PresentationPeer, message: Extract<ClientSyncMessage, { type: "location.publish" }>): PublishResult,
  ping(token: string, peer: PresentationPeer): void,
  end(token: string, peer: PresentationPeer): EndResult,
  sweepExpired(): number,
});
```

Internally keep `roomsById`, `roomIdByCode`, and `membershipByToken` maps. Do not delete membership tokens on socket disconnect; they are the reconnect credential. Match both token and peer identity during disconnect and every state-changing message so a replaced socket's late close or message event cannot affect the newer connection. Record `emptySince` only when the final peer leaves. On accepted publish, increment the revision once and broadcast one `location.snapshot`. On stale publish, send only the publishing peer a `location.rejected`. Add a comment explaining first-writer-wins revision convergence.

- [x] **Step 5: Verify room behavior**

Run:

```powershell
pnpm --dir web --filter @lda/web-server test -- src/presentation-sync/rooms.test.ts
pnpm --dir web --filter @lda/web-server typecheck
```

Expected: focused tests and typecheck pass.

- [x] **Step 6: Commit the room state machine**

```powershell
git add web/apps/server/package.json web/apps/server/tsconfig.json web/apps/server/src/presentation-sync/rooms.ts web/apps/server/src/presentation-sync/rooms.test.ts web/pnpm-lock.yaml
git commit -m "feat: add presentation sync room state"
```

---

### Task 3: Hono Session And WebSocket Endpoints

**Files:**

- Create: `web/apps/server/src/presentation-sync/routes.ts`
- Create: `web/apps/server/src/presentation-sync/routes.test.ts`
- Modify: `web/apps/server/src/app.ts`
- Modify: `web/apps/server/src/index.ts`
- Modify: `web/apps/server/package.json`
- Modify: `web/apps/console/vite.config.ts`

**Interfaces:**

- Consumes `PresentationRoomService` from Task 2 and `upgradeWebSocket` from `@hono/node-server`.
- Produces `addPresentationSyncRoutes(app, { rooms, upgradeWebSocket })`.
- Exposes `POST /api/presentation-sync/sessions`, `POST /api/presentation-sync/sessions/join`, and `GET /api/presentation-sync/ws?token=...`.

- [x] **Step 1: Install the official Node WebSocket dependencies**

Run:

```powershell
pnpm --dir web --filter @lda/web-server add ws@8.21.0
pnpm --dir web --filter @lda/web-server add -D @types/ws@8.18.1
```

Use `upgradeWebSocket` from the already-installed `@hono/node-server`; do not add a second Hono WebSocket adapter.

- [x] **Step 2: Write failing HTTP and two-client WebSocket tests**

Start a real ephemeral Node server in the test with `new WebSocketServer({ noServer: true })`, `serve({ fetch: app.fetch, websocket: { server: wss }, port: 0 })`, and `ws` clients. Test:

- valid creation returns `201`, code, token, snapshot, and `/api/presentation-sync/ws` path;
- invalid hash and invalid/expired code return bounded `400`/`404` JSON errors;
- both sockets receive initial location and presence snapshots;
- presenter and audience updates propagate in both directions;
- stale publish returns `location.rejected` with the accepted snapshot;
- reconnecting with the same token receives the latest snapshot;
- audience `session.end` receives `protocol.error` without ending the room;
- presenter `session.end` broadcasts `session.ended` and closes peers;
- oversized and malformed messages are rejected without crashing the room.

The core propagation assertion should read:

```ts
presenter.send(JSON.stringify({
  type: "location.publish",
  hash: "#scene/planner-runtime/boundary",
  baseRevision: 0,
  messageId: "p-1",
}));
await expectMessage(audience, (message) =>
  message.type === "location.snapshot" && message.snapshot.revision === 1
);
```

- [x] **Step 3: Run endpoint tests and confirm RED**

Run: `pnpm --dir web --filter @lda/web-server test -- src/presentation-sync/routes.test.ts`

Expected: FAIL because no synchronization routes exist.

- [x] **Step 4: Implement HTTP setup and WebSocket routing**

Create route setup with this boundary:

```ts
export const addPresentationSyncRoutes = (
  app: Hono,
  dependencies: {
    readonly rooms: PresentationRoomService;
    readonly upgradeWebSocket: typeof upgradeWebSocket;
  },
): void => { /* register the three routes */ };
```

Creation and join responses must use this shape:

```ts
type SessionGrant = {
  readonly sessionId: string;
  readonly code: string;
  readonly connectionToken: string;
  readonly websocketPath: "/api/presentation-sync/ws";
  readonly snapshot: PresentationSnapshot;
};
```

The WebSocket route reads `token` from the query string. Its callbacks adapt Hono's socket context to a stable `PresentationPeer`, decode every client frame, call the peer-aware `rooms.publish`, `rooms.ping`, or `rooms.end`, and call `rooms.disconnect(token, peer)` on close. Keep messages text-only. Invalid binary/oversized input receives a bounded protocol error and closes with code `1009` or `1003` as appropriate.

- [x] **Step 5: Wire server startup and expiry sweep**

Change `createApp` to accept a required `presentationSync` dependency containing `rooms` and `upgradeWebSocket`, then register sync routes before static routes. Update every `createApp` test call to use a small helper that supplies a fresh room service.

In `index.ts`:

```ts
const rooms = createPresentationRoomService();
const wss = new WebSocketServer({ noServer: true });
const app = createApp({
  runOperation,
  presentationSync: { rooms, upgradeWebSocket },
  ...(staticConsoleRoot ? { consoleRoot: staticConsoleRoot } : {}),
});
const server = serve({
  fetch: app.fetch,
  hostname,
  port,
  websocket: { server: wss },
});
const expirySweep = setInterval(() => rooms.sweepExpired(), 60_000);
expirySweep.unref();
```

Clear `expirySweep`, close active WebSocket clients, and close `wss` during shutdown before waiting for the HTTP server. Bound forced termination so connected clients cannot hold shutdown open indefinitely. Add a comment that the periodic sweep enforces reconnect grace and inactivity expiry without persisting rooms.

- [x] **Step 6: Enable Vite WebSocket proxying**

Add `ws: true` to the existing `/api` proxy in `web/apps/console/vite.config.ts`. Keep the current HTTP error handler. Add a short comment that presentation synchronization shares the API origin in development while Vite HMR keeps its own socket.

- [x] **Step 7: Verify server integration**

Run:

```powershell
pnpm --dir web --filter @lda/web-server test -- src/presentation-sync/routes.test.ts src/app.test.ts
pnpm --dir web --filter @lda/web-server typecheck
pnpm --dir web --filter @lda/web-server build
```

Expected: all pass with no open handles.

- [x] **Step 8: Commit the server transport**

```powershell
git add web/apps/server web/apps/console/vite.config.ts web/pnpm-lock.yaml
git commit -m "feat: serve presentation sync sessions"
```

---

### Task 4: Browser Synchronization Controller

**Files:**

- Create: `web/apps/console/src/presentation/sync/presentation-sync-state.ts`
- Create: `web/apps/console/src/presentation/sync/presentation-sync-state.test.ts`
- Create: `web/apps/console/src/presentation/sync/presentation-sync-client.ts`
- Create: `web/apps/console/src/presentation/sync/presentation-sync-client.test.ts`
- Create: `web/apps/console/src/presentation/sync/usePresentationSync.ts`
- Create: `web/apps/console/src/presentation/sync/usePresentationSync.test.tsx`
- Modify: `web/apps/console/package.json`
- Modify: `web/apps/console/tsconfig.json`

**Interfaces:**

- Produces `usePresentationSync({ role, currentHash, applyRemoteHash })`.
- Produces `PresentationSyncController` with `state`, `startSession`, `joinSession`, `retry`, `leaveSession`, and `endSession`.
- Stores only the reconnect grant in session storage under `lda.presentation-sync.connection.v1`; it does not persist room snapshots or navigation history.

- [x] **Step 1: Add the shared contract dependency**

Add `@lda/presentation-sync: "workspace:*"` to the console dependencies and a TypeScript project reference to `../../packages/presentation-sync`. Add `predev`, `prebuild`, and `pretypecheck` scripts that build the shared package.

- [x] **Step 2: Write reducer tests for every controller state**

Define and test this union:

```ts
export type ConnectedSyncState = {
  readonly grant: SessionGrant;
  readonly snapshot: PresentationSnapshot;
  readonly presence: PresentationPresence;
};

export type PresentationSyncState =
  | { readonly kind: "standalone" }
  | { readonly kind: "creating" }
  | { readonly kind: "joining"; readonly code: string }
  | ConnectedSyncState & { readonly kind: "waiting" | "connected" | "reconnecting" }
  | { readonly kind: "failed"; readonly message: string; readonly retryable: boolean }
  | { readonly kind: "ended"; readonly reason: "presenter_ended" | "expired" | "left" };

export type PresentationSyncController = {
  readonly state: PresentationSyncState;
  readonly startSession: () => Promise<void>;
  readonly joinSession: (code: string) => Promise<void>;
  readonly retry: () => void;
  readonly leaveSession: () => void;
  readonly endSession: () => void;
};
```

Test create/join progress, grant receipt, presence-driven waiting versus connected, reconnect state, accepted snapshots, stale rejection convergence, explicit end, local leave, and retryable failure.

- [x] **Step 3: Write client transport tests**

Use fake `fetch`, `WebSocket`, timer, session storage, and location objects. Pin:

- same-origin HTTP paths;
- `ws://` for HTTP and `wss://` for HTTPS;
- opposite-route join URL construction;
- QR/manual code normalization;
- reconnect delays of `500`, `1_000`, `2_000`, then capped at `5_000` ms;
- saved grant restoration after reload;
- no reconnect after `session.ended` or explicit leave.

- [x] **Step 4: Write hook tests for hash publication and suppression**

The critical feedback-loop test must assert exactly one publish:

```ts
it("applies a remote hash without publishing it back", async () => {
  const applyRemoteHash = vi.fn();
  const { rerender } = renderHook(
    ({ hash }) => usePresentationSync({ role: "audience", currentHash: hash, applyRemoteHash }),
    { initialProps: { hash: "#scene/thesis/title" } },
  );
  fakeSocket.serverMessage(snapshot("#scene/problem/direct-actions", 1));
  expect(applyRemoteHash).toHaveBeenCalledWith("#scene/problem/direct-actions");
  rerender({ hash: "#scene/problem/direct-actions" });
  expect(fakeSocket.sent.filter(isLocationPublish)).toHaveLength(0);
});
```

Also test one local publish, stale snapshot application, server-snapshot-wins reconnect, standalone behavior after server failure, query-string auto-join, and cleanup on unmount.

- [x] **Step 5: Run controller tests and confirm RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/sync/presentation-sync-state.test.ts src/presentation/sync/presentation-sync-client.test.ts src/presentation/sync/usePresentationSync.test.tsx
```

Expected: FAIL because the controller modules do not exist.

- [x] **Step 6: Implement the pure reducer and transport**

Implement `createPresentationSyncClient` with injected browser dependencies for testability:

```ts
export const createPresentationSyncClient = (dependencies: {
  readonly fetch: typeof fetch;
  readonly createWebSocket: (url: string) => WebSocket;
  readonly storage: Storage;
  readonly origin: string;
  readonly protocol: string;
  readonly setTimeout: typeof window.setTimeout;
  readonly clearTimeout: typeof window.clearTimeout;
}) => ({ create, join, connect, publish, end, leave });
```

Use a monotonic client message counter plus `crypto.randomUUID()` for message IDs. Decode every server frame through `decodeServerSyncMessage`. Cap reconnect delay at 5 seconds. Preserve the grant in session storage after transient disconnect, but delete it on explicit leave, explicit end, expired room, or invalid token.

- [x] **Step 7: Implement `usePresentationSync`**

The hook must:

1. restore a saved grant or consume `?pair=CODE` once on mount;
2. connect and apply the initial server snapshot before publishing anything;
3. publish local `currentHash` changes only when connected;
4. set `remoteHashInFlightRef` immediately before `applyRemoteHash`;
5. suppress the next matching `currentHash` effect, then clear the ref;
6. preserve standalone local navigation on all failures; and
7. expose stable action functions.

Add a comment at steps 4-5 explaining why applying a remote hash must not echo it back as another revision.

- [x] **Step 8: Verify the controller**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/sync
pnpm --dir web --filter @lda/console typecheck
```

Expected: all sync controller tests and typecheck pass.

- [x] **Step 9: Commit the browser controller**

```powershell
git add web/apps/console/package.json web/apps/console/tsconfig.json web/apps/console/src/presentation/sync web/pnpm-lock.yaml
git commit -m "feat: add presentation sync client"
```

---

### Task 5: Uniform Pairing Panel And QR Flow

**Files:**

- Create: `web/apps/console/src/presentation/sync/PresentationPairingPanel.tsx`
- Create: `web/apps/console/src/presentation/sync/PresentationPairingPanel.test.tsx`
- Create: `web/apps/console/src/presentation/sync/presentation-sync.css`
- Modify: `web/apps/console/package.json`

**Interfaces:**

- Consumes `PresentationSyncController`, current route role, and opposite-route join URL from Task 4.
- Produces one reusable panel for both audience and presenter routes.

- [x] **Step 1: Install the QR component**

Run: `pnpm --dir web --filter @lda/console add react-qr-code@2.2.0`

- [x] **Step 2: Write failing panel tests**

Test all visible states:

- standalone collapsed trigger named **Pair presentation**;
- expanded Start session and code-entry controls;
- creating/joining disabled controls;
- waiting state with six-character code, QR value, copyable opposite-route URL, and peer counts;
- connected and reconnecting status copy;
- retryable failure;
- ended state;
- presenter-only two-step **End presentation** confirmation;
- no end action for audience role.

Use the real `QRCode` component but assert its wrapper's accessible label and `data-qr-value`, not SVG internals.

- [x] **Step 3: Run panel tests and confirm RED**

Run: `pnpm --dir web --filter @lda/console test -- src/presentation/sync/PresentationPairingPanel.test.tsx`

Expected: FAIL because the panel does not exist.

- [x] **Step 4: Implement the compact panel**

Use a single component API:

```ts
type PresentationPairingPanelProps = {
  readonly role: PresentationRole;
  readonly controller: PresentationSyncController;
};
```

The expanded panel must use ordinary form semantics, uppercase the visible code, show `react-qr-code` only after creation, and use `navigator.clipboard.writeText` behind a small copy action with an in-DOM status message. Do not make pairing a full-screen modal. Keep the collapsed connected surface readable on a phone and non-dominant on the audience deck.

The join URL is:

```ts
const oppositePath = role === "presenter" ? "/present" : "/presenter";
const joinUrl = `${window.location.origin}${oppositePath}?pair=${state.code}`;
```

- [x] **Step 5: Add restrained styling**

Create `presentation-sync.css` with the existing editorial token vocabulary. Use one compact bordered surface, a two-column QR/details layout when expanded, and a single-column layout below 640 px. Do not introduce gradients, oversized pills, or a second theme.

- [x] **Step 6: Verify panel behavior**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/sync/PresentationPairingPanel.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: tests and typecheck pass.

- [x] **Step 7: Commit the pairing surface**

```powershell
git add web/apps/console/package.json web/apps/console/src/presentation/sync web/pnpm-lock.yaml
git commit -m "feat: add presentation pairing panel"
```

---

### Task 6: Synchronize `/present`

**Files:**

- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/PresentationFooter.tsx`
- Modify: `web/apps/console/src/presentation/PresentationFooter.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Consumes `usePresentationSync` and `PresentationPairingPanel`.
- Publishes the audience route's existing `hashForLocation(state.location)` and applies remote hashes through the existing `jump_hash` reducer path.

- [x] **Step 1: Write failing route integration tests**

Mock only the sync transport, not the presentation reducer. Test:

- panel is visible on `/present`;
- local ArrowRight changes the hash and publishes once;
- direct hash and figure focus changes publish the complete focus path;
- a remote discussion hash enters the existing discussion panel;
- a remote hash is not echoed;
- server failure leaves Space/arrow navigation working.

- [x] **Step 2: Run audience integration tests and confirm RED**

Run: `pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx`

Expected: new pairing and synchronization assertions fail.

- [x] **Step 3: Mount the shared controller**

In `PresentationRoute`, compute:

```ts
const canonicalHash = hashForLocation(state.location);
const presentationSync = usePresentationSync({
  role: "audience",
  currentHash: canonicalHash,
  applyRemoteHash: (hash) => dispatch({ type: "jump_hash", hash }),
});
```

Do not replace the existing hashchange listener, keyboard listener, reducer, or `history.replaceState` effect. Thread the controller through `PresentationStage` to `PresentationFooter` and render `PresentationPairingPanel` in the footer's non-demo utility area. It must not displace the live workflow demo rail.

- [x] **Step 4: Verify the audience route**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx src/presentation/PresentationFooter.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: focused tests pass.

- [x] **Step 5: Commit audience synchronization**

```powershell
git add web/apps/console/src/presentation
git commit -m "feat: synchronize audience presentation route"
```

---

### Task 7: Synchronize `/presenter` And End Sessions

**Files:**

- Modify: `web/apps/console/src/presentation/presenter/PresenterRoute.tsx`
- Modify: `web/apps/console/src/presentation/presenter/PresenterRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/presenter/PresenterShell.tsx`
- Modify: `web/apps/console/src/presentation/presenter/PresenterShell.test.tsx`
- Modify: `web/apps/console/src/presentation/presenter/PresenterNavigationBar.tsx`
- Modify: `web/apps/console/src/presentation/presenter/presenter.css`

**Interfaces:**

- Consumes the same controller and panel as Task 6 with role `presenter`.
- Publishes `presenterHashForNote`/current canonical hash changes and applies remote hashes by assigning `window.location.hash`, allowing the existing presenter navigation parser to update notes and Q&A.

- [x] **Step 1: Write failing presenter integration tests**

Test:

- the pairing panel appears in the stable presenter navigation area;
- Previous, Next, arrow keys, swipe callbacks, sidebar links, and Q&A links publish canonical hashes;
- audience-originated hashes update the visible presenter note;
- a remote Q&A hash opens the correct Q&A content;
- remote application does not publish a feedback message;
- presenter end confirmation calls `session.end` and displays ended state;
- local navigation still works after socket failure.

- [x] **Step 2: Run presenter tests and confirm RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/presenter/PresenterRoute.test.tsx src/presentation/presenter/PresenterShell.test.tsx
```

Expected: new synchronization assertions fail.

- [x] **Step 3: Mount the shared controller and panel**

Use the URL as the source for the current hash because rapid swipe/key events already resolve from it:

```ts
const presentationSync = usePresentationSync({
  role: "presenter",
  currentHash: window.location.hash || "#scene/thesis/title",
  applyRemoteHash: (hash) => {
    if (window.location.hash !== hash) window.location.hash = hash;
  },
});
```

Render the panel beside the stable Previous/Next controls, not inside scrolling speaker-note content. Preserve the current mobile swipe target exclusions and auto-scroll behavior.

- [x] **Step 4: Verify presenter behavior**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/presenter
pnpm --dir web --filter @lda/console typecheck
```

Expected: presenter tests and typecheck pass.

- [x] **Step 5: Commit presenter synchronization**

```powershell
git add web/apps/console/src/presentation/presenter
git commit -m "feat: synchronize presenter controls"
```

---

### Task 8: Two-Context Browser Verification And LAN Runbook

**Files:**

- Create: `web/apps/console/e2e/presentation-sync.spec.ts`
- Modify: `web/apps/console/package.json`
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/project_map.md`
- Move: `docs/superpowers/plans/2026-07-14-lan-presentation-sync.md` to `docs/historical/superpowers/plans/2026-07-14-lan-presentation-sync.md`

**Interfaces:**

- Verifies the complete server/browser contract without introducing production APIs.
- Documents the exact LAN launch, pairing, recovery, and security boundary.

- [x] **Step 1: Add a browser test script using the repository's existing Playwright CLI dependency strategy**

Add a `test:presentation-sync:e2e` script that starts from a built console and Hono server. Do not add a second permanent browser-test framework if Playwright is already available through the local tooling; otherwise add `@playwright/test` as a console dev dependency and commit the lockfile.

- [x] **Step 2: Write the two-context browser test**

The test must:

1. open `/presenter#scene/thesis/title` in a phone-sized context;
2. create a room and read the code;
3. open `/present?pair=CODE#scene/thesis/title` in a 1280x720 context;
4. press Next on the phone and assert both hashes match;
5. press ArrowLeft on the audience page and assert both hashes match;
6. navigate the audience page to an architecture focus hash and assert the phone follows;
7. reload the phone and assert it receives the latest server snapshot;
8. end from the phone and assert both panels show ended state;
9. repeat creation from `/present` and joining from `/presenter` to verify symmetry.

- [x] **Step 3: Run the complete verification matrix**

Run:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
pnpm --dir web --filter @lda/console test:presentation-sync:e2e
git diff --check
```

Expected: all unit/integration tests, typechecks, build, browser test, and whitespace check pass. The existing Vite chunk warning is acceptable; new runtime errors or open handles are not.

- [x] **Step 4: Perform manual LAN smoke on two devices or two browser contexts**

Run:

```powershell
pnpm --dir web build
$env:WEB_HOST = "0.0.0.0"
pnpm --dir web start
```

Open `http://<laptop-lan-ip>:8787/presenter` and `http://<laptop-lan-ip>:8787/present`. Verify code entry, QR target, navigation in both directions, reconnect after reload, and presenter termination. Confirm the workflow RPC server remains loopback-only and browser workflow operations still pass through Hono.

- [x] **Step 5: Update live documentation**

In `web/README.md`, document:

- build/start commands;
- `WEB_HOST=0.0.0.0` and port 8787;
- symmetric Start/Join behavior;
- QR/code/link pairing;
- reconnect and server-snapshot-wins behavior;
- presenter termination;
- trusted-LAN-only boundary; and
- the fact that `8765` may remain loopback-only behind Hono.

Mark the roadmap item completed and link the historical implementation plan. Keep the approved design spec live because it remains the current behavior contract.

Add `@lda/presentation-sync` to `docs/project_map.md` as the shared bounded wire-contract package used by the browser console and `@lda/web-server`. State explicitly that room lifecycle remains in the web server and navigation semantics remain in the console.

- [x] **Step 6: Run independent review and fix valid findings**

Use the `requesting-code-review` skill. Review along both Standards and Spec axes. Re-run focused tests for every corrected finding, then re-run typecheck and `git diff --check`.

- [x] **Step 7: Archive the completed plan and commit**

```powershell
git mv docs/superpowers/plans/2026-07-14-lan-presentation-sync.md docs/historical/superpowers/plans/2026-07-14-lan-presentation-sync.md
git add web/README.md web/apps/console/e2e web/apps/console/package.json web/pnpm-lock.yaml docs/current_roadmap.md docs/project_map.md docs/historical/superpowers/plans/2026-07-14-lan-presentation-sync.md
git commit -m "docs: complete LAN presentation sync"
```

## Final Acceptance Checklist

- [x] Starting from either route produces a code, QR, and opposite-route link.
- [x] Joining receives the latest canonical hash and revision immediately.
- [x] Phone presenter controls move the audience deck.
- [x] Audience keyboard, mouse, direct hash, discussion, and figure focus navigation update presenter notes.
- [x] A remote hash is never echoed as a second revision.
- [x] Concurrent same-revision updates converge to the first accepted snapshot.
- [x] Reconnect applies the server snapshot and does not overwrite it with offline local navigation.
- [x] The room survives a temporary disconnect, then expires at the documented bounds.
- [x] Only presenter-role clients can end the session.
- [x] Pairing failure never disables standalone navigation.
- [x] No storyboard data or workflow operations enter the room service.
- [x] No TLS or public-internet security claim appears in UI or docs.
- [x] Full tests, typecheck, build, two-context browser smoke, and `git diff --check` pass.
