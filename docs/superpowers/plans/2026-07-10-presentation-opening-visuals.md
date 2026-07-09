# Presentation Opening Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the text-heavy opening Scenes 1 and 2 with visual, icon-backed diagrams that explain the origin story: external agents can plan and call tools; the submitted work focuses on the workflow-platform/substrate layer that makes actions reusable.

**Architecture:** Keep this slice inside the existing React presentation app. Add small source-owned presentation primitives for concept icons and concept rails, then use them in two focused scene components. Do not introduce shadcn/ui in this slice: shadcn copies components into the source tree and requires project-wide conventions; it should be a separate component-system/chat cleanup decision, not a one-off opening-slide dependency.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind 4 tokens already present in `editorial.css`, existing presentation CSS, Vitest + Testing Library, Playwright screenshot smoke.

## Global Constraints

- Do not redesign Scenes 3, 4, or 5.
- Do not change the thesis title text.
- Do not add live LLM behavior.
- Do not rework the report workflow demo.
- Do not add named related-system comparisons before Scene 3.
- Do not introduce `wf` CLI branding in the opening.
- Use `Codex`, `Claude`, and `OpenCode` as planner examples.
- Prefer source-owned reusable presentation primitives for chips, icon plaques, timeline steps, and placeholder surfaces.
- Do not add shadcn/ui, lucide, Radix, assistant-ui, or AI SDK dependencies in this slice.
- Use icons and shapes, not text-only lists.
- Keep copy readable at 720p.
- Main slide body must stay confident; the “not a new autonomous planning algorithm” sentence belongs in speaker notes/Q&A, not the main visual.

---

## File Structure

- Create `web/apps/console/src/presentation/opening/ConceptPrimitives.tsx`
  - Owns small reusable presentation primitives:
    - `ConceptIcon`
    - `ConceptNode`
    - `ConceptRail`
  - These are source-owned placeholders aligned with future chat/product component language.
- Create `web/apps/console/src/presentation/opening/ConceptPrimitives.test.tsx`
  - Pins accessible labels and reusable rendering behavior.
- Create `web/apps/console/src/presentation/opening/OpeningThesisScene.tsx`
  - Owns Scene 1 title reveal and contribution focus.
- Create `web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx`
  - Pins planner/tool/platform decomposition, known agent names, submitted substrate block, and defense question rail availability.
- Create `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`
  - Owns Scene 2 action sequence vs reusable automation.
- Create `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`
  - Pins simple verbs and excludes formal lifecycle terms.
- Modify `web/apps/console/src/presentation/SceneBody.tsx`
  - Route `scene.id === "thesis"` to `OpeningThesisScene`.
  - Route `scene.id === "problem"` to `ProblemLoopScene`.
  - Leave other `narrative` scenes on `NarrativeScene`.
- Modify `web/apps/console/src/presentation/SceneBody.test.tsx`
  - Add integration checks for Scene 1 and Scene 2.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Add visual styles for opening primitives and scene layouts.
- Modify `docs/current_roadmap.md`
  - Mark the opening visual slice completed after implementation.
- Move this plan to `docs/historical/superpowers/plans/` after completion.

---

### Task 1: Source-Owned Concept Primitives

**Files:**
- Create: `web/apps/console/src/presentation/opening/ConceptPrimitives.tsx`
- Create: `web/apps/console/src/presentation/opening/ConceptPrimitives.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Produces:
  - `type ConceptIconName = "planner" | "tool" | "platform" | "think" | "toolCall" | "observe" | "done" | "design" | "save" | "connect" | "run" | "inspect"`
  - `ConceptIcon(props: { name: ConceptIconName; label: string }): JSX.Element`
  - `ConceptNode(props: { title: string; subtitle?: string; icon: ConceptIconName; emphasis?: "normal" | "primary" | "muted"; children?: React.ReactNode }): JSX.Element`
  - `ConceptRail(props: { label: string; children: React.ReactNode }): JSX.Element`
- Consumes: existing presentation CSS tokens from `.presentation-route`.

- [ ] **Step 1: Write failing primitive tests**

Create `web/apps/console/src/presentation/opening/ConceptPrimitives.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConceptIcon, ConceptNode, ConceptRail } from "./ConceptPrimitives.js";

describe("ConceptPrimitives", () => {
  it("renders labelled concept icons without external icon dependencies", () => {
    render(<ConceptIcon name="planner" label="Planner icon" />);

    expect(screen.getByRole("img", { name: "Planner icon" })).toBeInTheDocument();
  });

  it("renders concept nodes with stable emphasis attributes", () => {
    render(
      <ConceptNode title="Workflow Platform" subtitle="submitted substrate" icon="platform" emphasis="primary">
        <span>Typed · Durable · Inspectable</span>
      </ConceptNode>,
    );

    const node = screen.getByRole("group", { name: /Workflow Platform/i });
    expect(node).toHaveAttribute("data-concept-emphasis", "primary");
    expect(node).toHaveTextContent("submitted substrate");
    expect(node).toHaveTextContent("Typed · Durable · Inspectable");
  });

  it("renders a labelled concept rail", () => {
    render(
      <ConceptRail label="Reusable automation rail">
        <ConceptNode title="Design" icon="design" />
        <ConceptNode title="Run" icon="run" />
      </ConceptRail>,
    );

    expect(screen.getByRole("group", { name: "Reusable automation rail" })).toBeInTheDocument();
    expect(screen.getByText("Design")).toBeInTheDocument();
    expect(screen.getByText("Run")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run primitive tests and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ConceptPrimitives.test.tsx
```

Expected: FAIL because `ConceptPrimitives.tsx` does not exist.

- [ ] **Step 3: Implement concept primitives**

Create `web/apps/console/src/presentation/opening/ConceptPrimitives.tsx`:

```tsx
import type { ReactNode } from "react";

export type ConceptIconName =
  | "planner"
  | "tool"
  | "platform"
  | "think"
  | "toolCall"
  | "observe"
  | "done"
  | "design"
  | "save"
  | "connect"
  | "run"
  | "inspect";

type ConceptIconProps = {
  readonly name: ConceptIconName;
  readonly label: string;
};

const iconPathFor = (name: ConceptIconName): string => {
  if (name === "planner") return "M7 11c0-3 2-5 5-5s5 2 5 5-2 5-5 5-5-2-5-5Zm5-8v3m0 10v5M4 11H1m22 0h-3M6 4l2 2m10-2-2 2M6 18l2-2m10 2-2-2";
  if (name === "tool") return "M5 19h14M7 17V7l5-3 5 3v10M9 10h6M9 14h6";
  if (name === "platform") return "M4 7h16v10H4zM8 17v3m8-3v3M7 20h10M8 10h8m-8 3h5";
  if (name === "think") return "M8 15h8a4 4 0 0 0 0-8H9a5 5 0 0 0-1 10v3l3-3";
  if (name === "toolCall") return "M6 7h12M6 12h8M6 17h12M18 12l3 3-3 3";
  if (name === "observe") return "M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12Zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z";
  if (name === "done") return "M4 12l5 5L20 6";
  if (name === "design") return "M4 20l4-1 11-11-3-3L5 16l-1 4Zm10-14 3 3";
  if (name === "save") return "M5 4h12l2 2v14H5zM8 4v6h8V4M8 20v-6h8v6";
  if (name === "connect") return "M7 7h4v4H7zM13 13h4v4h-4zM11 9h3a3 3 0 0 1 3 3v1";
  if (name === "run") return "M7 5v14l12-7z";
  return "M3 11h18M5 5h14v14H5zM9 15h6";
};

export const ConceptIcon = ({ name, label }: ConceptIconProps) => (
  <svg className="concept-icon" role="img" aria-label={label} viewBox="0 0 24 24">
    <path d={iconPathFor(name)} />
  </svg>
);

type ConceptNodeProps = {
  readonly title: string;
  readonly subtitle?: string;
  readonly icon: ConceptIconName;
  readonly emphasis?: "normal" | "primary" | "muted";
  readonly children?: ReactNode;
};

export const ConceptNode = ({
  title,
  subtitle,
  icon,
  emphasis = "normal",
  children,
}: ConceptNodeProps) => (
  <article className="concept-node" role="group" aria-label={title} data-concept-emphasis={emphasis}>
    <ConceptIcon name={icon} label={`${title} icon`} />
    <div className="concept-node__copy">
      <strong>{title}</strong>
      {subtitle && <span>{subtitle}</span>}
      {children && <div className="concept-node__meta">{children}</div>}
    </div>
  </article>
);

type ConceptRailProps = {
  readonly label: string;
  readonly children: ReactNode;
};

export const ConceptRail = ({ label, children }: ConceptRailProps) => (
  <div className="concept-rail" role="group" aria-label={label}>
    {children}
  </div>
);
```

- [ ] **Step 4: Add primitive CSS**

Modify `web/apps/console/src/presentation/presentation.css` near the existing scene body styles:

```css
.concept-rail {
  display: flex;
  align-items: stretch;
  gap: 0.7rem;
  min-width: 0;
}

.concept-node {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 0.65rem;
  min-width: 0;
  border: 1px solid color-mix(in oklch, var(--stage-line) 72%, transparent);
  border-radius: 0.85rem;
  background: color-mix(in oklch, var(--stage-surface) 86%, transparent);
  padding: 0.72rem 0.82rem;
  color: var(--text-primary);
}

.concept-node[data-concept-emphasis="primary"] {
  border-color: var(--accent-cyan);
  background: color-mix(in oklch, var(--accent-cyan) 12%, var(--stage-surface));
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--accent-cyan) 18%, transparent);
}

.concept-node[data-concept-emphasis="muted"] {
  opacity: 0.62;
}

.concept-icon {
  width: 2rem;
  height: 2rem;
  color: var(--accent-cyan);
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.concept-node__copy {
  display: grid;
  gap: 0.12rem;
  min-width: 0;
}

.concept-node__copy strong {
  color: var(--text-primary);
  font: 750 0.96rem/1.05 var(--font-interface);
}

.concept-node__copy span {
  color: var(--text-secondary);
  font: 0.78rem/1.25 var(--font-interface);
}

.concept-node__meta {
  color: var(--accent-cyan);
  font: 700 0.72rem/1.2 var(--font-evidence);
}
```

- [ ] **Step 5: Run primitive tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ConceptPrimitives.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/presentation/opening/ConceptPrimitives.tsx web/apps/console/src/presentation/opening/ConceptPrimitives.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: add presentation concept primitives"
```

---

### Task 2: Scene 1 Opening Thesis Visual

**Files:**
- Create: `web/apps/console/src/presentation/opening/OpeningThesisScene.tsx`
- Create: `web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes:
  - `ConceptNode`, `ConceptRail` from `./opening/ConceptPrimitives.js`
  - `StageCaption`
  - `DiscussionLinks` remains internal in `SceneBody`; this scene does not own the Q&A rail.
- Produces:
  - `OpeningThesisScene(props: { scene: SceneDefinition; beat: SceneBeatDefinition }): JSX.Element`

- [ ] **Step 1: Write failing component test**

Create `web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { OpeningThesisScene } from "./OpeningThesisScene.js";

const thesisScene = findScene("thesis")!;

describe("OpeningThesisScene", () => {
  it("renders the title reveal with latent component icons", () => {
    render(<OpeningThesisScene scene={thesisScene} beat={findBeat("thesis", "title")!} />);

    expect(screen.getByRole("heading", { name: /Design and Implementation of lda\.chat/i })).toBeInTheDocument();
    expect(screen.getByText("Planner")).toBeInTheDocument();
    expect(screen.getByText("Tool Surface")).toBeInTheDocument();
    expect(screen.getByText("Workflow Platform")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Planner icon/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Tool Surface icon/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Workflow Platform icon/i })).toBeInTheDocument();
  });

  it("renders contribution focus without relying on lda.chat as category label", () => {
    render(<OpeningThesisScene scene={thesisScene} beat={findBeat("thesis", "substrate")!} />);

    expect(screen.getByText("Codex / Claude / OpenCode")).toBeInTheDocument();
    expect(screen.getByText("CLI / MCP / APIs")).toBeInTheDocument();
    expect(screen.getByText("submitted substrate")).toBeInTheDocument();
    expect(screen.getByText("Typed · Durable · Inspectable")).toBeInTheDocument();
    expect(screen.queryByText("wf")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run component test and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/OpeningThesisScene.test.tsx
```

Expected: FAIL because `OpeningThesisScene.tsx` does not exist.

- [ ] **Step 3: Implement opening thesis scene**

Create `web/apps/console/src/presentation/opening/OpeningThesisScene.tsx`:

```tsx
import { StageCaption } from "../StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";
import { ConceptNode, ConceptRail } from "./ConceptPrimitives.js";

type OpeningThesisSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

const title = "Design and Implementation of lda.chat";

export const OpeningThesisScene = ({ scene, beat }: OpeningThesisSceneProps) => {
  const contributionBeat = beat.id === "substrate";
  return (
    <>
      <StageCaption eyebrow="Origin story" title={title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section
        className="opening-thesis"
        aria-label="AI agent decomposition"
        data-opening-beat={beat.id}
      >
        <div className="opening-thesis__title-card">
          <span>AI agent for workspace workflows</span>
          <strong>{contributionBeat ? "Decomposed" : scene.title}</strong>
        </div>
        <ConceptRail label="AI agent components">
          <ConceptNode
            title="Planner"
            subtitle="Codex / Claude / OpenCode"
            icon="planner"
            emphasis={contributionBeat ? "muted" : "normal"}
          />
          <ConceptNode
            title="Tool Surface"
            subtitle="CLI / MCP / APIs"
            icon="tool"
            emphasis={contributionBeat ? "muted" : "normal"}
          />
          <ConceptNode
            title="Workflow Platform"
            subtitle="submitted substrate"
            icon="platform"
            emphasis="primary"
          >
            <span>Typed · Durable · Inspectable</span>
          </ConceptNode>
        </ConceptRail>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
```

- [ ] **Step 4: Add opening thesis CSS**

Append to `web/apps/console/src/presentation/presentation.css` near other scene styles:

```css
.opening-thesis {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(8rem, 0.85fr) auto;
  gap: 1rem;
  align-items: center;
}

.opening-thesis__title-card {
  display: grid;
  place-items: center;
  gap: 0.5rem;
  min-height: 10rem;
  border: 1px solid color-mix(in oklch, var(--stage-line) 54%, transparent);
  border-radius: 1rem;
  background:
    radial-gradient(circle at 30% 30%, color-mix(in oklch, var(--accent-cyan) 12%, transparent), transparent 34%),
    var(--stage-inset);
  text-align: center;
}

.opening-thesis__title-card span {
  color: var(--text-secondary);
  font: 700 0.85rem/1 var(--font-evidence);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.opening-thesis__title-card strong {
  max-width: 14ch;
  color: var(--text-primary);
  font: 800 clamp(2rem, 7vw, 4.8rem)/0.92 var(--font-editorial);
  text-wrap: balance;
}

.opening-thesis .concept-rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
```

- [ ] **Step 5: Wire SceneBody to Scene 1**

Modify `web/apps/console/src/presentation/SceneBody.tsx` imports:

```tsx
import { OpeningThesisScene } from "./opening/OpeningThesisScene.js";
```

Modify the `case "narrative":` branch:

```tsx
    case "narrative":
      if (scene.id === "thesis") return <OpeningThesisScene scene={scene} beat={beat} />;
      return <NarrativeScene scene={scene} beat={beat} />;
```

- [ ] **Step 6: Add SceneBody integration test for Scene 1**

Modify `web/apps/console/src/presentation/SceneBody.test.tsx` inside `describe("SceneBody", ...)`:

```tsx
  it("renders Scene 1 as an opening decomposition visual", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "thesis", beatId: "substrate", focusPath: [] };

    render(
      <SceneBody
        location={location}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    expect(screen.getByLabelText("AI agent decomposition")).toBeInTheDocument();
    expect(screen.getByText("submitted substrate")).toBeInTheDocument();
    expect(screen.getByText("Typed · Durable · Inspectable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /where is the ai agent/i })).toBeInTheDocument();
  });
```

- [ ] **Step 7: Run tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/OpeningThesisScene.test.tsx src/presentation/SceneBody.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add web/apps/console/src/presentation/opening/OpeningThesisScene.tsx web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: add presentation opening thesis visual"
```

---

### Task 3: Scene 2 Action Sequence Versus Reusable Automation

**Files:**
- Create: `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`
- Create: `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes:
  - `ConceptNode`, `ConceptRail` from `./opening/ConceptPrimitives.js`
  - `StageCaption`
- Produces:
  - `ProblemLoopScene(props: { scene: SceneDefinition; beat: SceneBeatDefinition }): JSX.Element`

- [ ] **Step 1: Write failing component test**

Create `web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { findBeat, findScene } from "../storyboard.js";
import { ProblemLoopScene } from "./ProblemLoopScene.js";

const problemScene = findScene("problem")!;

describe("ProblemLoopScene", () => {
  it("renders the action sequence as useful but insufficient", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "direct-actions")!} />);

    const action = screen.getByRole("group", { name: "Action sequence" });
    expect(within(action).getByText("think")).toBeInTheDocument();
    expect(within(action).getAllByText("tool")).toHaveLength(2);
    expect(within(action).getByText("observe")).toBeInTheDocument();
    expect(within(action).getByText("done")).toBeInTheDocument();
    expect(screen.getByText(/useful once/i)).toBeInTheDocument();
  });

  it("renders reusable automation with simple verbs only", () => {
    render(<ProblemLoopScene scene={problemScene} beat={findBeat("problem", "missing-contracts")!} />);

    const automation = screen.getByRole("group", { name: "Reusable automation" });
    for (const label of ["design", "save", "connect", "run", "inspect"]) {
      expect(within(automation).getByText(label)).toBeInTheDocument();
    }
    for (const formalName of ["Draft", "Artifact", "Deployment", "Trace"]) {
      expect(screen.queryByText(formalName)).not.toBeInTheDocument();
    }
  });
});
```

- [ ] **Step 2: Run component test and confirm failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ProblemLoopScene.test.tsx
```

Expected: FAIL because `ProblemLoopScene.tsx` does not exist.

- [ ] **Step 3: Implement problem loop scene**

Create `web/apps/console/src/presentation/opening/ProblemLoopScene.tsx`:

```tsx
import { StageCaption } from "../StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "../storyboard.js";
import { ConceptNode, ConceptRail } from "./ConceptPrimitives.js";

type ProblemLoopSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
};

export const ProblemLoopScene = ({ scene, beat }: ProblemLoopSceneProps) => {
  const automationBeat = beat.id === "missing-contracts";
  return (
    <>
      <StageCaption eyebrow="Problem shape" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section className="problem-loop-scene" aria-label="action sequence versus reusable automation">
        <div className="problem-loop-scene__side" data-problem-active={automationBeat ? "false" : "true"}>
          <h2>Action sequence</h2>
          <ConceptRail label="Action sequence">
            <ConceptNode title="think" icon="think" emphasis={automationBeat ? "muted" : "normal"} />
            <ConceptNode title="tool" icon="toolCall" emphasis={automationBeat ? "muted" : "normal"} />
            <ConceptNode title="observe" icon="observe" emphasis={automationBeat ? "muted" : "normal"} />
            <ConceptNode title="tool" icon="toolCall" emphasis={automationBeat ? "muted" : "normal"} />
            <ConceptNode title="done" icon="done" emphasis={automationBeat ? "muted" : "normal"} />
          </ConceptRail>
          <p>Useful once. Hard to reuse.</p>
        </div>

        <div className="problem-loop-scene__bridge" aria-hidden="true">→</div>

        <div className="problem-loop-scene__side" data-problem-active={automationBeat ? "true" : "false"}>
          <h2>Reusable automation</h2>
          <ConceptRail label="Reusable automation">
            <ConceptNode title="design" icon="design" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="save" icon="save" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="connect" icon="connect" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="run" icon="run" emphasis={automationBeat ? "primary" : "normal"} />
            <ConceptNode title="inspect" icon="inspect" emphasis={automationBeat ? "primary" : "normal"} />
          </ConceptRail>
          <p>The platform makes work reusable.</p>
        </div>
      </section>
      <p className="scene-body__evidence">{scene.evidencePointer}</p>
    </>
  );
};
```

- [ ] **Step 4: Add problem loop CSS**

Append to `web/apps/console/src/presentation/presentation.css` after the opening thesis CSS:

```css
.problem-loop-scene {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 1rem;
}

.problem-loop-scene__side {
  display: grid;
  gap: 0.8rem;
  min-width: 0;
  border: 1px solid color-mix(in oklch, var(--stage-line) 60%, transparent);
  border-radius: 1rem;
  background: var(--stage-inset);
  padding: 1rem;
}

.problem-loop-scene__side[data-problem-active="false"] {
  opacity: 0.62;
}

.problem-loop-scene__side h2 {
  margin: 0;
  color: var(--text-primary);
  font: 800 clamp(1.5rem, 3vw, 2.4rem)/0.95 var(--font-editorial);
}

.problem-loop-scene__side p {
  margin: 0;
  color: var(--text-secondary);
  font: 0.95rem/1.35 var(--font-interface);
}

.problem-loop-scene .concept-rail {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.problem-loop-scene .concept-node {
  grid-template-columns: 1fr;
  justify-items: center;
  text-align: center;
  padding: 0.7rem 0.45rem;
}

.problem-loop-scene .concept-node__copy span,
.problem-loop-scene .concept-node__meta {
  display: none;
}

.problem-loop-scene__bridge {
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

- [ ] **Step 5: Wire SceneBody to Scene 2**

Modify `web/apps/console/src/presentation/SceneBody.tsx` imports:

```tsx
import { ProblemLoopScene } from "./opening/ProblemLoopScene.js";
```

Modify the `case "narrative":` branch from Task 2:

```tsx
    case "narrative":
      if (scene.id === "thesis") return <OpeningThesisScene scene={scene} beat={beat} />;
      if (scene.id === "problem") return <ProblemLoopScene scene={scene} beat={beat} />;
      return <NarrativeScene scene={scene} beat={beat} />;
```

- [ ] **Step 6: Add SceneBody integration test for Scene 2**

Modify `web/apps/console/src/presentation/SceneBody.test.tsx`:

```tsx
  it("renders Scene 2 as action sequence versus reusable automation", () => {
    const location: PresentationLocation = { kind: "main", sceneId: "problem", beatId: "missing-contracts", focusPath: [] };

    render(
      <SceneBody
        location={location}
        demo={demo}
        selectedNodeId={null}
        selectNode={noop}
        openEvidence={noop}
        openDiscussion={noop}
        onFocusPathChange={noop}
        motionDisabled={false}
      />,
    );

    expect(screen.getByLabelText("action sequence versus reusable automation")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Action sequence" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Reusable automation" })).toBeInTheDocument();
    expect(screen.queryByText("Draft")).not.toBeInTheDocument();
    expect(screen.queryByText("Artifact")).not.toBeInTheDocument();
    expect(screen.queryByText("Deployment")).not.toBeInTheDocument();
  });
```

- [ ] **Step 7: Run tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/opening/ProblemLoopScene.test.tsx src/presentation/SceneBody.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add web/apps/console/src/presentation/opening/ProblemLoopScene.tsx web/apps/console/src/presentation/opening/ProblemLoopScene.test.tsx web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: add presentation problem visual"
```

---

### Task 4: Visual Smoke, Docs, And Archive

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-10-presentation-opening-visuals.md` to `docs/historical/superpowers/plans/2026-07-10-presentation-opening-visuals.md`

**Interfaces:**
- Consumes: Tasks 1-3 complete.
- Produces: completed roadmap entry and archived implementation plan.

- [ ] **Step 1: Run full presentation tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation
```

Expected: PASS. If route-level tests fail because text moved from narrative to diagrams, update tests to assert semantic labels (`AI agent decomposition`, `action sequence versus reusable automation`) rather than exact text position.

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

- [ ] **Step 4: Run React Doctor on changed React files**

Run from `web/apps/console`:

```bash
npx react-doctor@latest --verbose --scope changed
```

Expected: no new Critical/Important issues. Fix warnings if they are caused by this slice and are not false positives.

- [ ] **Step 5: Capture visual smoke screenshots**

Run:

```bash
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/thesis/title" web/apps/console/.visual-smoke/opening-01-title.png
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/thesis/substrate" web/apps/console/.visual-smoke/opening-01-substrate.png
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/problem/direct-actions" web/apps/console/.visual-smoke/opening-02-actions.png
pnpm dlx playwright screenshot --viewport-size="1280,720" "http://127.0.0.1:5173/present#scene/problem/missing-contracts" web/apps/console/.visual-smoke/opening-02-automation.png
```

Expected: screenshots render without blank areas, clipped text, or text-only walls. `.visual-smoke/` is ignored and should not be committed.

- [ ] **Step 6: Update roadmap**

Modify `docs/current_roadmap.md` under `Recommended next visual slices`:

```md
1. Completed: Opening visuals rebuilt Scenes 1 and 2 around concrete diagrams
   for "AI-agent pursuit -> workflow substrate" and "direct actions are not
   reusable automation". Design:
   [`presentation opening visuals`](superpowers/specs/2026-07-10-presentation-opening-visuals-design.md).
   Implementation:
   [`presentation opening visuals plan`](historical/superpowers/plans/2026-07-10-presentation-opening-visuals.md).
```

- [ ] **Step 7: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-10-presentation-opening-visuals.md docs/historical/superpowers/plans/2026-07-10-presentation-opening-visuals.md
```

- [ ] **Step 8: Commit docs/archive**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-10-presentation-opening-visuals.md
git commit -m "docs: complete presentation opening visuals"
```

---

## Self-Review Checklist

- Spec coverage:
  - Scene 1 title reveal and contribution focus: Task 2.
  - Scene 2 action sequence vs reusable automation: Task 3.
  - Icons/shapes instead of text-only lists: Tasks 1-3.
  - No `wf` opening branding: Task 2 tests and spec constraints.
  - `Codex / Claude / OpenCode`: Task 2.
  - No formal lifecycle names in Scene 2: Task 3 tests.
  - Scenes 3/4/5 untouched: Global constraints and tasks only route `thesis`/`problem`.
- Placeholder scan:
  - No unresolved placeholder markers or unspecified "handle errors" steps.
- Dependency check:
  - No shadcn/ui dependency is added. This is deliberate because shadcn is a copied-source component-system decision, not a one-slide icon dependency.
- Type consistency:
  - `ConceptIconName`, `ConceptIcon`, `ConceptNode`, and `ConceptRail` are defined in Task 1 and consumed by Tasks 2 and 3.
