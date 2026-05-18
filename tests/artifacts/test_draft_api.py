from __future__ import annotations

from wf_artifacts.drafts import compile_workflow_draft, patch_workflow_draft


def test_compile_workflow_draft_returns_raw_core_shape() -> None:
    plan = compile_workflow_draft(_keyed_echo_draft())

    assert plan["nodes"][0]["id"] == "echo"
    assert plan["nodes"][0]["node"] == "demo.echo"
    assert plan["edges"][0]["outcome"] == "ok"


def test_patch_workflow_draft_uses_stable_step_paths() -> None:
    result = patch_workflow_draft(
        _keyed_echo_draft(),
        [
            {
                "op": "replace",
                "path": "/steps/echo/in/input.text",
                "value": "message",
            }
        ],
    )

    assert result["status"] == "valid"
    assert result["draft"]["steps"]["echo"]["in"]["input.text"] == "message"


def _keyed_echo_draft() -> dict[str, object]:
    return {
        "name": "echo",
        "input_schema": {},
        "state_schema": {"fields": {}},
        "output_schema": {},
        "start": "echo",
        "steps": {
            "echo": {
                "use": "demo.echo",
                "in": {"input.text": "text"},
                "out": {"echoed": "state.echoed"},
            }
        },
        "routes": {"echo": {"ok": "__end__"}},
    }
