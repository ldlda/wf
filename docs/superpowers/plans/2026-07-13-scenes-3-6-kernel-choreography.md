# Interactive graphs and Scenes 3-6 choreography implementation plan

> **Dependency:** Execute after `2026-07-13-defense-story-reweighting.md`.

**Goal:** Give Scenes 3-5 restrained beat-to-beat motion, rebuild Scene 6 as a readable interactive architecture explorer, and improve the long prepared-run graph and its node inspector without adding unsupported evidence.

**Architecture:** Reuse the editorial canvas, Motion dependency, and React Flow figure system. Scene 6 keeps semantic zoom, but each subsystem uses the topology that explains it: layered overview, fan-in client surface, branched core loop, provider grouping, or NodeUse sequence. The prepared-run graph remains visible when its node inspector opens. Do not force every relationship into a horizontal chain.

## Constraints

- Keep one editorial light theme and remove non-demo blue dominance.
- Preserve simultaneous visibility for comparisons that require it.
- Use existing CSS tokens and icons.
- Respect `prefers-reduced-motion` and the presentation motion-disabled state.
- Do not add hand-positioned connectors or a second graph renderer.
- Use React Flow pan, zoom, fit-view, and layout inputs rather than CSS scaling around the graph.
- Use icons and conventional state/flow shapes where they improve scanning; do not render every node as the same rounded rectangle.
- Keep graph labels at least 18px at `1280x720`; prefer 20-22px for active nodes.
- Keep the current scene IDs and deep-link behavior unless a migration updates every live reference and test.

## Task 1: Pin visual contracts before restyling

**Files:**
- Modify tests for `PositioningScene`, `BoundaryScene`, `LifecycleScene`, and `ArchitectureScene`
- Modify route tests for Scenes 3-6

- [ ] Assert one primary visual region per beat through `data-visual-role="primary"`.
- [ ] Assert reduced-motion behavior and stable accessible headings.
- [ ] Assert Scene 6 exposes public surface, kernel loop, state/trace/routing, and provider boundary concepts across its four beats.
- [ ] Assert architecture figures declare a topology appropriate to their subject rather than four repeated linear flows.
- [ ] Assert the prepared-run graph preserves ten displayed action/boundary/outcome nodes, readable labels, pan/zoom, and a factual node inspector.
- [ ] Capture baseline screenshots at `1280x720` and `1024x768` before implementation.

## Task 2: Add restrained motion to Scene 3 positioning

**Files:**
- Modify: positioning scene component in `SceneBody.tsx` or extract a focused module
- Modify: `presentation.css`
- Modify: focused tests

- [ ] Keep the existing information architecture and add one shared layout transition between the two beats.
- [ ] On `landscape`, keep the related-system map as the complete comparison.
- [ ] On `lda-position`, enlarge the typed-substrate position and shift the surrounding systems enough to make the focus obvious without hiding the comparison axis.
- [ ] Use position and scale before opacity; one clear transform is enough.
- [ ] Keep titles, category labels, and evidence readable at both target viewports.

## Task 3: Add restrained motion to Scene 4 planner/runtime ownership

- [ ] Preserve the current three-pane comparison.
- [ ] On `planner`, enlarge the planner pane while retaining runtime destination context.
- [ ] On `runtime`, let the runtime pane grow into the released space.
- [ ] On `boundary`, restore both sides and enlarge the typed CLI/JSON-RPC seam.
- [ ] Animate position and width between states; do not change color theme between beats.
- [ ] Keep the spoken claim exact: planner proposes; runtime owns validation, state, execution, trace, and explicit resume.

## Task 4: Add restrained motion to Scene 5 lifecycle vocabulary

- [ ] Preserve the four-record lifecycle rail and its order.
- [ ] For each beat, grow the active record into the available space while the other records compress but remain readable.
- [ ] Keep arrows and order visible so the audience does not mistake the records for independent cards.
- [ ] Show raw-plan-to-artifact as optional visual evidence without implying Draft is mandatory.
- [ ] Avoid replaying the prepared example; Scene 9 owns applied evidence.

## Task 5: Rebuild Scene 6 as an interactive semantic zoom

**Files:**
- Modify: `web/apps/console/src/presentation/scenes/ArchitectureScene.tsx`
- Modify: `web/apps/console/src/presentation/figures/architecture-catalog.ts`
- Modify: `web/apps/console/src/presentation/figures/model.ts`
- Modify: `web/apps/console/src/presentation/figures/layout.ts`
- Modify: `web/apps/console/src/presentation/figures/InteractiveFigure.tsx` only if required by an existing figure contract
- Modify: associated tests and CSS

- [ ] Base the root figure on the thesis Architecture Spine, not an invented package map: workflow owner and external agent enter through CLI/JSON-RPC, `WorkflowServer` composes the API, records, inventory, and `wf_core`, then status/output/trace return through the public surface.
- [ ] Keep providers as one compact input into capability inventory at the root. Provider-family detail is optional drill-down, not one quarter of the main architecture story.
- [ ] Keep click-to-focus and breadcrumb navigation. A node with `childFigureId` zooms into its subsystem; a leaf node opens evidence/details without replacing the whole figure.
- [ ] Give the client surface a fan-in topology, with human/external agent clients and the web console converging on CLI or JSON-RPC and then WorkflowApi.
- [ ] Give the WorkflowApi zoom a lifecycle-operation surface: capabilities, drafts, artifacts, deployments, and runs surrounding the API boundary. Use compact HTML operation receipts or method groups inside graph nodes when they communicate more than another label box.
- [ ] Add a core-runtime child figure based on the thesis flowchart at `system-design-implementation.md:626`: select frame, branch by step kind, trace and route loop, interrupt/resume branch, and terminal output.
- [ ] Represent node, condition, foreach, join, subgraph, interrupt, and end with icons or conventional shapes. Explicitly exclude general fork/gather.
- [ ] Make `NodeUse` inside the core loop clickable. Its child figure follows the thesis sequence diagram: Runtime, Binding Resolver, NodeDef Handler, State Reducers, and Trace Store. Use participant lanes, message arrows, and small factual state/result panels instead of six identical nodes.
- [ ] Allow further click-through from important core nodes where useful: interrupt opens request/resume contract evidence; trace opens a representative trace frame; step dispatch opens the supported-step palette. Do not create drill-down merely because a node exists.
- [ ] Group built-in, MCP, and Python providers around the provider-neutral capability boundary; do not connect source families as an arbitrary adjacency chain.
- [ ] Use larger labels and summaries, and allow user pan/zoom instead of shrinking the full graph until it fits.
- [ ] Qualify determinism in visible copy: core semantics are deterministic for fixed definitions and handler results.
- [ ] Keep React Flow as the one interactive graph system. Extend its layout model with named topologies or rank/position hints instead of manually drawing edge coordinates.

### Scene 6 figure hierarchy

Implement and test this hierarchy before polishing individual nodes:

```text
Architecture spine
├─ Front door and transport
├─ Workflow API operations
├─ WorkflowServer composition
├─ wf_core execution loop
│  ├─ Supported step kinds
│  ├─ NodeUse sequence
│  ├─ Typed interrupt contract
│  └─ Trace frame evidence
├─ Lifecycle records
└─ Capability inventory
   └─ Built-in / MCP / Python providers
```

The four scripted beats need not visit every child. The audience path should be root architecture, public/API boundary, `wf_core` loop, then NodeUse execution. The remaining children exist for interaction and Q&A.

## Task 6: Improve the prepared-run graph and node inspector

**Files:**
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
- Modify: `web/apps/console/src/presentation/NodeSpotlight.tsx`
- Modify: `web/apps/console/src/presentation/OperationBlock.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`
- Modify: associated tests

- [ ] Re-layout the long run graph into a readable two-dimensional flow with the submitted and revision branches separated vertically. Do not shrink ten displayed nodes into one horizontal strip.
- [ ] Keep pan, drag, and zoom enabled. Use fit-view as the initial state, not the only readable state.
- [ ] Remove selected/current-node treatment from the static graph beat unless a real execution state supports it.
- [ ] Replace the generic `NodeSpotlight` paragraph with a reusable node inspector showing node kind, capability or boundary, factual input/output or schema summary, outcomes, and code/evidence pointer.
- [ ] Keep the run graph visible behind or beside its inspector so selection retains context.
- [ ] Replace “View raw evidence ->” with a precise action label such as “Inspect protocol receipt”. Open the existing evidence inspector at the relevant event rather than a generic drawer.
- [ ] Test the interrupt and issue-creation nodes as distinct inspector examples, plus the fallback for ordinary nodes.

## Task 7: Visual verification

- [ ] Run focused scene and figure tests, full presentation tests, typecheck, and build.
- [ ] Capture every Scene 3-6 beat and the Scene 10 graph at both rehearsal viewports.
- [ ] Capture architecture root, client surface, core runtime, NodeUse, provider detail, and the open run-node inspector.
- [ ] Verify no page scroll, no clipped captions, no detached connectors, and no text below 18px at `1280x720`.
- [ ] Run the Impeccable detector and review screenshots manually.
- [ ] Update roadmap, archive this plan, and commit.

**Completion gate:** Scenes 3-5 gain clear motion without redesign churn. Scene 6 remains interactive but every zoom level uses a readable, subject-appropriate diagram. The prepared-run graph is readable without fitting ten nodes into one thin row, and node selection reveals factual details rather than a generic paragraph.
