# Defense Speech Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the terminology-heavy timed narration for Scenes 1-8 with short spoken English that carries one idea per beat.

**Architecture:** Keep `presenter-notes.ts` as the typed source of truth and keep the readable runbook synchronized through its existing test. Only `mustSay` text and timing change; evidence pointers, warnings, fallbacks, and Q&A links remain available to the presenter.

**Tech Stack:** TypeScript, Vitest, Markdown runbooks, React presenter route.

## Global Constraints

- The audience-facing storyboard remains unchanged in this slice.
- Do not remove evidence warnings, replay disclosures, or Q&A links.
- Scenes 1-8 must use one mandatory spoken idea per beat and avoid lists of unexplained system nouns.
- Provider neutrality, typed contracts, source resolution, resume boundaries, and NodeUse remain optional-detail or Q&A material unless a beat visually demonstrates them.
- The timed Scenes 1-8 path must total 257 seconds or less.
- The complete must-say catalog must contain 500-700 words.

---

### Task 1: Pin The Simpler Speech And Timing Contract

**Files:**
- Modify: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`
- Test: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`

**Interfaces:**
- Consumes: `presenterNotes`, `presenterSceneNotes()`, `mainSpeechWordCount()`.
- Produces: regression constraints for the rewritten catalog.

- [ ] **Step 1: Replace the old timing and word-budget expectations**

Assert scene totals of `[30, 30, 35, 40, 36, 32, 12, 42, 35, 30, 50, 120, 75]`, a complete-deck target of `642` including the existing 75-second navigation buffer, and a `500-700` word budget. Add a loop over Scenes 1-8 that strips Markdown emphasis, splits on whitespace, and asserts no `mustSay` value exceeds 28 words.

```ts
const openingSceneIds = new Set([
  "thesis",
  "problem",
  "positioning",
  "planner-runtime",
  "lifecycle",
  "architecture",
  "agent-handoff",
  "prepared-lifecycle",
]);

for (const note of presenterNotes.filter((item) => openingSceneIds.has(item.sceneId))) {
  const words = note.mustSay.replaceAll("**", "").trim().split(/\s+/);
  expect(words.length, `${note.sceneId}/${note.beatId}`).toBeLessThanOrEqual(28);
}
```

- [ ] **Step 2: Replace the obsolete diagnostic assertions**

```ts
expect(presenterBeatNoteFor("prepared-lifecycle", "diagnose")?.mustSay)
  .toMatch(/missing.*route/i);
expect(presenterBeatNoteFor("prepared-lifecycle", "repair")?.mustSay)
  .toMatch(/adds.*route|route.*validation passes/i);
expect(presenterBeatNoteFor("prepared-lifecycle", "diagnose")?.mustSay)
  .not.toMatch(/output projection/i);
```

- [ ] **Step 3: Run the focused test and verify RED**

Run:

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/presenter/presenter-notes.test.ts
```

Expected: failures for timing, word budget, maximum beat length, and the obsolete diagnostic text.

- [ ] **Step 4: Commit the failing contract**

```powershell
git add web/apps/console/src/presentation/presenter/presenter-notes.test.ts
git commit -m "test: define simpler defense speech contract"
```

### Task 2: Rewrite Scenes 1-8 Must-Say Notes

**Files:**
- Modify: `web/apps/console/src/presentation/presenter/presenter-notes.ts`
- Test: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`

**Interfaces:**
- Consumes: `beatNote()` and the existing note metadata.
- Produces: the exact presenter speech rendered by `/presenter`.

- [ ] **Step 1: Set the new target seconds**

Use these per-beat values:

```ts
// Scene 1: 15, 15
// Scene 2: 15, 15
// Scene 3: 18, 17
// Scene 4: 12, 16, 12
// Scene 5: 9, 9, 9, 9
// Scene 6: 6, 8, 9, 9
// Scene 7: 12
// Scene 8: 7, 7, 7, 7, 7, 7
```

- [ ] **Step 2: Replace the exact `mustSay` values for Scenes 1-8**

Use these sentences in storyboard order:

```text
The title describes the original goal: an AI agent for workspace automation. My contribution is the platform underneath that agent.
It lets agents and humans build workflows, run them, and inspect what happened.

Like the chat example, an agent can call tools and finish one task. But that conversation is not yet a reusable workflow.
Reusable automation needs a saved definition, validation, execution records, and a clear way to pause and continue.

Existing systems solve different parts of this problem: Python scripts, n8n, Zapier, LangGraph, and MCP.
My platform does not replace them. It provides a provider-neutral workflow layer that agents and humans can operate.

A human or AI planner decides what workflow to build.
The runtime validates the graph, executes it step by step, records state and traces, and pauses at declared boundaries.
Both sides communicate through the Workflow API. Today, clients reach it through the CLI or JSON-RPC without accessing runtime internals directly.

A workflow moves through four lifecycle stages. Draft means the workflow is still being built.
Artifact is a saved, immutable version.
Deployment connects that version to the sources it needs and checks whether it is ready.
Run is one recorded execution, including its status, output, and trace.

This is how those concepts are organized in the implementation.
Humans and agents use the same public workflow operations.
The Workflow API is the front door. It exposes lifecycle operations without exposing runtime internals.
Behind it, the workflow server brings together stored records, available capabilities, and the execution core.

This is a prepared example, not a live autonomous AI agent. It shows how an agent could use the platform to build and run a workflow.

First, the agent checks which sources and operations are available.
Then it builds an editable workflow draft.
Validation finds that the analyze step has no route for its ok outcome.
The agent adds that route, and validation passes.
The valid workflow is saved as an immutable artifact.
Finally, a deployment connects it to the three local sources it needs.
```

Preserve the existing warnings, fallbacks, evidence pointers, and Q&A branch IDs. Move the existing qualification about fixed definitions/provider variability into `optionalDetail` on `planner-runtime/runtime` if it is not already represented by `warning`.

- [ ] **Step 3: Run the focused test and verify only runbook synchronization remains RED**

Run the focused presenter-note test. Expected: catalog/timing/word constraints pass; synchronization fails because the readable runbook still contains the old speech.

- [ ] **Step 4: Commit the typed catalog rewrite**

```powershell
git add web/apps/console/src/presentation/presenter/presenter-notes.ts web/apps/console/src/presentation/presenter/presenter-notes.test.ts
git commit -m "docs: simplify opening defense speech"
```

### Task 3: Synchronize The Readable Speech Runbook

**Files:**
- Modify: `docs/runbooks/defense-speech-and-claim-audit.md`
- Test: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`

**Interfaces:**
- Consumes: exact `mustSay` strings from Task 2.
- Produces: a readable rehearsal document synchronized with `/presenter`.

- [ ] **Step 1: Update timing prose and table**

Change the must-say target from `11:00` to `9:27`, retain a `1:15` navigation buffer, and set the complete-deck target to `10:42`. Update the Scenes 1-8 segment times to match Task 2; leave Scenes 9-13 targets unchanged.

- [ ] **Step 2: Replace the Scene 1-8 `Say:` blocks verbatim**

Use the exact plain-text versions of Task 2's sentences. Keep claim qualifications below each block; do not require the presenter to speak them.

- [ ] **Step 3: Run verification**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/presenter/presenter-notes.test.ts
pnpm --dir web --filter @lda/console typecheck
git diff --check
```

Expected: all presenter tests pass, typecheck is clean, and no whitespace errors are reported.

- [ ] **Step 4: Verify `/presenter` at desktop and mobile widths**

Open `/presenter#scene/planner-runtime/boundary` and `/presenter#scene/architecture/api` at `1280x720` and `390x844`. Confirm bold phrases remain readable, Previous/Next controls stay stable, and the simplified `mustSay` text does not overflow.

- [ ] **Step 5: Commit the synchronized runbook**

```powershell
git add docs/runbooks/defense-speech-and-claim-audit.md
git commit -m "docs: synchronize simplified defense runbook"
```

### Task 4: Close The Speech Slice

**Files:**
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-07-13-defense-speech-simplification.md` to `docs/historical/superpowers/plans/2026-07-13-defense-speech-simplification.md`

**Interfaces:**
- Consumes: verified implementation from Tasks 1-3.
- Produces: accurate live roadmap status and historical implementation record.

- [ ] **Step 1: Mark only the speech item completed**

Leave the Scene 8 evidence item planned until its separate plan is implemented.

- [ ] **Step 2: Move this completed plan and verify links**

Update the roadmap link to the historical path, run `git diff --check`, and confirm no live document points to the old active-plan path.

- [ ] **Step 3: Commit docs closure**

```powershell
git add docs/current_roadmap.md docs/superpowers/plans/2026-07-13-defense-speech-simplification.md docs/historical/superpowers/plans/2026-07-13-defense-speech-simplification.md
git commit -m "docs: complete defense speech simplification"
```
