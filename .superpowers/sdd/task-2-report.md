# Task 2 Report: Remove The Stale Replay Requirement And Verify Navigation

## Changed Files

- `web/apps/console/src/presentation/demo-beat-requirements.ts`
  - Removed the obsolete `typed-human-boundary/cancel` requirement.
  - Preserved `interrupt` and `approval` requirements with `requiredStage: "interrupt"`.
- `web/apps/console/src/presentation/demo-beat-requirements.test.ts`
  - Updated the Scene 11 table to cover only `interrupt` and `approval`.
  - Added an assertion that the removed `cancel` beat has no replay requirement.
- `web/apps/console/src/presentation/storyboard-navigation.test.ts`
  - Added direct `interrupt` to `approval`, then Scene 12 navigation coverage.
  - Added fallback coverage for the removed Scene 11 cancel hash.

The unrelated existing modification to `web/apps/console/src/presentation/authoring/Scene8ChatEntry.tsx` was not changed or staged. Task 1 commit `3efb5167` was preserved.

## TDD Evidence

Red:

```text
Test Files  1 failed | 1 passed (2)
Tests       1 failed | 23 passed (24)
The cancel assertion received requiredStage: "interrupt" instead of null.
```

Green:

```text
Test Files  2 passed (2)
Tests       24 passed (24)
```

## Verification

- Focused command passed:
  `pnpm --dir web --filter @lda/console test -- src/presentation/demo-beat-requirements.test.ts src/presentation/storyboard-navigation.test.ts`
- `git diff --check` passed; Git emitted only normal LF-to-CRLF working-copy warnings.
- The commit stages only the requested Task 2 files and this report; the pre-existing Scene 8 edit remains unstaged.

## Concerns

- No known functional concerns for Task 2. Broader console typecheck/build and the full repository test suite were not run because the brief requested focused tests.
