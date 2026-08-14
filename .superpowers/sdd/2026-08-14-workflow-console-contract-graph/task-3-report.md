# Task 3 Report: Expose Authoring Contract Inspection

## Status

Implemented Task 3 of the workflow contract graph backend slice.

## Changes

- Added `WorkflowDraftSurface.inspect_draft_authoring_contract` and the
  matching `WorkflowApi` implementation.
- Added read-only persisted workspace loading with canonical revision-conflict
  precedence and no validation-save or revision mutation.
- Projected tolerant workflow input/state/output schemas through the Task 1
  inventory projector.
- Projected resolved capability input/output schemas, outcomes, descriptions,
  and executable entry candidates for keyed `use` steps. Projection ids and
  `__end__` are not advertised as entry candidates.
- Integrated Task 2 runtime context analysis for the selected step. Compile or
  interpretation failures leave scoped context empty and become warnings.
- Added the JSON-RPC params model, method dispatch, typed remote client method,
  nullable `selected_step_id`, and named OpenRPC payload references.
- Preserved existing domain error mapping for unknown steps and missing
  workspaces, `-32602` for malformed RPC params, and the existing
  `revision_conflict` result for stale revisions.

## Test-First Evidence

The required RED command was run after adding the service tests and before
production implementation:

```text
uv run pytest tests/wf_api/test_drafts_service.py -q -k authoring_contract
```

It failed for the expected missing seam:

```text
4 failed
AttributeError: 'WorkflowApi' object has no attribute
'inspect_draft_authoring_contract'
```

After implementation, the new authoring-contract service and transport tests
passed:

```text
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_openrpc_contract.py -q -k authoring_contract
12 passed
```

## Verification

```text
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_openrpc_contract.py -q -k "not reads_admin_state"
391 passed, 184 warnings

uv run ruff check <touched source and test files>
All checks passed!

uv run ruff format --check <touched source and test files>
10 files already formatted

uv run basedpyright --level error <touched source files>
0 errors, 0 warnings, 0 notes
```

The exact broad target command also contains the existing
`test_rpc_workflow_client_reads_admin_state` failure: its recorded event lacks
the required `timestamp_epoch_ms` field when serialized as `AdminEventPayload`.
That failure reproduces in isolation and is unrelated to the Task 3 files.

No Serena configuration was modified.

## Concerns

- The repository's existing admin-event timestamp validation failure prevents
  the unfiltered four-file target command from being fully green; the full
  target set passes when that isolated test is excluded.
- FastAPI JSON-RPC emits deprecation warnings from the installed
  `fastapi-jsonrpc` dependency; no new warning class was introduced.

## Round 1 Review Fixes

Addressed all three Important findings from `task-3-review.md`.

### Test-First Evidence

Each regression was verified RED before its production fix:

- Invalid persisted workflow schema: `test_inspect_draft_authoring_contract_tolerates_invalid_workflow_schema` initially raised `ValueError` from `schema_path_options` during inventory projection.
- Saved wrapper capability: `test_inspect_draft_authoring_contract_resolves_saved_wrapper_capability` initially returned no entry contract because the service only called `get_qualified_spec`.
- Explicit empty capability schemas: `test_inspect_draft_authoring_contract_preserves_empty_capability_schemas` was forced back to the pre-fix truthiness resolver and then advertised Pydantic model fields instead of empty projections.

### Fixes

- Added per-schema validation at the inventory service boundary. Invalid persisted input, state, or output schemas now produce an empty affected projection and a warning while preserving the other inventory sections.
- Added `WorkflowCapabilityApi.resolve_capability_contract` as the shared resolver for live `NodeSpec` and saved wrapper contracts. Draft inventory inspection now resolves wrapper artifacts using the same capability surface and preserves wrapper schemas/outcomes.
- Capability schema fallback now uses `is not None`, preserving explicit `{}` input and output contracts.

### Verification

```text
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_api/test_capability_api.py tests/wf_api/test_authoring_contracts.py -q -k "inspect_draft_authoring_contract or authoring_contract or saved_wrapper"
17 passed

uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_openrpc_contract.py -q -k "not reads_admin_state"
394 passed, 184 warnings

uv run ruff check
All checks passed

uv run ruff format --check <touched files>
3 files already formatted

uv run basedpyright --level error src/wf_api/capabilities.py src/wf_api/service.py
0 errors, 0 warnings, 0 notes
```

Repository-wide basedpyright still reports 394 pre-existing diagnostics in
unrelated examples, CLI, MCP, and test files. The known isolated
`test_rpc_workflow_client_reads_admin_state` failure remains excluded from the
target command; no admin-event or Serena configuration files were changed.
