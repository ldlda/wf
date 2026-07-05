# Defense Presentation Storyboard Design

## Status

Current narrative and composition contract for the lda.chat thesis defense.

This document defines what the presentation must communicate and how the stage
changes while it does so. It complements the
[React presentation mode design](2026-07-03-react-presentation-mode-design.md),
which defines the existing route and component architecture, and the
[constrained demo agent design](2026-07-03-constrained-demo-agent-design.md),
which defines the prepared replay driver.

## Purpose

The defense must explain a systems contribution, demonstrate a real product
surface, and survive unreliable network or model access. The current `/present`
route proves that the components can be composed, but it does not yet provide a
coherent defense story or fit the content into a `1280x720` viewport.

The presentation is not a conventional slide deck wrapped around a separate
demo. It is a staged React compositor. Thesis claims, architecture diagrams,
chat, workflow graphs, operations, interrupt approval, outputs, and evidence
occupy the same stable stage and move between semantic scenes.

The listed scene budgets total 8 minutes 36 seconds. Rehearsal should target a
10-to-11-minute main path after transitions, approval interaction, and natural
pauses. This leaves margin in a 15-minute slot without forcing the presenter to
rush.

## Speaking Voice

The spoken script primarily uses personal defense voice:

- "I designed and implemented ..."
- "I evaluated ..."
- "I deliberately excluded ..."

Technical invariants remain neutral where precision matters:

- "The runtime validates the payload before execution."
- "A deployment binds logical requirements to concrete sources."

This keeps ownership clear without making the system sound subjective.

## Claim Discipline

Every scene carries one claim class. The visual treatment must make the class
clear without requiring the presenter to recite a disclaimer.

- **Motivation:** problem framing or design rationale; not an empirical result.
- **Implemented:** supported by current code, tests, or a product operation.
- **Evaluated:** supported by the thesis case studies or the audited 36-trial
  challenge cohort.
- **External context:** a cited result from another organization; not evidence
  about lda.chat.
- **Future work:** a plausible extension that is not part of the submitted
  implementation.

Each scene definition must retain an evidence pointer. An evidence pointer may
be a thesis section, repository path, deterministic replay event, test group, or
external source. A scene without an evidence pointer may present motivation or
transition language, but it may not introduce a new factual claim.

## Stable Stage Geography

The presentation uses three canonical layers:

- **Editorial Canvas:** the persistent warm, light visual identity used for the
  spoken argument, figures, and transitions.
- **Product Surface:** a real application or evidence surface that expands from
  an inline trigger when the story requires product proof.
- **Presentation Frame:** the thin remainder of the Editorial Canvas that stays
  visible around an expanded Product Surface.

The presentation is therefore an editorial thesis deck that temporarily
transforms into the product. It is not a dashboard or chat application used as
a decorative container for every scene.

The stage has two stable content regions and one transient inspection layer:

```text
+----------------+--------------------------------+
| agent / chat   | primary graph, model, output   |
| optional       | always owns visual focus       |
+----------------+--------------------------------+
| progress and compact evidence receipt           |
+-------------------------------------------------+
```

The regions may expand, collapse, or overlap, but they do not swap meanings.
The audience should learn the geography once. A Product Surface may occupy
roughly 80 percent of the stage, but it does not erase the Presentation Frame;
the audience must still read it as evidence inside the argument rather than an
accidental application switch.

- **Left:** agent conversation and operation intent.
- **Center:** the primary explanation, workflow graph, output, or evaluation
  result.
- **Overlay:** raw and interpreted evidence, trace, schemas, or source details.

Narrative scenes hide chat. Demo scenes may show chat as `full`, `rail`, or
`dock`. Evidence appears as a compact progress-row receipt unless the presenter
explicitly opens the centered inspector.

The dock remains visible in a corner when chat is otherwise hidden. Pointer
hover may preview it, but opening chat requires a click, keyboard action, or
presenter control so the interaction remains usable without a precise mouse.

Vertical stacking is forbidden on the main path. Across supported logical
canvases from `960x720` through `1280x720`, the presenter must not scroll to
discover the graph, approval control, output, or next action.

The audience route keeps a deterministic `720px` logical height and adapts its
logical width continuously from `960px` to `1280px`, covering `4:3` through
`16:9`. Container queries adapt placement without omitting information.
Unsupported extreme ratios letterbox. Presenter and audience views preserve
the same semantic content and Focus Path. See the
[adaptive presentation canvas design](2026-07-05-adaptive-presentation-canvas-design.md).

## Unified Presentation Identity

The Editorial Canvas keeps one warm, light identity from introduction through
conclusion. Product surfaces may use their native light or dark appearance,
but entering a product surface does not switch the theme of the entire deck.
Chat remains independently positioned because it is a product element, not the
presentation's visual identity:

See [ADR 0005](../../adr/0005-editorial-canvas-around-shared-product-surfaces.md).

Major claims use an editorial display serif, provisionally Newsreader. Source
Sans 3 remains the explanatory and interface face, while IBM Plex Mono is
reserved for commands, identifiers, schemas, and evidence. Condensed all-caps
type is an accent rather than the default title treatment.

```ts
type PresentationAppearance = {
  readonly chatMode: "hidden" | "full" | "rail" | "dock";
  readonly productExpansion: "inline" | "expanded";
};
```

A rehearsal toolbar may override chat position, product expansion, motion,
playback mode, and scene selection. It is hidden during the defense.

Remote or phone control is not required for the redesign. Presentation actions
remain input-agnostic so a later remote can dispatch them, but keyboard and
pointer operation are the supported defense controls.

## Defense Chrome

The audience-facing route persistently shows only a quiet scene number or
progress marker. The full scene rail, replay status, discussion index,
presenter controls, and prepared-agent trigger are hidden until explicitly
summoned.

On first visit, a dismissible presenter onboarding overlay explains navigation
and rehearsal controls. Afterwards, `?` opens a presenter-only command and
shortcut palette. Presenter controls are therefore discoverable without
becoming persistent audience chrome; the existing secret `P` shortcut is not a
sufficient interface.

A separate `/presenter` companion route shows the current and next beat,
speaker notes, timer, Discussion Library, and presentation controls without
exposing them on the projected `/present` route. A temporary notes overlay on
`/present` remains the single-screen fallback.

Audience and presenter routes communicate through a typed **Presentation
Transport** that carries reducer actions. The first adapter uses
`BroadcastChannel` for same-browser windows. A future authenticated WebSocket
relay may connect different machines or networks using the same event contract;
that relay does not execute workflows or own presentation semantics.

The presenter palette includes a searchable **Discussion Library** instead of
an audience-facing discussion button. Opening a prepared question stores the
exact scene, beat, and Focus Path. Closing the discussion restores that return
location.

The prepared workflow starts from the chat surface, provisionally through a
button or slash command, rather than through a detached corner action. This
entry point is part of the product story and may later be replaced by a fuller
chat framework without changing the presentation contract.

A **Guided Run** is the prepared agent sequence used during the defense. The
presentation timeline owns its pacing. After emitting the content permitted by
the current beat, the driver waits at a **Beat Gate** until the presenter
advances. Advancing releases at most the next audience-relevant operation;
internal or repetitive actions remain hidden.

The chat starts a Guided Run through a visible **Prompt Macro**, provisionally
`/demo report`. Invoking it expands into the full natural-language request, and
the transcript displays that expanded request rather than a raw slash command.
Expandable provenance may identify the originating macro.

The audience sees a quiet execution provenance label, `Prepared replay` or
`Live server`, but no mode controls. Live and replay drivers must produce the
same Guided Run and Beat Gate structure. If live setup fails, replay replaces
it without changing the presentation narrative or interaction sequence.

Only one audience-relevant operation may cross a Beat Gate at a time. If a live
operation is still running, further advance input does not launch another
operation or skip the gate. The beat shows a restrained working state, and a
presenter-only action may replace that operation with its prepared replay.

If a live operation fails, its failed Chat Tool Receipt remains visible. The
presenter may explicitly choose `Continue with prepared replay`; the
continuation changes the provenance label and never rewrites the failed live
evidence.

An audience-relevant operation has two independent projections from the same
canonical event:

- **Chat Tool Receipt:** a subtle collapsed chat row, expandable on demand into
  a bounded, scrollable terminal-style detail. A future chat framework should
  own its interaction and accessibility.
- **Stage Projection:** a curated operation view rendered only when the current
  argument needs that operation as evidence.

The Chat Tool Receipt does not physically morph into the Stage Projection.
Their continuity is semantic and timeline-driven, which avoids coupling chat
layout to presentation choreography.

A pending typed interrupt creates one **Approval Session** with synchronized
chat and Product Surface projections. Chat presents a compact approval card and
selection summary; the Product Surface presents the full schema-backed list or
form. Edits from either projection update the same draft response. Submission
from either resolves the interrupt exactly once, then both projections become
read-only with the same result.

Both projections consume a reusable **Schema Form Surface** rather than
hand-built interrupt fields. It accepts JSON Schema, a draft value, validation
state, read-only state, and custom widget registrations. Typed interrupts are
the first consumer; deployment inputs, run inputs, and future configuration
surfaces may reuse the same boundary. Domain-specific interactions such as
issue selection are custom widgets over the generic form contract.

The Schema Form Surface lives in a small shared web package. Console and
presentation surfaces import that package, while app-specific widgets and
Approval Session orchestration remain in their owning applications.

Chat rendering uses source-owned, established AI-chat primitives rather than
project-specific message and tool-call components. The adopted surface must
cover conversation, message, collapsed tool receipt, bounded terminal detail,
and prompt input. It owns rendering and accessibility only;
`AgentMessagePart`, `AgentDriver`, Guided Run, and Beat Gate semantics remain
project contracts.

Tailwind and shadcn-compatible styling may be introduced additively for these
source-owned primitives and new presentation components. Existing console CSS
is not subject to a wholesale rewrite; it migrates only when a component is
replaced. See [ADR 0004](../../adr/0004-adopt-tailwind-additively-for-source-owned-ui.md).

## Motion Contract

Motion uses only three primitives:

- **Reveal:** a fast opacity transition introduces genuinely new explanatory
  content.
- **Expand:** an existing object grows into a Product Surface while preserving
  its identity.
- **Reframe:** existing content moves aside to retain context while another
  surface takes focus.

Unchanged objects do not remount or replay entrance animation between beats.
Blur, bounce, generic stagger, and decorative typewriter effects are forbidden.
Reduced-motion mode replaces Expand and Reframe with immediate layout changes
and keeps Reveal brief.

## Interactive Figures

Architecture, authoring, workflow, and evidence diagrams use a shared
**Interactive Figure** model rather than scene-specific card layouts. An
Interactive Figure contains addressable **Figure Nodes** and relationships.
Graph-shaped figures may use the existing React Flow and Dagre dependencies;
linear figures may use lighter SVG or HTML renderers over the same interaction
contract.

A Figure Node may reference a child figure. Activating it pushes the node onto
a single **Focus Path** and reframes the canvas around that child figure.
Ancestors remain available through a compact breadcrumb, and `Escape` pops one
focus level. A child figure may contain further expandable nodes, but only one
Focus Path is active; the interface never stacks nested modals or sidebars.

Normal figures are authored as declarative TypeScript definitions containing
nodes, relationships, semantic types, child-figure references, and canonical
Focus Paths. The shared renderer owns layout, focus, keyboard behavior, and
motion. A custom React renderer is an explicit escape hatch for exceptional
figures rather than the default scene-authoring mechanism.

Factual architecture and evaluation nodes carry evidence pointers in their
definitions. Those pointers remain hidden during the normal path and become
available through focused inspection, Q&A, or the evidence surface.
Motivational nodes may omit evidence pointers.

Main-path Figure Node labels use system concepts such as “Runtime” or “Source
providers.” Focused detail may reveal concrete packages, public operations,
tests, or symbols such as `wf_core` and `wf_api`.

Initial figure layout supports only layered, flow, and explicit-position modes.
Dagre may calculate spacing inside the first two. A new reusable layout mode is
added only after at least two concrete figures require it; the presentation is
not a general diagram-layout engine.

Interactive Figures expose keyboard navigation: `Tab` reaches Figure Nodes,
arrow keys move spatially between related nodes, `Enter` expands the focused
node, and `Escape` pops one Focus Path level. Breadcrumbs remain pointer and
keyboard accessible. The presenter `?` palette lists these controls when figure
focus is active.

While a Figure Node owns focus, arrow keys belong to the figure. `Escape`
returns focus to the presentation stage, after which arrows navigate beats.
`Space` remains a global advance shortcut except while focus is inside chat,
forms, terminal detail, or another text-entry control.

Each beat may declare a canonical Focus Path for deterministic playback.
Presenter interaction may temporarily replace it for explanation or Q&A.
Advancing to another beat applies that beat's canonical Focus Path, preventing
manual exploration from making later scenes nondeterministic.

Canonical deep links encode scene, beat, and optional Focus Path so an
interactive figure state can be reproduced directly. Ephemeral UI state such
as chat scroll, expanded Chat Tool Receipts, and presenter-palette visibility
does not enter the URL.

Editorial figures use restrained semantic color:

- blue identifies planner or client intent;
- green identifies deterministic runtime execution;
- orange identifies human boundaries or intervention.

The warm canvas and black typography remain dominant. Labels, connector styles,
and node shapes must carry the same distinction when color is unavailable.

The renderer exposes a small **Figure Vocabulary** rather than one universal
rounded node: actors, operations, artifacts, runtime systems, human boundaries,
and evidence. Scenes compose those primitives differently so they share
interaction behavior without looking mechanically generated from one template.

Visual personality primarily comes from expressive scale, asymmetry, direct
figure manipulation, memorable scene transformations, and occasional
purpose-built illustration or iconography. Decorative gradients, badges, and
background effects are permitted only when they support a specific scene; they
are not the default source of visual interest.

The workflow graph in the product demonstration is not reconstructed through
the Figure Vocabulary. It embeds the real console graph component, driven by
the canonical workflow and run state, inside an expanded Product Surface.
Editorial annotations may explain it without replacing the product evidence.

Product Surfaces use the console's shared components and design tokens rather
than a presentation-only skin. Improving graph, form, receipt, or evidence
styling therefore improves both `/console` and `/present`; presentation code
controls only framing, scale, and when a surface is shown.

The main defense path uses the console's light product theme to remain coherent
with the warm Editorial Canvas. Dark mode remains available in the console but
is not part of the main defense sequence. Terminal and code insets may remain
dark when that treatment communicates their actual content type.

## Scene Semantics

A scene is larger than a slide. It is a semantic chapter composed from several
visual states. Text, diagrams, operations, graphs, and evidence may enter,
leave, expand, or collapse while the scene id remains stable.

Advancing within a scene changes a **beat**. Advancing after the final beat
changes the **scene**. Discussion branches can return to the exact scene and
beat from which they were opened.

Each beat definition carries its short visible claim, speaker notes, timing
budget, evidence pointer, visual or figure id, canonical Focus Path, and
optional Beat Gate. Components render that definition; they do not own the
spoken script or duplicate scene-specific content.

At `1280x720`, each beat presents one primary visual, one short claim, and at
most three supporting labels. A command, schema, or evidence view may replace
the primary visual but does not compete beside another primary visual. Speaker
notes carry details that do not fit this composition budget.

## Main Storyboard

The sequence below preserves the current argument and evidence order, but its
exact scene boundaries and beat counts are not frozen. Visual redesign may
merge, split, or re-time scenes when the claim order, evidence coverage,
discussion returns, and overall defense budget remain intact.

Visual review uses a Playwright-generated gallery of selected beats at
`1280x720` plus manual traversal in the browser. Automated checks cover state,
keyboard behavior, accessibility, overflow, and interaction contracts. The
gallery supports human approval and is not initially enforced through brittle
pixel-diff thresholds.

The redesign preserves public navigation, canonical replay evidence, and
useful reducer actions. It removes obsolete internal contracts cleanly,
including whole-stage theme switching, one-off diagram components, persistent
audience chrome, and presentation-only product skins. Unused UI APIs do not
receive compatibility wrappers.

### Scene 1: Thesis

- **Time:** 0:20
- **Claim class:** Implemented
- **Spoken intent:** "I began with the goal of building an AI agent for creating
  and automating workspace workflows. That exposed a more fundamental need: a
  typed system for creating, validating, running, and inspecting the workflows
  that an agent proposes. This thesis implements that substrate."
- **Primary visual:** title and one-sentence thesis.
- **Composition:** warm Editorial Canvas; chat hidden; no evidence panel.
- **Evidence pointer:** thesis Abstract and Introduction.
- **Transition:** the title contracts into a small persistent lda.chat mark.

### Scene 2: The Problem

- **Time:** 0:40
- **Claim class:** Motivation
- **Spoken intent:** direct agent tool calls can perform actions, but reusable
  automation also needs typed contracts, lifecycle state, source bindings,
  deterministic execution, persistence, traceability, and recovery boundaries.
- **Primary visual:** an unstable sequence of direct tool calls contrasted with
  a durable workflow record; the missing responsibilities appear around it.
- **Composition:** warm Editorial Canvas; chat hidden.
- **Evidence pointer:** thesis problem statement, requirements, and research
  question.
- **Transition:** the requirements arrange into a landscape of related systems.

### Scene 3: Positioning and Related Systems

- **Time:** 0:50
- **Claim class:** Motivation
- **Spoken intent:** direct tool loops maximize flexibility, generated scripts
  maximize simplicity, hosted automation platforms provide mature triggers and
  integrations, agent graph frameworks provide durable agent execution, and
  MCP standardizes capability access. lda.chat explores a different center of
  gravity: typed lifecycle contracts and provider-neutral sources intended for
  external-agent operation.
- **Primary visual:** related approaches progressively occupy distinct positions
  around lda.chat; do not reproduce the thesis comparison table.
- **Composition:** warm Editorial Canvas; each approach enters while the positioning axis
  remains stable.
- **Evidence pointer:** thesis Positioning and Related Systems chapter.
- **Transition:** lda.chat's position resolves into the planner/runtime boundary.

### Scene 4: Planner and Runtime

- **Time:** 0:40
- **Claim class:** Implemented
- **Spoken intent:** the external planner proposes or revises workflow
  structure; the deterministic runtime validates, executes, records, and
  resumes it.
- **Primary visual:** a two-sided planner/runtime boundary with explicit
  operations crossing it.
- **Composition:** warm Editorial Canvas; chat hidden; the planner/runtime
  boundary carries its own semantic color and shape treatment.
- **Evidence pointer:** thesis architecture overview and workflow API boundary.
- **Transition:** the runtime side expands into the lifecycle.

### Scene 5: Lifecycle

- **Time:** 1:00
- **Claim class:** Implemented
- **Spoken intent:** explain Draft, Artifact, Deployment, and Run as distinct
  records with different mutability and responsibility.
- **Primary visual:** lifecycle records, including both draft-save and direct
  plan-import paths into an immutable artifact.
- **Composition:** warm Editorial Canvas; center focus; the progress row may
  show one compact evidence receipt.
- **Evidence pointer:** thesis lifecycle chapter and lifecycle explorer.
- **Transition:** selecting a deployment zooms into the runtime architecture.

### Scene 6: Architecture Zoom

- **Time:** 1:25
- **Claim class:** Implemented
- **Spoken intent:** walk from client operations through JSON-RPC, WorkflowApi,
  providers and stores, then into the graph runner and one `NodeUse` execution.
- **Primary visual:** semantic zoom through four levels rather than four
  unrelated diagrams.
- **Composition:** warm Editorial Canvas; chat hidden; the evidence receipt
  exposes concrete package or operation names without resizing the figure.
- **Evidence pointer:** thesis architecture diagrams, `docs/project_map.md`, and
  `docs/source_architecture.md`.
- **Transition:** the semantic zoom backs out into the public authoring surface.

### Scene 7: Author, Validate, Repair

- **Time:** 0:45
- **Claim class:** Implemented
- **Spoken intent:** show discovery, focused draft operations, validation
  diagnostics, repair hints, compilation, and save as one machine-operable
  loop.
- **Primary visual:** an operation sequence with one structured diagnostic and
  its repair action.
- **Composition:** warm Editorial Canvas; chat hidden; a locally dark operation
  or terminal block may occupy center while the evidence receipt updates below.
- **Evidence pointer:** CLI documentation, draft authoring API, and challenge
  UX findings.
- **Transition:** the operation block becomes the first card in the agent UI.

### Scene 8: Agent Handoff

- **Time:** 0:20
- **Claim class:** Implemented
- **Spoken intent:** "The submitted contribution is the substrate. This prepared
  agent interaction shows how a thin external interface can operate it."
- **Primary visual:** a standard AI application surface enters full-screen.
- **Composition:** source-owned light chat surface expands within the warm
  Editorial Canvas; evidence hidden.
- **Evidence pointer:** constrained demo agent design and prepared replay recipe.
- **Transition:** the operator request and first operation appear immediately.

### Scene 9: Workflow Takes the Stage

- **Time:** 0:45
- **Claim class:** Implemented
- **Spoken intent:** the prepared agent invokes the report workflow; the visible
  tool call expands into raw and interpreted operation output; the workflow
  graph becomes primary.
- **Primary visual:** operation card transforming into the report workflow
  graph.
- **Composition:** chat moves from full to rail; graph owns center; evidence
  remains collapsed.
- **Evidence pointer:** prepared recording events and
  `examples/lda_report_workflow/`.
- **Transition:** execution stops at the typed `issue_review` interrupt.

### Scene 10: Interrupt, Resume, Evidence

- **Time:** 1:30
- **Claim class:** Implemented
- **Spoken intent:** explain the typed approval contract, approve selected
  issues, resume the same run, then show the generated report, issue-board
  writes, trace frames, and raw/interpreted evidence.
- **Primary visual:** interrupt approval followed by output and trace projection.
- **Composition:** chat rail during approval, then dock; center alternates
  between interrupt, output, and trace; the centered evidence inspector opens
  once through an explicit action.
- **Evidence pointer:** deterministic replay recording, typed interrupt schemas,
  run inspect result, and trace events.
- **Failure fallback:** if the live server or operation fails, switch to the
  reviewed replay at the current semantic event without resetting the layout or
  explaining a new UI.
- **Transition:** trace frames collapse into evaluation evidence.

### Scene 11: Evaluation

- **Time:** 1:25
- **Claim class:** Evaluated
- **Spoken intent:** present the 36-trial cohort as bounded agent-operability and
  longitudinal product evidence, not a model leaderboard or broad success-rate
  estimate.
- **Primary visual:** cohort structure, audited validity, failure classes, and
  selected product improvements discovered through trials.
- **Composition:** warm Editorial Canvas; chat hidden; one chart at a time; the
  evidence receipt links to the audit/run records.
- **Evidence pointer:** thesis evaluation chapter, Appendix C, generated cohort
  figures, and challenge reports.
- **Transition:** limitations remain while the charts simplify into the final
  planner/runtime boundary.

### Scene 12: Limits and Conclusion

- **Time:** 1:00
- **Claim class:** Future work
- **Spoken intent:** distinguish implemented substrate from a future live LLM
  interface, production security, scheduling, broader model evaluation, and
  comparative studies; end on the planner/runtime separation.
- **Primary visual:** implemented core in focus, future layers around it, then
  the one-sentence thesis.
- **Composition:** warm Editorial Canvas; chat dock may remain as a
  subtle reminder that the agent is a client of the substrate.
- **Evidence pointer:** thesis limitations and future-work chapters.
- **Transition:** none; hold a stable conclusion frame for questions.

## Presenter Controls

The presenter needs a hidden or unobtrusive rehearsal surface with:

- next and previous scene;
- direct scene jump by number or hash;
- current and next speaker note;
- elapsed and planned time;
- audience progress and current Focus Path;
- motion reduction toggle;
- replay/live indicator and forced replay fallback;
- reset to the start of the current scene;
- open Q&A index.

The audience view must not expose these controls unless explicitly opened.
The same semantic control actions may later be exposed to a phone or second
device. This storyboard does not choose the remote-control transport, host, or
deployment topology.

## Discussion Branches

Discussion branches are prepared scenes outside the main timer. They attach to
the main story at semantically relevant points and return to the originating
scene and beat.

Scene 3 owns the first branch group:

- **3A Direct orchestration:** dynamic adaptation versus durable reusable
  procedure.
- **3B Generated scripts:** simplicity and debuggability versus managed
  lifecycle records.
- **3C Hosted automation:** integrations, triggers, scheduling, and operational
  maturity. A concrete future-work example may ask an agent to prepare a
  recurring workflow that starts a headless coding agent with a prompt. The
  exact command must be verified before presentation; scheduling remains
  outside the implemented lda.chat scope.
- **3D Durable agent graphs:** overlap with LangGraph-style persistence and
  human-in-the-loop execution, and the distinct artifact/deployment/source
  binding emphasis in this work.
- **3E MCP and agent-facing scale:** MCP as a capability protocol rather than a
  workflow lifecycle, plus progressive discovery, CLI surfaces, and Code Mode.
  External measurements remain explicitly attributed: Cloudflare reports
  roughly 1,000 tokens for two Code Mode tools versus 1.17 million for an
  equivalent flat MCP surface, while Anthropic reports a worked example
  reducing tool context from 150,000 to 2,000 tokens. These are external
  examples, not lda.chat measurements:
  [Cloudflare Code Mode](https://blog.cloudflare.com/code-mode-mcp/) and
  [Anthropic code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp).

Additional branch groups may attach to architecture, evaluation, and future
work, but they must follow the same claim-class and evidence-pointer rules as
the main path.

## Q&A Index

Q&A material is not the next numbered main scene. It is a separate deep-link
index that can open focused views without replaying the main story.

Required entries:

- where the AI agent is and what is actually submitted;
- Draft versus Artifact versus Deployment versus Run;
- raw-plan import versus draft authoring;
- source-provider boundary and MCP status;
- schema validation and repair hints;
- deterministic execution and reducer-aware state;
- typed interrupt and resume contract;
- persistence and recovery boundaries;
- challenge methodology and validity limits;
- security and sandboxing non-goals;
- why not direct tool calling, generated scripts, LangGraph, Temporal, or n8n;
- live demo failure and replay provenance.

Each entry should deep-link to an existing component or evidence record. Avoid a
second, disconnected slide deck.

## Chat Component Direction

The next visual slice should copy source-owned primitives from Vercel AI
Elements rather than invent another chat UI or adopt a second agent runtime.
Useful primitives include conversation scrolling, messages, Markdown response,
prompt input, and tool-call presentation.

The copied components adapt to the existing `AgentMessagePart` and
`AgentDriver` contracts. Do not adopt `useChat`, model selection, attachments,
accounts, or a complete ChatGPT shell until a live AI SDK driver exists.

The chat remains a supporting presentation surface. It must never push the
graph, approval, or evidence below the fold.

## Content and Visual Freeze

Content freezes before visual polish:

1. approve scene order, claims, evidence pointers, and spoken intent;
2. implement the compositor states and navigation;
3. replace chat primitives and establish visual tokens;
4. tune motion and final scene styling;
5. rehearse timing and revise wording without restructuring components.

This ordering prevents the presentation from becoming visually polished while
still telling the wrong story.

## Acceptance Criteria

The storyboard implementation is acceptable when:

1. all 12 main scenes are directly addressable and navigable without page
   scroll;
2. the main path fits within 12 minutes in rehearsal;
3. every factual scene has a claim class and evidence pointer;
4. external measurements are visibly attributed and never presented as
   lda.chat evaluation;
5. chat, graph, approval, output, and evidence retain stable stage geography;
6. stage and chat themes can be controlled independently;
7. live failure can fall back to the matching replay event without layout
   reset;
8. the full main path is readable from `960x720` through `1280x720` logical
   canvases with browser zoom at 100%;
9. reduced-motion mode preserves all information and controls;
10. discussion branches and the Q&A index open focused evidence and return to
    the originating scene without replaying the presentation;
11. the spoken script primarily uses personal defense voice while technical
    invariants remain precise;
12. the existing `/console` product route remains independent from cinematic
    presentation styling.

## Out of Scope

- a live general-purpose LLM planner;
- a second slide framework or Astro shell;
- a generic drag-and-drop presentation editor;
- redesigning the normal console in the presentation's cinematic style;
- reproducing every thesis diagram or code listing;
- presenting historical challenge waves as a controlled benchmark;
- adding claims merely because a visual component can display them.
