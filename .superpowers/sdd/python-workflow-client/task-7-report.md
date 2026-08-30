# Task 7 Report

## Delivered

- Added a real `httpx.ASGITransport` proof for capability discovery, local
  authoring, remote validation, immutable artifact save, deployment selection,
  and durable run execution.
- Added bounded, inert `repr()` and `_repr_html_()` implementations for the
  Python client's loaded capability, artifact, deployment, validation, run,
  diagnostic, and trace objects. The shared private renderer HTML-escapes,
  bounds nested previews, and redacts credential-shaped keys without touching
  the client port.
- Added the `wf_client` package map, source/API boundary notes, and a concrete
  Python walkthrough that explains the artifact -> deployment -> run model.
- Added an opt-out seam for server draft composition. `drafts=False` skips
  draft service construction, does not require a draft store, and omits draft
  JSON-RPC methods; the existing implementation remains available to explicit
  draft-enabled callers.

## Verification

- `uv run pytest tests/wf_client -q` — 46 passed.
- Focused/cross-layer Task 7 selection — 288 passed.
- `uv run pytest tests/wf_api/test_durable_context.py tests/wf_transport_rpc_http/test_app.py::test_rpc_app_can_omit_draft_methods -q` — passed.
- Ruff check and basedpyright for changed client/API/transport surfaces — passed.
- `uv run python -m wf_contract_manifest check` — passed.
- `pnpm --dir web --filter @lda/workflow-rpc contract:check` — passed.
- `pnpm --dir web --filter @lda/workflow-rpc test` — 151 passed, 3 skipped.

The broader repository format check still reports pre-existing formatting
differences in `src/wf_api/deployments.py`, `src/wf_authoring/builder/core.py`,
and `tests/wf_client/test_authoring.py`; no formatting errors remain in the
changed Task 7 files. The full `uv run pytest -q` run reached 2,613 passed,
1 skipped, and 1 xfailed; three failures were external to this change: two
legacy direct-service/draft tests were fixed by retaining the default-enabled
constructor compatibility, while the remaining thesis asset test expects
untracked PDF figures absent from the base worktree.
