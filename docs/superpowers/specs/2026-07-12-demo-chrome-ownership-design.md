# Presentation Demo Chrome Ownership

## Status

Approved design direction for the next presentation slice.

## Problem

The presentation currently renders the live-target truth badge in the footer of
every main scene. It also renders launch controls inside the Scene 10 operation
content. The target-health model mixes service availability with replay/live
playback, so a healthy live service can appear as `Replay evidence` while a
direct replay route is being primed. These independent state changes produce
stale labels, layout shifts, and visible flicker when the presenter backtracks.

The input file browser has a separate honesty problem: it displays `selected /
read`, but the rows are not interactive and the recording only contains input
paths, not file contents or a read operation.

## Goals

1. Show live-target truth only where the prepared workflow demo is active.
2. Move prepared-run and retry actions into the persistent presentation footer.
3. Make footer content derive from the current scene and beat, so backtracking
   cannot retain a previous beat's status or copy.
4. Separate target health from demo playback mode.
5. Keep the footer slot geometrically stable while target health is checking or
   the run changes phase.
6. Make the prepared-run control available throughout the demo arc without
   repeating large buttons inside individual scenes.
7. Replace unsupported file claims with factual input-manifest language.

## Non-goals

- Do not implement file selection, file reading, or file-content preview in this
  slice. Those require content-backed fixtures or a source-read operation.
- Do not change the workflow graph, trace facts, approval form, or live RPC
  protocol.
- Do not make the presentation footer a second application navigation system.

## Demo scope

The demo control rail is visible only for the prepared workflow arc:

- Scene 8: `agent-handoff`
- Scene 9: `prepared-lifecycle`
- Scene 10: `run-from-deployment`
- Scene 11: `typed-human-boundary`
- Scene 12: `resume-output-evidence`

Scene 8 (`agent-handoff`) remains a scripted conversation, but gains the same
small footer control rail so the presenter can start the prepared run without
adding another large button to the chat composition. All narrative,
architecture, evaluation, conclusion, and discussion locations hide the target
badge and demo actions.

## State model

The presentation uses two independent concepts:

### Target health

`PresentationTargetHealth` describes the external service:

- `checking`: the configured target is being probed
- `ready`: the target responded successfully and no run is active
- `active`: a live run is in progress
- `failed`: the target is unavailable and replay is the fallback
- `replay`: no live target is configured

When the target is healthy, the status remains `ready` even if the current
timeline is showing a reviewed replay. `Replay evidence` is not a substitute
for `Live target ready`; playback mode is separate state.

### Playback mode

The demo timeline continues to own whether the current walkthrough is `live` or
`replay`. This value controls action labels and execution behavior, not the
target-health badge.

## Footer composition

`PresentationFooter` owns one stable demo slot between scene progress and the
evidence receipt. The slot is reserved for every Scene 8–12 location and is
empty elsewhere.

For non-demo scenes, the slot is absent and no target-health copy is rendered.
For the demo arc, the slot is always present with a stable minimum width and
height. It shows exactly one of these states:

- Before execution: a compact primary action, `Run prepared workflow` when the
  live target is healthy or `Play replay walkthrough` when it is unavailable.
- While checking: a compact `Checking live service` state with the same
  footprint.
- While running: a non-interactive `Running workflow...` information label,
  not a disabled button.
- While paused at the typed boundary: `Run paused - review required`.
- After completion: `Run complete`.
- When retry is meaningful: a compact secondary `Retry live service` action may
  sit beside the primary action without changing the slot's size.

The large `DemoRunLaunchControl` section is removed from scene content layouts.
Its behavior is preserved through this footer rail. There is only one actual
prepared-run action; chat remains explanatory and does not gain a duplicate
run button.

## Input manifest language

Until source content is available, each input row says `included in prepared
run`. The row is not a button and does not claim that the presenter can open or
read the file. The output destination remains a factual manifest field.

A later slice may introduce a `RunInputFilePreview` backed by bundled fixture
content or a real source-read operation. That slice must add an actual click
target, preview content, and tests for the read path rather than relabeling the
current static rows.

## Verification contract

The implementation must test:

- title and non-demo scenes render no target badge or demo controls;
- every Scene 8–12 beat renders exactly one compact demo rail;
- the pre-run demo rail renders the run action without an in-scene launch panel;
- a running demo renders an information label instead of a disabled run button;
- a paused demo renders the review-required information label;
- a completed demo renders the terminal information label;
- a healthy target remains `Live target ready` while the timeline is replaying;
- failed health renders replay fallback only inside demo scope;
- backtracking between Scene 8–12 updates the rail from current state without
  retaining stale copy;
- backtracking from the demo arc to title removes the rail immediately;
- checking does not change footer dimensions or mount a stale replay label;
- input rows use `included in prepared run` and expose no unsupported button or
  preview affordance.

## Deferred follow-up

Build a real input-file preview surface with content-backed fixtures or a
source-read RPC. Keep it separate from this chrome ownership slice so target
truth and file-content evidence do not become another mixed state machine.
