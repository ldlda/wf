# Task 3 Report

## Scope

Removed cancel-specific presentation layout plumbing from `DemoWorkflowScene`.
The approval beat remains the sole approval layout mapping, and the existing
Scene 11 composition test continues to assert `data-demo-layout="approval"`.

The approval composition regression coverage now asserts that both `Submit`
and `Request revision` controls are enabled and that the factual outcomes are
visible as `submitted / cancelled`.

## TDD Evidence

### RED

Command:

```text
pnpm --dir web --filter @lda/console test -- src/presentation/DemoWorkflowScene.test.tsx src/presentation/GuidedProductMoment.test.tsx
```

Result: failed with 2 tests failing because the new slash-delimited outcome
assertion was absent; the existing UI rendered `submitted, cancelled`.

### GREEN

Changed the decision-form outcome presentation from comma-delimited to
slash-delimited factual contract output, then simplified `DemoWorkflowScene`
to map only `approval` to the approval layout.

The same focused command passed with 2 test files and 31 tests passing.

## Verification

- Focused Scene 11 test command passed: 2 files, 31 tests.
- No `cancel` render branch remains in `DemoWorkflowScene.tsx`.
- The unrelated working-tree change in `authoring/Scene8ChatEntry.tsx` was not modified or staged.

## Deviations

- `InterruptDecisionForm.tsx` was changed although it was not in the primary Task 3 file list. The focused regression test demonstrated that the required factual `submitted / cancelled` output was otherwise impossible in the Scene 11 renderer; no behavior or outcome projection was changed.
- `DemoWorkflowScene.test.tsx` required no net diff because its existing approval composition test already asserts the approval root layout and both controls.

## Concerns

- The canonical interrupt payload still uses the underlying `cancelled` outcome; only its display separator changed. The operator action remains `Request revision` as required by the Task 2 contract.
- The pre-existing unrelated `Scene8ChatEntry.tsx` modification remains unstaged.
