# Defense Rehearsal Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current 14-scene presentation into a repeatable rehearsal artifact by checking every scene at 16:9 and 4:3, validating the live/replay demo path, and recording story-flow findings without mixing in new product features.

**Architecture:** Keep `/present` as the source of truth for scene and beat definitions. Add a small route matrix and screenshot runner that derive their coverage from the storyboard rather than maintaining a second presentation model. Use browser smoke checks for geometry and interaction, then write a human-readable story audit that separates visual defects, factual gaps, and product holes.

**Tech Stack:** React 19, TypeScript, Vitest, existing `pnpx playwright screenshot` tooling, PowerShell, Markdown runbooks, and the existing `mainScenes`/`hashForLocation` presentation contracts.

## Global Constraints

- Do not add new product functionality during rehearsal; log product holes as follow-up work.
- Do not alter thesis claims, workflow facts, run records, trace records, or live/replay semantics.
- Preserve the user’s current uncommitted Scene 9 bottom-alignment fix and `26rem` Scene 2 height unless a screenshot proves either causes a concrete regression.
- Test both `1280x720` and `1024x768` at browser zoom 100%.
- Treat screenshots as human-reviewed evidence; do not use pixel snapshots as the correctness oracle.
- Keep the existing runbook fallback: the defense must remain explainable when the RPC server or live target is unavailable.
- Do not mark a route healthy merely because it returns HTTP 200; verify visible scene content, controls, and layout metrics.

---

### Task 1: Define The Rehearsal Route Matrix

**Files:**
- Create: `docs/runbooks/presentation-rehearsal-matrix.md`
- Create: `scripts/presentation-rehearsal-routes.json`
- Modify: `docs/runbooks/defense-presentation.md`
- Test: `web/apps/console/src/presentation/storyboard-navigation.test.ts`

**Interfaces:**
- Consumes: `mainScenes` and `hashForLocation` from `web/apps/console/src/presentation/storyboard-navigation.ts`.
- Produces: one documented matrix and one machine-readable route manifest covering all 14 scenes, every beat, the canonical hash, visual primary, expected chat mode, and the evidence/fallback note.

- [ ] **Step 1: Enumerate the canonical route matrix from the storyboard.**

  Use the current scene definitions, not stale historical names. The matrix must include these scene IDs and their current beat IDs:

  ```text
  thesis: title, substrate
  problem: direct-actions, missing-contracts
  positioning: landscape, lda-position
  planner-runtime: planner, runtime, boundary
  lifecycle: draft, artifact, deployment, run
  architecture: client, api, runtime, node-use
  authoring: discover, author, diagnose, repair
  agent-handoff: request
  prepared-lifecycle: discover, draft, validate, artifact, deployment
  run-from-deployment: input, operation, graph
  typed-human-boundary: interrupt, approval
  resume-output-evidence: resume, output, trace
  evaluation: cohort, validity, findings
  conclusion: limits, future, conclusion, questions
  ```

  Store the captureable route portion in `scripts/presentation-rehearsal-routes.json` as an array of objects with exactly these fields:

  ```json
  {
    "sceneId": "problem",
    "beatId": "direct-actions",
    "route": "problem/direct-actions",
    "fileStem": "02-problem-direct-actions"
  }
  ```

  The JSON is an execution manifest, not a replacement for `mainScenes`. The coverage test in the next step must fail when it is missing a storyboard scene/beat or contains a route that no longer exists.

- [ ] **Step 2: Add a route coverage assertion.**

  In `storyboard-navigation.test.ts`, import the JSON manifest and assert that every `mainScenes` scene/beat pair has exactly one manifest entry, that every manifest entry exists in `mainScenes`, and that each route round-trips through `hashForLocation` and `locationFromHash`. Keep the assertions field-level and make a missing beat fail with its scene ID.

- [ ] **Step 3: Write the rehearsal matrix.**

  For every route, record:

  - what the presenter should say in one sentence;
  - the dominant visual and the supporting visual;
  - whether chat is hidden, full, rail, or dock;
  - whether the beat is replay-only, live-capable, or requires an explicit run;
  - the exact fallback route if live evidence is unavailable.

  Do not invent expected output. Point to the existing evidence pointer or runbook section.

- [ ] **Step 4: Link the matrix from the defense runbook.**

  Add the matrix beside `Useful Deep Links`, and explicitly state that it is the route checklist for rehearsal, not a new story or product contract.

- [ ] **Step 5: Run the focused navigation tests and commit.**

  ```powershell
  pnpm --dir web/apps/console test -- src/presentation/storyboard-navigation.test.ts
  git add docs/runbooks/presentation-rehearsal-matrix.md scripts/presentation-rehearsal-routes.json docs/runbooks/defense-presentation.md web/apps/console/src/presentation/storyboard-navigation.test.ts
  git commit -m "docs: define presentation rehearsal route matrix"
  ```

---

### Task 2: Add A Repeatable Screenshot Runner

**Files:**
- Create: `scripts/presentation-rehearsal.ps1`
- Modify: `.gitignore`
- Modify: `docs/runbooks/presentation-visual-review.md`

**Interfaces:**
- Consumes: a running `pnpm --dir web dev` server at `http://127.0.0.1:5173` and `scripts/presentation-rehearsal-routes.json` from Task 1.
- Produces: ignored screenshots under `web/apps/console/.visual-smoke/rehearsal/<viewport>/` with stable route-based names.

- [ ] **Step 1: Define the capture inputs.**

  The script must accept an optional base URL and output root, defaulting to:

  ```powershell
  $BaseUrl = "http://127.0.0.1:5173"
  $OutputRoot = "web/apps/console/.visual-smoke/rehearsal"
  $Viewports = @("1280,720", "1024,768")
  ```

  Load every route object from `scripts/presentation-rehearsal-routes.json`. Do not hand-maintain a partial “interesting routes” list in the PowerShell script.

- [ ] **Step 2: Capture each route at both viewports.**

  Each capture must use the settled route and wait at least 800 ms before capture:

  ```powershell
  pnpx --yes playwright screenshot `
    --viewport-size $Viewport `
    --wait-for-timeout 800 `
    "$BaseUrl/present#scene/$Route" `
    "$OutputRoot/$Viewport/$FileName.png"
  ```

  Sanitize route names into stable filenames. Preserve the original hash in the matrix so a reviewer can navigate back to the exact state.

- [ ] **Step 3: Add ignored-output rules and failure guidance.**

  Ignore only the generated rehearsal directory. If the dev server is unavailable, fail with the exact startup command instead of silently producing empty captures.

- [ ] **Step 4: Document the capture command and review order.**

  Update `presentation-visual-review.md` with:

  ```powershell
  pwsh -File scripts/presentation-rehearsal.ps1
  ```

  Review in story order, then inspect any route that shows clipping, stale chrome, unreadable copy, or a changed primary visual.

- [ ] **Step 5: Run the runner and commit.**

  ```powershell
  pwsh -File scripts/presentation-rehearsal.ps1
  git diff --check
  git add scripts/presentation-rehearsal.ps1 .gitignore docs/runbooks/presentation-visual-review.md
  git commit -m "test: add repeatable presentation screenshot rehearsal"
  ```

---

### Task 3: Add Route-Level Geometry And Chrome Smoke Checks

**Files:**
- Create: `web/apps/console/src/presentation/presentation-rehearsal.test.ts`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Consumes: the route matrix and existing presentation test helpers.
- Produces: deterministic jsdom coverage for scene identity, expected heading, chat mode, and demo-chrome ownership. Browser-only dimensions remain in the screenshot review.

- [ ] **Step 1: Add a pure route matrix test.**

  Import `mainScenes` and assert each scene has the expected count of beats and canonical beat IDs. The test must fail with the scene ID and missing beat when the storyboard changes without a rehearsal update.

- [ ] **Step 2: Add direct-hash route assertions.**

  Extend `PresentationRoute.test.tsx` with a table covering at least:

  ```text
  thesis/title
  architecture/client
  authoring/diagnose
  prepared-lifecycle/discover
  run-from-deployment/graph
  typed-human-boundary/approval
  resume-output-evidence/trace
  evaluation/cohort
  conclusion/questions
  ```

  Assert the visible scene heading and that demo footer controls appear only for Scenes 8–12. Do not assert implementation CSS classes as a proxy for visible behavior.

- [ ] **Step 3: Add a no-accidental-chrome contract.**

  Assert that title, problem, architecture, evaluation, and conclusion routes do not render the live target badge, run/retry controls, or prepared-run action. Assert that the prepared lifecycle route keeps its assistant pane and footer ownership without duplicating a run action.

- [ ] **Step 4: Run focused route tests and commit.**

  ```powershell
  pnpm --dir web/apps/console test -- src/presentation/presentation-rehearsal.test.ts src/presentation/PresentationRoute.test.tsx
  git add web/apps/console/src/presentation/presentation-rehearsal.test.ts web/apps/console/src/presentation/PresentationRoute.test.tsx
  git commit -m "test: cover presentation route rehearsal contracts"
  ```

---

### Task 4: Rehearse The Live And Replay Demo Paths

**Files:**
- Modify: `docs/runbooks/defense-presentation.md`
- Create: `docs/runbooks/presentation-rehearsal-log.md`

**Interfaces:**
- Consumes: the existing Python RPC server, `/present` live/replay target selection, Scene 10 start action, Scene 11 approval form, and Scene 12 output/trace views.
- Produces: a dated rehearsal log with submitted and revision-requested outcomes, fallback behavior, and any concrete defects.

- [ ] **Step 1: Rehearse replay first.**

  Force replay using the documented session-storage command, then verify:

  1. Scene 8 request/send reveals the prepared conversation without claiming a run.
  2. Scene 9 staged messages progress through Discover, Draft, Validate, Artifact, and Deployment.
  3. Scene 10 exposes the run action and reaches the typed boundary.
  4. Scene 11 approval accepts a submitted outcome and a revision-requested outcome.
  5. Scene 12 preserves the same run identity and shows output plus trace evidence.

- [ ] **Step 2: Rehearse the live path.**

  With the example server running:

  ```powershell
  uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
  ```

  Confirm the live badge, start action, health probe, approval payload, resume action, output, and trace. Record the exact point where live behavior diverges from replay, if it does.

- [ ] **Step 3: Rehearse failure fallback.**

  Stop or point the target at an unavailable endpoint. Confirm the UI says replay/fallback rather than claiming a live run, and verify the direct approval/output/trace hashes still render.

- [ ] **Step 4: Record concrete results.**

  `presentation-rehearsal-log.md` must contain the date, viewport, target mode, route, operator action, observed result, and classification:

  ```text
  PASS       expected behavior confirmed
  VISUAL     layout/contrast/overflow defect
  FACTUAL    UI claim does not match evidence
  PRODUCT    missing capability outside this slice
  BLOCKED    environment or server prevented the check
  ```

  Product holes belong in the `PRODUCT` category and must not be “fixed” inside this rehearsal slice.

- [ ] **Step 5: Commit the rehearsal log and runbook changes.**

  ```powershell
  git add docs/runbooks/defense-presentation.md docs/runbooks/presentation-rehearsal-log.md
  git commit -m "docs: record live and replay presentation rehearsal"
  ```

---

### Task 5: Perform The Story-Flow Audit

**Files:**
- Create: `docs/runbooks/presentation-story-audit.md`
- Modify: `docs/current_roadmap.md`

**Interfaces:**
- Consumes: the screenshot matrix, rehearsal log, `docs/runbooks/defense-presentation.md`, `docs/runbooks/defense-qna.md`, and the existing `random shit/presentation-story-lda.md` as private narrative input when available locally.
- Produces: a short ordered audit of what each scene proves, what it assumes, what is missing, and what should change next.

- [ ] **Step 1: Audit every scene in order.**

  For each scene, record exactly four lines:

  ```markdown
  ### Scene N — <title>
  - Audience takeaway:
  - Visible proof:
  - Missing or confusing:
  - Next action: keep | visual fix | factual fix | product follow-up
  ```

- [ ] **Step 2: Check transitions, not only isolated screenshots.**

  Review these transitions explicitly:

  - Scene 1 → 2: goal becomes problem.
  - Scene 5 → 6: lifecycle vocabulary becomes architecture.
  - Scene 7 → 8: authoring surface becomes external-agent request.
  - Scene 8 → 9: request becomes staged authoring lifecycle.
  - Scene 9 → 10: deployment becomes execution, without implying Scene 9 ran anything.
  - Scene 10 → 11 → 12: one run reaches a typed human boundary and remains inspectable.
  - Scene 13 → 14: evaluation limits become contribution and future work.

- [ ] **Step 3: Keep product holes separate.**

  Add a final `Product follow-ups` section for missing file browsing, live agent execution, richer trace frames, real source reads, or other holes found during rehearsal. Do not mix these with visual acceptance criteria.

- [ ] **Step 4: Update the roadmap with findings and commit.**

  Link the audit and rehearsal log under the rehearsal gate. If the audit finds a concrete visual defect, create a new narrowly scoped visual plan rather than editing this plan retroactively.

  ```powershell
  git add docs/current_roadmap.md docs/runbooks/presentation-story-audit.md
  git commit -m "docs: audit presentation story flow"
  ```

---

### Task 6: Final Verification And Plan Archival

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-13-defense-rehearsal-gate.md` to `docs/historical/superpowers/plans/2026-07-13-defense-rehearsal-gate.md`

- [ ] **Step 1: Run the focused presentation checks.**

  ```powershell
  pnpm --dir web/apps/console test -- src/presentation/presentation-rehearsal.test.ts src/presentation/PresentationRoute.test.tsx
  ```

- [ ] **Step 2: Run the complete web gate.**

  ```powershell
  pnpm --dir web test
  pnpm --dir web typecheck
  pnpm --dir web build
  git diff --check
  ```

  The known Vite chunk-size warning is acceptable if no new build failure appears.

- [ ] **Step 3: Confirm the screenshot matrix.**

  Verify every matrix route has both viewport captures, no outer page scroll, no clipped headings, no unreadable labels, no accidental demo chrome, and no live claim in replay mode.

- [ ] **Step 4: Request the two-axis review.**

  Review the complete range against this plan. Fix Critical and Important findings before archival; record Minor findings in the rehearsal log.

- [ ] **Step 5: Archive and mark complete.**

  Update the roadmap to link the historical plan, rehearsal matrix, rehearsal log, and story audit. Move the plan only after the review and verification gates pass.
