from __future__ import annotations

from pathlib import Path

import pytest

from wf_api.models import RawWorkflowPlan
from wf_core.models.steps import InputExpressionBinding
from wf_server import build_local_static_workflow_server


def _composite_concat_draft() -> dict[str, object]:
    return {
        "name": "composite_concat_vertical",
        "input_schema": {"type": "object", "properties": {}},
        "state_schema": {
            "type": "object",
            "properties": {
                "foo": {"type": "string", "default": "hello"},
                "text": {"type": "string"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        },
        "start": "concat",
        "steps": {
            "concat": {
                "use": "wf.std.concat",
                "input": [],
                "output": [{"source": "text", "target": "state.text"}],
            }
        },
        "output": [{"path": "state.text", "target": "result"}],
        "routes": {"concat": {"ok": "__end__"}},
    }


@pytest.mark.asyncio
async def test_composite_concat_runs_through_the_platform_registry(
    tmp_path: Path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_draft_workspace(
        workspace_id="composite_concat",
        draft=_composite_concat_draft(),
    )

    authored = await server.api.draft_authoring.set_step_input_bindings(
        workspace_id="composite_concat",
        revision=1,
        step_id="concat",
        bindings=[
            InputExpressionBinding.model_validate(
                {
                    "target": ".",
                    "expression": {
                        "kind": "object",
                        "fields": {
                            "items": {
                                "kind": "array",
                                "items": [
                                    {"kind": "path", "path": "state.foo"},
                                    {"kind": "literal", "value": "wowcool"},
                                ],
                            },
                            "separator": {"kind": "literal", "value": " "},
                        },
                    },
                }
            )
        ],
    )

    assert authored["revision"] == 2
    compiled = await server.api.compile_draft_workspace(
        workspace_id="composite_concat",
    )
    plan = RawWorkflowPlan.model_validate(compiled["compiled_plan"])
    run = await server.context.runtime.run_workflow_from_plan(plan, {})

    assert run.trace[0].resolved_input == {
        "items": ["hello", "wowcool"],
        "separator": " ",
    }
    assert run.output == {"result": "hello wowcool"}
