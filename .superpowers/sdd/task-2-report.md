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
