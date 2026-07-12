# Task 2 Implementation Report

## Summary

Task 2 separates target health from replay playback. A healthy configured target
now remains `Live target ready` while the demo timeline is replaying, while the
reviewed-recording fallback remains available when no target is configured or
health probing is disabled. Health probing is enabled only for main routes whose
scene is included by Task 1's `isDemoChromeScene`, including Scene 8.

## Changed Files

- `web/apps/console/src/presentation/presentation-target-status.ts`
  - Removed the `replayActive` argument and replay-specific healthy-target
    branch.
  - Preserved the public `PresentationTargetHealth` and `TargetProbeState`
    types and existing target/probe/liveActive/failureReason inputs.
- `web/apps/console/src/presentation/presentation-target-status.test.ts`
  - Updated healthy replay expectations to `ready` / `Live target ready`.
  - Added explicit no-target reviewed-recording fallback coverage.
- `web/apps/console/src/presentation/usePresentationTargetStatus.ts`
  - Removed replay coupling from health calculation.
  - Kept disabled probing generic and ensured it does not call
    `workflow.health`.
- `web/apps/console/src/presentation/usePresentationTargetStatus.test.tsx`
  - Updated direct replay readiness expectations.
  - Added disabled-probing coverage.
- `web/apps/console/src/presentation/PresentationRoute.tsx`
  - Replaced the Scene 8 exception with `isDemoChromeScene`-based probing for
    main routes.
- `web/apps/console/src/presentation/PresentationRoute.test.tsx`
  - Covered healthy direct replay status, Scene 8 probing with a local
    composer, title-route non-probing, and existing live controls under the
    updated route behavior.

## Verification

- TDD red run: the updated tests failed against the old replay branch, disabled
  Scene 8 probe, and title-route probe behavior as expected.
- Focused tests:
  - `pnpm --dir web --filter @lda/console test -- src/presentation/presentation-target-status.test.ts src/presentation/usePresentationTargetStatus.test.tsx src/presentation/PresentationRoute.test.tsx`
  - Result: 3 test files passed, 60 tests passed.
- Typecheck:
  - `pnpm --dir web typecheck`
  - Result: all workspace typecheck projects passed.
- `git diff --check` passed.

## Deviations

The focused route tests that asserted live controls on the default title route
were moved to a demo scene hash, because non-demo routes must no longer probe or
show target health actions. The live action assertions now account for both the
operator-chat and demo-stage controls that are present on a healthy demo route.

No footer rendering or file-browser changes were made.

## Concerns

The existing `OperatorChat.tsx` still has its own `isScene8` action-visibility
condition. It was intentionally left unchanged because it is not target health
or route probing logic, and changing it would exceed this task's scope.

## Review Fix: Hide Target Status Outside Demo Arc

- `PresentationFooter` now derives demo-arc membership from `isDemoChromeScene`
  and omits the target status badge for title and other non-demo routes.
- Added footer-level coverage for a non-demo `conclusion` scene and route-level
  coverage for `#scene/conclusion/questions` with a configured target.
- No `PresentationStage`, `PresentationDemoRail`, file-browser, or unrelated
  chat rendering changes were needed.

## Review Fix Verification

- TDD red run: both new regressions failed against the unconditional footer badge.
- Covering tests:
  - `pnpm --dir web --filter @lda/console test -- src/presentation/PresentationFooter.test.tsx src/presentation/PresentationRoute.test.tsx src/presentation/presentation-target-status.test.ts src/presentation/usePresentationTargetStatus.test.tsx`
  - Result: 4 test files passed, 63 tests passed.
- Typecheck:
  - `pnpm --dir web typecheck`
  - Result: all workspace typecheck projects passed.
- `git diff --check` passed.

## Review Fix Concerns

None beyond the pre-existing `OperatorChat.tsx` Scene 8 condition documented
above; Task 3 and unrelated presentation surfaces were not touched.
