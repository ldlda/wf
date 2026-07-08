# Presentation Contrast Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the immediate `/present` readability regressions from the visual pass: dark-on-dark Scene 7 authoring loop text, dark-on-dark Scene 10 chat rail text, and generated screenshot hygiene.

**Architecture:** Treat this as a bugfix, not a redesign. Add explicit foreground colors and small DOM/test hooks where the contrast contract matters, keep the existing presentation layout, and verify with focused tests plus screenshots. Do not change scene composition, chat framework, or storyboard content.

**Tech Stack:** React, TypeScript, CSS, Vitest, Testing Library, Playwright CLI screenshot smoke.

## Global Constraints

- Do not change `/console`.
- Do not add dependencies.
- Do not rewrite chat UI in this slice.
- Do not alter storyboard scene order or branch content.
- Keep visual fixes scoped to `web/apps/console/src/presentation`.
- Explicitly set foreground colors where dark surfaces are used.
- Generated screenshot directories must not remain untracked after the slice.

---

## File Structure

- Modify `web/apps/console/src/presentation/SceneBody.tsx`
  - Add stable readability data hooks to Scene 7 authoring nodes.
- Modify `web/apps/console/src/presentation/SceneBody.test.tsx`
  - Pin Scene 7 authoring node readability hook.
- Modify `web/apps/console/src/presentation/OperatorChat.tsx`
  - Restore or add chat theme/readability attributes.
- Modify `web/apps/console/src/presentation/OperatorChat.test.tsx`
  - Pin chat surface readability attributes.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Set explicit authoring-loop and chat-rail foreground colors.
- Modify `.gitignore`
  - Ignore generated visual smoke screenshot folder.
- Modify `docs/current_roadmap.md`
  - Mark contrast/readability pass completed after implementation.
- Move this plan to `docs/historical/superpowers/plans/2026-07-08-presentation-contrast-readability.md` after implementation.

---

### Task 1: Scene 7 Authoring Loop Contrast

**Files:**
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: existing Scene 7 authoring loop DOM:
  - `aria-label="agent authoring loop"`
  - `.scene-body__authoring-node`
  - `data-authoring-active`
  - `data-authoring-past`
- Produces:
  - `data-readable-surface="dark"`
  - explicit foreground colors for label/detail/number on authoring nodes.

- [ ] **Step 1: Add a failing readability-hook test**

In `web/apps/console/src/presentation/SceneBody.test.tsx`, inside the existing test `"renders Scene 7 as an agent authoring loop with beat-specific emphasis"`, add this assertion after `const loop = ...`:

```tsx
    expect(loop).toHaveAttribute("data-readable-surface", "dark");
```

Also add this assertion after the active-stage assertion:

```tsx
    expect(screen.getByText("Validate and diagnose").closest(".scene-body__authoring-node"))
      .toHaveAttribute("data-readable-surface", "dark");
```

- [ ] **Step 2: Run failing test**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
```

Expected: FAIL because the authoring loop does not expose the readability hook yet.

- [ ] **Step 3: Add readability data hooks**

In `web/apps/console/src/presentation/SceneBody.tsx`, change:

```tsx
    <div className="scene-body__authoring-loop" aria-label="agent authoring loop" data-active-stage={beat.id}>
```

to:

```tsx
    <div
      className="scene-body__authoring-loop"
      aria-label="agent authoring loop"
      data-active-stage={beat.id}
      data-readable-surface="dark"
    >
```

Change the authoring node element:

```tsx
          <div
            key={step.id}
            className="scene-body__authoring-node"
            data-authoring-active={isActive}
            data-authoring-past={isPast}
          >
```

to:

```tsx
          <div
            key={step.id}
            className="scene-body__authoring-node"
            data-authoring-active={isActive}
            data-authoring-past={isPast}
            data-readable-surface="dark"
          >
```

- [ ] **Step 4: Fix authoring foreground CSS**

In `web/apps/console/src/presentation/presentation.css`, update `.scene-body__authoring-node` to set explicit text color:

```css
.scene-body__authoring-node {
  position: relative;
  z-index: 1;
  display: grid;
  align-content: start;
  gap: 0.35rem;
  min-height: 8.6rem;
  border: 1px solid color-mix(in oklch, var(--stage-line) 72%, transparent);
  border-radius: 0.75rem;
  padding: 0.75rem;
  background: color-mix(in oklch, var(--stage-surface) 88%, transparent);
  color: var(--text-primary);
  transition: opacity 180ms ease, transform 180ms ease, border-color 180ms ease, background 180ms ease;
}
```

Add:

```css
.scene-body__authoring-node strong {
  color: var(--text-primary);
}
```

Replace:

```css
.scene-body__authoring-node small {
  color: var(--text-muted);
  font: 0.72rem/1.35 var(--font-interface);
}
```

with:

```css
.scene-body__authoring-node small {
  color: color-mix(in oklch, var(--text-primary) 72%, var(--text-muted));
  font: 0.72rem/1.35 var(--font-interface);
}
```

If `--text-primary` or `--text-muted` are not available in this scope during browser review, use the existing stage tokens already present in nearby CSS. Do not introduce new global tokens.

- [ ] **Step 5: Run focused test**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "fix: restore authoring loop contrast"
```

---

### Task 2: Scene 10 Chat Rail Contrast

**Files:**
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes:
  - `compositionForState(state)` result with `chatMode` and `chatTheme`.
  - Existing `.operator-chat` and `.chat-message` CSS classes.
- Produces:
  - `data-chat-theme={composition.chatTheme}`
  - `data-readable-surface="dark"` or `"light"` on the chat root.
  - explicit chat message foreground colors.

- [ ] **Step 1: Add failing chat theme/readability test**

In `web/apps/console/src/presentation/OperatorChat.test.tsx`, add:

```tsx
  it("exposes chat theme and readable surface attributes", () => {
    render(<OperatorChat state={initialPresentationState} />);

    const chat = screen.getByLabelText("scripted operator chat");
    expect(chat).toHaveAttribute("data-chat-theme");
    expect(chat).toHaveAttribute("data-readable-surface");
  });
```

- [ ] **Step 2: Run failing test**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx
```

Expected: FAIL because `OperatorChat` currently emits `data-mode` only.

- [ ] **Step 3: Restore chat attributes**

In `web/apps/console/src/presentation/OperatorChat.tsx`, replace:

```tsx
    <aside className="operator-chat" data-mode={composition.chatMode} aria-label="scripted operator chat">
```

with:

```tsx
    <aside
      className="operator-chat"
      data-mode={composition.chatMode}
      data-chat-theme={composition.chatTheme}
      data-readable-surface={composition.chatTheme === "light" ? "light" : "dark"}
      aria-label="scripted operator chat"
    >
```

If `composition.chatTheme` can be undefined in the current type, use:

```tsx
      data-chat-theme={composition.chatTheme ?? "dark"}
      data-readable-surface={(composition.chatTheme ?? "dark") === "light" ? "light" : "dark"}
```

Prefer the typed version if the compiler accepts it.

- [ ] **Step 4: Fix chat foreground CSS**

In `web/apps/console/src/presentation/presentation.css`, replace the current `.chat-message` rule with explicit foreground:

```css
.chat-message {
  border: 1px solid oklch(0.34 0.035 250);
  border-radius: 0.65rem;
  padding: 0.65rem 0.75rem;
  background: oklch(0.18 0.025 250);
  color: var(--text-primary);
  font-size: 0.85rem;
}
```

Add:

```css
.chat-message strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
}

.chat-message p,
.chat-message span,
.chat-message code {
  color: inherit;
}

.operator-chat[data-readable-surface="light"] .chat-message {
  border-color: color-mix(in oklch, var(--color-editorial-muted, oklch(0.48 0.025 65)) 35%, transparent);
  background: color-mix(in oklch, var(--color-editorial-paper, oklch(0.975 0.012 82)) 92%, white);
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}

.operator-chat[data-readable-surface="light"] .chat-message strong {
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}
```

Then inspect the existing `.chat-tool-part` rules around `presentation.css:604`. If they set dark text implicitly, add:

```css
.chat-tool-part {
  color: var(--text-primary);
}

.operator-chat[data-readable-surface="light"] .chat-tool-part {
  color: var(--color-editorial-ink, oklch(0.19 0.015 65));
}
```

Do not restyle the chat layout beyond foreground/readability.

- [ ] **Step 5: Run focused test**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/OperatorChat.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add web/apps/console/src/presentation/OperatorChat.tsx web/apps/console/src/presentation/OperatorChat.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "fix: restore presentation chat contrast"
```

---

### Task 3: Visual Smoke Hygiene And Roadmap

**Files:**
- Modify: `.gitignore`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-08-presentation-contrast-readability.md` to `docs/historical/superpowers/plans/2026-07-08-presentation-contrast-readability.md`

**Interfaces:**
- Consumes: Task 1 and Task 2 fixes.
- Produces: clean worktree with generated screenshots ignored or removed.

- [ ] **Step 1: Ignore generated screenshot folder**

Add this near the testing/coverage ignores in root `.gitignore`:

```gitignore
# Local presentation screenshots
web/apps/console/.visual-smoke/
```

- [ ] **Step 2: Remove existing generated folder if present**

Run:

```powershell
$target = Resolve-Path -LiteralPath 'web/apps/console/.visual-smoke' -ErrorAction SilentlyContinue
if ($target -and $target.Path -like (Resolve-Path '.').Path + '*') {
  Remove-Item -LiteralPath $target.Path -Recurse -Force
}
```

Expected: no `web/apps/console/.visual-smoke/` entry in `git status --short`.

- [ ] **Step 3: Re-capture two screenshots for review only**

Start dev server if needed:

```bash
pnpm --dir web dev
```

Capture:

```powershell
New-Item -ItemType Directory -Force web/apps/console/.visual-smoke | Out-Null
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#scene/authoring/discover" web/apps/console/.visual-smoke/scene-07-authoring-contrast-1280x720.png
pnpx playwright screenshot --viewport-size=1280,720 "http://127.0.0.1:5173/present#scene/interrupt-evidence/approval" web/apps/console/.visual-smoke/scene-10-approval-contrast-1280x720.png
```

Manual acceptance:
- Scene 7 authoring node labels and details are readable.
- Scene 10 chat rail labels and message text are readable.
- Screenshot folder remains ignored by git.

- [ ] **Step 4: Update roadmap**

In `docs/current_roadmap.md`, under `Next presentation visual slices`, replace:

```md
  1. Contrast and readability fix pass: repair dark-on-dark text in the Scene 7
     authoring loop and the Scene 10 chat rail, then ignore or remove generated
     `.visual-smoke/` screenshots.
```

with:

```md
  1. Completed: contrast and readability fix pass repaired dark-on-dark text in
     the Scene 7 authoring loop and the Scene 10 chat rail, and ignored local
     `.visual-smoke/` screenshots. Implementation:
     [`presentation contrast readability`](historical/superpowers/plans/2026-07-08-presentation-contrast-readability.md).
```

- [ ] **Step 5: Archive plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-08-presentation-contrast-readability.md docs/historical/superpowers/plans/2026-07-08-presentation-contrast-readability.md
```

If the plan is not tracked yet, use PowerShell:

```powershell
Move-Item docs/superpowers/plans/2026-07-08-presentation-contrast-readability.md docs/historical/superpowers/plans/2026-07-08-presentation-contrast-readability.md
```

- [ ] **Step 6: Commit Task 3**

```bash
git add .gitignore docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-08-presentation-contrast-readability.md
git commit -m "docs: record presentation contrast readability pass"
```

---

## Final Verification

- [ ] Run focused tests:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx src/presentation/OperatorChat.test.tsx
```

Expected: PASS.

- [ ] Run console typecheck:

```bash
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

- [ ] Run full web tests:

```bash
pnpm --dir web test
```

Expected: PASS.

- [ ] Run whitespace/status checks:

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

- Scene 7 screenshot has readable authoring labels and details.
- Scene 10 screenshot has readable chat rail labels and message text.
- `/console` unaffected.
- No layout/composition changes beyond contrast/readability.
- `.visual-smoke/` ignored or removed.
- Roadmap still lists scene composition pass and craft pass as follow-ups.
