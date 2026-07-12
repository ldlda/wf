# Presentation Live/Replay Activation Design

**Status:** Proposed

## Goal

Make the prepared workflow demo's live/replay boundary explicit and usable. A
presenter must be able to see the live-run action, start the real workflow
through the existing browser-to-console-to-RPC path, and fall back to the
reviewed recording only through an explicit replay action or an unavailable
service.

This slice does not change the Scene 1/2 story, fact-check storyboard content,
Scene 8/9 authoring recording, chat framework, or visual theme system.

## Current Problem

The live timeline controller and RPC executor already exist, but the visible
action is owned by `OperatorChat`. Scenes 10–12 currently hide that chat, so a
prepared run can be implemented without a visible way to start it. Direct
Scene 10–12 hashes also prime replay state by design, while the target health
status is only probed on mount. This makes the system look disconnected even
when `wf-rpc-server` is running.

## Design

### Launch surface

Expose a compact prepared-run control on Scene 10's `operation` beat. It is a
scene-owned control, not a reintroduced chat rail. It must remain visible while
the target is checking, ready, failed, or the live run is active.

The control communicates the current action:

| Target/timeline state | Visible action |
| --- | --- |
| Checking | `Checking live service` and a retry action when the check settles |
| Healthy, not started | `Run prepared workflow` |
| Live run active | Current operation/`Running live workflow`; duplicate start disabled |
| Health failed | `Play replay walkthrough` plus the failure reason |
| Replay active | `Replay walkthrough active` |

Only an explicit launch action changes the timeline from ready to running. A
direct deep link remains replay-backed when it has no active run context.

### Target status and retry

Reuse `resolvePresentationTarget()` and `usePresentationTargetStatus()`. Add a
retry mechanism at the presentation boundary rather than duplicating target
configuration or connection logic. Retrying must re-run `workflow.health`
against the same resolved target and update the visible status without a full
page reload.

The two local servers remain separate and documented:

```text
browser :5173 -> console server :8787 -> wf-rpc-server :8765/rpc
```

The browser never calls `wf-rpc-server` directly; all operation evidence still
comes from the existing `/api/rpc` proxy.

### Live execution

The launch action calls the existing `DemoTimelineController.start("live")`.
The existing live executor remains the source of truth for:

1. deployment inspection;
2. run start and typed interrupt payload;
3. submitted or revision-requested resume;
4. final trace read.

After the first live operation succeeds, the timeline must not be replaced by
canonical replay data. A live failure is shown as a failed live event with its
operation and error; it may offer an explicit `Play replay walkthrough` action,
but fallback must not happen silently.

### Scope of truth indicators

The live/replay status and live launch control belong to the prepared demo
surface. Non-demo narrative, architecture, evaluation, conclusion, and
discussion views should not gain a persistent live-service badge or run action.

## Acceptance Criteria

1. With `wf-rpc-server` and the web server running, Scene 10's operation beat
   visibly exposes `Run prepared workflow` and starts a live timeline.
2. A live run records deployment inspection, run start, interrupt, resume, and
   trace evidence using the existing `callOperation` path.
3. The typed approval form remains the only way to provide the resume decision;
   both submitted and revision-requested outcomes are sent to the live server.
4. A direct Scene 10–12 hash without an active run still shows the reviewed
   replay, not a fabricated live state.
5. When health fails, the presenter sees the reason and an explicit replay
   action; no live operation is silently represented as replay evidence.
6. Starting the live server after the presentation is already open can be
   recovered with retry, without reloading the page or reconnecting manually.
7. The launch control cannot issue duplicate starts while an operation is in
   flight or a live run is already active.
8. Scene 8 and Scene 9 remain deterministic authoring replay and do not call
   workflow authoring RPC operations.

## Verification

Unit and component tests must cover target retry/status transitions, launch
visibility, duplicate-start protection, explicit replay fallback, and live
versus replay operation calls. A browser smoke run must verify:

```text
Scene 10 operation -> live start -> interrupt -> approval -> resume -> trace
Scene 10 direct hash with server unavailable -> explicit replay
server started after page load -> retry -> live-ready action
```

The final verification must include the existing scoped console tests,
typecheck, build, and `git diff --check`. The unrelated user edit in
`web/apps/console/src/presentation/authoring/Scene8ChatEntry.tsx` must remain
unstaged.
