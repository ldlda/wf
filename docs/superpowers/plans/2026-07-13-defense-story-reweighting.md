# Defense story reweighting implementation plan

> **For agentic workers:** Use subagent-driven development or execute this plan task by task. Follow TDD and request an independent review before completion.

**Goal:** Reweight the 14-scene defense around the thesis contribution, reduce the must-say speech to 750-850 words, and create one structured source for future presenter notes.

**Architecture:** Keep `storyboard.ts` as the audience route and visual catalog. Add a separate typed presenter-note catalog keyed by scene and beat. The catalog owns speech, timing, evidence, warnings, fallback wording, and Q&A links. Audience components must not render presenter-only content.

**Tech stack:** React 19, TypeScript, Vitest, existing presentation state and storyboard models.

## Constraints

- Preserve 14 scenes and current route order.
- Do not add another demo scene.
- Treat Scene 5 as vocabulary and Scene 9 as evidence.
- Describe the later issue-review workflow as an implementation extension, not the thesis's three-node report case study.
- Do not claim production approval, scheduling, broad model performance, arbitrary crash recovery, or live Scene 10-12 rehearsal.
- Submitted replay may use same-run wording. Revision replay must be labeled as a separate prepared recording.
- Keep the main speech between 750 and 850 words, excluding optional notes and Q&A.

## Task 1: Define the presenter-note contract

**Files:**
- Create: `web/apps/console/src/presentation/presenter/presenter-notes.ts`
- Create: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`
- Read: `docs/runbooks/defense-speech-and-claim-audit.md`

- [ ] Define `PresenterBeatNote` with `sceneId`, `beatId`, `targetSeconds`, `mustSay`, `optionalDetail`, `warning`, `fallback`, `evidencePointers`, and `qnaBranchIds`.
- [ ] Use explicit nullable fields rather than empty placeholder strings.
- [ ] Add helpers for route lookup, scene totals, complete-deck totals, and main-speech word count.
- [ ] Test that every storyboard beat has exactly one note, no stale note exists, total target time is at most 780 seconds, and must-say text is 750-850 words.
- [ ] Test that every evidence pointer is non-empty and every Q&A ID resolves through `discussionBranchForId`.

Troubleshooting: derive route completeness from `mainScenes`; do not maintain a second route array.

## Task 2: Reweight the speech and scene transitions

**Files:**
- Modify: `web/apps/console/src/presentation/presenter/presenter-notes.ts`
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `docs/runbooks/defense-speech-and-claim-audit.md`
- Modify: `docs/runbooks/presentation-rehearsal-matrix.md`
- Test: `web/apps/console/src/presentation/storyboard.test.ts`
- Test: `web/apps/console/src/presentation/presenter/presenter-notes.test.ts`

- [ ] Allocate the target time as: Scenes 1-2 90s, Scene 3 45s, Scenes 4-7 195s, Scenes 8-12 180s, Scene 13 120s, Scene 14 75s, and 75s navigation buffer.
- [ ] Keep one must-say paragraph per scene. Beat notes after the first should contain only the sentence needed for the visual change.
- [ ] Compress Scene 5 to definitions; move the applied lifecycle explanation to Scene 9.
- [ ] Give Scene 13 two minutes and include 27 pass, 8 invalid, 1 fail, author audit, changing snapshots, and non-benchmark wording.
- [ ] Name the five thesis contributions across Scenes 1, 4, 5, 7, and 13 without reading a five-item list.
- [ ] Keep stateful MCP session reuse and the operation/repair/instruction-layer distinction as optional notes or Q&A, not main-path additions.
- [ ] Update the Markdown speech so its must-say version matches the typed catalog.

## Task 3: Correct known factual presentation defects

**Files:**
- Modify: `web/apps/console/src/presentation/authoring/authoring-recording.ts`
- Modify: affected authoring tests
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.tsx`
- Modify: affected guided-moment tests
- Modify: `docs/runbooks/defense-presentation.md`
- Modify: `docs/runbooks/defense-qna.md`

- [ ] Replace stale `workflow.draft_workspaces.*` labels with the actual `workflow.drafts.*` namespace, or label composite CLI actions without pretending they map to one JSON-RPC method.
- [ ] Preserve the factual configured source ID `local.lda_docs`.
- [ ] Remove unconditional same-run wording from any revision-requested presentation state.
- [ ] State that the decision is a typed interrupt/resume contract, not a production approval gate.
- [ ] Update replay fallback answers so they distinguish recorded product evidence from rehearsed live evidence.
- [ ] Replace stale future-work answers that list already-built presentation UI as the next product priority.

## Task 4: Verify and document

- [ ] Run focused storyboard, presenter-note, authoring, guided-moment, and Q&A tests.
- [ ] Run `pnpm --dir web typecheck` and `pnpm --dir web build`.
- [ ] Run `uv run pytest tests/docs -q`.
- [ ] Review the 14-scene route matrix against the final note catalog.
- [ ] Update `docs/current_roadmap.md`, archive this plan, and commit the slice.

**Completion gate:** A presenter can read only `mustSay` fields and deliver the argument in under 13 minutes without unsupported claims.
