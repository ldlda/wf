# Presentation Coherence Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make presentation mode feel like one coherent product demo instead of a pile of individually fixed scenes.

**Architecture:** Add a small scene-coherence model that states what each scene is allowed to emphasize, then use it to guide two visible corrections: Scene 2 becomes a chat/tool-loop transcript instead of a left-to-right pipeline, and Scenes 8-12 expose stable product-flow surface metadata for visual hierarchy. This pass does not introduce new UI frameworks; it tightens existing React components and CSS.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind 4 tokens already present in `editorial.css`, existing presentation CSS, Vitest + Testing Library, Playwright screenshot smoke.

## Global Constraints

- Do not add shadcn/ui, assistant-ui, AI SDK, Radix, lucide, or any other dependency.
- Do not change `/console`.
- Do not rewrite the storyboard order.
- Do not redesign baseline-good Scenes 3, 4, and 5.
- Keep chat secondary unless a beat is actively narrating, approving, or showing trace context.
- Each scene gets one primary artifact and at most one support surface.
- Preserve existing hash routes.
- Preserve current keyboard navigation.
- Keep 720p readability as the main constraint.
- Screenshot verification must include `1280x720` and `1024x768` for affected scenes.

---

## File Structure

- Create `web/apps/console/src/presentation/presentation-coherence.ts`
  - Defines the scene matrix and helper functions.
  - Gives future workers one place to inspect what each scene should visually prioritize.
- Create `web/apps/console/src/presentation/presentation-coherence.test.ts`
  - Pins coverage for all 14 scenes and checks that each scene has one primary artifact.
- Modify `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`
  - Replaces the left-side abstract tile rail with a vertical chat/tool transcript.
- Modify `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`
  - Pins the transcript metaphor and keeps the reusable-automation side in simple language.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
  - Adds `data-primary-surface` and `data-support-surface` from the coherence model.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
  - Pins surface metadata for Scenes 8-12.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Adds transcript styling and surface-hierarchy CSS for the demo scenes.
- Modify `docs/current_roadmap.md`
  - Mark this coherence pass completed after implementation.
- Move this plan to `docs/historical/superpowers/plans/` after completion.

---

### Task 1: Scene Coherence Matrix

**Files:**
- Create: `web/apps/console/src/presentation/presentation-coherence.ts`
- Create: `web/apps/console/src/presentation/presentation-coherence.test.ts`

**Interfaces:**
- Produces:
  - `type PrimaryArtifact`
  - `type SupportSurface`
  - `type ChatRole`
  - `type SceneCoherenceEntry`
  - `sceneCoherenceMatrix: readonly SceneCoherenceEntry[]`
  - `coherenceForScene(sceneId: string): SceneCoherenceEntry`
  - `demoSurfaceForBeat(sceneId: string, beatId: string): { readonly primarySurface: string; readonly supportSurface: string }`
- Consumes:
  - `scenes` from `web/apps/console/src/presentation/storyboard.ts`

- [ ] **Step 1: Write failing tests for matrix coverage and constraints**

Create `web/apps/console/src/presentation/presentation-coherence.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { scenes } from "./storyboard.js";
import {
  coherenceForScene,
  demoSurfaceForBeat,
  sceneCoherenceMatrix,
} from "./presentation-coherence.js";

describe("presentation coherence matrix", () => {
  it("covers every storyboard scene exactly once", () => {
    const sceneIds = scenes.map((scene) => scene.id);
    const matrixIds = sceneCoherenceMatrix.map((entry) => entry.sceneId);

    expect(matrixIds).toEqual(sceneIds);
    expect(new Set(matrixIds).size).toBe(sceneIds.length);
  });

  it("gives every scene one primary artifact and at most one support surface", () => {
    for (const scene of scenes) {
      const entry = coherenceForScene(scene.id);

      expect(entry.primaryArtifact.length).toBeGreaterThan(0);
      expect(entry.supportSurface).not.toContain("+");
      expect(entry.chatRole).toMatch(/^(hidden|narration|approval|trace)$/);
    }
  });

  it("keeps baseline scenes 3 through 5 stable", () => {
    expect(coherenceForScene("positioning")).toMatchObject({
      primaryArtifact: "positioning-map",
      supportSurface: "discussion-rail",
      chatRole: "hidden",
    });
    expect(coherenceForScene("planner-runtime")).toMatchObject({
      primaryArtifact: "boundary-diagram",
      supportSurface: "discussion-rail",
      chatRole: "hidden",
    });
    expect(coherenceForScene("lifecycle")).toMatchObject({
      primaryArtifact: "lifecycle-rail",
      supportSurface: "current-state-panel",
      chatRole: "hidden",
    });
  });

  it("classifies demo beats into one primary surface and one support surface", () => {
    expect(demoSurfaceForBeat("run-from-deployment", "graph")).toEqual({
      primarySurface: "workflow-graph",
      supportSurface: "run-receipt",
    });
    expect(demoSurfaceForBeat("typed-human-boundary", "approval")).toEqual({
      primarySurface: "interrupt-approval",
      supportSurface: "facts-only",
    });
    expect(demoSurfaceForBeat("resume-output-evidence", "trace")).toEqual({
      primarySurface: "trace-evidence",
      supportSurface: "output-summary",
    });
  });
});
```

- [ ] **Step 2: Run matrix tests and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-coherence.test.ts
```

Expected: FAIL because `presentation-coherence.js` does not exist.

- [ ] **Step 3: Implement coherence matrix**

Create `web/apps/console/src/presentation/presentation-coherence.ts`:

```ts
export type PrimaryArtifact =
  | "opening-decomposition"
  | "tool-loop-transcript"
  | "positioning-map"
  | "boundary-diagram"
  | "lifecycle-rail"
  | "interactive-architecture"
  | "authoring-loop"
  | "agent-handoff"
  | "prepared-lifecycle"
  | "workflow-graph"
  | "interrupt-approval"
  | "trace-evidence"
  | "evaluation-board"
  | "future-work-map";

export type SupportSurface =
  | "none"
  | "discussion-rail"
  | "current-state-panel"
  | "run-receipt"
  | "facts-only"
  | "output-summary";

export type ChatRole = "hidden" | "narration" | "approval" | "trace";

export type SceneCoherenceEntry = {
  readonly sceneId: string;
  readonly primaryArtifact: PrimaryArtifact;
  readonly supportSurface: SupportSurface;
  readonly chatRole: ChatRole;
  readonly presenterFocus: string;
};

export const sceneCoherenceMatrix = [
  {
    sceneId: "thesis",
    primaryArtifact: "opening-decomposition",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Move from AI-agent ambition to the submitted workflow substrate.",
  },
  {
    sceneId: "problem",
    primaryArtifact: "tool-loop-transcript",
    supportSurface: "none",
    chatRole: "hidden",
    presenterFocus: "Contrast a one-off agent/tool loop with reusable automation requirements.",
  },
  {
    sceneId: "positioning",
    primaryArtifact: "positioning-map",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Place the system among scripts, tool loops, hosted automation, MCP, and agent graphs.",
  },
  {
    sceneId: "planner-runtime",
    primaryArtifact: "boundary-diagram",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Show that external planners propose while the runtime validates and records.",
  },
  {
    sceneId: "lifecycle",
    primaryArtifact: "lifecycle-rail",
    supportSurface: "current-state-panel",
    chatRole: "hidden",
    presenterFocus: "Explain Draft -> Artifact -> Deployment -> Run as the durable lifecycle.",
  },
  {
    sceneId: "architecture",
    primaryArtifact: "interactive-architecture",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Use the recursive architecture figure as the only primary artifact.",
  },
  {
    sceneId: "authoring",
    primaryArtifact: "authoring-loop",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Show the authoring loop without turning it into generic process cards.",
  },
  {
    sceneId: "agent-handoff",
    primaryArtifact: "agent-handoff",
    supportSurface: "none",
    chatRole: "narration",
    presenterFocus: "Introduce the prepared operator flow only as a bridge into product proof.",
  },
  {
    sceneId: "prepared-lifecycle",
    primaryArtifact: "prepared-lifecycle",
    supportSurface: "none",
    chatRole: "hidden",
    presenterFocus: "Show the prepared workflow before execution starts.",
  },
  {
    sceneId: "run-from-deployment",
    primaryArtifact: "workflow-graph",
    supportSurface: "run-receipt",
    chatRole: "hidden",
    presenterFocus: "Start a persisted run from a deployment and keep the graph dominant.",
  },
  {
    sceneId: "typed-human-boundary",
    primaryArtifact: "interrupt-approval",
    supportSurface: "facts-only",
    chatRole: "approval",
    presenterFocus: "Show the typed interrupt, selected issues, and operator decision.",
  },
  {
    sceneId: "resume-output-evidence",
    primaryArtifact: "trace-evidence",
    supportSurface: "output-summary",
    chatRole: "trace",
    presenterFocus: "Show resume, output, and trace as evidence from the same run.",
  },
  {
    sceneId: "evaluation",
    primaryArtifact: "evaluation-board",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Summarize evaluation as bounded evidence, not a model leaderboard.",
  },
  {
    sceneId: "conclusion",
    primaryArtifact: "future-work-map",
    supportSurface: "discussion-rail",
    chatRole: "narration",
    presenterFocus: "End on boundary and future layers without overclaiming an autonomous agent.",
  },
] as const satisfies readonly SceneCoherenceEntry[];

export const coherenceForScene = (sceneId: string): SceneCoherenceEntry => {
  const entry = sceneCoherenceMatrix.find((candidate) => candidate.sceneId === sceneId);
  if (!entry) {
    throw new Error(`No presentation coherence entry for scene ${sceneId}`);
  }
  return entry;
};

export const demoSurfaceForBeat = (
  sceneId: string,
  beatId: string,
): { readonly primarySurface: string; readonly supportSurface: string } => {
  if (sceneId === "prepared-lifecycle") {
    return { primarySurface: "prepared-lifecycle", supportSurface: "none" };
  }
  if (sceneId === "run-from-deployment") {
    return {
      primarySurface: beatId === "operation" ? "run-operation" : "workflow-graph",
      supportSurface: beatId === "operation" ? "none" : "run-receipt",
    };
  }
  if (sceneId === "typed-human-boundary") {
    return {
      primarySurface: beatId === "interrupt" ? "interrupt-payload" : "interrupt-approval",
      supportSurface: "facts-only",
    };
  }
  if (sceneId === "resume-output-evidence") {
    if (beatId === "resume") return { primarySurface: "resume-decision", supportSurface: "output-summary" };
    if (beatId === "output") return { primarySurface: "workflow-output", supportSurface: "none" };
    return { primarySurface: "trace-evidence", supportSurface: "output-summary" };
  }
  return { primarySurface: "none", supportSurface: "none" };
};
```

- [ ] **Step 4: Run matrix tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/presentation-coherence.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit matrix**

```bash
git add web/apps/console/src/presentation/presentation-coherence.ts web/apps/console/src/presentation/presentation-coherence.test.ts
git commit -m "feat: define presentation coherence matrix"
```

---

### Task 2: Replace Scene 2 Pipeline With Tool-Loop Transcript

**Files:**
- Modify: `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`
- Modify: `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes:
  - `ConceptNode` and `ConceptRail` from `ConceptPrimitives.tsx`.
- Produces:
  - Scene 2 left side reads as a vertical conversation/tool loop, not a deterministic pipeline.
  - Existing `ProblemLoopScene` export remains unchanged.

- [ ] **Step 1: Write failing tests for transcript metaphor**

Modify `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx` to include:

```tsx
it("shows direct action as a vertical chat and tool transcript", () => {
  render(<ProblemLoopScene scene={problemScene} beat={problemScene.beats[0]!} />);

  const transcript = screen.getByRole("list", { name: /one-off tool loop transcript/i });
  expect(within(transcript).getByText("User prompt")).toBeInTheDocument();
  expect(within(transcript).getByText("Agent reasoning")).toBeInTheDocument();
  expect(within(transcript).getByText("Tool call")).toBeInTheDocument();
  expect(within(transcript).getByText("Observation")).toBeInTheDocument();
  expect(within(transcript).getByText("Final answer")).toBeInTheDocument();
  expect(screen.queryByRole("group", { name: /^Action sequence$/i })).not.toBeInTheDocument();
});

it("keeps reusable automation as the durable counterpart without formal lifecycle words", () => {
  render(<ProblemLoopScene scene={problemScene} beat={problemScene.beats[1]!} />);

  expect(screen.getByRole("group", { name: /reusable automation/i })).toBeInTheDocument();
  expect(screen.getByText("design")).toBeInTheDocument();
  expect(screen.getByText("save")).toBeInTheDocument();
  expect(screen.getByText("connect")).toBeInTheDocument();
  expect(screen.getByText("run")).toBeInTheDocument();
  expect(screen.getByText("inspect")).toBeInTheDocument();
  expect(screen.queryByText("Draft")).not.toBeInTheDocument();
  expect(screen.queryByText("Artifact")).not.toBeInTheDocument();
  expect(screen.queryByText("Deployment")).not.toBeInTheDocument();
  expect(screen.queryByText("Trace")).not.toBeInTheDocument();
});
```

If this test file does not already import `within`, update the import:

```tsx
import { cleanup, render, screen, within } from "@testing-library/react";
```

- [ ] **Step 2: Run Scene 2 tests and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ProblemLoopScene.test.tsx
```

Expected: FAIL because the transcript list does not exist and the old `Action sequence` concept rail still exists.

- [ ] **Step 3: Replace the left side with transcript markup**

Modify `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`.

Add this local data near the top of the file:

```tsx
const toolLoopTurns = [
  { role: "User prompt", detail: "Do this workspace task once." },
  { role: "Agent reasoning", detail: "Decides the next action." },
  { role: "Tool call", detail: "Runs an operation directly." },
  { role: "Observation", detail: "Reads the result." },
  { role: "Final answer", detail: "Reports success, but keeps no reusable lifecycle." },
] as const;
```

Replace the first `.problem-loop-scene__side` body with:

```tsx
<div
  className="problem-loop-scene__side problem-loop-scene__side--transcript"
  data-problem-active={automationBeat ? "false" : "true"}
>
  <h2>One-off tool loop</h2>
  <ol className="problem-loop-transcript" aria-label="one-off tool loop transcript">
    {toolLoopTurns.map((turn) => (
      <li key={turn.role} className="problem-loop-transcript__turn">
        <span>{turn.role}</span>
        <p>{turn.detail}</p>
      </li>
    ))}
  </ol>
  <p>Useful once. Hard to reuse.</p>
</div>
```

Keep the reusable automation side as the right side.

- [ ] **Step 4: Add transcript CSS**

Modify `web/apps/console/src/presentation/presentation.css`.

Add after the existing `.problem-loop-scene__side p` rule:

```css
.problem-loop-scene__side--transcript {
  align-self: stretch;
}

.problem-loop-transcript {
  display: grid;
  gap: 0.45rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.problem-loop-transcript__turn {
  display: grid;
  grid-template-columns: 7.5rem minmax(0, 1fr);
  gap: 0.65rem;
  align-items: start;
  border: 1px solid color-mix(in oklch, var(--stage-line) 66%, transparent);
  border-radius: 0.65rem;
  background: color-mix(in oklch, var(--stage-surface) 88%, transparent);
  padding: 0.5rem 0.6rem;
}

.problem-loop-transcript__turn span {
  color: var(--accent-cyan);
  font: 700 0.72rem/1.15 var(--font-evidence);
}

.problem-loop-transcript__turn p {
  color: var(--text-primary);
  font: 0.8rem/1.25 var(--font-interface);
}
```

- [ ] **Step 5: Run Scene 2 tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ProblemLoopScene.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Scene 2 metaphor fix**

```bash
git add web/apps/console/src/presentation/opening/ProblemLoopScene.tsx web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "fix: make presentation problem scene read as tool loop"
```

---

### Task 3: Attach Coherence Metadata To Demo Scenes

**Files:**
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes:
  - `demoSurfaceForBeat(sceneId: string, beatId: string)` from Task 1.
- Produces:
  - `.demo-workflow-stage` has `data-primary-surface` and `data-support-surface`.
  - CSS can consistently reduce secondary panels instead of local one-off layout rules.

- [ ] **Step 1: Write failing metadata tests for demo scenes**

Modify `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx` to add:

```tsx
it("marks graph beats with one primary workflow graph and one run receipt support surface", () => {
  renderDemoWorkflowScene({
    sceneId: "run-from-deployment",
    beatId: "graph",
  });

  const stage = screen.getByLabelText(/demo workflow stage/i);
  expect(stage).toHaveAttribute("data-primary-surface", "workflow-graph");
  expect(stage).toHaveAttribute("data-support-surface", "run-receipt");
});

it("marks approval beats as interrupt approval with facts-only support", () => {
  renderDemoWorkflowScene({
    sceneId: "typed-human-boundary",
    beatId: "approval",
  });

  const stage = screen.getByLabelText(/demo workflow stage/i);
  expect(stage).toHaveAttribute("data-primary-surface", "interrupt-approval");
  expect(stage).toHaveAttribute("data-support-surface", "facts-only");
});

it("marks trace beats as trace evidence with output summary support", () => {
  renderDemoWorkflowScene({
    sceneId: "resume-output-evidence",
    beatId: "trace",
  });

  const stage = screen.getByLabelText(/demo workflow stage/i);
  expect(stage).toHaveAttribute("data-primary-surface", "trace-evidence");
  expect(stage).toHaveAttribute("data-support-surface", "output-summary");
});
```

If this test file does not have a helper named `renderDemoWorkflowScene`, add one near existing render helpers:

```tsx
const renderDemoWorkflowScene = ({
  sceneId,
  beatId,
}: {
  readonly sceneId: string;
  readonly beatId: string;
}) => {
  const scene = findScene(sceneId)!;
  const beat = findBeat(sceneId, beatId)!;
  return render(
    <DemoWorkflowScene
      scene={scene}
      beat={beat}
      demo={demoController}
      selectedNodeId={null}
      selectNode={vi.fn()}
      openEvidence={vi.fn()}
    />,
  );
};
```

Use the existing demo controller fixture name if it differs from `demoController`; do not create a second fixture if the file already has one.

- [ ] **Step 2: Run demo scene tests and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx
```

Expected: FAIL because the stage lacks the new data attributes.

- [ ] **Step 3: Add demo surface metadata**

Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`.

Add import:

```ts
import { demoSurfaceForBeat } from "./presentation-coherence.js";
```

Inside `DemoWorkflowScene`, after `const layout = layoutForBeat(beat.id);`, add:

```ts
  const surface = demoSurfaceForBeat(scene.id, beat.id);
```

Change the stage element to:

```tsx
      <div
        className="demo-workflow-stage"
        data-beat={beat.id}
        data-demo-layout={layout}
        data-primary-surface={surface.primarySurface}
        data-support-surface={surface.supportSurface}
        aria-label="demo workflow stage"
      >
```

- [ ] **Step 4: Add hierarchy CSS for support surfaces**

Modify `web/apps/console/src/presentation/presentation.css`.

Add near demo workflow scene CSS:

```css
.demo-workflow-stage[data-support-surface="run-receipt"] .operation-block[data-operation-variant="receipt"],
.demo-workflow-stage[data-support-surface="output-summary"] .run-facts-card[data-output-priority="summary"] {
  opacity: 0.86;
}

.demo-workflow-stage[data-primary-surface="interrupt-approval"] .guided-product-moment__header,
.demo-workflow-stage[data-primary-surface="trace-evidence"] .guided-product-moment__header {
  border-color: color-mix(in oklch, var(--accent-cyan) 38%, var(--stage-line));
}
```

If `OperationBlock` does not expose `data-operation-variant`, add this attribute in `OperationBlock.tsx`:

```tsx
data-operation-variant={variant}
```

and add a focused test in `OperationBlock.test.tsx`:

```tsx
expect(screen.getByRole("article", { name: /workflow operation/i })).toHaveAttribute("data-operation-variant", "receipt");
```

- [ ] **Step 5: Run demo tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx src/presentation/OperationBlock.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit demo metadata**

```bash
git add web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/OperationBlock.tsx web/apps/console/src/presentation/OperationBlock.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: mark presentation demo surface hierarchy"
```

If `OperationBlock.tsx` and `OperationBlock.test.tsx` were not needed, omit them from `git add`.

---

### Task 4: Coherence Verification And Roadmap

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-10-presentation-coherence-pass.md` to `docs/historical/superpowers/plans/2026-07-10-presentation-coherence-pass.md`

**Interfaces:**
- Consumes:
  - Scene coherence matrix from Task 1.
  - Scene 2 transcript from Task 2.
  - Demo surface metadata from Task 3.
- Produces:
  - Roadmap entry documenting the completed coherence pass.
  - Visual smoke screenshots for affected scenes.

- [ ] **Step 1: Run focused presentation tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation
```

Expected: PASS.

- [ ] **Step 2: Run typecheck**

Run:

```bash
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

- [ ] **Step 3: Run build**

Run:

```bash
pnpm --dir web --filter @lda/console build
```

Expected: PASS. The existing Vite chunk-size warning is acceptable.

- [ ] **Step 4: Capture screenshot smoke**

Run with the dev server already running at `http://127.0.0.1:5173`:

```bash
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/problem/direct-actions" web/apps/console/.visual-smoke/coherence-02-actions-1280.png
pnpm dlx playwright screenshot --viewport-size="1024,768" "http://127.0.0.1:5173/present#scene/problem/direct-actions" web/apps/console/.visual-smoke/coherence-02-actions-1024.png
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/run-from-deployment/graph" web/apps/console/.visual-smoke/coherence-09-graph-1280.png
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/typed-human-boundary/approval" web/apps/console/.visual-smoke/coherence-10-approval-1280.png
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/resume-output-evidence/trace" web/apps/console/.visual-smoke/coherence-12-trace-1280.png
```

Expected:
- Scene 2 left side looks like a vertical chat/tool transcript.
- Scene 9 graph remains the first thing the viewer sees.
- Scene 10 approval shows factual input/interruption/decision without output dominating before submit.
- Scene 12 trace shows trace evidence as the primary artifact.

- [ ] **Step 5: Update roadmap**

Modify `docs/current_roadmap.md` under `Recommended next visual slices`:

```md
2. Completed: Presentation coherence pass added a 14-scene visual matrix,
   corrected Scene 2's direct-action metaphor into a chat/tool transcript, and
   marked demo beats with primary/support surface metadata so Scenes 8-12 can
   keep one dominant product proof at a time. Implementation:
   [`presentation coherence pass`](historical/superpowers/plans/2026-07-10-presentation-coherence-pass.md).
```

- [ ] **Step 6: Archive this plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-10-presentation-coherence-pass.md docs/historical/superpowers/plans/2026-07-10-presentation-coherence-pass.md
```

- [ ] **Step 7: Commit docs/archive**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-10-presentation-coherence-pass.md
git commit -m "docs: complete presentation coherence pass"
```

---

## Self-Review Checklist

- Spec coverage:
  - 14-scene matrix: Task 1.
  - Scene 2 no longer left-to-right pipeline: Task 2.
  - Chat remains secondary: Task 1 `chatRole` and no chat dependency changes.
  - Scenes 8-12 product-flow hierarchy: Task 3.
  - Screenshot gates: Task 4.
  - No new dependencies: Global constraints and no package files listed.
- Placeholder scan:
  - No unresolved placeholder markers or vague implementation steps.
- Type consistency:
  - `SceneCoherenceEntry`, `coherenceForScene`, and `demoSurfaceForBeat` are defined in Task 1 and consumed in Task 3.
  - `primarySurface` and `supportSurface` attribute names are consistent across tests and implementation.
- Scope check:
  - This pass does not finish all visual work. It creates coherence rules and fixes the most misleading metaphor plus demo hierarchy. Evaluation and conclusion visuals remain a separate future slice.
