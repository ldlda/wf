# Defense Q&A Branch Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Project the strongest defense Q&A runbook answers into `/present` discussion branches so the presenter can open likely examiner questions directly from the defense deck.

**Architecture:** Keep `web/apps/console/src/presentation/storyboard.ts` as the single source of truth for discussion branch metadata. Extend the existing `DiscussionBranchDefinition` shape with optional Q&A fields, render those fields in `DiscussionPanel`, and attach a small core set of examiner questions to the most relevant existing scenes. Do not add a second Q&A router, transport, state store, or modal system.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing presentation reducer/navigation, existing CSS module-free presentation stylesheet.

## Global Constraints

- Preserve the existing `/present` hash contract: main scenes use `#scene/<scene>/<beat>` and branches use `#discuss/<branch>`.
- Keep discussion branch data in `storyboard.ts`; do not create a separate Q&A catalog unless this file becomes too large in a future slice.
- Branches must stay presenter-safe: concise question, short spoken answer, optional expanded answer, evidence pointer, and optional links.
- Do not change the 12-scene order or existing scene IDs.
- Do not implement visual redesign, chat replacement, schema forms, presenter companion, or guided beat gates in this slice.
- Run focused console tests before broad web checks.

---

## File Structure

- Modify `web/apps/console/src/presentation/storyboard.ts`
  - Extend `DiscussionBranchDefinition`.
  - Add `QuestionAnswerBranchFields`.
  - Add core defense Q&A branches and upgrade selected existing branches with Q&A fields.
- Modify `web/apps/console/src/presentation/DiscussionPanel.tsx`
  - Render optional `question`, `shortAnswer`, `expandedAnswer`, and `speakerHint`.
  - Preserve existing title, claim badge, evidence, summary, detail, links, focus trap, and return behavior.
- Modify `web/apps/console/src/presentation/presentation.css`
  - Add compact panel styles for Q&A fields.
  - Keep styles scoped to `.discussion-panel`.
- Modify `web/apps/console/src/presentation/storyboard.test.ts`
  - Pin required core branch IDs and Q&A field completeness.
- Modify `web/apps/console/src/presentation/storyboard-navigation.test.ts`
  - Pin hash round-trip for one new Q&A branch.
- Modify `web/apps/console/src/presentation/DiscussionPanel.test.tsx`
  - Assert Q&A rendering and existing detail/link behavior.
- Modify `web/apps/console/src/presentation/SceneBody.test.tsx`
  - Assert scene-local buttons expose the new Q&A branch.
- Modify `docs/current_roadmap.md`
  - Mark the Q&A branch projection as completed and link the historical plan after implementation.
- Move this plan to `docs/historical/superpowers/plans/2026-07-08-defense-qna-branch-projection.md` after implementation.

---

### Task 1: Extend Discussion Branch Data Model

**Files:**
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Test: `web/apps/console/src/presentation/storyboard.test.ts`

**Interfaces:**
- Consumes: existing `DiscussionBranchDefinition`, `discussionBranches`, `DiscussionBranchId`, `findDiscussionBranch`.
- Produces: optional branch fields `question`, `shortAnswer`, `expandedAnswer`, `speakerHint` for Task 2 rendering.

- [ ] **Step 1: Add failing tests for core Q&A branch coverage**

Add these tests to `web/apps/console/src/presentation/storyboard.test.ts` inside the existing `describe("defense storyboard catalog", ...)` block:

```ts
  it("defines core defense Q&A branches for expected examiner questions", () => {
    expect(discussionBranches.map((branch) => branch.id)).toEqual(
      expect.arrayContaining([
        "where-is-ai-agent",
        "title-ai-agent-wording",
        "not-just-cli",
        "not-just-scripts",
        "evaluation-validity",
        "security-production-boundary",
        "demo-reliability",
        "prepared-replay-boundary",
        "why-schemas",
        "production-readiness",
      ]),
    );
  });

  it("keeps defense Q&A branches speaker-ready", () => {
    const qnaBranches = discussionBranches.filter((branch) => branch.question);
    expect(qnaBranches.length).toBeGreaterThanOrEqual(10);
    for (const branch of qnaBranches) {
      expect(branch.question).toMatch(/\?$/);
      expect(branch.shortAnswer?.length).toBeGreaterThan(40);
      expect(branch.shortAnswer?.length).toBeLessThan(360);
      expect(branch.expandedAnswer?.length).toBeGreaterThan(80);
      expect(branch.evidencePointer.length).toBeGreaterThan(0);
    }
  });
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts
```

Expected: FAIL because the new branch IDs and Q&A fields do not exist yet.

- [ ] **Step 3: Extend the branch type**

In `web/apps/console/src/presentation/storyboard.ts`, replace the current `DiscussionBranchDefinition` type with:

```ts
type DiscussionLink = {
  readonly label: string;
  readonly href: string;
};

type DiscussionBranchDetail = {
  readonly text: string;
  readonly links?: readonly DiscussionLink[];
};

type QuestionAnswerBranchFields = {
  readonly question?: string;
  readonly shortAnswer?: string;
  readonly expandedAnswer?: string;
  readonly speakerHint?: string;
};

export type DiscussionBranchDefinition = QuestionAnswerBranchFields & {
  readonly id: string;
  readonly parentSceneId: MainSceneId;
  readonly title: string;
  readonly claimClass: ClaimClass;
  readonly evidencePointer: string;
  readonly summary: string;
  readonly detail?: DiscussionBranchDetail;
};
```

- [ ] **Step 4: Add and upgrade Q&A branches**

In the `discussionBranches` array, add the following branch objects. Keep the existing positioning branches in their current order, then add the new branches near their parent scene groups.

Add these new branches:

```ts
  {
    id: "where-is-ai-agent",
    parentSceneId: "thesis",
    title: "Where is the AI agent?",
    claimClass: "implemented",
    evidencePointer: "Abstract; Chapter 1 framing; presentation Scene 1",
    summary: "The implementation is the agent-operable workflow substrate, not a bundled autonomous planner.",
    question: "Where is the AI agent in this thesis?",
    shortAnswer: "The submitted implementation is the lower-level workflow substrate that external agents operate. It exposes typed lifecycle, validation, execution, trace, and inspection surfaces; the autonomous planner layer is intentionally outside the core contribution.",
    expandedAnswer: "The forced product framing uses AI-agent language, but the engineering contribution is not a new planning algorithm. The system gives external LLM operators and human users a reliable workflow lifecycle: drafts, artifacts, deployments, runs, source bindings, diagnostics, traces, and bounded resume. A thin chat or agent graph interface could sit above it, but this thesis evaluates the substrate that makes such an interface useful.",
    speakerHint: "Answer directly first; do not sound defensive. Say substrate, then lifecycle evidence.",
  },
  {
    id: "title-ai-agent-wording",
    parentSceneId: "thesis",
    title: "Title wording boundary",
    claimClass: "implemented",
    evidencePointer: "Abstract; Introduction; Future Work",
    summary: "The title is defended as product direction while the body narrows the implemented contribution.",
    question: "Does the title overclaim by saying AI Agent?",
    shortAnswer: "It is a risky title if read as a claim that the thesis implements a complete autonomous agent brain. The body narrows that claim: this work implements the workflow substrate for agent-operated automation.",
    expandedAnswer: "The safest defense is to distinguish product ambition from the submitted technical artifact. The artifact owns schemas, validation, source projection, lifecycle state, deployment binding, run records, traces, and typed interrupts. A future agent wrapper can use those operations as tools, but that wrapper is not the thesis contribution.",
    speakerHint: "Do not argue that the platform is secretly a full agent. Reframe to agent-operable substrate.",
  },
  {
    id: "not-just-cli",
    parentSceneId: "planner-runtime",
    title: "Not just a CLI",
    claimClass: "implemented",
    evidencePointer: "wf_api surface; JSON-RPC transport; web console",
    summary: "The CLI is one front door over the same workflow API and runtime lifecycle.",
    question: "Is this just a CLI wrapper?",
    shortAnswer: "No. The CLI is only one client. The same operations are exposed through the workflow API and JSON-RPC server, and the web console uses that protocol boundary to inspect lifecycle records and execute the prepared demo.",
    expandedAnswer: "A CLI-only project would stop at command parsing. This system has typed workflow models, source providers, transport-neutral API surfaces, persisted artifacts/deployments/runs, trace inspection, validation diagnostics, and a React console that consumes JSON-RPC. The CLI remains useful because agents and humans can operate it, but it is not the architecture boundary.",
  },
  {
    id: "not-just-scripts",
    parentSceneId: "positioning",
    title: "Why not scripts?",
    claimClass: "motivation",
    evidencePointer: "Chapter 3 positioning; Draft-Artifact-Deployment-Run model",
    summary: "Scripts are simple, but they do not naturally provide lifecycle state, deployment binding, validation, traces, or reusable inspection records.",
    question: "Why not generate Python scripts instead?",
    shortAnswer: "Generated scripts can solve one task, but reusable workspace automation needs lifecycle state, validation, deployment binding, traces, and recovery boundaries that should not be left inside generated code.",
    expandedAnswer: "The thesis does not claim scripts are bad. It claims that as soon as external agents are expected to author reusable automations, the platform should own the durable parts: schema contracts, source inventory, validation, immutable artifacts, deployment bindings, run records, and inspection. Generated scripts can still be one capability source behind that boundary.",
  },
  {
    id: "security-production-boundary",
    parentSceneId: "architecture",
    title: "Security and production boundary",
    claimClass: "implemented",
    evidencePointer: "Limitations; source-provider boundary; loopback console policy",
    summary: "The prototype defines boundaries but does not claim production hardening.",
    question: "Is this secure enough for production?",
    shortAnswer: "No. The thesis is explicit that this is a prototype. It demonstrates source/provider boundaries, local-first transport, and typed validation, but not production-grade authentication, authorization, sandboxing, secret handling, or tenant isolation.",
    expandedAnswer: "The implemented boundary is still useful: sources are projected through a provider-neutral surface, deployments bind requirements explicitly, and runs are inspectable. But production security would require a separate hardening track: credentials, RBAC, audit policy, sandboxed tool execution, untrusted workflow review, network policy, and operational monitoring.",
  },
  {
    id: "demo-reliability",
    parentSceneId: "workflow-demo",
    title: "Live demo reliability",
    claimClass: "implemented",
    evidencePointer: "Prepared lda_report_workflow; replay recording; defense presentation runbook",
    summary: "The demo is designed with live and replay paths so the defense can explain the system even if local services fail.",
    question: "What if the live demo fails?",
    shortAnswer: "The defense has a replay path with the same recorded operation sequence and evidence. If live RPC fails, the point is still demonstrable: the workflow lifecycle, typed interrupt, resume result, trace, and output records are shown from the prepared recording.",
    expandedAnswer: "The replay is not presented as fresh empirical evidence. It is a presentation fallback for an already-tested deterministic example. The live path demonstrates current server behavior when available; the replay path preserves the explanation if Wi-Fi, local ports, or process state fail during the defense.",
  },
  {
    id: "prepared-replay-boundary",
    parentSceneId: "workflow-demo",
    title: "Prepared replay boundary",
    claimClass: "evaluated",
    evidencePointer: "Demo recording fixture; replay provenance branch; runbook fallback wording",
    summary: "Prepared replay is a communication artifact, not a benchmark result.",
    question: "Is the replay cheating?",
    shortAnswer: "It would be cheating if presented as a new live result. Here it is a controlled presentation artifact that shows a previously verified operation path, with provenance separated from the external-agent evaluation.",
    expandedAnswer: "The thesis separates implementation evidence, automated tests, external-agent trials, and presentation replay. Replay exists so the audience can see the lifecycle without relying on a fragile live environment. It should be described as recorded evidence of a deterministic path, not as a live autonomous-agent success.",
  },
  {
    id: "why-schemas",
    parentSceneId: "authoring",
    title: "Why schemas matter",
    claimClass: "implemented",
    evidencePointer: "wf schema command; draft validation diagnostics; typed interrupt contracts",
    summary: "Schemas move correctness checks out of agent guesses and into the platform.",
    question: "Why put so much emphasis on schemas?",
    shortAnswer: "Schemas are how the platform turns agent-authored workflow guesses into checkable contracts. They let the system validate bindings, project capability inputs/outputs, describe interrupts, and explain repair paths before runtime execution.",
    expandedAnswer: "Without schemas, the planner must infer every shape and failure appears late. With schemas, the runtime can detect invalid source paths, undeclared destinations, missing outcomes, incompatible resume payloads, and source drift. That does not make agents perfect, but it gives them a public surface to discover and repair against.",
  },
  {
    id: "production-readiness",
    parentSceneId: "conclusion",
    title: "Production readiness",
    claimClass: "future-work",
    evidencePointer: "Limitations; Future Work; roadmap",
    summary: "The system is submission-ready as a prototype, not production-ready as a hosted automation service.",
    question: "What is missing before this becomes a production product?",
    shortAnswer: "The major missing pieces are security hardening, real credential management, better hosted operations, stronger UI flows, controlled evaluation, scheduler semantics, and a real external-agent interface.",
    expandedAnswer: "The thesis contribution is the substrate: typed lifecycle, validation, source binding, artifacts, deployments, runs, traces, and interrupt contracts. A production product would need authentication, RBAC, secret stores, sandboxing, migration policy, operational dashboards, scaling, billing or tenant boundaries, and a validated planner/chat layer on top.",
  },
```

Upgrade the existing `evaluation-validity` branch by adding these fields to its object:

```ts
    question: "How valid is the 36-trial external-agent evaluation?",
    shortAnswer: "It is useful engineering evidence, but not a controlled model comparison. The thesis treats it as bounded longitudinal evidence about agent-operability and UX failure modes.",
    expandedAnswer: "The cohort has N=3 per cell, two challenges, two hosted models, and three instruction profiles, but it spans product and prompt evolution. Manual audit is authoritative for validity. That supports feasibility and failure analysis, not broad claims about model generalization, token savings, or superiority over other workflow systems.",
    speakerHint: "Emphasize honesty: useful evidence, deliberately bounded claim.",
```

Upgrade the existing `provider-security` branch by adding:

```ts
    question: "Do source providers solve security?",
    shortAnswer: "No. Source providers create a clearer boundary for capability projection and deployment binding, but they are not a complete security model.",
    expandedAnswer: "The provider boundary helps separate source inventory, schemas, and runtime calls from the workflow graph. It gives the platform a place to inspect and validate capabilities. Production security still needs credentials, sandboxing, RBAC, policy enforcement, and operational audit beyond this prototype.",
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts
git commit -m "feat: add defense qna branch metadata"
```

---

### Task 2: Render Q&A Fields In DiscussionPanel

**Files:**
- Modify: `web/apps/console/src/presentation/DiscussionPanel.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Test: `web/apps/console/src/presentation/DiscussionPanel.test.tsx`

**Interfaces:**
- Consumes: optional `question`, `shortAnswer`, `expandedAnswer`, `speakerHint` on `DiscussionBranchDefinition`.
- Produces: accessible discussion modal that still works for old non-Q&A branches.

- [ ] **Step 1: Add failing render tests**

Add this test to `web/apps/console/src/presentation/DiscussionPanel.test.tsx`:

```tsx
  it("renders defense Q&A fields when present", () => {
    render(<DiscussionPanel branchId="where-is-ai-agent" onClose={onClose} />);

    expect(screen.getByText("Where is the AI agent in this thesis?")).toBeDefined();
    expect(screen.getByText(/workflow substrate that external agents operate/i)).toBeDefined();
    expect(screen.getByText(/not a new planning algorithm/i)).toBeDefined();
    expect(screen.getByText(/Answer directly first/i)).toBeDefined();
  });
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: FAIL because the panel does not render Q&A-specific fields yet.

- [ ] **Step 3: Render the Q&A section**

In `DiscussionPanel.tsx`, after the summary paragraph and before `branch.detail`, insert:

```tsx
      {branch.question && (
        <section className="discussion-panel__qna" aria-label="defense question">
          <p className="discussion-panel__question">{branch.question}</p>
          {branch.shortAnswer && (
            <p className="discussion-panel__short-answer">{branch.shortAnswer}</p>
          )}
          {branch.expandedAnswer && (
            <p className="discussion-panel__expanded-answer">{branch.expandedAnswer}</p>
          )}
          {branch.speakerHint && (
            <p className="discussion-panel__speaker-hint">
              <span>Speaker hint</span>
              {branch.speakerHint}
            </p>
          )}
        </section>
      )}
```

Keep the existing `detail` block unchanged so older branches continue to render.

- [ ] **Step 4: Add scoped panel styles**

Add these rules to `web/apps/console/src/presentation/presentation.css` near the existing `.discussion-panel` rules:

```css
.discussion-panel__qna {
  display: grid;
  gap: 0.6rem;
  margin: 0.75rem 0;
  padding: 0.85rem;
  border: 1px solid color-mix(in srgb, var(--presentation-accent, #4f8cff) 35%, transparent);
  border-radius: 1rem;
  background: color-mix(in srgb, var(--presentation-surface, #101624) 82%, transparent);
}

.discussion-panel__question {
  margin: 0;
  font-size: 1.02rem;
  font-weight: 750;
  color: var(--presentation-text, #f7fbff);
}

.discussion-panel__short-answer,
.discussion-panel__expanded-answer {
  margin: 0;
  color: var(--presentation-muted, #aeb8c8);
  line-height: 1.45;
}

.discussion-panel__short-answer {
  color: var(--presentation-text, #f7fbff);
}

.discussion-panel__speaker-hint {
  margin: 0;
  padding-top: 0.5rem;
  border-top: 1px solid color-mix(in srgb, var(--presentation-line, #334155) 70%, transparent);
  color: var(--presentation-muted, #aeb8c8);
  font-size: 0.88rem;
}

.discussion-panel__speaker-hint span {
  display: block;
  margin-bottom: 0.2rem;
  color: var(--presentation-accent, #4f8cff);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
```

If the CSS file uses different variable names for current presentation tokens, adapt these names to the current token names. Do not introduce `:root` tokens for this slice.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DiscussionPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add web/apps/console/src/presentation/DiscussionPanel.tsx web/apps/console/src/presentation/DiscussionPanel.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "feat: render defense qna discussion fields"
```

---

### Task 3: Pin Scene Access And Hash Navigation

**Files:**
- Modify: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Modify: `web/apps/console/src/presentation/storyboard-navigation.test.ts`

**Interfaces:**
- Consumes: branch IDs from Task 1.
- Produces: tests proving Q&A branches are reachable from scene buttons and direct hashes.

- [ ] **Step 1: Add scene button test**

Add this test to `web/apps/console/src/presentation/SceneBody.test.tsx`:

```tsx
  it("opens thesis Q&A branches from the thesis scene", async () => {
    const user = userEvent.setup();
    const location: PresentationLocation = { kind: "main", sceneId: "thesis", beatId: "title", focusPath: [] };
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

    await user.click(screen.getByRole("button", { name: /where is the ai agent/i }));

    expect(openDiscussion).toHaveBeenCalledWith("where-is-ai-agent");
  });
```

- [ ] **Step 2: Add direct hash navigation test**

Add this assertion to the existing `"round-trips main and discussion hashes"` test in `storyboard-navigation.test.ts`:

```ts
    expect(locationFromHash("#discuss/where-is-ai-agent")).toEqual({
      kind: "discussion",
      branchId: "where-is-ai-agent",
    });
```

Also add:

```ts
    expect(hashForLocation({ kind: "discussion", branchId: "where-is-ai-agent" }))
      .toBe("#discuss/where-is-ai-agent");
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/SceneBody.test.tsx src/presentation/storyboard-navigation.test.ts
```

Expected: PASS.

- [ ] **Step 4: Commit Task 3**

```bash
git add web/apps/console/src/presentation/SceneBody.test.tsx web/apps/console/src/presentation/storyboard-navigation.test.ts
git commit -m "test: pin defense qna branch navigation"
```

---

### Task 4: Roadmap And Plan Archival

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-08-defense-qna-branch-projection.md` to `docs/historical/superpowers/plans/2026-07-08-defense-qna-branch-projection.md`

**Interfaces:**
- Consumes: completed code/tests from Tasks 1-3.
- Produces: live roadmap link to the completed historical plan.

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under `Presentation wishlist / defense readiness`, replace:

```md
- Defense Q&A branch set:
  [`defense Q&A runbook`](runbooks/defense-qna.md) collects answers for
  "Where is the AI agent?", evaluation validity, security boundaries, demo
  reliability, and other likely examiner questions. Later work can project the
  strongest entries into `/present` discussion branches.
```

with:

```md
- Defense Q&A branch set:
  [`defense Q&A runbook`](runbooks/defense-qna.md) collects answers for
  "Where is the AI agent?", evaluation validity, security boundaries, demo
  reliability, and other likely examiner questions. Completed projection into
  `/present` discussion branches:
  [`defense Q&A branch projection`](historical/superpowers/plans/2026-07-08-defense-qna-branch-projection.md).
```

- [ ] **Step 2: Move the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-08-defense-qna-branch-projection.md docs/historical/superpowers/plans/2026-07-08-defense-qna-branch-projection.md
```

- [ ] **Step 3: Run docs sanity checks**

Run:

```bash
rg -n "2026-07-08-defense-qna-branch-projection|Defense Q&A branch" docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-08-defense-qna-branch-projection.md
git diff --check
```

Expected:
- `rg` shows the roadmap link and historical plan title.
- `git diff --check` reports no whitespace errors.

- [ ] **Step 4: Commit Task 4**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-08-defense-qna-branch-projection.md
git commit -m "docs: record defense qna branch projection"
```

---

### Task 5: Final Verification

**Files:**
- No new files.
- Verify all files touched by Tasks 1-4.

**Interfaces:**
- Consumes: completed implementation.
- Produces: final confidence that `/present` Q&A branches compile, render, and route correctly.

- [ ] **Step 1: Run focused presentation tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts src/presentation/DiscussionPanel.test.tsx src/presentation/SceneBody.test.tsx src/presentation/storyboard-navigation.test.ts
```

Expected: PASS.

- [ ] **Step 2: Run console typecheck**

Run:

```bash
pnpm --dir web --filter @lda/console typecheck
```

Expected: PASS.

- [ ] **Step 3: Run full web checks**

Run:

```bash
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Expected:
- All tests pass.
- Typecheck is clean.
- Build succeeds. Existing chunk-size warnings are acceptable if unchanged.
- No whitespace errors.

- [ ] **Step 4: Manual browser smoke**

With `pnpm dev` running, open:

```text
http://127.0.0.1:5173/present#discuss/where-is-ai-agent
```

Verify:
- Modal opens directly.
- It shows the question, short answer, expanded answer, evidence pointer, and speaker hint.
- `Escape` closes the modal and returns to the parent scene.

Open:

```text
http://127.0.0.1:5173/present#scene/thesis/title
```

Verify:
- The scene has a visible `Where is the AI agent?` discussion button.
- Clicking it opens the same modal.

- [ ] **Step 5: Final commit if needed**

If Tasks 1-4 already committed everything, do not create an empty commit. If final fixes were required:

```bash
git add web/apps/console/src/presentation docs/current_roadmap.md
git commit -m "fix: polish defense qna branch projection"
```

---

## Self-Review Checklist

- Spec coverage: The plan projects Q&A runbook content into `/present` branches, pins direct hashes, scene buttons, rendering, and docs status.
- Placeholder scan: No `TBD`, `TODO`, or "similar to" placeholders are present.
- Type consistency: `question`, `shortAnswer`, `expandedAnswer`, and `speakerHint` are defined in Task 1 and consumed by Task 2.
- Scope guard: No chat replacement, scene visual pass, schema form surface, or guided beat gate is included.
- Risk: The branch list grows in `storyboard.ts`. This is acceptable for this slice because the presentation catalog is currently the single source of truth. If the file becomes hard to maintain, split branch data in a later refactor.
