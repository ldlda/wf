# Presentation Live/Replay Truth Design

## Purpose

The defense presentation can now show a prepared workflow as replay evidence and
can also run against a local `wf-rpc-server`. The UI must make that distinction
obvious. A viewer should never have to infer whether the screen is showing
recorded evidence, a configured live target, or an actually reachable live
server.

## Problem

The presentation currently resolves `http://127.0.0.1:8765/rpc` as a live target
by default, even before a health check. At the same time, direct scene hashes are
replay-backed so the slides are immediately ready. This is technically useful
but semantically blurry:

- The chat says a live workflow target is configured.
- The screen often shows replay evidence.
- The run button can say "Run prepared workflow" even when the visible evidence
  is replayed.
- When the example server is running, the fake/replay path can look real enough
  to be misleading.

## Design Goal

Add a small truth layer that distinguishes:

1. **Replay evidence**: the slide is showing the reviewed recording.
2. **Live target configured**: a URL exists, but reachability has not been
   proven in this presentation session.
3. **Live target reachable**: `workflow.health` succeeded.
4. **Live run active**: the operator clicked the run action and the timeline is
   executing live operations.
5. **Live unavailable**: health check failed or target is invalid; replay is the
   fallback.

This is not a large connection redesign. It is a presentation honesty layer.

## Scope

In scope:

- Health probing the presentation target.
- A visible presentation status badge or strip.
- Clear chat copy for replay vs configured vs reachable vs live active.
- Route tests and component tests for status rendering.
- Browser smoke for reachable local example server and replay fallback.

Out of scope:

- New connection UI.
- Replacing chat with AI Elements.
- Changing `/console` connection behavior.
- Adding remote/VPS presenter companion behavior.
- Full live/replay recording reconciliation.

## UX Rules

- Direct scene hashes remain replay-backed until the operator intentionally
  starts a live run.
- A reachable live server should be shown as "Live target ready", not "Live run
  active".
- "Live run active" only appears after `Run prepared workflow` starts a live
  timeline.
- If health fails, the run button should either use replay wording or explain
  why live is unavailable.
- Replay evidence should be labelled calmly, not apologetically.

Recommended copy:

- Replay: `Replay evidence · reviewed recording`
- Configured: `Live target configured · checking`
- Reachable: `Live target ready · 127.0.0.1:8765`
- Active: `Live run active · operations sent to wf-rpc-server`
- Failed: `Replay fallback · live target unreachable`

## Architecture

Add a small presentation target status hook:

```ts
export type PresentationTargetHealth =
  | { readonly kind: "replay"; readonly label: string; readonly detail: string }
  | { readonly kind: "checking"; readonly target: string; readonly label: string; readonly detail: string }
  | { readonly kind: "ready"; readonly target: string; readonly label: string; readonly detail: string }
  | { readonly kind: "active"; readonly target: string; readonly label: string; readonly detail: string }
  | { readonly kind: "failed"; readonly target: string | null; readonly label: string; readonly detail: string };
```

The hook should not own timeline state. It consumes target resolution and demo
state, then exposes display status and whether live run actions should be
enabled.

Health check should use the existing RPC client/operation layer if one is
already available in the console package. Do not hand-roll a second JSON-RPC
transport unless the existing operation layer cannot call `workflow.health`.

## UI Placement

Add the status to the footer near scene progress/evidence receipt. It should be
visible but quiet: a compact pill or strip. The audience should see it without
it becoming a new hero element.

The chat intro should use the same status language. It should not claim "server
is available" before health succeeds.

## Testing Requirements

Model/hook tests:

- Invalid target produces replay/failed fallback.
- Default target starts as checking, then ready when health succeeds.
- Health failure produces failed fallback.
- Demo state `live` + running/review/completed after live start produces active.

Presentation tests:

- Direct approval hash shows replay evidence status and ready live target status
  separately if health succeeds.
- Chat run label uses live wording only when health is ready.
- If health fails, chat run label uses replay wording.

Smoke:

- With `wf-rpc-server --config examples/lda_report_workflow/wf.config.json
  --host 127.0.0.1 --port 8765`, `/present#scene/interrupt-evidence/approval`
  shows the live target as ready while the slide remains replay-backed.
- With an invalid target in session storage, the same route shows replay
  fallback.

## Success Criteria

- No screen implies a live run is active before the operator starts it.
- The audience can distinguish replay evidence from live server reachability.
- Live target success makes the demo feel credible without hiding replay
  fallback.
- Existing direct-hash readiness remains intact.
