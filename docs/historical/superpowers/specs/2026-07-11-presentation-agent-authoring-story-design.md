# Presentation Agent Authoring Story Design

## Purpose

Scenes 8 and 9 should make the defense's agent-facing claim concrete without
claiming that lda.chat contains an autonomous planning model. Scene 8 introduces
an external planner through a full-screen conversation. Scene 9 proves the
durable authoring work through a prepared, inspectable command trace and a
matching workflow lifecycle projection.

The design replaces the current disconnected combination of a generic agent
handoff and a chat-free lifecycle scene. It does not replace the existing live
run, interrupt, output, or trace proof in Scenes 10 through 12.

## Scope

This slice contains:

- A full-screen, read-only Scene 8 conversation with operator/assistant turns
  interleaved with prepared tool activity.
- A continuous Scene 8 to Scene 9 conversation transition.
- A deterministic prepared-authoring recording with literal `wf` commands,
  command results, and phase-specific workflow projections.
- A Scene 9 workflow canvas with a synchronized compact chat dock.
- Expandable tool groups inside the dock instead of a separate trace modal.
- Keyboard, route, and responsive behavior for the new surfaces.

This slice excludes:

- Live LLM calls, credentials, or a chat backend.
- A new assistant runtime or `AssistantRuntimeProvider` adapter.
- A user-editable composer or slash command execution.
- Any claim that a model made the recorded authoring decisions.
- Changes to the factual live run path in Scenes 10 through 12.

## Assistant UI Boundary

The repository already owns `@assistant-ui/react` tool fallback and tool-group
components. The official `thread.json`, `assistant-modal.json`, and
`composer-trigger-popover.json` registry templates were inspected as visual and
interaction references.

The generated `Thread` requires a full assistant-ui runtime and brings a
composer, attachments, suggestions, reasoning, message action bars, and other
interactive controls. `assistant-modal.json` embeds that same generated Thread,
and `composer-trigger-popover.json` requires the unstable runtime composer
primitive. Installing either generated component unchanged would conflict with
the deterministic source-owned transcript projection.

Therefore this slice keeps `AssistantOperatorThread` as a read-only renderer.
It uses the source-owned assistant-ui tool fallback and tool-group components
for both the full thread and compact dock. A later live-agent slice may
introduce a real assistant runtime, `thread.json`, and a truthful slash-command
composer together.

References:

- [assistant-ui Thread](https://www.assistant-ui.com/docs/ui/thread)
- [assistant-ui Assistant Modal](https://www.assistant-ui.com/docs/ui/assistant-modal)
- [assistant-ui Tool Fallback](https://www.assistant-ui.com/docs/ui/tool-fallback)
- [assistant-ui Composer Trigger Popover](https://www.assistant-ui.com/docs/ui/composer-trigger-popover)

## Story And Composition

### Scene 8: Agent Handoff

Scene 8 is a full-screen conversation with no graph, lifecycle rail, evidence
receipt, or console chrome competing for attention. It must read as a real
chat screen: visibly separated user and assistant turns, normal message
spacing, and prepared tool groups interleaved with assistant narration. It has
two beats:

1. `request`: the operator asks for a reusable thesis-readiness workflow from
   selected documents and an issue board.
2. `handoff`: the external agent explains that it will discover the available
   workflow surface, author the reusable graph, validate it, and prepare a
   deployment.

The assistant's final handoff response contains a concise factual summary of
the five prepared authoring phases. It must say these are prepared operations,
not hidden reasoning or autonomous live execution. The request and handoff
beats use the same conversation source, revealing additional already-recorded
turns and tool groups rather than synthesizing new text at render time.

### Transition: Continuous Conversation Dock

Scene 9 keeps the same assistant thread visible as a compact dock at the bottom
of the stage. The dock is not a screenshot, receipt, or second transcript. It
projects the same stable message IDs and tool-call IDs used by Scene 8.

On scene entry the thread container contracts while the workflow canvas takes
the upper stage. The active phase's tool group is expanded and scrolled into
view; completed groups collapse to one-line status receipts. The dock may be
manually expanded, but it never covers the primary workflow projection.

### Scene 9: Prepared Workflow Lifecycle

The Scene 9 canvas is primary. It shows one lifecycle projection per beat. The
conversation dock is secondary and remains anchored below it. There is no
separate `Agent trace` modal.

Each Scene 9 beat selects exactly one authoring phase:

| Beat | Canvas projection | Active dock group |
| --- | --- | --- |
| `discover` | Required sources, capabilities, and input schema | Discover |
| `draft` | Draft graph with nodes and declared outcome routes | Draft |
| `validate` | Invalid binding/diagnostic followed by repair status | Validate and repair |
| `artifact` | Immutable artifact identifier and version | Compile artifact |
| `deployment` | Concrete local source bindings and deployment validation | Deploy and validate |

Other tool groups stay collapsed. The presenter can expand them manually, but
changing a group does not alter the active canvas phase.

The five canvas projections use distinct factual visual forms:

- `discover`: source inventory plus capability and schema contract.
- `draft`: a compact directed graph with declared outcome routes.
- `validate`: diagnostic before/after repair with the corrected projection.
- `artifact`: immutable artifact identity, version, and required sources.
- `deployment`: logical-to-concrete source bindings and validation status.

## Prepared Authoring Recording

Create a canonical, versioned recording separate from
`lda-report-success.v1.json`. It is authored evidence for workflow construction,
not a proxy for an LLM trace. Each phase includes a label, a concise narrator
line, multiple literal CLI commands, bounded result data, and a canvas
projection.

The command sequence is:

1. **Discover**: `wf source list`, `wf cap list`, and `wf schema` inspect the
   configured capability inventory and public input shapes.
2. **Draft**: `wf draft create`, `wf draft add-step`, and declared route
   operations create the reusable graph.
3. **Validate and repair**: bindings are applied, validation returns a bounded
   diagnostic, and the corrected binding/route operation produces a valid draft.
4. **Compile artifact**: `wf draft compile` and `wf artifact inspect` show the
   immutable versioned workflow definition.
5. **Deploy and validate**: `wf deploy save` and `wf deploy validate` bind
   logical requirements to the local report, issue-board, and document sources.

Command text must use the public `wf` surface and match the example's supported
commands. Result text must stay short enough for the dock. Longer JSON or
diagnostics are expandable, scroll-contained details rather than default
content.

## Data Boundaries

The recording owns the authoring facts. A pure projection function maps the
selected phase to:

- the Scene 9 lifecycle/canvas model;
- dock messages and active tool group;
- the active Scene 9 beat.

`PresentationRoute` remains the route owner. It maps a Scene 9 hash to a phase;
it must not create another chat state store or call the workflow RPC server.
`AssistantOperatorThread` remains a renderer of projected messages. A small
presentation-owned wrapper controls only full-thread versus dock layout and the
active expanded tool group.

If the recording cannot decode, Scene 9 renders a compact unavailable state
with the evidence pointer and does not invent authoring facts. The dock shows a
single unavailable message rather than fabricated tool results.

## Accessibility And Responsive Rules

- Tool groups are buttons with `aria-expanded`; their literal commands remain
  copyable text.
- At 1280 by 720, the dock occupies no more than 30 percent of the stage. At
  1024 by 768 and narrower, it remains full-width below the canvas with its own
  scroll containment.
- Canvas content may scroll inside its own region; the presentation viewport
  must not acquire page-level scrollbars.
- Motion is limited to a 150–250 ms thread-container resize and canvas
  crossfade. Do not blur, scale, or pan unchanged thread content. Motion honors
  `prefers-reduced-motion` and the existing presentation motion toggle.

## Verification

- Unit-test recording decoding and phase projection, including rejected/missing
  recording data.
- Unit-test dock projection, active-group synchronization, and stable IDs.
- Component-test full-thread/dock layout, tool expansion, and compact
  unavailable state.
- Route-test all five Scene 9 hashes and Scene 8 to Scene 9 transition state.
- Browser-smoke the full-screen Scene 8 thread and each synchronized Scene 9
  phase at 1280 by 720 and 1024 by 768.
- Run console tests, console typecheck, console build, and `git diff --check`.

## Follow-On Work

The following needs its own design because it changes the interaction contract:

- an assistant-ui runtime adapter backed by a real agent service;
- a truthful live composer and slash command popover;
- optional commands that focus figures, run lifecycle operations, or open
  evidence using the same tool/action contract as the live agent.
