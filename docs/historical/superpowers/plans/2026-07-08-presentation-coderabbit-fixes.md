# Presentation CodeRabbit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve still-valid CodeRabbit findings from `random shit/rabbitreview/pih.txt` without mixing correctness fixes with broader visual redesign.

**Architecture:** Treat the presentation as three independent surfaces: reducer/state correctness, agent/timeline lifecycle correctness, and presentational accessibility/figure data integrity. Keep the first slice small enough to test and commit safely; defer larger chat/visual/data-model cleanup into follow-up slices.

**Tech Stack:** React 19, TypeScript, Vite/Vitest, React Flow, Motion, Valibot, Effect-backed RPC package, Markdown docs.

## Global Constraints

- Work from repo root unless a command explicitly uses `--dir web`.
- Before editing docs, follow `docs/AGENTS.md`; completed plans move to `docs/historical/superpowers/plans/`.
- Keep changes minimal: fix only verified current issues from the review.
- Use tests for behavior changes; do not rely on visual inspection for reducer or hook semantics.
- Do not duplicate canvas/container CSS if `styles/editorial.css` already owns the wrapper setup.

---

## Execution Status

Completed on 2026-07-08. The implementation fixed the still-valid correctness, accessibility, lifecycle, figure-validation, and stale-doc findings. Deferred items are intentionally not hidden:

- `PresentationCanvas` container findings were stale; `styles/editorial.css` already owns the positioned viewport, absolute canvas, transform origin, and `presentation-canvas` container.
- Full reuse of `FigureNodeView` inside React Flow nodes was deferred; the accessibility behavior is now covered by tests, and the component split can be handled in a later refactor.
- Broader scene visual redesign remains separate from review-fix work.

### Task 1: Correctness And Accessibility Fixes

**Files:**
- Modify: `web/apps/console/src/presentation/presentation-state.ts`
- Modify: `web/apps/console/src/presentation/presentation-state.test.ts`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Modify: `web/apps/console/src/demo/agent/useDemoAgent.ts`
- Modify: `web/apps/console/src/demo/agent/useDemoAgent.test.tsx`
- Modify: `web/apps/console/src/presentation/DiscussionPanel.tsx`
- Modify: `web/apps/console/src/presentation/DiscussionPanel.test.tsx`

**Interfaces:**
- Produces: `createInitialPresentationState(): PresentationState`
- Produces: `selectNode(nodeId: string | null): void` throughout presentation components
- Produces: modal keyboard behavior in `DiscussionPanel`

- [x] **Step 1: Add failing reducer tests**

  Add tests proving `jump_hash` into `#discuss/...` clears `evidencePresentationOverride`, `select_node` accepts `null`, and fresh state uses a new `startedAt`.

- [x] **Step 2: Update reducer types and initialization**

  Narrow `jump` to `MainLocation`, add `createInitialPresentationState`, allow nullable `select_node`, and clear evidence override for discussion deep links.

- [x] **Step 3: Add failing agent lifecycle tests**

  Add tests proving unmount/reset aborts a pending approval and that normal approval resolution removes the abort listener lifecycle.

- [x] **Step 4: Harden `useDemoAgent` approval cleanup**

  Track the active approval request as one object with `resolve`, `reject`, `signal`, and `abortHandler`; only clear refs for the matching active request.

- [x] **Step 5: Add modal behavior to `DiscussionPanel`**

  Align with `EvidenceInspector`: `aria-modal`, initial focus, focus trap, Escape close, and focus restoration.

- [x] **Step 6: Run focused tests and commit**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/presentation-state.test.ts src/demo/agent/useDemoAgent.test.tsx src/presentation/DiscussionPanel.test.tsx
  pnpm --dir web --filter @lda/console typecheck
  ```

  Commit message: `fix: harden presentation state and agent lifecycle`.

### Task 2: Figure Data And Keyboard Integrity

**Files:**
- Modify: `web/apps/console/src/presentation/figures/catalog.ts`
- Modify: `web/apps/console/src/presentation/figures/catalog.test.ts`
- Modify: `web/apps/console/src/presentation/figures/InteractiveFigure.tsx`
- Modify: `web/apps/console/src/presentation/figures/InteractiveFigure.test.tsx`
- Modify: `web/apps/console/src/presentation/figures/FigureNodeView.tsx`
- Modify: `web/apps/console/src/presentation/figures/interactive-figure.css`
- Modify: `web/apps/console/src/presentation/scenes/ArchitectureScene.tsx`
- Modify: `web/apps/console/src/presentation/scenes/ArchitectureScene.test.tsx`

**Interfaces:**
- Produces: catalog issue `missing_explicit_position`
- Produces: roving tab order based on focused node, not active marker

- [x] **Step 1: Validate explicit layout positions**

  Add a catalog test for an explicit layout missing one node position, then add `missing_explicit_position` to `FigureCatalogIssue` and `issueToCode`.

- [x] **Step 2: Fix figure keyboard entry**

  Add a test that a figure with `activeNodeId={null}` has exactly one tabbable node. Drive `tabIndex` from focused-node state and fall back to the first node.

- [x] **Step 3: Fix affordance selector typo**

  Rename `figure-node__expand-affance` to `figure-node__expand-affordance` in both CSS and renderers.

- [x] **Step 4: Resolve architecture catalog by beat metadata**

  Use `beat.figure?.catalogId` to select the catalog. If no known catalog matches, render the architecture catalog as a safe fallback.

- [x] **Step 5: Run focused tests and commit**

  Run:

  ```bash
  pnpm --dir web --filter @lda/console test -- src/presentation/figures/catalog.test.ts src/presentation/figures/InteractiveFigure.test.tsx src/presentation/scenes/ArchitectureScene.test.tsx
  pnpm --dir web --filter @lda/console typecheck
  ```

  Commit message: `fix: validate presentation figures`.

### Task 3: Docs And Deferred Cleanup

**Files:**
- Modify: `docs/superpowers/specs/2026-07-03-constrained-demo-agent-design.md`
- Modify: `web/apps/console/src/demo/agent/recipes.ts`
- Modify: `web/apps/console/src/demo/agent/preparedRecipeDriver.ts`
- Modify: `web/apps/console/src/demo/useDemoTimeline.ts`
- Modify: `web/apps/console/src/presentation/DiscussionPanel.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`
- Modify: `web/apps/console/src/presentation/WorkflowGraphStage.tsx`

**Interfaces:**
- Produces: docs that use `EvidenceInspector`, not `EvidenceDrawer`
- Produces: prepared recipe step inputs instead of hardcoded `review_issues`
- Produces: unique SVG marker IDs in `WorkflowGraphStage`

- [x] **Step 1: Refresh stale spec terms**

  Rename `EvidenceDrawer` to `EvidenceInspector` in the flow diagram and update the prepared-recipe section to say `requestApproval` gates the typed review step.

- [x] **Step 2: Remove small data hardcodes**

  Derive recipe tool names from shared tool types, move the selected workflow node into recipe step data, and render discussion branch details from branch data when that model is ready.

- [x] **Step 3: Add missing branch tests**

  Add `OperatorChat` tests for approval, error, presentation action, prepared handoff, and fallback messages.

- [x] **Step 4: Run full web verification and archive plan**

  Run:

  ```bash
  pnpm --dir web test
  pnpm --dir web typecheck
  pnpm --dir web build
  git diff --check
  ```

  Move this plan to `docs/historical/superpowers/plans/` and commit.

## Review Notes

- Canvas/container findings are stale if `web/apps/console/src/presentation/styles/editorial.css` remains imported by the presentation route; it already provides positioned viewport, absolute canvas, transform origin, and `container-name: presentation-canvas`.
- The visual quality of scenes 6, 7, and 10 is not solved by this review-fix plan. Treat those as a separate presentation design pass.
