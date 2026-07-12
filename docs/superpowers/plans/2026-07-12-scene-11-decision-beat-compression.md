# Scene 11 Decision Beat Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Scene 11 from three navigation beats to two so the typed interrupt and operator decision remain visible while revision/cancellation is represented as an approval outcome rather than a duplicate slide.

**Architecture:** Keep the existing `typed-human-boundary` scene, its factual `GuidedProductMoment`, and the existing `DemoApprovalActions` handlers. Remove only the storyboard-level `cancel` beat and the presentation-only plumbing that exists solely to support that beat. The canonical interrupt contract and run facts continue to expose `submitted` and `cancelled` outcomes, and `Request revision` continues to resume the same run through the negative outcome branch.

**Tech Stack:** React 19, TypeScript, Vitest, existing storyboard hash navigation, Valibot-backed demo projections.

## Global Constraints

- Scene 11 remains scene number 11 with id `typed-human-boundary`.
- Scene 11 must contain exactly two beats, in order: `interrupt`, then `approval`.
- The approval beat remains the only UI entry point for both `Submit` and `Request revision`.
- Keep canonical persisted outcome values `submitted` and `cancelled`; do not rename backend or replay fields to `revision_requested`.
- Do not change `useDemoTimeline`, live RPC execution, run facts, approval handlers, or Scene 12 behavior.
- `#scene/typed-human-boundary/cancel` must fail closed to `defaultMainLocation`; it must not become an alias.
- Keep the single Editorial Canvas and existing hidden internal-scroll behavior.
- Do not add dependencies, a second state store, or a new transport.

---

### Task 1: Update The Storyboard Contract

**Files:**
- Create: `docs/superpowers/plans/2026-07-12-scene-11-decision-beat-compression.md`
- Modify: `docs/current_roadmap.md`
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Test: `web/apps/console/src/presentation/storyboard.test.ts`

**Interfaces:**
- Produces the canonical Scene 11 beat list consumed by `nextMainLocation`, `locationFromHash`, and `SceneBody`.
- The resulting beat ids are exactly `readonly ["interrupt", "approval"]`.

- [ ] **Step 1: Add the failing storyboard contract test**

Add a test that asserts the exact beat sequence and rejects the removed route:

```ts
it("compresses Scene 11 into interrupt context and one operator decision beat", () => {
  expect(findScene("typed-human-boundary")?.beats.map((beat) => beat.id)).toEqual([
    "interrupt",
    "approval",
  ]);
  expect(findBeat("typed-human-boundary", "interrupt")?.caption).toMatch(/boundary|interrupt/i);
  expect(findBeat("typed-human-boundary", "approval")?.caption).toMatch(/decision|resume/i);
  expect(findBeat("typed-human-boundary", "cancel")).toBeUndefined();
});
```

Keep the existing scene-number assertions. Update any existing Scene 11 tests that still expect `cancel` to expect only the two-beat contract.

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts
```

Expected: the new test fails because `storyboard.ts` still declares the `cancel` beat.

- [ ] **Step 3: Remove only the redundant storyboard beat**

In `storyboard.ts`, delete the `sceneBeat("cancel", ...)` entry from `typed-human-boundary`. Keep the `interrupt` caption and both beats' hidden chat configuration unchanged; the `approval` caption may be clarified to describe both outcomes.

Use copy that makes the decision beat cover both outcomes, for example:

```ts
sceneBeat(
  "approval",
  "Approval",
  "The operator chooses a submitted or revision-requested outcome for the paused run.",
  { chatMode: "hidden", chatTheme: "light" },
),
```

Do not add a separate cancel or revision beat.

- [ ] **Step 4: Update the live roadmap link**

Under `## Next: Scene 8–14 Defense Recomposition`, update item 4 to link the active plan:

```md
4. **Scene 11 compression:** reduce the typed-human-boundary scene to two
   beats: interrupt context and approval decision. Cancellation remains a
   decision outcome rather than a near-duplicate presentation beat.
   Implementation plan:
   [`Scene 11 decision beat compression`](superpowers/plans/2026-07-12-scene-11-decision-beat-compression.md).
```

- [ ] **Step 5: Run the storyboard tests and commit**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts
```

Expected: all storyboard tests pass. Commit the plan, roadmap link, storyboard, and tests:

```powershell
git add docs/superpowers/plans/2026-07-12-scene-11-decision-beat-compression.md docs/current_roadmap.md web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts
git commit -m "feat: compress Scene 11 storyboard beats"
```

### Task 2: Remove The Stale Replay Requirement And Verify Navigation

**Files:**
- Modify: `web/apps/console/src/presentation/demo-beat-requirements.ts`
- Test: `web/apps/console/src/presentation/demo-beat-requirements.test.ts`
- Test: `web/apps/console/src/presentation/storyboard-navigation.test.ts`

**Interfaces:**
- `requirementForDemoBeat("typed-human-boundary", "approval")` continues to require the `interrupt` stage.
- No requirement exists for `typed-human-boundary/cancel`.

- [ ] **Step 1: Add failing navigation assertions**

Extend the navigation tests with these assertions:

```ts
it("advances Scene 11 directly from interrupt to approval, then Scene 12", () => {
  const interrupt = { kind: "main", sceneId: "typed-human-boundary", beatId: "interrupt", focusPath: [] } as const;
  const approval = { kind: "main", sceneId: "typed-human-boundary", beatId: "approval", focusPath: [] } as const;

  expect(nextMainLocation(interrupt)).toEqual(approval);
  expect(nextMainLocation(approval)).toMatchObject({
    kind: "main",
    sceneId: "resume-output-evidence",
    beatId: "resume",
  });
});

it("fails closed for the removed Scene 11 cancel hash", () => {
  expect(locationFromHash("#scene/typed-human-boundary/cancel")).toEqual(defaultMainLocation);
});
```

Update the existing demo requirement table to cover only `interrupt` and `approval` for Scene 11.

- [ ] **Step 2: Run the focused tests and verify stale support is exposed**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/demo-beat-requirements.test.ts src/presentation/storyboard-navigation.test.ts
```

Expected: the navigation test should pass after Task 1; any remaining failure should identify a stale `cancel` requirement or test expectation.

- [ ] **Step 3: Remove the obsolete cancel requirement**

Delete the `"typed-human-boundary/cancel"` entry from `demo-beat-requirements.ts`. Keep the `interrupt` and `approval` entries requiring `requiredStage: "interrupt"`.

- [ ] **Step 4: Verify and commit navigation cleanup**

Run the same focused command. Expected: all tests pass, including the default fallback for the removed hash.

```powershell
git add web/apps/console/src/presentation/demo-beat-requirements.ts web/apps/console/src/presentation/demo-beat-requirements.test.ts web/apps/console/src/presentation/storyboard-navigation.test.ts
git commit -m "test: enforce Scene 11 decision navigation"
```

### Task 3: Remove Cancel-Specific Scene Rendering Plumbing

**Files:**
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Test: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
- Test: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`

**Interfaces:**
- `DemoWorkflowScene` maps `approval` to the approval layout; no rendering branch accepts `cancel` as a presentation beat.
- `GuidedProductMoment` remains the factual Scene 11 renderer and continues to expose both decision controls.

- [ ] **Step 1: Add the approval-outcome regression test**

In the existing approval composition test, assert both available operator outcomes remain visible:

```tsx
expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
expect(screen.getByRole("button", { name: "Request revision" })).toBeEnabled();
expect(screen.getByText(/submitted\s*\/\s*cancelled/i)).toBeInTheDocument();
```

Add or update the `DemoWorkflowScene` test to render the `approval` beat and assert its root has `data-demo-layout="approval"`. Do not add a `cancel` render case.

- [ ] **Step 2: Run the focused tests and verify the existing branch is covered**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx src/presentation/GuidedProductMoment.test.tsx
```

- [ ] **Step 3: Remove the stale `cancel` layout condition**

In `DemoWorkflowScene.tsx`, simplify:

```ts
if (beatId === "approval") return "approval";
```

Do not change `GuidedProductMoment`, `DemoApprovalActions`, `InterruptDecisionForm`, or the underlying outcome projection unless a focused test demonstrates a regression. The existing `Request revision` action is the intended negative outcome within the approval beat.

- [ ] **Step 4: Run the focused tests and commit**

Run the focused command again. Expected: all Scene 11 composition tests pass and no test references a `cancel` presentation beat.

```powershell
git add web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/GuidedProductMoment.test.tsx
git commit -m "refactor: keep Scene 11 outcomes in approval beat"
```

### Task 4: Full Verification, Visual Smoke, Review, And Archive

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-12-scene-11-decision-beat-compression.md` to `docs/historical/superpowers/plans/2026-07-12-scene-11-decision-beat-compression.md`

- [ ] **Step 1: Run the presentation verification gate**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected: all presentation tests, typechecking, and the console build pass. The existing Vite chunk-size warning is acceptable; new failures are not.

- [ ] **Step 2: Run direct-route visual smoke**

With `pnpm dev` running, inspect these routes at `1280x720`, `1024x768`, and `1920x1080`:

```text
http://127.0.0.1:5173/present#scene/typed-human-boundary/interrupt
http://127.0.0.1:5173/present#scene/typed-human-boundary/approval
http://127.0.0.1:5173/present#scene/typed-human-boundary/cancel
```

Expected:

- Interrupt shows the typed interrupt context.
- Approval shows the decision form with Submit and Request revision; no separate cancel slide is needed.
- The removed cancel route falls back to the default presentation location.
- Advancing from approval reaches Scene 12 resume directly.
- No outer document scrollbar appears.

- [ ] **Step 3: Search for stale presentation-beat references**

Run:

```powershell
rg -n 'sceneBeat\("cancel"|typed-human-boundary/cancel|findBeat\("typed-human-boundary", "cancel"\)|beatId === "cancel"' web/apps/console/src/presentation docs/current_roadmap.md web/README.md -g '!*.test.ts' -g '!*.test.tsx'
```

Expected: no matches in production/docs files. The negative-route tests intentionally retain the removed hash and `findBeat` assertion. Other uses of the factual persisted outcome string `cancelled`, runtime cancellation variables, and `Request revision` are valid and must remain.

- [ ] **Step 4: Run independent review**

Run the repository review task against the implementation commits. Fix only concrete findings related to stale navigation, incorrect Scene 11 state, approval outcome semantics, or regressions in existing routes. Do not expand this slice into the broader visual scale/color pass.

- [ ] **Step 5: Archive the completed plan and close the roadmap item**

After verification and review, change item 4 under `## Next: Scene 8–14 Defense Recomposition` from the active wording to `Completed`, link the historical plan, and move the plan:

```powershell
Move-Item docs/superpowers/plans/2026-07-12-scene-11-decision-beat-compression.md docs/historical/superpowers/plans/2026-07-12-scene-11-decision-beat-compression.md
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-12-scene-11-decision-beat-compression.md
git commit -m "docs: complete Scene 11 decision beat compression"
```

## Self-Review Checklist

- [ ] Scene 11 has exactly `interrupt` and `approval` beats.
- [ ] The approval surface still exposes both `Submit` and `Request revision`.
- [ ] Canonical `submitted` and `cancelled` outcome data is unchanged.
- [ ] `#scene/typed-human-boundary/cancel` fails closed instead of aliasing approval.
- [ ] Approval advances directly to Scene 12 resume.
- [ ] No live RPC, replay event, or Scene 12 behavior changed.
- [ ] No stale cancel beat references remain in presentation navigation or requirements.
- [ ] Presentation tests, typecheck, build, visual smoke, and review pass before archival.
