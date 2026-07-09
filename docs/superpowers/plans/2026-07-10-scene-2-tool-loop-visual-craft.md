# Scene 2 Tool Loop Visual Craft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Scene 2 visually explain the problem: a chat/tool loop can solve one task, but reusable automation needs a durable workflow artifact.

**Architecture:** Keep Scene 2 isolated inside `ProblemLoopScene`. Replace the current dark-row transcript and equal-weight right card with two deliberately different artifacts: a compact chat transcript on the left and a durable workflow blueprint on the right. Do not change storyboard order, demo scenes, chat framework, or shared presentation runtime.

**Tech Stack:** React 19, TypeScript, Vite, existing presentation CSS, Vitest + Testing Library, Playwright screenshot smoke.

## Global Constraints

- Only touch Scene 2 implementation, Scene 2 tests, shared opening primitive tests if required, presentation CSS, and roadmap/docs.
- Do not add dependencies.
- Do not introduce assistant-ui, shadcn/ui, AI SDK, Radix, lucide, or icon packages.
- Do not change `/console`.
- Do not change Scene 1 or Scenes 3-14.
- Keep the left side vertical; chat/tool loops are turn-based, not left-to-right pipelines.
- Keep the right side as reusable automation using simple verbs: `design`, `save`, `connect`, `run`, `inspect`.
- Do not use formal lifecycle words in Scene 2 body: `Draft`, `Artifact`, `Deployment`, `Trace`.
- Keep Scene 2 readable at `1280x720` and `1024x768`.
- Avoid huge serif/card headings inside the scene body. Stage heading can remain; internal labels should feel like product UI.

---

## File Structure

- Modify `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`
  - Add local structured data for transcript turns and workflow blueprint steps.
  - Render the left artifact as a chat transcript with message/tool/observation visual roles.
  - Render the right artifact as a durable automation blueprint with a compact step rail plus proof chips.
- Modify `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`
  - Replace duplicate label-only tests with structure tests for transcript roles, durable blueprint, and forbidden formal lifecycle words.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Replace the current Scene 2 card/row styling with a distinct transcript and blueprint layout.
- Modify `docs/current_roadmap.md`
  - Mark the Scene 2 craft pass completed after implementation.
- Move this plan to `docs/historical/superpowers/plans/` after completion.

---

### Task 1: Strengthen Scene 2 DOM Contract

**Files:**
- Modify: `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`

**Interfaces:**
- Consumes:
  - `ProblemLoopScene(scene: SceneDefinition, beat: SceneBeatDefinition)`.
- Produces:
  - Tests that enforce a chat/tool transcript and durable workflow blueprint.

- [ ] **Step 1: Replace duplicate tests with structural tests**

Replace the contents of `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx` with:

```tsx
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { ProblemLoopScene } from "./ProblemLoopScene.js";

const problemScene = findScene("problem")!;

afterEach(() => cleanup());

describe("ProblemLoopScene", () => {
  it("renders the direct-action side as a chat-style tool transcript", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "direct-actions")!} />);

    const transcript = screen.getByRole("list", { name: /one-off chat and tool transcript/i });
    const turns = within(transcript).getAllByRole("listitem");

    expect(turns).toHaveLength(5);
    expect(turns[0]).toHaveAttribute("data-turn-kind", "user");
    expect(turns[1]).toHaveAttribute("data-turn-kind", "assistant");
    expect(turns[2]).toHaveAttribute("data-turn-kind", "tool");
    expect(turns[3]).toHaveAttribute("data-turn-kind", "observation");
    expect(turns[4]).toHaveAttribute("data-turn-kind", "answer");
    expect(within(transcript).getByText("User")).toBeInTheDocument();
    expect(within(transcript).getByText("Tool call")).toBeInTheDocument();
    expect(within(transcript).getByText("Observation")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /^Action sequence$/i })).not.toBeInTheDocument();
  });

  it("renders reusable automation as a durable workflow blueprint", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "missing-contracts")!} />);

    const blueprint = screen.getByRole("group", { name: /durable workflow blueprint/i });
    expect(blueprint).toHaveAttribute("data-blueprint-active", "true");

    for (const label of ["design", "save", "connect", "run", "inspect"]) {
      expect(within(blueprint).getByText(label)).toBeInTheDocument();
    }

    expect(within(blueprint).getByText("schemas")).toBeInTheDocument();
    expect(within(blueprint).getByText("bindings")).toBeInTheDocument();
    expect(within(blueprint).getByText("records")).toBeInTheDocument();
  });

  it("keeps Scene 2 body out of formal lifecycle vocabulary", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "missing-contracts")!} />);

    for (const formalName of ["Draft", "Artifact", "Deployment", "Trace"]) {
      expect(screen.queryByText(formalName)).not.toBeInTheDocument();
    }
  });
});
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ProblemLoopScene.test.tsx
```

Expected: FAIL because the component does not yet expose `data-turn-kind`, transcript label `one-off chat and tool transcript`, `data-blueprint-active`, or the proof chips.

- [ ] **Step 3: Commit failing tests**

```bash
git add web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx
git commit -m "test: specify Scene 2 tool-loop visual contract"
```

---

### Task 2: Recompose Scene 2 Markup

**Files:**
- Modify: `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`

**Interfaces:**
- Consumes:
  - Existing `ConceptNode` and `ConceptRail` from `ConceptPrimitives.tsx`.
- Produces:
  - Left artifact: `.problem-chat-card` containing `ol.problem-chat-transcript`.
  - Right artifact: `.problem-blueprint` with `role="group"` and `aria-label="durable workflow blueprint"`.

- [ ] **Step 1: Replace local data with richer turn and proof data**

In `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`, replace `toolLoopTurns` with:

```tsx
const toolLoopTurns = [
  {
    kind: "user",
    label: "User",
    detail: "Can you finish this workspace task?",
  },
  {
    kind: "assistant",
    label: "Assistant",
    detail: "Plans the next direct action.",
  },
  {
    kind: "tool",
    label: "Tool call",
    detail: "Runs one operation against the workspace.",
  },
  {
    kind: "observation",
    label: "Observation",
    detail: "Reads the result and decides what to do next.",
  },
  {
    kind: "answer",
    label: "Answer",
    detail: "Reports success, but leaves no reusable workflow behind.",
  },
] as const;

const automationProof = ["schemas", "bindings", "records"] as const;
```

- [ ] **Step 2: Replace the returned scene body**

Keep the `StageCaption` and final evidence paragraph. Replace the `<section className="problem-loop-scene" ...>` contents with:

```tsx
<section className="problem-loop-scene" aria-label="chat tool loop versus reusable automation">
  <article
    className="problem-chat-card"
    data-problem-active={automationBeat ? "false" : "true"}
    aria-label="one-off chat and tool loop"
  >
    <header className="problem-artifact-header">
      <span>One-off</span>
      <h2>Chat + tool loop</h2>
      <p>Good at getting through one request.</p>
    </header>
    <ol className="problem-chat-transcript" aria-label="one-off chat and tool transcript">
      {toolLoopTurns.map((turn) => (
        <li key={turn.kind} className="problem-chat-turn" data-turn-kind={turn.kind}>
          <span className="problem-chat-turn__label">{turn.label}</span>
          <p>{turn.detail}</p>
        </li>
      ))}
    </ol>
    <p className="problem-artifact-note">The useful work lives in the conversation history.</p>
  </article>

  <div className="problem-loop-scene__bridge" aria-hidden="true">→</div>

  <article
    className="problem-blueprint"
    role="group"
    aria-label="durable workflow blueprint"
    data-blueprint-active={automationBeat ? "true" : "false"}
  >
    <header className="problem-artifact-header">
      <span>Reusable</span>
      <h2>Workflow blueprint</h2>
      <p>Good at preserving how the work should run again.</p>
    </header>
    <ConceptRail label="Reusable automation">
      <ConceptNode title="design" icon="design" emphasis={automationBeat ? "primary" : "normal"} />
      <ConceptNode title="save" icon="save" emphasis={automationBeat ? "primary" : "normal"} />
      <ConceptNode title="connect" icon="connect" emphasis={automationBeat ? "primary" : "normal"} />
      <ConceptNode title="run" icon="run" emphasis={automationBeat ? "primary" : "normal"} />
      <ConceptNode title="inspect" icon="inspect" emphasis={automationBeat ? "primary" : "normal"} />
    </ConceptRail>
    <ul className="problem-blueprint__proof" aria-label="reusable automation proof points">
      {automationProof.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  </article>
</section>
```

- [ ] **Step 3: Run Scene 2 tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ProblemLoopScene.test.tsx
```

Expected: PASS.

- [ ] **Step 4: Commit markup**

```bash
git add web/apps/console/src/presentation/opening/ProblemLoopScene.tsx
git commit -m "feat: recompose Scene 2 as chat loop and workflow blueprint"
```

---

### Task 3: Replace Scene 2 Visual Styling

**Files:**
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes:
  - `.problem-chat-card`
  - `.problem-chat-transcript`
  - `.problem-chat-turn`
  - `.problem-blueprint`
  - `.problem-blueprint__proof`
- Produces:
  - Scene 2 visually differentiates ephemeral chat history from durable workflow artifact.

- [ ] **Step 1: Add CSS contract tests using existing DOM tests**

No new test file is needed. The DOM tests from Task 1 enforce stable class/attribute names. This task is visually verified with screenshots in Task 4.

- [ ] **Step 2: Replace old Scene 2 CSS**

In `web/apps/console/src/presentation/presentation.css`, replace the existing block from `/* Problem loop scene */` through the `@container presentation-canvas (max-width: 1050px)` block with:

```css
/* Problem loop scene */
.problem-loop-scene {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(24rem, 0.95fr) auto minmax(26rem, 1.05fr);
  align-items: stretch;
  gap: 1rem;
}

.problem-chat-card,
.problem-blueprint {
  min-width: 0;
  border: 1px solid color-mix(in oklch, var(--stage-line) 62%, transparent);
  border-radius: 0.95rem;
  padding: 0.85rem;
}

.problem-chat-card {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 0.65rem;
  background:
    linear-gradient(180deg, color-mix(in oklch, var(--stage-inset) 94%, black), var(--stage-inset));
}

.problem-blueprint {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 0.75rem;
  background:
    radial-gradient(circle at 12% 16%, color-mix(in oklch, var(--accent-cyan) 13%, transparent), transparent 30%),
    color-mix(in oklch, var(--stage-surface) 88%, black);
}

.problem-chat-card[data-problem-active="false"],
.problem-blueprint[data-blueprint-active="false"] {
  opacity: 0.62;
}

.problem-artifact-header {
  display: grid;
  gap: 0.18rem;
}

.problem-artifact-header span {
  color: var(--accent-cyan);
  font: 700 0.68rem/1 var(--font-evidence);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.problem-artifact-header h2 {
  margin: 0;
  color: var(--text-primary);
  font: 800 1.45rem/0.98 var(--font-interface);
}

.problem-artifact-header p,
.problem-artifact-note {
  margin: 0;
  color: var(--text-secondary);
  font: 0.86rem/1.3 var(--font-interface);
}

.problem-chat-transcript {
  display: grid;
  align-content: start;
  gap: 0.45rem;
  min-height: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.problem-chat-turn {
  display: grid;
  grid-template-columns: 5.8rem minmax(0, 1fr);
  gap: 0.65rem;
  align-items: start;
  border: 1px solid color-mix(in oklch, var(--stage-line) 62%, transparent);
  border-radius: 0.55rem;
  background: color-mix(in oklch, var(--stage-canvas) 72%, transparent);
  padding: 0.46rem 0.55rem;
}

.problem-chat-turn[data-turn-kind="tool"] {
  border-color: color-mix(in oklch, var(--accent-cyan) 44%, var(--stage-line));
  background: color-mix(in oklch, var(--accent-cyan) 9%, var(--stage-canvas));
}

.problem-chat-turn[data-turn-kind="observation"] {
  border-style: dashed;
}

.problem-chat-turn__label {
  color: var(--accent-cyan);
  font: 700 0.68rem/1.1 var(--font-evidence);
}

.problem-chat-turn p {
  margin: 0;
  color: var(--text-primary);
  font: 0.79rem/1.25 var(--font-interface);
}

.problem-blueprint .concept-rail {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  align-items: stretch;
}

.problem-blueprint .concept-node {
  grid-template-columns: 1fr;
  justify-items: center;
  text-align: center;
  padding: 0.72rem 0.45rem;
}

.problem-blueprint .concept-node__copy span,
.problem-blueprint .concept-node__meta {
  display: none;
}

.problem-blueprint__proof {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.problem-blueprint__proof li {
  border: 1px solid color-mix(in oklch, var(--accent-cyan) 36%, var(--stage-line));
  border-radius: 999px;
  color: var(--text-primary);
  background: color-mix(in oklch, var(--accent-cyan) 9%, transparent);
  padding: 0.25rem 0.55rem;
  font: 700 0.72rem/1 var(--font-evidence);
}

.problem-loop-scene__bridge {
  align-self: center;
  color: var(--accent-cyan);
  font: 800 2rem/1 var(--font-interface);
}

@container presentation-canvas (max-width: 1050px) {
  .problem-loop-scene {
    grid-template-columns: 1fr;
  }

  .problem-loop-scene__bridge {
    display: none;
  }
}
```

- [ ] **Step 3: Remove stale selectors**

After replacing the block, run:

```bash
rg -n 'problem-loop-scene__side|problem-loop-transcript|problem-loop-transcript__turn' web/apps/console/src/presentation/presentation.css
```

Expected: no matches. If matches remain, remove the stale rules.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ProblemLoopScene.test.tsx src/presentation/SceneBody.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit CSS**

```bash
git add web/apps/console/src/presentation/presentation.css
git commit -m "style: craft Scene 2 transcript and blueprint visuals"
```

---

### Task 4: Visual Smoke, Docs, And Archive

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-10-scene-2-tool-loop-visual-craft.md` to `docs/historical/superpowers/plans/2026-07-10-scene-2-tool-loop-visual-craft.md`

**Interfaces:**
- Consumes:
  - New Scene 2 transcript and blueprint from Tasks 2-3.
- Produces:
  - Screenshot evidence and roadmap completion entry.

- [ ] **Step 1: Run Scene 2 and presentation tests**

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

- [ ] **Step 4: Capture screenshots**

Run with the dev server running at `http://127.0.0.1:5173`:

```bash
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/problem/direct-actions" web/apps/console/.visual-smoke/scene-2-craft-actions-1280.png
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/problem/missing-contracts" web/apps/console/.visual-smoke/scene-2-craft-automation-1280.png
pnpm dlx playwright screenshot --viewport-size="1024,768" "http://127.0.0.1:5173/present#scene/problem/direct-actions" web/apps/console/.visual-smoke/scene-2-craft-actions-1024.png
pnpm dlx playwright screenshot --viewport-size="1024,768" "http://127.0.0.1:5173/present#scene/problem/missing-contracts" web/apps/console/.visual-smoke/scene-2-craft-automation-1024.png
```

Expected:
- The left side reads as a chat/tool transcript, not abstract rows.
- The right side reads as a durable artifact, not another equal chat card.
- Internal headings are smaller than the slide title.
- No body text is clipped.
- At `1024x768`, the two artifacts stack cleanly.

- [ ] **Step 5: Update roadmap**

Modify `docs/current_roadmap.md` under `Recommended next visual slices` by adding this line after the completed coherence pass entry:

```md
3. Completed: Scene 2 visual craft pass made the one-off side read as a
   chat/tool transcript and the reusable side read as a durable workflow
   blueprint, while preserving simple vocabulary and 720p readability.
   Implementation:
   [`Scene 2 tool-loop visual craft`](historical/superpowers/plans/2026-07-10-scene-2-tool-loop-visual-craft.md).
```

Renumber following entries in that short list if needed.

- [ ] **Step 6: Archive this plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-10-scene-2-tool-loop-visual-craft.md docs/historical/superpowers/plans/2026-07-10-scene-2-tool-loop-visual-craft.md
```

- [ ] **Step 7: Commit docs/archive**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-10-scene-2-tool-loop-visual-craft.md
git commit -m "docs: complete Scene 2 visual craft"
```

---

## Self-Review Checklist

- Spec coverage:
  - Left side vertical chat/tool transcript: Tasks 1-3.
  - Right side durable workflow blueprint: Tasks 1-3.
  - Simple verbs preserved: Task 1 tests.
  - No formal lifecycle words in Scene 2 body: Task 1 tests.
  - 720p and 1024x768 screenshot gates: Task 4.
  - No dependencies: Global constraints and no package files listed.
- Placeholder scan:
  - No unresolved placeholder markers or vague implementation steps.
- Type consistency:
  - `toolLoopTurns.kind` values match the `data-turn-kind` assertions.
  - `problem-blueprint` uses `data-blueprint-active`, matching tests and CSS.
- Scope check:
  - This plan only changes Scene 2 visual craft. Evaluation, conclusion, chat framework, and demo proof scenes remain separate slices.
