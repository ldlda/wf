from __future__ import annotations

import pytest

from wf_artifacts.drafts import compile_workflow_draft, patch_workflow_draft


def test_compile_draft_maps_use_step_to_raw_node_use() -> None:
    plan = compile_workflow_draft(_draft_with_steps([_use_step()]))

    assert plan["name"] == "echo_probe"
    assert plan["start"] == "echo"
    assert plan["nodes"][0]["id"] == "echo"
    assert plan["nodes"][0]["type"] == "node"
    assert plan["nodes"][0]["node"] == "everything.echo"
    assert plan["nodes"][0]["in_map"]["input.message"] == "message"
    assert plan["nodes"][0]["out_map"]["content"] == "state.content"
    assert plan["edges"][0]["to"] == "__end__"


def test_compile_draft_maps_condition_foreach_interrupt_and_join() -> None:
    plan = compile_workflow_draft(
        _draft_with_steps(
            [
                {
                    "id": "route",
                    "kind": "condition",
                    "check": {"op": "exists", "path": "input.items"},
                },
                {
                    "id": "each",
                    "kind": "foreach",
                    "over": "input.items",
                    "as": "item",
                    "mode": "serial",
                    "on_item_error": "collect",
                },
                {
                    "id": "approval",
                    "kind": "interrupt",
                    "interrupt_kind": "approval",
                    "request": {"input.message": "message"},
                    "resume": {"approved": "state.approved"},
                    "outcomes": ["submitted"],
                },
                {"id": "joined", "kind": "join"},
            ],
            edges=[
                {"from": "route", "outcome": "true", "to": "each"},
                {"from": "each", "outcome": "done", "to": "approval"},
                {"from": "approval", "outcome": "submitted", "to": "joined"},
                {"from": "joined", "outcome": "done", "to": "__end__"},
            ],
            start="route",
        )
    )

    assert plan["nodes"][0]["type"] == "condition"
    assert plan["nodes"][0]["check"]["op"] == "exists"
    assert plan["nodes"][1]["type"] == "foreach"
    assert plan["nodes"][1]["as"] == "item"
    assert plan["nodes"][1]["on_item_error"] == "collect"
    assert plan["nodes"][2]["type"] == "interrupt"
    assert plan["nodes"][2]["kind"] == "approval"
    assert plan["nodes"][2]["request_map"]["input.message"] == "message"
    assert plan["nodes"][2]["out_map"]["approved"] == "state.approved"
    assert plan["nodes"][3]["type"] == "join"
    assert plan["edges"][3]["from"] == "joined"


def test_compile_draft_requires_explicit_step_ids() -> None:
    draft = _draft_with_steps([{"kind": "join"}])

    with pytest.raises(ValueError) as exc_info:
        compile_workflow_draft(draft)

    assert "steps[0].id" in str(exc_info.value)


def test_patch_workflow_draft_applies_json_patch_and_validates_result() -> None:
    patched = patch_workflow_draft(
        _draft_with_steps([_use_step()]),
        [
            {
                "op": "replace",
                "path": "/steps/0/in/input.message",
                "value": "text",
            },
            {
                "op": "add",
                "path": "/edges/-",
                "value": {"from": "echo", "outcome": "error", "to": "__end__"},
            },
        ],
    )

    assert patched["status"] == "valid"
    assert patched["draft"]["steps"][0]["in"]["input.message"] == "text"
    assert patched["compiled_plan"]["edges"][1]["outcome"] == "error"


def test_patch_workflow_draft_reports_invalid_patch_without_partial_result() -> None:
    patched = patch_workflow_draft(
        _draft_with_steps([_use_step()]),
        [{"op": "replace", "path": "/steps/99/id", "value": "missing"}],
    )

    assert patched["status"] == "invalid"
    assert patched["diagnostics"][0]["code"] == "patch_invalid"
    assert "draft" not in patched


def _draft_with_steps(
    steps: list[dict[str, object]],
    *,
    edges: list[dict[str, str]] | None = None,
    start: str = "echo",
) -> dict[str, object]:
    return {
        "name": "echo_probe",
        "input_schema": {"type": "object", "properties": {}},
        "state_schema": {"fields": {"content": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {}},
        "start": start,
        "steps": steps,
        "edges": edges or [{"from": "echo", "outcome": "ok", "to": "__end__"}],
    }


def _use_step() -> dict[str, object]:
    return {
        "id": "echo",
        "kind": "use",
        "capability": "everything.echo",
        "in": {"input.message": "message"},
        "out": {"content": "state.content"},
    }
