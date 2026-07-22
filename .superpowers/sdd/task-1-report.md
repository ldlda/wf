# Task 1 Report: Atomic Capability-Aware Output Replacement

## Changed Files

- `src/wf_api/draft_authoring.py`
  - Added stable-index overlap diagnostics for state targets.
  - Added the atomic output-binding patch builder.
  - Added `WorkflowDraftAuthoringApi.set_step_output_bindings` with revision-first
    validation, capability source validation, schema projection, exact-equivalent
    target reuse, no-op handling, and canonical ordered replacement.
- `src/wf_api/surface.py`
  - Added `set_step_output_bindings` to `WorkflowDraftSurface`, and therefore the
    composed `WorkflowApiSurface`.
- `src/wf_api/service.py`
  - Added the `WorkflowApi` delegation method.
- `tests/wf_api/test_drafts_service.py`
  - Added canonical replacement and source fan-out coverage.
  - Added nested and whole-payload schema projection coverage.
  - Added exact-equivalent no-op, clear, overlap, duplicate, missing-source,
    incompatible-target, missing-step, non-capability-step, stale-revision, and
    no-mutation coverage.
  - Added an explicit nested output schema contract matching the Task 1 brief.
- `tests/core/test_atomic_state_patches.py`
  - Added runtime source fan-out coverage asserting both state writes.

## RED Evidence

Command:

```text
uv run pytest tests/wf_api/test_drafts_service.py -q -k "step_output" --basetemp C:\\tmp\\pytest-task1-red
```

Result: 12 failed. Every failure reached the intended missing-feature error:
`AttributeError: 'WorkflowApi' object has no attribute 'set_step_output_bindings'`.

The first environment attempt could not start the local `uv` shim. A first
rerun also found a missing `StatePath` test import; that test-only error was
fixed before the canonical RED run above.

## GREEN Evidence

Focused API command:

```text
uv run pytest tests/wf_api/test_drafts_service.py -q -k "step_output" --basetemp C:\\tmp\\pytest-task1-green-api
```

Result: `12 passed in 9.51s`.

Required combined command:

```text
uv run pytest tests/wf_api/test_drafts_service.py tests/core/test_atomic_state_patches.py -q --basetemp C:\\tmp\\pytest-task1-green-all
```

Result: `160 passed in 9.93s`.

Additional verification:

- `uv run ruff check` on all five Task 1 files: passed.
- `uv run ruff format --check` on all five Task 1 files: passed.
- `uv run basedpyright --level error` on all five Task 1 files: `0 errors, 0 warnings, 0 notes`.
- `git diff --check`: passed.

## Deviations

- The test capability uses an explicit output schema contract rather than the
  generated Pydantic schema so the assertions match the brief's exact nested
  `title`/`markdown` contract and do not depend on generated metadata or `$ref`
  names.
- Pytest used `--basetemp C:\\tmp\\...` because the default system temp
  cleanup failed with `PermissionError: [WinError 5]` in this environment.
- RPC/MCP/CLI transport adapters were not changed; the brief limits Task 1 to
  the Python authoring/runtime contract and explicitly lists only the five
  implementation/test files.

## Concerns

Full repository `basedpyright --level error` remains red with four conformance
errors in `src/wf_cli/context.py`, `tests/wf_api/test_surface_protocol.py`, and
`tests/wf_transport_rpc_http/test_client.py`. These are downstream adapter
typing failures because `RpcWorkflowApiClient` does not yet implement the new
protocol method. The Task 1 scoped type check is clean; later transport work
must add the corresponding RPC/client surface before the full type check can
pass.
