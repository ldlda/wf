# Presentation Surface Theme Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize `/present` chat and discussion/Q&A surfaces so light chat, direct discussion branches, and presenter notes share one editorial presentation vocabulary.

**Architecture:** Add a small semantic surface contract with `data-presentation-surface="editorial|night"` on presentation side-surfaces. Style `OperatorChat` and `DiscussionPanel` through that contract, keeping existing storyboard, layout, chat messages, and discussion routing intact. Do not introduce a new theme engine or component library in this slice.

**Tech Stack:** React, TypeScript, CSS, Vitest, Testing Library, Playwright CLI screenshot smoke.

## Global Constraints

- Follow design spec: `docs/superpowers/specs/2026-07-08-presentation-surface-theme-normalization-design.md`.
- Do not change `/console`.
- Do not replace chat UI.
- Do not alter storyboard content or scene composition.
- Do not add dependencies.
- Keep CSS scoped to presentation surfaces.
- Prefer semantic surface attributes over ad hoc color selectors.
- Generated `.visual-smoke/` screenshots must remain ignored.

---

## File Structure

- Modify `web/apps/console/src/presentation/OperatorChat.tsx`
  - Add `data-presentation-surface`.
- Modify `web/apps/console/src/presentation/OperatorChat.test.tsx`
  - Pin editorial/night surface mapping.
- Modify `web/apps/console/src/presentation/DiscussionPanel.tsx`
  - Add `data-presentation-surface="editorial"`.
- Modify `web/apps/console/src/presentation/DiscussionPanel.test.tsx`
  - Pin discussion panel surface contract for Q&A branches and legacy branches.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Normalize chat/discussion/presenter-note surfaces.
- Modify `docs/current_roadmap.md`
  - Mark surface normalization complete after implementation.
- Move this plan to `docs/historical/superpowers/plans/2026-07-08-presentation-surface-theme-normalization.md` after implementation.

---

### Task 1: Add Semantic Surface Attributes

**Files:**
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`
- Modify: `web/apps/console/src/presentation/DiscussionPanel.tsx`
- Modify: `web/apps/console/src/presentation/DiscussionPanel.test.tsx`

**Interfaces:**
- Consumes:
  - `compositionForState(state).chatTheme`
  - `DiscussionPanel` branch ID.
- Produces:
  - `OperatorChat` root has `data-presentation-surface="editorial"` when `chatTheme === "light"`, otherwise `"night"`.
  - `DiscussionPanel` root has `data-presentation-surface="editorial"`.

- [ ] **Step 1: Add failing OperatorChat surface test**

In `web/apps/console/src/presentation/OperatorChat.test.tsx`, add this test:

```tsx
  it("maps light chat theme to the editorial presentation surface", () => {
    const state = {
      ...initialPresentationState,
      location: { kind: "main" as const, sceneId: "workflow-demo" as const, beatId: "graph", focusPath: [] },
    };

    render(<OperatorChat state={state} />);

    const chat = screen.getByLabelText("scripted operator chat");
    expect(chat).toHaveAttribute("data-chat-theme", "light");
    expect(chat).toHaveAttribute("data-presentation-surface", "editorial");
  });
```

Add a second test:

```tsx
  it("maps dark chat theme to the night presentation surface", () => {
    render(<OperatorChat state={initialPresentationState} />);

    const chat = screen.getByLabelText("scripted operator chat");
    expect(chat).toHaveAttribute("data-presentation-surface", "night");
  });
```

- [ ] **Step 2: Add failing DiscussionPanel surface tests**

In `web/apps/console/src/presentation/DiscussionPanel.test.tsx`, add:

```tsx
  it("renders Q&A branches on the editorial presentation surface", () => {
    render(<DiscussionPanel branchId="where-is-ai-agent" onClose={onClose} />);

    expect(screen.getByRole("dialog")).toHaveAttribute("data-presentation-surface", "editorial");
  });

  it("renders legacy discussion branches on the same editorial surface", () => {
    render(<DiscussionPanel branchId="hosted-automation" onClose={onClose} />);

    expect(screen.getByRole("dialog")).toHaveAttribute("data-presentation-surface", "editorial");
  });
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx src/presentation/DiscussionPanel.test.tsx
```

Expected: FAIL because `data-presentation-surface` is not emitted yet.

- [ ] **Step 4: Add `OperatorChat` surface attribute**

In `web/apps/console/src/presentation/OperatorChat.tsx`, find:

```tsx
  const composition = compositionForState(state);
  return (
    <aside
      className="operator-chat"
      data-mode={composition.chatMode}
      data-chat-theme={composition.chatTheme}
      data-readable-surface={composition.chatTheme === "light" ? "light" : "dark"}
      aria-label="scripted operator chat"
    >
```

Replace with:

```tsx
  const composition = compositionForState(state);
  const presentationSurface = composition.chatTheme === "light" ? "editorial" : "night";
  return (
    <aside
      className="operator-chat"
      data-mode={composition.chatMode}
      data-chat-theme={composition.chatTheme}
      data-readable-surface={composition.chatTheme === "light" ? "light" : "dark"}
      data-presentation-surface={presentationSurface}
      aria-label="scripted operator chat"
    >
```

- [ ] **Step 5: Add `DiscussionPanel` surface attribute**

In `web/apps/console/src/presentation/DiscussionPanel.tsx`, find the root `<div>`:

```tsx
    <div
      ref={dialogRef}
      className="discussion-panel"
      role="dialog"
      aria-modal="true"
      aria-label={branch.title}
      onKeyDown={trapKeyboardWithinDialog}
    >
```

Add:

```tsx
      data-presentation-surface="editorial"
```

Expected result:

```tsx
    <div
      ref={dialogRef}
      className="discussion-panel"
      data-presentation-surface="editorial"
      role="dialog"
      aria-modal="true"
      aria-label={branch.title}
      onKeyDown={trapKeyboardWithinDialog}
    >
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx src/presentation/DiscussionPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx web/apps/console/src/presentation/DiscussionPanel.tsx web/apps/console/src/presentation/DiscussionPanel.test.tsx
git commit -m "feat: mark presentation side surfaces"
```

---

### Task 2: Normalize Chat Surface Styling

**Files:**
- Modify: `web/apps/console/src/presentation/presentation.css`
- Test: `web/apps/console/src/presentation/OperatorChat.test.tsx`

**Interfaces:**
- Consumes:
  - `.operator-chat[data-presentation-surface="editorial"]`
  - `.operator-chat[data-presentation-surface="night"]`
  - `.chat-message`
  - `.chat-tool-part`
- Produces:
  - Editorial chat cards are off-paper/tinted, not pure white.
  - Night chat cards stay dark and readable.

- [ ] **Step 1: Add test for message surface class stability**

In `OperatorChat.test.tsx`, add this to the light-theme test from Task 1 after the `data-presentation-surface` assertion:

```tsx
    expect(screen.getAllByText(/Found prepared workflow recipe/)[0]?.closest(".chat-message"))
      .toHaveClass("chat-message");
```

This test does not assert computed color. It pins the DOM hook that CSS relies on.

- [ ] **Step 2: Update chat CSS**

In `web/apps/console/src/presentation/presentation.css`, keep the base `.chat-message` dark readable style, then replace the current light override:

```css
.operator-chat[data-readable-surface="light"] .chat-message {
  border-color: color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 35%, transparent);
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 92%, white);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}
```

with:

```css
.operator-chat[data-presentation-surface="editorial"] .chat-message {
  border-color: color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 34%, transparent);
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 82%, var(--color-editorial-muted, oklch(0.48 0.025 65)) 18%);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}
```

Replace:

```css
.operator-chat[data-readable-surface="light"] .chat-message strong {
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}
```

with:

```css
.operator-chat[data-presentation-surface="editorial"] .chat-message strong {
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}
```

Replace:

```css
.operator-chat[data-readable-surface="light"] .chat-tool-part {
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}
```

with:

```css
.operator-chat[data-presentation-surface="editorial"] .chat-tool-part {
  border-color: color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 40%, transparent);
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 70%, transparent);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}
```

Keep `data-readable-surface` selectors only if another rule still uses them. Prefer the new semantic surface selectors for new rules.

- [ ] **Step 3: Run focused test**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx
```

Expected: PASS.

- [ ] **Step 4: Commit Task 2**

```bash
git add web/apps/console/src/presentation/presentation.css web/apps/console/src/presentation/OperatorChat.test.tsx
git commit -m "fix: normalize presentation chat surface"
```

---

### Task 3: Normalize Discussion/Q&A Surface Styling

**Files:**
- Modify: `web/apps/console/src/presentation/presentation.css`
- Test: `web/apps/console/src/presentation/DiscussionPanel.test.tsx`

**Interfaces:**
- Consumes:
  - `.discussion-panel[data-presentation-surface="editorial"]`
  - `.discussion-panel__qna`
  - `.discussion-panel__presenter-note`
- Produces:
  - Discussion panels use editorial surface colors.
  - Q&A answers are readable.
  - Presenter notes are demoted but legible.

- [ ] **Step 1: Add tests for Q&A/presenter-note hooks**

In `DiscussionPanel.test.tsx`, extend `"renders defense Q&A fields when present"` with:

```tsx
    expect(screen.getByLabelText("defense question")).toBeInTheDocument();
```

Extend `"renders speaker hints as presenter notes instead of answer content"` with:

```tsx
    expect(note).toHaveClass("discussion-panel__presenter-note");
```

- [ ] **Step 2: Update discussion panel CSS**

In `web/apps/console/src/presentation/presentation.css`, replace the base `.discussion-panel` rule:

```css
.discussion-panel {
  padding: 1rem;
  border: 1px solid oklch(0.36 0.04 250);
  background: oklch(0.16 0.025 250);
  border-radius: 0.65rem;
}
```

with:

```css
.discussion-panel {
  padding: 1rem;
  border: 1px solid color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 35%, transparent);
  border-radius: 0.75rem;
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 88%, white);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}
```

Update the following selectors to use editorial colors:

```css
.discussion-panel h2 {
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.discussion-panel__badge {
  background: color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 18%, transparent);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.discussion-panel__evidence {
  color: var(--color-editorial-muted, oklch(0.48 0.025 65));
}

.discussion-panel__summary {
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.discussion-panel__qna {
  border-color: color-mix(in oklch, var(--color-intent, oklch(0.53 0.17 250)) 28%, transparent);
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 74%, white);
}

.discussion-panel__question,
.discussion-panel__short-answer {
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.discussion-panel__expanded-answer {
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 82%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
}

.discussion-panel__presenter-note {
  border-color: color-mix(in oklch, var(--color-human, oklch(0.68 0.17 55)) 38%, transparent);
  background: color-mix(in oklch, var(--color-human, oklch(0.68 0.17 55)) 10%, var(--color-editorial-paper, oklch(0.975 0.012 82)));
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 76%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
}

.discussion-panel__presenter-note span {
  color: color-mix(in oklch, var(--color-human, oklch(0.68 0.17 55)) 70%, var(--color-editorial-ink, oklch(0.19 0.015 65)));
}

.discussion-panel__detail {
  color: color-mix(in oklch, var(--color-editorial-ink, oklch(0.19 0.015 65)) 82%, var(--color-editorial-muted, oklch(0.48 0.025 65)));
  border-left-color: color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 42%, transparent);
}
```

Keep `.discussion-panel__return` as a clear action button, but ensure it does not look like a saturated unrelated pill. If needed, update it to:

```css
.discussion-panel__return {
  margin-top: 0.75rem;
  border: 1px solid var(--color-editorial-ink, oklch(0.19 0.015 65));
  border-radius: 0.4rem;
  padding: 0.4rem 0.75rem;
  background: var(--color-editorial-ink, oklch(0.19 0.015 65));
  color: var(--color-editorial-paper, oklch(0.975 0.012 82));
  font-weight: 600;
}
```

- [ ] **Step 3: Run focused test**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 4: Commit Task 3**

```bash
git add web/apps/console/src/presentation/presentation.css web/apps/console/src/presentation/DiscussionPanel.test.tsx
git commit -m "fix: normalize discussion surface theme"
```

---

### Task 4: Screenshot Smoke And Roadmap

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-08-presentation-surface-theme-normalization.md` to `docs/historical/superpowers/plans/2026-07-08-presentation-surface-theme-normalization.md`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: verified visual smoke and updated roadmap.

- [ ] **Step 1: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx src/presentation/DiscussionPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Run build checks**

Run:

```bash
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
git diff --check
```

Expected:
- Typecheck passes.
- Build succeeds. Existing chunk-size warning is acceptable if unchanged.
- No whitespace errors.

- [ ] **Step 3: Capture screenshot smoke**

Start dev server if needed:

```bash
pnpm --dir web dev
```

Capture:

```powershell
New-Item -ItemType Directory -Force web/apps/console/.visual-smoke | Out-Null
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#scene/positioning/landscape" web/apps/console/.visual-smoke/surface-positioning-1280x720.png
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#scene/planner-runtime/planner" web/apps/console/.visual-smoke/surface-planner-runtime-1280x720.png
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#scene/lifecycle/draft" web/apps/console/.visual-smoke/surface-lifecycle-1280x720.png
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#discuss/where-is-ai-agent" web/apps/console/.visual-smoke/surface-qna-agent-1280x720.png
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#discuss/evaluation-validity" web/apps/console/.visual-smoke/surface-qna-evaluation-1280x720.png
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#scene/interrupt-evidence/approval" web/apps/console/.visual-smoke/surface-approval-1280x720.png
```

Manual acceptance:
- Chat is not a bright white card stack.
- Discussion/Q&A panels look editorial and readable.
- Presenter note is demoted but legible.
- Scene 3/4/5 direct surfaces do not look like mismatched dark modals.
- `.visual-smoke/` remains ignored by git.

- [ ] **Step 4: Update roadmap**

In `docs/current_roadmap.md`, under `Next presentation visual slices`, replace:

```md
  2. Surface theme normalization pass: make light chat, discussion modals, and
     Q&A branches use the same editorial presentation surface instead of
     jumping between overly white chat cards and dark modal interiors.
```

with:

```md
  2. Completed: surface theme normalization pass made light chat, discussion
     modals, and Q&A branches use the same editorial presentation surface.
     Implementation:
     [`presentation surface theme normalization`](historical/superpowers/plans/2026-07-08-presentation-surface-theme-normalization.md).
```

Renumber the remaining entries so the scene composition pass is `3` and the
presentation craft pass is `4`.

- [ ] **Step 5: Archive plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-08-presentation-surface-theme-normalization.md docs/historical/superpowers/plans/2026-07-08-presentation-surface-theme-normalization.md
```

If the plan is not tracked yet, use PowerShell:

```powershell
Move-Item docs/superpowers/plans/2026-07-08-presentation-surface-theme-normalization.md docs/historical/superpowers/plans/2026-07-08-presentation-surface-theme-normalization.md
```

- [ ] **Step 6: Commit Task 4**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-08-presentation-surface-theme-normalization.md
git commit -m "docs: record presentation surface normalization"
```

---

## Final Verification

- [ ] Run focused tests:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx src/presentation/DiscussionPanel.test.tsx
```

Expected: PASS.

- [ ] Run full web tests:

```bash
pnpm --dir web test
```

Expected: PASS.

- [ ] Run full web typecheck:

```bash
pnpm --dir web typecheck
```

Expected: PASS.

- [ ] Run status checks:

```bash
git diff --check
git status --short
```

Expected:
- No whitespace errors.
- No untracked `.visual-smoke/` files.
- Only intentional files remain if not yet committed.

---

## Review Checklist

- Chat no longer appears as a bright white card stack.
- Direct discussion routes are readable and editorial.
- Q&A branches and legacy branches use the same discussion surface.
- Presenter notes are demoted and legible.
- `/console` unchanged.
- No new dependency added.
- Scene composition remains deferred to the next slice.
