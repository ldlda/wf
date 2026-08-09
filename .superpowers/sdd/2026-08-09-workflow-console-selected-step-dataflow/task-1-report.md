# Task 1 Report

## Outcome

Task 1 is implemented on `main`. The canonical `InputValueBinding.value` contract
now accepts recursive JSON values, including finite numbers, while preserving
boolean/integer distinction and rejecting non-JSON objects and non-finite
numbers. The two focused browser RPC operations are authored, dispatched,
registered, exported, tested, and included in the explicit browser policy.

The authored RPC fixture now uses the same recursive JSON-value schema as the
canonical/generated contract. Runtime and parity tests cover scalar, boolean,
null, array, and object literals.

## Changed Files

- `src/wf_core/models/steps.py`: Added the canonical recursive finite JSON-value alias and used it for `InputValueBinding.value`.
- `tests/core/test_canonical_node_bindings.py`: Added category, recursion, rejection, boolean-distinction, and finite-number tests.
- `tests/wf_contract_manifest/test_generate.py`: Added manifest operation and recursive `JsonValue` assertions; updated generated component count.
- `contracts/workflow-api.manifest.json`: Regenerated checked manifest.
- `web/packages/rpc/scripts/workflow-contract-generator.ts`: Added both focused methods to the runtime operation cohort.
- `web/packages/rpc/scripts/workflow-contract-generator.test.ts`: Added missing-operation and reachable-schema coverage for both methods and recursive `JsonValue` output.
- `web/packages/rpc/src/generated/workflow-contract.ts`: Regenerated checked TypeScript contract.
- `web/packages/rpc/src/json-schema/authored-rpc-fixtures.ts`: Replaced object-only input literal validation with recursive JSON-value validation and added focused authored fixtures.
- `web/packages/rpc/src/json-schema/runtime-schema.test.ts`: Added focused runtime schema inventory and JSON literal coverage.
- `web/packages/rpc/src/json-schema/rpc-parity.test.ts`: Added both payload/result parity cases and canonical binding-union coverage.
- `web/packages/rpc/src/rpcs.ts`: Added schema-backed `Rpc.make` definitions and `WorkflowRpcs` membership.
- `web/packages/rpc/src/service.ts`: Added decode-before-dispatch cases for both operations.
- `web/packages/rpc/src/method-registry.ts`: Added metadata, interpretation, and replacement CLI evidence renderers.
- `web/packages/rpc/src/index.ts`: Added public operation and payload/result schema exports.
- `web/packages/rpc/src/service.test.ts`: Added representative request/response dispatch cases.
- `web/packages/rpc/src/method-registry.test.ts`: Added set-input/set-output, clear, and non-equivalent evidence assertions.
- `web/apps/console/src/connection/contracts.ts`: Added both operation names to the explicit browser DTO contract.
- `web/apps/server/src/browser-operation-policy.ts`: Added both names to the explicit browser allowlist.
- `web/apps/server/src/browser-operation-policy.test.ts`: Pinned the allowlist and continued rejecting generic/admin operations.
- `web/apps/server/src/app.test.ts`: Added one accepted request case per operation.

## TDD Evidence

### RED

- Initial brief commands passed the pre-existing tests: Python `25 passed`; generator `8 passed`, demonstrating the missing behavior was not previously asserted.
- After adding canonical/generator tests, Python failed `3` targeted tests: unconstrained `object` had no recursive `$defs` and accepted `object()`; the manifest value had no `anyOf`. Generator failed `3` tests because both operations were absent from the runtime cohort.
- After adding RPC/server tests, the RPC focused run failed `8` tests: both service operations were unknown, both registry entries were missing, and the authored RPC catalog did not contain the new methods. The requested `@lda/server` pnpm selector did not exist in this workspace.
- The finite-number test then failed all `3` cases before switching the canonical alias to `FiniteFloat`.

### GREEN

- Canonical/manifest Python suite: `38 passed`.
- Contract generator suite: `11 passed`.
- Focused RPC suite: `66 passed`.
- Focused server suite: `32 passed`.

## Verification

- `pnpm --dir web --filter @lda/workflow-rpc typecheck`: passed.
- `pnpm --dir web --filter @lda/web-server typecheck`: passed.
- `pnpm --dir web --filter @lda/workflow-rpc contract:check`: passed.
- Touched-file `uv run ruff check`: passed.
- Touched-file `uv run ruff format --check`: passed.
- Touched-file `uv run basedpyright --level error`: `0 errors, 0 warnings, 0 notes`.
- `git diff --check`: passed; only Git line-ending warnings were reported.

## Deviations

- The brief names the server package `@lda/server`; the current workspace package is `@lda/web-server`, so the equivalent focused test and typecheck commands used `@lda/web-server`.
- Repository-wide `uv run ruff format --check` is not clean because unrelated pre-existing files under `src/wf_api/` would be reformatted. They were not changed.
- Repository-wide `uv run basedpyright --level error` reports `353` errors across the existing project. The touched Python files were checked separately and have zero diagnostics.

## Concerns

- Parity continues to report the translator's existing `oneOf` blockers for structural path unions. The new focused payloads add the corresponding `InputPathBinding.path` and `OutputBinding.source` blocker entries; authored and manifest acceptance remains aligned for tested values.
- No Serena configuration was modified, and no generated output was hand-edited.

## Round 1/5 Review Fix

### Changed Files

- `src/wf_core/models/steps.py`: Made `InputValueBinding` strict and added a recursive pre-validator that rejects tuples, sets, `Decimal`, non-string object keys, and non-finite numbers without coercion while retaining finite recursive JSON values and the existing generated schema.
- `tests/core/test_canonical_node_bindings.py`: Added rejection coverage for tuple, set, `Decimal`, and non-string-key values.
- `web/packages/rpc/src/json-schema/authored-rpc-fixtures.ts`: Added a shared `Schema.String.pipe(Schema.minLength(1))` path segment schema to every checked structural input/output binding path.
- `web/packages/rpc/src/json-schema/rpc-parity.test.ts`: Added authored decode tests for empty segments in input path, input value target, output source, and output target, plus checked-manifest component assertions for all five structural path fields.

### RED

- Before the production edits, the new Python test failed 3 cases: tuple, set, and `Decimal` were coerced; the non-string-key case already failed under the existing recursive validator.
- Before the Effect fixture edit, the new parity test accepted an empty `InputPathBinding.path` segment.

### GREEN

- `uv run pytest tests/core/test_canonical_node_bindings.py -q`: `36 passed`.
- `pnpm exec vitest run src/json-schema/rpc-parity.test.ts`: `5 passed`.

### Verification

- Focused RPC runtime/parity/generator tests: `28 passed`.
- RPC package typecheck: passed.
- Checked contract verification: passed with `All checks passed!`.
- Touched-file Ruff and basedpyright checks: passed; basedpyright reported `0 errors, 0 warnings, 0 notes`.
- `git diff --check`: passed; only Git line-ending warnings were reported.

### Deviations

- No generated output changed: strict Pydantic validation and authored fixture constraints preserve the existing checked contract, so the contract check was run without rewriting generated files.

### Concerns

- The pre-existing translator blockers for structural `oneOf` path unions remain unchanged; this round only tightens authored decode parity and confirms the checked component `minLength` constraints.
