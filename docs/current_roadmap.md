# Current Roadmap

This is the live, short roadmap. Completed implementation plans and long slice
history live under [`historical/`](historical/). Current architecture references:

- [`wf_api_architecture.md`](wf_api_architecture.md): workflow API, server,
  transport, and source package boundaries.
- [`project_map.md`](project_map.md): package map and entrypoints.
- [`wf_cli.md`](wf_cli.md): current CLI usage.

## Current Product Shape

```text
wf_cli
  -> local WorkflowApi or wf_transport_rpc_http.RpcWorkflowApiClient
  -> wf_server.WorkflowServer
  -> wf_api.WorkflowApi / admin surfaces
  -> wf_core / wf_artifacts / wf_sources_mcp
```

The durable product path is now `wf-rpc-server` plus neutral `wf_config` /
`wf_server` composition. The old `wf-mcp` script remains a legacy/special-purpose
MCP entrypoint and compatibility surface.

## Active Initiative: Workflow Console And Defense Demo

The next product-facing push is a local-first web console and defense demo that
shows the lifecycle without forcing viewers to read raw JSON. It connects to a
loopback `wf-rpc-server` through JSON-RPC, displays lifecycle records and traces,
and runs a prepared `lda.chat` report workflow with a typed human approval
interrupt.

Design contracts:

- [`workflow console, agent demo, and defense presentation`](superpowers/specs/2026-07-01-workflow-console-agent-demo.md)
- [`self-describing interrupt contracts`](superpowers/specs/2026-07-01-self-describing-interrupt-contracts.md)
- [`workflow console lifecycle explorer`](superpowers/specs/2026-07-02-workflow-console-lifecycle-explorer.md)
- [`demo autoplay and replay`](superpowers/specs/2026-07-03-demo-autoplay-replay.md)
- [`defense presentation storyboard`](superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md)
- [`adaptive presentation canvas and evidence inspector`](superpowers/specs/2026-07-05-adaptive-presentation-canvas-design.md)
- [`Scene 10 guided product moment`](superpowers/specs/2026-07-09-scene-10-guided-product-moment-design.md)
- [`presentation live/replay truth`](superpowers/specs/2026-07-09-presentation-live-replay-truth-design.md)
- [`presentation lifecycle story expansion`](superpowers/specs/2026-07-09-presentation-lifecycle-story-expansion-design.md)
- [`presentation opening visuals`](superpowers/specs/2026-07-10-presentation-opening-visuals-design.md)
- [`presentation evaluation and closing`](superpowers/specs/2026-07-10-presentation-evaluation-closing-design.md)

Implementation order:

1. Completed: self-describing interrupt request/resume schemas are carried
   through core execution, persisted run inspection, and resume validation.
2. Completed: deterministic `examples/lda_report_workflow/` case study with
   local document, report, issue-board sources, and typed issue-review
   interrupt.
3. Completed: add a top-level `web/` pnpm workspace with a React/Vite console,
   Hono local server, Effect JSON-RPC boundary, loopback connection flow,
   source inventory, protocol evidence, and production static serving. Design:
   [`workflow console foundation`](superpowers/specs/2026-07-01-workflow-console-foundation-design.md).
   Implementation:
   [`workflow console foundation plan`](historical/superpowers/plans/2026-07-02-workflow-console-foundation.md).
4. Completed: add the generic console lifecycle explorer, exercised first through
   the artifact -> deployment -> run -> trace path, with interactive graph and raw
   RPC evidence. Design:
   [`workflow console lifecycle explorer`](superpowers/specs/2026-07-02-workflow-console-lifecycle-explorer.md).
   Implementation:
   [`workflow console lifecycle explorer plan`](historical/superpowers/plans/2026-07-02-workflow-console-lifecycle-explorer.md).
   Draft workspace inspection reuses the same shell after the first vertical
   path.
5. Completed: the web console can operate the prepared
   `examples/lda_report_workflow/` deployment through run start, typed
   `issue_review` interrupt, resume, trace, and final output inspection.
6. Completed: lifecycle autoplay, typed approval, issue-board output, and replay.
   Design:
   [`demo autoplay and replay`](superpowers/specs/2026-07-03-demo-autoplay-replay.md).
   Implementation:
   [`demo autoplay and replay plan`](historical/superpowers/plans/2026-07-03-demo-autoplay-replay.md).
7. Completed: React presentation mode foundation for the prepared workflow demo.
   Make the report workflow story primary, demote lifecycle evidence to
   supporting panels, and keep the layout usable on a 720p display. Decision:
   [`React presentation mode before Astro`](adr/0003-react-presentation-mode-before-astro.md).
   Design:
   [`React presentation mode`](superpowers/specs/2026-07-03-react-presentation-mode-design.md).
   Implementation:
   [`React presentation mode plan`](historical/superpowers/plans/2026-07-03-react-presentation-mode.md).
8. Completed: constrained demo agent that invokes one prepared recipe macro.
   Live mode is deferred to a future slice; the prepared driver is replay-only
   for now.
   Design:
   [`constrained demo agent`](superpowers/specs/2026-07-03-constrained-demo-agent-design.md).
   Implementation:
   [`constrained demo agent plan`](historical/superpowers/plans/2026-07-03-constrained-demo-agent.md).
9. Completed: implement the approved 12-scene defense storyboard as a no-scroll
   720p compositor. Content and evidence freeze before chat replacement, visual
   polish, or motion tuning. Design:
   [`defense presentation storyboard`](superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md).
   Implementation:
   [`defense storyboard compositor plan`](historical/superpowers/plans/2026-07-04-defense-storyboard-compositor.md).
10. Completed: make the workflow execution handoff the visual center of Scenes
    9 and 10. The canonical replay now drives an interpreted operation surface,
    persistent execution graph, typed interrupt contract, and raw evidence
    drawer. Design:
    [`workflow takes the stage`](historical/superpowers/specs/2026-07-05-workflow-takes-stage-visual-design.md).
    Implementation:
    [`workflow takes the stage plan`](historical/superpowers/plans/2026-07-05-workflow-takes-stage-visual.md).
11. Completed: replace whole-stage theme switching with one scalable Editorial
    Canvas and prove the reusable recursive Interactive Figure through Scene 6.
    Design:
    [`defense presentation storyboard`](superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md).
    Implementation:
    [`editorial canvas and Interactive Figure plan`](historical/superpowers/plans/2026-07-05-editorial-canvas-interactive-figure.md).
12. Completed: adapt the logical presentation canvas continuously from `4:3` to
    `16:9` and replace the resizing evidence drawer with a progress-row receipt
    and centered inspector. Design:
    [`adaptive presentation canvas and evidence inspector`](superpowers/specs/2026-07-05-adaptive-presentation-canvas-design.md).
    Implementation:
    [`adaptive presentation canvas plan`](historical/superpowers/plans/2026-07-06-adaptive-presentation-canvas.md).
13. Completed: address the presentation CodeRabbit review pass covering
    reducer state semantics, agent approval cleanup, discussion modal
    accessibility, figure validation, keyboard roving focus, and stale demo
    agent spec wording. Implementation:
    [`presentation CodeRabbit fixes`](historical/superpowers/plans/2026-07-08-presentation-coderabbit-fixes.md).
14. Completed: presentation chat uses source-owned AI Elements-style
    conversation, message, tool, and prompt-action primitives against existing
    `AgentMessagePart` / `TimelineAgent` contracts. Live AI SDK driver remains
    deferred; the current chat runs the deterministic timeline agent.
    Implementation:
    [`presentation AI chat surface`](historical/superpowers/plans/2026-07-09-presentation-ai-chat-surface.md).
15. Completed: schema approval surface for typed interrupt/resume decisions.
    Scene 10 and prepared-agent approval requests now render schema/payload
    approval UI instead of raw `{ "type": "object" }` as the primary product
    proof. Implementation:
    [`schema approval surface`](historical/superpowers/plans/2026-07-09-schema-approval-surface.md).
16. Completed: presentation chat now drives the prepared workflow timeline.
    The chat run action, schema approval submit/revision, graph, evidence, and
    live/replay execution all share `useDemoTimeline`; AI SDK remains a later
    driver for the same seam. Implementation:
    [`presentation chat timeline bridge`](historical/superpowers/plans/2026-07-09-presentation-chat-timeline-bridge.md).
17. Completed: guided run beat gates connect Scene 10 schema approval, chat
    approval, graph focus, and evidence transitions into one deterministic
    presenter sequence. Implementation:
    [`guided run beat gates`](historical/superpowers/plans/2026-07-09-guided-run-beat-gates.md).
18. Completed: Scene 10 guided product moment primes replay state for direct
    hashes and stages approval, resume, output, and trace as one readable
    product flow. Design:
    [`Scene 10 guided product moment`](superpowers/specs/2026-07-09-scene-10-guided-product-moment-design.md).
    Implementation:
    [`Scene 10 guided product moment plan`](historical/superpowers/plans/2026-07-09-scene-10-guided-product-moment.md).
19. Completed: presentation live/replay truth surface distinguishes reviewed
    replay evidence, live target readiness, live active run state, and replay
    fallback. Design:
    [`presentation live/replay truth`](superpowers/specs/2026-07-09-presentation-live-replay-truth-design.md).
    Implementation:
    [`presentation live/replay truth plan`](historical/superpowers/plans/2026-07-09-presentation-live-replay-truth.md).
20. Completed: Scene 10 now presents factual run state: workflow input,
    interrupt payload, operator resume decision, output, and trace frame facts.
    The live workflow contract supports a same-run negative outcome; the
    current prepared revision recording uses a separate run identity and is
    documented as a factual follow-up. Implementation:
    [`Scene 10 factual run state`](historical/superpowers/plans/2026-07-09-scene-10-factual-run-state.md).
21. Completed: presentation lifecycle story expansion splits the demo climax
    into prepared lifecycle, run start, typed human boundary, and
    resume/output/evidence scenes so Draft -> Artifact -> Deployment -> Run is
    visible before the run inspector details. Design:
    [`presentation lifecycle story expansion`](superpowers/specs/2026-07-09-presentation-lifecycle-story-expansion-design.md).
    Implementation:
    [`presentation lifecycle story expansion plan`](historical/superpowers/plans/2026-07-09-presentation-lifecycle-story-expansion.md).
22. Completed: presentation demo proof composition makes scenes 9-12 factual
    and readable: the workflow graph reflects the prepared plan, approval
    shows input/interruption/decision only, and resume/output/trace expose
    scroll-contained proof panes. Implementation:
    [`presentation demo proof composition`](historical/superpowers/plans/2026-07-09-presentation-demo-proof-composition.md).
23. Future: presenter companion and defense evidence assets.
24. Add a static slide/appendix shell only after presentation mode is clear.
    Astro remains an option, not the default next surface.
25. Completed: presentation agent authoring story creates a canonical prepared
    authoring recording, Scene 8 as an authentic single-beat full-screen
    conversation, and Scene 9 as a 5-phase lifecycle with route-level coverage
    that never calls workflow authoring RPC operations during Scene 9
    navigation. Implementation:
    [`presentation agent authoring story`](historical/superpowers/plans/2026-07-11-presentation-agent-authoring-story.md).
26. Completed: compress Scene 11 typed approval and Scene 12 resume/output/trace
    evidence into a decision-led, continuation-led presentation, and restore
    live prepared-run activation against the configured JSON-RPC target.
    Implementation plan:
    [`Scene 11-12 evidence and live activation`](historical/superpowers/plans/2026-07-11-scene-11-12-live-evidence.md).

Presentation visual audit, July 11:

- Baseline-good: Scenes 3, 4, and 5 are good enough for now. Do not churn them
  unless a later rehearsal exposes a concrete problem.
- Completed: Scene 1 introduces the agent-shaped product goal through
  `Planner -> Tool surface -> Runner / platform`, then identifies the last
  role as the implemented contribution. Scene 2 remains responsible for the
  automation problem. Scenes 2, 6, and 7 retain their concrete focal artifacts,
  and Scenes 8-10 share a prepared authoring/run spine. Implementation:
  [`presentation opening title`](historical/superpowers/plans/2026-07-11-presentation-opening-title.md).
- Completed: Scenes 11-12 now use decision-led approval, continuation-led
  resume/output, and compact factual trace rows so approval, resume, output,
  and trace remain factual without competing panels or repeated low-signal
  values. A healthy prepared target remains live; failed health probes switch
  the presentation back to the offline recording.
- Completed: Scenes 13 and 14 now close with a bounded evaluation board,
  contribution boundary/future-work map, and canonical defense-question index.

## Completed: Presentation Recomposition And Authoring Story

Scenes 8 and 9 are now implemented as authentic external-agent request and
factual prepared-authoring proof. Scene 8 is one local request-to-first-turn
beat; its obsolete `/handoff` route fails closed. Scene 9 keeps a persistent
prepared assistant pane beside five factual phase visuals in an adaptive
approximately 35/65 split. The obsolete receipt/trace modal and lower chat dock
were removed. Plans:
[`presentation agent authoring story`](historical/superpowers/plans/2026-07-11-presentation-agent-authoring-story.md)
and
[`Scene 9 assistant pane`](historical/superpowers/plans/2026-07-12-scene-9-assistant-modal.md).
The staged message-box completion is recorded in
[`Scene 9 staged message box`](historical/superpowers/plans/2026-07-12-scene-9-staged-message-box.md).

Recommended next visual slices:

1. Completed: Opening visuals rebuilt Scenes 1 and 2 around concrete diagrams
   for "AI-agent pursuit -> workflow substrate" and "direct actions are not
   reusable automation". Design:
   [`presentation opening visuals`](superpowers/specs/2026-07-10-presentation-opening-visuals-design.md).
   Implementation:
   [`presentation opening visuals plan`](historical/superpowers/plans/2026-07-10-presentation-opening-visuals.md).
2. Completed: Presentation coherence pass added a 14-scene visual matrix,
   corrected Scene 2's direct-action metaphor into a chat/tool transcript, and
   marked demo beats with primary/support surface metadata so Scenes 8-12 can
   keep one dominant product proof at a time. Implementation:
   [`presentation coherence pass`](historical/superpowers/plans/2026-07-10-presentation-coherence-pass.md).
3. Completed: Scene 2 visual craft pass made the one-off side read as a
   chat/tool transcript and the reusable side read as a durable workflow
   blueprint, while preserving simple vocabulary and 720p readability.
   Implementation:
   [`Scene 2 tool-loop visual craft`](historical/superpowers/plans/2026-07-10-scene-2-tool-loop-visual-craft.md).
4. Completed: guided proof scene composition cleanup made approval, resume,
   output, and trace beats read as product evidence without chat competing for
   space. Implementation:
   [`guided proof scene composition cleanup`](historical/superpowers/plans/2026-07-10-guided-proof-scene-composition-cleanup.md).
5. Completed: Evidence and closing visuals make Scenes 13 and 14 readable as a
    defense artifact: bounded evaluation board, claim boundaries, future-work
    map, and canonical examiner-question index. Design:
    [`presentation evaluation and closing`](superpowers/specs/2026-07-10-presentation-evaluation-closing-design.md).
    Implementation:
    [`presentation evaluation and closing plan`](historical/superpowers/plans/2026-07-10-presentation-evaluation-closing.md).
6. Completed: Presentation agent authoring story rebuilds Scenes 8 and 9 as
    authentic external-agent handoff and factual prepared-authoring proof.
    Implementation:
    [`presentation agent authoring story plan`](historical/superpowers/plans/2026-07-11-presentation-agent-authoring-story.md).
7. Completed: Scene 1 now introduces the agent-shaped product goal through
   `Planner -> Tool surface -> Runner / platform`, then identifies the last role
   as the implemented contribution. Scene 2 remains responsible for the
   automation problem. Implementation:
   [`presentation opening title`](historical/superpowers/plans/2026-07-11-presentation-opening-title.md).
8. Completed: harden the live/replay defense rehearsal path with visible live
   start readiness, submitted and revision-requested outcome evidence,
   deterministic replay fallback, current deep links, and reset instructions.
   The live contract is same-run; the prepared revision branch uses a separate
   recording and is disclosed in the rehearsal log.
   Implementation:
   [`defense presentation rehearsal`](historical/superpowers/plans/2026-07-12-defense-presentation-rehearsal.md).
9. Completed: Scenes 7-9 now use one dominant factual artifact per beat on the
   Editorial Canvas: authoring/repair evidence, an authentic light agent chat,
   and a light prepared lifecycle canvas with synchronized secondary chat.
   Implementation:
   [`Scenes 7-9 editorial focal proof`](historical/superpowers/plans/2026-07-12-scenes-7-9-editorial-focal-proof.md).
10. Next: revise the remaining visual outliers only when a screenshot identifies
    a concrete hierarchy, overflow, or factual-readability problem.

## Next: Scene 8–14 Defense Recomposition

The next presentation work is intentionally split into six implementation
slices followed by a rehearsal gate. The broader story-flow review remains a
separate activity after these surfaces are stable.

1. **Completed: Scene 8 chat entry:** replaced the standalone run button with
   a full-screen assistant-style chat entry. The local composer/send action
   reveals the first prepared authoring conversation without starting a
   workflow run. Implementation:
   [`Scene 8 chat entry`](historical/superpowers/plans/2026-07-12-scene-8-chat-entry.md).
2. **Completed: Scene 9 staged message box:** kept one message box visible
   across Discover, Draft, Validate, Artifact, and Deployment; Draft and
   Artifact Send advance the prepared lifecycle while preserving edited user
   turns, and Deployment Send records a truthful local run request without
   execution or RPC. Implementation:
   [`Scene 9 staged message box`](historical/superpowers/plans/2026-07-12-scene-9-staged-message-box.md).
   The boundary is explicit: Scenes 10–12 own run activation, approval,
   resume, output, and trace evidence.
3. **Completed: Live/replay truth and run activation:** Scene 10 exposes the
   prepared-run action outside the hidden chat, retries the existing health
   probe, starts live execution explicitly, and keeps direct links and failed
   services on truthful replay evidence. Implementation:
   [`presentation live/replay activation`](historical/superpowers/plans/2026-07-12-presentation-live-replay-activation.md).
4. **Completed: Scene 11 compression:** reduce the typed-human-boundary scene to two
   beats: interrupt context and approval decision. Cancellation remains a
    decision outcome rather than a near-duplicate presentation beat.
   Implementation plan:
   [`Scene 11 decision beat compression`](historical/superpowers/plans/2026-07-12-scene-11-decision-beat-compression.md).
5. **Completed: Scene 10 factual proof and graph composition:** the factual
   graph, selected input files, and proof layout are now implemented. The
   completed plan is [`Scene 10 factual graph and proof layout`](historical/superpowers/plans/2026-07-12-scene-10-factual-graph-and-proof-layout.md).
   File-preview rendering remains explicitly deferred as a separate follow-up.
6. **Completed: presentation demo-chrome ownership:** Scenes 8–12 share one
   route-projected footer rail for run, replay fallback, retry, paused, and
   terminal states. Design:
   [`presentation demo-chrome ownership`](superpowers/specs/2026-07-12-demo-chrome-ownership-design.md).
   Implementation:
   [`presentation demo-chrome ownership plan`](historical/superpowers/plans/2026-07-12-presentation-demo-chrome-ownership.md).
7. **Completed: visual scale and color pass:** removed unwanted blue from Scenes 2 and 14,
   shorten Scene 2's two-column composition, enlarge the focal diagrams in
   Scenes 7, 9, 13, and 14, separate Scene 7 Validate from Repair visuals, and
   improve Scene 1 title-box padding and contrast. Design:
   [`presentation visual scale and color pass`](superpowers/specs/2026-07-12-presentation-visual-scale-color-pass-design.md).
   Implementation:
   [`presentation visual scale and color pass plan`](historical/superpowers/plans/2026-07-12-presentation-visual-scale-color-pass.md).
8. **Completed: defense rehearsal gate:** all 14 scenes have paired `1280x720`
   and `1024x768` replay captures, and the rehearsal matrix, log, and story
   audit are recorded. The live end-to-end path remains blocked, the prepared
   revision branch has a separate recorded run identity, and the full web test
   gate passes after route-contract stabilization. Historical implementation plan:
   [`defense rehearsal gate`](historical/superpowers/plans/2026-07-13-defense-rehearsal-gate.md).
   Route matrix: [`presentation rehearsal matrix`](runbooks/presentation-rehearsal-matrix.md);
   Story-flow audit: [`presentation story audit`](runbooks/presentation-story-audit.md);
   dated evidence: [`presentation rehearsal log`](runbooks/presentation-rehearsal-log.md).

9. **Deferred: factual input file browser:** replace the Scene 10 input
   manifest-only view with a read-only browser backed by canonical prepared or
   live run facts. Distinguish declared, selected, read, and produced files;
   do not imply file reads without evidence.

10. **Active plan: presentation follow-up visual/story pass:** clarify Scene 1
    and the lifecycle-to-authoring narrative, give Scenes 7 and 9 a stronger
    dominant artifact, make the Scene 10 graph easier to present, and densify
    Evaluation and Conclusion beats without inventing evidence.
    Implementation plan:
    [`presentation follow-up visual/story pass`](superpowers/plans/2026-07-13-presentation-followup-visual-story-pass.md).

Presentation wishlist / defense readiness:

- Completed: visual pass for Scenes 6, 7, and 10 fixed architecture figure
  scale, authoring-loop clarity, interrupt/evidence emphasis, and presenter-note
  treatment. Implementation:
  [`defense presentation visual pass`](historical/superpowers/plans/2026-07-08-defense-presentation-visual-pass.md).
- Next presentation visual slices:
  1. Completed: contrast and readability fix pass repaired dark-on-dark text in
     the Scene 7 authoring loop and the Scene 10 chat rail, and ignored local
     `.visual-smoke/` screenshots. Implementation:
     [`presentation contrast readability`](historical/superpowers/plans/2026-07-08-presentation-contrast-readability.md).
  2. Completed: surface theme normalization pass made light chat, discussion
     modals, and Q&A branches use the same editorial presentation surface.
     Implementation:
     [`presentation surface theme normalization`](historical/superpowers/plans/2026-07-08-presentation-surface-theme-normalization.md).
   3. Completed: scene composition pass expanded the positioning map,
      planner/runtime boundary, lifecycle rail, and Scene 10 demo
      graph/contract readability. Implementation:
      [`presentation scene composition`](historical/superpowers/plans/2026-07-08-presentation-scene-composition.md).
   4. Completed: alignment/layout polish fixed Scene 6 figure dimensions,
      settled React Flow fitting, Scene 3 chip/evidence collision, narrow
      chat rail behavior, and Scene 10 smoke route. Implementation:
      [`presentation alignment and layout polish`](historical/superpowers/plans/2026-07-08-presentation-alignment-layout-polish.md).
   5. Completed: demo climax craft pass made Scenes 9 and 10 read as one
      continuous product demonstration from agent handoff, to persisted run, to
      typed interrupt, to resume/output/evidence. Implementation:
      [`demo climax craft pass`](historical/superpowers/plans/2026-07-08-demo-climax-craft-pass.md).
   6. Completed: demo product proof layout pass hid chat during graph-heavy
      beats, kept workflow graph nodes in frame, added run-proof labels inside
      the graph, and cleared outcome panels below the receipt row. Implementation:
      [`demo product proof layout`](historical/superpowers/plans/2026-07-09-demo-product-proof-layout.md).
   7. Completed: demo interrupt layout focus pass made approval/interrupt beats
      contract-first, reduced the graph to compact context where appropriate,
      and removed the remaining three-column crowding. Implementation:
      [`demo interrupt layout focus`](historical/superpowers/plans/2026-07-09-demo-interrupt-layout-focus.md).
    8. Completed: discussion craft pass replaced detached branch chips with a
       presenter question rail and rebuilt Q&A modals around answer,
       provenance, and presenter-note hierarchy. Implementation:
       [`presentation discussion craft`](historical/superpowers/plans/2026-07-09-presentation-discussion-craft.md).
   9. Completed: discussion modal composition pass made Q&A and context-only
      routes stage-aware, with body/support/action regions instead of plain
      document cards. Implementation:
      [`presentation discussion modal composition`](historical/superpowers/plans/2026-07-09-presentation-discussion-modal-composition.md).
   10. Completed: Scene 10 guided product moment primes replay state for direct
        hashes and stages approval, resume, output, and trace as one readable
        product flow. Design:
        [`Scene 10 guided product moment`](superpowers/specs/2026-07-09-scene-10-guided-product-moment-design.md).
        Implementation:
        [`Scene 10 guided product moment plan`](historical/superpowers/plans/2026-07-09-scene-10-guided-product-moment.md).
11. Completed: presentation demo proof composition makes scenes 9-12 factual
        and readable: the workflow graph reflects the prepared plan, approval
        shows input/interruption/decision only, and resume/output/trace expose
        scroll-contained proof panes. Implementation:
        [`presentation demo proof composition`](historical/superpowers/plans/2026-07-09-presentation-demo-proof-composition.md).
    12. Completed: hardened the replay/live evidence handoff so the trace beat
        consistently renders canonical frames without stale or empty state.
        Implementation:
        [`presentation evidence handoff`](historical/superpowers/plans/2026-07-11-presentation-evidence-handoff.md).
   13. Completed: deck hierarchy pass gave Scenes 1, 2, 6, 7, 8-12, and 13-14
       one focal artifact per beat, reused factual authoring/demo projections,
       kept one editorial canvas, and froze Scenes 3-5. Implementation:
       [`defense deck hierarchy pass`](historical/superpowers/plans/2026-07-11-defense-deck-hierarchy-pass.md).
- Presenter runbook:
  [`defense presentation runbook`](runbooks/defense-presentation.md) covers
  exact URLs, keyboard controls, live RPC/demo fallback steps, story spine,
  timing, and short speaker notes for what to say if the live demo fails.
- Defense Q&A branch set:
  [`defense Q&A runbook`](runbooks/defense-qna.md) collects answers for
  "Where is the AI agent?", evaluation validity, security boundaries, demo
  reliability, and other likely examiner questions. Completed projection into
  `/present` discussion branches:
  [`defense Q&A branch projection`](historical/superpowers/plans/2026-07-08-defense-qna-branch-projection.md).
- Chat surface replacement: make the prepared demo agent feel operable from a
  real chat surface, not from custom slide chrome. The chat should own the
  "run prepared agent" affordance, render tool calls/results with a standard
  modern AI-app vocabulary, and expose approval requests as normal chat events
  that can also drive presentation actions.
- Completed: guided run beat gates connect Scene 10 schema approval, chat
  approval, graph focus, and evidence transitions into one deterministic
  presenter sequence. Implementation:
  [`guided run beat gates`](historical/superpowers/plans/2026-07-09-guided-run-beat-gates.md).
- Completed: Scene 10 guided product moment removes delayed direct-link readiness
  and gives approval, resume, output, and trace one dominant proof surface each.
  Design:
  [`Scene 10 guided product moment`](superpowers/specs/2026-07-09-scene-10-guided-product-moment-design.md).
  Implementation:
  [`Scene 10 guided product moment plan`](historical/superpowers/plans/2026-07-09-scene-10-guided-product-moment.md).
- Completed: presentation lifecycle story expansion makes the demo climax less
  run-only by adding explicit prepared lifecycle scenes before the run,
  interrupt, output, and trace proof. Design:
  [`presentation lifecycle story expansion`](superpowers/specs/2026-07-09-presentation-lifecycle-story-expansion-design.md).
  Implementation:
  [`presentation lifecycle story expansion plan`](historical/superpowers/plans/2026-07-09-presentation-lifecycle-story-expansion.md).
- Evidence assets and rehearsal timing: prepare fallback screenshots/recordings,
  expected run states, and a timed walkthrough checklist for a 15-minute defense.
- Presenter companion feasibility: decide whether phone/laptop control is local
  only, same-network, or out-of-network; defer implementation until the core
  presentation is stable.

Boundaries: this is not a production admin panel, generic visual workflow
editor, scheduler, external Google Drive/mail integration, or benchmark evidence
for free-form autonomous planning.

## Priority 1: Product Smoke And Status UX

The platform is usable enough to test as a product. Next work should focus on
clear operator feedback before adding more architecture.

- Completed: `wf status` is a compact read-only target/server status command,
  including durable run counts and the latest run summary when available.
- Completed: a real CLI smoke pass against `wf-rpc-server --config wf.config.json`
  is captured in
  [`2026-06-09 product smoke RPC CLI`](superpowers/research/2026-06-09-product-smoke-rpc-cli.md).
- Completed: `wf artifact inspect` now accepts `--version` as an alias for the
  positional version argument.
- Completed: `wf artifact delete <artifact_id> <version> --confirm` deletes
  unreferenced artifact versions and rejects versions still referenced by
  deployments. Implementation:
  [`wf artifact delete`](historical/superpowers/plans/2026-06-09-wf-artifact-delete.md).
- Completed: `wf draft delete <workspace_id> --confirm` exposes existing draft
  workspace deletion as a safe CLI command. Implementation:
  [`wf draft delete CLI/RPC`](historical/superpowers/plans/2026-06-09-wf-draft-delete-cli-rpc.md).
- Completed: bounded RPC CLI smoke runbook with cleanup commands:
  [`RPC CLI smoke runbook`](runbooks/rpc-cli-smoke.md).
- Completed: automated RPC CLI smoke example:
  [`RPC CLI smoke example`](historical/superpowers/plans/2026-06-09-rpc-cli-smoke-example.md).
- Completed: `cap call` output is safer for humans through compact/text modes
  without changing default JSON semantics. Implementation:
  [`cap call output safety`](historical/superpowers/plans/2026-06-09-cap-call-output-safety.md).
- Completed: raw JSON/YAML workflow plans can be turned into artifacts through
  JSON-RPC and `wf artifact create-from-plan`, allowing agent/evidence harnesses
  to use the product-facing CLI path.
- Completed: the opencode browser-click challenge harness is local-first via
  `wf --config examples/browser_click_workflow/wf.config.json --local`, with
  optional `--start-server` / `--server-url` modes for JSON-RPC-path trials.
- Completed: focused draft edit helpers are exposed through RPC/CLI, and
  `wf deploy create` is accepted as an alias for `wf deploy save`. Docs now
  distinguish draft shape from raw plan shape for agent authoring.
- Completed: `wf draft set-input` and `wf draft set-output` now accept
  `--merge`, preserving existing bindings when agents split map edits across
  multiple revisions.
- Completed: `wf schema` now lists workflow document/component models, emits
  compact JSON outlines for agent discovery, and emits valid self-contained
  JSON Schema with `--verbose`.
- Completed: `wf draft bind --from ... --to ...` composes input/state/output
  schema projection with step binding merge, replacing the prior narrower
  output-to-state helper and reducing manual draft patch repairs in agent
  challenge runs.
- Completed: draft CLI vocabulary now uses `wf draft create --capability` and
  `wf draft add-step --capability`, replacing the longer
  `*-from-capability` commands that agents repeatedly guessed around.
- Completed: `wf draft add-step` inserts one explicit
  capability-backed step with route, input, and output-to-state schema/binding
  wiring in a single revision, reducing brittle JSON Patch authoring for
  multi-step workflows. Accepts `--route OUTCOME=TARGET` for multi-outcome steps.
- Completed: `wf draft branch` and `wf draft handle` provide atomic route
  editing for existing draft steps without rewriting the full routes object.
- Completed: `wf draft compile` returns the compiled raw plan plus required
  capabilities without mutating or saving the draft workspace.
- Completed: draft validation now preserves structured core validation issues
  and adds exact `wf draft bind` repair hints for missing state fields.
- Completed: `wf explain` now covers draft/workflow validation codes such as
  `unknown_edge_destination`, `invalid_source_path`, and `patch_invalid`.
  Implementation plan:
  [`draft explain diagnostics`](historical/superpowers/plans/2026-06-28-explain-draft-diagnostics.md).
- Completed: draft workspaces can persist invalid intermediate route states,
  allowing agents to add missing target steps before final validation/save.
  Implementation:
  [`invalid intermediate draft authoring`](historical/superpowers/plans/2026-06-28-draft-invalid-intermediate-authoring.md).
- Completed: draft workspaces expose focused remove commands for routes, steps,
  and step bindings so agents can recover from bad edits without raw JSON Patch.
  Implementation:
  [`draft remove commands`](historical/superpowers/plans/2026-06-28-draft-remove-commands.md).
- Completed: `wf draft set-workflow-output` and full-stack API/RPC/CLI support
  for editing top-level workflow output bindings. Accepts repeatable `--map`
  and `--merge` flag. Implementation:
  [`set-workflow-output API/RPC/CLI`](historical/superpowers/plans/2026-06-29-set-workflow-output.md).
- Completed: challenge-driven output UX polish makes `set-workflow-output`
  project missing top-level output schema fields from declared `input.*` and
  `state.*` sources, and challenge prompt templates now always include
  `ux_issues_found: []` so debug-profile reports do not fail by omission.
- Completed: `wf draft bind` now reuses existing workflow input/state schema
  fields when binding to step-local inputs, avoiding redundant-schema failures
  found by debug challenge runs. Implementation:
  [`idempotent draft bind inputs`](historical/superpowers/plans/2026-06-29-idempotent-draft-bind-inputs.md).
- Keep status read-only; do not mutate registry, auth, config, or stores.

## Priority 2: Durable Run/Resume Hardening

The v1 durable run and resume path exists, including persisted interrupted runs,
bounded trace reads, dependency revalidation, and process-rebuild resume tests.
Remaining hardening should focus on correctness under real server use.

- Completed: same-process `resume_run` calls are serialized per run id.
  Implementation:
  [`resume run concurrency guard`](historical/superpowers/plans/2026-06-09-resume-run-concurrency-guard.md).
- Completed: store-level locking/transaction expectations are documented for
  current file stores and future transactional stores:
  [`store transaction boundary`](superpowers/specs/2026-06-09-store-transaction-boundary.md).
- Completed: paged `wf run list` exposes compact persisted stopped-run
  summaries without trace or checkpoint state. Implementation:
  [`run list API/RPC/CLI`](historical/superpowers/plans/2026-06-11-run-list-api-rpc-cli.md).
- Preserve existing semantics: broken pinned dependencies return blocked
  readiness and diagnostics; ordinary live tool/source failures are failed runs,
  not implicit pauses.
- Active specs:
  - [`persisted run/resume contract`](superpowers/specs/2026-06-03-persisted-run-resume-contract.md)
  - [`durable workflow runs and resume`](superpowers/specs/2026-05-26-durable-workflow-runs-and-resume-design.md)

## Priority 3: Source/Auth/Config Polish

Source registry, neutral MCP source config, role-specific stores, and local/dev
auth admin are implemented. The next work is polish, not new broad surfaces.

- Keep config bootstrap separate from mutable store-backed source registry state.
- Keep auth payload values write-only; display summaries must show metadata and
  payload keys only.
- Keep role-specific stores filesystem-only until a real SQL/secret-manager slice
  is planned.
- New source families should follow the generic runtime source lifecycle rather
  than being forced through MCP `ConnectionConfig`:
  [`runtime source lifecycle`](superpowers/specs/2026-06-09-runtime-source-lifecycle.md).
- Completed: static config `kind: "python"` sources can load trusted local
  `NodeSpec` registries and expose them through WorkflowServer. Implementation:
  [`static Python sources`](historical/superpowers/plans/2026-06-11-static-python-sources.md).
- Completed: `wf config validate` preflights neutral workflow config files,
  including config-relative path resolution and trusted static Python source
  imports. MCP sources are shape-validated only; live upstream checks remain a
  server/status concern.
- Completed: Python source operator docs and RPC integration coverage now prove
  `ops.py` source config, capability call, draft artifact creation, deployment,
  and workflow run. Runbook:
  [`Python source`](runbooks/python-source.md).
- Completed: static source inventory providers now have an explicit
  `WorkflowSourceProvider.load_sources()` seam in `wf_server`, and Python
  source loading is behind `PythonSourceProvider`.
- Completed: `wf --local --config <workflow-config>` now composes configured
  neutral server sources in-process instead of falling back to built-in static
  sources only. `--local` is process-local server composition, not local-only
  source transports or shared in-memory source sessions.
- Completed: server startup policy moved to `wf_server.cli`; JSON-RPC HTTP
  remains in `wf_transport_rpc_http`:
  [`server CLI and transport boundary`](superpowers/specs/2026-06-10-server-cli-transport-boundary.md).
- Next auth work: typed/discriminated auth records and source-owned auth binders
  (`McpAuthBinder` first) are now completed. Remaining: Google Drive MCP smoke
  through `https://drivemcp.googleapis.com/mcp/v1` (manual/local-only, requires
  Google OAuth client credentials). OAuth refresh-token support and provider
  profiles are now implemented. Production secret manager integration and
  encrypted-at-rest file format remain deferred.
- Completed source auth diagnostics: `wf source diagnose <source_id>` now reports
  transport/auth/catalog state without exposing secret payloads.
- Completed source provider docs: `docs/source_provider_guide.md` now covers
  MCP HTTP, MCP stdio, Python sources, auth refs, OAuth refresh-token setup,
  diagnostics, and the Google Drive MCP caveat.
- Completed platform source policy: documented fixed-id sources such as `wf.std`
  and `wf.source` are platform sources. They resolve by fixed source id, do not
  require self-bindings, and legacy explicit self-bindings such as
  `wf.std=wf.std` are accepted as no-op compatibility. Deployment validation
  still rejects non-self platform-source bindings as stale configuration. Other
  `wf.*` namespaces are described by their own source docs/policies.
- Completed `wf.source.read_resource`: resource refs are inert pass-by-value
  data using `logical_source`; explicit platform helper nodes dereference them
  through runtime/platform context with bounded output.
- Completed source inventory CLI polish: `wf source resources` and
  `wf source prompts` list source-owned resource/prompt names without fetching
  content.
- Active specs:
  - [`workflow config targets and sources`](superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md)
  - [`store-backed source registry`](superpowers/specs/2026-06-03-store-backed-source-registry-design.md)
  - [`runtime source lifecycle`](superpowers/specs/2026-06-09-runtime-source-lifecycle.md)
  - [`server CLI and transport boundary`](superpowers/specs/2026-06-10-server-cli-transport-boundary.md)
  - [`auth/source secrets boundary`](superpowers/specs/2026-06-06-auth-source-secrets-boundary.md)

## Priority 4: MCP Package Split Finish Line

`wf_sources_mcp` now owns upstream MCP source implementation pieces: ids,
registry DTOs, auth/catalog stores, discovery/catalog DTOs, SDK adapter/facade,
runtime pool, schema helpers, tool events, wrappers, and adapter lookup.

Next split work should be selective:

- Avoid new dependencies on the combined `wf_mcp` facade from durable server or
  transport packages.
- Keep `wf_mcp` compatibility shims until callers are retired deliberately.
- Move only pieces with clear package ownership. Do not move proxy/UI/App
  metadata support into workflow transports by accident.
- MCP UI/App metadata remains source/proxy metadata only; do not advertise MCP
  Apps/widget support through durable workflow transports yet.

## Priority 5: Runtime/Core Polish Later

Core runtime foundations for native subgraphs, concurrent foreach, lineage state,
and durable stopped-run resume exist. Return here after product/server UX is
stable.

- Native subgraph polish: optional per-use-site child deployment overrides and
  clearer child trace inspection.
- Concurrent foreach polish: reuse barrier/lineage machinery for future
  fork/gather.
- Protocol-native progress: investigate MCP tasks/progress or WebSocket/SSE only
  after polling `wf run watch` proves insufficient.
- OpenAPI sources: continue from [`openapi capability sources`](openapi_capability_source.md)
  when a real non-MCP source is needed.

## Recently Completed Platform Milestones

- `WorkflowApiSurface` is the protocol-neutral workflow operation contract.
- `wf_transport_rpc_http` exposes local/static and MCP-backed `WorkflowServer`
  over JSON-RPC HTTP.
- `wf` can target local or remote workflow APIs for capability discovery, draft
  authoring, artifact/deployment operations, run, inspect, bounded trace,
  resume, and `cap call`.
- Desired source registry reads, mutations, and explicit apply/reload are exposed
  through JSON-RPC and CLI.
- Neutral `wf_config` can express MCP sources, role-specific filesystem stores,
  and client/server target separation.
- `wf config migrate-mcp` converts legacy broker configs to neutral workflow
  config without mutating the original.
- `McpRuntimePool` is shared for stateful upstream MCP operations and has
  JSON-RPC E2E coverage proving session reuse across workflow runs.
- `wf run watch` provides polling-based progress UX.
- CLI expected errors are compact by default; `wf --verbose ...` preserves raw
  tracebacks for debugging.
- Completed thesis case-study evidence bundle: `examples/report_workflow/`
  provides a deterministic report workflow with Python source, fixture input,
  config, runbook, and tests.
- Completed thesis system-design draft: `docs/thesis/system-design-implementation.md`
  now frames the platform as a formal system design/implementation report backed
  by `docs/thesis/evidence-index.md` and the report-workflow case study.
- Completed supplemental browser-click workflow example with serial multi-node lifecycle evidence.
- Completed: an opencode browser-click challenge harness captures external
  agent trials against the deterministic browser-click workflow example without
  changing product runtime code. The old staged-server modes were replaced by
  per-trial local configs in the generic V2 harness.
- Completed: `skills/`, runbooks, and challenge prompt templates are treated as
  the agent instruction layer. Challenge reports now track when trials rely on
  product code, prior stores, adjacent attempts, or existing example solutions.
- Completed: workflow/CLI agent instructions now form an explicit copyable
  bundle for controlled challenge profiles, use `wf schema` for public shape
  discovery, and avoid implementation/test-file guidance.
- Completed: the generic agent challenge harness now supports data-driven
  manifests, layered prompts, explicit `none|skills|all|debug` profiles,
  one-hour hard ceilings, normalized OpenCode tool/token evidence, policy
  findings, and manual-audited reports. Two data-driven challenges exist:
  browser-click and report-workflow. The central `run_trials.py` runner accepts
  any challenge manifest. The `debug` profile is opt-in and captures
  evidence-backed UX issue reports separately from normal benchmark scoring.
- Completed: report projections generate bounded Markdown and JSON reports for
  every V2 trial and regenerate both after audit without mutating raw evidence.
  Implementation:
  [`report projections`](historical/superpowers/plans/2026-06-23-agent-challenge-report-projections.md).
- Completed: challenge trial collection now supports bounded concurrency through
  `run_trials.py --concurrency` and a Python matrix runner,
  `examples/agent_challenges/run_matrix.py`. The PowerShell matrix helper now
  delegates to the Python runner.
- Completed: shared agent challenge evaluation runbook documents trial
  execution, instruction profiles, manual audit, and the distinction between
  evaluation validity and policy coverage:
  [`agent challenge evaluation`](runbooks/agent-challenge-evaluation.md).
- Completed: challenge matrix operations now have compact OpenCode thread
  titles, policy handling for canonical skill-document reads, and a central
  `summarize_trials.py` command for audited result tables.
- Completed: agent challenge results now record OpenCode session metadata and
  resume commands, so incomplete provider runs can be continued without
  mutating original raw evidence.
- Completed: canonical TOML path strings are the emitted workflow path form.
  Paths now serialize as `"input.text"`, `"state.echoed"`, and `"message"`
  (local). Structural `{"root": "input", "parts": ["text"]}` path objects
  remain accepted and are now advertised in generated schemas as an input form.
- Completed: challenge-driven CLI UX fixes now provide exact available
  deployment binding suggestions, reject bare `--bind-output` state targets
  before RPC with compact guidance, and accept `wf schema --full` as an alias
  for `--verbose`.
- Completed: `wf draft bind` with `--from local.x --to output.y` now lowers
  through state
  atomically (projecting into both state_schema and output_schema), and
  validation repair hints cover undeclared workflow input source paths.
  Implementation plan:
  [`bind repair hints`](historical/superpowers/plans/2026-06-29-draft-bind-repair-hints.md).
- Completed: capability-backed draft creation now auto-binds required inputs
  only; optional inputs are surfaced in wrapper-hint notes for explicit binding.
  Implementation plan:
  [`required-only wrapper inputs`](historical/superpowers/plans/2026-06-29-required-only-wrapper-inputs.md).
- Completed: `wf draft set-input` rejects `local.x` targets before RPC and
  shows the equivalent bare-target mapping.
- Completed: `wf draft add-step --route` errors include declared outcomes and
  direct add/remove repair guidance.
- Completed: repeated idempotent `wf draft bind input/state -> local` behavior
  is covered by regression tests.

Agent evaluation cohort status and policy:

- Treat trials collected while product code, prompts, fixtures, harness logic,
  or workspace isolation were changing as formative evaluation. Preserve them
  as qualitative evidence linking observed agent failures to product/harness
  fixes, but do not pool their timing, token, or success metrics with a frozen
  cohort.
- Completed: the primary longitudinal campaign now has N=3 per cell / 36
  manually audited trials across two challenges, two models, and
  `none|skills|all` profiles. The explicit cohort manifest, aggregate Markdown,
  and SVG/PDF figures live in `docs/thesis/`.
- The 36 trials span repository snapshots and a base-prompt change before the
  third wave. Treat the aggregate as longitudinal product/prompt engineering
  evidence, not as a frozen model comparison or causal profile experiment.
- Keep product code, challenge prompts, supplied skill bundle, model variants,
  timeout, concurrency, fixtures, and enabled tool set fixed if a future
  controlled cohort is collected. Record the product baseline and rendered
  prompt hashes with every result.
- Keep manual audit authoritative for final pass/fail/invalid interpretation.
  Automatic policy findings remain review inputs, not bespoke exceptions or
  final benchmark outcomes.

Planned challenge-driven UX follow-ups:

- Design a separate composite-binding/data-shaping slice for cases such as
  mapping state fields into a structured `report` object. Do not hide this
  behind the existing path binding syntax without a deliberate model.

## Historical References

- [`wf_api extraction roadmap`](historical/superpowers/plans/2026-06-01-wf-api-extraction-roadmap.md)
- [`source registry next slices`](historical/superpowers/plans/2026-06-03-source-registry-next-slices.md)
- [`MCP source connection seam`](historical/superpowers/plans/2026-06-07-mcp-source-connection-seam.md)
- [`MCP runtime RPC session reuse E2E`](historical/superpowers/plans/2026-06-08-mcp-runtime-rpc-session-reuse-e2e.md)
