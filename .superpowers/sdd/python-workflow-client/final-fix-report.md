# Final fix recovery report

## Scope

Audited the uncommitted patch on `b377311a` against the final review findings
and the Python workflow-client design/plan. The generated `.wf_mcp_store/` and
`test-artifacts/` directories were left untouched and unstaged.

## Fixes completed

- Opted the remaining draft-focused RPC client test into `drafts=True`; default
  server/storage composition remains draft-free.
- Added the public HTTP port adapter used by `App.from_http_jsonrpc()`. HTTP,
  connection, malformed JSON, and malformed JSON-RPC response failures become
  `WorkflowClientError` subclasses; known workflow error codes map to stable
  subclasses and unknown codes remain inspectable `ProtocolError` values with
  code/message/data preserved.
- Added strict identity validation for artifact inspection/save, capability
  calls, deployment lifecycle, run lifecycle, and bounded trace pages.
- Made `WorkflowArtifact`, `Deployment`, and `Run` retain deep private copies
  and expose defensive copies for nested mutable values.
- Narrowed workflow-plan reconstruction handling to Pydantic `ValidationError`.
- Typed deployment drift policy with the existing `wf_artifacts.DriftPolicy`
  enum and removed unused internal client exports/protocol operations.
- Hardened the underlying RPC client against valid JSON values that are not
  JSON-RPC objects, and removed `frozen=True` from `RpcProtocolError` so Python
  can attach exception traceback state.

## Verification

Commands were run from the feature worktree.

| Command | Result |
| --- | --- |
| `uv run pytest -q tests/wf_client tests/wf_transport_rpc_http` | **292 passed**, 257 warnings |
| `uv run pytest -q tests/wf_client tests/authoring/test_builder.py tests/authoring/test_subgraph.py tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_openrpc_contract.py tests/wf_contract_manifest/test_generate.py tests/wf_contract_manifest/test_committed_manifest.py tests/wf_api/test_stores.py tests/wf_server/test_local_static_server.py tests/wf_mcp/test_mcp_workflow_server.py tests/wf_mcp/server/test_tools.py tests/wf_mcp/workflow_surface tests/wf_cli/test_context.py tests/wf_server/test_cli.py` | **429 passed**, 201 warnings |
| `uv run ruff check` | **All checks passed** |
| `uv run ruff format --check` | **677 files already formatted** |
| `uv run basedpyright --level error` | **0 errors, 0 warnings, 0 notes** |
| `uv run python -m wf_contract_manifest check` | **checked** `contracts/workflow-api.manifest.json` |
| `pnpm --dir web --filter @lda/workflow-rpc contract:check` | **passed** |
| `pnpm --dir web --filter @lda/workflow-rpc test` | **151 passed**, 3 skipped |
| `git diff --check` | **passed** |
| `uv run pytest -q` | **2644 passed**, 1 skipped, 1 xfailed; 1 known baseline failure: `tests/docs/test_big_doc_links.py::test_thesis_bundle_has_reproducible_agent_evaluation_assets` (missing generated thesis figure PDFs) |

The full-suite failure is the documented pre-existing missing-asset failure;
no thesis assets were generated or added.
