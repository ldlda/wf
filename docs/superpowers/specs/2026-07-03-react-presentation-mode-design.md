# React Presentation Mode Design

## Status

Current design contract for the next Workflow Console slice.

## Related Decisions

- [React presentation mode before Astro](../../adr/0003-react-presentation-mode-before-astro.md)
- [Workflow console, agent demo, and defense presentation](2026-07-01-workflow-console-agent-demo.md)
- [Demo autoplay and replay](2026-07-03-demo-autoplay-replay.md)

## Purpose

The console can now run and replay the prepared `lda_report_workflow`, but the
screen still reads as a debug console. The defense needs a route that can explain
the product quickly, survive 720p projection, and answer questions without
forcing the viewer through raw JSON.

This slice adds a React presentation mode inside `web/apps/console`. It is not a
separate slide framework. It is a staged compositor over real React components:
chat, workflow graph, operation evidence, typed interrupt approval, report
output, trace, and captions can enter, leave, or take focus as scripted beats
advance.

The first implementation is not expected to be the final defense script. It
should establish the presentation infrastructure and use a provisional script
that can be revised cheaply. The target editing experience is that adding or
changing a beat is a small semantic change, not a rewrite of a large TSX file.
For example, selecting a workflow node and showing its `NodeUse` detail should
be expressed as a short beat/state edit, with the reusable graph and spotlight
components handling the rest.

## Product Boundary

The normal console remains the real product surface: dense, inspectable,
operator-facing, and evidence-first.

Presentation mode is a defense-stage surface over the same data and controller.
It may use replay by default, but it must not pretend a live LLM is making
planning decisions. The chat persona is scripted/replayed operator interaction
unless a later constrained macro explicitly runs.

Terminology:

- **Console:** ordinary workflow product UI.
- **Presentation mode:** cinematic staged route inside the React app.
- **Beat:** one named presentation moment.
- **Scene component:** a React component that renders one visible part of the
  stage.
- **Operation block:** a visible product call with raw and interpreted output.
- **Presentation agent:** scripted/replayed operator persona.
- **Constrained demo agent:** optional future macro client.
- **External LLM agent:** out of scope for the defense UI.

## Route

Add a dedicated route inside the console app:

```text
/present
```

The existing console page remains available separately. The exact console route
may be `/console` or the current root route, but presentation mode must not be a
mode toggle that permanently compromises the console layout.

Hash fragments select scripted beats:

```text
/present#intro
/present#graph-reveal
/present#interrupt-approval
/present#trace-evidence
```

Hash navigation is preferred over query parameters because it is easy to copy
during rehearsal, has no server-routing implications, and can survive a future
static shell.

## Interaction Model

Presentation mode is a hybrid of scripted beats and manual inspection.

Primary controls:

- `Space` / `ArrowRight`: next beat.
- `ArrowLeft`: previous scripted beat.
- `Esc`: close the current overlay or evidence drawer.
- Mouse/touch: inspect node, open evidence, submit approval, or jump timeline.

Backward navigation only rewinds visual/script state. It must not undo live
workflow mutations. If the current run was live, going backward replays the
stored stage state for explanation, not runtime rollback.

Replay mode is the default. Live mode is available but explicit.

## Stage Model

Avoid building a generic layout engine. Beats should be semantic state, and
components should decide their own motion and layout.

Acceptable state shape:

```ts
type BeatId =
  | "intro"
  | "chat-request"
  | "tool-call-start"
  | "graph-reveal"
  | "interrupt-approval"
  | "resume-output"
  | "trace-evidence"
  | "boundary-wrap";

type PresentationState = {
  readonly beat: BeatId;
  readonly selectedNodeId: string | null;
  readonly chatMode: "full" | "rail" | "hidden";
  readonly evidenceMode: "hidden" | "peek" | "open";
  readonly playbackMode: "replay" | "live";
};
```

Do not store React components or large layer configuration objects inside beat
data. The route rerenders normal React components from semantic state. CSS and
motion handle the choreography.

## Components

Keep the TSX files lean. Presentation behavior should be split into focused
components:

```text
presentation/
  PresentationRoute
  PresentationStage
  BeatController
  BeatRail
  StageCaption
  OperatorChat
  ChatMessage
  OperationBlock
  WorkflowGraphStage
  NodeSpotlight
  ApprovalScene
  ReportOutputScene
  TraceEvidenceScene
  EvidenceDrawer
```

The first implementation does not need every component above, but the route
should not become a single large TSX file.

Component extraction from the existing console/demo UI is in scope for the first
slice when it prevents duplicate graph, timeline, operation evidence, output, or
trace rendering. This is maintenance reduction, not optional polish: presentation
mode and console mode should share the useful product components while keeping
their layout/composition separate.

## Beat Outline

The first script should stay under eight beats:

1. **Intro:** claim frame: planner decisions are separated from deterministic
   runtime execution.
2. **Chat request:** operator asks for the thesis readiness report.
3. **Tool call start:** `lda.chat` runs the prepared workflow operation.
4. **Graph reveal:** workflow graph becomes primary; chat moves to a rail.
5. **Interrupt approval:** typed `issue_review` appears as an explicit human
   boundary.
6. **Resume output:** selected issue and markdown report are produced.
7. **Trace evidence:** trace and raw/interpreted evidence show inspectability.
8. **Boundary wrap:** clarify substrate versus autonomous agent claims.

Each beat should have one short caption. Avoid prose blocks. In Q&A, the
operator should be able to jump directly to graph, interrupt, trace, or evidence
beats.

## Operation Block

Operation calls are first-class presentation elements. They bridge chat and the
workflow substrate.

An operation block shows:

- equivalent CLI or JSON-RPC method;
- compact raw request/response;
- interpreted result;
- affected workflow/run ids;
- status and duration when available.

Example presentation:

```text
$ uv run wf run start lda_report_case_study.default --input-file run-input.json

raw:
{ "status": "interrupted", "interrupt": { "kind": "issue_review" } }

interpreted:
Human approval required
1 proposed issue
Resume outcomes: submitted | cancelled
```

The block can appear compact inside chat and expand into a terminal-like panel.
The interpreted side may highlight graph nodes or stage elements. Raw evidence
remains available through the global evidence drawer.

## Graph

Use a curated presentation graph backed by real workflow/run evidence.

The presentation graph may use clearer labels and positions than the raw plan,
but it must not invent steps that do not exist. Each visible node should be able
to point to one of:

- a workflow node id;
- a run trace frame;
- an operation block;
- a captured replay event.

Clicking a node can open `NodeSpotlight`, which shows the node purpose,
input/output summary, and related evidence.

## Motion

Motion should make state changes understandable:

- chat can enter full-screen, then scoot into a rail;
- graph can bloom into the main stage;
- a clicked node can expand into a detail panel;
- evidence can peek from the side, then open;
- beat rail progress can advance subtly.

No slow typewriter effect. Chat messages appear as complete messages with a
small fade or stagger. This resembles modern AI app streaming enough without
wasting defense time or implying a live model.

Every motion path needs a reduced-motion fallback.

## Visual Stack

Use React first. Add routing and motion before adopting a large component
library.

Tailwind-style utilities and copy-owned components such as shadcn/ui are
acceptable if they help speed up consistent layout. Avoid adopting a full chat or
agent framework until runtime agent behavior exists. Templates may be copied as
raw material, but the visual result should fit the lda.chat stage, not a generic
SaaS/chat clone.

## 720p Constraint

Design for `1280x720` as a first-class target.

Rules:

- one primary object per beat;
- one secondary detail at most;
- captions must be short;
- raw evidence is collapsed by default;
- long code/output wraps inside panels;
- the presenter must not need browser zoom during the main path.

## Testing

Unit tests should cover:

- beat reducer/state transitions;
- hash-to-beat and beat-to-hash behavior;
- keyboard controls;
- replay-default startup;
- backward navigation does not call live mutation operations;
- operation block rendering for CLI/raw/interpreted output.

Browser smoke should cover:

1. load `/present`;
2. verify replay is the default;
3. advance through all beats with keyboard;
4. open node spotlight;
5. open evidence drawer;
6. jump to `#interrupt-approval`;
7. complete the replay path on a `1280x720` viewport;
8. verify the normal console route still works.

## Success Criteria

The slice is complete when:

1. `/present` can run the prepared replay story without an RPC server;
2. the same route can optionally use live mode when connected;
3. keyboard controls can drive the main defense path;
4. hash links jump to important beats;
5. operation blocks make product calls visible and interpretable;
6. graph, interrupt, output, trace, and evidence are available without clutter;
7. the route is readable at `1280x720`;
8. the normal console remains product-like and is not forced into cinematic
   layout choices.
