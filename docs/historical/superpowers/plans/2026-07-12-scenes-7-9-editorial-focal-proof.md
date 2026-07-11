# Scenes 7-9 Editorial Focal Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recompose Scenes 7-9 so each beat has one dominant factual artifact on the warm Editorial Canvas, with light assistant-style chat and no dark-blue presentation panels outside actual run evidence.

**Architecture:** Keep the existing prepared authoring recording, projection functions, `AssistantOperatorThread`, and storyboard beats. This is a presentation-surface and composition pass, not a new chat runtime or a new source of facts. Each scene remains responsible for its own primary artifact while shared CSS tokens provide the editorial surface and consistent focus treatment.

**Tech Stack:** React 19, TypeScript, Vite, Vitest + Testing Library, existing assistant-ui-derived primitives, CSS custom properties, Playwright CLI screenshots.

## Global Constraints

- Do not add a second recording, chat store, transport, RPC call, or agent runtime.
- Keep `authoring-recording.ts` as the factual source for all Scene 7-9 labels, commands, results, IDs, and phase content.
- Keep Scene 7's operation/diagnostic evidence, Scene 8's prepared conversation, and Scene 9's lifecycle projections; improve hierarchy instead of replacing them with invented copy.
- Use the warm Editorial Canvas for Scenes 7-9. Dark-blue surfaces are reserved for actual run evidence in Scenes 10-12.
- Each beat must have one dominant artifact. Rails, operation labels, evidence pointers, and discussion links remain supporting surfaces.
- Keep the existing assistant-ui-derived `AssistantOperatorThread`; do not install another chat library or introduce `AssistantRuntimeProvider`.
- Do not combine blur with pan/zoom for core slide movement. Use opacity, position, border, or scale transitions only, respecting `motionDisabled` and `prefers-reduced-motion`.
- Preserve 1280x720 readability and verify 1024x768 without horizontal page overflow.

---

### Task 1: Establish The Editorial Surface Contract

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/AgentHandoffScene.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AgentHandoffScene.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: existing `SceneDefinition`, `SceneBeatDefinition`, `AuthoringPhaseProjection`, and `AssistantOperatorThread` props.
- Produces: explicit `data-presentation-surface="editorial"` markers and shared light-surface CSS that later scene-specific tasks can rely on.

- [x] **Step 1: Write failing surface-contract tests**

Add assertions to the scene tests:

```tsx
expect(screen.getByRole("region", { name: "prepared agent handoff" }))
  .toHaveAttribute("data-presentation-surface", "editorial");
expect(screen.getByRole("region", { name: "prepared workflow authoring lifecycle" }))
  .toHaveAttribute("data-presentation-surface", "editorial");
```

For `AuthoringPhaseVisual.test.tsx`, assert every phase visual exposes the same
surface marker on its root element:

```tsx
expect(screen.getByRole("region", { name: /evidence/i }))
  .toHaveAttribute("data-presentation-surface", "editorial");
```

- [x] **Step 2: Run the focused tests and verify the new assertions fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AgentHandoffScene.test.tsx src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx src/presentation/authoring/AuthoringPhaseVisual.test.tsx
```

Expected: the existing regions render, but the new `data-presentation-surface`
assertions fail because the markers do not yet exist.

- [x] **Step 3: Add semantic surface markers and shared tokens**

Add `data-presentation-surface="editorial"` to the Scene 8 and Scene 9 root
sections. Add the same attribute to each `AuthoringPhaseVisual` variant root.
Do not change projection data or operation names.

In `presentation.css`, define the shared local tokens on the marked roots and
make the root transparent to the global `section` card rule:

```css
.agent-handoff-scene[data-presentation-surface="editorial"],
.prepared-lifecycle-scene[data-presentation-surface="editorial"],
.authoring-visual[data-presentation-surface="editorial"] {
  --authoring-paper: var(--color-editorial-paper, oklch(0.975 0.012 82));
  --authoring-ink: var(--color-editorial-ink, oklch(0.19 0.015 65));
  --authoring-muted: var(--color-editorial-muted, oklch(0.48 0.025 65));
  --authoring-rule: color-mix(in oklch, var(--authoring-muted) 32%, transparent);
  background: var(--authoring-paper);
  color: var(--authoring-ink);
}

.presentation-stage__primary > .agent-handoff-scene,
.presentation-stage__primary > .prepared-lifecycle-scene {
  margin: 0;
  border: 0;
  border-radius: 0;
  padding: 0;
}
```

Keep the root reset separate from the inner artifact borders. The purpose is
to prevent the global `section` rule from creating another outer card.

- [x] **Step 4: Run the focused tests and typecheck**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AgentHandoffScene.test.tsx src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx src/presentation/authoring/AuthoringPhaseVisual.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: all focused tests pass and the console typecheck is clean.

- [x] **Step 5: Commit the surface contract**

```powershell
git add web/apps/console/src/presentation/authoring web/apps/console/src/presentation/presentation.css
git commit -m "style: establish editorial surfaces for authoring scenes"
```

---

### Task 2: Recompose Scene 7 Authoring And Repair

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: `projectPreparedAuthoringPhase()` and the existing `AuthoringPhaseVisual` discriminated visual variants.
- Produces: a single large, light factual artifact per Scene 7 beat while preserving the authoring phase rail as orientation.

- [x] **Step 1: Write failing Scene 7 hierarchy tests**

Add tests that render `authoring/discover`, `authoring/diagnose`, and
`authoring/repair` and assert the primary artifact is present and editorial:

```tsx
expect(screen.getByRole("region", { name: "discovery evidence" }))
  .toHaveAttribute("data-presentation-surface", "editorial");
expect(screen.getByRole("region", { name: "validation repair evidence" }))
  .toHaveAttribute("data-presentation-surface", "editorial");
expect(screen.getByRole("region", { name: "authoring phase loop" })).toBeInTheDocument();
```

The test must also assert that the focused phase remains visible and that the
literal operation title from the prepared recording is rendered. Do not assert
implementation-only class names for the visual hierarchy.

- [x] **Step 2: Run the Scene 7 tests and verify the new hierarchy checks fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AuthoringPhaseVisual.test.tsx src/presentation/SceneBody.test.tsx
```

Expected: the factual regions pass, while the new editorial surface or
hierarchy assertions fail until the implementation is changed.

- [x] **Step 3: Make the primary authoring artifact light and beat-led**

Keep the existing visual variant markup and factual fields, but make each root
carry the editorial surface marker. In `presentation.css`:

- Give `.scene-body__authoring-composition` a light canvas and no inherited
  card border.
- Make `.scene-body__authoring-evidence` the large primary artifact with a
  neutral rule, generous padding, and a compact public-operation header.
- Make `.authoring-visual` fill the available composition height with a paper
  background and ink text.
- Use a thin cyan or amber rule only for active/diagnostic emphasis; do not use
  the old dark-blue `--stage-*` backgrounds.
- Keep the authoring phase loop as a shallow supporting rail. Its active item
  should use weight and a rule, while inactive items use opacity rather than
  dark cards.
- Keep the existing Lucide icons in the visual variants and do not replace
  them with text-only labels.
- Use `minmax(0, 1fr)` and `min-height: 0` so the artifact does not overflow at
  1024x768.

The intended shape is a large editorial evidence board, not a terminal card
with a row of dark status cards beneath it.

- [x] **Step 4: Add beat-state transitions without blur**

Use transitions on the existing data attributes only:

```css
.scene-body__authoring-evidence,
.scene-body__authoring-node,
.authoring-visual {
  transition: opacity 180ms ease, transform 180ms ease, border-color 180ms ease;
}

@media (prefers-reduced-motion: reduce) {
  .scene-body__authoring-evidence,
  .scene-body__authoring-node,
  .authoring-visual {
    transition: none;
  }
}
```

Do not add a blur filter or simultaneous pan/zoom to the same artifact.

- [x] **Step 5: Run focused tests, typecheck, and capture Scene 7 smoke**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AuthoringPhaseVisual.test.tsx src/presentation/SceneBody.test.tsx
pnpm --dir web --filter @lda/console typecheck
playwright-cli resize 1280 720
playwright-cli goto 'http://127.0.0.1:5173/present#scene/authoring/discover'
playwright-cli screenshot --filename=web/apps/console/.visual-smoke/scene7-discover-editorial.png
playwright-cli goto 'http://127.0.0.1:5173/present#scene/authoring/diagnose'
playwright-cli screenshot --filename=web/apps/console/.visual-smoke/scene7-diagnose-editorial.png
```

The screenshots must show a light primary artifact, a readable phase rail,
and no dark-blue authoring panel.

- [x] **Step 6: Commit the Scene 7 pass**

```powershell
git add web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "style: make authoring proof editorial and focal"
```

---

### Task 3: Make Scene 8 A Light, Authentic Chat Surface

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/AgentHandoffScene.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AgentHandoffScene.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringConversation.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: the existing prepared authoring thread and shared `AssistantOperatorThread` projection.
- Produces: a full-screen chat that reads like an AI application while remaining a deterministic prepared recording.

- [x] **Step 1: Write failing Scene 8 surface and turn tests**

Add tests for the request beat:

```tsx
const scene = screen.getByRole("region", { name: "prepared agent handoff" });
expect(scene).toHaveAttribute("data-presentation-surface", "editorial");
expect(screen.getByRole("log", { name: "prepared authoring conversation" }))
  .toHaveAttribute("data-surface", "stage");
expect(screen.getByText(/We need to author a report workflow/i)).toBeInTheDocument();
expect(screen.getByText(/Let me inspect the available sources/i)).toBeInTheDocument();
```

Keep the existing tool-group `aria-expanded` and prepared command assertions;
the test should prove the conversation structure, not a particular color.

- [x] **Step 2: Run the Scene 8 tests and verify the new surface assertion fails**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AgentHandoffScene.test.tsx src/presentation/authoring/AuthoringConversation.test.tsx
```

Expected: the conversation content passes, but the editorial surface marker or
new layout contract fails before implementation.

- [x] **Step 3: Recompose the full-screen chat on the Editorial Canvas**

Keep `AssistantOperatorThread` as the renderer. Change only the Scene 8 shell
and its styles:

- Use a warm paper root with ink text and no outer inherited card.
- Keep the phase rail as a quiet top orientation strip, not a dark navigation
  bar.
- Constrain the thread to a readable centered column while allowing its
  viewport to scroll internally.
- Render user turns as a restrained right-aligned paper/ink bubble and
  assistant turns as left-aligned editorial text.
- Render tool groups as collapsed-by-default neutral disclosure rows with a
  subtle cyan state marker. When expanded, show the literal operation name,
  arguments, and result in a bordered inset; do not turn every tool into a
  large card.
- Keep the `Run prepared workflow` action as the one clear bottom composer-like
  action. Do not add a fake text composer or slash command in this slice.
- Keep the prepared/replay copy factual; do not imply hidden reasoning or a
  live LLM response.

Use `data-surface="stage"` and the existing assistant thread classes as the
styling seam. Do not add a new chat primitive or runtime.

- [x] **Step 4: Run focused tests and capture Scene 8 smoke**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AgentHandoffScene.test.tsx src/presentation/authoring/AuthoringConversation.test.tsx
pnpm --dir web --filter @lda/console typecheck
playwright-cli goto 'http://127.0.0.1:5173/present#scene/agent-handoff/request'
playwright-cli screenshot --filename=web/apps/console/.visual-smoke/scene8-request-editorial.png
playwright-cli goto 'http://127.0.0.1:5173/present#scene/agent-handoff/handoff'
playwright-cli screenshot --filename=web/apps/console/.visual-smoke/scene8-handoff-editorial.png
```

The screenshots must read as a normal chat screen on a warm canvas, with
visible turn separation and tool groups, not as two screenshots or a dark
dashboard.

- [x] **Step 5: Commit the Scene 8 pass**

```powershell
git add web/apps/console/src/presentation/authoring/AgentHandoffScene.tsx web/apps/console/src/presentation/authoring/AgentHandoffScene.test.tsx web/apps/console/src/presentation/authoring/AuthoringConversation.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "style: make agent handoff read as editorial chat"
```

---

### Task 4: Make Scene 9 Lifecycle Primary And Chat Secondary

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringConversation.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: the same `AuthoringPhaseVisual` projections and `AuthoringConversation` phase filtering as Scene 8.
- Produces: a light lifecycle canvas with one large phase artifact and a synchronized, secondary chat dock.

- [x] **Step 1: Write failing Scene 9 hierarchy tests**

For `validate` and `artifact`, assert:

```tsx
const scene = screen.getByRole("region", { name: "prepared workflow authoring lifecycle" });
expect(scene).toHaveAttribute("data-presentation-surface", "editorial");
expect(screen.getByRole("region", { name: /validation repair evidence|artifact evidence/i }))
  .toHaveAttribute("data-presentation-surface", "editorial");
expect(screen.getByRole("log", { name: "prepared authoring conversation" }))
  .toHaveAttribute("data-surface", "dock");
```

Also assert that the active phase is represented by one active rail item and
that completed tool groups remain collapsed receipts rather than duplicate
full transcripts.

- [x] **Step 2: Run the Scene 9 tests and verify the new hierarchy checks fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx src/presentation/authoring/AuthoringConversation.test.tsx
```

Expected: the existing lifecycle and dock content renders, but the editorial
surface assertions fail before implementation.

- [x] **Step 3: Rebalance the lifecycle canvas and dock**

Keep the five phase rail items and existing projections. In `presentation.css`:

- Give `.prepared-lifecycle-scene` a warm paper background and neutral rule.
- Make `.prepared-lifecycle-scene__projection` the dominant region with
  `minmax(0, 1fr)` sizing and enough height for the current visual variant.
- Keep `.prepared-lifecycle-scene__dock` secondary at roughly 25-30% of the
  scene height. It may scroll internally, but must not create page overflow.
- Use a thin separator between canvas and dock rather than nested dark cards.
- Give the active phase a black/ink label with a cyan rule; give inactive
  phases muted text and no filled blue card.
- Ensure the dock uses the same editorial chat styling as Scene 8, but retain
  its compact `data-surface="dock"` mode and active tool group.

Do not add another trace panel, lifecycle store, or modal.

- [x] **Step 4: Run focused tests and capture Scene 9 smoke**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx src/presentation/authoring/AuthoringConversation.test.tsx
pnpm --dir web --filter @lda/console typecheck
playwright-cli goto 'http://127.0.0.1:5173/present#scene/prepared-lifecycle/validate'
playwright-cli screenshot --filename=web/apps/console/.visual-smoke/scene9-validate-editorial.png
playwright-cli goto 'http://127.0.0.1:5173/present#scene/prepared-lifecycle/deployment'
playwright-cli screenshot --filename=web/apps/console/.visual-smoke/scene9-deployment-editorial.png
playwright-cli resize 1024 768
playwright-cli goto 'http://127.0.0.1:5173/present#scene/prepared-lifecycle/validate'
playwright-cli screenshot --filename=web/apps/console/.visual-smoke/scene9-validate-4x3.png
```

The screenshots must keep the phase artifact dominant, keep the dock readable,
and show no horizontal overflow or dark-blue authoring panel.

- [x] **Step 5: Commit the Scene 9 pass**

```powershell
git add web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx web/apps/console/src/presentation/authoring/AuthoringConversation.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "style: make lifecycle proof primary"
```

---

### Task 5: Full Smoke, Documentation, And Review

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-12-scenes-7-9-editorial-focal-proof.md` to `docs/historical/superpowers/plans/2026-07-12-scenes-7-9-editorial-focal-proof.md`

**Interfaces:**
- Consumes: the three scene-specific visual contracts and their focused tests.
- Produces: a verified, archived visual pass with the next roadmap target left explicit.

- [x] **Step 1: Run the complete web verification gate**

Run:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Expected: all workspaces pass. The known Vite chunk-size warning may remain.

- [x] **Step 2: Run an Impeccable detector pass on the three scene routes**

Run:

```powershell
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#scene/authoring/diagnose
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#scene/agent-handoff/request
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#scene/prepared-lifecycle/validate
```

The pass must not introduce new `gpt-thin-border-wide-shadow`, `side-stripe`,
or all-caps body-text findings. Existing warnings outside the Scenes 7-9
selectors are not part of this slice.

- [x] **Step 3: Update the roadmap and archive the plan**

Replace roadmap item 9 with:

```markdown
9. Completed: Scenes 7-9 now use one dominant factual artifact per beat on the
   Editorial Canvas: authoring/repair evidence, an authentic light agent chat,
   and a light prepared lifecycle canvas with synchronized secondary chat.
   Implementation:
   [`Scenes 7-9 editorial focal proof`](historical/superpowers/plans/2026-07-12-scenes-7-9-editorial-focal-proof.md).
10. Next: revise the remaining visual outliers only when a screenshot identifies
    a concrete hierarchy, overflow, or factual-readability problem.
```

Move this plan to `docs/historical/superpowers/plans/` and tick every completed
checkbox before committing.

- [x] **Step 4: Request review and commit completion**

Run the repository review workflow, then commit the roadmap and archive move:

```powershell
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-12-scenes-7-9-editorial-focal-proof.md
git add -u docs/superpowers/plans
git commit -m "docs: complete Scenes 7-9 editorial focal proof"
git status --short
```

Expected: the working tree is clean and the final review has no Critical or
Important findings.

## Self-Review

- **Spec coverage:** Task 1 prevents the global `section` card rule from
  producing duplicate frames; Tasks 2-4 make each scene's primary artifact
  editorial and beat-led; Task 5 verifies routes, sizes, detector output, and
  documentation.
- **Placeholder scan:** no unresolved instructions, fake data source, or
  undefined visual behavior remains in the plan.
- **Type consistency:** all tasks preserve `AuthoringPhaseProjection`,
  `AuthoringConversation`, `AssistantOperatorThread`, and existing storyboard
  beat IDs; no new runtime interface is introduced.
- **Scope:** this plan changes presentation composition and CSS only. It does
  not add live LLM calls, a new chat framework, a new transport, or a second
  recording.
