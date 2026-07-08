# Presentation Discussion Craft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the remaining loose discussion chips and flat Q&A modal with a clearer presenter-ready discussion layer that supports defense questions without looking like generic slide chrome.

**Architecture:** Keep the existing `discussionBranches` data and navigation model. Refactor only the presentation components that render discussion affordances: `SceneBody` owns the per-scene question rail, and `DiscussionPanel` owns the modal hierarchy. CSS changes stay in `presentation.css`; the demo workflow layout and replay state are not part of this slice.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing presentation CSS, `npx -y impeccable detect` rendered-route scan, Playwright CLI screenshot smoke.

## Global Constraints

- Do not change discussion branch ids, route hashes, or Q&A copy in `storyboard.ts`.
- Do not change demo workflow replay, graph layout, or evidence inspector behavior.
- Do not introduce a component library in this slice.
- Avoid the known slop patterns: pill-only chip pile, side-stripe callout, wide diffuse card shadows, and all-caps body text.
- Keep keyboard/focus behavior for the discussion dialog intact.
- Add comments only around non-obvious layout decisions.

---

## Current Findings

The demo proof layout is now structurally acceptable. The remaining weak presentation surfaces are:

1. Bottom discussion chips look detached from the slide and read as generic tag pills.
2. Q&A modal presents useful content, but hierarchy is flat: title, evidence, summary, answer, note, detail all compete.
3. `impeccable detect` still flags rendered presentation routes for low contrast and generic generated-UI tells. Some contrast warnings are detector sensitivity over gradients, but the discussion layer can still avoid obvious patterns.

This slice should make discussion feel like a deliberate defense control: a small rail of available examiner questions, and a modal that clearly separates answer, evidence, and presenter-only note.

---

## File Structure

- Modify `web/apps/console/src/presentation/SceneBody.tsx`
  - Replace raw button pile in `DiscussionLinks` with a labelled rail and list semantics.
- Modify `web/apps/console/src/presentation/SceneBody.test.tsx`
  - Pin rail semantics and branch metadata rendering.
- Modify `web/apps/console/src/presentation/DiscussionPanel.tsx`
  - Add explicit Q&A layout sections: question header, answer card, evidence/provenance card, presenter-note card.
- Modify `web/apps/console/src/presentation/DiscussionPanel.test.tsx`
  - Pin Q&A hierarchy, non-Q&A fallback, and focus trap behavior.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Replace pill-chip styling with rail styling.
  - Replace flat modal card styling with a two-zone editorial dialog.
  - Remove side-stripe detail treatment.
- Modify `docs/current_roadmap.md`
  - Mark discussion craft pass complete after implementation.
- Move this plan to `docs/historical/superpowers/plans/2026-07-09-presentation-discussion-craft.md` after implementation.

---

### Task 1: Replace Discussion Chips With A Presenter Question Rail

**Files:**
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: `discussionBranches`, `openDiscussion(branchId: string)`.
- Produces: `.scene-body__discussion-links` rail with `data-discussion-rail="true"`, a visible label, list semantics, and branch claim labels.

- [ ] **Step 1: Add failing tests for rail semantics**

In `web/apps/console/src/presentation/SceneBody.test.tsx`, add these tests inside the existing `describe("SceneBody", ...)` block:

```tsx
it("renders discussion branches as a labelled presenter rail", () => {
  const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "landscape", focusPath: [] };
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

  const rail = screen.getByLabelText("defense discussion topics");
  expect(rail).toHaveAttribute("data-discussion-rail", "true");
  expect(within(rail).getByText("Defense questions")).toBeInTheDocument();
  expect(within(rail).getByRole("list")).toBeInTheDocument();
  expect(within(rail).getByRole("button", { name: /Hosted automation future-work/i })).toBeInTheDocument();
});

it("keeps discussion rail actions wired to branch ids", async () => {
  const user = userEvent.setup();
  const location: PresentationLocation = { kind: "main", sceneId: "positioning", beatId: "landscape", focusPath: [] };
  const openDiscussion = vi.fn();
  render(
    <SceneBody
      location={location}
      demo={demo}
      selectedNodeId={null}
      selectNode={noop}
      openEvidence={noop}
      openDiscussion={openDiscussion}
      onFocusPathChange={noop}
      motionDisabled={false}
    />,
  );

  await user.click(screen.getByRole("button", { name: /Hosted automation future-work/i }));

  expect(openDiscussion).toHaveBeenCalledWith("hosted-automation");
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
```

Expected: fail because the rail label, list semantics, and `data-discussion-rail` do not exist yet.

- [ ] **Step 3: Refactor `DiscussionLinks` markup**

In `web/apps/console/src/presentation/SceneBody.tsx`, replace the `DiscussionLinks` return block with:

```tsx
  return (
    <aside className="scene-body__discussion-links" aria-label="defense discussion topics" data-discussion-rail="true">
      <span className="scene-body__discussion-label">Defense questions</span>
      <ul className="scene-body__discussion-list">
        {branches.map((branch) => (
          <li key={branch.id}>
            <button
              type="button"
              onClick={() => openDiscussion(branch.id)}
            >
              <span>{branch.title}</span>
              <small>{branch.claimClass}</small>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
```

- [ ] **Step 4: Replace rail CSS**

In `web/apps/console/src/presentation/presentation.css`, replace the existing `.scene-body__discussion-links` and `.scene-body__discussion-links button` rules with:

```css
.scene-body__discussion-links {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 0.7rem;
  margin-top: 0.55rem;
  border-top: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 30%, transparent);
  padding-top: 0.45rem;
}

.scene-body__discussion-label {
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 72%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  font: 650 0.72rem/1 var(--font-interface);
}

.scene-body__discussion-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.scene-body__discussion-links button {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 36%, transparent);
  border-radius: 0.55rem;
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 72%, transparent);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  padding: 0.34rem 0.55rem;
  font: 600 0.74rem/1 var(--font-interface);
}

.scene-body__discussion-links button small {
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 62%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  font: 0.68rem/1 var(--font-interface);
}

.scene-body__discussion-links button:hover,
.scene-body__discussion-links button:focus-visible {
  border-color: var(--color-intent, oklch(0.53 0.17 250));
  background: color-mix(in oklch, var(--color-intent, oklch(0.53 0.17 250)) 8%, var(--color-editorial-paper, oklch(0.975 0.012 82)));
}
```

Remove the old uppercase/tracked/pill styling. Do not add a side stripe or shadow.

- [ ] **Step 5: Run tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
```

Expected: pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "fix: turn discussion chips into presenter rail"
```

---

### Task 2: Rebuild Discussion Panel Hierarchy

**Files:**
- Modify: `web/apps/console/src/presentation/DiscussionPanel.tsx`
- Modify: `web/apps/console/src/presentation/DiscussionPanel.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: existing `DiscussionBranchDefinition` fields.
- Produces: Q&A dialog with `data-discussion-layout="qna" | "context"`, explicit answer/provenance/presenter-note sections, and unchanged focus trap behavior.

- [ ] **Step 1: Add failing tests for modal hierarchy**

In `web/apps/console/src/presentation/DiscussionPanel.test.tsx`, add:

```tsx
it("separates Q&A answer, provenance, and presenter note regions", () => {
  render(<DiscussionPanel branchId="where-is-ai-agent" onClose={onClose} />);

  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveAttribute("data-discussion-layout", "qna");
  expect(screen.getByLabelText("short defense answer")).toHaveTextContent(/workflow substrate/i);
  expect(screen.getByLabelText("answer expansion")).toHaveTextContent(/planning algorithm/i);
  expect(screen.getByLabelText("answer provenance")).toHaveTextContent(/Abstract/i);
  expect(screen.getByLabelText("presenter note")).toHaveTextContent(/Answer directly first/i);
});

it("uses context layout for non-Q&A discussion branches", () => {
  render(<DiscussionPanel branchId="hosted-automation" onClose={onClose} />);

  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveAttribute("data-discussion-layout", "context");
  expect(screen.queryByLabelText("short defense answer")).not.toBeInTheDocument();
  expect(screen.getByLabelText("answer provenance")).toHaveTextContent(/Workflow Automation Platforms/i);
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: fail because `data-discussion-layout` and the labelled regions do not exist yet.

- [ ] **Step 3: Refactor `DiscussionPanel` content**

In `web/apps/console/src/presentation/DiscussionPanel.tsx`, add:

```tsx
  const hasQuestion = branch.question !== undefined;
```

Set these attributes on the dialog root:

```tsx
      data-presentation-surface="editorial"
      data-discussion-layout={hasQuestion ? "qna" : "context"}
```

Replace the current evidence/summary/Q&A/detail block between `</header>` and the return button with:

```tsx
      <section className="discussion-panel__provenance" aria-label="answer provenance">
        <span>Evidence</span>
        <p>{branch.evidencePointer}</p>
      </section>
      <p className="discussion-panel__summary">{branch.summary}</p>
      {hasQuestion && (
        <section className="discussion-panel__qna" aria-label="defense question">
          <p className="discussion-panel__question">{branch.question}</p>
          {branch.shortAnswer && (
            <article className="discussion-panel__answer-card" aria-label="short defense answer">
              <span>Short answer</span>
              <p>{branch.shortAnswer}</p>
            </article>
          )}
          {branch.expandedAnswer && (
            <article className="discussion-panel__answer-card discussion-panel__answer-card--expanded" aria-label="answer expansion">
              <span>Expanded answer</span>
              <p>{branch.expandedAnswer}</p>
            </article>
          )}
          {branch.speakerHint && (
            <aside className="discussion-panel__presenter-note" aria-label="presenter note">
              <span>Presenter note</span>
              <p>{branch.speakerHint}</p>
            </aside>
          )}
        </section>
      )}
      {branch.detail && (
        <section className="discussion-panel__detail" aria-label="additional context">
          <p>
            {branch.detail.links?.map((link, index) => (
              <span key={link.href}>
                {index > 0 && " · "}
                <a href={link.href} target="_blank" rel="noopener noreferrer">{link.label}</a>
              </span>
            ))}
            {branch.detail.links && branch.detail.links.length > 0 ? " — " : ""}
            {branch.detail.text}
          </p>
        </section>
      )}
```

Keep the existing focus trap and return button unchanged.

- [ ] **Step 4: Replace discussion panel CSS**

In `web/apps/console/src/presentation/presentation.css`, update the discussion panel block:

1. Replace `.discussion-panel__evidence` rules with `.discussion-panel__provenance` rules:

```css
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__provenance {
  display: grid;
  gap: 0.2rem;
  margin: 0.55rem 0 0;
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 24%, transparent);
  border-radius: 0.6rem;
  padding: 0.5rem 0.6rem;
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 82%, white);
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__provenance span,
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__answer-card span {
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 68%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  font: 700 0.68rem/1 var(--font-interface);
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__provenance p {
  margin: 0;
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 84%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  font-size: 0.82rem;
}
```

2. Replace `.discussion-panel__qna`, `.discussion-panel__question`, `.discussion-panel__short-answer`, and `.discussion-panel__expanded-answer` rules with:

```css
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__qna {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(14rem, 0.9fr);
  gap: 0.7rem;
  margin: 0.85rem 0;
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__question {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  font-size: 1.15rem;
  font-weight: 760;
  line-height: 1.15;
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__answer-card {
  display: grid;
  gap: 0.35rem;
  border: 1px solid color-mix(in oklch, var(--color-intent, oklch(0.53 0.17 250)) 26%, transparent);
  border-radius: 0.75rem;
  padding: 0.7rem;
  background: color-mix(in oklch, var(--color-intent, oklch(0.53 0.17 250)) 6%, var(--color-editorial-paper, oklch(0.975 0.012 82)));
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__answer-card--expanded {
  border-color: color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 28%, transparent);
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 90%, white);
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__answer-card p {
  margin: 0;
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  line-height: 1.42;
}
```

3. Replace `.discussion-panel__presenter-note` rules with:

```css
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__presenter-note {
  display: grid;
  gap: 0.3rem;
  margin: 0;
  border: 1px dashed color-mix(in oklch, var(--color-human, oklch(0.68 0.17 55)) 42%, transparent);
  border-radius: 0.75rem;
  padding: 0.7rem;
  background: color-mix(in oklch, var(--color-human, oklch(0.68 0.17 55)) 9%, var(--color-editorial-paper, oklch(0.975 0.012 82)));
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__presenter-note span {
  color: color-mix(in oklch, var(--color-human, oklch(0.68 0.17 55)) 70%, var(--color-editorial-ink, oklch(0.19 0.015 65)));
  font: 700 0.68rem/1 var(--font-interface);
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__presenter-note p {
  margin: 0;
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 84%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  font-size: 0.84rem;
  line-height: 1.35;
}
```

4. Replace `.discussion-panel__detail` to remove the side stripe:

```css
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__detail {
  margin: 0.65rem 0 0;
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 24%, transparent);
  border-radius: 0.65rem;
  padding: 0.6rem;
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 82%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  font-size: 0.85rem;
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__detail p {
  margin: 0;
}
```

5. Add a narrow-height fallback:

```css
@media (max-height: 760px) {
  .discussion-panel[data-presentation-surface="editorial"] .discussion-panel__qna {
    grid-template-columns: minmax(0, 1fr);
  }
}
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add web/apps/console/src/presentation/DiscussionPanel.tsx web/apps/console/src/presentation/DiscussionPanel.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "fix: clarify defense qna modal hierarchy"
```

---

### Task 3: Detector And Screenshot Verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-09-presentation-discussion-craft.md` to `docs/historical/superpowers/plans/2026-07-09-presentation-discussion-craft.md`

**Interfaces:**
- Consumes: rendered `/present` route and `impeccable detect` CLI.
- Produces: roadmap completion item and archived plan.

- [ ] **Step 1: Run focused presentation tests**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
```

Expected: all presentation tests pass.

- [ ] **Step 2: Run typecheck and build**

Run:

```powershell
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: typecheck clean; build passes with only the known Vite chunk-size warning if it appears.

- [ ] **Step 3: Run rendered detector smoke**

Run:

```powershell
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#scene/positioning/landscape
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#discuss/where-is-ai-agent
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#discuss/hosted-automation
```

Expected:

- No `gpt-thin-border-wide-shadow` findings.
- No `all-caps-body` finding introduced by the rail or modal.
- No `side-stripe`/border-left finding on `discussion-panel__detail`.
- Existing gradient contrast warnings may remain on scene captions; record them in the report rather than trying to fix unrelated surfaces.

- [ ] **Step 4: Capture screenshots**

Run:

```powershell
pnpx --package @playwright/cli playwright-cli -s=discussion-craft open "http://127.0.0.1:5173/present#scene/positioning/landscape"
pnpx --package @playwright/cli playwright-cli -s=discussion-craft resize 1280 720
pnpx --package @playwright/cli playwright-cli -s=discussion-craft screenshot --filename web/apps/console/.visual-smoke/discussion-craft-03-rail.png
pnpx --package @playwright/cli playwright-cli -s=discussion-craft open "http://127.0.0.1:5173/present#discuss/where-is-ai-agent"
pnpx --package @playwright/cli playwright-cli -s=discussion-craft screenshot --filename web/apps/console/.visual-smoke/discussion-craft-qna.png
pnpx --package @playwright/cli playwright-cli -s=discussion-craft open "http://127.0.0.1:5173/present#discuss/hosted-automation"
pnpx --package @playwright/cli playwright-cli -s=discussion-craft screenshot --filename web/apps/console/.visual-smoke/discussion-craft-context.png
```

Acceptance criteria:

- Scene discussion affordance reads as a presenter rail, not a pile of tags.
- Q&A modal answer can be read in this order: question, short answer, expanded answer, provenance, presenter note.
- Context-only branches still render cleanly without empty Q&A boxes.
- At `1280x720`, the modal does not cover its own return button or require page scroll.

- [ ] **Step 5: Update roadmap**

In `docs/current_roadmap.md`, replace item 8 under `Next presentation visual slices` with:

```md
   8. Completed: discussion craft pass replaced detached branch chips with a
      presenter question rail and rebuilt Q&A modals around answer,
      provenance, and presenter-note hierarchy. Implementation:
      [`presentation discussion craft`](historical/superpowers/plans/2026-07-09-presentation-discussion-craft.md).
   9. Presentation craft pass: tune remaining motion, evidence receipt
      placement, route-level caption contrast, and graph visual language after
      the discussion layer is stable.
```

- [ ] **Step 6: Archive the plan**

Run:

```powershell
Move-Item docs/superpowers/plans/2026-07-09-presentation-discussion-craft.md docs/historical/superpowers/plans/2026-07-09-presentation-discussion-craft.md
```

Verify:

```powershell
rg -n "presentation discussion craft|2026-07-09-presentation-discussion-craft" docs/current_roadmap.md docs/superpowers/plans docs/historical/superpowers/plans
```

Expected:

- Roadmap points to `historical/superpowers/plans/2026-07-09-presentation-discussion-craft.md`.
- No active copy remains under `docs/superpowers/plans/`.

- [ ] **Step 7: Final verification and commit**

Run:

```powershell
git diff --check
git status --short
```

Expected: only roadmap and plan movement are unstaged.

Commit:

```powershell
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-presentation-discussion-craft.md
git add -u docs/superpowers/plans/2026-07-09-presentation-discussion-craft.md
git commit -m "docs: record presentation discussion craft pass"
```

---

## Final Verification

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#scene/positioning/landscape
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#discuss/where-is-ai-agent
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#discuss/hosted-automation
git diff --check
git status --short
```

Expected:

- Presentation tests pass.
- Typecheck passes.
- Build passes with only known chunk-size warning if present.
- Detector shows no new discussion-layer slop findings. Existing unrelated route-level contrast warnings can be reported.
- `git diff --check` is clean.
- `git status --short` is clean.

## Self-Review

- Spec coverage: covers discussion rail, modal hierarchy, CSS slop removal, detector smoke, screenshots, and roadmap archival.
- Placeholder scan: no placeholder markers or vague implementation instructions are present.
- Type consistency: uses existing `DiscussionBranchDefinition`, `openDiscussion(branchId: string)`, and existing route hashes unchanged.
- Scope check: does not change demo workflow replay, graph layout, chat replacement, source data, or Q&A copy.
