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

- A full-screen, read-only Scene 8 conversation with one operator request and
  a concise external-agent response.
- A Scene 8 to Scene 9 conversation-receipt transition.
- A deterministic prepared-authoring recording with literal `wf` commands,
  command results, and phase-specific workflow projections.
- A Scene 9 workflow canvas with an anchored `Agent trace` control.
- A floating trace panel that opens at the current authoring phase.
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
It adopts the templates' readable tool grouping, floating-panel vocabulary,
focus behavior, and motion language without importing their whole runtime
surface. A later live-agent slice may introduce a real assistant runtime,
`thread.json`, and a truthful slash-command composer together.

References:

- [assistant-ui Thread](https://www.assistant-ui.com/docs/ui/thread)
- [assistant-ui Assistant Modal](https://www.assistant-ui.com/docs/ui/assistant-modal)
- [assistant-ui Tool Fallback](https://www.assistant-ui.com/docs/ui/tool-fallback)
- [assistant-ui Composer Trigger Popover](https://www.assistant-ui.com/docs/ui/composer-trigger-popover)

## Story And Composition

### Scene 8: Agent Handoff

Scene 8 is a full-screen conversation with no graph, lifecycle rail, evidence
receipt, or console chrome competing for attention. It must read as a real
chat transcript: visibly separated user and assistant turns, normal message
spacing, and no orphaned tool block presented as the whole conversation. It
has two beats:

1. `request`: the operator asks for a reusable thesis-readiness workflow from
   selected documents and an issue board.
2. `handoff`: the external agent explains that it will discover the available
   workflow surface, author the reusable graph, validate it, and prepare a
   deployment.

The assistant's final handoff response contains a concise factual summary of
the five prepared authoring phases. It must say these are prepared operations,
not hidden reasoning or autonomous live execution. The request and handoff
beats use the same conversation source, revealing additional already-recorded
turns rather than synthesizing new text at render time.

### Transition: Conversation Receipt

The presentation must not attempt to morph assistant-ui Thread internals into
the floating trace panel. Instead, when Scene 9 enters, the final Scene 8
handoff contracts into a small presentation-owned receipt at the lower edge of
the workflow canvas:

```text
Prepared workflow
Discover · author · validate
Open agent trace
```

The receipt is the visual bridge between scenes and the accessible trigger for
the Scene 9 trace panel. Its content remains factual and constant while the
active authoring phase changes.

### Scene 9: Prepared Workflow Lifecycle

The Scene 9 canvas is primary. It shows one lifecycle projection per beat. The
floating trace is secondary and opens only from the receipt or `Agent trace`
control. Opening it never resizes or replaces the canvas.

The trace panel uses the assistant-modal interaction model: anchored trigger,
focus moved into the panel, Escape/close returns focus to the trigger, and
reduced-motion removes transform-based entrance motion. It is not the generated
`assistant-modal.json` component because that component embeds the full runtime
Thread.

Each Scene 9 beat selects exactly one authoring phase:

| Beat | Canvas projection | Expanded trace group |
| --- | --- | --- |
| `discover` | Required sources, capabilities, and input schema | Discover |
| `draft` | Draft graph with nodes and declared outcome routes | Draft |
| `validate` | Invalid binding/diagnostic followed by repair status | Validate and repair |
| `artifact` | Immutable artifact identifier and version | Compile artifact |
| `deployment` | Concrete local source bindings and deployment validation | Deploy and validate |

Other trace groups stay collapsed. The presenter can expand them manually, but
changing a group does not alter the active canvas phase.

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
5. **Deploy and validate**: `wf deploy create` and `wf deploy validate` bind
   logical requirements to the local report, issue-board, and document sources.

Command text must use the public `wf` surface and match the example's supported
commands. Result text must stay short enough for the trace panel. Longer JSON
or diagnostics are expandable, scroll-contained details rather than default
content.

## Data Boundaries

The recording owns the authoring facts. A pure projection function maps the
selected phase to:

- the Scene 9 lifecycle/canvas model;
- the corresponding command-group transcript;
- receipt text and status;
- the active Scene 9 beat.

`PresentationRoute` remains the route owner. It maps a Scene 9 hash to a phase;
it must not create another chat state store or call the workflow RPC server.
`AssistantOperatorThread` remains a renderer of projected messages. A dedicated
floating-panel wrapper owns only open/close state and focus restoration.

If the recording cannot decode, Scene 9 renders a compact unavailable state
with the evidence pointer and does not invent authoring facts. The trace trigger
is disabled with an explanatory label.

## Accessibility And Responsive Rules

- The receipt trigger is a semantic button with an accessible name that includes
  `Agent trace`.
- Opening the panel focuses its heading or close control. Closing with Escape
  or the close button restores focus to the receipt trigger.
- Tool groups are buttons with `aria-expanded`; their literal commands remain
  copyable text.
- At 1280 by 720, the panel overlays the canvas at a readable maximum width and
  height. At 1024 by 768 and narrower, it becomes a bottom sheet or full-width
  inset without clipping its command list.
- Canvas content may scroll inside its own region; the presentation viewport
  must not acquire page-level scrollbars.
- Motion is limited to opacity and short positional transitions. It honors
  `prefers-reduced-motion` and the existing presentation motion toggle.

## Verification

- Unit-test recording decoding and phase projection, including rejected/missing
  recording data.
- Unit-test the trace panel's active-group and collapse behavior.
- Component-test receipt trigger, focus restoration, Escape, and compact
  unavailable state.
- Route-test all five Scene 9 hashes and Scene 8 to Scene 9 transition state.
- Browser-smoke the full-screen Scene 8 thread, each Scene 9 phase, open/close
  trace panel, 1280 by 720, and 1024 by 768.
- Run console tests, console typecheck, console build, and `git diff --check`.

## Follow-On Work

The following needs its own design because it changes the interaction contract:

- an assistant-ui runtime adapter backed by a real agent service;
- a truthful live composer and slash command popover;
- optional commands that focus figures, run lifecycle operations, or open
  evidence using the same tool/action contract as the live agent.
