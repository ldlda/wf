# Defense Speech Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the terminology-heavy timed narration for Scenes 1-8 with a clear audience goal, anchor terms, and short suggested wording for every beat.

**Architecture:** Keep `presenter-notes.ts` as the typed source of truth and add `goal` plus `keywords` beside the existing suggested `mustSay` wording. Render all three in `/presenter`, keep the readable runbook synchronized through tests, and preserve evidence pointers, warnings, fallbacks, and Q&A links.

**Tech Stack:** TypeScript, Vitest, Markdown runbooks, React presenter route.

## Global Constraints

- The audience-facing storyboard remains unchanged in this slice.
- Do not remove evidence warnings, replay disclosures, or Q&A links.
- Every beat must define one audience goal and one to three anchor terms.
- Scenes 1-8 must additionally use one short suggested sentence per beat.
- `mustSay` is suggested wording, not a word-for-word obligation; `/presenter` must label it accordingly.
- Provider neutrality, typed contracts, source resolution, resume boundaries, and NodeUse remain optional-detail or Q&A material unless a beat visually demonstrates them.
- The timed Scenes 1-8 path must total 257 seconds or less.
- The complete must-say catalog must contain 500-700 words.

---

### Task 1: Pin Goals, Keywords, Simpler Speech, And Timing

**Files:**
- Modify: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`
- Test: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`

**Interfaces:**
- Consumes: `presenterNotes`, `presenterSceneNotes()`, `mainSpeechWordCount()`.
- Produces: regression constraints for the rewritten catalog.

- [ ] **Step 1: Replace the old timing and word-budget expectations**

Assert scene totals of `[30, 30, 35, 40, 36, 32, 12, 42, 35, 30, 50, 120, 75]`, a complete-deck target of `642` including the existing 75-second navigation buffer, and a `500-700` word budget. Check every beat has a non-empty `goal` and one to three non-empty `keywords`. Separately check that no suggested `mustSay` value in Scenes 1-8 exceeds 28 words.

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

for (const note of presenterNotes) {
  expect(note.goal.trim().length, `${note.sceneId}/${note.beatId}`).toBeGreaterThan(0);
  expect(note.keywords.length, `${note.sceneId}/${note.beatId}`).toBeGreaterThanOrEqual(1);
  expect(note.keywords.length, `${note.sceneId}/${note.beatId}`).toBeLessThanOrEqual(3);
  expect(note.keywords.every((keyword) => keyword.trim().length > 0)).toBe(true);
}

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

### Task 2: Add Goals And Keywords To Every Beat, Then Rewrite Scenes 1-8

**Files:**
- Modify: `web/apps/console/src/presentation/presenter/presenter-notes.ts`
- Test: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`

**Interfaces:**
- Consumes: `beatNote()` and the existing note metadata.
- Produces: presenter goals, anchor terms, and suggested speech rendered by `/presenter`.

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

- [ ] **Step 2: Extend the presenter note type and constructor**

Add these required fields:

```ts
export type PresenterBeatNote = {
  readonly sceneId: MainSceneId;
  readonly beatId: string;
  readonly targetSeconds: number;
  readonly goal: string;
  readonly keywords: readonly [string, ...string[]];
  readonly mustSay: string;
  // existing metadata remains unchanged
};
```

Add `goal` and `keywords` parameters to `beatNote()` before `mustSay`. Keep
`mustSay` as the existing field name to avoid unrelated navigation churn.

- [ ] **Step 3: Add exact goals and keywords for every beat**

Use this catalog in storyboard order:

```text
thesis/title: Goal "Separate the AI-agent ambition from the implemented contribution." Keywords "AI-agent goal", "platform underneath"
thesis/substrate: Goal "State what the platform lets its users do." Keywords "agents and humans", "build, run, inspect"
problem/direct-actions: Goal "Show why one successful chat is not yet automation." Keywords "tool calls", "not reusable"
problem/missing-contracts: Goal "Name the minimum durable properties reusable automation needs." Keywords "saved definition", "validation", "execution records"
positioning/landscape: Goal "Place the work beside familiar adjacent systems." Keywords "Python / n8n / Zapier", "LangGraph", "MCP"
positioning/lda-position: Goal "State the platform's narrow position without a superiority claim." Keywords "provider-neutral", "workflow layer", "not a replacement"
planner-runtime/planner: Goal "Assign workflow decisions to an external planner." Keywords "human or AI planner"
planner-runtime/runtime: Goal "Assign execution and recording to the runtime." Keywords "validation", "step-by-step execution", "state and traces"
planner-runtime/boundary: Goal "Introduce the public seam between clients and runtime." Keywords "Workflow API", "CLI", "JSON-RPC"
lifecycle/draft: Goal "Introduce the editable lifecycle state." Keywords "Draft", "being built"
lifecycle/artifact: Goal "Introduce the immutable saved definition." Keywords "Artifact", "immutable version"
lifecycle/deployment: Goal "Connect a saved definition to a runnable environment." Keywords "Deployment", "sources", "ready"
lifecycle/run: Goal "Introduce one persisted execution record." Keywords "Run", "status", "output and trace"
architecture/overview: Goal "Show how the implementation realizes the earlier concepts." Keywords "architecture spine"
architecture/client: Goal "Show that humans and agents share one public surface." Keywords "shared operations"
architecture/api: Goal "Identify the system's public front door." Keywords "Workflow API", "public boundary"
architecture/runtime: Goal "Explain what the server composes behind the API." Keywords "WorkflowServer", "records and capabilities", "execution core"
agent-handoff/request: Goal "Disclose the prepared demonstration before it begins." Keywords "prepared example", "not an autonomous planner"
prepared-lifecycle/discover: Goal "Show that authoring starts with interface discovery." Keywords "sources", "capabilities"
prepared-lifecycle/draft: Goal "Show mutable workflow authoring." Keywords "Draft", "editable workflow"
prepared-lifecycle/diagnose: Goal "Show a concrete structured validation failure." Keywords "validation", "missing_outcome_edge"
prepared-lifecycle/repair: Goal "Show the exact focused correction and revalidation." Keywords "set-route", "validation passes"
prepared-lifecycle/artifact: Goal "Show the transition to an immutable saved version." Keywords "Artifact", "immutable"
prepared-lifecycle/deployment: Goal "Show source binding and readiness before execution." Keywords "Deployment", "three local sources"
run-from-deployment/input: Goal "Show the concrete inputs supplied before execution." Keywords "run input", "selected documents"
run-from-deployment/operation: Goal "Show that one public operation creates a persisted execution." Keywords "workflow.runs.start", "persisted Run"
run-from-deployment/graph: Goal "Show the reusable workflow executing beyond the chat conversation." Keywords "workflow graph", "declared interrupt"
typed-human-boundary/interrupt: Goal "Show what the paused workflow asks from the operator." Keywords "issue_review", "interrupt payload", "resume schema"
typed-human-boundary/approval: Goal "Show that the operator chooses a declared continuation." Keywords "submitted", "revision-requested", "typed resume"
resume-output-evidence/resume: Goal "Show continuation of the same recorded run." Keywords "workflow.runs.resume", "same Run"
resume-output-evidence/output: Goal "Show the persisted terminal results of the submitted path." Keywords "report output", "issue-board changes"
resume-output-evidence/trace: Goal "Show that execution evidence remains inspectable after completion." Keywords "trace frames", "protocol evidence"
evaluation/cohort: Goal "Describe the external-agent evaluation design." Keywords "36 trials", "two challenges", "three profiles"
evaluation/validity: Goal "Separate audited valid evidence from contaminated samples." Keywords "27 pass", "8 invalid", "1 fail"
evaluation/findings: Goal "State what the evaluation supports and what it cannot prove." Keywords "longitudinal evidence", "not a benchmark"
conclusion/limits: Goal "Bound the prototype claims before the final contribution statement." Keywords "prototype", "not production security"
conclusion/future: Goal "Name the surrounding layers left as future work." Keywords "live agent", "scheduling", "controlled evaluation"
conclusion/conclusion: Goal "Restate the implemented contribution and planner-runtime boundary." Keywords "planner proposes", "platform executes"
conclusion/questions: Goal "Open structured examiner discussion without introducing new claims." Keywords "defense questions", "evidence"
```

- [ ] **Step 4: Replace the exact `mustSay` values for Scenes 1-8**

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

- [ ] **Step 5: Run the focused test and verify only UI/runbook synchronization remains RED**

Run the focused presenter-note test. Expected: catalog/timing/word constraints pass; synchronization fails because the readable runbook still contains the old speech.

- [ ] **Step 6: Commit the typed catalog rewrite**

```powershell
git add web/apps/console/src/presentation/presenter/presenter-notes.ts web/apps/console/src/presentation/presenter/presenter-notes.test.ts
git commit -m "docs: simplify opening defense speech"
```

### Task 3: Render Goals And Keywords In `/presenter`

**Files:**
- Modify: `web/apps/console/src/presentation/presenter/PresenterNote.tsx`
- Modify: `web/apps/console/src/presentation/presenter/PresenterNote.test.tsx`
- Modify: `web/apps/console/src/presentation/presenter/presenter.css`

**Interfaces:**
- Consumes: `PresenterBeatNote.goal`, `keywords`, and `mustSay`.
- Produces: a rehearsal surface that distinguishes the slide goal, anchor terms, and flexible wording.

- [ ] **Step 1: Write failing presenter-note tests**

Assert the current note renders regions labelled `Beat goal`, `Anchor terms`,
and `Suggested wording`. Assert every keyword is visible and that the old label
`Must say` is absent.

- [ ] **Step 2: Run the focused test and verify RED**

Run `PresenterNote.test.tsx` directly.

- [ ] **Step 3: Render the three-level rehearsal hierarchy**

Render the goal first as one concise sentence, keywords second as a plain list
of one to three strong terms, and the Markdown sentence under `Suggested
wording`. Do not render keywords as decorative pills; use readable inline text
or a compact list.

- [ ] **Step 4: Style for desktop and mobile rehearsal**

Keep the goal visually strongest, keywords high-contrast and scannable, and
suggested wording readable but subordinate. Preserve the stable Previous/Next
bar and existing Q&A sidebar.

- [ ] **Step 5: Run tests and commit**

```powershell
pnpm --dir web --filter @lda/console test -- src/presentation/presenter/PresenterNote.test.tsx
git add web/apps/console/src/presentation/presenter
git commit -m "feat: show presenter goals and anchor terms"
```

### Task 4: Synchronize The Readable Speech Runbook

**Files:**
- Modify: `docs/runbooks/defense-speech-and-claim-audit.md`
- Test: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`

**Interfaces:**
- Consumes: exact `mustSay` strings from Task 2.
- Produces: a readable rehearsal document synchronized with `/presenter`.

Add each beat's **Goal** and **Anchor terms** throughout the runbook. For Scenes
1-8, also replace the **Suggested wording** with the exact plain-text version of
Task 2's `mustSay` value so the existing synchronization test stays meaningful.

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

### Task 5: Close The Speech Slice

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
