# Workflow Artifact Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make saved workflow artifacts safe enough to rely on before merging MCP server modes or exposing workflow execution more broadly.

**Architecture:** Keep `wf_artifacts` provider-neutral. `wf_mcp` may project artifact operations, but validation, storage, artifact creation, and diagnostics should stay in `wf_artifacts` where possible.

**Tech Stack:** Python 3.14, Pydantic v2, pytest, `wf_core.Workflow` validation, existing `wf_mcp` broker service.

---

## Why This Comes First

The live Codex probe proved the artifact execution path works, but it also found
a real weakness: `create_workflow_artifact_from_plan` saved an invalid
`state_schema` shape, and the error surfaced only when `run_workflow_deployment`
tried to compile the workflow.

Before unifying broker and transparent proxy modes, artifact creation should
reject invalid plans earlier and return structured diagnostics.

## Scope

This plan hardens saved workflow creation and dependency validation. It does not
merge MCP server modes and does not add native subgraphs.

## Tasks

### Task 1: Validate Plan Shape During Artifact Creation

**Files:**

- Modify: `src/wf_artifacts/factory.py`
- Test: `tests/artifacts/test_factory.py`

- [ ] Add a failing test proving `create_workflow_artifact_from_plan` rejects a
      plan that cannot become a `wf_core.Workflow`.
- [ ] Implement validation by constructing `wf_core.Workflow.model_validate`
      from the plan fields.
- [ ] Keep the validation dependency one-way: `wf_artifacts` may import
      `wf_core`, but `wf_core` must not import `wf_artifacts`.
- [ ] Return `ValueError` with a concise message containing the failing field
      path or Pydantic error message.
- [ ] Run `uv run --with pytest pytest tests\artifacts\test_factory.py -q`.

### Task 2: Add Artifact Creation Diagnostics

**Files:**

- Modify: `src/wf_artifacts/models.py`
- Modify: `src/wf_artifacts/factory.py`
- Test: `tests/artifacts/test_factory.py`

- [ ] Decide whether creation failures should raise exceptions only or also
      expose a `validate_workflow_artifact_plan(...) -> list[DependencyDiagnostic]`
      style function.
- [ ] Recommended v1: add a separate `validate_workflow_artifact_plan(plan)`
      that returns structured diagnostics, while the factory still raises on errors.
- [ ] Add tests for missing `input_schema`, missing `output_schema`, invalid
      state schema, and missing start node.

### Task 3: Validate Direct Workflow Dependencies

**Files:**

- Modify: `src/wf_artifacts/validation.py`
- Test: `tests/artifacts/test_validation.py`

- [ ] Add artifact-store-aware validation for `workflow_dependencies`.
- [ ] Validate exact artifact-version pins.
- [ ] Return `dependency_missing` when a child artifact version does not exist.
- [ ] Return `dependency_cycle` when direct/transitive workflow artifact
      dependencies cycle.
- [ ] Do not copy child dependency snapshots into the parent.

### Task 4: Improve Capability Contract Checking

**Files:**

- Modify: `src/wf_artifacts/validation.py`
- Test: `tests/artifacts/test_validation.py`
- Optional: `src/wf_mcp/broker/artifact_tools.py`

- [ ] Preserve current hash comparison behavior.
- [ ] Add tests for kind mismatch, for example required `tool` but available
      `node_spec`.
- [ ] Decide whether `node_spec` can satisfy `tool` when the provider is an MCP
      wrapper. Recommended: no implicit kind coercion in `wf_artifacts`; adapters
      should present the available kind they mean to expose.
- [ ] Add diagnostics with `code="capability_kind_mismatch"`.

### Task 5: Document Current Runtime Limitations In Tool Responses

**Files:**

- Modify: `src/wf_mcp/broker/artifact_tools.py`
- Test: `tests/wf_mcp/test_broker_server.py`

- [ ] Keep interrupting artifacts rejected by `run_workflow_deployment`.
- [ ] Add `repair_hint` text explaining native subgraphs/nested resume are not
      implemented yet.
- [ ] Add a test proving unsupported interrupt artifacts return a diagnostic
      instead of raising.

## Verification

- [ ] `uv run --with pytest pytest tests\artifacts -q`
- [ ] `uv run --with pytest pytest tests\wf_mcp\test_broker_server.py -q`
- [ ] `uv run --with pytest pytest -q`
- [ ] `uv run ruff check src tests examples main.py`
- [ ] `uv run basedpyright src tests examples main.py --level error`

## Non-Goals

- No native `wf_core` subgraph implementation.
- No MCP Tasks implementation.
- No run history persistence.
- No broker/transparent mode merge in this plan.
