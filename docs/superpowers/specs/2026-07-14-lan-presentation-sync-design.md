# LAN Presentation Synchronization Design

## Status

Approved for implementation planning on 2026-07-14.

## Purpose

The audience deck at `/present` and the presenter reader at `/presenter` can
currently navigate the same storyboard, but they do so independently. During a
defense, the presenter reader should run on a phone and control the audience
deck on a laptop. Navigation performed directly on the laptop must also update
the phone.

This design adds an ephemeral, bidirectional synchronization channel through
`@lda/web-server`. The first version is for a trusted local network. It does not
implement TLS or claim secure public-internet operation.

## Existing Controls

The audience route currently supports:

- `Space` or `ArrowRight` for the next beat;
- `ArrowLeft` for the previous beat;
- `Escape` for the top overlay;
- direct hash navigation, discussion branches, and figure focus paths; and
- local mouse interaction with figures, evidence, forms, and questions.

The presenter route currently supports Previous and Next links, arrow keys,
mobile swipe gestures, sidebar navigation, Q&A navigation, and direct hashes.

Synchronization must reuse these controls and the existing canonical hashes.
It must not create a second storyboard or navigation implementation.

## Goals

- Pair `/present` and `/presenter` from either route.
- Allow either client to change the shared presentation location.
- Reflect laptop navigation on the phone and phone navigation on the laptop.
- Preserve standalone behavior before pairing and after disconnection.
- Support reconnection to a short-lived in-memory session.
- Expose an explicit session termination action from `/presenter`.
- Keep the protocol small enough to test as a state machine.

## Non-Goals

- Public-internet deployment, TLS termination, or production authentication.
- Remote workflow execution, approval submission, evidence controls, or notes
  editing.
- Persisting sessions across server restarts.
- Synchronizing scroll position, open disclosure widgets, timers, or local form
  drafts.
- Replacing hashes with server-owned slide identifiers.

## Pairing Experience

Both routes use the same compact **Pair presentation** panel.

### Start A Session

Pressing **Start session** creates an in-memory room initialized from the
creator's current canonical hash. The panel displays:

- a short, case-insensitive join code;
- a QR code;
- a copyable join URL; and
- a waiting or connected status.

If the creator is on `/present`, the generated link opens `/presenter`. If the
creator is on `/presenter`, it opens `/present`. This makes pairing symmetric
without requiring the phone to be the permanent transport host.

### Join A Session

Either route can enter the short code in the same panel. A QR or URL carries
the same code and skips manual entry. After joining, the new client immediately
receives the latest accepted location and revision.

The expanded pairing panel then collapses into a small status surface showing
the connection state and peer presence. `/presenter` additionally exposes an
**End presentation** action behind a confirmation step. Any connected presenter
client may end the trusted-LAN session. Closing one browser only disconnects
that client and does not immediately terminate the room.

## Authority And Data Flow

The server is authoritative only for the latest accepted synchronization
snapshot. The clients remain authoritative for navigation semantics.

1. A local control computes its next location using the existing route logic.
2. The client updates its local route and publishes the canonical hash with its
   current base revision.
3. The server accepts one update for that revision, increments the revision,
   and broadcasts the resulting snapshot.
4. Peers apply the snapshot through their existing hash/reducer path.
5. Applying a remote snapshot does not republish the same change.

The synchronized value is the complete canonical hash, including scene, beat,
discussion branch, and optional figure focus path. This lets laptop-only
interactions update the phone without adding dedicated protocol messages for
each interaction.

When two clients publish from the same base revision, the first accepted update
wins. The stale client receives the current snapshot and converges instead of
overwriting newer state.

## Server Module

Add a focused `presentation-sync` module to `@lda/web-server`. Its public
boundary owns:

- room creation and code lookup;
- join-token validation;
- WebSocket membership;
- the current hash and monotonic revision;
- presenter and audience presence;
- explicit termination; and
- inactivity cleanup.

The room store is in memory. A room remains reconnectable for ten minutes after
all clients disconnect and expires after two hours without activity. A server
restart ends every room.

The module must not import console storyboard data. It validates message shape,
hash length, allowed hash prefixes, revision ordering, and payload bounds only.

## Protocol

Session setup uses ordinary JSON HTTP endpoints. Live synchronization uses one
WebSocket per client.

Client messages:

- `location.publish`: canonical hash, base revision, and client message ID;
- `session.end`: presenter-requested termination; and
- `ping`: bounded liveness signal when needed by the runtime.

Server messages:

- `location.snapshot`: accepted hash, revision, and originating message ID;
- `presence.snapshot`: connected presenter and audience counts;
- `location.rejected`: stale revision plus the current snapshot;
- `session.ended`: explicit or expired termination; and
- `protocol.error`: bounded, user-safe error information.

Every message is schema-decoded before use. Unknown message variants and
oversized payloads close or reject the offending connection without affecting
the room.

## Client Integration

A source-owned presentation synchronization controller is shared by `/present`
and `/presenter`. It exposes a small state model:

- standalone;
- creating;
- waiting;
- joining;
- connected;
- reconnecting;
- failed; and
- ended.

The controller owns HTTP setup, WebSocket lifecycle, revision tracking,
remote-application suppression, and presence. Route components provide the
current canonical hash and a callback that applies a remote hash. Pairing UI
does not know storyboard semantics.

Local navigation remains usable while disconnected. On reconnection, the
server snapshot wins. The UI must state this clearly rather than silently
merging divergent histories.

## LAN Operation

For rehearsal, build the console and expose the Hono server on the laptop's LAN
interface:

```powershell
pnpm --dir web build
$env:WEB_HOST = "0.0.0.0"
pnpm --dir web start
```

Both devices then use `http://<laptop-lan-ip>:8787`. The existing workflow RPC
server may remain loopback-only because browser workflow calls continue through
the Hono proxy running on the laptop.

The join code is protection against accidental room crossover, not
authentication against hostile network users. Internet exposure is deferred to
infrastructure such as a trusted tunnel or reverse proxy and is not part of
this implementation.

## Failure Behavior

- An invalid or expired code leaves the client standalone and shows a compact
  retryable error.
- A dropped WebSocket enters reconnecting state with bounded backoff.
- The room survives a temporary client disconnect.
- A stale location publish is rejected and replaced by the latest snapshot.
- Explicit termination moves every client to ended state and stops automatic
  reconnection.
- Server restart or room expiry requires a new pairing session.
- Local navigation never depends on synchronization availability.

## Testing

### Pure State Tests

- room creation, code uniqueness, and initial location;
- monotonic revision acceptance and stale-update rejection;
- presence accounting, disconnect grace, expiry, and termination; and
- bounded protocol decoding.

### Server Tests

- create and join endpoint success and failure;
- two WebSocket clients receiving the initial snapshot;
- presenter-to-audience and audience-to-presenter location propagation;
- stale publish convergence;
- reconnect snapshot recovery; and
- presenter termination broadcasting to all clients.

### Console Tests

- uniform pairing panel on both routes;
- code, QR target, URL, waiting, connected, reconnecting, and ended states;
- local hash changes publishing once;
- remote hashes applying without feedback loops;
- presenter controls updating the audience route;
- audience keyboard/hash changes updating presenter notes; and
- standalone navigation when the server is unavailable.

### Browser Smoke

Use two browser contexts against the LAN-style server:

1. Create on `/presenter`, join `/present`, and navigate in both directions.
2. Create on `/present`, join `/presenter`, and repeat the same checks.
3. Reload one client and verify it receives the latest snapshot.
4. End from `/presenter` and verify both clients leave synchronized mode.

## Success Criteria

- A phone running `/presenter` can move the audience deck backward and forward.
- Laptop navigation updates the phone to the same scene and beat.
- Pairing can begin from either route using code, QR, or URL.
- Both clients converge after reconnecting or racing one update.
- Ending from `/presenter` terminates the shared room.
- Losing synchronization never breaks local presentation navigation.
