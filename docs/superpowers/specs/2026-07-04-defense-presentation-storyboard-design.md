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

The listed scene budgets total 8 minutes 54 seconds. Rehearsal should target a
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

The stage has three stable regions:

```text
+----------------+--------------------------------+----------------+
| agent / chat   | primary graph, model, output   | evidence       |
| optional       | always owns visual focus       | optional       |
+----------------+--------------------------------+----------------+
```

The regions may expand, collapse, or overlap, but they do not swap meanings.
The audience should learn the geography once.

- **Left:** agent conversation and operation intent.
- **Center:** the primary explanation, workflow graph, output, or evaluation
  result.
- **Right:** raw and interpreted evidence, trace, schemas, or source details.

Narrative scenes hide chat. Demo scenes may show chat as `full`, `rail`, or
`dock`. Evidence is collapsed unless the scene explicitly needs it.

Vertical stacking is forbidden on the main path. At `1280x720`, the presenter
must not scroll to discover the graph, approval control, output, or next action.

## Independent Presentation State

The stage and chat are independently themed and positioned:

```ts
type PresentationAppearance = {
  readonly stageTheme: "paper" | "night";
  readonly chatTheme: "light" | "dark";
  readonly chatMode: "hidden" | "full" | "rail" | "dock";
};
```

The themes are not required to match. A professional light chat may enter over
a dark cinematic stage, then collapse into a narrow rail while the graph takes
focus.

A rehearsal toolbar may override scene defaults for stage theme, chat theme,
motion, playback mode, and scene selection. It is hidden during the defense.

## Motion Contract

Motion explains changing ownership of the stage:

- chat enters as a complete application surface;
- an operation card expands from chat into the center stage;
- the workflow graph takes over while chat moves to a rail;
- a selected node expands into a spotlight without navigating away;
- evidence peeks from the right and opens only when needed;
- chat collapses to a dock after the workflow completes.

Messages appear as complete blocks with a short fade. There is no slow
typewriter simulation. Major transitions should normally complete within one
second and never exceed two seconds. Reduced-motion mode replaces spatial
movement with immediate visibility changes or short fades.

## Main Storyboard

### Scene 1: Thesis

- **Time:** 0:20
- **Claim class:** Implemented
- **Spoken intent:** "I designed and implemented lda.chat as a workflow
  substrate that external agents and human operators can use to create,
  validate, run, and inspect reusable workspace automations."
- **Primary visual:** title and one-sentence thesis.
- **Composition:** paper stage; chat hidden; no evidence panel.
- **Evidence pointer:** thesis Abstract and Introduction.
- **Transition:** the title contracts into a small persistent lda.chat mark.

### Scene 2: The Problem

- **Time:** 0:40
- **Claim class:** Motivation
- **Spoken intent:** direct agent tool calls can perform actions, but reusable
  automation also needs lifecycle state, validation, bindings, persistence,
  traceability, and recovery boundaries.
- **Primary visual:** an unstable sequence of direct tool calls contrasted with
  a durable workflow record.
- **Composition:** night stage; chat hidden.
- **Evidence pointer:** thesis problem statement and research question.
- **Transition:** scattered calls align into named system responsibilities.

### Scene 3: The Missing Middle

- **Time:** 0:35
- **Claim class:** Implemented
- **Spoken intent:** "I moved contracts and durable execution concerns out of
  the planner loop and into the platform."
- **Primary visual:** five requirements: typed contracts, lifecycle, source
  bindings, deterministic execution, and evidence.
- **Composition:** paper stage; one requirement enters at a time.
- **Evidence pointer:** thesis requirements and contribution summary.
- **Transition:** the requirements become the boundary between planner and
  runtime.

### Scene 4: Planner and Runtime

- **Time:** 0:40
- **Claim class:** Implemented
- **Spoken intent:** the external planner proposes or revises workflow
  structure; the deterministic runtime validates, executes, records, and
  resumes it.
- **Primary visual:** a two-sided planner/runtime boundary with explicit
  operations crossing it.
- **Composition:** night stage; chat hidden.
- **Evidence pointer:** thesis architecture overview and workflow API boundary.
- **Transition:** the runtime side expands into the lifecycle.

### Scene 5: Lifecycle

- **Time:** 1:00
- **Claim class:** Implemented
- **Spoken intent:** explain Draft, Artifact, Deployment, and Run as distinct
  records with different mutability and responsibility.
- **Primary visual:** lifecycle records, including both draft-save and direct
  plan-import paths into an immutable artifact.
- **Composition:** paper stage; center focus; evidence panel may show one compact
  record at a time.
- **Evidence pointer:** thesis lifecycle chapter and lifecycle explorer.
- **Transition:** selecting a deployment zooms into the runtime architecture.

### Scene 6: Architecture Zoom

- **Time:** 1:25
- **Claim class:** Implemented
- **Spoken intent:** walk from client operations through JSON-RPC, WorkflowApi,
  providers and stores, then into the graph runner and one `NodeUse` execution.
- **Primary visual:** semantic zoom through four levels rather than four
  unrelated diagrams.
- **Composition:** night stage; chat hidden; right evidence panel peeks for
  concrete package or operation names.
- **Evidence pointer:** thesis architecture diagrams, `docs/project_map.md`, and
  `docs/source_architecture.md`.
- **Transition:** the node contract narrows into progressive capability
  discovery.

### Scene 7: Scaling Agent Interfaces

- **Time:** 0:45
- **Claim class:** External context
- **Spoken intent:** large flat tool catalogs create context pressure; industry
  work increasingly uses progressive discovery and code or CLI surfaces.
- **Primary visual:** two externally attributed measurements, followed by a
  separate "lda.chat alignment" panel listing schema discovery, CLI operations,
  workflow wrappers, artifacts, and replayable runs.
- **Composition:** paper stage; external results use visibly distinct source
  labels.
- **Evidence pointer:** Cloudflare reports roughly 1,000 tokens for two Code
  Mode tools versus 1.17 million for an equivalent flat MCP surface, and
  Anthropic reports a worked example reducing tool context from 150,000 to
  2,000 tokens. These are external examples, not lda.chat measurements:
  [Cloudflare Code Mode](https://blog.cloudflare.com/code-mode-mcp/) and
  [Anthropic code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp).
- **Transition:** the alignment panel becomes lda.chat's authoring loop.

### Scene 8: Author, Validate, Repair

- **Time:** 0:45
- **Claim class:** Implemented
- **Spoken intent:** show discovery, focused draft operations, validation
  diagnostics, repair hints, compilation, and save as one machine-operable
  loop.
- **Primary visual:** an operation sequence with one structured diagnostic and
  its repair action.
- **Composition:** night stage; chat hidden; operation block in center; evidence
  peeks right.
- **Evidence pointer:** CLI documentation, draft authoring API, and challenge
  UX findings.
- **Transition:** the operation block becomes the first card in the agent UI.

### Scene 9: Agent Handoff

- **Time:** 0:20
- **Claim class:** Implemented
- **Spoken intent:** "The submitted contribution is the substrate. This prepared
  agent interaction shows how a thin external interface can operate it."
- **Primary visual:** a standard AI application surface enters full-screen.
- **Composition:** light chat full-screen over a night stage; evidence hidden.
- **Evidence pointer:** constrained demo agent design and prepared replay recipe.
- **Transition:** the operator request and first operation appear immediately.

### Scene 10: Workflow Takes the Stage

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

### Scene 11: Interrupt, Resume, Evidence

- **Time:** 1:30
- **Claim class:** Implemented
- **Spoken intent:** explain the typed approval contract, approve selected
  issues, resume the same run, then show the generated report, issue-board
  writes, trace frames, and raw/interpreted evidence.
- **Primary visual:** interrupt approval followed by output and trace projection.
- **Composition:** chat rail during approval, then dock; center alternates
  between interrupt, output, and trace; right evidence panel opens once.
- **Evidence pointer:** deterministic replay recording, typed interrupt schemas,
  run inspect result, and trace events.
- **Failure fallback:** if the live server or operation fails, switch to the
  reviewed replay at the current semantic event without resetting the layout or
  explaining a new UI.
- **Transition:** trace frames collapse into evaluation evidence.

### Scene 12: Evaluation

- **Time:** 1:25
- **Claim class:** Evaluated
- **Spoken intent:** present the 36-trial cohort as bounded agent-operability and
  longitudinal product evidence, not a model leaderboard or broad success-rate
  estimate.
- **Primary visual:** cohort structure, audited validity, failure classes, and
  selected product improvements discovered through trials.
- **Composition:** paper stage; chat hidden; one chart at a time; evidence panel
  links to the audit/run records.
- **Evidence pointer:** thesis evaluation chapter, Appendix C, generated cohort
  figures, and challenge reports.
- **Transition:** limitations remain while the charts simplify into the final
  planner/runtime boundary.

### Scene 13: Limits and Conclusion

- **Time:** 1:00
- **Claim class:** Future work
- **Spoken intent:** distinguish implemented substrate from a future live LLM
  interface, production security, scheduling, broader model evaluation, and
  comparative studies; end on the planner/runtime separation.
- **Primary visual:** implemented core in focus, future layers around it, then
  the one-sentence thesis.
- **Composition:** night stage returning to paper; chat dock may remain as a
  subtle reminder that the agent is a client of the substrate.
- **Evidence pointer:** thesis limitations and future-work chapters.
- **Transition:** none; hold a stable conclusion frame for questions.

## Presenter Controls

The presenter needs a hidden or unobtrusive rehearsal surface with:

- next and previous scene;
- direct scene jump by number or hash;
- current and next speaker note;
- elapsed and planned time;
- stage-theme and chat-theme overrides;
- motion reduction toggle;
- replay/live indicator and forced replay fallback;
- reset to the start of the current scene;
- open Q&A index.

The audience view must not expose these controls unless explicitly opened.

## Q&A Index

Q&A material is not scene 14. It is a separate deep-link index that can open
focused views without replaying the main story.

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

1. all 13 scenes are directly addressable and navigable without page scroll;
2. the main path fits within 12 minutes in rehearsal;
3. every factual scene has a claim class and evidence pointer;
4. external measurements are visibly attributed and never presented as
   lda.chat evaluation;
5. chat, graph, approval, output, and evidence retain stable stage geography;
6. stage and chat themes can be controlled independently;
7. live failure can fall back to the matching replay event without layout
   reset;
8. the full main path is readable at `1280x720` with browser zoom at 100%;
9. reduced-motion mode preserves all information and controls;
10. the Q&A index opens focused evidence without replaying the presentation;
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
