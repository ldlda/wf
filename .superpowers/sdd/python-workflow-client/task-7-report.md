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

- Initial Task 7 client and cross-layer selection — 288 passed.
- Fix-round focused client/composition selection — 55 passed.
- Ruff check and basedpyright for changed client/API/transport surfaces — passed.
- `uv run python -m wf_contract_manifest check` — passed.
- `pnpm --dir web --filter @lda/workflow-rpc contract:check` — passed.
- `pnpm --dir web --filter @lda/workflow-rpc test` — 151 passed, 3 skipped.

The full repository suite was not used as the fix-round gate: legacy direct
draft-service tests still construct draft APIs without the now-required
explicit `drafts=True` opt-in, and one thesis asset test expects untracked PDF
figures absent from the base worktree. No generated `.wf_mcp_store/` or
`test-artifacts/` files are part of this change.

## Fix round 2

- `file_workflow_stores()` now skips `FileDraftWorkspaceStore` by default;
  `build_local_static_workflow_server()` forwards `drafts` so default local
  composition creates no draft directory, while `drafts=True` remains a
  working explicit opt-in.
- Draft-bearing MCP broker/workflow-surface and CLI compositions now pass
  `drafts=True` explicitly. The standalone RPC server CLI does the same for
  its documented draft RPC surface. The complete OpenRPC inventory fixture and
  draft-focused RPC tests now opt into both server storage and RPC method
  registration.
- The API architecture walkthrough now imports `App` from `wf_client`.

Fix-round 2 verification (fresh after formatting):

- `uv run pytest tests/wf_api/test_stores.py tests/wf_server/test_local_static_server.py tests/wf_mcp/test_mcp_workflow_server.py tests/wf_mcp/server/test_tools.py tests/wf_mcp/workflow_surface tests/wf_cli/test_context.py tests/wf_server/test_cli.py tests/wf_transport_rpc_http/test_openrpc_contract.py -q` — 183 passed.
- `uv run pytest tests/wf_client tests/authoring/test_builder.py tests/authoring/test_subgraph.py tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_openrpc_contract.py tests/wf_contract_manifest/test_generate.py tests/wf_contract_manifest/test_committed_manifest.py -q` — 291 passed, 201 warnings.
- Ruff check and `ruff format --check` on changed Python surfaces — passed.
- `uv run basedpyright --level error src/wf_api src/wf_cli src/wf_mcp/broker src/wf_mcp/workflow_surface src/wf_server` — 0 errors, 0 warnings, 0 notes.
- `uv run python -m wf_contract_manifest check` — passed.
- `pnpm --dir web --filter @lda/workflow-rpc contract:check` — passed.
- `pnpm --dir web --filter @lda/workflow-rpc test` — 151 passed, 3 skipped.
- `git diff --check` — passed.

## Fix round 1

- Normal `WorkflowApi`, nested capability/artifact services, durable context,
  local server construction, and JSON-RPC app composition now default to
  `drafts=False`. Draft APIs are stored as `None` when disabled and require
  explicit `drafts=True` at composition time; RPC registration rejects an
  opt-in against a disabled API.
- The two live walkthroughs now include real schemas, explicit constant input
  and output bindings, an `end` step, and the terminal route.
- The repr projector now follows the console evidence policy's exact-key
  matching, normalizes camelCase spellings (`apiKey`, `accessToken`, etc.),
  avoids false positives (`tokenCount`, `secretary`), and consumes at most a
  bounded prefix of mappings/sequences/iterables.
- Fix-round verification: focused client/composition tests `55 passed`; Ruff
  and basedpyright passed with zero errors.
