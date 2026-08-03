# Task 2 Report

## Scope

Implemented fail-closed contract and `$ref` validation for
`wf_contract_manifest.manifest_from_openrpc()` without changing the Task 1
public interface. JSON Schema keywords remain opaque; validation is limited to
the OpenRPC envelope, normalized operation/component values, and their `$ref`
graph.

## TDD Evidence

- Added tests for unsupported OpenRPC versions, malformed envelopes, duplicate
  methods, malformed dotted names, invalid parameters, invalid result shapes,
  and non-component success results.
- Added tests for external, unsupported-local, unsupported-component,
  dangling, and escaped component references.
- Added a passing nested schema reference case while retaining the existing
  error-component reference assertion.
- Ran the new tests before implementation: 10 cases failed for the intended
  missing validation behaviors; existing Task 1 coverage remained green.

## Implementation

- Pins `$.openrpc` to `1.2.6`.
- Rejects duplicate method names at the later method path.
- Uses the strict `malformed dotted method name` diagnostic.
- Requires success results to be exactly a local `components/schemas` `$ref`
  object.
- Walks every operation parameter/result/error and every normalized component,
  recursively inspecting only `$ref` values.
- Rejects external refs, unsupported namespaces, escaped component keys, and
  dangling refs; forward refs are accepted after the complete manifest is
  assembled.

## Verification

```text
39 passed in 0.10s
ruff check: All checks passed!
basedpyright --level error: 0 errors, 0 warnings, 0 notes
git diff --check: passed (only Git line-ending warnings)
```

## Commit

The Task 2 commit is recorded by the final response after the final verification
and scope audit.

## Concerns

None identified.

## Task 2 Review Fixes

### Findings Addressed

1. Reference validation now runs against operations in original source order,
   and reports `$.methods[index]...` paths before deterministic lexical sorting.
   A regression test uses the source order `workflow.zeta.run`, then
   `workflow.alpha.inspect`, and asserts the exact later ref path.
2. Success result validation now checks raw mapping keys before `_schema()`
   removes `title`, so a valid `$ref` plus an extra `title` is rejected.
3. The malformed-contract mutation table now uses the typed
   `DocumentMutation` Protocol instead of an `Any` mutation annotation.

### TDD Evidence

- Review regression tests were run before implementation: 2 failed as
  intended, one for the title-stripping acceptance and one for the sorted
  operation path.
- After implementation, all 41 focused normalization tests passed.

### Fix Verification

```text
.venv\Scripts\python.exe -m pytest tests\wf_contract_manifest\test_normalize.py -n 0 -q
41 passed in 0.13s

.venv\Scripts\ruff.exe check src\wf_contract_manifest tests\wf_contract_manifest
All checks passed!

.venv\Scripts\basedpyright.exe --level error src\wf_contract_manifest tests\wf_contract_manifest
0 errors, 0 warnings, 0 notes

git diff --check
passed (only Git line-ending warnings)
```

### Fix Concerns

None identified.
