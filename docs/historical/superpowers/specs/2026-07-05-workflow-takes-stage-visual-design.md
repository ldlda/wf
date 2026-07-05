# Workflow Takes the Stage Visual Design

## Status

Approved design for the first cinematic presentation polish slice.

This specification refines Scene 9, "Workflow Takes the Stage," and the shared
presentation surfaces used by Scenes 8 through 10. It does not change the
storyboard, replay protocol, workflow semantics, or evidence records.

## Problem

The presentation compositor is functionally complete, but Scene 9 is the
weakest visual moment in the main path. A `1280x720` review exposed four
problems:

- night-stage text is rendered over light nested surfaces, producing
  unreadable white-on-white content;
- the chat rail renders dark text over a dark panel;
- raw and interpreted JSON receive equal visual weight even though the
  interpreted result is the audience-facing explanation;
- the operation and graph are stacked as unrelated panels instead of showing
  the workflow taking ownership of the stage.

Scene 10 reuses the same operation, chat, and evidence surfaces, so fixing only
one selector would leave the larger transition incoherent.

## Objective

Make Scene 9 the visual standard for the presentation:

1. The audience can read the command, interpreted result, graph, and interrupt
   state from the back of a room at `1280x720`.
2. The composition visibly transfers attention from agent intent to workflow
   execution.
3. Raw protocol evidence remains available without competing with the main
   explanation.
4. Scene 9 flows directly into Scene 10's approval boundary.
5. The same components remain truthful projections of the canonical replay.

## Scope

### In Scope

- the three Scene 9 beats: `operation`, `graph`, and `interrupt`;
- shared night-stage, chat, operation, graph, and evidence presentation
  primitives used by Scenes 8 through 10;
- deterministic Motion choreography between those beats;
- compact audience-facing interpretation of the existing replay event;
- `1280x720`, keyboard, and reduced-motion verification.

### Out of Scope

- rewriting the prepared replay or its evidence;
- adding a live AI SDK driver;
- redesigning all twelve scenes in this slice;
- adopting a general component library for the entire console;
- changing `/console` styling or behavior;
- changing the thesis claims or scene order.

## Visual Direction

Scene 9 is a dark technical stage, not a white admin page placed inside a dark
frame. The center uses one continuous night surface. Cyan marks the current
execution focus, amber is reserved for the typed interrupt, and neutral text
provides hierarchy. Only one semantic accent should dominate a beat.

The visual hierarchy is:

1. current workflow state;
2. interpreted operation result;
3. equivalent CLI and stable identifiers;
4. raw protocol evidence on demand.

The design must not use two equal JSON columns. Raw JSON belongs in the right
evidence drawer. The center explains what happened while retaining direct links
to the run and deployment identifiers.

## Stable Composition

The existing stage geography remains authoritative:

- left: operator and agent intent;
- center: operation, graph, and interrupt state;
- right: raw evidence;
- bottom: scene navigation.

Scene 9 changes ownership within that geography rather than rearranging it.
The chat can contract from full width to a rail, but it does not jump to another
side. The graph expands in the center. Raw evidence enters from the right.

At `1280x720`, the center must retain at least 60 percent of the usable width
during the `graph` and `interrupt` beats. The scene rail remains available but
uses a quieter treatment than the active workflow state.

## Beat Choreography

### Beat 1: Start Operation

The operator request remains visible on the left. The agent's workflow start
tool call visually expands into the center as one operation surface.

The center operation surface contains:

- operation name and successful/interrupted status;
- equivalent CLI in a single compact command row;
- a concise interpreted summary with deployment id, run id, and interrupt kind;
- a small "View raw evidence" action that opens the existing evidence drawer.

The interpreted summary is normal product UI, not serialized JSON. The raw
response is not duplicated in the center.

### Beat 2: Reusable Graph

The operation surface contracts into a compact execution receipt at the top of
the center. The chat becomes a rail. The workflow graph expands into the
remaining stage area.

The graph must show connectors and execution direction, not only independently
positioned buttons. Completed nodes are visually settled, the current node uses
cyan, and future nodes remain neutral. Labels must be readable without opening
the node spotlight.

The receipt retains the run id and status so the graph is visibly tied to the
operation that created it.

### Beat 3: Typed Interrupt

Execution focus advances to `review_issues`. The interrupt node becomes the
only amber focal point. A compact contract preview appears adjacent to the
selected node and states:

- interrupt kind;
- expected resume object;
- available outcomes;
- persisted run id.

This is a preview, not the approval form. Advancing to Scene 10 opens the full
approval interaction without changing the selected run or graph context.

## Component Boundaries

### `DemoWorkflowScene`

Owns beat-specific composition only. It determines whether the center displays
the expanded operation, compact receipt, graph, or interrupt preview. It does
not decode replay payloads or own animation timing.

### `OperationBlock`

Gains explicit presentation variants rather than inferring layout from CSS:

- `expanded`: command plus interpreted operation summary;
- `receipt`: compact operation, status, duration, and run id.

The component receives already-decoded `DemoEvent` data. A focused projection
helper converts the event into audience-facing fields. Unknown or absent fields
render as unavailable rather than throwing.

### `WorkflowGraphStage`

Owns the graph's visual execution state. Its input identifies the current node
and completed nodes. It renders semantic connectors and keeps buttons for
keyboard selection and node spotlight behavior.

The graph remains a presentation projection; it does not introduce a second
workflow model or fetch product data.

### `OperatorChat`

Retains the existing message and approval contracts. This slice corrects its
light and dark theme tokens and adds a stable visual anchor for the tool call
that expands into the center. It does not become a new generic chat product.

### `EvidenceDrawer`

Remains the sole raw protocol surface. The operation's evidence action opens
the existing replay evidence at the corresponding event when possible. If
event-level selection is not available, opening the bounded recording evidence
is acceptable; inventing a second evidence store is not.

## Motion

Use the existing `motion` dependency. Motion communicates ownership:

- the workflow-start tool part and expanded operation share a layout identity;
- the expanded operation contracts into the receipt between beats;
- graph nodes enter in execution order with a short stagger;
- the current-node indicator moves from the start path to the interrupt;
- the interrupt contract preview uses a short fade and horizontal reveal.

Normal transitions should complete in 250 to 650 milliseconds. No transition
may exceed one second. There is no typewriter effect, bounce, or decorative
continuous animation.

With `prefers-reduced-motion` or the presentation motion toggle disabled,
layout morphs become immediate state changes with a short opacity crossfade at
most.

## Theme And Token Repair

Nested presentation components must consume stage and chat tokens instead of
hard-coded assumptions about their parent background. Define a bounded token
set for:

- night canvas, raised surface, inset surface, and structural line;
- primary, secondary, and muted text;
- current execution cyan;
- interrupt amber;
- success and failure states.

Night-stage children must not inherit the console's paper surface. Chat text
and controls must derive from `data-chat-theme`, independently of the stage
theme. New colors and radii must be represented by presentation tokens rather
than adding more literal values throughout `presentation.css`.

This slice may split the large stylesheet into presentation token, stage,
operation, graph, and chat files if imports remain centralized through the
presentation route. The split is justified only where it makes the visual
contract easier to maintain.

## Accessibility

- Normal text meets WCAG 2.2 AA contrast.
- Cyan and amber are never the only indication of current or interrupted state;
  labels and state text remain present.
- Graph nodes remain buttons with visible focus.
- The evidence action and node spotlight remain keyboard reachable.
- Motion-disabled operation preserves every piece of information.
- No required content is clipped or scroll-dependent at `1280x720`.

## Testing And Verification

### Component Tests

- expanded operations emphasize interpreted fields and omit center-stage raw
  JSON;
- receipt operations retain operation, status, duration, and run id;
- graph execution state distinguishes completed, current, interrupt, and future
  nodes semantically;
- missing optional event fields render a bounded fallback;
- the raw-evidence action invokes the existing evidence opening callback.

### Presentation Tests

- Scene 9 beat transitions select the correct operation and graph variants;
- Scene 9's interrupt beat retains the same run id used by Scene 10;
- keyboard navigation and node spotlight behavior remain intact;
- reduced-motion mode does not hide content.

### Browser Verification

Capture all three Scene 9 beats and Scene 10's approval beat at `1280x720`.
Verify:

- no overflow or clipped primary actions;
- readable chat, command, interpreted result, and graph labels;
- raw evidence opens and closes without changing the current beat;
- the operation-to-graph transition communicates one continuous run;
- `/console` remains visually and functionally unchanged.

## Success Criteria

The slice is complete when:

1. Scene 9 is readable and visually coherent at `1280x720`.
2. The center no longer renders competing raw and interpreted JSON columns.
3. The same run visibly progresses from start operation to graph to interrupt.
4. Scene 10 receives the interrupt context without a visual or data reset.
5. Raw evidence remains one deliberate action away.
6. Reduced-motion and keyboard operation preserve the full story.
7. Focused tests, console tests, typecheck, build, and browser smoke pass.

## Follow-Up

After this slice, extract the proven visual language across the remaining
presentation scenes. Scenes 8 through 10 should be polished as one centerpiece
sequence before broad styling work. Speaker-script rehearsal, offline defense
hardening, `/console` component-library adoption, a live AI driver, and remote
presenter control remain later work.
