# Final Fix Report

## Scope

- Reattached persisted, inspectable evidence beneath the typed substrate at wide desktop and retained the 1080px and 640px layout contracts.
- Restored the exact seven defense-topic labels from the closing design.
- Restored the `DefenseDiscussionIndex` component boundary: canonical branches and `openDiscussion` are props; a pure, exhaustively typed projection groups the supplied catalog without copying branch objects.

## TDD Record

- RED: `pnpm --dir web\\apps\\console test -- src/presentation/conclusion/conclusion-model.test.ts src/presentation/conclusion/ConclusionScene.test.tsx src/presentation/discussion/defense-discussion-index.test.ts src/presentation/discussion/DefenseDiscussionIndex.test.tsx src/presentation/presentation-css.test.ts`
  - Result: failed as expected, with 7 failures across the missing evidence model/layout contract and missing projection/component API.
- GREEN: `pnpm --dir web\\apps\\console test -- src/presentation/conclusion/conclusion-model.test.ts src/presentation/conclusion/ConclusionScene.test.tsx src/presentation/discussion/defense-discussion-index.test.ts src/presentation/discussion/DefenseDiscussionIndex.test.tsx src/presentation/SceneBody.test.tsx src/presentation/presentation-css.test.ts; pnpm --dir web\\apps\\console typecheck`
  - Result: 6 test files passed, 43 tests passed; console typecheck passed.

## Changed Files

- `web/apps/console/src/presentation/conclusion/ConclusionScene.tsx`
- `web/apps/console/src/presentation/conclusion/conclusion-model.ts`
- `web/apps/console/src/presentation/presentation.css`
- `web/apps/console/src/presentation/discussion/DefenseDiscussionIndex.tsx`
- `web/apps/console/src/presentation/discussion/defense-discussion-index.ts`
- `web/apps/console/src/presentation/SceneBody.tsx`
- Focused conclusion, discussion, SceneBody, and presentation CSS tests.

## Deviations And Concerns

- Deviations: none.
- Concerns: no manual browser screenshot pass was run in this fix wave; the requested responsive behavior is covered by CSS contract tests at 1080px and 640px.
