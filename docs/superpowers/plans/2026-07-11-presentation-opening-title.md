# Presentation Opening Title Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Scene 1 as an agent-shaped title composition that identifies
`Runner / platform` as the implemented contribution without stealing Scene 2's
problem framing.

**Architecture:** Keep the existing `OpeningThesisScene` and `ConceptNode`
primitives, but give Scene 1 its own wrapper and connected-role composition.
The scene owns its two beat states through `data-opening-focus`; no global
theme, router, or story-flow changes are required. The formal thesis title stays
in a compact Scene 1 caption while the role system becomes the focal artifact.

**Tech Stack:** React 19, TypeScript, Vitest + Testing Library, existing
presentation CSS and concept SVG primitives.

## Global Constraints

- Preserve the existing editorial canvas, Barlow Condensed/Source Sans/IBM Plex
  Mono typography, and cyan as the only active presentation accent.
- Do not change Scene 2's transcript, copy, or direct-actions-versus-reusable-
  automation responsibility.
- Do not introduce a third presentation theme, a new component library, or
  generic same-weight card grids.
- Keep both Scene 1 beats readable and unclipped at 1280x720 and respect the
  existing reduced-motion rule.
- Add a concise comment for the non-obvious fallback or state mapping only.

---

### Task 1: Define the Scene 1 Copy And Beat Contract

**Files:**
- Modify: `web/apps/console/src/presentation/opening/OpeningThesisScene.tsx`
- Modify: `web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx`

**Interfaces:**
- Consumes: `SceneDefinition`, `SceneBeatDefinition`, `ConceptNode`, and
  `ConceptRail`.
- Produces: `OpeningThesisScene` markup with `data-opening-focus="title" |
  "contribution"`, a main heading, and an agent-role group.

- [ ] **Step 1: Write failing title-beat assertions**

```tsx
const opening = screen.getByRole("region", { name: /thesis opening/i });
expect(opening).toHaveAttribute("data-opening-focus", "title");
expect(screen.getByRole("heading", { name: "An AI Agent for Workspace Workflows" })).toBeInTheDocument();
expect(screen.getByRole("group", { name: "AI agent roles" })).toBeInTheDocument();
expect(screen.queryByRole("heading", { name: "Thesis" })).not.toBeInTheDocument();
expect(screen.queryByText("Decomposed")).not.toBeInTheDocument();
```

- [ ] **Step 2: Run the title-beat test and verify it fails**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/opening/OpeningThesisScene.test.tsx
```

Expected: FAIL because the main heading is currently `Thesis` and the agent
roles retain the old `AI agent components` label.

- [ ] **Step 3: Write failing contribution-beat assertions**

```tsx
render(<OpeningThesisScene scene={thesisScene} beat={findBeat("thesis", "substrate")!} />);

const opening = screen.getByRole("region", { name: /thesis opening/i });
expect(opening).toHaveAttribute("data-opening-focus", "contribution");
expect(screen.getByText("Runner / platform")).toBeInTheDocument();
expect(screen.getByText("Implemented contribution")).toBeInTheDocument();
expect(screen.getByText("Lifecycle, validation, records, traces, and interrupt/resume")).toBeInTheDocument();
expect(screen.getByText("Planner")).toBeInTheDocument();
expect(screen.getByText("Tool surface")).toBeInTheDocument();
```

- [ ] **Step 4: Run the contribution-beat test and verify it fails**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/opening/OpeningThesisScene.test.tsx
```

Expected: FAIL because the current label is `Workflow Platform` and no
`Implemented contribution` scope exists.

- [ ] **Step 5: Implement the semantic opening composition**

Replace the old title-card strings and decomposition labels with this structure:

```tsx
const contributionBeat = beat.id === "substrate";

return (
  <section className="opening-thesis-scene" aria-label="thesis opening">
    <StageCaption eyebrow="Title" title="Design and Implementation of lda.chat">
      <p>{beat.caption}</p>
    </StageCaption>
    <div
      className="opening-thesis"
      data-opening-focus={contributionBeat ? "contribution" : "title"}
    >
      <div className="opening-thesis__statement">
        <p>Product goal</p>
        <h2>An AI Agent for Workspace Workflows</h2>
      </div>
      <ConceptRail label="AI agent roles">
        <ConceptNode title="Planner" subtitle="Codex, Claude, OpenCode" icon="planner" emphasis="normal" />
        <ConceptNode title="Tool surface" subtitle="CLI, MCP, JSON-RPC" icon="tool" emphasis="normal" />
        <ConceptNode
          title="Runner / platform"
          subtitle="Workflow lifecycle and deterministic execution"
          icon="platform"
          emphasis={contributionBeat ? "primary" : "normal"}
        >
          {contributionBeat ? (
            <>
              <span>Implemented contribution</span>
              <span>Lifecycle, validation, records, traces, and interrupt/resume</span>
            </>
          ) : null}
        </ConceptNode>
      </ConceptRail>
    </div>
  </section>
);
```

Keep `scene.evidencePointer` after the section. If `ConceptNode` needs to
accept multi-line metadata, change its `children` wrapper to retain nested
content without changing its behavior in Scene 2.

- [ ] **Step 6: Run the focused tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/opening/OpeningThesisScene.test.tsx src/presentation/SceneBody.test.tsx
```

Expected: PASS. Scene 1 tests enforce the new title and contribution wording;
Scene 2 integration assertions remain unchanged.

- [ ] **Step 7: Commit the semantic composition**

```powershell
git add web/apps/console/src/presentation/opening/OpeningThesisScene.tsx web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx
git commit -m "feat: reframe presentation opening as agent roles"
```

### Task 2: Render One Connected Agent System Instead Of Three Cards

**Files:**
- Modify: `web/apps/console/src/presentation/presentation.css`
- Test: `web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx`

**Interfaces:**
- Consumes: the `opening-thesis-scene`, `opening-thesis`, and `ConceptRail`
  markup created in Task 1.
- Produces: distinct title and contribution layouts controlled solely by
  `data-opening-focus`.

- [ ] **Step 1: Add a failing structural assertion for the connected system**

```tsx
const roles = screen.getByRole("group", { name: "AI agent roles" });
expect(roles).toHaveClass("opening-thesis__agent-system");
expect(roles.querySelectorAll("[data-concept-emphasis]")).toHaveLength(3);
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/opening/OpeningThesisScene.test.tsx
```

Expected: FAIL because Scene 1 currently uses the generic concept rail class
without a Scene 1 system hook.

- [ ] **Step 3: Implement Scene 1-specific layout rules**

Add `className="opening-thesis__agent-system"` to the Scene 1 `ConceptRail`.
Replace the existing `.opening-thesis` and `.opening-thesis__title-card` block
with rules following this shape:

```css
.opening-thesis-scene {
  display: grid;
  flex: 1 1 auto;
  min-height: 0;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 0.85rem;
}

.opening-thesis {
  display: grid;
  min-height: 0;
  align-content: center;
  gap: clamp(1.5rem, 4vh, 3rem);
}

.opening-thesis__statement {
  max-width: 21ch;
}

.opening-thesis__statement h2 {
  margin: 0;
  font: 800 clamp(2.8rem, 6.5vw, 5.25rem) / 0.95 var(--font-editorial);
  letter-spacing: -0.03em;
  text-wrap: balance;
}

.opening-thesis__agent-system {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
}

.opening-thesis__agent-system .concept-node {
  border: 0;
  border-radius: 0;
  background: transparent;
}

.opening-thesis__agent-system .concept-node:not(:last-child)::after {
  position: absolute;
  top: 50%;
  right: -0.45rem;
  width: 0.9rem;
  border-top: 1px solid var(--stage-line);
  content: "";
}

.opening-thesis[data-opening-focus="contribution"] .opening-thesis__agent-system {
  grid-template-columns: 0.72fr 0.72fr minmax(0, 1.56fr);
}
```

Add a compact contribution label treatment inside only the selected platform
role. It may use cyan text and a solid stage-surface background, but the planner
and tool roles remain connected context rather than dimmed generic cards. Add a
`prefers-reduced-motion` override matching the existing presentation rules.

- [ ] **Step 4: Run the focused tests and typecheck**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/opening/OpeningThesisScene.test.tsx src/presentation/SceneBody.test.tsx
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS with no TypeScript errors.

- [ ] **Step 5: Capture both 720p opening beats and inspect them**

Run:

```powershell
playwright-cli goto 'http://127.0.0.1:5173/present#scene/thesis/title'
playwright-cli screenshot --filename='web/apps/console/.visual-smoke/opening-title-agent-system.png' --hires
playwright-cli goto 'http://127.0.0.1:5173/present#scene/thesis/substrate'
playwright-cli screenshot --filename='web/apps/console/.visual-smoke/opening-contribution-agent-system.png' --hires
```

Expected: the first screenshot has `An AI Agent for Workspace Workflows` as its
largest text; the second makes `Runner / platform` clearly dominant without
clipping the formal title, footer, or role labels.

- [ ] **Step 6: Commit the visual system**

```powershell
git add web/apps/console/src/presentation/opening/OpeningThesisScene.tsx web/apps/console/src/presentation/opening/OpeningThesisScene.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "style: connect presentation opening agent roles"
```

### Task 3: Record Completion And Verify The Presentation Surface

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-11-presentation-opening-title.md` to `docs/historical/superpowers/plans/2026-07-11-presentation-opening-title.md`

**Interfaces:**
- Consumes: completed Scene 1 component, focused tests, and captured local
  screenshots.
- Produces: a roadmap that accurately marks the Scene 1 title slice complete
  and retains the separate rehearsal slice as next work.

- [ ] **Step 1: Update the roadmap entry**

Replace the current Scene 1 next-slice wording with:

```markdown
7. Completed: Scene 1 now introduces the agent-shaped product goal through
   Planner -> Tool surface -> Runner / platform, then identifies the last role
   as the implemented contribution. Scene 2 remains responsible for the
   automation problem. Implementation:
   [`presentation opening title`](historical/superpowers/plans/2026-07-11-presentation-opening-title.md).
```

- [ ] **Step 2: Run the full web verification suite**

Run:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Expected: all workspace tests, typechecks, and builds pass. The existing Vite
chunk-size warning may remain; do not change bundle configuration in this slice.

- [ ] **Step 3: Archive the completed plan and commit documentation**

```powershell
Move-Item docs/superpowers/plans/2026-07-11-presentation-opening-title.md docs/historical/superpowers/plans/2026-07-11-presentation-opening-title.md
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-11-presentation-opening-title.md
git add -u docs/superpowers/plans
git commit -m "docs: complete presentation opening title slice"
```

## Self-Review

- Spec coverage: Task 1 implements exact title/role/copy acceptance criteria;
  Task 2 implements the connected visual system, focus state, and 720p visual
  evidence; Task 3 records completion and verifies the presentation surface.
- Placeholder scan: no TODO, TBD, or deferred implementation steps remain.
- Type consistency: `data-opening-focus` has only `title` and `contribution`
  values in the plan, and Task 1's tests use the same names that Task 2 styles.
- Scope: the rehearsal contract is deliberately excluded and remains the next
  independent slice.
