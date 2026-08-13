# Task 5 Review Fix Report

## Status

Complete. Task 6 was not started.

## Fixed Findings

### P1: Legacy form expression preservation

`CapabilityNodeForm` now carries expression bindings found in rehydrated
`initialValue.inputBindings` through legacy-form submission. The existing
schema editor still owns simple path/value serialization; expression rows are
appended only from the rehydrated expression subset, so they are preserved
without duplicating rows or pretending that the legacy editor can edit them.

Added an interaction regression covering render, submit, and exact preservation
of a rehydrated array expression.

### P1: Sound discriminated `oneOf` translation

The JSON Schema translator now accepts the special case only when all branches
are distinct local component references, the discriminator mapping is an exact
branch mapping, and every referenced branch is a closed object with the
required discriminator property constrained to a distinct string `const`.

Decorative inline discriminators and overlapping branches without discriminator
constants now fail translation instead of being weakened into an Effect union.

### P2: TypeScript expression node budget

Added shared recursive traversal helpers with the canonical `1024` node limit.
The count includes expression nodes and nested array/object containers inside
literal values. The check is applied to authored expression bindings and to
runtime RPC payload/result boundaries, with cyclic values rejected safely.

Added runtime and authored validation-error regressions for both large
expression arrays and nested literal containers.

### P2: Named generated `StepInputBinding`

Changed the canonical Python alias to `typing.TypeAliasType`, causing the
OpenRPC manifest and generated TypeScript contract to expose a named
`StepInputBinding` component/type. Repeated node-local operation fields now
reference that name, while workflow-output bindings remain on the simple
path/value union.

Updated the method registry and generated contract tests to consume the
generated alias. The manifest and TypeScript contract were regenerated with
the documented commands; no generated file was hand-edited.

## TDD Evidence

The new form, translator, runtime-budget, authored-budget, manifest, and
generator tests were written before their corresponding fixes. The initial
focused runs reproduced the four review failures; the final focused runs are
green.

## Verification

- `uv run pytest tests/wf_contract_manifest/test_generate.py tests/wf_contract_manifest/test_committed_manifest.py tests/wf_transport_rpc_http/test_openrpc_contract.py tests/core/test_input_expressions.py tests/core/test_input_expression_runtime.py tests/core/test_canonical_node_bindings.py tests/wf_transport_rpc_http/test_rpc_models.py tests/wf_api/test_input_expression_validation.py -q` — **168 passed**
- `pnpm --dir web --filter @lda/workflow-rpc test` — **147 passed, 6 skipped** across 13 files
- Focused console tests — **59 passed** across 5 files
- `pnpm --dir web --filter @lda/workflow-rpc typecheck` — clean
- `pnpm --dir web --filter @lda/console typecheck` — clean
- `pnpm --dir web --filter @lda/workflow-rpc contract:check` — clean
- `uv run ruff check ...` — clean
- `git diff --check` — clean; only expected Windows LF/CRLF warnings

An additional broader sweep exposed an unrelated existing admin-events fixture
failure: `test_rpc_workflow_client_reads_admin_state` omits the required
`timestamp_epoch_ms` field. It is outside this Task 5 remediation and no
production code was changed for it.
