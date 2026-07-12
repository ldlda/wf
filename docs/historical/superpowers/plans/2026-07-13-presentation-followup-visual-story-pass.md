# Presentation Follow-up Visual And Story Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the remaining defense scenes explain their role clearly and use the available 720p canvas deliberately without inventing runtime evidence.

**Architecture:** Keep the existing React presentation compositor, storyboard metadata, and scene-specific projections. This pass changes scene copy, composition, and CSS only where the screenshot review found a concrete hierarchy problem; it does not introduce a second layout system, a new theme, or a new transport. The factual Scene 10 file browser remains a separate roadmap item.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, existing CSS tokens, lucide-react icons, Playwright CLI.

## Global Constraints

- Preserve the single Editorial Canvas and responsive `1280x720` / `1024x768` rehearsal targets.
- Do not reintroduce a stage-wide dark/light theme switch or blue accents on non-demo editorial scenes.
- Do not claim that a replay branch preserves a run identity when its recording uses another ID.
- Keep Scenes 3–5 structurally stable unless a copy or spacing change is required to explain the transition into Scene 7.
- Do not add an input-file browser in this pass; the factual browser is a separate product slice already tracked in `docs/current_roadmap.md`.
- Every visual change must have a route-level or component-level test and a screenshot check at both rehearsal viewports.

---

## Task 1: Clarify The Opening And Lifecycle-to-Authoring Story

**Files:**
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/opening/OpeningThesisScene.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Test: `web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx`
- Test: `web/apps/console/src/presentation/SceneBody.test.tsx`

**Interfaces:**
- Consumes: `SceneDefinition`, `SceneBeatDefinition`, and the existing Scene 1/5/7 render paths.
- Produces: explicit opening and transition copy that distinguishes product goal, implemented contribution, lifecycle vocabulary, and authoring/repair work.

- [ ] **Step 1: Add failing copy-contract tests.**

Add assertions that the title beat exposes all three ideas without treating them as synonyms:

```tsx
expect(screen.getByRole("heading", { name: /design and implementation of lda\.chat/i })).toBeInTheDocument();
expect(screen.getByText(/product goal.*AI agent.*workspace automation/i)).toBeInTheDocument();
expect(screen.getByText(/implemented contribution.*typed workflow substrate/i)).toBeInTheDocument();
```

Add a Scene 7 integration assertion that the authoring scene names its relationship to the lifecycle rather than presenting an isolated diagnostic screen:

```tsx
expect(screen.getByText(/turns an agent proposal into a valid workflow/i)).toBeInTheDocument();
```

Run:

```powershell
pnpm --dir web/apps/console test -- src/presentation/opening/OpeningThesisScene.test.tsx src/presentation/SceneBody.test.tsx
```

Expected: the new assertions fail because the current title/authoring copy does not expose those distinctions.

- [ ] **Step 2: Update storyboard copy and scene framing.**

Use copy with these meanings, keeping the existing title and product name:

```text
Scene 1 title: The product goal: an AI agent for workspace automation.
Scene 1 substrate: The implemented contribution: a typed workflow substrate that external agents can operate.
Scene 5 lifecycle: Draft, Artifact, Deployment, and Run are the durable vocabulary behind reusable automation.
Scene 7 authoring: This is how an external agent proposal becomes a valid workflow: discover, author, diagnose, repair.
```

Render the first two Scene 1 statements as separate hierarchy levels in the existing opening composition. Do not make the phrase “AI agent” disappear; make the implementation boundary visible directly below it. Keep the three planner/tool-surface/runner nodes as supporting decomposition, not a second title.

- [ ] **Step 3: Verify copy and accessibility.**

Run the focused tests again and confirm the accessible heading remains unique after any scene transition animation:

```powershell
pnpm --dir web/apps/console test -- src/presentation/opening/OpeningThesisScene.test.tsx src/presentation/SceneBody.test.tsx
pnpm --dir web/apps/console typecheck
```

Expected: focused tests and typecheck pass.

- [ ] **Step 4: Commit.**

```powershell
git add web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/opening/OpeningThesisScene.tsx web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx web/apps/console/src/presentation/SceneBody.test.tsx
git commit -m "feat: clarify presentation opening and authoring story"
```

---

## Task 2: Give Authoring And Prepared Lifecycle A Dominant Artifact

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Test: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx`
- Test: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx`

**Interfaces:**
- Consumes: existing authoring projection phases and the prepared lifecycle recording.
- Produces: a stable primary evidence region that is larger at 720p, with chat/phase rail remaining supporting context.

- [ ] **Step 1: Write layout-contract tests.**

Assert that the active diagnostic/repair evidence is marked as the primary region and the assistant remains a supporting region:

```tsx
expect(screen.getByRole("region", { name: /validation repair evidence/i })).toHaveAttribute("data-visual-role", "primary");
expect(screen.getByRole("complementary", { name: /prepared authoring assistant/i })).toHaveAttribute("data-visual-role", "support");
```

Assert that the prepared lifecycle has a single primary lifecycle evidence region and a visible phase label at every beat.

- [ ] **Step 2: Recompose only the existing grids.**

Use the current CSS variables and data attributes. At `1280x720`, allocate the main evidence region at least `minmax(0, 1fr)` of the available stage height after caption/footer; constrain the chat rail to its content rather than letting it determine the stage height. At `1024x768`, collapse to the existing narrow layout without introducing page scroll.

For Scene 7, keep the five-stage rail but make the active evidence panel the dominant surface; do not scale all five cards equally. For Scene 9, keep the assistant transcript and lifecycle rail visible, but give the active phase evidence enough width for its operation/tool details to be read without opening a browser zoom.

- [ ] **Step 3: Run component tests and screenshot checks.**

```powershell
pnpm --dir web/apps/console test -- src/presentation/AuthoringPhaseVisual.test.tsx src/presentation/PreparedAuthoringLifecycleScene.test.tsx
pnpm --dir web/apps/console typecheck
```

Capture and inspect:

```text
/present#scene/authoring/diagnose
/present#scene/authoring/repair
/present#scene/prepared-lifecycle/validate
/present#scene/prepared-lifecycle/deployment
```

At both `1280x720` and `1024x768`, verify the primary evidence is larger, the phase rail remains legible, and `document.documentElement.scrollHeight === window.innerHeight`.

- [ ] **Step 4: Commit.**

```powershell
git add web/apps/console/src/presentation/authoring web/apps/console/src/presentation/presentation.css
git commit -m "feat: strengthen authoring and lifecycle visual hierarchy"
```

---

## Task 3: Make Scene 10 Graph Beat Read As A Workflow Diagram

**Files:**
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
- Modify: `web/apps/console/src/presentation/styles/demo-workflow.css`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Test: `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`
- Test: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**
- Consumes: `GraphExecutionPresentation`, canonical prepared graph nodes, and the existing React Flow graph component.
- Produces: a graph beat with readable node labels, intentional horizontal flow, and factual node/outcome semantics.

- [ ] **Step 1: Add graph-contract tests before changing layout.**

Assert the graph exposes exactly the canonical node set and that only real workflow nodes appear:

```tsx
expect(screen.getAllByRole("button", { name: /workflow node/i })).toHaveLength(10);
expect(screen.queryByText(/cancel: no submitted output/i)).not.toBeInTheDocument();
expect(screen.getByText(/revision requested/i)).toBeInTheDocument();
```

Assert the graph container exposes `data-graph-layout="horizontal"` on the graph beat and that action, boundary, and outcome legends remain present.

- [ ] **Step 2: Rebalance graph layout without hand-positioning connectors.**

Continue using React Flow for node/edge coordinates. Change only the canonical node layout/configuration and graph viewport padding: use the existing horizontal layout, reserve enough vertical space for the two outcome branches, and enlarge nodes/labels through the graph’s size variables rather than per-node pixel offsets. Keep arrowheads, edge labels, and semantic node shape variants owned by the graph component.

Do not add a second SVG connector system. If a label collides, fix the node dimensions/layout inputs or React Flow edge label placement, not a one-off transform on the label.

- [ ] **Step 3: Verify graph semantics and screenshots.**

```powershell
pnpm --dir web/apps/console test -- src/presentation/WorkflowGraphStage.test.tsx src/presentation/DemoWorkflowScene.test.tsx
```

Capture:

```text
/present#scene/run-from-deployment/graph
/present#scene/run-from-deployment/operation
/present#scene/typed-human-boundary/approval
```

Expected: the graph reads left-to-right at both rehearsal viewports, no connector/label is detached, and the graph contains ten real workflow nodes rather than a synthetic cancellation node.

- [ ] **Step 4: Commit.**

```powershell
git add web/apps/console/src/presentation/WorkflowGraphStage.tsx web/apps/console/src/presentation/styles/demo-workflow.css web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/WorkflowGraphStage.test.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx
git commit -m "feat: clarify workflow graph presentation"
```

---

## Task 4: Fill Evaluation And Conclusion Beats With Their Actual Claim

**Files:**
- Modify: `web/apps/console/src/presentation/evaluation/EvaluationEvidenceScene.tsx`
- Modify: `web/apps/console/src/presentation/conclusion/ConclusionScene.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Test: `web/apps/console/src/presentation/evaluation/EvaluationEvidenceScene.test.tsx`
- Test: `web/apps/console/src/presentation/conclusion/ConclusionScene.test.tsx`

**Interfaces:**
- Consumes: `evaluationEvidence`, `conclusion-model`, scene beat focus metadata, and existing lucide icon mappings.
- Produces: denser evidence and conclusion boards that remain readable at 720p without adding unsupported claims.

- [ ] **Step 1: Add beat-specific content contracts.**

For Evaluation `findings`, assert that the six findings have a readable two-row arrangement, the campaign-size evidence remains present, and the validity statement is not hidden. For Conclusion `conclusion`, assert that the central contribution statement and planner/runtime boundary remain visible.

```tsx
expect(screen.getByRole("group", { name: /evaluation evidence board/i })).toHaveAttribute("data-evaluation-focus", "findings");
expect(screen.getAllByRole("listitem")).toHaveLength(6);
expect(screen.getByText(/bounded longitudinal engineering evidence/i)).toBeInTheDocument();
```

- [ ] **Step 2: Recompose the boards around a focal claim.**

For Evaluation `findings`, use a readable `3 × 2` finding grid with icons and a compact but visible campaign/evidence strip. Remove unused vertical whitespace rather than shrinking typography. For Conclusion, keep the contribution flow centered, enlarge the contribution node and statement, and allow limits/future-work branches to recede on the conclusion beat while remaining available on their own beats.

Use existing editorial colors and icon mappings. Do not introduce a new blue theme or a generic dashboard/stat-card treatment.

- [ ] **Step 3: Verify all final-scene beats.**

```powershell
pnpm --dir web/apps/console test -- src/presentation/EvaluationEvidenceScene.test.tsx src/presentation/ConclusionScene.test.tsx
```

Capture:

```text
/present#scene/evaluation/cohort
/present#scene/evaluation/findings
/present#scene/conclusion/limits
/present#scene/conclusion/future
/present#scene/conclusion/conclusion
```

Expected: no scene is mostly empty at `1280x720`, no text is clipped at `1024x768`, and each beat has one obvious statement to present.

- [ ] **Step 4: Commit.**

```powershell
git add web/apps/console/src/presentation/evaluation web/apps/console/src/presentation/conclusion web/apps/console/src/presentation/presentation.css
git commit -m "feat: strengthen evaluation and conclusion visuals"
```

---

## Task 5: Full Follow-up Smoke And Documentation

**Files:**
- Modify: `docs/current_roadmap.md`
- Create: `docs/runbooks/presentation-followup-visual-review.md`
- Test: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Consumes: all four visual tasks, the existing rehearsal route manifest, and the current screenshot runner.
- Produces: route-level regression coverage and a dated visual review record that separates fixed visuals from the deferred factual input browser/live E2E work.

- [ ] **Step 1: Add route regression coverage.**

Add a table-driven smoke contract for the changed routes. It must assert the expected heading, primary visual role, and no outer scroll for the route-specific test harness. Use exact-one heading assertions with a settled wait, not `getAllByRole(...).length > 0`.

- [ ] **Step 2: Run the complete gate.**

```powershell
pnpm --dir web test -- --run
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Expected: console, RPC, and server tests pass; typecheck/build pass with only the known Vite chunk-size warning.

- [ ] **Step 3: Capture both viewports.**

Run:

```powershell
./scripts/presentation-rehearsal.ps1
```

Manually inspect the changed routes listed in Tasks 1–4 at both viewports. Record any remaining `VISUAL`, `FACTUAL`, `PRODUCT`, or `BLOCKED` item in `docs/runbooks/presentation-followup-visual-review.md`.

- [ ] **Step 4: Update roadmap and commit.**

Link the plan and review record from `docs/current_roadmap.md`. Keep the factual input browser, live end-to-end run, prepared revision run identity, and full screenshot inspection as explicit follow-ups if they remain unresolved.

```powershell
git add docs/current_roadmap.md docs/runbooks/presentation-followup-visual-review.md web/apps/console/src/presentation/PresentationRoute.test.tsx
git commit -m "docs: record presentation visual follow-up pass"
```

---

## Self-Review

- Scene 1 framing is covered by Task 1.
- Scene 5 to Scene 7 narrative continuity is covered by Task 1.
- Scene 7 and Scene 9 scale/readability are covered by Task 2.
- Scene 10 graph scale and semantics are covered by Task 3.
- Scene 10 factual input browser is explicitly excluded and remains roadmap item 9.
- Scene 13/14 density and focal claims are covered by Task 4.
- Both rehearsal viewports and route-level verification are covered by Task 5.
- Live execution and replay run-identity issues are not silently included in a visual pass.
