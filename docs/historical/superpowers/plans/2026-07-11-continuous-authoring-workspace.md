# Continuous Authoring Workspace Implementation Plan

Status: Completed on 2026-07-11.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Scenes 8 and 9 as one continuous assistant conversation that synchronizes prepared tool activity with five factual workflow-authoring projections.

**Architecture:** The prepared authoring recording remains the single source of truth. A pure projector emits stable assistant messages and identifies the active phase tool group; Scene 8 renders that thread full-stage, while Scene 9 renders the same thread in a bottom dock beneath one phase-specific product visual. The separate trace modal and presentation receipt are removed.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing assistant-ui tool fallback/group primitives, React Flow where graph structure earns it, CSS, Vite, Playwright CLI.

## Global Constraints

- Keep the authoring evidence deterministic and explicitly prepared; do not add an LLM backend or authoring RPC calls.
- Use only verified public `wf` CLI syntax.
- Preserve stable message IDs and tool-call IDs across Scene 8 and Scene 9.
- Scene 9 chat occupies at most 30 percent of the 1280 by 720 stage.
- Do not use a modal, detached receipt, blur transition, pan transition, or scale transition for the thread.
- Use source-owned assistant-ui primitives for chat and tool-call interactions.
- Respect reduced motion and the existing presentation motion toggle.
- Preserve Scenes 10 through 12.

---

### Task 1: Project One Stable Authoring Conversation

**Files:**

- Modify: `web/apps/console/src/demo/agent/tools.ts`
- Modify: `web/apps/console/src/presentation/authoring/authoring-recording.ts`
- Modify: `web/apps/console/src/presentation/authoring/authoring-recording.test.ts`
- Modify: `web/apps/console/src/presentation/authoring/authoring-projection.ts`
- Modify: `web/apps/console/src/presentation/authoring/authoring-projection.test.ts`

**Interfaces:**

- Add `runWorkflowCommand` to `AgentToolName`.
- Produce `projectPreparedAuthoringThread(throughPhase?: AuthoringPhaseId): readonly AgentMessage[]`.
- Produce `authoringToolGroupId(phase: AuthoringPhaseId): string`.

- [ ] **Step 1: Write failing stable-ID and phase-boundary tests**

```ts
const full = projectPreparedAuthoringThread("deployment");
const draft = projectPreparedAuthoringThread("draft");
expect(draft.map(({ id }) => id)).toEqual(full.slice(0, draft.length).map(({ id }) => id));
expect(draft.flatMap(({ parts }) => parts).some((part) =>
  part.type === "tool-call" && part.call.name === "runWorkflowCommand"
)).toBe(true);
expect(authoringToolGroupId("validate")).toBe("authoring-validate");
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `pnpm --dir web --filter @lda/console test -- src/presentation/authoring/authoring-recording.test.ts src/presentation/authoring/authoring-projection.test.ts`

Expected: FAIL because the thread projector and authoring tool are absent.

- [ ] **Step 3: Implement the projection from the existing recording**

For each phase, emit one assistant message containing narration followed by paired `tool-call`/`tool-result` parts for every recorded command. Use IDs derived only from phase and command index, for example `authoring-draft-command-1`. Tool input is `{ command, summary }`; result is `{ status, detail }`. Keep the request and operator constraint as user messages.

- [ ] **Step 4: Run tests and typecheck**

Run: `pnpm --dir web --filter @lda/console test -- src/presentation/authoring/authoring-recording.test.ts src/presentation/authoring/authoring-projection.test.ts`

Run: `pnpm --dir web --filter @lda/console typecheck`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/apps/console/src/demo/agent/tools.ts web/apps/console/src/presentation/authoring
git commit -m "feat: project prepared authoring conversation"
```

### Task 2: Give the Assistant Thread a Controlled Dock Mode

**Files:**

- Modify: `web/apps/console/src/presentation/chat/AssistantOperatorThread.tsx`
- Modify: `web/apps/console/src/presentation/chat/AssistantOperatorThread.test.tsx`
- Create: `web/apps/console/src/presentation/authoring/AuthoringConversation.tsx`
- Create: `web/apps/console/src/presentation/authoring/AuthoringConversation.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Add optional `activeToolGroupId?: string` and `surface?: "stage" | "dock"` props to `AssistantOperatorThread`.
- Produce `AuthoringConversation({ throughPhase, surface, activePhase })`.

- [ ] **Step 1: Write failing full-thread and dock tests**

```tsx
render(<AuthoringConversation throughPhase="validate" surface="dock" activePhase="validate" />);
expect(screen.getByRole("log", { name: "prepared authoring conversation" })).toHaveAttribute("data-surface", "dock");
expect(screen.getByRole("button", { name: /validate.*tool calls/i })).toHaveAttribute("aria-expanded", "true");
expect(screen.getByRole("button", { name: /draft.*tool calls/i })).toHaveAttribute("aria-expanded", "false");
```

- [ ] **Step 2: Run tests and verify red**

Run: `pnpm --dir web --filter @lda/console test -- src/presentation/chat/AssistantOperatorThread.test.tsx src/presentation/authoring/AuthoringConversation.test.tsx`

- [ ] **Step 3: Implement controlled phase groups**

Group tool pairs by their `authoring-<phase>` prefix. Use controlled `open` on `ToolGroupRoot` only for the active phase; preserve manual expansion in component state after initial synchronization. Label group triggers with phase plus count, not only `N tool calls`. Keep individual tool fallbacks collapsed by default.

- [ ] **Step 4: Implement full-stage and dock CSS**

The stage surface fills its region and reads like a normal assistant thread. The dock uses a fixed-height internal viewport, compact message spacing, and a top rule rather than another card. Transition only `height`/grid track over 200 ms; reduced motion sets transition duration to effectively zero.

- [ ] **Step 5: Verify and commit**

Run the two focused test files and typecheck. Commit:

```bash
git add web/apps/console/src/presentation/chat web/apps/console/src/presentation/authoring web/apps/console/src/presentation/presentation.css
git commit -m "feat: add synchronized authoring chat dock"
```

### Task 3: Render Five Factual Phase Visuals

**Files:**

- Create: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.tsx`
- Create: `web/apps/console/src/presentation/authoring/AuthoringPhaseVisual.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/authoring-projection.ts`
- Modify: `web/apps/console/src/presentation/authoring/authoring-projection.test.ts`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Extend `AuthoringPhaseProjection` with a discriminated `visual` union for `discover`, `draft`, `validate`, `artifact`, and `deployment`.
- Produce `AuthoringPhaseVisual({ projection })` with `role="region"` and phase-specific accessible labels.

- [ ] **Step 1: Write failing tests for all five visual contracts**

```ts
expect(projectPreparedAuthoringPhase("discover").visual).toMatchObject({ kind: "inventory" });
expect(projectPreparedAuthoringPhase("draft").visual).toMatchObject({ kind: "graph" });
expect(projectPreparedAuthoringPhase("validate").visual).toMatchObject({ kind: "repair" });
expect(projectPreparedAuthoringPhase("artifact").visual).toMatchObject({ kind: "artifact" });
expect(projectPreparedAuthoringPhase("deployment").visual).toMatchObject({ kind: "bindings" });
```

Render tests must assert source/capability/schema facts, graph nodes and route labels, diagnostic and corrected projection, immutable artifact ID/version, and all three concrete bindings.

- [ ] **Step 2: Run tests and verify red**

Run: `pnpm --dir web --filter @lda/console test -- src/presentation/authoring/authoring-projection.test.ts src/presentation/authoring/AuthoringPhaseVisual.test.tsx`

- [ ] **Step 3: Implement the discriminated projection and visuals**

Use familiar product forms rather than five matching cards: inventory rows for discovery; compact directed graph for draft; before/after diagnostic for validation; identity plate for artifact; binding table for deployment. Use icons from the existing Lucide dependency for source, schema, route, artifact, and binding cues. Keep cyan limited to the active fact or route.

- [ ] **Step 4: Verify and commit**

Run the focused tests and typecheck. Commit:

```bash
git add web/apps/console/src/presentation/authoring web/apps/console/src/presentation/presentation.css
git commit -m "feat: visualize prepared authoring phases"
```

### Task 4: Compose Scenes 8 And 9 as One Workspace

**Files:**

- Modify: `web/apps/console/src/presentation/authoring/AgentHandoffScene.tsx`
- Modify: `web/apps/console/src/presentation/authoring/AgentHandoffScene.test.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.tsx`
- Modify: `web/apps/console/src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx`
- Delete: `web/apps/console/src/presentation/authoring/AuthoringTracePanel.tsx`
- Delete: `web/apps/console/src/presentation/authoring/AuthoringTracePanel.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**

- Scene 8 renders `AuthoringConversation` with `surface="stage"`.
- Scene 9 renders `AuthoringPhaseVisual` above `AuthoringConversation` with `surface="dock"` and the current beat as `activePhase`.

- [ ] **Step 1: Write failing composition tests**

Assert Scene 8 contains user, assistant, and tool-call content. Assert every Scene 9 beat contains exactly one phase visual and the same conversation log. Assert no `Agent trace` button or `Authoring trace` dialog exists.

- [ ] **Step 2: Run focused scene tests and verify red**

Run: `pnpm --dir web --filter @lda/console test -- src/presentation/authoring/AgentHandoffScene.test.tsx src/presentation/authoring/PreparedAuthoringLifecycleScene.test.tsx src/presentation/SceneBody.test.tsx`

- [ ] **Step 3: Implement the continuous composition**

Replace the receipt and modal with a two-row Scene 9 workspace. Keep the phase rail as a small orientation control above the visual. Ensure the full-stage and dock thread receive the exact same projected message IDs.

- [ ] **Step 4: Remove obsolete trace code and selectors**

Run `rg -n 'AuthoringTracePanel|prepared-lifecycle-scene__receipt|authoring-trace' web/apps/console/src`. Delete only obsolete files and CSS after the search confirms no remaining caller.

- [ ] **Step 5: Verify and commit**

Run focused tests, console typecheck, and console build. Commit:

```bash
git add web/apps/console/src/presentation
git commit -m "feat: compose continuous authoring workspace"
```

### Task 5: Browser Acceptance, Documentation, And Cleanup

**Files:**

- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move: this plan to `docs/historical/superpowers/plans/2026-07-11-continuous-authoring-workspace.md`

- [ ] **Step 1: Run the complete presentation verification**

Run: `pnpm --dir web --filter @lda/console test -- src/presentation`

Run: `pnpm --dir web --filter @lda/console typecheck`

Run: `pnpm --dir web --filter @lda/console build`

Run: `git diff --check`

- [ ] **Step 2: Browser-smoke the required routes**

Capture Scene 8 request/handoff and all five Scene 9 phases at 1280 by 720 and 1024 by 768. Store screenshots only under the ignored `web/apps/console/.visual-smoke/` directory. Verify no body overflow, no clipped dock, active tool group synchronization, and no console error other than the known favicon 404.

- [ ] **Step 3: Update live documentation**

Describe the continuous thread/dock behavior and distinguish prepared authoring evidence from live run execution. Mark the correction slice complete in the roadmap.

- [ ] **Step 4: Archive the plan and commit**

```bash
git add web/README.md docs/current_roadmap.md docs/superpowers/plans docs/historical/superpowers/plans
git commit -m "docs: complete continuous authoring workspace"
```

## Self-Review

- The plan replaces the modal/receipt contract rather than layering another surface over it.
- Stable IDs and one recording guarantee Scene 8/9 continuity.
- Each Scene 9 beat has a distinct factual product visual and one synchronized chat group.
- Tests cover data projection, assistant interaction, scene composition, routes, responsive layout, and the absence of obsolete modal behavior.
- No task introduces live LLM, composer, or authoring RPC behavior.
