# Presentation Evaluation And Closing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the weak final two presentation scenes with a factual evaluation evidence board, an icon-supported contribution/future-work map, and a canonical end-of-defense discussion index.

**Architecture:** Add three focused presentation components and two small typed projection modules. `SceneBody` remains a router. Scene facts live in typed, testable catalogs; the discussion index derives from the canonical `discussionBranches` catalog and uses an exhaustive branch-to-topic mapping. Existing presentation routing, `DiscussionPanel`, editorial tokens, and reduced-motion behavior remain authoritative.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Lucide React icons already installed in the console package, CSS container queries, existing hash-based presentation navigation.

## Global Constraints

- Follow `docs/superpowers/specs/2026-07-10-presentation-evaluation-closing-design.md` exactly.
- Use test-driven development: add each behavioral test, run it and observe the expected failure, then add the minimum implementation.
- Do not add a charting or icon dependency. Use `lucide-react`, which is already present, and always pair icons with visible text.
- Do not show percentages, success-rate language, model rankings, or statistical significance.
- Keep chat hidden for all Scene 13 and 14 beats.
- Preserve exact counts: 36 total, 27 clean passes, 8 invalid samples, 1 failure, 7 automatic successes invalidated, and 3 automatic failures accepted.
- Keep the contribution wording `Planner proposes; runtime executes.`
- Keep all content readable at 1280x720 and 1024x768 and reachable at browser zoom.
- Add comments around non-obvious exhaustive mappings and return-location behavior.
- Do not modify Scenes 1 through 12.

---

### Task 1: Evaluation Evidence Projection And Scene

**Files:**
- Create: `web/apps/console/src/presentation/evaluation/evaluation-evidence.ts`
- Create: `web/apps/console/src/presentation/evaluation/evaluation-evidence.test.ts`
- Create: `web/apps/console/src/presentation/evaluation/EvaluationEvidenceScene.tsx`
- Create: `web/apps/console/src/presentation/evaluation/EvaluationEvidenceScene.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: `SceneDefinition`, `SceneBeatDefinition`, and `StageCaption`.
- Produces:

```ts
export type EvaluationBeatId = "cohort" | "validity" | "findings";
export type EvaluationFindingIcon = "schema" | "repair" | "binding" | "output" | "shell" | "contamination";

export type EvaluationEvidenceModel = {
  readonly cohortFactors: readonly { readonly value: string; readonly label: string }[];
  readonly totalTrials: 36;
  readonly outcomes: readonly { readonly value: number; readonly label: string; readonly kind: "pass" | "invalid" | "fail" }[];
  readonly auditCorrections: readonly { readonly automatic: string; readonly audited: string }[];
  readonly findings: readonly { readonly label: string; readonly icon: EvaluationFindingIcon }[];
  readonly validityStatement: string;
};

export const evaluationEvidence: EvaluationEvidenceModel;
export const isEvaluationBeatId: (value: string) => value is EvaluationBeatId;
export const EvaluationEvidenceScene: React.FC<{ readonly scene: SceneDefinition; readonly beat: SceneBeatDefinition }>;
```

- Use Lucide icons such as `SearchCode`, `Wrench`, `Cable`, `FileOutput`, `Terminal`, and `ShieldAlert` for the six findings. Icons are decorative with `aria-hidden="true"`; visible labels carry meaning.

- [ ] **Step 1: Write failing projection tests**

Create tests that assert exact counts, the exact validity statement, all six finding labels, unique icon keys, and absence of percentage/ranking vocabulary:

```ts
expect(evaluationEvidence.totalTrials).toBe(36);
expect(evaluationEvidence.outcomes).toEqual([
  { value: 27, label: "clean product-path passes", kind: "pass" },
  { value: 8, label: "invalid evaluation samples", kind: "invalid" },
  { value: 1, label: "failure", kind: "fail" },
]);
expect(evaluationEvidence.auditCorrections).toEqual([
  { automatic: "7 automatic successes", audited: "invalid as clean evidence" },
  { automatic: "3 automatic failures", audited: "accepted from saved evidence" },
]);
expect(evaluationEvidence.validityStatement).toBe(
  "Bounded longitudinal engineering evidence, not a controlled model comparison.",
);
expect(evaluationEvidence.findings.map((finding) => finding.label)).toEqual([
  "Schema discovery",
  "Repair hints",
  "Binding commands",
  "Output schemas",
  "Shell assumptions",
  "Source contamination",
]);
expect(JSON.stringify(evaluationEvidence)).not.toMatch(/%|success rate|leaderboard|superior/i);
```

- [ ] **Step 2: Run projection tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/evaluation/evaluation-evidence.test.ts
```

Expected: FAIL because `evaluation-evidence.ts` does not exist.

- [ ] **Step 3: Implement the typed evidence catalog**

Create the exact model above. Keep source facts in this module rather than spreading literals through JSX. Add this comment above `auditCorrections`:

```ts
// These are campaign-specific audit disagreements, not a general accuracy
// measure for automatic grading.
```

- [ ] **Step 4: Run projection tests and verify GREEN**

Run the command from Step 2. Expected: all projection tests PASS.

- [ ] **Step 5: Write failing scene tests**

Render each beat and assert:

```tsx
expect(screen.getByRole("group", { name: /evaluation evidence board/i })).toHaveAttribute("data-evaluation-beat", "cohort");
expect(screen.getByText("36")).toBeInTheDocument();
expect(screen.getByText("27")).toBeInTheDocument();
expect(screen.getByText("8")).toBeInTheDocument();
expect(screen.getByText("1")).toBeInTheDocument();
```

For `validity`, assert both audit-correction rows and the validity statement. For `findings`, assert all six labels and six SVG icons beneath the labelled findings region. Assert the scene does not render `%`, `success rate`, or `leaderboard`.

- [ ] **Step 6: Run scene tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/evaluation/EvaluationEvidenceScene.test.tsx
```

Expected: FAIL because `EvaluationEvidenceScene` does not exist.

- [ ] **Step 7: Implement the evaluation scene and CSS**

Compose:

```tsx
<>
  <StageCaption eyebrow={`Act III · ${scene.claimClass}`} title={scene.title}>
    <p>{beat.caption}</p>
  </StageCaption>
  <section className="evaluation-board" aria-label="evaluation evidence board" data-evaluation-beat={beatId}>
    <div className="evaluation-board__cohort" aria-label="campaign cohort equation">...</div>
    <ol className="evaluation-board__outcomes" aria-label="audited outcomes">...</ol>
    <div className="evaluation-board__audit" aria-label="automatic and manual audit reconciliation">...</div>
    <ol className="evaluation-board__findings" aria-label="UX gaps exposed by trials">...</ol>
    <p className="evaluation-board__boundary">{evaluationEvidence.validityStatement}</p>
  </section>
  <p className="scene-body__evidence">{scene.evidencePointer}</p>
</>
```

Use one board surface with a cohort equation, horizontal audited-outcome rail, two-row audit reconciliation, and connected finding ledger. Beat attributes control emphasis; no block is conditionally removed. At the existing 1080px container threshold, wrap the cohort equation and stack audit rows. Add 150-250ms opacity/transform transitions, covered by existing reduced-motion overrides.

- [ ] **Step 8: Run tests and commit**

Run both Task 1 test files. Expected: PASS.

```powershell
git add web/apps/console/src/presentation/evaluation web/apps/console/src/presentation/presentation.css
git commit -m "feat: add evaluation evidence board"
```

---

### Task 2: Contribution And Future-Work Closing Scene

**Files:**
- Create: `web/apps/console/src/presentation/conclusion/conclusion-model.ts`
- Create: `web/apps/console/src/presentation/conclusion/conclusion-model.test.ts`
- Create: `web/apps/console/src/presentation/conclusion/ConclusionScene.tsx`
- Create: `web/apps/console/src/presentation/conclusion/ConclusionScene.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: `SceneDefinition`, `SceneBeatDefinition`, `StageCaption`.
- Produces:

```ts
export type ConclusionBeatId = "limits" | "future" | "conclusion" | "questions";
export type FutureWorkIcon = "agent" | "security" | "schedule" | "evaluation" | "runtime";

export const contributionNodes: readonly [
  { readonly id: "planner"; readonly label: "External planner" },
  { readonly id: "substrate"; readonly label: "Typed workflow substrate" },
  { readonly id: "runtime"; readonly label: "Deterministic runtime" },
  { readonly id: "evidence"; readonly label: "Persisted, inspectable evidence" },
];
export const nonClaims: readonly string[];
export const futureWorkBranches: readonly { readonly id: string; readonly label: string; readonly example: string; readonly icon: FutureWorkIcon }[];
export const isConclusionBeatId: (value: string) => value is ConclusionBeatId;
```

- Map icons to existing Lucide components: `Bot`, `ShieldCheck`, `CalendarClock`, `ChartNoAxesCombined`, and `Workflow`. Pair every icon with visible label and example text.

- [ ] **Step 1: Write failing model tests**

Assert the four stable contribution nodes, exact three non-claims, exact five future-work branches, unique IDs/icons, and closing wording.

```ts
expect(nonClaims).toEqual([
  "Not a production sandbox",
  "Not a scheduler",
  "Not a broad agent benchmark",
]);
expect(futureWorkBranches).toHaveLength(5);
expect(new Set(futureWorkBranches.map((branch) => branch.icon)).size).toBe(5);
```

- [ ] **Step 2: Run model tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/conclusion/conclusion-model.test.ts
```

Expected: FAIL because `conclusion-model.ts` does not exist.

- [ ] **Step 3: Implement the closing model**

Use these concrete examples:

```ts
[
  { id: "agent-interface", label: "Agent interface", example: "Chat or planner loop over wf operations", icon: "agent" },
  { id: "security", label: "Security and credentials", example: "Secrets, RBAC, sandboxing, policy", icon: "security" },
  { id: "scheduling", label: "Hosted operations", example: "Scheduling, daemon lifecycle, monitoring", icon: "schedule" },
  { id: "evaluation", label: "Controlled evaluation", example: "Frozen prompts, more trials, independent audit", icon: "evaluation" },
  { id: "runtime", label: "Runtime expansion", example: "Transactional stores, debugging, providers", icon: "runtime" },
]
```

- [ ] **Step 4: Run model tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Write failing component tests**

Assert that all beats preserve the labelled `thesis contribution boundary` diagram. Assert the `limits` beat emphasizes three non-claims, the `future` beat exposes five labelled icon branches, and the `conclusion` beat renders `Planner proposes; runtime executes.` with future branches marked as receded. Do not test CSS color values; test semantic data attributes.

- [ ] **Step 6: Run component tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/conclusion/ConclusionScene.test.tsx
```

Expected: FAIL because `ConclusionScene` does not exist.

- [ ] **Step 7: Implement the closing scene and CSS**

Render the stable center as semantic HTML with CSS connectors, not React Flow. The diagram only has four fixed nodes and should not introduce graph interaction. Use:

```tsx
<section className="conclusion-map" aria-label="thesis contribution boundary" data-conclusion-beat={beatId}>
  <div className="conclusion-map__flow">...</div>
  <ul className="conclusion-map__non-claims" aria-label="explicit non-claims">...</ul>
  <ul className="conclusion-map__future" aria-label="future work layers">...</ul>
  <p className="conclusion-map__statement">Planner proposes; runtime executes.</p>
</section>
```

Use familiar left-to-right reading order and visible arrow connectors. At 4:3, keep planner/substrate/runtime horizontal and move evidence beneath substrate; future branches wrap around the central line without overlap. Apply one cyan emphasis to the substrate and neutral treatments elsewhere.

- [ ] **Step 8: Run tests and commit**

Run both Task 2 test files. Expected: PASS.

```powershell
git add web/apps/console/src/presentation/conclusion web/apps/console/src/presentation/presentation.css
git commit -m "feat: add contribution closing map"
```

---

### Task 3: Canonical Defense Discussion Index And Questions Beat

**Files:**
- Create: `web/apps/console/src/presentation/discussion/defense-discussion-index.ts`
- Create: `web/apps/console/src/presentation/discussion/defense-discussion-index.test.ts`
- Create: `web/apps/console/src/presentation/discussion/DefenseDiscussionIndex.tsx`
- Create: `web/apps/console/src/presentation/discussion/DefenseDiscussionIndex.test.tsx`
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`
- Modify: `web/apps/console/src/presentation/storyboard-navigation.test.ts`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: canonical `discussionBranches`, `DiscussionBranchDefinition`, `DiscussionBranchId`, and `openDiscussion(branchId: string)`.
- Produces:

```ts
export type DefenseDiscussionTopicId =
  | "contribution"
  | "positioning"
  | "runtime"
  | "authoring"
  | "demo"
  | "evaluation"
  | "production";

export type DefenseDiscussionGroup = {
  readonly id: DefenseDiscussionTopicId;
  readonly label: string;
  readonly branches: readonly DiscussionBranchDefinition[];
};

export const discussionTopicByBranchId: Record<DiscussionBranchId, DefenseDiscussionTopicId>;
export const defenseDiscussionGroups: readonly DefenseDiscussionGroup[];
export const DefenseDiscussionIndex: React.FC<{ readonly openDiscussion: (branchId: string) => void }>;
```

- Use Lucide topic icons (`BadgeHelp`, `Map`, `Boxes`, `FileCode2`, `PlaySquare`, `ChartNoAxesCombined`, `Rocket`) in group headings, always with visible labels.

- [ ] **Step 1: Write failing exhaustive projection tests**

Assert that every canonical branch ID occurs exactly once and no mapping key is stale:

```ts
const indexedIds = defenseDiscussionGroups.flatMap((group) => group.branches.map((branch) => branch.id));
expect(indexedIds).toHaveLength(discussionBranches.length);
expect(new Set(indexedIds)).toEqual(new Set(discussionBranches.map((branch) => branch.id)));
expect(Object.keys(discussionTopicByBranchId).sort()).toEqual(
  discussionBranches.map((branch) => branch.id).sort(),
);
```

- [ ] **Step 2: Run projection tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/discussion/defense-discussion-index.test.ts
```

Expected: FAIL because `defense-discussion-index.ts` does not exist.

- [ ] **Step 3: Implement the exhaustive topic mapping**

Create the explicit `Record<DiscussionBranchId, DefenseDiscussionTopicId>`. Add this comment:

```ts
// This explicit record is intentionally exhaustive: adding a Q&A branch must
// also place it in the end-of-defense index instead of silently hiding it.
```

Derive group branch objects from `discussionBranches`; do not duplicate titles,
answers, claim classes, or evidence pointers.

Use this complete mapping:

```ts
export const discussionTopicByBranchId: Record<DiscussionBranchId, DefenseDiscussionTopicId> = {
  "where-is-ai-agent": "contribution",
  "title-ai-agent-wording": "contribution",
  "direct-orchestration": "positioning",
  "generated-scripts": "positioning",
  "hosted-automation": "positioning",
  "durable-agent-graphs": "positioning",
  "mcp-agent-scale": "positioning",
  "not-just-scripts": "positioning",
  "not-just-cli": "runtime",
  "lifecycle-states": "runtime",
  "run-persistence": "runtime",
  "raw-plan-import": "authoring",
  "validation-diagnostics": "authoring",
  "why-schemas": "authoring",
  "typed-interrupts": "authoring",
  "replay-provenance": "demo",
  "demo-reliability": "demo",
  "prepared-replay-boundary": "demo",
  "evaluation-validity": "evaluation",
  "provider-security": "production",
  "security-production-boundary": "production",
  "production-readiness": "production",
};
```

- [ ] **Step 4: Run projection tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Write failing component and storyboard tests**

Component tests assert seven group headings, every canonical branch title, icon presence in group headings, and `openDiscussion` receiving the selected canonical branch ID.

Storyboard tests assert:

```ts
expect(findBeat("conclusion", "questions")).toBeDefined();
expect(findBeat("evaluation", "cohort")?.chatMode).toBe("hidden");
expect(findBeat("conclusion", "conclusion")?.chatMode).toBe("hidden");
expect(findBeat("conclusion", "questions")?.chatMode).toBe("hidden");
expect(locationFromHash("#scene/conclusion/questions")).toEqual({
  kind: "main",
  sceneId: "conclusion",
  beatId: "questions",
  focusPath: [],
});
```

- [ ] **Step 6: Run tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/discussion/DefenseDiscussionIndex.test.tsx src/presentation/storyboard.test.ts src/presentation/storyboard-navigation.test.ts
```

Expected: FAIL because the component and `questions` beat do not exist.

- [ ] **Step 7: Implement the Questions beat and index UI**

Append:

```ts
sceneBeat("questions", "Questions", "Discussion topics gathered for examiner questions.", {
  chatMode: "hidden",
  chatTheme: "light",
})
```

Also explicitly set `chatMode: "hidden"` on every Scene 13 and Scene 14 beat.
Render the index as a labelled `<nav>` with seven sections and standard buttons.
Use a two-column editorial ledger, not a cloud of pills. At narrow widths, use
one scrollable column with visible focus outlines.

- [ ] **Step 8: Run tests and commit**

Run the Task 3 projection and component/storyboard commands. Expected: PASS.

```powershell
git add web/apps/console/src/presentation/discussion web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts web/apps/console/src/presentation/storyboard-navigation.test.ts web/apps/console/src/presentation/presentation.css
git commit -m "feat: gather defense discussion topics"
```

---

### Task 4: Scene Routing, Return Semantics, And Integration

**Files:**
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation-state.test.ts`

**Interfaces:**
- Consumes: `EvaluationEvidenceScene`, `ConclusionScene`, `DefenseDiscussionIndex`, existing `openDiscussion`, and existing discussion return state.
- Produces: Scene 13/14 rendering and Questions-index discussion return behavior.

- [ ] **Step 1: Write failing SceneBody tests**

Add a test helper that renders `SceneBody` at a main location. Assert:

```tsx
expect(screen.getByRole("group", { name: /evaluation evidence board/i })).toBeInTheDocument();
expect(screen.getByRole("group", { name: /thesis contribution boundary/i })).toBeInTheDocument();
expect(screen.getByRole("navigation", { name: /defense discussion index/i })).toBeInTheDocument();
```

On the Questions beat, click `Where is the AI agent?` and assert
`openDiscussion("where-is-ai-agent")`.

- [ ] **Step 2: Run SceneBody tests and verify RED**

Expected: old EvaluationScene/generic NarrativeScene render, and no discussion index.

- [ ] **Step 3: Route dedicated components**

Remove `evaluationStats` and the local `EvaluationScene` from `SceneBody.tsx`.
Import the three dedicated components. Route:

```tsx
case "evaluation":
  return <EvaluationEvidenceScene scene={scene} beat={beat} />;
case "conclusion":
  return beat.id === "questions"
    ? <DefenseDiscussionIndex openDiscussion={openDiscussion} />
    : <ConclusionScene scene={scene} beat={beat} />;
```

Keep the normal per-scene discussion rail off the Questions beat to avoid
duplicating the index below itself:

```tsx
const showDiscussionRail = !(scene.id === "conclusion" && beat.id === "questions");
```

- [ ] **Step 4: Run SceneBody tests and verify GREEN**

Expected: PASS.

- [ ] **Step 5: Write route-level return tests**

Start at `#scene/conclusion/questions`, click a branch, assert the discussion
route opens, then close it and assert the hash/location returns to
`#scene/conclusion/questions`. Also assert Arrow Right from
`#scene/conclusion/conclusion` reaches `#scene/conclusion/questions`.

- [ ] **Step 6: Run route tests and verify RED or existing support**

If the return test already passes because `open_discussion` stores the current
main location, record that result and keep the regression test. The Arrow Right
test must fail until the new beat exists.

- [ ] **Step 7: Make only required state changes**

The existing reducer should already preserve the current main location as
`discussionReturn`. Do not add a Questions-specific state branch unless the
regression test proves it necessary. If a fix is required, comment why the
canonical return location must remain the Questions beat rather than the
discussion branch's parent scene.

- [ ] **Step 8: Run focused integration tests and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx src/presentation/PresentationRoute.test.tsx src/presentation/presentation-state.test.ts
git add web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/presentation/presentation-state.test.ts
git commit -m "feat: integrate evaluation closing and questions"
```

---

### Task 5: Documentation, Browser Craft Review, And Completion Gate

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `web/README.md`
- Move after implementation: `docs/superpowers/plans/2026-07-10-presentation-evaluation-closing.md` to `docs/historical/superpowers/plans/2026-07-10-presentation-evaluation-closing.md`

**Interfaces:**
- Consumes the completed UI and test suite.
- Produces current roadmap/readme documentation and an archived completed plan.

- [ ] **Step 1: Update live documentation**

Mark `Evidence and closing visuals` complete in `docs/current_roadmap.md` and
link both the current design spec and historical implementation plan. Add one
short `web/README.md` paragraph explaining that the final presentation beats
show bounded evaluation evidence, claim boundaries, future work, and the
canonical defense discussion index.

- [ ] **Step 2: Run focused and full verification**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected: all commands exit 0. The existing Vite chunk-size warning is
acceptable; new warnings are not.

- [ ] **Step 3: Capture browser screenshots**

Using the existing local dev server and Playwright CLI, capture:

```text
#scene/evaluation/cohort
#scene/evaluation/validity
#scene/evaluation/findings
#scene/conclusion/limits
#scene/conclusion/future
#scene/conclusion/conclusion
#scene/conclusion/questions
```

Capture every route at 1280x720 and 1024x768. Store screenshots only under the
gitignored `web/apps/console/.visual-smoke/` directory.

- [ ] **Step 4: Perform the visual craft checklist**

For every screenshot verify:

- no clipped labels, connectors, or discussion buttons;
- icons are visible, stylistically consistent, and paired with text;
- no generic metric-card grid or pill cloud dominates the composition;
- outcome counts read as audited evidence rather than a leaderboard;
- the center contribution line remains stable across Scene 14 beats;
- projector contrast remains readable;
- 4:3 reading order matches 16:9;
- Questions content scrolls and every branch remains reachable;
- the final conclusion beat is visually quieter than the future-work beat.

Fix visual failures with a failing DOM/class-contract test where practical,
then repeat screenshots for affected routes.

- [ ] **Step 5: Run independent review**

Generate the current task diff and dispatch independent standards and spec
review. Fix every Critical or Important finding and rerun the affected tests.

- [ ] **Step 6: Archive and commit**

Move the completed plan under `docs/historical/superpowers/plans/`, update live
links, then run `git diff --check`.

```powershell
git add docs/current_roadmap.md web/README.md docs/superpowers/plans/2026-07-10-presentation-evaluation-closing.md docs/historical/superpowers/plans/2026-07-10-presentation-evaluation-closing.md
git commit -m "docs: complete evaluation and closing visuals"
```

Do not declare completion until the working tree is clean and the fresh test,
typecheck, build, screenshot, and review evidence has been read.
