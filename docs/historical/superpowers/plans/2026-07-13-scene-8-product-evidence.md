# Scene 8 Product Evidence Implementation Plan

> Historical: completed 2026-07-13. Scene 8 evidence, route assertions,
> verification, and documentation closure are recorded in the historical plan
> archive.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Scene 8's inaccurate missing-output story and sparse prepared visuals with compact product-result views derived from reviewed `wf` output.

**Architecture:** Store reviewed deterministic evidence in one source-owned TypeScript catalog, project it through the existing prepared-authoring boundary, and render one dominant result per lifecycle beat. Presentation navigation remains replay-only; no authoring RPC call occurs when the audience opens Scene 8.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Lucide icons, existing editorial presentation CSS.

## Global Constraints

- Use reviewed CLI evidence, not invented JSON and not runtime authoring calls.
- Diagnose must show `missing_outcome_edge`, `nodes[analyze]`, revision `3`, and the reviewed message.
- Repair must show `wf draft set-route lda_report_workflow --revision 3 --step analyze --outcome ok --to __end__`, then revision `4`, `status: valid`, and zero diagnostics.
- Do not display disposable probe workspace IDs.
- Do not claim automatic repair or live authoring.
- Preserve the left prepared-assistant pane, six lifecycle beats, discussion rail, internal chat scrolling, and the full-height 4:3/16:9 layout.
- Use product vocabulary and restrained editorial styling; do not create nested generic cards.

---

### Task 1: Create The Reviewed Authoring Evidence Catalog

**Files:**
- Create: `web/apps/console/src/presentation/authoring/reviewed-authoring-evidence.ts`
- Create: `web/apps/console/src/presentation/authoring/reviewed-authoring-evidence.test.ts`

**Interfaces:**
- Produces: `ReviewedAuthoringEvidence`, `ReviewedAuthoringStep`, and `reviewedAuthoringEvidenceFor(step)`.
- Consumed by: authoring recording/projection and Scene 8 visual components.

- [x] **Step 1: Write failing catalog tests**

Test all six step IDs and pin the reviewed diagnostic/repair facts:

```ts
expect(reviewedAuthoringEvidenceFor("diagnose")).toMatchObject({
  kind: "diagnostic",
  workspaceId: "lda_report_workflow",
  revision: 3,
  status: "invalid",
  diagnostic: {
    code: "missing_outcome_edge",
    path: "nodes[analyze]",
    message: "reachable node is missing edges for outcomes ['ok']",
  },
});

expect(reviewedAuthoringEvidenceFor("repair")).toMatchObject({
  kind: "repair",
  fromRevision: 3,
  toRevision: 4,
  command: "wf draft set-route lda_report_workflow --revision 3 --step analyze --outcome ok --to __end__",
  status: "valid",
  diagnosticCount: 0,
});
```

Also assert that the serialized catalog does not contain `presentation_diag_probe`, `missing output projection`, or `no state projection`.

- [x] **Step 2: Run the catalog test and verify RED**

Run the new test directly. Expected: module-not-found failure.

- [x] **Step 3: Implement the discriminated union and catalog**

Define these variants:

```ts
export type ReviewedAuthoringEvidence =
  | { readonly kind: "inventory"; readonly sourceCount: 6; readonly sources: readonly string[]; readonly capability: { readonly name: string; readonly inputs: readonly string[]; readonly outputs: readonly string[]; readonly outcomes: readonly string[] } }
  | { readonly kind: "draft"; readonly workspaceId: "lda_report_workflow"; readonly revision: 2; readonly status: "valid"; readonly stepCount: 2; readonly routeCount: 2; readonly steps: readonly string[]; readonly routes: readonly string[] }
  | { readonly kind: "diagnostic"; readonly workspaceId: "lda_report_workflow"; readonly revision: 3; readonly status: "invalid"; readonly diagnostic: { readonly code: "missing_outcome_edge"; readonly path: "nodes[analyze]"; readonly message: string; readonly explanation: string } }
  | { readonly kind: "repair"; readonly fromRevision: 3; readonly toRevision: 4; readonly command: string; readonly status: "valid"; readonly diagnosticCount: 0 }
  | { readonly kind: "artifact"; readonly artifactId: "lda_report_case_study"; readonly version: 1; readonly immutable: true; readonly requiredSources: readonly string[] }
  | { readonly kind: "deployment"; readonly deploymentId: "lda_report_case_study.default"; readonly status: "runnable"; readonly bindings: readonly { readonly requirement: string; readonly source: string }[] };
```

Use the three local source IDs and `local.lda_report.analyze_documents` with input `documents`, output `analysis`, and outcome `ok`.

- [x] **Step 4: Run tests and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/reviewed-authoring-evidence.test.ts
git add web/apps/console/src/presentation/authoring/reviewed-authoring-evidence.ts web/apps/console/src/presentation/authoring/reviewed-authoring-evidence.test.ts
git commit -m "feat: capture reviewed authoring evidence"
```

### Task 2: Correct The Prepared Recording And Storyboard

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/authoring-recording.ts`
- Modify: `web/apps/console/src/presentation/authoring/authoring-recording.test.ts`
- Modify: `web/apps/console/src/presentation/authoring/authoring-projection.ts`
- Modify: `web/apps/console/src/presentation/authoring/authoring-projection.test.ts`
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`

**Interfaces:**
- Consumes: `reviewedAuthoringEvidenceFor()` from Task 1.
- Produces: factual command transcript and `PreparedLifecycleStepProjection.evidence`.

- [x] **Step 1: Write failing factual tests**

Replace obsolete assertions with:

```ts
expect(diagnose.primaryCommand.title).toBe("workflow.draft_workspaces.validate");
expect(diagnose.primaryCommand.detail).toContain("missing_outcome_edge");
expect(repair.primaryCommand.title).toBe("workflow.draft_workspaces.set_route");
expect(repair.primaryCommand.command).toContain("--revision 3 --step analyze --outcome ok --to __end__");
expect(diagnose.evidence.kind).toBe("diagnostic");
expect(repair.evidence.kind).toBe("repair");
```

Assert storyboard captions mention a missing `ok` route and a route repair, and do not mention a missing output projection.

- [x] **Step 2: Run focused tests and verify RED**

Run the authoring recording, projection, and storyboard tests.

- [x] **Step 3: Update the validate recording**

Use:

```ts
{
  title: "workflow.draft_workspaces.validate",
  command: "wf draft validate lda_report_workflow",
  summary: "Validate the workflow draft",
  result: "diagnostic",
  detail: "missing_outcome_edge at nodes[analyze]: reachable node is missing edges for outcomes ['ok']",
}
```

and:

```ts
{
  title: "workflow.draft_workspaces.set_route",
  command: "wf draft set-route lda_report_workflow --revision 3 --step analyze --outcome ok --to __end__",
  summary: "Restore the missing terminal route",
  result: "success",
  detail: "Revision 4 validates with status valid and diagnostics [].",
}
```

Change proof strings to `missing_outcome_edge`, `analyze.ok -> __end__`, and `revision 4: valid`.

- [x] **Step 4: Project reviewed evidence per presentation step**

Add `readonly evidence: ReviewedAuthoringEvidence` to `PreparedLifecycleStepProjection` and populate it with `reviewedAuthoringEvidenceFor(step)`. Stop constructing the obsolete `repair` visual with hardcoded output-map text; either replace `visual` with the evidence union or derive the visual from `evidence` in one place.

- [x] **Step 5: Update storyboard captions**

Use:

```text
Validation returns a structured diagnostic because analyze has no route for its ok outcome.
One route edit sends analyze.ok to __end__; the follow-up validation is valid.
```

- [x] **Step 6: Run focused tests and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/authoring-recording.test.ts src/presentation/authoring/authoring-projection.test.ts src/presentation/storyboard.test.ts
git add web/apps/console/src/presentation/authoring web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts
git commit -m "fix: use factual prepared validation evidence"
```

### Task 3: Render Product-Like Scene 8 Results

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx`

**Interfaces:**
- Consumes: `PreparedLifecycleStepProjection.evidence`.
- Produces: accessible phase result regions with `data-authoring-result` values matching each evidence kind.

- [x] **Step 1: Write failing component tests**

Pin the following audience-visible facts:

```ts
expect(screen.getByRole("region", { name: /draft validation diagnostic/i }))
  .toHaveAttribute("data-authoring-result", "diagnostic");
expect(screen.getByText("missing_outcome_edge")).toBeInTheDocument();
expect(screen.getByText("nodes[analyze]")).toBeInTheDocument();
expect(screen.getByText(/missing edges for outcomes.*ok/i)).toBeInTheDocument();
```

For Repair, assert the full command is visible, the status reads `Valid`, revision `4` is visible, diagnostic count is `0`, and the invalid message is present only as compact prior context rather than the primary result.

Add one test per remaining phase for source count/capability contract, draft revision/steps/routes, immutable artifact identity, and runnable deployment bindings.

- [x] **Step 2: Run component tests and verify RED**

Run `AuthoringPhaseVisual.test.tsx` and `PreparedAuthoringLifecycleScene.test.tsx`.

- [x] **Step 3: Implement a shared result header and six evidence renderers**

Use one local `ResultHeader` component with icon, label, status, and optional revision. Render semantic `dl` rows for identifiers and counts, a plain list for sources/bindings, and `code` for commands/paths. Keep icons from the existing Lucide dependency: `Database`, `Workflow`, `AlertTriangle`, `Route`, `CheckCircle2`, `LockKeyhole`, and `Link2`.

Diagnose hierarchy:

```text
INVALID DRAFT · REVISION 3
missing_outcome_edge
nodes[analyze]
reachable node is missing edges for outcomes ['ok']
The workflow cannot prove where execution goes next.
```

Repair hierarchy:

```text
ROUTE REPAIR
missing_outcome_edge · nodes[analyze]
wf draft set-route ... --to __end__
VALID · REVISION 4 · 0 DIAGNOSTICS
```

- [x] **Step 4: Preserve the phase boundary in the scene wrapper**

Pass the full step projection to `AuthoringPhaseVisual`; do not make the visual infer Diagnose versus Repair from CSS alone. Retain `data-authoring-step`, `data-recording-phase`, and the stable assistant/frame sibling structure.

- [x] **Step 5: Run focused tests and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AuthoringPhaseVisual.test.tsx src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx
git add web/apps/console/src/presentation/authoring
git commit -m "feat: render Scene 8 product evidence"
```

### Task 4: Style The Product Results Without Reintroducing Overflow

**Files:**
- Modify: `web/apps/console/src/presentation/presentation.css`
- Modify: `web/apps/console/src/presentation/presentation-css.test.ts`

**Interfaces:**
- Consumes: `data-authoring-result` hooks from Task 3.
- Produces: responsive editorial result layouts within the existing full-height frame.

- [x] **Step 1: Add failing CSS contract tests**

Assert that:

- the result root uses `min-height: 0` and `overflow: auto`;
- Diagnose uses a single primary diagnostic column rather than hidden sibling cards;
- Repair uses a command band followed by a valid-result row;
- status is not communicated by color alone;
- no wide `56vh` cap or content-sized scene row returns; and
- the discussion rail remains transparent and borderless.

- [x] **Step 2: Run CSS tests and verify RED**

Run `presentation-css.test.ts` directly.

- [x] **Step 3: Implement restrained result styling**

Use the existing editorial paper, ink, muted, rule, success, and amber tokens. Use one structural rule between result sections, no wide shadow, no nested rounded cards, and `font-mono` only for commands, codes, paths, IDs, and revisions. Give Diagnose and Repair enough scale to fill the right frame without stretching single lines across the full width.

At narrow canvas widths, stack result metadata above the main evidence while preserving internal scrolling. Do not change the outer Scene 8 grid or assistant width in this task.

- [x] **Step 4: Run tests and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-css.test.ts src/presentation/authoring/AuthoringPhaseVisual.test.tsx
git add web/apps/console/src/presentation/presentation.css web/apps/console/src/presentation/presentation-css.test.ts
git commit -m "style: compose Scene 8 product results"
```

### Task 5: Route Smoke, Full Verification, And Docs Closure

**Files:**
- Modify if assertions need factual correction: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `docs/current_roadmap.md`
- Archived at: `docs/historical/superpowers/plans/2026-07-13-scene-8-product-evidence.md`

**Interfaces:**
- Consumes: completed Scene 8 evidence implementation.
- Produces: route-level regression coverage and accurate roadmap state.

- [x] **Step 1: Add direct-hash route assertions**

For `#scene/prepared-lifecycle/diagnose`, assert `missing_outcome_edge`, `nodes[analyze]`, and no `missing output projection`. For Repair, assert the exact set-route command and `Valid` revision `4` result.

- [x] **Step 2: Run the complete presentation test set**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
npx react-doctor@latest --verbose --scope changed
git diff --check
```

Expected: all tests pass, typecheck/build succeed, React Doctor reports no regression, and diff check is clean.

- [x] **Step 3: Perform browser smoke at three viewport sizes**

Capture all six routes at `1280x720`, `1024x768`, and `1920x1080`:

```text
#scene/prepared-lifecycle/discover
#scene/prepared-lifecycle/draft
#scene/prepared-lifecycle/diagnose
#scene/prepared-lifecycle/repair
#scene/prepared-lifecycle/artifact
#scene/prepared-lifecycle/deployment
```

For each viewport, confirm the scene and document do not overflow, the right result fills the available stage, the chat transcript scrolls internally, the composer remains anchored, and the discussion rail has no enclosing panel background/border.

- [x] **Step 4: Mark the roadmap item completed and archive the plan**

Record the reviewed diagnostic code and route repair in the completion note. Update links to the historical plan path.

- [x] **Step 5: Commit closure**

```powershell
git add web/apps/console/src/presentation/PresentationRoute.test.tsx docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-13-scene-8-product-evidence.md
git commit -m "docs: complete Scene 8 product evidence"
```
