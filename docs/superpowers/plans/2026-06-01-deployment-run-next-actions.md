# Deployment And Run Next Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add advisory `next_actions` guidance to deployment validation and run lifecycle responses so MCP clients know the safest next workflow tool to call.

**Architecture:** Extend the existing `src/wf_mcp/workflow_surface/next_actions.py` module with deployment/run constructors instead of putting more UX policy in `handlers.py`. Thread the resulting `NextActions` object into `validate_deployment(...)` and `_run_payload(...)`, which covers `run_deployment`, `resume_run`, `inspect_run`, and `read_run_trace`. Keep diagnostics and runtime status authoritative; `next_actions` remains advisory.

**Tech Stack:** Python 3.14, Pydantic v2, pytest, ruff, basedpyright.

---

## File Structure

- Modify `src/wf_mcp/workflow_surface/next_actions.py`
  - Add `NextActions.from_deployment_validation(...)`.
  - Add `NextActions.from_run_result(...)`.
  - Add tiny private helpers for diagnostic code inspection and bounded trace examples.

- Modify `src/wf_mcp/workflow_surface/handlers.py`
  - Add `next_actions` to `validate_deployment(...)`.
  - Add optional `next_actions` construction inside `_run_payload(...)`.
  - Do not duplicate branching logic in individual handler methods.

- Modify `tests/wf_mcp/workflow_surface/test_next_actions.py`
  - Unit-test deployment/run constructors directly.

- Modify `tests/wf_mcp/workflow_surface/test_deployments.py`
  - Assert `validate_deployment` returns useful next actions for runnable and unrunnable deployments.

- Modify `tests/wf_mcp/workflow_surface/test_runs.py`
  - Assert run lifecycle responses return next actions for completed and failed runs.
  - Add interrupt/resume tests only if an existing fixture/helper makes this small; otherwise leave interrupt-specific coverage to constructor unit tests.

- Modify `tests/wf_mcp/server/test_config.py`
  - Assert output schemas for `validate_deployment` and `run_deployment` include `next_actions`.

- Modify `docs/workflow_capabilities.md`
  - Add a short note that deployment/run responses now include advisory `next_actions`.

## Scope Boundaries

- Do not create new workflow tools.
- Do not make `next_actions` required for correctness.
- Do not read or return full traces automatically.
- Do not add auto-repair behavior.
- Do not change existing status strings, diagnostics, or run payload fields.
- Do not implement persisted resume changes in this pass.

---

### Task 1: Add Constructor Unit Tests

**Files:**
- Modify: `tests/wf_mcp/workflow_surface/test_next_actions.py`

- [ ] **Step 1: Add imports**

At the top of `tests/wf_mcp/workflow_surface/test_next_actions.py`, add:

```python
from wf_artifacts import DependencyDiagnostic, DiagnosticSeverity
```

Keep the existing `NextActionTool` / `NextActions` import.

- [ ] **Step 2: Add deployment validation constructor tests**

Append to `tests/wf_mcp/workflow_surface/test_next_actions.py`:

```python
def test_next_actions_from_runnable_deployment_recommends_run() -> None:
    actions = NextActions.from_deployment_validation(
        deployment_id="echo.personal",
        diagnostics=[],
    )

    dumped = actions.model_dump(mode="json")
    assert dumped["can_continue"] is True
    assert dumped["recommended_next_tool"] == NextActionTool.RUN_DEPLOYMENT.value
    assert "run_deployment" in dumped["reason"]
    assert dumped["warnings"] == []


def test_next_actions_from_unrunnable_deployment_recommends_validation_retry() -> None:
    diagnostic = DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="source_unreachable",
        logical_ref="demo.echo_tool",
        bound_source="demo.personal",
        message="Live check for upstream source 'demo.personal' failed.",
        repair_hint="Start or reconnect the source.",
    )

    actions = NextActions.from_deployment_validation(
        deployment_id="echo.personal",
        diagnostics=[diagnostic],
    )

    dumped = actions.model_dump(mode="json")
    assert dumped["can_continue"] is True
    assert dumped["recommended_next_tool"] == NextActionTool.VALIDATE_DEPLOYMENT.value
    assert "fix or reconnect" in dumped["reason"]
    assert dumped["warnings"][0] == "source_unreachable: demo.personal"
```

- [ ] **Step 3: Add run result constructor tests**

Append to `tests/wf_mcp/workflow_surface/test_next_actions.py`:

```python
def test_next_actions_from_completed_run_has_no_required_next_tool() -> None:
    actions = NextActions.from_run_result(
        run_id="run_123",
        status="completed",
        trace_count=2,
        diagnostics=[],
    )

    dumped = actions.model_dump(mode="json")
    assert dumped["can_continue"] is False
    assert dumped["recommended_next_tool"] is None
    assert "completed" in dumped["reason"]
    assert dumped["patch_examples"] == []


def test_next_actions_from_failed_run_recommends_bounded_trace() -> None:
    actions = NextActions.from_run_result(
        run_id="run_123",
        status="failed",
        trace_count=12,
        diagnostics=[],
    )

    dumped = actions.model_dump(mode="json")
    assert dumped["can_continue"] is True
    assert dumped["recommended_next_tool"] == NextActionTool.READ_RUN_TRACE.value
    assert "bounded trace" in dumped["reason"]
    assert dumped["patch_examples"][0]["tool"] == NextActionTool.READ_RUN_TRACE.value
    assert dumped["patch_examples"][0]["request"]["run_id"] == "run_123"
    assert dumped["patch_examples"][0]["request"]["trace_range"]["start"] == 0
    assert dumped["patch_examples"][0]["request"]["trace_range"]["limit"] == 25


def test_next_actions_from_interrupted_run_recommends_resume() -> None:
    actions = NextActions.from_run_result(
        run_id="run_123",
        status="interrupted",
        trace_count=3,
        diagnostics=[],
    )

    dumped = actions.model_dump(mode="json")
    assert dumped["can_continue"] is True
    assert dumped["recommended_next_tool"] == NextActionTool.RESUME_RUN.value
    assert "resume_run" in dumped["reason"]
    assert dumped["patch_examples"] == []
```

- [ ] **Step 4: Run the new tests to verify they fail**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py -q
```

Expected: FAIL with `AttributeError` for missing `from_deployment_validation` and `from_run_result`.

---

### Task 2: Implement Deployment/Run Constructors

**Files:**
- Modify: `src/wf_mcp/workflow_surface/next_actions.py`

- [ ] **Step 1: Add type-only imports**

In `src/wf_mcp/workflow_surface/next_actions.py`, add:

```python
from collections.abc import Sequence
```

Do not import `DependencyDiagnostic` directly unless needed at runtime. The constructors can accept diagnostics as objects or dicts to keep coupling low.

- [ ] **Step 2: Add `from_deployment_validation`**

Inside `class NextActions`, after `from_wrapper_hints(...)`, add:

```python
    @classmethod
    def from_deployment_validation(
        cls,
        *,
        deployment_id: str,
        diagnostics: Sequence[object],
    ) -> Self:
        """Create guidance after validate_deployment."""
        if not diagnostics:
            return cls(
                can_continue=True,
                can_save_now=None,
                recommended_next_tool=NextActionTool.RUN_DEPLOYMENT,
                reason=(
                    f"Deployment {deployment_id!r} is runnable; call "
                    "wf.workflow.run_deployment with workflow_input."
                ),
                patch_examples=[],
                warnings=[],
            )

        codes = {_diagnostic_field(diagnostic, "code") for diagnostic in diagnostics}
        warnings = [_diagnostic_warning(diagnostic) for diagnostic in diagnostics]
        if "source_unreachable" in codes:
            reason = (
                "One or more live sources are unreachable; fix or reconnect the "
                "source, then rerun wf.workflow.validate_deployment with live_check=true."
            )
        elif "source_missing" in codes or "binding_missing" in codes:
            reason = (
                "Deployment bindings or sources are missing; inspect the deployment "
                "and save corrected bindings before running."
            )
        elif "capability_missing" in codes or "schema_changed" in codes:
            reason = (
                "A required capability is missing or drifted; inspect capabilities "
                "or refresh sources, then validate again."
            )
        else:
            reason = (
                "Deployment is not runnable; inspect diagnostics, repair the "
                "deployment or sources, then validate again."
            )
        return cls(
            can_continue=True,
            can_save_now=None,
            recommended_next_tool=NextActionTool.VALIDATE_DEPLOYMENT,
            reason=reason,
            patch_examples=[],
            warnings=warnings,
        )
```

- [ ] **Step 3: Add `from_run_result`**

Inside `class NextActions`, after `from_deployment_validation(...)`, add:

```python
    @classmethod
    def from_run_result(
        cls,
        *,
        run_id: str | None,
        status: str,
        trace_count: int,
        diagnostics: Sequence[object],
    ) -> Self:
        """Create guidance after run_deployment, inspect_run, resume_run, or read_run_trace."""
        warnings = [_diagnostic_warning(diagnostic) for diagnostic in diagnostics]
        if status == "interrupted" and run_id is not None:
            return cls(
                can_continue=True,
                can_save_now=None,
                recommended_next_tool=NextActionTool.RESUME_RUN,
                reason=(
                    "Run is interrupted; call wf.workflow.resume_run with this "
                    "run_id and the interrupt response payload."
                ),
                patch_examples=[],
                warnings=warnings,
            )
        if status in {"failed", "unrunnable"}:
            examples = (
                [_bounded_trace_example(run_id=run_id, trace_count=trace_count)]
                if run_id is not None and trace_count > 0
                else []
            )
            return cls(
                can_continue=bool(examples),
                can_save_now=None,
                recommended_next_tool=(
                    NextActionTool.READ_RUN_TRACE if examples else None
                ),
                reason=(
                    "Run failed; read a bounded trace slice for debugging."
                    if examples
                    else "Run failed before producing trace entries; inspect diagnostics and error."
                ),
                patch_examples=examples,
                warnings=warnings,
            )
        if status == "completed":
            examples = (
                [_bounded_trace_example(run_id=run_id, trace_count=trace_count)]
                if run_id is not None and trace_count > 0
                else []
            )
            return cls(
                can_continue=False,
                can_save_now=None,
                recommended_next_tool=None,
                reason=(
                    "Run completed. No required next workflow tool; use read_run_trace "
                    "with a bounded trace_range only if debugging."
                ),
                patch_examples=examples,
                warnings=warnings,
            )
        return cls(
            can_continue=False,
            can_save_now=None,
            recommended_next_tool=None,
            reason=f"Run status {status!r} has no obvious next workflow tool.",
            patch_examples=[],
            warnings=warnings,
        )
```

- [ ] **Step 4: Add private diagnostic helpers**

Below `_wrapper_draft_patch_examples(...)`, add:

```python
def _diagnostic_field(diagnostic: object, field: str) -> str | None:
    """Read a diagnostic field from either a Pydantic model or a JSON dict."""
    if isinstance(diagnostic, dict):
        value = diagnostic.get(field)
    else:
        value = getattr(diagnostic, field, None)
    return value if isinstance(value, str) else None


def _diagnostic_warning(diagnostic: object) -> str:
    """Format one compact diagnostic warning for next_actions."""
    code = _diagnostic_field(diagnostic, "code") or "diagnostic"
    bound_source = _diagnostic_field(diagnostic, "bound_source")
    logical_ref = _diagnostic_field(diagnostic, "logical_ref")
    if bound_source:
        return f"{code}: {bound_source}"
    if logical_ref:
        return f"{code}: {logical_ref}"
    return code


def _bounded_trace_example(
    *,
    run_id: str,
    trace_count: int,
) -> NextActionPatchExample:
    """Return a safe read_run_trace request; never suggest full trace reads."""
    return NextActionPatchExample(
        description=(
            "Read a bounded debug trace slice. Increase start/limit only when needed."
        ),
        tool=NextActionTool.READ_RUN_TRACE,
        request={
            "run_id": run_id,
            "trace_range": {
                "start": 0,
                "limit": min(trace_count, 25),
            },
        },
    )
```

- [ ] **Step 5: Run constructor tests**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py -q
```

Expected: PASS.

---

### Task 3: Thread NextActions Through Deployment Validation

**Files:**
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `tests/wf_mcp/workflow_surface/test_deployments.py`

- [ ] **Step 1: Add deployment assertions**

In `test_workflow_surface_validate_deployment_live_check_is_opt_in`, after current payload assertions, add:

```python
    assert payload["next_actions"]["can_continue"] is True
    assert payload["next_actions"]["recommended_next_tool"] == (
        "wf.workflow.run_deployment"
    )
```

In `test_workflow_surface_validates_deployment_dependencies`, after diagnostic assertions, add:

```python
    assert payload["next_actions"]["can_continue"] is True
    assert payload["next_actions"]["recommended_next_tool"] == (
        "wf.workflow.validate_deployment"
    )
    assert payload["next_actions"]["warnings"][0] == "source_missing: context7.personal"
```

If the exact warning uses `context7` instead of `context7.personal`, keep the assertion stable by checking fields separately:

```python
    assert payload["next_actions"]["warnings"]
    assert "source_missing" in payload["next_actions"]["warnings"][0]
```

Prefer the exact assertion only if the implementation returns `bound_source`.

- [ ] **Step 2: Update `validate_deployment` return payload**

In `src/wf_mcp/workflow_surface/handlers.py`, replace the return body in `validate_deployment(...)` with:

```python
        status = "unrunnable" if diagnostics else "runnable"
        diagnostic_payloads = [
            diagnostic.model_dump(mode="json") for diagnostic in diagnostics
        ]
        return {
            "deployment_id": deployment.id,
            "artifact_id": artifact.id,
            "artifact_version": artifact.version,
            "status": status,
            "diagnostics": diagnostic_payloads,
            "next_actions": NextActions.from_deployment_validation(
                deployment_id=deployment.id,
                diagnostics=diagnostics,
            ).model_dump(mode="json"),
        }
```

- [ ] **Step 3: Run deployment tests**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_deployments.py tests/wf_mcp/workflow_surface/test_next_actions.py -q
```

Expected: PASS.

---

### Task 4: Thread NextActions Through Run Payloads

**Files:**
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `tests/wf_mcp/workflow_surface/test_runs.py`

- [ ] **Step 1: Add completed-run assertions**

In `test_workflow_surface_runs_non_interrupting_deployment`, after current run payload assertions, add:

```python
    assert payload["next_actions"]["can_continue"] is False
    assert payload["next_actions"]["recommended_next_tool"] is None
    assert "completed" in payload["next_actions"]["reason"]
```

After the `inspected` assertions in the same test, add:

```python
    assert inspected["next_actions"]["can_continue"] is False
    assert inspected["next_actions"]["recommended_next_tool"] is None
```

- [ ] **Step 2: Add failed-run assertions**

In `test_workflow_surface_failed_deployment_exposes_error_on_run_and_inspect`, after current assertions, add:

```python
    assert payload["next_actions"]["recommended_next_tool"] is None
    assert "before producing trace" in payload["next_actions"]["reason"]
    assert inspected["next_actions"]["recommended_next_tool"] is None
```

This failing artifact currently has `trace_count == 0`, so the safe guidance is diagnostics/error, not `read_run_trace`.

- [ ] **Step 3: Add trace-detail assertion**

In `test_workflow_surface_run_deployment_can_include_trace_detail`, after the current trace assertions, add:

```python
    assert payload["next_actions"]["patch_examples"][0]["request"]["trace_range"][
        "limit"
    ] == 1
```

This confirms completed runs may include bounded trace guidance without making it required.

- [ ] **Step 4: Update `_run_payload`**

In `src/wf_mcp/workflow_surface/handlers.py`, inside `_run_payload(...)`, add `next_actions` to the base `payload` dict:

```python
        "next_actions": NextActions.from_run_result(
            run_id=run_id,
            status=status,
            trace_count=trace_count,
            diagnostics=diagnostics or [],
        ).model_dump(mode="json"),
```

The resulting base payload should include:

```python
    payload = {
        "deployment_id": deployment.id,
        "artifact_id": artifact.id,
        "artifact_version": artifact.version,
        "status": status,
        "run_id": run_id,
        "resume_readiness": resume_readiness,
        "interrupt": interrupt,
        "outcome": outcome,
        "error": error,
        "output": output,
        "diagnostics": [
            diagnostic.model_dump(mode="json") for diagnostic in diagnostics or []
        ],
        "trace_count": trace_count,
        "next_actions": NextActions.from_run_result(
            run_id=run_id,
            status=status,
            trace_count=trace_count,
            diagnostics=diagnostics or [],
        ).model_dump(mode="json"),
    }
```

- [ ] **Step 5: Run run tests**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_runs.py tests/wf_mcp/workflow_surface/test_next_actions.py -q
```

Expected: PASS.

---

### Task 5: Update MCP Output Schema Tests

**Files:**
- Modify: `tests/wf_mcp/server/test_config.py`
- Modify: `tests/wf_mcp/server/test_tools.py`

- [ ] **Step 1: Add schema assertions for deployment/run outputs**

In `tests/wf_mcp/server/test_config.py`, find the existing workflow-surface schema test that checks `create_draft_workspace_from_capability` output contains `next_actions`.

Add assertions for `wf.workflow.validate_deployment` and `wf.workflow.run_deployment` output schemas. Use the same local `by_name` / tool lookup style already in that test file:

```python
validate_deployment = by_name["wf.workflow.validate_deployment"]
run_deployment = by_name["wf.workflow.run_deployment"]

validate_output = validate_deployment.outputSchema
run_output = run_deployment.outputSchema

assert "next_actions" in validate_output["properties"]
assert "recommended_next_tool" in validate_output["properties"]["next_actions"][
    "properties"
]
assert "next_actions" in run_output["properties"]
assert "recommended_next_tool" in run_output["properties"]["next_actions"][
    "properties"
]
```

If this test file uses `tool.outputSchema` through dict access instead of attributes, follow the existing style in the file. Do not assert the whole schema.

- [ ] **Step 2: Add tool description assertion only if output schema exists**

In `tests/wf_mcp/server/test_tools.py`, add a small assertion that `run_deployment.description` or the output schema describes `next_actions` only if that file already inspects output schemas. Do not add fragile full-schema assertions.

If `test_tools.py` only checks input schemas and titles, skip this step.

- [ ] **Step 3: Run server tests**

Run:

```bash
uv run pytest tests/wf_mcp/server/test_config.py tests/wf_mcp/server/test_tools.py -q
```

Expected: PASS.

---

### Task 6: Update Docs

**Files:**
- Modify: `docs/workflow_capabilities.md`

- [ ] **Step 1: Add deployment/run guidance note**

Add this paragraph near the existing `next_actions` explanation:

```markdown
Deployment validation and run lifecycle responses also expose `next_actions`.
For runnable deployments this points to `wf.workflow.run_deployment`; for
unrunnable deployments it points back to validation after the caller repairs
bindings, sources, or schema drift. Failed runs never suggest reading an
unbounded trace; trace guidance always uses a bounded `trace_range`.
```

- [ ] **Step 2: Run docs tests**

Run:

```bash
uv run pytest tests/wf_mcp/server/test_docs.py -q
```

Expected: PASS.

---

### Task 7: Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run focused test set**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_deployments.py tests/wf_mcp/workflow_surface/test_runs.py tests/wf_mcp/server/test_config.py tests/wf_mcp/server/test_tools.py tests/wf_mcp/server/test_docs.py -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting check on touched files**

Run:

```bash
uv run ruff format --check src/wf_mcp/workflow_surface/next_actions.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_deployments.py tests/wf_mcp/workflow_surface/test_runs.py tests/wf_mcp/server/test_config.py tests/wf_mcp/server/test_tools.py
```

Expected: PASS.

- [ ] **Step 3: Run lint on touched files**

Run:

```bash
uv run ruff check src/wf_mcp/workflow_surface/next_actions.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_deployments.py tests/wf_mcp/workflow_surface/test_runs.py tests/wf_mcp/server/test_config.py tests/wf_mcp/server/test_tools.py
```

Expected: PASS.

- [ ] **Step 4: Run type check**

Run:

```bash
uv run basedpyright --level error
```

Expected: `0 errors`.

- [ ] **Step 5: Optional full suite**

Run:

```bash
uv run pytest -q
```

Expected: full suite remains green with the existing skip/xfail count.

---

## Self-Review Checklist

- `next_actions` is present on `validate_deployment` responses.
- `next_actions` is present on all `_run_payload(...)` responses.
- Completed runs do not require another tool.
- Failed runs recommend bounded trace only when a trace exists.
- Interrupted runs recommend `wf.workflow.resume_run`.
- Diagnostics remain authoritative; guidance only summarizes.
- No unbounded trace read is suggested.
- Existing fields remain unchanged.

## Notes For Opencode

- Keep this as an additive UX change.
- Do not make any runtime/deployment behavior depend on `next_actions`.
- Do not add a new tool.
- Do not broaden trace payloads.
- If server schema tests are awkward, prefer field-level assertions over whole-schema equality.
