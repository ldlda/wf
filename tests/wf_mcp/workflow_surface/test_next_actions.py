from __future__ import annotations

from wf_mcp.workflow_surface.next_actions import NextActionTool, NextActions


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
    assert dumped["patch_examples"][0]["tool"] == (
        NextActionTool.PATCH_DRAFT_WORKSPACE.value
    )
    assert dumped["patch_examples"][0]["request"]["workspace_id"] == "echo_workspace"
    assert dumped["patch_examples"][0]["request"]["revision"] == 4
    assert dumped["patch_examples"][0]["request"]["patch"][0]["path"] == (
        "/draft/steps/call/output"
    )
    assert dumped["patch_examples"][1]["request"]["patch"] == []
