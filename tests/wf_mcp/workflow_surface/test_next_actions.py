from __future__ import annotations

from wf_artifacts import DependencyDiagnostic, DiagnosticSeverity

from wf_api.next_actions import NextActionTool, NextActions


def test_next_actions_from_high_confidence_wrapper_hints_can_validate() -> None:
    actions = NextActions.from_wrapper_hints(
        workspace_id="echo_workspace",
        revision=3,
        hints={
            "confidence": "high",
            "missing_decisions": [],
            "notes": [],
        },
    )

    dumped = actions.model_dump(mode="json")
    assert dumped["can_continue"] is True
    assert dumped["can_save_now"] is True
    assert dumped["recommended_next_tool"] == (
        NextActionTool.VALIDATE_DRAFT_WORKSPACE.value
    )
    assert "high confidence" in dumped["reason"]
    assert dumped["patch_examples"] == []
    assert dumped["warnings"] == []


def test_next_actions_from_low_confidence_wrapper_hints_can_patch() -> None:
    actions = NextActions.from_wrapper_hints(
        workspace_id="echo_workspace",
        revision=4,
        hints={
            "confidence": "low",
            "missing_decisions": [
                {
                    "kind": "review_nested_output",
                    "message": "Review nested output fields before mapping.",
                },
                {
                    "kind": "confirm_boolean_outcomes",
                    "message": "Boolean fields may be data, not outcomes.",
                },
            ],
            "notes": ["Raw MCP tool output is not workflow-shaped."],
        },
    )

    dumped = actions.model_dump(mode="json")
    assert dumped["can_continue"] is True
    assert dumped["can_save_now"] is False
    assert dumped["recommended_next_tool"] == NextActionTool.PATCH_DRAFT_WORKSPACE.value
    assert "missing wrapper decisions" in dumped["reason"]
    assert dumped["warnings"][0] == "Raw MCP tool output is not workflow-shaped."
    assert len(dumped["patch_examples"]) == 2
    assert dumped["patch_examples"][0]["tool"] == (
        NextActionTool.PATCH_DRAFT_WORKSPACE.value
    )
    assert dumped["patch_examples"][0]["request"]["workspace_id"] == "echo_workspace"
    assert dumped["patch_examples"][0]["request"]["revision"] == 4
    assert dumped["patch_examples"][0]["request"]["patch"][0]["path"] == (
        "/draft/steps/call/output"
    )
    assert dumped["patch_examples"][1]["request"]["patch"] == []


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
    assert dumped["patch_examples"][0]["request"]["trace_range"]["limit"] == 12


def test_next_actions_from_failed_run_caps_large_trace_example() -> None:
    actions = NextActions.from_run_result(
        run_id="run_123",
        status="failed",
        trace_count=100,
        diagnostics=[],
    )

    dumped = actions.model_dump(mode="json")
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


def test_workflow_surface_next_actions_shim_reexports_canonical_model() -> None:
    from wf_api.next_actions import NextActions
    from wf_mcp.workflow_surface.next_actions import NextActions as NextActionsShim

    assert NextActionsShim is NextActions
