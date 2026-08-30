# Task 6 report: deployment and durable run objects

## Status

Implemented and committed as `112e9656` (`feat: add Python deployment and run objects`).

## Files

- Added `src/wf_client/deployments.py` with immutable `Deployment` and
  `DeploymentValidation` snapshots plus strict artifact deployment selection.
- Added `src/wf_client/runs.py` with immutable `Run` and bounded `TracePage`
  snapshots, resume/refresh lifecycle methods, and core interrupt/trace
  reconstruction.
- Added `tests/wf_client/test_deployments.py` and
  `tests/wf_client/test_runs.py`.
- Updated `WorkflowArtifact`, `App`, public exports, codecs, and structured
  deployment exceptions.

## Verification

- `uv run pytest tests/wf_client/test_deployments.py tests/wf_client/test_runs.py tests/wf_api/test_deployment_api.py tests/wf_api/test_run_api.py -q` — **30 passed**.
- `uv run pytest tests/wf_client -q` — **28 passed**.
- `uv run ruff check src/wf_client tests/wf_client/test_deployments.py tests/wf_client/test_runs.py` — **passed**.
- `uv run basedpyright --level error src/wf_client tests/wf_client/test_deployments.py tests/wf_client/test_runs.py` — **0 errors**.

## Caveats

- `.wf_mcp_store/` and `test-artifacts/` remain untracked generated directories
  and were intentionally not staged.
- Trace limits follow the existing server bound of 1–100 and are validated
  before issuing a trace request.

## Review fix round 1

Identity checks now reject mismatched deployment/artifact/run ids at every
inspect, validate, start, refresh, and resume boundary. Nested interrupt route
references are converted to `InvalidResponse` with operation context, and run
decoding accepts truthful inspect/start/resume operation names.

Fixes committed in the follow-up review commit for this report.

## Review fix round 2

The sole discovered deployment path now rechecks the inspected artifact
identity, deployment creation acknowledgements and inspected ids are checked
before validation, and run-start responses enforce deployment plus artifact
identity. Missing-run errors preserve server text, including operation-aware
start interrupt decoding.
