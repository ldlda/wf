# Defense Deck Hierarchy Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Every task ends with focused tests, a browser smoke check where applicable, and a commit.

**Goal:** Recompose the affected defense scenes so every beat has one dominant factual artifact, staged supporting evidence, and a coherent transition into the prepared workflow demonstration.

**Architecture:** Preserve the existing 14-scene storyboard, `presentation-coherence.ts` matrix, `AssistantOperatorThread`, recursive `InteractiveFigure`, prepared authoring recording, and factual demo projections. Improve scene-local composition rather than creating a second presentation runtime or a generic card framework. Scenes 3–5 remain behaviorally and visually frozen except for regression tests.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, Motion, assistant-ui/shadcn-derived primitives already installed in `web/apps/console`, React Flow, Lucide icons, existing BEM/scene CSS.

## Global Constraints

- The presentation is a cinematic product explanation, not a second `/console` and not a live-agent benchmark UI.
- Every beat has one primary artifact; support surfaces must be smaller, quieter, or staged after the primary artifact.
- Chat is a framing device. Use the existing assistant-ui-based `AssistantOperatorThread`; do not add another hand-rolled chat renderer or a second chat state model.
- Replay remains truthful. Prepared recordings must not imply live RPC execution; live `/console` behavior remains separate.
- Use real workflow vocabulary and operation names from the prepared authoring recording and demo projections.
- Keep the existing `paper`/`night` stage themes. Do not introduce a third palette or a global theme switch.
- Preserve the 720p target and verify at `1280x720` and `1024x768`; content may scroll inside a deliberate evidence region but the stage itself must not overflow.
- No `transform: scale()` ancestor may be added around React Flow. React Flow owns graph zoom/pan; the presentation canvas remains percentage-based.
- Use icons only where they explain a real role or state. Do not add decorative icon grids.
- Respect `prefers-reduced-motion` and the existing presentation motion toggle.
- Do not alter Scenes 3, 4, or 5 layout/content during this pass unless a regression test proves they broke.

## Current Scene Contract

The existing `sceneCoherenceMatrix` in `web/apps/console/src/presentation/presentation-coherence.ts` remains the source of truth for each scene's primary artifact, support surface, and chat role. The following changes are intentional:

| Scenes | Primary change |
|---|---|
| 1 | Make the thesis/product boundary the opening focal artifact; reveal the decomposition second. |
| 2 | Make the one-off assistant/tool loop read like a real chat transcript and the reusable workflow read like the durable answer. |
| 3–5 | Freeze. Keep current positioning, boundary, and lifecycle compositions. |
| 6 | Make recursive architecture a navigable semantic zoom with readable labels and stable focus. |
| 7 | Replace generic authoring cards with one evidence-backed author/diagnose/repair loop. |
| 8 | Make the prepared agent handoff a real full-stage conversation, not two static screenshots. |
| 9 | Make the prepared authoring lifecycle the bridge from conversation to product evidence; keep the chat secondary and synchronized. |
| 10 | Keep run operation and graph as separate beats; remove residual support clutter. |
| 11 | Make typed interrupt payload and decision form the sole dominant approval moment. |
| 12 | Give resume, output, and trace separate dominant surfaces with same-run continuity. |
| 13 | Stage cohort, validity, and findings as separate evidence boards rather than one dense dashboard. |
| 14 | Stage limits, future work, contribution, and questions as separate conclusion states. |

---

### Task 1: Lock the Visual Contract and Regression Boundaries

**Files:**
- Modify: `web/apps/console/src/presentation/presentation-coherence.ts`
- Test: `web/apps/console/src/presentation/presentation-coherence.test.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`
- Modify: `docs/current_roadmap.md`

**Interfaces:**
- Preserve `SceneCoherenceEntry`, `coherenceForScene`, and `demoSurfaceForBeat` exports.
- Add a small typed beat contract beside the existing matrix:

```ts
export type BeatVisualMode = "focal" | "split" | "zoom" | "conversation" | "evidence";

export type SceneBeatVisualContract = {
  readonly sceneId: string;
  readonly beatId: string;
  readonly mode: BeatVisualMode;
  readonly primarySurface: string;
  readonly supportSurface: string;
};

const beatContracts = {
  "thesis/title": { mode: "focal", primarySurface: "title-boundary", supportSurface: "none" },
  "thesis/substrate": { mode: "split", primarySurface: "opening-decomposition", supportSurface: "none" },
  "problem/direct-actions": { mode: "split", primarySurface: "tool-loop-transcript", supportSurface: "workflow-blueprint" },
  "problem/missing-contracts": { mode: "split", primarySurface: "workflow-blueprint", supportSurface: "tool-loop-transcript" },
  "architecture/client": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "none" },
  "architecture/api": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "none" },
  "architecture/runtime": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "none" },
  "architecture/node-use": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "evidence-receipt" },
  "authoring/discover": { mode: "evidence", primarySurface: "authoring-discovery", supportSurface: "authoring-loop" },
  "authoring/author": { mode: "evidence", primarySurface: "authoring-draft", supportSurface: "authoring-loop" },
  "authoring/diagnose": { mode: "evidence", primarySurface: "authoring-diagnostic", supportSurface: "authoring-loop" },
  "authoring/repair": { mode: "evidence", primarySurface: "authoring-repair", supportSurface: "authoring-loop" },
  "agent-handoff/request": { mode: "conversation", primarySurface: "prepared-conversation", supportSurface: "none" },
  "agent-handoff/handoff": { mode: "conversation", primarySurface: "prepared-conversation", supportSurface: "none" },
  "evaluation/cohort": { mode: "evidence", primarySurface: "evaluation-cohort", supportSurface: "none" },
  "evaluation/validity": { mode: "evidence", primarySurface: "evaluation-validity", supportSurface: "audit-reconciliation" },
  "evaluation/findings": { mode: "evidence", primarySurface: "evaluation-findings", supportSurface: "validity-boundary" },
  "conclusion/limits": { mode: "evidence", primarySurface: "contribution-boundary", supportSurface: "non-claims" },
  "conclusion/future": { mode: "evidence", primarySurface: "future-layers", supportSurface: "contribution-boundary" },
  "conclusion/conclusion": { mode: "focal", primarySurface: "contribution-statement", supportSurface: "evidence-attachment" },
  "conclusion/questions": { mode: "focal", primarySurface: "discussion-index", supportSurface: "none" },
} as const satisfies Record<string, Omit<SceneBeatVisualContract, "sceneId" | "beatId">>;

export const beatVisualContractFor = (
  sceneId: string,
  beatId: string,
): SceneBeatVisualContract => {
  const key = `${sceneId}/${beatId}`;
  const contract = beatContracts[key];
  if (!contract) throw new Error(`No visual contract for ${key}`);
  return { sceneId, beatId, ...contract };
};
```

- Add contracts for the affected beats only. Keep the existing `demoSurfaceForBeat` API as a compatibility projection.

- [ ] **Step 1: Write failing contract tests**

Add tests that assert:

```ts
expect(beatVisualContractFor("thesis", "title")).toMatchObject({
  mode: "focal",
  primarySurface: "title-boundary",
});
expect(beatVisualContractFor("architecture", "node-use")).toMatchObject({
  mode: "zoom",
  primarySurface: "interactive-architecture",
});
expect(beatVisualContractFor("evaluation", "validity")).toMatchObject({
  mode: "evidence",
  primarySurface: "evaluation-validity",
});
expect(() => beatVisualContractFor("unknown", "beat")).toThrow();
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-coherence.test.ts
```

Expected: FAIL because the beat contract function is not yet implemented.

- [ ] **Step 3: Implement the smallest contract map**

Use a typed record keyed by `sceneId/beatId`, not a second reducer or runtime store. Include the following primary modes:

```ts
const beatContracts = {
  "thesis/title": { mode: "focal", primarySurface: "title-boundary", supportSurface: "none" },
  "thesis/substrate": { mode: "split", primarySurface: "opening-decomposition", supportSurface: "none" },
  "problem/direct-actions": { mode: "split", primarySurface: "tool-loop-transcript", supportSurface: "workflow-blueprint" },
  "problem/missing-contracts": { mode: "split", primarySurface: "workflow-blueprint", supportSurface: "tool-loop-transcript" },
  "architecture/client": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "none" },
  "architecture/api": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "none" },
  "architecture/runtime": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "none" },
  "architecture/node-use": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "evidence-receipt" },
  "authoring/discover": { mode: "evidence", primarySurface: "authoring-discovery", supportSurface: "authoring-loop" },
  "authoring/author": { mode: "evidence", primarySurface: "authoring-draft", supportSurface: "authoring-loop" },
  "authoring/diagnose": { mode: "evidence", primarySurface: "authoring-diagnostic", supportSurface: "authoring-loop" },
  "authoring/repair": { mode: "evidence", primarySurface: "authoring-repair", supportSurface: "authoring-loop" },
  "agent-handoff/request": { mode: "conversation", primarySurface: "prepared-conversation", supportSurface: "none" },
  "agent-handoff/handoff": { mode: "conversation", primarySurface: "prepared-conversation", supportSurface: "none" },
  "evaluation/cohort": { mode: "evidence", primarySurface: "evaluation-cohort", supportSurface: "none" },
  "evaluation/validity": { mode: "evidence", primarySurface: "evaluation-validity", supportSurface: "audit-reconciliation" },
  "evaluation/findings": { mode: "evidence", primarySurface: "evaluation-findings", supportSurface: "validity-boundary" },
  "conclusion/limits": { mode: "evidence", primarySurface: "contribution-boundary", supportSurface: "non-claims" },
  "conclusion/future": { mode: "evidence", primarySurface: "future-layers", supportSurface: "contribution-boundary" },
  "conclusion/conclusion": { mode: "focal", primarySurface: "contribution-statement", supportSurface: "evidence-attachment" },
  "conclusion/questions": { mode: "focal", primarySurface: "discussion-index", supportSurface: "none" },
} as const;
```

- [ ] **Step 4: Add freeze tests for Scenes 3–5 and current chat policy**

Keep the existing baseline assertions and add explicit checks that no affected pass changes the baseline matrix entries.

- [ ] **Step 5: Run focused tests and commit**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-coherence.test.ts src/presentation/storyboard.test.ts
```

Commit:

```powershell
git add web/apps/console/src/presentation/presentation-coherence.ts web/apps/console/src/presentation/presentation-coherence.test.ts web/apps/console/src/presentation/storyboard.test.ts docs/current_roadmap.md
git commit -m "docs: define defense deck visual hierarchy contract"
```

### Task 2: Recompose the Opening Scenes

**Files:**
- Modify: `web/apps/console/src/presentation/opening/OpeningThesisScene.tsx`
- Test: `web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx`
- Modify: `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`
- Test: `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Keep the existing `{ scene, beat }` props.
- Keep `ConceptNode`, `ConceptRail`, and `AssistantOperatorThread` as the existing primitives.
- Add stable data attributes: `data-opening-focus`, `data-problem-focus`, `data-support-state`.

- [ ] **Step 1: Write failing structural tests**

Assert:

```ts
expect(screen.getByRole("region", { name: /thesis opening/i })).toHaveAttribute("data-opening-focus", "title");
expect(screen.getByRole("region", { name: /thesis opening/i })).toHaveAttribute("data-support-state", "receded");
expect(screen.getByRole("region", { name: /chat tool loop versus reusable automation/i })).toHaveAttribute("data-problem-focus", "tool-loop");
```

For `missing-contracts`, assert that the blueprint is primary and the transcript is present but not the visual lead.

- [ ] **Step 2: Implement Scene 1 hierarchy**

Use two authored states:

- `title`: title boundary is the single large object. Show the product title, the forced “AI agent for workspace workflows” origin phrase, and a compact three-part decomposition rail below or behind it. The decomposition is supporting context, not three equal cards.
- `substrate`: keep the title at reduced scale, move the `Workflow Platform` node to the center, and reveal `Planner` and `Tool Surface` as flanking context with explicit labels `external planner` and `public operations`.

Do not add a new title or claim. Use the existing storyboard copy and icons.

- [ ] **Step 3: Implement Scene 2 hierarchy**

Keep the assistant transcript vertically ordered as user → assistant text → tool group → observation. On `direct-actions`, make the transcript the dominant left/center region and keep the blueprint as a quiet destination preview. On `missing-contracts`, shrink/recede the transcript and enlarge the blueprint; show only the three factual proof terms `schemas`, `bindings`, and `records`.

The bridge must not be a large decorative arrow. Use a short semantic label such as `one request` / `reusable definition`.

- [ ] **Step 4: Add scene-local CSS transitions**

Animate only opacity, transform, and width/position of the two authored regions. Do not animate blur or apply a scale transform to React Flow. Add reduced-motion overrides alongside the existing presentation rules.

- [ ] **Step 5: Run focused tests and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/opening/OpeningThesisScene.test.tsx src/presentation/opening/ProblemLoopScene.test.tsx src/presentation/SceneBody.test.tsx
git add web/apps/console/src/presentation/opening web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: give opening scenes a clear visual focal point"
```

### Task 3: Polish the Architecture Semantic Zoom

**Files:**
- Modify: `web/apps/console/src/presentation/scenes/ArchitectureScene.tsx`
- Test: `web/apps/console/src/presentation/scenes/ArchitectureScene.test.tsx`
- Modify: `web/apps/console/src/presentation/figures/InteractiveFigure.tsx`
- Test: `web/apps/console/src/presentation/figures/InteractiveFigure.test.tsx`
- Modify: `web/apps/console/src/presentation/figures/interactive-figure.css`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Preserve `InteractiveFigure` props and React Flow as the graph engine.
- Keep `caption` owned by `ArchitectureScene`; keep figure focus hash-backed through `onFocusPathChange`; do not add a second figure navigation API.

- [ ] **Step 1: Add failing tests for focus presentation**

Cover:

- base architecture route shows breadcrumbs and an accessible figure frame;
- focused `runtime-providers` and `node-use` routes expose the current node and focus path;
- the figure canvas has a horizontal scroll contract at stage size;
- `data-pan-zoom="enabled"` remains true only for focused figures;
- graph nodes remain reachable by keyboard.

- [ ] **Step 2: Implement a stable architecture frame**

Make the frame own the available stage height and give the graph a minimum logical width based on the figure layout orientation. At 1280px, fit the figure without microscopic labels. At 1024px, allow horizontal scrolling inside `.interactive-figure__canvas` rather than shrinking nodes. Keep breadcrumbs outside the scroll region.

- [ ] **Step 3: Make semantic zoom visually explicit**

Use the existing `focusPath` to add `data-figure-focus-level` and a short focus caption such as `System boundary`, `Runtime providers`, or `NodeUse execution`. The active/current node is high-emphasis; inactive nodes remain readable. Avoid extra explanatory cards beside the graph.

- [ ] **Step 4: Verify React Flow coordinate safety**

Do not place `ReactFlow` beneath a CSS `transform: scale()` ancestor. Use the existing responsive canvas and React Flow viewport zoom/pan. Add a comment at the canvas seam explaining this constraint so a future visual pass does not reintroduce the bug.

- [ ] **Step 5: Run focused tests, browser smoke, and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/scenes/ArchitectureScene.test.tsx src/presentation/figures/InteractiveFigure.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Capture:

- `/present#scene/architecture/client`
- `/present#scene/architecture/runtime/focus/runtime-providers`
- `/present#scene/architecture/node-use/focus/node-use`

at `1280x720` and `1024x768`. Commit:

```powershell
git add web/apps/console/src/presentation/scenes web/apps/console/src/presentation/figures web/apps/console/src/presentation/presentation.css
git commit -m "fix: make architecture semantic zoom readable"
```

### Task 4: Replace the Generic Authoring Loop With Product Evidence

**Files:**
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Test: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx`
- Test: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Reuse: `web/apps/console/src/presentation/authoring/authoring-recording.ts`, `authoring-projection.ts`

**Interfaces:**
- Keep `AuthoringPhaseVisual` as the factual phase renderer.
- Add an `AuthoringPhaseId`-based projection prop to the Scene 7 composition only; do not duplicate the recording.

- [ ] **Step 1: Add failing tests**

Assert each Scene 7 beat renders:

- one active loop stage;
- one concrete evidence artifact from the prepared recording;
- a public operation/method name or command;
- an icon with an accessible label where it represents a source, workflow, diagnostic, artifact, or binding;
- no generic “step card” list as the only content.

- [ ] **Step 2: Build an authoring evidence projection**

Map Scene 7 beats to the existing authoring recording:

```ts
discover -> projectPreparedAuthoringPhase("discover")
author -> projectPreparedAuthoringPhase("draft")
diagnose -> projectPreparedAuthoringPhase("validate")
repair -> projectPreparedAuthoringPhase("validate")
```

Render a compact loop rail as orientation, then make `AuthoringPhaseVisual` the large center object. For `diagnose`, show the structured diagnostic and repair command together. For `repair`, show the corrected binding and valid status. Keep the fifth compile/save state as a supporting terminal marker, not a new beat.

- [ ] **Step 3: Add beat-aware layout**

Use `data-authoring-focus` to move the active evidence projection to the center and reduce the loop rail to a quiet spine. Keep the existing dark operation/evidence treatment; do not turn Scene 7 into full-screen chat.

- [ ] **Step 4: Run focused tests and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx src/presentation/authoring/AuthoringPhaseVisual.test.tsx
git add web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/authoring web/apps/console/src/presentation/presentation.css
git commit -m "feat: show factual authoring evidence in scene seven"
```

### Task 5: Recompose the Prepared Agent Handoff and Demo Spine

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/AgentHandoffScene.tsx`
- Test: `web/apps/console/src/presentation/authoring/AgentHandoffScene.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringConversation.tsx`
- Test: `web/apps/console/src/presentation/authoring/AuthoringConversation.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx`
- Test: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Test: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.tsx`
- Test: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Continue to source Scene 8/9 conversation content from `authoring-recording.ts` and `projectPreparedAuthoringThread`.
- Continue to source run facts from `projectDemoRunFacts` and the canonical replay.
- Keep approval action callbacks and live target status unchanged.

- [ ] **Step 1: Add failing route and hierarchy tests**

Assert:

- Scene 8 exposes a single full-stage conversation region with user turns, assistant turns, grouped tool calls, and phase progression;
- Scene 9 has one dominant phase projection and a secondary synchronized conversation rail;
- Scene 10 operation and graph beats do not render the same primary artifact simultaneously;
- Scene 11 approval renders the interrupt payload and decision form, without an output placeholder;
- Scene 12 resume/output/trace each expose their own primary region and preserve the same run ID.

- [ ] **Step 2: Make Scene 8 read as one real chat surface**

Keep the prepared thread but give it a single conversation frame: user request, assistant response, tool groups, interpreted results, and a compact phase rail. Remove duplicated screenshot-like headers and do not add a fake composer. The scene must remain read-only and visibly prepared/replay evidence.

- [ ] **Step 3: Make Scene 9 the bridge, not another chat screen**

Keep `AuthoringPhaseVisual` dominant. Render the conversation as a collapsible secondary rail or modal trigger using the existing assistant thread primitives. The phase rail and the factual projection remain visible when chat is collapsed.

- [ ] **Step 4: Reapply one-primary rules to Scenes 10–12**

Use the existing `data-primary-surface`/`data-support-surface` attributes:

- Scene 10 operation beat: operation block primary; no graph.
- Scene 10 graph beat: graph primary; receipt/proof strip secondary.
- Scene 11 interrupt beat: payload facts and decision form primary; input facts compact.
- Scene 11 approval beat: decision result primary; graph/context secondary.
- Scene 12 resume: resume operation and report primary; support facts compact.
- Scene 12 output: markdown/issues output primary; no empty trace panel.
- Scene 12 trace: trace frames primary; output summary compact and factual.

- [ ] **Step 5: Add transition choreography**

Use layout transitions only between authored regions that persist across adjacent beats. Do not blur or zoom the same object in place. When the primary surface changes, fade the old support region down and reveal the new primary region with a short directional movement. Reduced-motion mode must switch to immediate visibility.

- [ ] **Step 6: Run focused tests and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring src/presentation/DemoWorkflowScene.test.tsx src/presentation/GuidedProductMoment.test.tsx
pnpm --dir web --filter @lda/console typecheck
git add web/apps/console/src/presentation/authoring web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/GuidedProductMoment.tsx web/apps/console/src/presentation/GuidedProductMoment.test.tsx web/apps/console/src/presentation/styles/demo-workflow.css web/apps/console/src/presentation/presentation.css
git commit -m "feat: give the agent handoff and demo one visual spine"
```

### Task 6: Stage Evaluation and Conclusion Evidence

**Files:**
- Modify: `web/apps/console/src/presentation/evaluation/EvaluationEvidenceScene.tsx`
- Test: `web/apps/console/src/presentation/evaluation/EvaluationEvidenceScene.test.tsx`
- Modify: `web/apps/console/src/presentation/conclusion/ConclusionScene.tsx`
- Test: `web/apps/console/src/presentation/conclusion/ConclusionScene.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`

**Interfaces:**
- Preserve `evaluationEvidence`, `contributionNodes`, `futureWorkBranches`, and existing scene props.
- Keep Lucide icons for findings and future work; use the existing models as the only content source.

- [ ] **Step 1: Add failing beat-visibility tests**

Evaluation tests must assert:

- `cohort` emphasizes total and cohort factors;
- `validity` emphasizes audited outcomes and automatic/manual reconciliation;
- `findings` emphasizes a short findings list and validity statement;
- no beat presents all board regions at equal emphasis.

Conclusion tests must assert:

- `limits` emphasizes non-claims;
- `future` emphasizes future branches;
- `conclusion` emphasizes `Planner proposes; runtime executes.`;
- `questions` remains the full discussion index.

- [ ] **Step 2: Implement staged evaluation board**

Keep one persistent board frame, but assign `data-evaluation-focus` to the beat's dominant region. Reduce non-primary regions to labels or a compact strip. Do not remove the exact 36-trial numbers or change `27 / 8 / 1` into a success rate.

- [ ] **Step 3: Implement staged conclusion map**

Keep the contribution flow as the persistent spine. On `limits`, show the three explicit non-claims as the support region. On `future`, reveal future work branches while the contribution spine recedes. On `conclusion`, hide the non-claims/future details and center the contribution statement with the evidence attachment. The questions beat remains a separate discussion index.

- [ ] **Step 4: Run focused tests and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/evaluation src/presentation/conclusion src/presentation/storyboard.test.ts
git add web/apps/console/src/presentation/evaluation web/apps/console/src/presentation/conclusion web/apps/console/src/presentation/presentation.css web/apps/console/src/presentation/storyboard.test.ts
git commit -m "feat: stage evaluation and conclusion evidence"
```

### Task 7: Full Verification, Browser Smoke, and Documentation

**Files:**
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation-css.test.ts`
- Modify: `docs/current_roadmap.md`
- Move: this plan to `docs/historical/superpowers/plans/` after completion

- [ ] **Step 1: Add direct-hash regression coverage**

Cover these routes:

```text
/present#scene/thesis/title
/present#scene/problem/direct-actions
/present#scene/architecture/client
/present#scene/architecture/node-use/focus/node-use
/present#scene/authoring/diagnose
/present#scene/agent-handoff/request
/present#scene/prepared-lifecycle/validate
/present#scene/run-from-deployment/graph
/present#scene/typed-human-boundary/approval
/present#scene/resume-output-evidence/trace
/present#scene/evaluation/validity
/present#scene/conclusion/conclusion
/present#scene/conclusion/questions
```

Assert each route has a primary region and no duplicate generic chat rail when chat is hidden.

- [ ] **Step 2: Run full checks**

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

- [ ] **Step 3: Run browser smoke**

At both `1280x720` and `1024x768`, capture settled screenshots after transitions finish. Verify:

- no stage-level horizontal or vertical overflow;
- Scene 6 graph labels and connectors remain readable;
- Scene 7 factual evidence is larger than the orientation rail;
- Scene 8 reads as one conversation, not two screenshots;
- Scene 11 decision form is visible and usable;
- Scene 12 trace contains the captured frames;
- Scene 13 does not show all evidence blocks at equal weight;
- Scene 14 has one clear conclusion statement;
- reduced-motion mode still reveals all content.

- [ ] **Step 4: Update roadmap and archive the plan**

Add one completed entry to `docs/current_roadmap.md` linking to the archived plan and record any consciously deferred work. Move this file to:

```text
docs/historical/superpowers/plans/2026-07-11-defense-deck-hierarchy-pass.md
```

- [ ] **Step 5: Commit verification/docs**

```powershell
git add web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/presentation/presentation-css.test.ts docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-11-defense-deck-hierarchy-pass.md
git commit -m "docs: complete defense deck hierarchy pass"
```

## Troubleshooting Guidance

- If an opening or conclusion beat becomes unreadable at 1024px, reduce support content before reducing the primary artifact. The deck is allowed to omit secondary prose during a beat.
- If React Flow connectors shift, inspect ancestor transforms first. Do not add another `fitView` timeout as a visual fix; verify that the graph remains outside any CSS-scaled ancestor and that its own viewport handles zoom.
- If a test finds duplicate text after adding a proof strip, scope the query to the semantic region with `within()` rather than weakening the assertion to “at least one match.”
- If the prepared recording and a scene label disagree, update the recording/projection source rather than inventing scene-only copy.
- If a CSS rule fixes one scene but changes Scenes 3–5, scope it under the scene view or a stable scene-specific data attribute and rerun the baseline tests.
- If a browser screenshot is black or incomplete immediately after navigation, wait for the existing entry transition to settle before judging the layout.

## Self-Review Checklist

- Scenes 3–5 are not redesigned.
- Scene 6 still uses React Flow and remains keyboard navigable.
- Scene 7 uses real authoring recording facts and icons.
- Scene 8 remains replay-only and does not claim live execution.
- Scenes 10–12 show the same run ID and factual trace frames.
- Evaluation still says `27 clean product-path passes / 8 invalid evaluation samples / 1 failure`, not a success rate.
- Conclusion separates implemented boundary, future work, and questions.
- No new generic card grid, theme system, chat runtime, or transport was introduced.
- All affected routes have focused tests and settled screenshots at both target sizes.
