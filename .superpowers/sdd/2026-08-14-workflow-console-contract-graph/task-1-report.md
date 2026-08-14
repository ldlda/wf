# Task 1 Report: Model Schema-Derived Authoring Choices

## Status

Implemented Task 1 of the workflow contract graph backend slice.

## Changes

- Added explicit transport payload types for path options, step contracts, and
  revision-scoped authoring inventories.
- Added `schema_path_options`, which derives deterministic parent-before-child
  choices from JSON Schema object properties.
- Preserved whole arrays as selectable paths without synthetic wildcard paths.
- Omitted invented child names for unconstrained or open-ended
  `additionalProperties`.
- Reused `schema_fragment_at_location` and its bounded local-reference depth for
  nested schema fragments and `$defs`/`definitions` references.
- Derived labels from schema titles or humanized path segments and copied only
  string descriptions.
- Added pure inventory composition for input/state/context sources, selected
  step targets and sources, state/output targets, entry steps, outcomes, and
  warnings.
- Re-exported the new payload types through `wf_api.models`.

## Test-First Evidence

The required RED command was run before production implementation:

```text
uv run pytest tests/wf_api/test_authoring_contracts.py -q
```

It failed during collection with:

```text
ModuleNotFoundError: No module named 'wf_api.authoring_contracts'
```

After implementation, the focused authoring-contract tests passed.

## Verification

```text
uv run pytest tests/wf_api/test_authoring_contracts.py tests/wf_api/test_schema_projection.py -q
48 passed

uv run basedpyright --level error src/wf_api/authoring_contracts.py src/wf_api/models/authoring_contracts.py
0 errors, 0 warnings, 0 notes

uv run ruff check src/wf_api/authoring_contracts.py src/wf_api/models/authoring_contracts.py src/wf_api/models/__init__.py tests/wf_api/test_authoring_contracts.py
All checks passed!

uv run ruff format --check src/wf_api/authoring_contracts.py src/wf_api/models/authoring_contracts.py src/wf_api/models/__init__.py tests/wf_api/test_authoring_contracts.py
4 files already formatted
```

## Concerns

None for the Task 1 scope. Runtime-context analysis and persisted workspace or
capability loading remain intentionally deferred to Tasks 2 and 3.

## Round 1 Fix

The review identified that recursive schema walking was not bounded even
though individual `$ref` chains were bounded. A self-referential local
definition repeatedly expanded `_append_schema_options` until
`RecursionError`.

Added the regression test
`test_schema_path_options_stops_expanding_recursive_local_definition` before
changing production code. The RED run failed with `RecursionError` in
`_append_schema_options` after repeatedly traversing the self-reference.

The fix tracks active local `$ref` definitions per traversal branch. A repeated
definition is emitted as a selectable path but is not expanded again. Distinct
active references are also capped using the existing
`_MAX_LOCAL_SCHEMA_REFERENCE_DEPTH` limit from `schema_projection`.

Round 1 verification:

```text
uv run pytest tests/wf_api/test_authoring_contracts.py tests/wf_api/test_schema_projection.py -q
49 passed

uv run basedpyright --level error src/wf_api/authoring_contracts.py src/wf_api/models/authoring_contracts.py
0 errors, 0 warnings, 0 notes

uv run ruff check src/wf_api/authoring_contracts.py src/wf_api/models/authoring_contracts.py src/wf_api/models/__init__.py tests/wf_api/test_authoring_contracts.py
All checks passed!

uv run ruff format --check src/wf_api/authoring_contracts.py src/wf_api/models/authoring_contracts.py src/wf_api/models/__init__.py tests/wf_api/test_authoring_contracts.py
4 files already formatted
```
