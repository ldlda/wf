# Task 2 Report: Analyze Node-Scoped Runtime Context

## Status

Implemented Task 2 of the workflow contract graph backend slice.

## Changes

- Added `wf_core.context_contracts` with the exact standard runtime context
  field schemas and shared key constants.
- Added `foreach_context_fields`, including `loop_item`, `loop_index`, and a
  configured alias with duplicate loop-key aliases removed.
- Updated `frame_context_values` to use the shared context key registry while
  preserving its existing runtime values.
- Added `context_fields_by_node`, an abstract traversal that memoizes
  `(node_id, active_foreach_id)` and distinguishes available from conditional
  fields across reachable frame scopes.
- Added bounded graph warnings for missing route targets, missing loop routes,
  invalid workflow starts, and invalid edge sources.
- Derived foreach item schemas from declared input/state array sources, falling
  back to `{}` when the source is not declared as an array with an item schema.
- Added Task 1 authoring projection helpers for canonical `context.<key>` paths.
  Runtime context is offered only for `step_input`; workflow output projections
  do not advertise `context.*`.
- Added coverage for ordinary frames, serial/concurrent foreach, conditional
  reachability, nested scope replacement/restoration, malformed routes, cyclic
  graphs, alias deduplication, and authoring projection behavior.

## Test-First Evidence

The required RED command was run after adding tests and before production
changes:

```text
uv run pytest tests/core/test_context_scopes.py tests/core/test_scheduler.py tests/wf_api/test_authoring_contracts.py -q
```

It failed during collection for the expected missing production seams:

```text
ModuleNotFoundError: No module named 'wf_core.analysis'
ImportError: cannot import name 'context_path_options' from 'wf_api.authoring_contracts'
14 passed, 2 errors
```

## Verification

```text
uv run pytest tests/core/test_context_scopes.py tests/core/test_scheduler.py tests/wf_api/test_authoring_contracts.py -q
29 passed

uv run pytest tests/core -q
296 passed

uv run pytest tests/wf_api/test_authoring_contracts.py -q
7 passed

uv run ruff check src/wf_core/context_contracts.py src/wf_core/analysis src/wf_core/runtime/ops/frames.py src/wf_api/authoring_contracts.py tests/core/test_context_scopes.py tests/core/test_scheduler.py tests/wf_api/test_authoring_contracts.py
All checks passed!

uv run basedpyright --level error src/wf_core/context_contracts.py src/wf_core/analysis src/wf_core/runtime/ops/frames.py
0 errors, 0 warnings, 0 notes
```

## Concerns

- Foreach item schema traversal intentionally handles declared direct object
  properties and array `items`; complex external or deeply composed schema
  references fall back conservatively to `{}` rather than inventing a type.
- The authoring projector accepts an optional workflow for automatic context
  projection, while existing callers can continue supplying Task 1 payloads
  explicitly.
