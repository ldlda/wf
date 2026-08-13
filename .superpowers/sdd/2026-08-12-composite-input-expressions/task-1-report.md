# Task 1 Report: Canonical Input Expressions And Persistence

## Status

Implemented and verified. The task adds a recursive, discriminated input-expression model and widens only node-local persisted input/request fields. Workflow-level output remains on the existing simple path/value union.

## Changed Content

- Added `src/wf_core/models/json_values.py` with the shared recursive `JsonValue` type and strict JSON validator.
- Added `src/wf_core/models/input_bindings.py` with path/value bindings, literal/path/array/object expressions, `InputExpressionBinding`, `StepInputBinding`, and bounded raw-tree validation.
- Updated `src/wf_core/models/steps.py` to preserve legacy binding imports while using `StepInputBinding` for `NodeUse.input`, `SubgraphNode.input`, and `InterruptNode.request`.
- Updated `src/wf_artifacts/drafts/models.py` to use `StepInputBinding` for draft use, subgraph, and interrupt input fields.
- Exported the new public models and JSON helpers from `wf_core.models` and `wf_core`.
- Added a narrow typed cast in `src/wf_artifacts/drafts/adapter.py` because the existing Python authoring builder remains simple-binding-only until the later API carry-through task. This preserves Task 1 persistence without pretending runtime authoring support is already complete.
- Added model and persistence coverage in `tests/core/test_input_expressions.py`, `tests/core/test_canonical_node_bindings.py`, and `tests/artifacts/test_draft_models.py`.

## Behavior Covered

- The exact composite object/array/path/literal binding round-trips through `NodeUse`, `SubgraphNode`, `InterruptNode`, `DraftUseStep`, `DraftSubgraphPayload`, and `DraftInterruptPayload`.
- Workflow final-output parsing rejects composite expressions and keeps the existing simple union.
- Existing path/value bindings dump unchanged.
- Extra fields are rejected at binding and expression nodes.
- Literal expressions accept only strict finite JSON values; tuples, sets, NaN, and infinity are rejected.
- Expression depth is bounded at 64 levels.
- Total expression/container nodes are bounded at 1,024.
- Malformed raw expression structures are left for normal Pydantic validation rather than recursively trusted by the limit walker.

## TDD And Verification

The new model suite was first run before production implementation and failed during collection because `InputExpressionBinding` did not exist. After implementation, the focused suite passed.

Commands run:

```powershell
uv run pytest tests/core/test_input_expressions.py tests/core/test_canonical_node_bindings.py tests/artifacts/test_draft_models.py -q
uv run basedpyright --level error src/wf_core/models src/wf_artifacts/drafts
uv run ruff check src/wf_core/models src/wf_artifacts/drafts tests/core/test_input_expressions.py tests/core/test_canonical_node_bindings.py tests/artifacts/test_draft_models.py
uv run ruff format --check src/wf_core/models src/wf_artifacts/drafts tests/core/test_input_expressions.py tests/core/test_canonical_node_bindings.py tests/artifacts/test_draft_models.py
git diff --check
```

Results:

- `67 passed`
- `basedpyright`: `0 errors, 0 warnings, 0 notes`
- Ruff check: all checks passed
- Ruff format: all files already formatted
- Git diff check: clean apart from normal Windows line-ending warnings

## Concerns And Follow-Up

- Composite expressions are persisted and decoded by the core/draft models, but the Python authoring builder and runtime resolution paths still require the later planned carry-through task.
- The adapter cast is deliberately isolated at that boundary and documented so future API work can replace it with a widened authoring input type rather than spreading casts.
- No transport, CLI, TypeScript, or console changes are included in this task.
