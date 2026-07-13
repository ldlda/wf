# Consolidated Authoring Story Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the duplicate conceptual authoring scene, preserve its strongest visual language inside the prepared lifecycle demonstration, remove NodeUse from the rehearsed architecture sequence, and renumber the defense as a coherent 13-scene story.

**Architecture:** Keep the prepared authoring recording as the factual source of truth. Add a presentation-step projection above its five canonical phases so the existing `validate` phase can be shown as separate Diagnose and Repair beats without inventing another recorded operation. Recompose `PreparedAuthoringLifecycleScene` around one large six-step rail, one framed phase artifact containing its caption and public method, the existing supporting assistant pane, and the migrated authoring Q&A rail.

**Tech Stack:** React 19, TypeScript, Vitest and Testing Library, existing assistant-ui-derived presentation chat, existing CSS presentation system, Vite.

## Global Constraints

- Preserve the prepared recording as presentation evidence, not a model trace or live RPC response.
- Do not invent capabilities, methods, diagnostics, file reads, lifecycle states, or run evidence.
- Keep the canonical recording phases `discover | draft | validate | artifact | deployment` unchanged.
- The presentation sequence has six steps: `discover | draft | diagnose | repair | artifact | deployment`.
- Remove `authoring` from the main scene catalog and remove `node-use` from Architecture's linear beats.
- Keep NodeUse available through an explicit Architecture focus deep link and defense Q&A.
- Renumber the deck to 13 scenes; do not retain compatibility aliases for unused old scene hashes.
- Preserve the current prepared assistant, composer behavior, tool groups, and live/replay truth boundaries.
- Move authoring discussion branches to `prepared-lifecycle` and render their discussion rail on that scene.
- Use the existing editorial palette and authoring visual components; do not add another theme or decorative accent.
- Respect `prefers-reduced-motion` and the existing presentation motion-disable switch.
- Add comments around the non-obvious six-step-to-five-phase projection.
- Re-read `presentation.css` before editing and preserve the user's current uncommitted changes in that file.
- Leave unrelated workspace files, including untracked `ISSUES.md`, untouched.

---

### Task 1: Consolidate The Canonical Storyboard

**Files:**
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`
- Modify: `web/apps/console/src/presentation/presentation-rehearsal.test.ts`
- Modify: `web/apps/console/src/presentation/SceneProgress.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationFooter.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation-coherence.ts`
- Modify: `web/apps/console/src/presentation/presentation-coherence.test.ts`

**Interfaces:**
- Produces: a 13-entry `mainScenes` catalog with no `authoring` scene.
- Produces: Architecture beats `overview | client | api | runtime`.
- Produces: Prepared lifecycle beats `discover | draft | diagnose | repair | artifact | deployment`.
- Produces: updated `SceneView` without the unused `authoring` member.

- [ ] **Step 1: Write failing storyboard and rehearsal tests**

Update the scene catalog assertions to require exactly these IDs and counts:

```ts
expect(mainScenes.map((scene) => scene.id)).toEqual([
  "thesis",
  "problem",
  "positioning",
  "planner-runtime",
  "lifecycle",
  "architecture",
  "agent-handoff",
  "prepared-lifecycle",
  "run-from-deployment",
  "typed-human-boundary",
  "resume-output-evidence",
  "evaluation",
  "conclusion",
]);
expect(mainScenes).toHaveLength(13);
expect(findScene("architecture")?.beats.map((beat) => beat.id)).toEqual([
  "overview", "client", "api", "runtime",
]);
expect(findScene("prepared-lifecycle")?.beats.map((beat) => beat.id)).toEqual([
  "discover", "draft", "diagnose", "repair", "artifact", "deployment",
]);
expect(findScene("conclusion")?.number).toBe(13);
expect(findScene("authoring")).toBeUndefined();
```

In `presentation-rehearsal.test.ts`, remove `authoring`, remove Architecture `node-use`, and split prepared lifecycle validation:

```ts
architecture: ["overview", "client", "api", "runtime"],
"agent-handoff": ["request"],
"prepared-lifecycle": ["discover", "draft", "diagnose", "repair", "artifact", "deployment"],
```

Update progress/footer assertions from `/ 14` to `/ 13` and shift scene positions after Architecture. Architecture Runtime becomes `4 / 4`; Run From Deployment becomes `9 / 13`; Agent Request becomes `7 / 13`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts src/presentation/presentation-rehearsal.test.ts src/presentation/SceneProgress.test.tsx src/presentation/PresentationFooter.test.tsx src/presentation/presentation-coherence.test.ts
```

Expected: failures report 14 scenes, the removed `authoring` scene, the `node-use` beat, and the old prepared lifecycle beat list.

- [ ] **Step 3: Implement the 13-scene catalog**

In `storyboard.ts`:

1. Remove `"authoring"` from `SceneView`.
2. Delete the entire `id: "authoring"` scene definition.
3. Delete Architecture's `node-use` beat, but do not remove its figure catalog data.
4. Renumber `agent-handoff` through `conclusion` from 7 through 13.
5. Replace Prepared Lifecycle's `validate` beat with separate `diagnose` and `repair` beats:

```ts
sceneBeat(
  "diagnose",
  "Diagnose invalid draft",
  "Validation returns a structured missing-output diagnostic before artifact creation.",
  { chatMode: "hidden", chatTheme: "light" },
),
sceneBeat(
  "repair",
  "Apply targeted repair",
  "A focused output-map edit resolves the diagnostic and produces a valid Draft.",
  { chatMode: "hidden", chatTheme: "light" },
),
```

Update `presentation-coherence.ts` by deleting the `authoring` matrix entry and its four beat contracts. Keep one `prepared-lifecycle` matrix entry and add six beat contracts whose primary surfaces are discovery, draft graph, diagnostic, repair, artifact, and deployment respectively.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected test files pass.

- [ ] **Step 5: Commit the story catalog**

```powershell
git add web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts web/apps/console/src/presentation/presentation-rehearsal.test.ts web/apps/console/src/presentation/SceneProgress.test.tsx web/apps/console/src/presentation/PresentationFooter.test.tsx web/apps/console/src/presentation/presentation-coherence.ts web/apps/console/src/presentation/presentation-coherence.test.ts
git commit -m "refactor: consolidate authoring defense story"
```

---

### Task 2: Project Six Presentation Steps From Five Recorded Phases

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/authoring-projection.ts`
- Modify: `web/apps/console/src/presentation/authoring/authoring-projection.test.ts`
- Move: `web/apps/console/src/presentation/authoring/scene9-message-state.ts` to `web/apps/console/src/presentation/authoring/prepared-lifecycle-message-state.ts`
- Move: `web/apps/console/src/presentation/authoring/scene9-message-state.test.ts` to `web/apps/console/src/presentation/authoring/prepared-lifecycle-message-state.test.ts`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringConversation.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PresentationAssistantPane.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PresentationAssistantPane.test.tsx`

**Interfaces:**
- Produces: `PreparedLifecycleStepId = "discover" | "draft" | "diagnose" | "repair" | "artifact" | "deployment"`.
- Produces: `projectPreparedLifecycleStep(step): PreparedLifecycleStepProjection`.
- Produces: `recordingPhaseForStep(step): AuthoringPhaseId`.
- Produces: number-independent `PreparedLifecycleMessageState`, `preparedLifecycleMessageReducer`, `projectPreparedLifecycleMessage`, and `projectPreparedLifecycleSubmittedOverrides` names.
- Preserves: `projectPreparedAuthoringPhase(phase)` for recording-oriented callers.

- [ ] **Step 1: Write failing projection tests**

Add tests requiring Diagnose and Repair to use different commands and different visual focus while sharing canonical phase `validate`:

```ts
it("splits one recorded validate phase into diagnosis and repair presentation steps", () => {
  const diagnose = projectPreparedLifecycleStep("diagnose");
  const repair = projectPreparedLifecycleStep("repair");

  expect(diagnose.recordingPhase).toBe("validate");
  expect(repair.recordingPhase).toBe("validate");
  expect(diagnose.focus).toBe("diagnose");
  expect(repair.focus).toBe("repair");
  expect(diagnose.primaryCommand.title).toBe("workflow.draft_workspaces.validate");
  expect(repair.primaryCommand.title).toBe("workflow.draft_workspaces.set_step_output_map");
});
```

Add one exhaustive test for the six presentation steps and five recording phases.

- [ ] **Step 2: Run the projection tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/authoring-projection.test.ts src/presentation/authoring/prepared-lifecycle-message-state.test.ts src/presentation/authoring/PresentationAssistantPane.test.tsx
```

Expected: `projectPreparedLifecycleStep` and `PreparedLifecycleStepId` do not exist.

- [ ] **Step 3: Implement the projection seam**

Add these types and mapping in `authoring-projection.ts`:

```ts
export type PreparedLifecycleStepId =
  | "discover"
  | "draft"
  | "diagnose"
  | "repair"
  | "artifact"
  | "deployment";

export type PreparedLifecycleStepProjection = AuthoringPhaseProjection & {
  readonly step: PreparedLifecycleStepId;
  readonly recordingPhase: AuthoringPhaseId;
  readonly focus: "full" | "diagnose" | "repair";
  readonly primaryCommand: PreparedAuthoringCommand;
};

export const recordingPhaseForStep = (
  step: PreparedLifecycleStepId,
): AuthoringPhaseId => {
  if (step === "diagnose" || step === "repair") return "validate";
  return step;
};
```

Implement `projectPreparedLifecycleStep` by calling the existing phase projection. Select command index `0` for Diagnose and index `1` for Repair; all other steps select index `0`. Throw a descriptive error if a recorded phase unexpectedly has no command. Add a comment explaining that the duplicate `validate` projection is presentation choreography over one factual recording phase.

Move the Scene 9 message-state module and test to the number-independent filenames above. Rename all exported `Scene9*` types/constants and `scene9*` functions to `PreparedLifecycle*` and `preparedLifecycle*`. Update `AuthoringConversation`, `PresentationAssistantPane`, and their tests to use the new imports. Replace DOM IDs `scene9-authoring-message` and `scene9-authoring-message-help` with `prepared-lifecycle-authoring-message` and `prepared-lifecycle-authoring-message-help`.

Update the message-state projection to accept `PreparedLifecycleStepId`, mapping Diagnose and Repair back to `validate` before reading prepared conversation turns. Do not duplicate or mutate the recording.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the command from Step 2. Expected: all tests pass.

- [ ] **Step 5: Commit the projection seam**

```powershell
git add web/apps/console/src/presentation/authoring/authoring-projection.ts web/apps/console/src/presentation/authoring/authoring-projection.test.ts web/apps/console/src/presentation/authoring/prepared-lifecycle-message-state.ts web/apps/console/src/presentation/authoring/prepared-lifecycle-message-state.test.ts web/apps/console/src/presentation/authoring/AuthoringConversation.tsx web/apps/console/src/presentation/authoring/PresentationAssistantPane.tsx web/apps/console/src/presentation/authoring/PresentationAssistantPane.test.tsx
git commit -m "feat: split authoring diagnosis and repair beats"
```

---

### Task 3: Move Scene 7's Rail And Operation Frame Into Prepared Lifecycle

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: `projectPreparedLifecycleStep(beat.id)` from Task 2.
- Produces: one six-step `prepared-lifecycle-scene__rail` with label, number, and short detail per step.
- Produces: one `prepared-lifecycle-scene__frame` containing phase caption, method name, CLI command, and the existing phase visual.

- [ ] **Step 1: Write failing scene tests**

Require the larger rail and framed operation evidence:

```tsx
const rail = screen.getByRole("list", { name: /prepared authoring lifecycle/i });
expect(within(rail).getAllByRole("listitem")).toHaveLength(6);
expect(within(rail).getByText("Diagnose")).toBeInTheDocument();
expect(within(rail).getByText("Repair")).toBeInTheDocument();

const frame = screen.getByRole("region", { name: /active authoring operation/i });
expect(frame).toHaveTextContent("workflow.draft_workspaces.validate");
expect(frame).toHaveTextContent("wf draft validate lda_report_workflow");
expect(frame).toHaveTextContent(/structured missing-output diagnostic/i);
```

Rerender with the Repair beat and require `workflow.draft_workspaces.set_step_output_map` plus the repair-focused visual. Also assert the assistant pane remains present and subordinate.

- [ ] **Step 2: Run the scene tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx src/presentation/authoring/AuthoringPhaseVisual.test.tsx
```

Expected: five rail items, no Diagnose/Repair split, and no framed method/command header.

- [ ] **Step 3: Recompose the lifecycle scene**

Replace the current label-only `phases` array with six presentation-step records:

```ts
const steps = [
  { id: "discover", label: "Discover", detail: "Sources, capabilities, schemas" },
  { id: "draft", label: "Author", detail: "Create and edit mutable Draft" },
  { id: "diagnose", label: "Diagnose", detail: "Structured validation result" },
  { id: "repair", label: "Repair", detail: "Focused output-map edit" },
  { id: "artifact", label: "Artifact", detail: "Immutable versioned definition" },
  { id: "deployment", label: "Deployment", detail: "Bind and validate sources" },
] as const satisfies readonly {
  id: PreparedLifecycleStepId;
  label: string;
  detail: string;
}[];
```

Inside the primary presentation column, render the larger rail before the frame. Each item contains its ordinal, label, and detail. Use `data-active` and `data-complete`; do not use opacity below 0.72 for inactive steps.

Put the caption and method inside the frame:

```tsx
<article
  className="prepared-lifecycle-scene__frame"
  role="region"
  aria-label="active authoring operation"
  data-authoring-step={step.id}
>
  <header className="prepared-lifecycle-scene__frame-header">
    <div>
      <span>{step.label}</span>
      <h2>{beat.title}</h2>
      <p>{beat.caption}</p>
    </div>
    <dl>
      <div><dt>Method</dt><dd><code>{projection.primaryCommand.title}</code></dd></div>
      <div><dt>Equivalent CLI</dt><dd><code>{projection.primaryCommand.command}</code></dd></div>
    </dl>
  </header>
  <AuthoringPhaseVisual projection={projection} focus={projection.focus} />
</article>
```

Keep the assistant pane at approximately 26–30% width and the presentation at 70–74%. The rail and frame must remain the primary artifact. Remove the duplicate external StageCaption caption for this scene or reduce it to the scene title only; beat-specific explanatory copy belongs in the frame.

- [ ] **Step 4: Implement visual hierarchy and motion**

In `presentation.css`:

- Enlarge the rail to six equal columns with a minimum height of `5.4rem`.
- Give each step an ordinal, `1rem` label, and readable `0.72rem` detail.
- Keep the rail on the editorial surface; use one thin active underline instead of filled pills.
- Make the frame a grid with an `auto` evidence header and `minmax(0, 1fr)` visual region.
- Keep Method and Equivalent CLI in the frame's top-right evidence block.
- Animate only the frame content and active underline at `180–240ms`; do not replay a full entrance animation on every render.
- Under `1050px`, keep the rail horizontally scrollable with hidden scrollbar and a minimum step width of `9.5rem`.
- Preserve all reduced-motion rules.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all focused tests pass.

- [ ] **Step 6: Commit the unified visual**

```powershell
git add web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: unify prepared authoring lifecycle visual"
```

---

### Task 4: Remove The Duplicate Scene And Move Its Defense Questions

**Files:**
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`
- Modify: `web/apps/console/src/presentation/presentation-state.test.ts`
- Modify: `web/apps/console/src/presentation/presentation-demo-chrome.test.ts`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Removes: `AuthoringScene`, `authoringSteps`, and `authoringPhaseForBeat` from `SceneBody.tsx`.
- Moves: `raw-plan-import`, `validation-diagnostics`, and `why-schemas` parent scene to `prepared-lifecycle`.
- Produces: a discussion rail beneath Prepared Lifecycle without showing it on run/interrupt/output proof scenes.
- Produces: number-independent `onPreparedLifecycleAdvance` props and `handlePreparedLifecycleAdvance` callback names.

- [ ] **Step 1: Write failing composition and Q&A tests**

Replace the old Scene 7 tests with assertions that:

```ts
expect(findScene("authoring")).toBeUndefined();
expect(
  discussionBranches
    .filter((branch) => branch.parentSceneId === "prepared-lifecycle")
    .map((branch) => branch.id),
).toEqual(expect.arrayContaining([
  "raw-plan-import",
  "validation-diagnostics",
  "why-schemas",
]));
```

Render `prepared-lifecycle/diagnose` and require `defense discussion topics`. Continue to require that `run-from-deployment`, `typed-human-boundary`, and `resume-output-evidence` do not render the rail.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx src/presentation/storyboard.test.ts src/presentation/presentation-state.test.ts src/presentation/presentation-demo-chrome.test.ts src/presentation/PresentationRoute.test.tsx src/presentation/PresentationStage.test.tsx
```

Expected: old Authoring scene still exists, branches still point to it, and Prepared Lifecycle suppresses the rail.

- [ ] **Step 3: Remove the duplicate implementation**

Delete from `SceneBody.tsx`:

- `AuthoringScene`;
- `authoringSteps`;
- `authoringPhaseForBeat`;
- unused authoring imports;
- the `case "authoring"` switch branch.

Rename `onScene9Advance` to `onPreparedLifecycleAdvance` through `SceneBody`, `PresentationStage`, and `PresentationRoute`, including tests. Rename `handleScene9Advance` to `handlePreparedLifecycleAdvance`. This is a clean internal migration; do not keep deprecated aliases.

Delete only CSS selectors exclusive to `scene-body__authoring-composition`, `scene-body__authoring-evidence`, and the old Scene 7 wrapper. Preserve reusable authoring visual selectors and migrate the useful rail node treatment into Prepared Lifecycle before deleting the old names.

- [ ] **Step 4: Move Q&A and selectively expose its rail**

Change the three authoring branch `parentSceneId` values to `prepared-lifecycle`. Adjust `showDiscussionRail` so `prepared-lifecycle` is the only workflow-demo scene allowed to show its migrated discussion rail:

```ts
const showDiscussionRail = !(scene.id === "conclusion" && beat.id === "questions")
  && (!isWorkflowDemoScene || scene.id === "prepared-lifecycle");
```

Keep the rail after the scene content so it occupies the established bottom lane. Tighten its prepared-lifecycle spacing rather than overlaying the phase frame.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all focused tests pass.

- [ ] **Step 6: Commit duplicate-scene removal**

```powershell
git add web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts web/apps/console/src/presentation/presentation-state.test.ts web/apps/console/src/presentation/presentation-demo-chrome.test.ts web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx web/apps/console/src/presentation/PresentationStage.tsx web/apps/console/src/presentation/PresentationStage.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "refactor: remove duplicate authoring scene"
```

---

### Task 5: Preserve NodeUse As An Optional Architecture Deep Dive

**Files:**
- Modify: `web/apps/console/src/presentation/storyboard-navigation.test.ts`
- Modify: `web/apps/console/src/presentation/presenter/presenter-notes.ts`
- Modify: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`
- Modify: `docs/runbooks/defense-qna.md`
- Modify: `docs/runbooks/presentation-rehearsal-matrix.md`

**Interfaces:**
- Produces: canonical optional NodeUse route `#scene/architecture/overview/focus/node-use`.
- Removes: rehearsed `architecture/node-use` beat and its timed presenter note.

- [ ] **Step 1: Write failing deep-link and presenter-note tests**

Add a navigation round-trip for:

```ts
const nodeUseDeepDive = {
  kind: "main" as const,
  sceneId: "architecture",
  beatId: "overview",
  focusPath: ["node-use"],
};
expect(locationFromHash(hashForLocation(nodeUseDeepDive))).toEqual(nodeUseDeepDive);
```

Assert presenter notes contain no timed `architecture/node-use` entry and that the Architecture overview/API/runtime notes remain available.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard-navigation.test.ts src/presentation/presenter/presenter-notes.test.ts
```

Expected: the presenter-note expectations still include the removed beat until implementation.

- [ ] **Step 3: Move NodeUse guidance out of the rehearsed sequence**

Delete the timed `beatNote("architecture", "node-use", ...)`. Update the defense Q&A `What is NodeUse?` pointer to the optional deep link. Update the rehearsal matrix to list the deep link under contingency/Q&A routes, not the main forward sequence.

- [ ] **Step 4: Run tests and verify GREEN**

Run the command from Step 2. Expected: all focused tests pass.

- [ ] **Step 5: Commit the optional deep dive**

```powershell
git add web/apps/console/src/presentation/storyboard-navigation.test.ts web/apps/console/src/presentation/presenter/presenter-notes.ts web/apps/console/src/presentation/presenter/presenter-notes.test.ts docs/runbooks/defense-qna.md docs/runbooks/presentation-rehearsal-matrix.md
git commit -m "docs: move nodeuse to optional defense deep dive"
```

---

### Task 6: Reconcile Presenter Speech, Timing, And Live Documentation

**Files:**
- Modify: `web/apps/console/src/presentation/presenter/presenter-notes.ts`
- Modify: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/runbooks/defense-speech-and-claim-audit.md`
- Modify: `docs/runbooks/presentation-story-audit.md`
- Modify: `docs/runbooks/presentation-followup-visual-review.md`
- Modify: `docs/runbooks/presentation-rehearsal-log.md`
- Modify: `docs/superpowers/specs/2026-07-12-demo-chrome-ownership-design.md`
- Modify: `docs/superpowers/specs/2026-07-12-presentation-live-replay-activation-design.md`
- Move: `docs/superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md` to `docs/historical/superpowers/specs/2026-07-04-defense-presentation-storyboard-design.md`
- Move: `docs/superpowers/specs/2026-07-09-presentation-lifecycle-story-expansion-design.md` to `docs/historical/superpowers/specs/2026-07-09-presentation-lifecycle-story-expansion-design.md`
- Move: `docs/superpowers/specs/2026-07-11-presentation-agent-authoring-story-design.md` to `docs/historical/superpowers/specs/2026-07-11-presentation-agent-authoring-story-design.md`
- Move: `docs/superpowers/specs/2026-07-12-scene-8-chat-entry-design.md` to `docs/historical/superpowers/specs/2026-07-12-scene-8-chat-entry-design.md`
- Move: `docs/superpowers/specs/2026-07-12-presentation-visual-scale-color-pass-design.md` to `docs/historical/superpowers/specs/2026-07-12-presentation-visual-scale-color-pass-design.md`

**Interfaces:**
- Produces: a 13-scene presenter script with authoring explanation concentrated in Prepared Lifecycle.
- Preserves: total planned speech at or below 15 minutes before Q&A.

- [ ] **Step 1: Write failing presenter completeness tests**

Update tests to require one note per canonical beat in the 13-scene storyboard and no note for removed scene/beat IDs. Add assertions that Diagnose mentions structured diagnostics and Repair mentions the focused output-map edit.

- [ ] **Step 2: Run presenter tests and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/presenter
```

Expected: stale authoring notes, 14-scene assumptions, and missing Diagnose/Repair notes fail.

- [ ] **Step 3: Move the speech into Prepared Lifecycle**

Delete all four `authoring/*` notes. Expand Prepared Lifecycle to six concise notes:

- Discover: inspect sources, capabilities, and schemas rather than guessing.
- Draft: focused operations modify mutable authoring state.
- Diagnose: structured diagnostics identify the missing projection.
- Repair: one targeted output-map operation resolves it; hints do not guarantee automatic repair.
- Artifact: save immutable version 1.
- Deployment: bind and validate three local sources; execution starts in the next scene.

Keep each note around 8–10 seconds. Reduce the old combined Scene 7 + Scene 9 budget rather than preserving every removed sentence.

- [ ] **Step 4: Reconcile live docs**

Replace current 14-scene references with 13 where they describe current behavior. Update all scene numbers after Architecture. Keep historical statements unchanged only inside `docs/historical/**`.

Archive the five superseded storyboard/authoring slice specs listed in this task rather than editing them into a false history. Before moving each file, search for references and update live links. At minimum, run:

```powershell
rg -n -F '2026-07-12-scene-8-chat-entry-design.md' docs web
rg -n -F '2026-07-12-presentation-visual-scale-color-pass-design.md' docs web
rg -n -F '2026-07-11-presentation-agent-authoring-story-design.md' docs web
```

Keep `demo-chrome-ownership` and `presentation-live-replay-activation` as live contracts, but update their numeric Scene references while preserving their scene-ID behavior.

Mark this roadmap slice completed only after browser verification.

- [ ] **Step 5: Run presenter tests and verify GREEN**

Run the command from Step 2. Expected: all presenter tests pass and summed planned seconds remain at or below 900.

- [ ] **Step 6: Commit documentation reconciliation**

```powershell
git add web/apps/console/src/presentation/presenter web/README.md docs/current_roadmap.md docs/runbooks docs/superpowers/specs docs/historical/superpowers/specs
git commit -m "docs: reconcile consolidated defense story"
```

---

### Task 7: Visual, Accessibility, And Regression Gate

**Files:**
- Modify only if a verified defect is found: files changed by Tasks 1–6.

- [ ] **Step 1: Run the complete presentation test suite**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
```

Expected: all presentation tests pass.

- [ ] **Step 2: Run typecheck and production build**

```powershell
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: typecheck is clean; build succeeds with only the existing chunk-size warning.

- [ ] **Step 3: Run React Doctor**

```powershell
npx react-doctor@latest --verbose --scope changed
```

Expected: no new issues and no score regression.

- [ ] **Step 4: Browser-check the forward story at 1280×720**

Verify and capture:

```text
#scene/architecture/overview
#scene/architecture/runtime
#scene/agent-handoff/request
#scene/prepared-lifecycle/discover
#scene/prepared-lifecycle/diagnose
#scene/prepared-lifecycle/repair
#scene/prepared-lifecycle/artifact
#scene/prepared-lifecycle/deployment
#scene/architecture/overview/focus/node-use
```

Acceptance checks:

- Architecture advances from Overview to Runtime with no NodeUse linear beat.
- Agent Request advances directly into Prepared Lifecycle Discover.
- The six-step rail is larger than the old Scene 9 label strip and remains readable at 720p.
- Diagnose and Repair visibly focus different halves of the same factual validation recording.
- The active frame contains beat caption, method name, equivalent CLI, and phase visual.
- The assistant remains supporting, not dominant.
- Authoring Q&A pills appear below Prepared Lifecycle without covering the assistant, rail, or frame.
- NodeUse remains reachable only through explicit focus navigation or Q&A.
- No outer presentation scrollbars appear.

- [ ] **Step 5: Browser-check at 1024×768 and 1920×1080**

At 1024×768, verify the phase rail scrolls internally without exposing a browser scrollbar. At 1920×1080, verify the frame does not become a sparse oversized box and method/CLI text remains aligned inside it.

- [ ] **Step 6: Run diff hygiene and independent review**

```powershell
git diff --check
git status --short
```

Run the repository review workflow against the full slice. Fix Critical and Important findings; document any intentionally deferred Minor findings.

- [ ] **Step 7: Commit verified corrections only when review changed files**

If Step 6 required corrections, stage each corrected file by its exact path as
reported by `git status --short`, verify the staged diff with
`git diff --cached`, and commit with message
`fix: close consolidated authoring review findings`. If review required no
correction, do not create an empty commit. Never stage untracked `ISSUES.md` or
unrelated user changes.
