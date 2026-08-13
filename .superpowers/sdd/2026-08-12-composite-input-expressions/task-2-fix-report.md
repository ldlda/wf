# Task 2 Review Fix Report

## Status

Fixed the sole Task 2 review finding: direct `InputPathBinding` resolution now
preserves the pre-Task 2 runtime behavior, while composite `PathExpression`
leaves retain strict `JsonValue` validation.

## Change

`resolve_step_input_bindings()` now forwards values from direct path bindings
unchanged into `set_local_value`. This preserves both identity and legacy
acceptance of opaque runtime values. `resolve_input_expression()` continues to
call `validate_strict_json_value()` for composite path leaves, as required by
the composite expression contract.

No Task 4 authoring adapter files were modified.

## TDD Evidence

- RED: the new legacy identity test failed because the direct path branch
  rejected an opaque nested object through strict JSON validation.
- GREEN: removing validation from only the direct path branch made the legacy
  test pass while the composite path strictness regression remained passing.

## Verification

- Shared resolver tests: `9 passed`.
- Task 2 focused/core selection: `37 passed`.
- Full core suite: `287 passed`.
- Ruff check: clean for all changed files.
- Ruff format check: clean.
- Scoped basedpyright: `0 errors, 0 warnings, 0 notes` for
  `src/wf_core/runtime` and `src/wf_core/validation`.
- `git diff --check`: clean apart from normal Windows line-ending warnings.

## Concerns

- The Task 4 Python authoring adapter widening remains intentionally separate
  and was not touched by this fix.
