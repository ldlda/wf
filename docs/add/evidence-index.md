# Thesis Evidence Index

This file maps thesis claims to implementation evidence. It is not prose for the
final report; it is a guardrail against unsupported claims.

## Core Workflow Lifecycle

Claim: The platform separates mutable drafts, immutable artifacts, deployments,
runs, and traces.

Evidence:

- `src/wf_artifacts/models.py` — artifact/deployment models.
- `src/wf_artifacts/runs/` — run records and run store.
- `src/wf_api/service.py` — facade for workflow lifecycle operations.
- `tests/wf_api/test_artifact_api.py`
- `tests/wf_api/test_run_api.py`

## Source Provider Boundary

Claim: Workflow execution consumes source-provided capabilities without making
the core runtime MCP-specific.

Evidence:

- `src/wf_platform/sources.py` — neutral source DTOs and source policy.
- `src/wf_server/config.py` — server composition for configured sources.
- `src/wf_sources_mcp/` — MCP source family.
- `src/wf_sources_python/` — Python source family.
- `docs/source_architecture.md`

## Agent-Operable Surface

Claim: External agents can operate the workflow lifecycle through stable CLI/API
surfaces.

Evidence:

- `src/wf_cli/`
- `src/wf_transport_rpc_http/`
- `tests/wf_cli/`
- `tests/wf_transport_rpc_http/`
- `docs/wf_cli.md`

## Validation And Diagnostics

Claim: Validation and diagnostics make failed workflow states repairable.

Evidence:

- `src/wf_artifacts/validation.py`
- `src/wf_api/next_actions.py`
- `src/wf_api/source_admin.py`
- `tests/artifacts/test_validation.py`
- `tests/wf_api/test_source_admin_api.py`

## Stateful MCP Source Correctness

Claim: MCP-backed sources can preserve stateful sessions across workflow calls.

Evidence:

- `src/wf_sources_mcp/runtime/`
- `src/wf_sources_mcp/client/`
- `tests/wf_sources_mcp/test_runtime.py`
- `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

## Python Source Case Study

Claim: The source-provider model is not MCP-only.

Evidence:

- `examples/report_workflow/`
- `src/wf_sources_python/`
- `tests/examples/test_report_workflow_example.py`
- `tests/wf_sources_python/test_loader.py`
- `examples/browser_click_workflow/`
- `tests/examples/test_browser_click_workflow_example.py`
- `examples/agent_challenges/browser_click_challenge/`
- `tests/examples/test_opencode_browser_click_challenge.py`

## Limitations

Claim: This is a prototype platform substrate, not a finished automation product.

Evidence:

- `docs/add/thesis-outline.md`
- `docs/current_roadmap.md`
- absence of scheduler/visual-editor/secret-manager production packages in
  current source tree.
