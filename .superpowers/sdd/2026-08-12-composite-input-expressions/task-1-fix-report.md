# Task 1 Review Fix Report

## Status

Fixed P1 findings #1 and #2 from `task-1-review.md`. P2 #3 was intentionally left for the planned Python API/runtime tasks.

## Fixes

### P1 #1: Prebuilt expression limits

`InputExpressionBinding.check_limits()` now converts an already-constructed Pydantic expression model with `model_dump(mode="python")` before invoking the raw-tree limit walker. This keeps the same bounded validation path for both JSON mappings and prebuilt `ArrayExpression`/`LiteralExpression` instances.

Added regressions for:

- a prebuilt array containing 1,024 literal expressions;
- a prebuilt literal containing 64 nested JSON containers.

Both now fail with the configured node/depth validation errors instead of bypassing the limits.

### P1 #2: Strict JSON mapping boundary

`validate_strict_json_value()` now accepts native `dict` containers, matching the original strict contract, rather than every `collections.abc.Mapping`. A `UserDict` is rejected instead of being silently converted into a JSON-shaped dictionary.

Added a regression covering `UserDict` through the literal-expression boundary.

### P2 #3: Deferred builder/runtime carry-through

No change. Task 1 is persistence-only. The existing adapter cast remains documented as a temporary boundary because Task 4 widens builder signatures and Task 2 adds runtime resolution. No Task 1 persistence test is broken by leaving that work deferred.

## TDD And Verification

The new review regressions were run before the production fixes and failed as expected: `3 failed, 14 passed`. After the fixes, the focused expression suite passed with `17 passed`.

Final commands:

```powershell
uv run pytest tests/core/test_input_expressions.py tests/core/test_canonical_node_bindings.py tests/artifacts/test_draft_models.py -q
uv run basedpyright --level error src/wf_core/models src/wf_artifacts/drafts
uv run ruff check src/wf_core/models src/wf_artifacts/drafts tests/core/test_input_expressions.py tests/core/test_canonical_node_bindings.py tests/artifacts/test_draft_models.py
uv run ruff format --check src/wf_core/models src/wf_artifacts/drafts tests/core/test_input_expressions.py tests/core/test_canonical_node_bindings.py tests/artifacts/test_draft_models.py
git diff --check
```

Results before the fix commit:

- `70 passed`
- `basedpyright`: `0 errors, 0 warnings, 0 notes`
- Ruff check: all checks passed
- Ruff format: all files already formatted
- Git diff check: clean apart from normal Windows line-ending warnings

## Changed Files

- `src/wf_core/models/input_bindings.py`
- `src/wf_core/models/json_values.py`
- `tests/core/test_input_expressions.py`
- This report file
