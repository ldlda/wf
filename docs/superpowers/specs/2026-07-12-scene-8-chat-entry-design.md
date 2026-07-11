# Scene 8 Chat Entry Design

## Status

Approved design for the first slice of the Scene 8–14 defense recomposition.

## Goal

Turn Scene 8 into a convincing full-screen assistant entry surface: the
audience sees the presentation title, a familiar empty chat state, and a
composer containing the report-workflow request. Sending that request reveals
the first prepared authoring turn without starting the workflow run.

## Context

Scene 8 currently renders a prepared authoring transcript inside a custom stage
layout with a phase rail and a separate `Run prepared workflow` button. That
mixes two different stories:

- authoring begins as an external-agent conversation;
- workflow execution begins later in the Run From Deployment scene.

The revised scene must make that distinction visible. The chat entry is a
presentation interaction backed by the deterministic authoring recording. It is
not an LLM call and it is not the live workflow start operation.

## Design

### Scene Composition

Scene 8 retains the existing `StageCaption` title and caption. Below it, the
primary region becomes one full-height chat surface:

```text
Stage title and framing
            |
    assistant-style thread
    welcome / turns / tools
            |
       composer + Send
```

The old five-step phase rail is removed from Scene 8. The lifecycle sequence is
shown by Scene 9, where the authoring canvas is the primary artifact and the
conversation becomes a secondary modal.

The standalone `Run prepared workflow` action is removed from Scene 8. The
workflow-run action belongs to Slice 3 and will be exposed in Scene 10.

### Chat Surface Boundary

Use the assistant-ui Thread/Composer template and shadcn-owned primitives for
the visual vocabulary: message spacing, composer shell, send affordance,
empty-state layout, focus treatment, and tool-group treatment.

Do not introduce an assistant-ui runtime in this slice. The presentation keeps
`AgentMessage`, `projectPreparedAuthoringThread`, and the existing deterministic
recording as the source of truth. The Scene 8 adapter owns only the local
entry-state transition and delegates the rendered turns to the existing
projection path.

This boundary is deliberate:

- it avoids a second chat state store;
- it avoids reintroducing the duplicate-message/runtime problem previously
  found with an external assistant runtime;
- it keeps replay deterministic and inspectable;
- it leaves a future live AI SDK driver compatible with the same visual shell.

### Entry State

On the Scene 8 request beat, render:

- the Scene 8 title and caption;
- an assistant-style welcome heading or short framing line;
- an empty conversation viewport;
- a composer with the request text prefilled:
  `We need to author a report workflow for the lda_report scenario. What sources and capabilities are available?`;
- an enabled Send button;
- no workflow operation, run ID, deployment ID, or live target action.

The prefilled text is editable. The scene does not require the presenter to
retype the request during the defense.

### Send Transition

When Send is activated with non-empty text:

1. prevent the native form submission;
2. record the local submitted request in the Scene 8 controller state;
3. replace the empty state with the first prepared authoring conversation turn;
4. reveal the first assistant response and the Discover tool group from the
   canonical recording;
5. clear the composer or replace it with a read-only continuation state;
6. keep the current location at `#scene/agent-handoff/request`.

The send action must not call `workflow.runs.start`, `workflow.runs.resume`, or
any other workflow RPC. It is a scripted presentation entry event.

If the presenter advances with `ArrowRight`, the existing storyboard location
changes to `#scene/agent-handoff/handoff`, and the full prepared authoring
conversation becomes visible through the existing phase projection.

If the composer is empty or contains only whitespace, Send is disabled and no
state transition occurs.

### Replay and Reload Behavior

The Scene 8 entry state is local presentation state. Reloading the request beat
returns to the empty composer. The canonical authoring recording remains the
source for all revealed turns.

Scene 8 must work with no workflow server and must not change the live/replay
target badge. The target badge remains scoped by the later demo truth slice.

### Responsive Behavior

The surface must remain readable at the reviewed `16:9` and `4:3` canvases:

- the composer remains visible without scrolling at `1280x720`;
- the composer remains reachable at `1024x768`;
- the conversation viewport may scroll internally once the prepared turns are
  taller than the available stage;
- long request text wraps inside the composer and never causes horizontal
  overflow;
- the assistant-ui shell must not inherit the old dark-stage palette in Scene
  8's editorial surface;
- reduced-motion users receive an immediate state transition or a short
  opacity-only transition.

## Data Flow

```text
prefilled request
        |
        v
Scene8ChatEntry local reducer
        |
        +--> submitted request / entry state
        |
        +--> projectPreparedAuthoringThread("discover")
                         |
                         v
              assistant-ui visual shell
```

The local state should be a small discriminated union, for example:

```ts
type Scene8EntryState =
  | { readonly phase: "empty"; readonly draft: string }
  | { readonly phase: "submitted"; readonly draft: string; readonly request: string };
```

The exact reducer location may follow the existing presentation module
conventions, but the state must not be added to the global presentation
reducer. Scene 8 entry state is not navigation state and does not need to be
encoded in the URL hash.

## Accessibility

- The composer is a labelled form control with an accessible name such as
  `Message input`.
- Send is a real button and exposes disabled state when the draft is blank.
- Enter submits the request; Shift+Enter inserts a newline if the chosen
  assistant-ui composer supports multiline input.
- The conversation is exposed as a log with a useful accessible label.
- Focus moves to the first revealed assistant content after send without
  stealing focus from the composer while the user is editing.
- Keyboard scene navigation remains owned by the existing presentation route;
  text input events must not advance the scene.

## Failure and Boundary States

- Blank draft: Send disabled; no message is revealed.
- Whitespace-only draft: treated as blank.
- Send while already submitted: disabled or ignored; it must not duplicate the
  prepared conversation.
- Direct navigation to the handoff beat: render the full prepared conversation
  without requiring the request-beat send transition.
- Missing recording data: preserve the existing bounded presentation fallback
  and render an explicit unavailable state rather than inventing a live result.

## Testing Contract

Add or update tests for:

1. request beat renders the title, empty conversation state, prefilled composer,
   and enabled Send button;
2. blank and whitespace-only drafts keep Send disabled;
3. sending reveals the prepared request/assistant/Discover content and does not
   call workflow RPC operations;
4. sending twice does not duplicate the first conversation;
5. direct navigation to the handoff beat still renders the full prepared
   conversation;
6. Scene 8 no longer renders the standalone `Run prepared workflow` button or
   the old phase rail;
7. 1280x720 and 1024x768 browser smoke captures show the composer without
   clipping or horizontal overflow;
8. reduced-motion mode does not hide the submitted conversation.

## Out Of Scope

- Real LLM or AI SDK execution;
- workflow run start or resume;
- Scene 9 assistant modal;
- truth-badge scoping;
- Scene 11 beat compression;
- changes to the overall story order;
- live authoring RPC calls;
- a persistent chat transcript across reloads.

## Acceptance Criteria

The slice is complete when the presenter can open
`#scene/agent-handoff/request`, see a credible full-screen chat entry, press
Send, see the first prepared authoring turn, advance to the handoff beat, and
continue into Scene 9 without a standalone run button or a second chat state
runtime. The behavior is covered by focused tests and 16:9/4:3 browser smoke.
