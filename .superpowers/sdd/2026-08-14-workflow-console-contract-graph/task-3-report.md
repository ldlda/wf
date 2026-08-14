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
