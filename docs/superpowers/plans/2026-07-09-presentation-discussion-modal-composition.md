# Presentation Discussion Modal Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make discussion routes look like intentional defense overlays instead of plain document cards by giving Q&A and context-only branches a stage-aware composition.

**Architecture:** Keep discussion navigation, branch data, and focus-trap behavior unchanged. Add a small presentation shell around `DiscussionPanel` content: the panel remains the only dialog component, but it gets an inner layout with header, content, and action zones. CSS chooses a Q&A layout or context layout from `data-discussion-layout`; no new state, routes, or component library.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing presentation CSS, Playwright CLI screenshots, `npx -y impeccable detect` rendered-route scan.

## Global Constraints

- Do not change branch ids, route hashes, or Q&A answer copy.
- Do not change focus trap semantics: return button focuses on open, Escape closes, Tab stays inside dialog.
- Do not introduce a modal library or component library.
- Do not touch demo workflow scenes, graph layout, evidence inspector, or replay state.
- Avoid slop patterns: centered generic card, huge empty context page, side-stripe callout, wide diffuse shadow, all-caps body text.
- At `1280x720`, both Q&A and context discussion routes must fit without page scroll.

---

## Current Findings

The previous discussion craft pass improved semantics and hierarchy, but screenshots still show:

- Q&A route reads as a document card spanning the top of the slide.
- Context-only route leaves the bottom two-thirds empty, which looks unfinished.
- Return action is functionally correct but visually disconnected from the content hierarchy.

This slice should make discussion feel like a stage overlay: left side for the question/claim, right side for answer/provenance/actions, and a compact context layout for non-Q&A branches.

---

## File Structure

- Modify `web/apps/console/src/presentation/DiscussionPanel.tsx`
  - Add structural wrappers: `.discussion-panel__shell`, `.discussion-panel__header`, `.discussion-panel__body`, `.discussion-panel__aside`, `.discussion-panel__actions`.
  - Keep current branch fields and focus trap.
- Modify `web/apps/console/src/presentation/DiscussionPanel.test.tsx`
  - Pin shell/body/aside/actions semantics for Q&A and context layouts.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Add stage-sized discussion layout.
  - Make context layout intentionally compact instead of top-heavy.
  - Preserve existing editorial tokens and avoid shadows/side stripes.
- Modify `docs/current_roadmap.md`
  - Mark this modal composition pass complete after implementation.
- Move this plan to `docs/historical/superpowers/plans/2026-07-09-presentation-discussion-modal-composition.md` after implementation.

---

### Task 1: Add Discussion Panel Composition Structure

**Files:**
- Modify: `web/apps/console/src/presentation/DiscussionPanel.tsx`
- Modify: `web/apps/console/src/presentation/DiscussionPanel.test.tsx`

**Interfaces:**
- Consumes: existing `DiscussionPanelProps` and `DiscussionBranchDefinition` fields.
- Produces: stable DOM sections with labels:
  - `discussion shell`
  - `discussion body`
  - `discussion support`
  - `discussion actions`

- [ ] **Step 1: Add failing structure tests**

In `web/apps/console/src/presentation/DiscussionPanel.test.tsx`, add:

```tsx
it("renders Q&A discussion as shell, body, support, and actions regions", () => {
  render(<DiscussionPanel branchId="where-is-ai-agent" onClose={onClose} />);

  expect(screen.getByRole("dialog")).toHaveAttribute("data-discussion-layout", "qna");
  expect(screen.getByLabelText("discussion shell")).toBeInTheDocument();
  expect(screen.getByLabelText("discussion body")).toHaveTextContent("Where is the AI agent in this thesis?");
  expect(screen.getByLabelText("discussion support")).toHaveTextContent("Evidence");
  expect(screen.getByLabelText("discussion actions")).toContainElement(
    screen.getByRole("button", { name: /return to thesis/i }),
  );
});

it("renders context-only discussion with a compact support column", () => {
  render(<DiscussionPanel branchId="hosted-automation" onClose={onClose} />);

  expect(screen.getByRole("dialog")).toHaveAttribute("data-discussion-layout", "context");
  expect(screen.getByLabelText("discussion body")).toHaveTextContent(/Hosted triggers/i);
  expect(screen.getByLabelText("discussion support")).toHaveTextContent(/Workflow Automation Platforms/i);
  expect(screen.queryByLabelText("defense question")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: fail because the labelled shell/body/support/actions regions do not exist.

- [ ] **Step 3: Refactor JSX into shell regions**

In `web/apps/console/src/presentation/DiscussionPanel.tsx`, keep imports, props, focus effect, `trapKeyboardWithinDialog`, and `hasQuestion` logic. Replace the dialog contents inside the root `<div>` with this structure:

```tsx
      <div className="discussion-panel__shell" aria-label="discussion shell">
        <header className="discussion-panel__header">
          <div>
            <span className="discussion-panel__badge">{branch.claimClass}</span>
            <h2>{branch.title}</h2>
          </div>
          <p>{branch.summary}</p>
        </header>

        <main className="discussion-panel__body" aria-label="discussion body">
          {hasQuestion ? (
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
            </section>
          ) : (
            <section className="discussion-panel__context" aria-label="discussion context">
              <p>{branch.summary}</p>
              {branch.detail && (
                <div className="discussion-panel__detail" aria-label="additional context">
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
                </div>
              )}
            </section>
          )}
        </main>

        <aside className="discussion-panel__aside" aria-label="discussion support">
          <section className="discussion-panel__provenance" aria-label="answer provenance">
            <span>Evidence</span>
            <p>{branch.evidencePointer}</p>
          </section>
          {branch.speakerHint && (
            <aside className="discussion-panel__presenter-note" aria-label="presenter note">
              <span>Presenter note</span>
              <p>{branch.speakerHint}</p>
            </aside>
          )}
        </aside>

        <footer className="discussion-panel__actions" aria-label="discussion actions">
          <button ref={returnButtonRef} type="button" onClick={onClose} className="discussion-panel__return">
            Return to {parentScene?.title ?? "scene"}
          </button>
        </footer>
      </div>
```

Important:

- Remove the old top-level `<p className="discussion-panel__summary">` outside the shell.
- Remove the old duplicate `branch.detail` block after the Q&A section.
- Keep `returnButtonRef` attached to the return button.
- Keep `role="dialog"`, `aria-modal`, `aria-label`, and `onKeyDown` on the root `.discussion-panel` element.

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add web/apps/console/src/presentation/DiscussionPanel.tsx web/apps/console/src/presentation/DiscussionPanel.test.tsx
git commit -m "fix: structure discussion modal regions"
```

---

### Task 2: Compose Q&A And Context Layouts Visually

**Files:**
- Modify: `web/apps/console/src/presentation/presentation.css`
- Modify: `web/apps/console/src/presentation/DiscussionPanel.test.tsx`

**Interfaces:**
- Consumes: `.discussion-panel[data-discussion-layout="qna" | "context"]` and shell regions from Task 1.
- Produces: stage-aware modal composition with no document-like top-heavy layout.

- [ ] **Step 1: Add class-contract tests**

In `web/apps/console/src/presentation/DiscussionPanel.test.tsx`, add:

```tsx
it("marks the modal shell with the active layout for styling", () => {
  const { rerender } = render(<DiscussionPanel branchId="where-is-ai-agent" onClose={onClose} />);
  expect(screen.getByLabelText("discussion shell")).toHaveClass("discussion-panel__shell");
  expect(screen.getByRole("dialog")).toHaveAttribute("data-discussion-layout", "qna");

  rerender(<DiscussionPanel branchId="hosted-automation" onClose={onClose} />);
  expect(screen.getByRole("dialog")).toHaveAttribute("data-discussion-layout", "context");
});
```

- [ ] **Step 2: Run tests**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: pass after Task 1. This test pins styling hooks before CSS work.

- [ ] **Step 3: Replace discussion panel base CSS**

In `web/apps/console/src/presentation/presentation.css`, replace the current `.discussion-panel[data-presentation-surface="editorial"]` block and its direct `h2`/badge rules with:

```css
.discussion-panel[data-presentation-surface="editorial"] {
  min-height: min(34rem, calc(100cqh - 2rem));
  padding: 0;
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 34%, transparent);
  border-radius: 0.9rem;
  overflow: hidden;
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 94%, white);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.discussion-panel__shell {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(17rem, 0.65fr);
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 0;
  min-height: inherit;
}

.discussion-panel__header {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 0.55fr);
  gap: 1rem;
  align-items: end;
  border-bottom: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 28%, transparent);
  padding: 1rem 1.1rem 0.85rem;
}

.discussion-panel__header h2 {
  margin: 0.35rem 0 0;
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  font-size: clamp(1.25rem, 2.6vw, 2rem);
  line-height: 1;
}

.discussion-panel__header p {
  margin: 0;
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 74%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  font-size: 0.9rem;
  line-height: 1.35;
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__badge {
  display: inline-block;
  border-radius: 0.35rem;
  background: color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 16%, transparent);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  padding: 0.18rem 0.45rem;
  font: 700 0.7rem/1 var(--font-interface);
}
```

- [ ] **Step 4: Add body/support/action CSS**

Still in `presentation.css`, replace the current `.discussion-panel__qna`, `.discussion-panel__question`, `.discussion-panel__answer-card`, `.discussion-panel__presenter-note`, `.discussion-panel__detail`, and `.discussion-panel__return` rules with:

```css
.discussion-panel__body {
  min-width: 0;
  padding: 1rem 1.1rem;
}

.discussion-panel__aside {
  display: grid;
  align-content: start;
  gap: 0.75rem;
  border-left: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 22%, transparent);
  padding: 1rem;
  background: color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 7%, transparent);
}

.discussion-panel__actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 22%, transparent);
  padding: 0.75rem 1rem;
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__qna {
  display: grid;
  gap: 0.75rem;
  margin: 0;
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__question {
  margin: 0;
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  font-size: clamp(1.35rem, 2.4vw, 2rem);
  font-weight: 760;
  line-height: 1.08;
  text-wrap: balance;
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__answer-card {
  display: grid;
  gap: 0.4rem;
  border: 1px solid color-mix(in oklch, var(--color-intent, oklch(0.53 0.17 250)) 28%, transparent);
  border-radius: 0.75rem;
  padding: 0.8rem 0.85rem;
  background: color-mix(in oklch, var(--color-intent, oklch(0.53 0.17 250)) 5%, var(--color-editorial-paper, oklch(0.975 0.012 82)));
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__answer-card--expanded {
  border-color: color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 28%, transparent);
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 90%, white);
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__answer-card span,
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__provenance span,
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__presenter-note span {
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 68%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  font: 700 0.68rem/1 var(--font-interface);
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__answer-card p {
  margin: 0;
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  line-height: 1.42;
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__provenance,
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__presenter-note,
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__detail {
  display: grid;
  gap: 0.35rem;
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 24%, transparent);
  border-radius: 0.7rem;
  padding: 0.65rem;
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 74%, white);
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__provenance p,
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__presenter-note p,
.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__detail p {
  margin: 0;
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 84%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  font-size: 0.85rem;
  line-height: 1.38;
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__presenter-note {
  border-style: dashed;
  background: color-mix(in oklch, var(--color-human, oklch(0.68 0.17 55)) 8%, var(--color-editorial-paper, oklch(0.975 0.012 82)));
}

.discussion-panel[data-presentation-surface="editorial"] .discussion-panel__return {
  border: 1px solid var(--color-editorial-ink, oklch(0.19 0.015 65));
  border-radius: 0.45rem;
  padding: 0.48rem 0.8rem;
  background: var(--color-editorial-ink, oklch(0.19 0.015 65));
  color: var(--color-editorial-paper, oklch(0.975 0.012 82));
  font-weight: 650;
}
```

- [ ] **Step 5: Add context layout CSS**

Add these rules after the block above:

```css
.discussion-panel[data-discussion-layout="context"] .discussion-panel__shell {
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 0.42fr);
  min-height: min(24rem, calc(100cqh - 2rem));
}

.discussion-panel[data-discussion-layout="context"] .discussion-panel__body {
  display: grid;
  align-content: start;
  gap: 0.75rem;
}

.discussion-panel__context {
  display: grid;
  gap: 0.75rem;
}

.discussion-panel__context > p {
  margin: 0;
  max-width: 68ch;
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
  font-size: 1.12rem;
  line-height: 1.35;
}

@media (max-height: 760px) {
  .discussion-panel__shell,
  .discussion-panel[data-discussion-layout="context"] .discussion-panel__shell {
    grid-template-columns: minmax(0, 1fr);
    min-height: auto;
  }

  .discussion-panel__header {
    grid-template-columns: minmax(0, 1fr);
  }

  .discussion-panel__aside {
    border-left: 0;
    border-top: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 22%, transparent);
  }
}
```

- [ ] **Step 6: Run tests and verify they pass**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: pass.

- [ ] **Step 7: Commit Task 2**

```powershell
git add web/apps/console/src/presentation/DiscussionPanel.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "fix: compose discussion modal stage layout"
```

---

### Task 3: Browser Smoke, Detector, And Roadmap

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-09-presentation-discussion-modal-composition.md` to `docs/historical/superpowers/plans/2026-07-09-presentation-discussion-modal-composition.md`

**Interfaces:**
- Consumes: rendered `/present#discuss/...` routes.
- Produces: screenshots, detector output, roadmap completion.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx src/presentation/PresentationRoute.test.tsx
```

Expected: pass.

- [ ] **Step 2: Run broad presentation checks**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected: presentation tests pass, typecheck clean, build passes with only known chunk-size warning, diff check clean.

- [ ] **Step 3: Run detector smoke**

Run:

```powershell
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#discuss/where-is-ai-agent
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#discuss/hosted-automation
```

Expected:

- No `gpt-thin-border-wide-shadow` findings.
- No `side-stripe` style finding.
- No new `all-caps-body` findings from modal content.
- `line-length` or `flat-type-hierarchy` findings may still appear; report them if present and do not expand scope.

- [ ] **Step 4: Capture screenshots**

Run:

```powershell
pnpx --package @playwright/cli playwright-cli -s=discussion-modal open "http://127.0.0.1:5173/present#discuss/where-is-ai-agent"
pnpx --package @playwright/cli playwright-cli -s=discussion-modal resize 1280 720
pnpx --package @playwright/cli playwright-cli -s=discussion-modal screenshot --filename web/apps/console/.visual-smoke/discussion-modal-qna.png
pnpx --package @playwright/cli playwright-cli -s=discussion-modal open "http://127.0.0.1:5173/present#discuss/hosted-automation"
pnpx --package @playwright/cli playwright-cli -s=discussion-modal screenshot --filename web/apps/console/.visual-smoke/discussion-modal-context.png
```

Acceptance criteria:

- Q&A modal uses the slide area intentionally with header/body/support/actions regions.
- Context-only modal no longer leaves a huge empty lower stage.
- Return button remains visible at `1280x720`.
- No visible page scrollbar.

- [ ] **Step 5: Update roadmap**

In `docs/current_roadmap.md`, under `Next presentation visual slices`, insert this completed item after the discussion craft item:

```md
   9. Completed: discussion modal composition pass made Q&A and context-only
      routes stage-aware, with body/support/action regions instead of plain
      document cards. Implementation:
      [`presentation discussion modal composition`](historical/superpowers/plans/2026-07-09-presentation-discussion-modal-composition.md).
   10. Presentation craft pass: tune remaining motion, evidence receipt
       placement, route-level caption contrast, and graph visual language after
       the discussion modal is stable.
```

Renumber the existing open craft-pass item if needed.

- [ ] **Step 6: Archive the plan**

Run:

```powershell
Move-Item docs/superpowers/plans/2026-07-09-presentation-discussion-modal-composition.md docs/historical/superpowers/plans/2026-07-09-presentation-discussion-modal-composition.md
```

Verify:

```powershell
rg -n "presentation discussion modal composition|2026-07-09-presentation-discussion-modal-composition" docs/current_roadmap.md docs/superpowers/plans docs/historical/superpowers/plans
```

Expected:

- Roadmap points to the historical plan path.
- No active copy remains under `docs/superpowers/plans/`.

- [ ] **Step 7: Commit Task 3**

```powershell
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-presentation-discussion-modal-composition.md
git add -u docs/superpowers/plans/2026-07-09-presentation-discussion-modal-composition.md
git commit -m "docs: record presentation discussion modal composition"
```

---

## Final Verification

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#discuss/where-is-ai-agent
npx -y impeccable detect --json --gpt --gemini http://127.0.0.1:5173/present#discuss/hosted-automation
git diff --check
git status --short
```

Expected:

- Presentation tests pass.
- Typecheck passes.
- Build passes with only known chunk warning if present.
- Detector shows no ghost-card, side-stripe, or all-caps-body findings from the discussion modal.
- `git diff --check` is clean.
- `git status --short` is clean.

## Self-Review

- Spec coverage: plan covers structure, visual composition, context-only route, detector smoke, screenshots, roadmap, and archival.
- Placeholder scan: no placeholder markers or vague implementation instructions are present.
- Type consistency: uses existing `DiscussionPanelProps`, existing branch fields, and current test utilities.
- Scope check: no demo workflow, graph, evidence inspector, route hash, or Q&A copy changes.
